output "frontend_url" {
  description = "Public URL of the UrbanMove web dashboard"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "user_service_url" {
  description = "User Service Cloud Run URL"
  value       = google_cloud_run_v2_service.user_service.uri
}

output "routing_engine_url" {
  description = "Routing Engine Cloud Run URL"
  value       = google_cloud_run_v2_service.routing_engine.uri
}

output "analytics_service_url" {
  description = "Analytics Service Cloud Run URL"
  value       = google_cloud_run_v2_service.analytics_service.uri
}

output "mlflow_server_url" {
  description = "MLflow Tracking Server URL (IAM-protected)"
  value       = google_cloud_run_v2_service.mlflow_server.uri
}

output "stream_processor_url" {
  description = "Stream Processor URL (used by Pub/Sub push subscription)"
  value       = google_cloud_run_v2_service.stream_processor.uri
}

output "artifact_registry_host" {
  description = "Artifact Registry repository URI for Docker push"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/urbanmove"
}

output "workload_identity_provider" {
  description = "WIF provider — paste this into GitHub Actions secrets as GCP_WIF_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "cicd_service_account" {
  description = "CI/CD service account email — paste into GitHub Actions secrets as GCP_SA_EMAIL"
  value       = google_service_account.cicd.email
}

output "mlflow_artifacts_bucket" {
  description = "GCS bucket for MLflow artifact storage"
  value       = google_storage_bucket.mlflow_artifacts.name
}
