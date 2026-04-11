# ── Cloud Monitoring ─────────────────────────────────────────

# Uptime checks
resource "google_monitoring_uptime_check_config" "frontend" {
  display_name = "Frontend Uptime"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/"
    port         = "443"
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = replace(google_cloud_run_v2_service.frontend.uri, "https://", "")
    }
  }

  depends_on = [google_cloud_run_v2_service.frontend]
}

resource "google_monitoring_uptime_check_config" "user_service" {
  display_name = "User Service Health"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/health"
    port         = "443"
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = replace(google_cloud_run_v2_service.user_service.uri, "https://", "")
    }
  }

  depends_on = [google_cloud_run_v2_service.user_service]
}

# Alert: Dead-letter topic receives messages (stream processor failures)
resource "google_monitoring_alert_policy" "dead_letter_alert" {
  display_name = "Dead Letter Topic — Stream Processor Failures"
  combiner     = "OR"

  conditions {
    display_name = "Dead letter message count > 0"
    condition_threshold {
      filter          = "resource.type = \"pubsub_subscription\" AND resource.labels.subscription_id = \"urbanmove-dead-letter-inspect\" AND metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = []
  depends_on            = [google_pubsub_subscription.dead_letter_inspect]
}

# Alert: Cloud Run error rate > 5%
resource "google_monitoring_alert_policy" "error_rate_alert" {
  display_name = "Cloud Run — High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "5xx error rate > 5%"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "120s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []
  depends_on            = [google_project_service.apis]
}
