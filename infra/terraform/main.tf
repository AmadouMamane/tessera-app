# Root configuration for the Tessera GCP deployment.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "gcs" {
    # Configured per-environment via `terraform init -backend-config=...`
    # Example:
    #   terraform init \
    #     -backend-config="bucket=<tf-state-bucket>" \
    #     -backend-config="prefix=tessera/production"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable the APIs the rest of the stack expects to be live.
locals {
  required_apis = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    # Observability lakehouse + GenAI evaluation sink (ADR 0010, Phase 3).
    "bigquery.googleapis.com",
  ]

  # Environment isolation (ADR 0014, layer 5): the deployment environment IS the
  # Terraform workspace, so `terraform workspace select staging|production` is the
  # single knob that isolates state (GCS auto-prefixes per workspace) and labels.
  # The `default` workspace falls back to var.environment so pre-workspace state
  # keeps working. This is the deployed sibling of TESSERA_ENVIRONMENT (schema /
  # path isolation on the local side).
  env = terraform.workspace == "default" ? var.environment : terraform.workspace

  # Recommended topology = one GCP project per env (set via env tfvars), so
  # resource names need no suffix. For a shared project, set var.name_suffix to
  # keep names distinct across workspaces.
  agent_service    = "${var.service_name}${var.name_suffix}"
  frontend_service = "${var.frontend_service_name}${var.name_suffix}"
  sql_instance     = "${var.service_name}-pg${var.name_suffix}"

  common_labels = {
    environment = local.env
    app         = "tessera"
  }
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  service            = each.value
  disable_on_destroy = false
}

# Service account that the Cloud Run revision runs as.
resource "google_service_account" "agent" {
  account_id   = "${local.agent_service}-runtime"
  display_name = "Tessera agent runtime"
  description  = "Service account used by the Cloud Run revision."
}

# Minimal IAM grants for the runtime SA.
locals {
  agent_roles = [
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
  ]
}

resource "google_project_iam_member" "agent_roles" {
  for_each = toset(local.agent_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.agent.email}"
}
