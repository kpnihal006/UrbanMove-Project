"""
Locust load test for UrbanMove Cloud Run services.

Usage (against deployed GCP services):
    locust --headless -u 50 -r 5 --run-time 120s \
           --host https://user-service-HASH-uc.a.run.app \
           -f tests/locustfile.py

Usage (against local docker-compose):
    locust --headless -u 20 -r 2 --run-time 60s \
           --host http://localhost:8001 \
           -f tests/locustfile.py

The test shows Cloud Run auto-scaling under load.
Watch Cloud Monitoring instance count climb and scale back to 0 after.
"""

import os
import random

from locust import HttpUser, between, task


ANALYTICS_URL = os.getenv(
    "ANALYTICS_SERVICE_URL",
    "https://analytics-service-replace-uc.a.run.app",
)
ROUTING_URL = os.getenv(
    "ROUTING_ENGINE_URL",
    "https://routing-engine-replace-uc.a.run.app",
)

# Paris bounding box
LAT_MIN, LAT_MAX = 48.815, 48.905
LNG_MIN, LNG_MAX = 2.224, 2.470

PARIS_ZONES = [
    "Paris-1er", "Paris-2eme", "Paris-3eme", "Paris-4eme", "Paris-5eme",
    "Paris-6eme", "Paris-7eme", "Paris-8eme", "Paris-9eme", "Paris-10eme",
]


def rand_lat() -> float:
    return round(random.uniform(LAT_MIN, LAT_MAX), 6)


def rand_lng() -> float:
    return round(random.uniform(LNG_MIN, LNG_MAX), 6)


class AnalyticsUser(HttpUser):
    """Simulates ops dashboard operator polling analytics endpoints."""
    wait_time = between(1, 3)
    host = ANALYTICS_URL

    @task(4)
    def get_congestion(self) -> None:
        self.client.get("/congestion", name="GET /congestion")

    @task(2)
    def get_stats(self) -> None:
        self.client.get("/stats", name="GET /stats")

    @task(1)
    def get_prediction(self) -> None:
        zone = random.choice(PARIS_ZONES)
        horizon = random.choice([15, 30, 60])
        self.client.get(
            f"/congestion/predict?zone={zone}&horizon={horizon}",
            name="GET /congestion/predict",
        )

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="GET /health")


class RoutingUser(HttpUser):
    """Simulates mobile users requesting route recommendations."""
    wait_time = between(2, 5)
    host = ROUTING_URL

    @task(5)
    def get_route(self) -> None:
        self.client.get(
            f"/route?origin_lat={rand_lat()}&origin_lng={rand_lng()}"
            f"&dest_lat={rand_lat()}&dest_lng={rand_lng()}&mode=driving",
            name="GET /route",
        )

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="GET /health")
