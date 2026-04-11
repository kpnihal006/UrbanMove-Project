# ── BigQuery ─────────────────────────────────────────────────

resource "google_bigquery_dataset" "urbanmove" {
  dataset_id                 = "urbanmove"
  friendly_name              = "UrbanMove Mobility Dataset"
  description                = "Real-time and historical mobility event data for Paris"
  location                   = "US"  # US multi-region for best free tier coverage
  delete_contents_on_destroy = true
  depends_on                 = [google_project_service.apis]
}

# Main mobility events table — partitioned by day for cost-efficient queries
resource "google_bigquery_table" "mobility_events" {
  dataset_id          = google_bigquery_dataset.urbanmove.dataset_id
  table_id            = "mobility_events"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "event_ts"
  }

  clustering = ["zone", "vehicle_id"]

  schema = jsonencode([
    { name = "vehicle_id", type = "STRING",    mode = "REQUIRED", description = "Unique vehicle identifier" },
    { name = "lat",        type = "FLOAT64",   mode = "REQUIRED", description = "Latitude (WGS84)" },
    { name = "lng",        type = "FLOAT64",   mode = "REQUIRED", description = "Longitude (WGS84)" },
    { name = "speed_kmh",  type = "FLOAT64",   mode = "NULLABLE", description = "Speed in km/h" },
    { name = "heading",    type = "FLOAT64",   mode = "NULLABLE", description = "Compass heading 0-360" },
    { name = "zone",       type = "STRING",    mode = "REQUIRED", description = "Paris arrondissement zone" },
    { name = "event_ts",   type = "TIMESTAMP", mode = "REQUIRED", description = "Event timestamp" },
    { name = "status",     type = "STRING",    mode = "NULLABLE", description = "Vehicle status: active/idle/offline" },
    { name = "ingested_at",type = "TIMESTAMP", mode = "NULLABLE", description = "Stream processor ingestion time" }
  ])
}

# BigQuery ML — Congestion prediction model
# Trained via ml/train_model.sql after mobility_events has data
# CREATE OR REPLACE MODEL `urbanmove.congestion_model` is run via BigQuery job, not Terraform
