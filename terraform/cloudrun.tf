locals {
  image_base        = "us-central1-docker.pkg.dev/${var.project_id}/urbanmove"
  # Used for initial Terraform provisioning before CI/CD pushes real images.
  # Cloud Run services are managed by CI/CD after the first apply.
  placeholder_image = "us-docker.pkg.dev/cloudrun/container/hello"
}

# ── Stream Processor (deployed first — Pub/Sub push needs its URL) ──

resource "google_cloud_run_v2_service" "stream_processor" {
  name                = "stream-processor"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.stream_processor.email
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = local.placeholder_image

      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = "urbanmove"
      }
      env {
        name  = "BIGQUERY_TABLE"
        value = "mobility_events"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    }
  }

  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.urbanmove,
    google_service_account.stream_processor,
  ]
}

# ── User Service ──────────────────────────────────────────────

resource "google_cloud_run_v2_service" "user_service" {
  name                = "user-service"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.user_service.email
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = local.placeholder_image

      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name = "GOOGLE_MAPS_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.maps_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.urbanmove,
    google_secret_manager_secret_version.maps_api_key,
  ]
}

# Public access for user service (auth handled by Firebase JWT in app)
resource "google_cloud_run_v2_service_iam_member" "user_service_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.user_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Routing Engine ────────────────────────────────────────────

resource "google_cloud_run_v2_service" "routing_engine" {
  name                = "routing-engine"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.routing_engine.email
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = local.placeholder_image

      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name = "GOOGLE_MAPS_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.maps_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.urbanmove,
    google_secret_manager_secret_version.maps_api_key,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "routing_engine_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.routing_engine.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Analytics Service ─────────────────────────────────────────

resource "google_cloud_run_v2_service" "analytics_service" {
  name                = "analytics-service"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.analytics_service.email
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = local.placeholder_image

      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = "urbanmove"
      }
      env {
        name  = "BIGQUERY_TABLE"
        value = "mobility_events"
      }
    }
  }

  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.urbanmove,
    google_bigquery_dataset.urbanmove,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "analytics_service_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.analytics_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── IoT Simulator (invoked by Cloud Scheduler) ────────────────

resource "google_cloud_run_v2_job" "iot_simulator" {
  name                = "iot-simulator"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.iot_simulator.email

      containers {
        image = local.placeholder_image

        resources {
          limits = { cpu = "1", memory = "512Mi" }
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "PUBSUB_TOPIC"
          value = "urbanmove-raw-events"
        }
        env {
          name  = "NUM_VEHICLES"
          value = "20"
        }
        env {
          name  = "PUBLISH_DURATION_SECONDS"
          value = "240"
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.urbanmove,
    google_pubsub_topic.raw_events,
  ]
}

# ── MLflow Server ─────────────────────────────────────────────

resource "google_cloud_run_v2_service" "mlflow_server" {
  name                = "mlflow-server"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.mlflow_server.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = local.placeholder_image

      resources {
        limits            = { cpu = "1", memory = "1Gi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.mlflow_artifacts.name
      }
      env {
        name  = "MLFLOW_BACKEND_STORE_URI"
        value = "sqlite:////tmp/mlflow.db"
      }
    }
  }

  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.urbanmove,
    google_storage_bucket.mlflow_artifacts,
  ]
}

# MLflow: IAM-protected — only authenticated users
resource "google_cloud_run_v2_service_iam_member" "mlflow_nihal" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.mlflow_server.name
  role     = "roles/run.invoker"
  member   = "user:kpnihal006@gmail.com"
}

# ── Frontend ──────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "frontend" {
  name                = "frontend"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.frontend.email
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = local.placeholder_image

      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "NEXT_PUBLIC_USER_SERVICE_URL"
        value = google_cloud_run_v2_service.user_service.uri
      }
      env {
        name  = "NEXT_PUBLIC_ROUTING_ENGINE_URL"
        value = google_cloud_run_v2_service.routing_engine.uri
      }
      env {
        name  = "NEXT_PUBLIC_ANALYTICS_SERVICE_URL"
        value = google_cloud_run_v2_service.analytics_service.uri
      }
      env {
        name  = "NEXT_PUBLIC_GCP_PROJECT_ID"
        value = var.project_id
      }
    }
  }

  lifecycle {
    ignore_changes = [template]
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.urbanmove,
    google_cloud_run_v2_service.user_service,
    google_cloud_run_v2_service.routing_engine,
    google_cloud_run_v2_service.analytics_service,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
