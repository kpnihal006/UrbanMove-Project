# ── Service Accounts ────────────────────────────────────────

resource "google_service_account" "user_service" {
  account_id   = "sa-user-service"
  display_name = "User Service SA"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "routing_engine" {
  account_id   = "sa-routing-engine"
  display_name = "Routing Engine SA"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "analytics_service" {
  account_id   = "sa-analytics-service"
  display_name = "Analytics Service SA"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "iot_simulator" {
  account_id   = "sa-iot-simulator"
  display_name = "IoT Simulator SA"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "stream_processor" {
  account_id   = "sa-stream-processor"
  display_name = "Stream Processor SA"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "mlflow_server" {
  account_id   = "sa-mlflow-server"
  display_name = "MLflow Server SA"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "frontend" {
  account_id   = "sa-frontend"
  display_name = "Frontend SA"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "cicd" {
  account_id   = "sa-cicd"
  display_name = "CI/CD GitHub Actions SA"
  depends_on   = [google_project_service.apis]
}

# ── IAM Bindings ─────────────────────────────────────────────

# User service: Firestore read/write
resource "google_project_iam_member" "user_service_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.user_service.email}"
}

resource "google_project_iam_member" "user_service_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.user_service.email}"
}

# Routing engine: Firestore read/write + Secret access
resource "google_project_iam_member" "routing_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.routing_engine.email}"
}

resource "google_project_iam_member" "routing_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.routing_engine.email}"
}

# Analytics: BigQuery read + Firestore read
resource "google_project_iam_member" "analytics_bq" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.analytics_service.email}"
}

resource "google_project_iam_member" "analytics_bq_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.analytics_service.email}"
}

resource "google_project_iam_member" "analytics_firestore" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.analytics_service.email}"
}

# IoT Simulator: Pub/Sub publish only
resource "google_project_iam_member" "iot_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.iot_simulator.email}"
}

# Stream Processor: Pub/Sub subscribe + Firestore write + BigQuery write
resource "google_project_iam_member" "processor_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.stream_processor.email}"
}

resource "google_project_iam_member" "processor_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.stream_processor.email}"
}

resource "google_project_iam_member" "processor_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.stream_processor.email}"
}

resource "google_project_iam_member" "processor_bq_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.stream_processor.email}"
}

# MLflow: GCS read/write for artifacts
resource "google_project_iam_member" "mlflow_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.mlflow_server.email}"
}

# CI/CD: Deploy to Cloud Run + push to Artifact Registry
resource "google_project_iam_member" "cicd_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cicd.email}"
}

resource "google_project_iam_member" "cicd_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cicd.email}"
}

resource "google_project_iam_member" "cicd_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cicd.email}"
}

resource "google_project_iam_member" "cicd_storage" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.cicd.email}"
}

# ── Workload Identity Federation ─────────────────────────────
# Allows GitHub Actions to authenticate to GCP without SA keys

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "WIF pool for GitHub Actions CI/CD"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Actions OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == '${var.github_org}/${var.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_binding" "cicd_wif" {
  service_account_id = google_service_account.cicd.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_org}/${var.github_repo}",
  ]
}
