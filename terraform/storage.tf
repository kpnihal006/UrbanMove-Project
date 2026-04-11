# ── GCS Buckets ──────────────────────────────────────────────

# Terraform state backend bucket (create manually before terraform init)
# gcloud storage buckets create gs://urbanmove-project-493010-tfstate --location=us-central1

# MLflow artifacts
resource "google_storage_bucket" "mlflow_artifacts" {
  name          = "${var.project_id}-mlflow-artifacts"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = 90 }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

# General exports and backups
resource "google_storage_bucket" "exports" {
  name          = "${var.project_id}-exports"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition { age = 30 }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  depends_on = [google_project_service.apis]
}
