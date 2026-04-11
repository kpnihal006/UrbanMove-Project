"""
IoT Simulator — Cloud Run Job
Generates realistic vehicle GPS events for 20 vehicles in Paris.
Publishes to Cloud Pub/Sub for PUBLISH_DURATION_SECONDS seconds.
Triggered by Cloud Scheduler every 5 minutes.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from google.cloud import pubsub_v1

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"iot-simulator","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC", "urbanmove-raw-events")
NUM_VEHICLES = int(os.getenv("NUM_VEHICLES", "20"))
PUBLISH_DURATION_SECONDS = int(os.getenv("PUBLISH_DURATION_SECONDS", "240"))
PUBLISH_INTERVAL_SECONDS = 2.0

# ── Paris zones (arrondissements) ─────────────────────────────
PARIS_ZONES = [
    {"name": "Paris-1er",  "lat": 48.8600, "lng": 2.3477, "radius": 0.006},
    {"name": "Paris-2eme", "lat": 48.8673, "lng": 2.3500, "radius": 0.005},
    {"name": "Paris-3eme", "lat": 48.8630, "lng": 2.3590, "radius": 0.005},
    {"name": "Paris-4eme", "lat": 48.8534, "lng": 2.3559, "radius": 0.006},
    {"name": "Paris-5eme", "lat": 48.8462, "lng": 2.3472, "radius": 0.006},
    {"name": "Paris-6eme", "lat": 48.8496, "lng": 2.3337, "radius": 0.006},
    {"name": "Paris-7eme", "lat": 48.8566, "lng": 2.3141, "radius": 0.007},
    {"name": "Paris-8eme", "lat": 48.8743, "lng": 2.3082, "radius": 0.008},
    {"name": "Paris-9eme", "lat": 48.8766, "lng": 2.3376, "radius": 0.006},
    {"name": "Paris-10eme","lat": 48.8762, "lng": 2.3590, "radius": 0.007},
    {"name": "Paris-11eme","lat": 48.8593, "lng": 2.3752, "radius": 0.008},
    {"name": "Paris-12eme","lat": 48.8417, "lng": 2.3869, "radius": 0.010},
    {"name": "Paris-13eme","lat": 48.8304, "lng": 2.3565, "radius": 0.010},
    {"name": "Paris-14eme","lat": 48.8283, "lng": 2.3271, "radius": 0.009},
    {"name": "Paris-15eme","lat": 48.8420, "lng": 2.2966, "radius": 0.012},
    {"name": "Paris-16eme","lat": 48.8637, "lng": 2.2758, "radius": 0.014},
    {"name": "Paris-17eme","lat": 48.8887, "lng": 2.3130, "radius": 0.010},
    {"name": "Paris-18eme","lat": 48.8920, "lng": 2.3439, "radius": 0.010},
    {"name": "Paris-19eme","lat": 48.8830, "lng": 2.3832, "radius": 0.010},
    {"name": "Paris-20eme","lat": 48.8636, "lng": 2.3977, "radius": 0.010},
]


@dataclass
class Vehicle:
    vehicle_id: str
    lat: float
    lng: float
    heading: float  # degrees 0-360
    speed_kmh: float
    zone: str
    status: str = "active"
    _idle_counter: int = field(default=0, repr=False)

    def move(self) -> None:
        """Simulate realistic vehicle movement within Paris streets."""
        # Random idle chance (15%)
        if random.random() < 0.15:
            self._idle_counter = random.randint(1, 3)

        if self._idle_counter > 0:
            self.status = "idle"
            self.speed_kmh = 0.0
            self._idle_counter -= 1
            return

        self.status = "active"
        # Speed varies: 5-60 km/h in urban Paris
        self.speed_kmh = random.gauss(25, 12)
        self.speed_kmh = max(5.0, min(60.0, self.speed_kmh))

        # Slight heading drift (±15° per tick)
        self.heading = (self.heading + random.gauss(0, 15)) % 360

        # Convert speed to coordinate delta (approximate)
        # At Paris latitude: 1 degree lat ≈ 111km, 1 degree lng ≈ 73km
        dt_seconds = PUBLISH_INTERVAL_SECONDS
        distance_km = self.speed_kmh * (dt_seconds / 3600)
        delta_lat = distance_km / 111.0 * math.cos(math.radians(self.heading))
        delta_lng = distance_km / 73.0  * math.sin(math.radians(self.heading))

        self.lat += delta_lat
        self.lng += delta_lng

        # Keep within Paris bounding box
        self.lat = max(48.815, min(48.905, self.lat))
        self.lng = max(2.224,  min(2.470, self.lng))

        # Update zone based on new position
        self.zone = _nearest_zone(self.lat, self.lng)

    def to_event(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "lat": round(self.lat, 6),
            "lng": round(self.lng, 6),
            "speed_kmh": round(self.speed_kmh, 1),
            "heading": round(self.heading, 1),
            "zone": self.zone,
            "event_ts": datetime.now(UTC).isoformat(),
            "status": self.status,
        }


def _nearest_zone(lat: float, lng: float) -> str:
    """Return the closest arrondissement name for given coordinates."""
    min_dist = float("inf")
    nearest = "Paris-1er"
    for z in PARIS_ZONES:
        dist = math.sqrt((lat - z["lat"]) ** 2 + (lng - z["lng"]) ** 2)
        if dist < min_dist:
            min_dist = dist
            nearest = z["name"]
    return nearest


def _init_vehicles(count: int) -> list[Vehicle]:
    vehicles = []
    for i in range(count):
        zone = PARIS_ZONES[i % len(PARIS_ZONES)]
        lat = zone["lat"] + random.uniform(-zone["radius"], zone["radius"])
        lng = zone["lng"] + random.uniform(-zone["radius"], zone["radius"])
        vehicles.append(Vehicle(
            vehicle_id=f"VM-PARIS-{i+1:03d}",
            lat=lat,
            lng=lng,
            heading=random.uniform(0, 360),
            speed_kmh=random.uniform(10, 40),
            zone=zone["name"],
        ))
    return vehicles


def main() -> None:
    logger.info(
        "IoT Simulator starting: vehicles=%d duration=%ds interval=%ss",
        NUM_VEHICLES, PUBLISH_DURATION_SECONDS, PUBLISH_INTERVAL_SECONDS,
    )

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GCP_PROJECT_ID, PUBSUB_TOPIC)
    vehicles = _init_vehicles(NUM_VEHICLES)

    end_time = time.monotonic() + PUBLISH_DURATION_SECONDS
    published = 0
    errors = 0

    while time.monotonic() < end_time:
        tick_start = time.monotonic()

        futures = []
        for vehicle in vehicles:
            vehicle.move()
            event = vehicle.to_event()
            data = json.dumps(event).encode("utf-8")
            try:
                future = publisher.publish(topic_path, data=data)
                futures.append(future)
            except Exception as exc:
                logger.error("Publish error vehicle=%s: %s", vehicle.vehicle_id, exc)
                errors += 1

        # Wait for all publishes in this tick
        for future in futures:
            try:
                future.result(timeout=5)
                published += 1
            except Exception as exc:
                logger.error("Publish future failed: %s", exc)
                errors += 1

        tick_elapsed = time.monotonic() - tick_start
        sleep_time = max(0, PUBLISH_INTERVAL_SECONDS - tick_elapsed)
        time.sleep(sleep_time)

    logger.info(
        "IoT Simulator finished: published=%d errors=%d",
        published, errors,
    )


if __name__ == "__main__":
    main()
