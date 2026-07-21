# Secret Manager entries consumed by the Cloud Run revision at start-up.
#
# Each secret resource is created here with automatic_replication.
# Secret *values* are either set by postgres.tf (for the DSN, which Terraform
# assembles from the generated password) or must be injected out-of-band via
# `gcloud secrets versions add` so that plaintext never enters Terraform state.

locals {
  managed_secrets = {
    # Key → human-readable description of the secret's purpose.
    postgres_url                   = "Tessera Postgres connection string (psycopg DSN, written by postgres.tf)."
    bearer_token                   = "Optional bearer token for the public API; leave empty to disable auth."
    audit_signing_key              = "Reserved legacy HMAC secret; it is not a substitute for the RFC 3161 ledger seal and is not injected at runtime."
    vertex_project_id              = "GCP project id used when calling Vertex AI (may differ from the deployment project)."
    api_session_signing_key        = "HMAC key for signed customer-session cookies (agent only)."
    operator_assertion_signing_key = "Shared HMAC key used by the frontend to mint and the agent to verify operator assertions."
    frontend_auth_secret           = "Auth.js JWT signing secret (frontend only)."
    frontend_admin_password        = "Seeded public-demo admin password (frontend only)."
    frontend_auditor_password      = "Seeded public-demo auditor password (frontend only)."
    frontend_collections_password  = "Seeded public-demo collections password (frontend only)."
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

# Initial versions for secrets whose values are otherwise provided out-of-band.
# `ignore_changes` means Terraform will not overwrite a value an operator sets later.
#
# Audit 2026-07-10, P1 `secret-default` (secrets.tf:38, :47). These two were seeded with the
# literal string "REPLACE_ME". Combined with `ignore_changes`, a forgotten rotation shipped a
# PUBLICLY KNOWN constant as:
#   * the service bearer — the credential guarding /audit, /memory and /settings; and
#   * `audit_signing_key` — the HMAC key over the compliance ledger, which means anyone who
#     had read this repository could FORGE audit entries. The ledger is the product's
#     opposable memory; a guessable signing key makes it decorative.
#
# The failure mode was silent and pointed the wrong way: forgetting a step left the system
# open. Generated instead, so the deployed value is a real secret even when nobody rotates
# it — the un-rotated state is now safe rather than catastrophic. An operator who wants to
# set their own value still can; ignore_changes keeps it.

resource "random_password" "bearer_token" {
  length  = 48
  special = false # a bearer travels in an HTTP header
}

resource "random_password" "audit_signing_key" {
  length  = 64
  special = false
}

resource "random_password" "api_session_signing_key" {
  length  = 64
  special = false
}

resource "random_password" "operator_assertion_signing_key" {
  length  = 64
  special = false
}

resource "random_password" "frontend_auth_secret" {
  length  = 64
  special = false
}

resource "random_password" "frontend_admin_password" {
  length  = 32
  special = false
}

resource "random_password" "frontend_auditor_password" {
  length  = 32
  special = false
}

resource "random_password" "frontend_collections_password" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret_version" "bearer_token_placeholder" {
  secret      = google_secret_manager_secret.managed["bearer_token"].id
  secret_data = random_password.bearer_token.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "audit_signing_key_placeholder" {
  secret      = google_secret_manager_secret.managed["audit_signing_key"].id
  secret_data = random_password.audit_signing_key.result

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

resource "google_secret_manager_secret_version" "api_session_signing_key" {
  secret      = google_secret_manager_secret.managed["api_session_signing_key"].id
  secret_data = random_password.api_session_signing_key.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "operator_assertion_signing_key" {
  secret      = google_secret_manager_secret.managed["operator_assertion_signing_key"].id
  secret_data = random_password.operator_assertion_signing_key.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "frontend_auth_secret" {
  secret      = google_secret_manager_secret.managed["frontend_auth_secret"].id
  secret_data = random_password.frontend_auth_secret.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "frontend_admin_password" {
  secret      = google_secret_manager_secret.managed["frontend_admin_password"].id
  secret_data = random_password.frontend_admin_password.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "frontend_auditor_password" {
  secret      = google_secret_manager_secret.managed["frontend_auditor_password"].id
  secret_data = random_password.frontend_auditor_password.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "frontend_collections_password" {
  secret      = google_secret_manager_secret.managed["frontend_collections_password"].id
  secret_data = random_password.frontend_collections_password.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Read access is scoped to the secrets each runtime actually consumes. The agent must not read
# dashboard passwords or Auth.js material; the frontend must not read the customer-session key.
locals {
  agent_runtime_secret_keys = toset([
    "postgres_url",
    "bearer_token",
    "api_session_signing_key",
    "operator_assertion_signing_key",
  ])
  frontend_runtime_secret_keys = toset([
    "bearer_token",
    "operator_assertion_signing_key",
    "frontend_auth_secret",
    "frontend_admin_password",
    "frontend_auditor_password",
    "frontend_collections_password",
  ])
}

resource "google_secret_manager_secret_iam_member" "runtime_access" {
  for_each  = local.agent_runtime_secret_keys
  secret_id = google_secret_manager_secret.managed[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_secret_manager_secret_iam_member" "frontend_runtime_access" {
  for_each  = local.frontend_runtime_secret_keys
  secret_id = google_secret_manager_secret.managed[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.frontend.email}"
}

# The qualified TSA trust root is supplied out of band. Its bytes never cross Terraform state.
data "google_secret_manager_secret" "seal_tsa_cert" {
  secret_id = var.seal_tsa_cert_secret_id
}

resource "google_secret_manager_secret_iam_member" "agent_seal_tsa_cert_access" {
  secret_id = data.google_secret_manager_secret.seal_tsa_cert.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}
