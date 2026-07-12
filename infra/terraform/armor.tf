# Cloud Armor edge rate limiting for the agent (ADR 0020, premium cloud tier).
#
# Cloud counterpart of infra/edge/nginx.conf: a managed WAF + rate limiter at
# the edge, in front of the app-level limiter. Cloud Run cannot have Cloud Armor
# attached directly — it needs an external HTTPS load balancer with a serverless
# NEG. The full wiring lives here, gated behind a flag so the default (direct
# Cloud Run ingress) keeps working for the demo.
#
# Enable with: -var="enable_edge_armor=true" -var="edge_domain=agent.example.eu"

variable "enable_edge_armor" {
  type        = bool
  default     = false
  description = "Front the Cloud Run service with an HTTPS LB + Cloud Armor."
}

variable "armor_rate_per_minute" {
  type        = number
  default     = 60
  description = "Edge rate-limit threshold (requests/minute/IP) before throttling."
}

variable "edge_domain" {
  type        = string
  default     = ""
  description = "FQDN served by the HTTPS load balancer (required when armor is on)."
}

resource "google_compute_security_policy" "edge" {
  count = var.enable_edge_armor ? 1 : 0
  name  = "${var.service_name}-${local.env}-edge"

  # Throttle abusive IPs (volumetric protection; app layer handles per-identity).
  rule {
    action   = "throttle"
    priority = 1000
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.armor_rate_per_minute
        interval_sec = 60
      }
    }
    description = "Per-IP volumetric rate limit at the edge."
  }

  # Default allow (rules above take precedence by priority).
  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default rule."
  }

  # Adaptive protection: ML-based L7 DDoS detection (premium).
  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable = true
    }
  }
}

resource "google_compute_region_network_endpoint_group" "agent" {
  count                 = var.enable_edge_armor ? 1 : 0
  name                  = "${var.service_name}-${local.env}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.agent.name
  }
}

resource "google_compute_backend_service" "agent" {
  count                 = var.enable_edge_armor ? 1 : 0
  name                  = "${var.service_name}-${local.env}-be"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"
  security_policy       = google_compute_security_policy.edge[0].id
  backend {
    group = google_compute_region_network_endpoint_group.agent[0].id
  }
}

resource "google_compute_url_map" "agent" {
  count           = var.enable_edge_armor ? 1 : 0
  name            = "${var.service_name}-${local.env}-um"
  default_service = google_compute_backend_service.agent[0].id
}

resource "google_compute_managed_ssl_certificate" "agent" {
  count = var.enable_edge_armor ? 1 : 0
  name  = "${var.service_name}-${local.env}-cert"
  managed {
    domains = [var.edge_domain]
  }
}

resource "google_compute_target_https_proxy" "agent" {
  count            = var.enable_edge_armor ? 1 : 0
  name             = "${var.service_name}-${local.env}-https"
  url_map          = google_compute_url_map.agent[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.agent[0].id]
}

resource "google_compute_global_forwarding_rule" "agent" {
  count                 = var.enable_edge_armor ? 1 : 0
  name                  = "${var.service_name}-${local.env}-fr"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "443"
  target                = google_compute_target_https_proxy.agent[0].id
}

# NOTE: when enable_edge_armor is true, also set the Cloud Run service ingress to
# "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" (cloud_run.tf) so the armor layer
# cannot be bypassed by hitting the run.app URL directly.
