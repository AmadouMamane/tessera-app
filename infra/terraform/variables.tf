# Input variables for the Tessera GCP deployment.
#
# Sensible defaults are provided for the demo region (europe-west1) and the
# canonical service names; per-environment overrides go in tfvars files
# that are never committed.

variable "project_id" {
  description = "Google Cloud project id that owns the deployment."
  type        = string
}

variable "region" {
  description = "Primary deployment region."
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Deployment environment label (e.g. production, staging). Usually left to the Terraform workspace; see local.env in main.tf."
  type        = string
  default     = "production"
}

variable "name_suffix" {
  description = "Suffix appended to globally-named resources (Cloud Run services, SQL instance, secrets) so multiple environments can share ONE GCP project without colliding. Leave empty when each env has its own project (the recommended topology)."
  type        = string
  default     = ""
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "tessera-agent"
}

variable "image" {
  description = "Fully-qualified agent container image (Artifact Registry path)."
  type        = string
}

variable "frontend_image" {
  description = "Fully-qualified Next.js front-end container image (Artifact Registry path)."
  type        = string
}

variable "frontend_service_name" {
  description = "Cloud Run service name for the Next.js front-end."
  type        = string
  default     = "tessera-frontend"
}

variable "seal_tsa_url" {
  description = "HTTPS endpoint of the qualified RFC 3161 TSA selected from an EU Trusted List."
  type        = string

  validation {
    condition     = can(regex("^https://", var.seal_tsa_url))
    error_message = "seal_tsa_url must be an HTTPS URL."
  }
}

variable "seal_tsa_cert_secret_id" {
  description = "Existing Secret Manager secret id whose latest version contains the TSA validation certificate/CA bundle; managed out of band so certificate material never enters Terraform state."
  type        = string

  validation {
    condition     = length(trimspace(var.seal_tsa_cert_secret_id)) > 0
    error_message = "seal_tsa_cert_secret_id must name an existing Secret Manager secret."
  }
}

variable "frontend_cpu" {
  description = "vCPU allocation per front-end Cloud Run instance."
  type        = string
  default     = "1"
}

variable "frontend_memory" {
  description = "RAM allocation per front-end Cloud Run instance."
  type        = string
  default     = "512Mi"
}

# Aliases matching the canonical naming convention while keeping
# backward-compat with the internal min/max_instances names used across files.
variable "cloud_run_min_instances" {
  description = "Cloud Run minimum-instance floor (use 0 for the demo)."
  type        = number
  default     = 0
}

variable "cloud_run_max_instances" {
  description = "Cloud Run hard cap on concurrent instances."
  type        = number
  default     = 5
}

# Internal aliases — kept so other files can reference either name consistently.
variable "min_instances" {
  description = "Alias for cloud_run_min_instances."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Alias for cloud_run_max_instances."
  type        = number
  default     = 5
}

variable "cpu" {
  description = "vCPU allocation per Cloud Run instance."
  type        = string
  default     = "2"
}

variable "memory" {
  description = "RAM allocation per Cloud Run instance."
  type        = string
  default     = "2Gi"
}

variable "postgres_tier" {
  description = "Cloud SQL machine tier (db-g1-small for low-cost demo, db-custom-* for prod)."
  type        = string
  default     = "db-g1-small"
}

variable "postgres_version" {
  description = "Cloud SQL Postgres major version."
  type        = string
  default     = "POSTGRES_16"
}

variable "tessera_default_language" {
  description = "ISO-639-1 language code used as the agent default locale (fr | de | en)."
  type        = string
  default     = "fr"

  validation {
    condition     = contains(["fr", "de", "en"], var.tessera_default_language)
    error_message = "tessera_default_language must be one of: fr, de, en."
  }
}

variable "vertex_chat_model" {
  description = "Vertex AI chat model id."
  type        = string
  default     = "gemini-2.0-flash-001"
}

variable "vertex_embedding_model" {
  description = "Vertex AI embedding model id."
  type        = string
  default     = "text-multilingual-embedding-002"
}

variable "log_retention_days" {
  description = "Cloud Logging retention window in days."
  type        = number
  default     = 30
}

variable "audit_retention_days" {
  description = "Retention for the audit-log bucket. Enforced by a LOCKED retention policy: objects cannot be deleted before this age, by anyone."
  type        = number
  default     = 365
}

variable "ingress" {
  # Audit 2026-07-10, P0 `terraform-exposure` (cloud_run.tf:11). Was hardcoded to
  # INGRESS_TRAFFIC_ALL. Internal + load balancer by default: the run.app URL stops being a
  # way around Cloud Armor, which only fronts the load balancer.
  description = "Cloud Run ingress. INGRESS_TRAFFIC_ALL publishes the run.app URL to the internet and bypasses Cloud Armor — only for a deliberate public demo."
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  validation {
    condition = contains([
      "INGRESS_TRAFFIC_ALL",
      "INGRESS_TRAFFIC_INTERNAL_ONLY",
      "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER",
    ], var.ingress)
    error_message = "ingress must be one of INGRESS_TRAFFIC_ALL, INGRESS_TRAFFIC_INTERNAL_ONLY, INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER."
  }
}

variable "allowed_invokers" {
  # Audit 2026-07-10, P0 `terraform-exposure` (variables.tf:147 · cloud_run.tf:11/162).
  # This defaulted to ["allUsers"]: the banking agent was invocable by the entire internet
  # unless someone remembered to override it. Callers could hit the run.app URL directly,
  # bypassing the frontend — which is the only intended caller — and with it Cloud Armor,
  # which only sits in front of the load balancer.
  #
  # Now empty by default: no principal may invoke the service until one is named. A public
  # demo is still possible, but it has to be ASKED for. Secure by default, exposed by choice.
  description = "IAM principals allowed to invoke the Cloud Run service. Normally the frontend service account ONLY. Set to [\"allUsers\"] to deliberately publish a public demo."
  type        = list(string)
  default     = []
}

variable "frontend_allowed_invokers" {
  description = "IAM principals allowed to invoke the public frontend. Keep empty for a private deployment; the demo workflow deliberately passes [\"allUsers\"]."
  type        = list(string)
  default     = []
}
