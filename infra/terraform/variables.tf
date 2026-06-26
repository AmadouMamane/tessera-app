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

variable "allowed_invokers" {
  description = "IAM principals allowed to invoke the Cloud Run service. Set to [\"allUsers\"] for a public demo."
  type        = list(string)
  default     = ["allUsers"]
}
