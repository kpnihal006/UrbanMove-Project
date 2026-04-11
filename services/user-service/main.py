"""
User Service — Cloud Run
Handles user registration, profile management, trip records.
JWT verification via Firebase Admin SDK.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import firebase_admin
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import auth
from google.cloud import firestore
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"user-service","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── OpenTelemetry ─────────────────────────────────────────────
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
trace.set_tracer_provider(tracer_provider)

# ── Firebase Admin ────────────────────────────────────────────
if not firebase_admin._apps:
    firebase_admin.initialize_app()

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
fs_client = firestore.AsyncClient(project=GCP_PROJECT_ID)

# ── Models ────────────────────────────────────────────────────


class UserProfile(BaseModel):
    uid: str
    email: str
    display_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpdateProfileRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)


class TripRecord(BaseModel):
    origin_lat: float = Field(..., ge=-90.0, le=90.0)
    origin_lng: float = Field(..., ge=-180.0, le=180.0)
    dest_lat: float = Field(..., ge=-90.0, le=90.0)
    dest_lng: float = Field(..., ge=-180.0, le=180.0)
    origin_name: str | None = None
    dest_name: str | None = None


# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="UrbanMove User Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth dependency ───────────────────────────────────────────


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Verify Firebase ID token from Authorization: Bearer <token>."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


# ── Routes ───────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "user-service"}


@app.post("/users/sync", response_model=UserProfile)
async def sync_user(user: dict = Depends(get_current_user)) -> UserProfile:  # noqa: B008
    """
    Called after Firebase login to ensure user doc exists in Firestore.
    Creates on first login, returns existing profile on subsequent calls.
    """
    uid = user["uid"]
    doc_ref = fs_client.collection("users").document(uid)
    doc = await doc_ref.get()
    now = datetime.now(UTC).isoformat()

    if not doc.exists:
        profile_data = {
            "uid": uid,
            "email": user.get("email", ""),
            "display_name": user.get("name", ""),
            "created_at": now,
            "updated_at": now,
        }
        await doc_ref.set(profile_data)
        logger.info("Created new user profile uid=%s", uid)
        return UserProfile(**profile_data)

    data = doc.to_dict() or {}
    return UserProfile(**data)


@app.get("/users/me", response_model=UserProfile)
async def get_my_profile(user: dict = Depends(get_current_user)) -> UserProfile:  # noqa: B008
    uid = user["uid"]
    doc = await fs_client.collection("users").document(uid).get()
    if not doc.exists:
        raise HTTPException(
            status_code=404,
            detail="User profile not found. Call /users/sync first.",
        )
    return UserProfile(**(doc.to_dict() or {}))


@app.patch("/users/me", response_model=UserProfile)
async def update_my_profile(
    body: UpdateProfileRequest,
    user: dict = Depends(get_current_user),  # noqa: B008
) -> UserProfile:
    uid = user["uid"]
    now = datetime.now(UTC).isoformat()
    doc_ref = fs_client.collection("users").document(uid)
    await doc_ref.update({"display_name": body.display_name, "updated_at": now})
    doc = await doc_ref.get()
    return UserProfile(**(doc.to_dict() or {}))


@app.post("/trips", status_code=status.HTTP_201_CREATED)
async def create_trip(
    trip: TripRecord,
    user: dict = Depends(get_current_user),  # noqa: B008
) -> dict:
    uid = user["uid"]
    now = datetime.now(UTC).isoformat()
    trip_ref = fs_client.collection("trips").document()
    data = {
        "trip_id": trip_ref.id,
        "user_id": uid,
        "origin_lat": trip.origin_lat,
        "origin_lng": trip.origin_lng,
        "dest_lat": trip.dest_lat,
        "dest_lng": trip.dest_lng,
        "origin_name": trip.origin_name,
        "dest_name": trip.dest_name,
        "created_at": now,
    }
    await trip_ref.set(data)
    logger.info("Saved trip trip_id=%s user=%s", trip_ref.id, uid)
    return {"trip_id": trip_ref.id, "created_at": now}


@app.get("/trips")
async def get_my_trips(user: dict = Depends(get_current_user)) -> list[dict]:  # noqa: B008
    uid = user["uid"]
    query = (
        fs_client.collection("trips")
        .where("user_id", "==", uid)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(20)
    )
    docs = query.stream()
    return [doc.to_dict() async for doc in docs]
