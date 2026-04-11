"""
Unit tests for the Stream Processor service.
Tests message validation, schema enforcement, and edge cases.
Run with: pytest tests/ -v
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Patch GCP clients before importing the app
with (
    patch("google.cloud.firestore.AsyncClient"),
    patch("google.cloud.bigquery.Client"),
    patch("opentelemetry.exporter.cloud_trace.CloudTraceSpanExporter"),
):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../services/stream-processor"))
    os.environ.setdefault("GCP_PROJECT_ID", "test-project")
    from main import app, VehicleEvent  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def make_push_envelope(payload: dict) -> dict:
    data_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    return {
        "message": {
            "data": data_b64,
            "messageId": "test-msg-001",
            "publishTime": "2025-01-01T12:00:00Z",
            "attributes": {},
        },
        "subscription": "projects/test/subscriptions/test-sub",
    }


VALID_EVENT = {
    "vehicle_id": "VM-PARIS-001",
    "lat": 48.8566,
    "lng": 2.3522,
    "speed_kmh": 35.0,
    "heading": 90.0,
    "zone": "Paris-1er",
    "event_ts": "2025-01-01T12:00:00+00:00",
    "status": "active",
}


# ── Schema Validation ─────────────────────────────────────────

class TestVehicleEventSchema:
    def test_valid_event_passes(self):
        event = VehicleEvent(**VALID_EVENT)
        assert event.vehicle_id == "VM-PARIS-001"
        assert event.lat == 48.8566

    def test_lat_out_of_range_raises(self):
        with pytest.raises(Exception):
            VehicleEvent(**{**VALID_EVENT, "lat": 95.0})

    def test_lng_out_of_range_raises(self):
        with pytest.raises(Exception):
            VehicleEvent(**{**VALID_EVENT, "lng": 200.0})

    def test_speed_negative_raises(self):
        with pytest.raises(Exception):
            VehicleEvent(**{**VALID_EVENT, "speed_kmh": -5.0})

    def test_speed_too_high_raises(self):
        with pytest.raises(Exception):
            VehicleEvent(**{**VALID_EVENT, "speed_kmh": 500.0})

    def test_invalid_status_raises(self):
        with pytest.raises(Exception):
            VehicleEvent(**{**VALID_EVENT, "status": "flying"})

    def test_idle_status_valid(self):
        event = VehicleEvent(**{**VALID_EVENT, "status": "idle"})
        assert event.status == "idle"

    def test_offline_status_valid(self):
        event = VehicleEvent(**{**VALID_EVENT, "status": "offline"})
        assert event.status == "offline"

    def test_empty_vehicle_id_raises(self):
        with pytest.raises(Exception):
            VehicleEvent(**{**VALID_EVENT, "vehicle_id": ""})


# ── HTTP Endpoints ────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "stream-processor"


class TestPubSubPushEndpoint:
    def test_invalid_json_envelope_returns_400(self, client):
        response = client.post("/pubsub/push", json={"bad": "envelope"})
        assert response.status_code == 400

    def test_invalid_base64_returns_400(self, client):
        response = client.post(
            "/pubsub/push",
            json={
                "message": {
                    "data": "!!!not-valid-base64!!!",
                    "messageId": "m1",
                    "publishTime": "2025-01-01T00:00:00Z",
                },
                "subscription": "projects/p/subscriptions/s",
            },
        )
        assert response.status_code == 400

    def test_schema_violation_returns_422(self, client):
        bad_payload = {**VALID_EVENT, "lat": 999.0}
        envelope = make_push_envelope(bad_payload)
        response = client.post("/pubsub/push", json=envelope)
        assert response.status_code == 422

    @patch("main.fs_client")
    @patch("main.bq_client")
    def test_valid_event_returns_204(self, mock_bq, mock_fs, client):
        mock_fs.collection.return_value.document.return_value.set = AsyncMock(return_value=None)
        mock_bq.insert_rows_json.return_value = []  # no errors

        envelope = make_push_envelope(VALID_EVENT)
        response = client.post("/pubsub/push", json=envelope)
        assert response.status_code == 204
