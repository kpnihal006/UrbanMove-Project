# ── Artifact Registry ────────────────────────────────────────

resource "google_artifact_registry_repository" "urbanmove" {
  location      = var.region
  repository_id = "urbanmove"
  description   = "UrbanMove Docker images"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-last-3"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"
    condition {
      older_than   = "604800s" # 7 days
      tag_state    = "UNTAGGED"
    }
  }

  depends_on = [google_project_service.apis]
}
