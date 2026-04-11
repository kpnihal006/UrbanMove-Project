"""
Routing Engine — Cloud Run
Calls Google Maps Directions API to compute optimal routes in Paris.
Caches results in Firestore to stay within Maps API free credit.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"routing-engine","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── OpenTelemetry ─────────────────────────────────────────────
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# ── Config ────────────────────────────────────────────────────
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GOOGLE_MAPS_API_KEY = os.environ["GOOGLE_MAPS_API_KEY"]
MAPS_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
CACHE_TTL_SECONDS = 300  # 5-minute route cache

fs_client = firestore.AsyncClient(project=GCP_PROJECT_ID)

# ── Models ────────────────────────────────────────────────────


class RouteStep(BaseModel):
    instruction: str
    distance_m: int
    duration_s: int
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float


class RouteResponse(BaseModel):
    route_id: str
    origin: str
    destination: str
    total_distance_m: int
    total_duration_s: int
    summary: str
    steps: list[RouteStep]
    polyline: str
    cached: bool = False
    computed_at: str


# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="UrbanMove Routing Engine", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "routing-engine"}


@app.get("/route", response_model=RouteResponse)
async def get_route(
    origin_lat: float = Query(..., ge=48.7, le=49.1, description="Origin latitude (Paris area)"),
    origin_lng: float = Query(..., ge=2.1, le=2.6, description="Origin longitude (Paris area)"),
    dest_lat: float = Query(..., ge=48.7, le=49.1, description="Destination latitude"),
    dest_lng: float = Query(..., ge=2.1, le=2.6, description="Destination longitude"),
    mode: str = Query(default="driving", regex="^(driving|walking|bicycling|transit)$"),
) -> RouteResponse:
    """
    Compute optimal route between two Paris coordinates.
    Results are cached in Firestore for 5 minutes.
    """
    with tracer.start_as_current_span("routing.get_route") as span:
        # Generate cache key
        cache_key = _make_cache_key(origin_lat, origin_lng, dest_lat, dest_lng, mode)
        span.set_attribute("route.cache_key", cache_key)

        # Check Firestore cache
        cached = await _get_cached_route(cache_key)
        if cached:
            logger.info("Cache hit for route %s", cache_key)
            return RouteResponse(**{**cached, "cached": True})

        # Call Google Maps Directions API
        origin = f"{origin_lat},{origin_lng}"
        destination = f"{dest_lat},{dest_lng}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                MAPS_DIRECTIONS_URL,
                params={
                    "origin": origin,
                    "destination": destination,
                    "mode": mode,
                    "region": "fr",
                    "language": "en",
                    "key": GOOGLE_MAPS_API_KEY,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "OK":
            logger.error("Maps API error: %s", data.get("status"))
            raise HTTPException(
                status_code=502,
                detail=f"Maps API returned status: {data.get('status')}",
            )

        route = _parse_directions_response(data, cache_key, origin, destination)

        # Cache in Firestore
        await _cache_route(cache_key, route)

        logger.info(
            "Computed route origin=%s dest=%s distance=%dm duration=%ds",
            origin,
            destination,
            route.total_distance_m,
            route.total_duration_s,
        )
        return route


def _make_cache_key(lat1: float, lng1: float, lat2: float, lng2: float, mode: str) -> str:
    raw = f"{round(lat1, 4)}:{round(lng1, 4)}:{round(lat2, 4)}:{round(lng2, 4)}:{mode}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]  # noqa: S324


def _parse_directions_response(data: dict, route_id: str, origin: str, dest: str) -> RouteResponse:
    leg = data["routes"][0]["legs"][0]
    steps: list[RouteStep] = []
    for step in leg["steps"]:
        steps.append(
            RouteStep(
                instruction=step["html_instructions"],
                distance_m=step["distance"]["value"],
                duration_s=step["duration"]["value"],
                start_lat=step["start_location"]["lat"],
                start_lng=step["start_location"]["lng"],
                end_lat=step["end_location"]["lat"],
                end_lng=step["end_location"]["lng"],
            )
        )
    return RouteResponse(
        route_id=route_id,
        origin=origin,
        destination=dest,
        total_distance_m=leg["distance"]["value"],
        total_duration_s=leg["duration"]["value"],
        summary=data["routes"][0].get("summary", ""),
        steps=steps,
        polyline=data["routes"][0]["overview_polyline"]["points"],
        cached=False,
        computed_at=datetime.now(UTC).isoformat(),
    )


async def _get_cached_route(cache_key: str) -> dict | None:
    doc = await fs_client.collection("route_cache").document(cache_key).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    # Check TTL
    cached_at = datetime.fromisoformat(data.get("computed_at", "2000-01-01T00:00:00+00:00"))
    age = (datetime.now(UTC) - cached_at).total_seconds()
    if age > CACHE_TTL_SECONDS:
        return None
    return data


async def _cache_route(cache_key: str, route: RouteResponse) -> None:
    await fs_client.collection("route_cache").document(cache_key).set(route.model_dump())
