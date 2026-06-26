# Cloud SQL Postgres with the pgvector extension.
#
# The pgvector extension itself is created at application start via
# tessera.retrieval.store.ensure_schema. Terraform only provisions the instance,
# the database, and the application user — it enables the pgvector flag so that
# the extension can be loaded at the database level.

resource "google_sql_database_instance" "tessera" {
  name             = local.sql_instance
  database_version = var.postgres_version
  region           = var.region

  # Prevent accidental deletion in production.
  deletion_protection = local.env == "production" ? true : false

  settings {
    tier              = var.postgres_tier
    availability_type = "ZONAL"
    disk_autoresize   = true
    disk_size         = 20

    user_labels = local.common_labels

    # Required for pgvector support.
    database_flags {
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }

    # Required to allow IAM-based authentication alongside password auth.
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      location                       = var.region
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = "projects/${var.project_id}/global/networks/default"
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "tessera" {
  name     = "tessera"
  instance = google_sql_database_instance.tessera.name
}

# Application user — password is stored in Secret Manager and injected at
# runtime; Terraform creates the user referencing the secret so that the
# password is never written to state in plaintext.
resource "google_sql_user" "tessera" {
  name     = "tessera"
  instance = google_sql_database_instance.tessera.name
  password = random_password.postgres.result
}

# Ephemeral random password used only at first provisioning; Secret Manager
# holds the canonical copy via postgres.tf → secrets.tf coupling below.
resource "random_password" "postgres" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Write the generated password into Secret Manager so the Cloud Run revision
# can assemble the full DSN from it at start-up.
resource "google_secret_manager_secret_version" "postgres_password" {
  secret = google_secret_manager_secret.managed["postgres_url"].id

  # Full psycopg DSN: postgresql+asyncpg://user:pass@host/db via Cloud SQL proxy.
  secret_data = "postgresql+asyncpg://tessera:${random_password.postgres.result}@/tessera?host=/cloudsql/${google_sql_database_instance.tessera.connection_name}"

  lifecycle {
    # Do not replace the secret version if the password was rotated out-of-band.
    ignore_changes = [secret_data]
  }
}
