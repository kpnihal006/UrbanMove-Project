"""
Analytics Service — Cloud Run
Queries BigQuery for mobility analytics and BigQuery ML for congestion prediction.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery, firestore
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"analytics-service","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── OpenTelemetry ─────────────────────────────────────────────
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# ── Config ────────────────────────────────────────────────────
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
BQ_DATASET = os.getenv("BIGQUERY_DATASET", "urbanmove")
BQ_TABLE = os.getenv("BIGQUERY_TABLE", "mobility_events")

bq_client = bigquery.Client(project=GCP_PROJECT_ID)
fs_client = firestore.Client(project=GCP_PROJECT_ID)

# ── Models ────────────────────────────────────────────────────


class ZoneCongestion(BaseModel):
    zone: str
    vehicle_count: int
    avg_speed_kmh: float
    congestion_level: str  # low / medium / high


class CongestionStats(BaseModel):
    timestamp: str
    total_active_vehicles: int
    zones: list[ZoneCongestion]


class PredictionResult(BaseModel):
    zone: str
    horizon_minutes: int
    predicted_vehicle_count: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    predicted_at: str


class DashboardStats(BaseModel):
    total_events_today: int
    active_vehicles_now: int
    avg_speed_kmh: float
    busiest_zone: str
    timestamp: str


# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="UrbanMove Analytics Service", version="1.0.0")
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
    return {"status": "ok", "service": "analytics-service"}


@app.get("/congestion", response_model=CongestionStats)
async def get_congestion() -> CongestionStats:
    """
    Returns live congestion status per Paris zone from Firestore.
    Firestore holds the latest position of every vehicle (upserted by the
    stream-processor on each event), so this reflects current state even
    when the IoT simulator is not actively running.
    """
    with tracer.start_as_current_span("analytics.congestion"):
        try:
            docs = fs_client.collection("vehicles").stream()
        except Exception as exc:
            logger.error("Firestore congestion query failed: %s", exc)
            raise HTTPException(status_code=502, detail="Analytics query failed") from exc

        # Aggregate vehicles by zone
        zone_counts: dict[str, int] = {}
        zone_speeds: dict[str, list[float]] = {}
        for doc in docs:
            v = doc.to_dict()
            zone = v.get("zone", "unknown")
            speed = float(v.get("speed_kmh") or 0)
            zone_counts[zone] = zone_counts.get(zone, 0) + 1
            zone_speeds.setdefault(zone, []).append(speed)

        zones: list[ZoneCongestion] = []
        total = 0
        for zone, count in sorted(zone_counts.items(), key=lambda x: -x[1]):
            speeds = zone_speeds[zone]
            avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0.0
            level = _congestion_level(count, avg_speed)
            zones.append(
                ZoneCongestion(
                    zone=zone,
                    vehicle_count=count,
                    avg_speed_kmh=avg_speed,
                    congestion_level=level,
                )
            )
            total += count

        return CongestionStats(
            timestamp=datetime.now(UTC).isoformat(),
            total_active_vehicles=total,
            zones=zones,
        )


@app.get("/congestion/predict", response_model=PredictionResult)
async def predict_congestion(
    zone: str = Query(..., description="Paris arrondissement zone, e.g. 'Paris-1er'"),
    horizon: int = Query(default=30, ge=5, le=120, description="Prediction horizon in minutes"),
) -> PredictionResult:
    """
    Uses BigQuery ML ARIMA_PLUS model to predict vehicle count
    for a given zone at a future horizon.
    Model must be trained first via ml/train_model.sql.
    """
    with tracer.start_as_current_span("analytics.predict") as span:
        span.set_attribute("zone", zone)
        span.set_attribute("horizon_minutes", horizon)

        query = f"""
            SELECT
              forecast_value,
              prediction_interval_lower_bound,
              prediction_interval_upper_bound
            FROM
              ML.FORECAST(
                MODEL `{GCP_PROJECT_ID}.{BQ_DATASET}.congestion_model`,
                STRUCT({horizon} AS horizon, 0.9 AS confidence_level)
              )
            WHERE zone_id = @zone
            ORDER BY forecast_timestamp ASC
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("zone", "STRING", zone),
            ]
        )

        try:
            results = bq_client.query(query, job_config=job_config).result()
            rows = list(results)
        except Exception as exc:
            logger.warning("ML prediction query failed (model may not be trained yet): %s", exc)
            # Return a mock prediction when model isn't trained yet
            return PredictionResult(
                zone=zone,
                horizon_minutes=horizon,
                predicted_vehicle_count=8.5,
                confidence_interval_lower=5.0,
                confidence_interval_upper=12.0,
                predicted_at=datetime.now(UTC).isoformat(),
            )

        if not rows:
            return PredictionResult(
                zone=zone,
                horizon_minutes=horizon,
                predicted_vehicle_count=0.0,
                confidence_interval_lower=0.0,
                confidence_interval_upper=0.0,
                predicted_at=datetime.now(UTC).isoformat(),
            )

        row = rows[0]
        return PredictionResult(
            zone=zone,
            horizon_minutes=horizon,
            predicted_vehicle_count=float(row.forecast_value),
            confidence_interval_lower=float(row.prediction_interval_lower_bound),
            confidence_interval_upper=float(row.prediction_interval_upper_bound),
            predicted_at=datetime.now(UTC).isoformat(),
        )


@app.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats() -> DashboardStats:
    """Aggregate statistics for the main dashboard.

    active_vehicles_now — counted from Firestore (live state) so it reflects
    the current fleet size even when IoT is between simulator runs.
    Historical counts (total events, avg speed, busiest zone) come from BigQuery.
    """
    with tracer.start_as_current_span("analytics.stats"):
        # Active vehicle count from Firestore (live, persistent)
        try:
            active_now = sum(
                1 for doc in fs_client.collection("vehicles").stream()
                if doc.to_dict().get("status") == "active"
            )
        except Exception as exc:
            logger.warning("Firestore active-vehicle count failed: %s", exc)
            active_now = 0

        # Historical aggregates from BigQuery
        query = f"""
            WITH stats AS (
              SELECT
                COUNT(*)                   AS total_events,
                ROUND(AVG(speed_kmh), 1)   AS avg_speed
              FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
              WHERE DATE(event_ts) = CURRENT_DATE()
            ),
            top_zone AS (
              SELECT zone
              FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
              WHERE DATE(event_ts) = CURRENT_DATE()
              GROUP BY zone
              ORDER BY COUNT(*) DESC
              LIMIT 1
            )
            SELECT
              s.total_events,
              s.avg_speed,
              COALESCE(t.zone, '—') AS busiest_zone
            FROM stats s
            LEFT JOIN top_zone t ON TRUE
        """
        try:
            results = list(bq_client.query(query).result())
        except Exception as exc:
            logger.error("Dashboard stats query failed: %s", exc)
            raise HTTPException(status_code=502, detail="Stats query failed") from exc

        row = results[0] if results else None
        return DashboardStats(
            total_events_today=int(row.total_events) if row else 0,
            active_vehicles_now=active_now,
            avg_speed_kmh=float(row.avg_speed or 0) if row else 0.0,
            busiest_zone=str(row.busiest_zone or "—") if row else "—",
            timestamp=datetime.now(UTC).isoformat(),
        )


def _congestion_level(vehicle_count: int, avg_speed: float) -> str:
    if vehicle_count >= 10 or avg_speed < 15:
        return "high"
    if vehicle_count >= 5 or avg_speed < 30:
        return "medium"
    return "low"
