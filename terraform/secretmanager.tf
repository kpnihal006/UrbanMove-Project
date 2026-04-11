# ── Secret Manager ───────────────────────────────────────────

resource "google_secret_manager_secret" "maps_api_key" {
  secret_id = "google-maps-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "maps_api_key" {
  secret      = google_secret_manager_secret.maps_api_key.id
  secret_data = var.google_maps_api_key
}

resource "google_secret_manager_secret" "firebase_api_key" {
  secret_id = "firebase-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "firebase_api_key" {
  secret      = google_secret_manager_secret.firebase_api_key.id
  secret_data = var.firebase_api_key
}
