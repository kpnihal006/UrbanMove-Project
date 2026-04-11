"""
Stream Processor — Cloud Run service
Receives Pub/Sub push messages, validates, writes to Firestore + BigQuery.
Replaces Dataflow at zero cost within Cloud Run free tier.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, Response, status
from google.cloud import bigquery, firestore
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field, field_validator

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"stream-processor","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── OpenTelemetry ─────────────────────────────────────────────
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# ── Config ────────────────────────────────────────────────────
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "urbanmove")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE", "mobility_events")

# ── GCP Clients ───────────────────────────────────────────────
fs_client = firestore.AsyncClient(project=GCP_PROJECT_ID)
bq_client = bigquery.Client(project=GCP_PROJECT_ID)
BQ_TABLE_REF = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"

# ── Models ────────────────────────────────────────────────────


class VehicleEvent(BaseModel):
    vehicle_id: str = Field(..., min_length=1, max_length=64)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    speed_kmh: float = Field(..., ge=0.0, le=300.0)
    heading: float = Field(..., ge=0.0, le=360.0)
    zone: str = Field(..., min_length=1, max_length=32)
    event_ts: str
    status: str = Field(default="active")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"active", "idle", "offline"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class PubSubMessage(BaseModel):
    model_config = {"populate_by_name": True}

    data: str  # base64-encoded JSON
    message_id: str = Field(alias="messageId")
    publish_time: str = Field(alias="publishTime")
    attributes: dict[str, str] = Field(default_factory=dict)


class PubSubPushEnvelope(BaseModel):
    message: PubSubMessage
    subscription: str


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="UrbanMove Stream Processor",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)
FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "stream-processor"}


@app.post("/pubsub/push")
async def handle_pubsub_push(request: Request) -> Response:
    """
    Receives Pub/Sub push messages.
    Returns 204 on success, 4xx to trigger dead-letter after max retries.
    """
    with tracer.start_as_current_span("pubsub.push.handle") as span:
        body = await request.json()

        try:
            envelope = PubSubPushEnvelope(**body)
        except Exception as exc:
            logger.error("Invalid Pub/Sub envelope: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid envelope") from exc

        # Decode base64 message data
        try:
            raw = base64.b64decode(envelope.message.data).decode("utf-8")
            payload = json.loads(raw)
        except Exception as exc:
            logger.error("Failed to decode message data: %s", exc)
            raise HTTPException(status_code=400, detail="Undecodable message") from exc

        # Validate against schema
        try:
            event = VehicleEvent(**payload)
        except Exception as exc:
            logger.warning(
                "Schema validation failed for message %s: %s",
                envelope.message.message_id,
                exc,
            )
            raise HTTPException(status_code=422, detail=f"Schema error: {exc}") from exc

        span.set_attribute("vehicle.id", event.vehicle_id)
        span.set_attribute("vehicle.zone", event.zone)

        ingested_at = datetime.now(UTC).isoformat()

        # Write to Firestore (live state — overwrite by vehicle_id)
        await _write_firestore(event)

        # Stream insert to BigQuery (historical record)
        _write_bigquery(event, ingested_at)

        logger.info(
            "Processed event vehicle=%s zone=%s ts=%s",
            event.vehicle_id,
            event.zone,
            event.event_ts,
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _write_firestore(event: VehicleEvent) -> None:
    """Upsert vehicle live position in Firestore."""
    doc_ref = fs_client.collection("vehicles").document(event.vehicle_id)
    await doc_ref.set(
        {
            "vehicle_id": event.vehicle_id,
            "lat": event.lat,
            "lng": event.lng,
            "speed_kmh": event.speed_kmh,
            "heading": event.heading,
            "zone": event.zone,
            "status": event.status,
            "event_ts": event.event_ts,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )


def _write_bigquery(event: VehicleEvent, ingested_at: str) -> None:
    """Insert one row into BigQuery via streaming insert."""
    rows = [
        {
            "vehicle_id": event.vehicle_id,
            "lat": event.lat,
            "lng": event.lng,
            "speed_kmh": event.speed_kmh,
            "heading": event.heading,
            "zone": event.zone,
            "status": event.status,
            "event_ts": event.event_ts,
            "ingested_at": ingested_at,
        }
    ]
    errors = bq_client.insert_rows_json(BQ_TABLE_REF, rows)
    if errors:
        logger.error("BigQuery insert errors: %s", errors)
        raise RuntimeError(f"BigQuery streaming insert failed: {errors}")
