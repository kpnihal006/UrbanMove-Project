# ── Cloud Scheduler ──────────────────────────────────────────
# Triggers the IoT Simulator job every 5 minutes for demo purposes

resource "google_cloud_scheduler_job" "iot_simulator_trigger" {
  name        = "iot-simulator-trigger"
  description = "Triggers the IoT Simulator Cloud Run Job every 5 minutes"
  schedule    = "*/5 * * * *"
  time_zone   = "Europe/Paris"
  region      = var.region

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.iot_simulator.name}:run"

    oauth_token {
      service_account_email = google_service_account.iot_simulator.email
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_job.iot_simulator,
  ]
}
