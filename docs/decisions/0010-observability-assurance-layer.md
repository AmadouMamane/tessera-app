# 10. Adopt an observability assurance layer

Date: 2026-06-07

## Status

Draft

## Context

Tessera already contains a basic observability foundation: structured logging,
OpenTelemetry wiring, Prometheus metrics, Cloud Monitoring Terraform, audit
trail support, and health/readiness endpoints. That is not enough for the
project's target demonstration. Tessera needs to show both:

- cloud-native operational maturity on Google Cloud Run, Cloud Logging, Cloud
  Monitoring, and Cloud Trace;
- on-premises operational maturity with a sovereign, local observability stack;
- LLM-specific investigation quality through a polished cockpit such as
  Langfuse;
- prompt management, datasets, experiments, and feedback loops without losing
  repository-controlled deployability;
- banking-grade privacy, auditability, and evidence for sensitive decisions.

The project also has a hard positioning constraint: the runtime guard layer is
`mcp-firewall` consumed as a dependency. Tessera should not accidentally present
itself as a replacement firewall unless a future ADR deliberately changes that
positioning. At the same time, Tessera can invent domain-specific evidence
patterns around tool decisions and propose generic parts upstream to
`mcp-firewall`.

## Decision

Tessera will adopt an **Observability Assurance Layer** rather than a simple
dashboard-oriented observability feature.

The layer has these architectural principles:

1. **One instrumentation model, multiple deployment profiles.** Tessera emits a
   stable OpenTelemetry/log/metric/audit/evidence model. Profiles route it to
   Google Cloud Observability, an on-premises stack, optional Langfuse, or
   air-gapped evidence files.
2. **OpenTelemetry is the portable spine.** Langfuse is an optional LLMOps
   cockpit for traces, prompt management, datasets, experiments, feedback, and
   scoring, not the source of truth.
3. **Privacy is enforced before export.** Telemetry passes through a Privacy
   Gateway that allowlists attributes, redacts PII, hashes correlation IDs, and
   forbids raw prompts by default.
4. **Sensitive decisions produce evidence.** Guard decisions, tool attempts,
   escalations, citations, and regulatory answers are linked through evidence
   bundles.
5. **Assurance is profile-driven.** Profiles such as `cloud_gcp_regulated`,
   `on_prem_standard`, and `on_prem_airgapped` declare expected exporters,
   retention, sampling, evidence depth, and conformance checks.
6. **Proof-carrying tool calls are an invention candidate.** Tessera will
   explore attaching short-lived, policy-bound decision proofs to sensitive tool
   calls. Generic decision-proof primitives should be proposed upstream to
   `mcp-firewall`; Tessera-specific banking evidence remains in Tessera.
7. **LLMOps changes are promoted through code and tests.** Langfuse can host
   prompt candidates, datasets, experiments, and human review, but deployable
   prompts remain YAML, eval cases remain JSON, guard policies remain YAML, and
   promotion requires the eval harness plus assurance conformance checks.

The longer design is captured in `docs/observability-assurance-layer.md`.

## Consequences

Tessera's observability becomes a product-quality assurance surface, not just
monitoring. The system can show:

- GCP operational maturity through Cloud Run metrics, Cloud Logging, Cloud
  Monitoring, Cloud Trace, SLOs, alerts, and audit sinks;
- on-premises maturity through OpenTelemetry Collector, Prometheus, Grafana,
  Tempo/Jaeger, Loki, Alertmanager, and local signed evidence;
- LLM-specific trace readability through optional Langfuse;
- prompt, dataset, experiment, and feedback workflows through Langfuse while
  preserving Tessera's repository as the deployable source of truth;
- banking assurance through redacted evidence bundles, proof quality, guard
  decision linkage, citation coverage, and audit correlation.

The cost is additional design and implementation work. A Langfuse-only approach
would be faster and visually strong, but would make the architecture less
portable and less convincing for sovereign on-premises operation. The chosen
approach is heavier but better aligned with Tessera's cloud/on-prem thesis.

Implementation must be staged. The first cut should deliver telemetry contract,
privacy gateway, cloud/on-prem profiles, Langfuse optional integration,
prompt/dataset/experiment metadata wiring, evidence bundle v1, dashboard
status, and conformance tests. Proof-carrying tool calls, Shadow Verifier,
proof consensus, signed bundles, LLMOps promotion gates, and digital twin
simulation belong to later iterations unless schedule allows.
