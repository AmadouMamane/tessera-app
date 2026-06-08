# GenAI observability on GCP (ADR 0010, Phase 3) — the `gcp` profile sinks.
#
# Independent, code-only addition: written and reviewed but NOT applied (no GCP
# project wired in this build). It demonstrates the GCP-native half of the dual
# profile — a BigQuery "lakehouse" for traces/evals (idea #120), a log-based
# *quality* metric round-tripped from eval-as-telemetry (idea #5), a faithfulness
# SLO alert (idea #15), and a GenAI-quality dashboard. Vertex AI Gen AI Evaluation
# reuses the runtime service account (already granted roles/aiplatform.user in
# main.tf) and writes results to the dataset below.
#
# Apply prerequisites (when a GCP project exists): the google provider auth, the
# GCS state backend, and `terraform init` to download the provider.

# ── BigQuery lakehouse — traces + eval scores (idea #120) ─────────────────────

resource "google_bigquery_dataset" "observability" {
  dataset_id  = "${replace(var.service_name, "-", "_")}_observability"
  location    = var.region
  description = "Tessera observability lakehouse: trace + evaluation analytics (ADR 0010)."
  labels      = local.common_labels

  depends_on = [google_project_service.apis]
}

# Destination table for online-eval scores (faithfulness, groundedness, …),
# fed both by the logging sink below and by the Vertex Gen AI Eval job.
resource "google_bigquery_table" "eval_scores" {
  dataset_id          = google_bigquery_dataset.observability.dataset_id
  table_id            = "eval_scores"
  deletion_protection = false
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "scored_at"
  }

  schema = jsonencode([
    { name = "scored_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "trace_id", type = "STRING", mode = "NULLABLE" },
    { name = "conversation_id", type = "STRING", mode = "NULLABLE" },
    { name = "language", type = "STRING", mode = "NULLABLE" },
    { name = "metric", type = "STRING", mode = "REQUIRED" },
    { name = "score", type = "FLOAT", mode = "REQUIRED" },
    { name = "judge_model", type = "STRING", mode = "NULLABLE" },
    { name = "sampled", type = "BOOLEAN", mode = "NULLABLE" },
  ])
}

# ── Logging sink — eval-as-telemetry → BigQuery (ideas #5 / #120) ─────────────
# The agent emits one structured log line per online-eval score
# (jsonPayload.type="tessera.eval.score"); this routes them into BigQuery for
# SQL analytics and Looker Studio, in addition to the Cloud Monitoring metric.

resource "google_logging_project_sink" "eval_scores_bq" {
  name        = "${var.service_name}-eval-scores-bq"
  description = "Routes tessera.eval.score log entries into the observability dataset."
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.observability.dataset_id}"

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.service_name}"
    jsonPayload.type="tessera.eval.score"
  EOT

  unique_writer_identity = true

  bigquery_options {
    use_partitioned_tables = true
  }
}

resource "google_bigquery_dataset_iam_member" "eval_sink_writer" {
  dataset_id = google_bigquery_dataset.observability.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.eval_scores_bq.writer_identity
}

# ── Log-based quality metric — faithfulness distribution (idea #5) ────────────
# Round-trips the online-eval faithfulness score into a Cloud Monitoring
# distribution metric, so quality becomes a time series we can alert on.

resource "google_logging_metric" "eval_faithfulness" {
  name        = "${var.service_name}/eval_faithfulness"
  description = "Distribution of online-eval faithfulness scores, by language."

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.service_name}"
    jsonPayload.type="tessera.eval.score"
    jsonPayload.metric="faithfulness"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key         = "language"
      value_type  = "STRING"
      description = "Conversation language (fr/de/en)."
    }
  }

  value_extractor  = "EXTRACT(jsonPayload.score)"
  label_extractors = { language = "EXTRACT(jsonPayload.language)" }

  bucket_options {
    linear_buckets {
      num_finite_buckets = 10
      width              = 0.1
      offset             = 0
    }
  }
}

# ── Quality SLO alert — faithfulness below threshold (idea #15) ────────────────

resource "google_monitoring_alert_policy" "faithfulness_below_slo" {
  display_name = "Tessera — faithfulness below SLO"
  combiner     = "OR"

  conditions {
    display_name = "median faithfulness < 0.80 over 30 min"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.eval_faithfulness.name}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 0.80
      duration        = "1800s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_PERCENTILE_50"
      }
    }
  }

  notification_channels = []

  documentation {
    content   = <<-EOT
      The agent's online faithfulness score has dropped below the 0.80 SLO
      (median over 30 minutes). A quality regression — not a latency one.

      **Steps**
      1. Check recent deploys / model or prompt version changes (lineage).
      2. Inspect failing traces in Phoenix / the BigQuery `eval_scores` table.
      3. Consider freezing deploys until the error budget recovers (docs/runbook.md).
    EOT
    mime_type = "text/markdown"
  }

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = local.common_labels
}

# ── GenAI-quality dashboard ────────────────────────────────────────────────────

resource "google_monitoring_dashboard" "genai_quality" {
  dashboard_json = jsonencode({
    displayName = "Tessera — GenAI quality (${var.environment})"
    labels      = local.common_labels
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Faithfulness (median) by language"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.eval_faithfulness.name}\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_PERCENTILE_50"
                      crossSeriesReducer = "REDUCE_MEAN"
                      groupByFields      = ["metric.labels.language"]
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Eval score volume"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.eval_faithfulness.name}\""
                    aggregation = {
                      alignmentPeriod  = "300s"
                      perSeriesAligner = "ALIGN_COUNT"
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }]
            }
          }
        },
      ]
    }
  })
}
