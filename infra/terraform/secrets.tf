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

# Read access for the runtime service account — grants the Cloud Run SA the
# ability to fetch the latest version of every managed secret at start-up.
resource "google_secret_manager_secret_iam_member" "runtime_access" {
  for_each  = google_secret_manager_secret.managed
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}
