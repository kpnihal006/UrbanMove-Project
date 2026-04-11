# ── Firestore ────────────────────────────────────────────────

resource "google_firestore_database" "urbanmove" {
  name        = "(default)"
  location_id = "us-central1"
  type        = "FIRESTORE_NATIVE"

  # Point-in-time recovery: 7-day window
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"

  depends_on = [google_project_service.apis]
}

# Composite indexes for common queries
resource "google_firestore_index" "vehicles_by_zone" {
  collection = "vehicles"
  fields {
    field_path = "zone"
    order      = "ASCENDING"
  }
  fields {
    field_path = "updated_at"
    order      = "DESCENDING"
  }
  depends_on = [google_firestore_database.urbanmove]
}

resource "google_firestore_index" "trips_by_user" {
  collection = "trips"
  fields {
    field_path = "user_id"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
  depends_on = [google_firestore_database.urbanmove]
}
