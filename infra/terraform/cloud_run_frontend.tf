# Cloud Run service hosting the Next.js dashboard (front-end).
#
# Topology: the browser only ever talks to this service. It proxies API calls
# to the agent service server-side (route handlers under app/api/*), injecting
# the shared bearer token so the agent stays protected even though both
# services are publicly invocable. See docs/runbook.md.
#
# This closes the gap noted in earlier iterations: previously only the agent
# had a Cloud Run service defined.

# Dedicated runtime SA for the front-end, least-privilege: it only needs to
# read the bearer token from Secret Manager.
resource "google_service_account" "frontend" {
  account_id   = "${local.frontend_service}-runtime"
  display_name = "Tessera frontend runtime"
  description  = "Service account used by the Next.js Cloud Run revision."
}

# Grant the front-end SA read access to the bearer-token secret only (the same
# secret the agent enforces), so it can inject Authorization on backend calls.
resource "google_secret_manager_secret_iam_member" "frontend_bearer_access" {
  secret_id = google_secret_manager_secret.managed["bearer_token"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.frontend.email}"
}

resource "google_cloud_run_v2_service" "frontend" {
  name     = local.frontend_service
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  labels = local.common_labels

  template {
    service_account = google_service_account.frontend.email
    timeout         = "300s"

    labels = local.common_labels

    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      image = var.frontend_image

      resources {
        limits = {
          cpu    = var.frontend_cpu
          memory = var.frontend_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      # Next standalone server (server.js) listens on $PORT, which Cloud Run
      # injects to match container_port. Do NOT set PORT manually (reserved).
      ports {
        container_port = 3000
      }

      # Backend URL = the agent service's own HTTPS URL. The token is injected
      # server-side by the Next route handlers (TESSERA_BACKEND_TOKEN).
      env {
        name  = "TESSERA_BACKEND_URL"
        value = google_cloud_run_v2_service.agent.uri
      }
      env {
        name = "TESSERA_BACKEND_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.managed["bearer_token"].secret_id
            version = "latest"
          }
        }
      }

      # The standalone server has no dedicated health route (/ 307-redirects to
      # the locale), so probe the socket rather than an HTTP path.
      startup_probe {
        period_seconds    = 5
        failure_threshold = 12
        tcp_socket {
          port = 3000
        }
      }

      liveness_probe {
        period_seconds = 30
        tcp_socket {
          port = 3000
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
    google_secret_manager_secret_version.bearer_token_placeholder,
  ]
}

# Public invoker binding for the demo — mirror the agent's policy.
resource "google_cloud_run_v2_service_iam_member" "frontend_invokers" {
  for_each = toset(var.allowed_invokers)
  project  = var.project_id
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = each.value
}
