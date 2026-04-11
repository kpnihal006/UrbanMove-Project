# ── Pub/Sub ──────────────────────────────────────────────────

# Dead-letter topic (created first, referenced by main topic subscription)
resource "google_pubsub_topic" "dead_letter" {
  name       = "urbanmove-dead-letter"
  depends_on = [google_project_service.apis]
}

# Dead-letter subscription (to retain failed messages for inspection)
resource "google_pubsub_subscription" "dead_letter_inspect" {
  name  = "urbanmove-dead-letter-inspect"
  topic = google_pubsub_topic.dead_letter.name

  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = false
  ack_deadline_seconds       = 60
}

# Raw events topic
resource "google_pubsub_topic" "raw_events" {
  name       = "urbanmove-raw-events"
  depends_on = [google_project_service.apis]

  schema_settings {
    schema   = google_pubsub_schema.vehicle_event.id
    encoding = "JSON"
  }
}

# Avro schema for vehicle events
resource "google_pubsub_schema" "vehicle_event" {
  name       = "vehicle-event-schema"
  type       = "AVRO"
  definition = jsonencode({
    type = "record"
    name = "VehicleEvent"
    fields = [
      { name = "vehicle_id", type = "string" },
      { name = "lat",        type = "double" },
      { name = "lng",        type = "double" },
      { name = "speed_kmh",  type = "float"  },
      { name = "heading",    type = "float"  },
      { name = "zone",       type = "string" },
      { name = "event_ts",   type = "string" },
      { name = "status",     type = "string" }
    ]
  })
  depends_on = [google_project_service.apis]
}

# Push subscription → Stream Processor Cloud Run function
resource "google_pubsub_subscription" "stream_processor_push" {
  name  = "urbanmove-stream-processor-push"
  topic = google_pubsub_topic.raw_events.name

  ack_deadline_seconds       = 60
  message_retention_duration = "86400s" # 1 day replay window
  retain_acked_messages      = false

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.stream_processor.uri}/pubsub/push"

    oidc_token {
      service_account_email = google_service_account.stream_processor.email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  depends_on = [google_cloud_run_v2_service.stream_processor]
}

# Allow Pub/Sub to invoke the stream processor
resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.stream_processor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.stream_processor.email}"
}
