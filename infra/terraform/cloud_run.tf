# Cloud Run service hosting the FastAPI app.
#
# Ingress is set to ALL_TRAFFIC because Tessera is a public demo that is
# accessed directly from the browser without a load-balancer front-end.
# For a private deployment, flip ingress to INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER
# and restrict allowed_invokers accordingly.

resource "google_cloud_run_v2_service" "agent" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  labels = local.common_labels

  template {
    service_account = google_service_account.agent.email
    timeout         = "300s"

    # 80 concurrent requests per instance — matches the psycopg async pool size.
    max_instance_request_concurrency = 80

    labels = local.common_labels

    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    # VPC egress for private Cloud SQL access (no public IP on the DB).
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = "default"
        subnetwork = "default"
      }
    }

    # Cloud SQL sidecar — lets the app connect via Unix socket (/cloudsql/...).
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.tessera.connection_name]
      }
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = 8080
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      # ── Plain environment variables ──────────────────────────────────────────

      env {
        name  = "TESSERA_ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "TESSERA_LLM_PROFILE"
        value = "frontier"
      }
      env {
        name  = "TESSERA_DEFAULT_LANGUAGE"
        value = var.tessera_default_language
      }
      env {
        name  = "TESSERA_VERTEX__PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "TESSERA_VERTEX__LOCATION"
        value = var.region
      }
      env {
        name  = "TESSERA_VERTEX__CHAT_MODEL"
        value = var.vertex_chat_model
      }
      env {
        name  = "TESSERA_VERTEX__EMBEDDING_MODEL"
        value = var.vertex_embedding_model
      }
      env {
        name  = "TESSERA_OBSERVABILITY__CLOUD_LOGGING_PROJECT"
        value = var.project_id
      }
      env {
        name  = "TESSERA_GUARD__AUDIT_SINK"
        value = "cloud_logging"
      }

      # ── Secret-backed environment variables ──────────────────────────────────

      env {
        name = "TESSERA_POSTGRES__DSN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.managed["postgres_url"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "TESSERA_API__BEARER_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.managed["bearer_token"].secret_id
            version = "latest"
          }
        }
      }

      # ── Probes ───────────────────────────────────────────────────────────────

      startup_probe {
        period_seconds    = 5
        failure_threshold = 12
        tcp_socket {
          port = 8080
        }
      }

      liveness_probe {
        period_seconds = 30
        http_get {
          path = "/healthz"
          port = 8080
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_version.postgres_password,
    google_secret_manager_secret_version.bearer_token_placeholder,
  ]
}

# IAM — public invoker binding for the demo.
# Replace allowed_invokers with specific service accounts for a private deployment.
resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each = toset(var.allowed_invokers)
  project  = var.project_id
  location = google_cloud_run_v2_service.agent.location
  name     = google_cloud_run_v2_service.agent.name
  role     = "roles/run.invoker"
  member   = each.value
}
