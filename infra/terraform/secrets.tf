# Secret Manager entries consumed by the Cloud Run revision at start-up.
#
# Each secret resource is created here with automatic_replication.
# Secret *values* are either set by postgres.tf (for the DSN, which Terraform
# assembles from the generated password) or must be injected out-of-band via
# `gcloud secrets versions add` so that plaintext never enters Terraform state.

locals {
  managed_secrets = {
    # Key → human-readable description of the secret's purpose.
    postgres_url      = "Tessera Postgres connection string (psycopg DSN, written by postgres.tf)."
    bearer_token      = "Optional bearer token for the public API; leave empty to disable auth."
    audit_signing_key = "HMAC key used to sign audit-trail entries."
    vertex_project_id = "GCP project id used when calling Vertex AI (may differ from the deployment project)."
  }
}

resource "google_secret_manager_secret" "managed" {
  for_each  = local.managed_secrets
  secret_id = "${local.agent_service}-${each.key}"

  labels = merge(local.common_labels, {
    managed = "terraform"
  })

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# Placeholder versions for secrets whose values must be provided out-of-band.
# Using ignore_changes means Terraform won't overwrite a value set manually.

resource "google_secret_manager_secret_version" "bearer_token_placeholder" {
  secret      = google_secret_manager_secret.managed["bearer_token"].id
  secret_data = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "audit_signing_key_placeholder" {
  secret      = google_secret_manager_secret.managed["audit_signing_key"].id
  secret_data = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "vertex_project_id_placeholder" {
  secret      = google_secret_manager_secret.managed["vertex_project_id"].id
  secret_data = var.project_id

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Read access for the runtime service account — grants the Cloud Run SA the
# ability to fetch the latest version of every managed secret at start-up.
resource "google_secret_manager_secret_iam_member" "runtime_access" {
  for_each  = google_secret_manager_secret.managed
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}
