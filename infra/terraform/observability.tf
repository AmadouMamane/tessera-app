# Logging retention, log-based metrics, Cloud Monitoring dashboard, and alert
# policies for the Tessera Cloud Run service.

# ── Log retention ────────────────────────────────────────────────────────────

resource "google_logging_project_bucket_config" "default" {
  project          = var.project_id
  location         = "global"
  bucket_id        = "_Default"
  retention_days   = var.log_retention_days
  enable_analytics = true
}

# ── Log sink — audit trail ────────────────────────────────────────────────────
# Routes all Tessera audit log entries to a dedicated Cloud Storage bucket so
# they can be exported, archived, and reviewed independently of the main log.

resource "google_logging_project_sink" "tessera_audit" {
  name        = "${var.service_name}-audit-sink"
  description = "Routes tessera.guard.audit log entries for compliance archiving."

  destination = "storage.googleapis.com/${google_storage_bucket.audit_logs.name}"

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.service_name}"
    jsonPayload.type="tessera.guard.audit"
  EOT

  # Grant the sink's writer identity write access to the bucket (see IAM below).
  unique_writer_identity = true
}

resource "google_storage_bucket" "audit_logs" {
  name                        = "${var.project_id}-${var.service_name}-audit"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  labels = local.common_labels

  # Audit 2026-07-10, P2 `infra-hardening` (observability.tf:281): the bucket deleted at 365
  # days with NO retention policy, so an object could also be deleted at any time BEFORE
  # then — by anyone with the role, including an attacker covering their tracks. An audit
  # trail you can quietly shorten is not tamper-evident, which is the one property this
  # product sells. The lock makes early deletion impossible even for a project owner.
  #
  # NOTE: `is_locked = true` is IRREVERSIBLE once applied — the retention period can be
  # raised but never lowered, and the bucket cannot be deleted until every object ages out.
  # That is the intent (it is what makes the trail opposable), and it is why this stays on
  # the branch for an explicit human decision rather than being merged autonomously.
  retention_policy {
    retention_period = var.audit_retention_days * 24 * 60 * 60
    is_locked        = true
  }

  lifecycle_rule {
    action { type = "Delete" }
    condition { age = var.audit_retention_days }
  }
}

resource "google_storage_bucket_iam_member" "audit_sink_writer" {
  bucket = google_storage_bucket.audit_logs.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.tessera_audit.writer_identity
}

# ── Log-based metrics ─────────────────────────────────────────────────────────

# Count of guard 'deny' decisions.
resource "google_logging_metric" "guard_denies" {
  name        = "${var.service_name}/guard_denies"
  description = "Number of guard 'deny' decisions emitted, by tool."
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.service_name}"
    jsonPayload.type="tessera.guard.audit"
    jsonPayload.outcome="denied"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "target"
      value_type  = "STRING"
      description = "Tool name that was denied."
    }
  }

  label_extractors = {
    target = "EXTRACT(jsonPayload.target)"
  }
}

# Count of HTTP 5xx responses emitted by Cloud Run — used for the error-rate alert.
resource "google_logging_metric" "http_5xx" {
  name        = "${var.service_name}/http_5xx"
  description = "Number of HTTP 5xx responses returned by the Cloud Run service."
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.service_name}"
    httpRequest.status>=500
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# ── Monitoring dashboard ──────────────────────────────────────────────────────

resource "google_monitoring_dashboard" "tessera" {
  dashboard_json = jsonencode({
    displayName = "Tessera — ${local.env}"
    labels      = local.common_labels
    mosaicLayout = {
      columns = 12
      tiles = [
        # Tile 0 — Request count
        {
          width  = 6
          height = 4
          widget = {
            title = "Request count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND metric.type=\"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.labels.response_code_class"]
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        # Tile 1 — Request latency (p50 / p95 / p99)
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Request latency"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_DELTA"
                      crossSeriesReducer = "REDUCE_PERCENTILE_95"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        # Tile 2 — CPU utilisation
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "CPU utilisation"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND metric.type=\"run.googleapis.com/container/cpu/utilizations\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        # Tile 3 — HTTP 5xx errors (log-based)
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "HTTP 5xx errors"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.http_5xx.name}\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_DELTA"
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }]
            }
          }
        },
        # Tile 4 — Guard deny decisions
        {
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Guard deny decisions"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.guard_denies.name}\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_DELTA"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.labels.target"]
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }]
            }
          }
        },
        # Tile 5 — Active instance count
        {
          xPos   = 6
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Active instances"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND metric.type=\"run.googleapis.com/container/instance_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
      ]
    }
  })
}

# ── Alert policies ────────────────────────────────────────────────────────────

# Alert: error rate > 5% over a 5-minute window.
resource "google_monitoring_alert_policy" "error_rate" {
  display_name = "Tessera — HTTP error rate > 5%"
  combiner     = "OR"

  conditions {
    display_name = "5xx rate > 5% over 5 min"
    condition_threshold {
      # Uses the built-in Cloud Run request_count metric split by response_code_class.
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05
      duration        = "300s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = []

  documentation {
    content   = <<-EOT
      The Tessera Cloud Run service is returning HTTP 5xx responses at more than 5%
      of the total request volume over the last 5 minutes.

      **Immediate steps**
      1. Check Cloud Run logs: `gcloud logging read 'resource.type="cloud_run_revision"' --limit 50`
      2. Check recent deployments in the Cloud Run console.
      3. Consult the runbook: docs/runbook.md
    EOT
    mime_type = "text/markdown"
  }

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = local.common_labels
}

# Alert: guard deny storm — more than 20 denies in a 10-minute window.
resource "google_monitoring_alert_policy" "guard_deny_storm" {
  display_name = "Tessera — guard deny storm"
  combiner     = "OR"

  conditions {
    display_name = "guard_denies > 20 / 10m"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.guard_denies.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 20
      duration        = "600s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = []

  documentation {
    content   = <<-EOT
      Tessera's guard layer emitted more than 20 deny decisions in the last 10 minutes.

      Investigate which tool is being repeatedly blocked and whether the user is being
      steered into a wall. A sudden spike may indicate a prompt-injection attempt.

      Check audit entries in Cloud Logging with:
      ```
      jsonPayload.type="tessera.guard.audit" AND jsonPayload.outcome="denied"
      ```
    EOT
    mime_type = "text/markdown"
  }

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = local.common_labels
}
