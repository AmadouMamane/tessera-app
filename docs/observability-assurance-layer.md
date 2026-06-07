# Tessera Observability Assurance Layer

Status: draft architecture paper  
Date: 2026-06-07  
Related ADR: `docs/decisions/0010-observability-assurance-layer.md`

## Executive thesis

Tessera should not treat observability as dashboards attached to an agent. For
European retail banking support, observability is part of the safety and audit
surface. The target architecture is therefore an **Observability Assurance
Layer**: a portable, deployment-aware, privacy-governed proof system that links
every sensitive agent decision to traces, logs, metrics, audit entries,
citations, runtime guard decisions, evidence bundles, and non-regression cases.

The design has three simultaneous goals:

1. Show current Google Cloud operations mastery in the Cloud Run profile.
2. Show current on-premises sovereignty mastery in the local profile.
3. Provide a polished LLM-specific cockpit through Langfuse without making
   Langfuse the source of truth.

The short formulation:

> Tessera emits vendor-neutral telemetry by default. In Cloud Run, it maps to
> Google Cloud Observability. On-premises, it maps to a sovereign
> OpenTelemetry/Prometheus/Grafana stack, with optional self-hosted Langfuse for
> LLM-specific trace analysis. Sensitive actions produce portable, redacted,
> verifiable evidence.

## Positioning

The base project still consumes `mcp-firewall` as the runtime guard dependency.
Tessera's primary value remains the banking assembly: multilingual agent,
runtime guard, regression harness, audit trail, human escalation, deployment,
and evidence.

This paper also proposes an invention that may be upstreamed to `mcp-firewall`:
**Proof-Carrying Tool Calls**. If the project decides to make that a public
Tessera invention, an ADR should supersede the current honest-positioning
language and explain the new claim carefully.

Until then, the safe distinction is:

- `mcp-firewall` decides whether a tool call is allowed, denied, or requires
  approval.
- Tessera enriches the decision with banking context and turns it into
  correlated, redacted, verifiable evidence.
- Generic decision-evidence primitives should be proposed upstream to
  `mcp-firewall` rather than duplicated permanently in Tessera.

## External anchors

This architecture is intentionally built on mainstream observability practices:

- OpenTelemetry Collector deployment patterns support multi-backend,
  cross-environment collection and routing. The official Collector deployment
  guide describes common deployment patterns and cross-environment,
  multi-backend configuration best practices.
  Source: https://opentelemetry.io/docs/collector/deploy/
- OpenTelemetry GenAI semantic conventions define signals for agent spans,
  model spans, GenAI events, exceptions, and metrics. As of the 1.41.1
  documentation, the GenAI conventions are still marked development, so Tessera
  should opt in deliberately and wrap them with a stable Tessera contract.
  Source: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- Google Cloud recommends Collector-based export when the environment supports
  it, because application code remains vendor-neutral while the Collector owns
  Google Cloud export logic.
  Source:
  https://docs.cloud.google.com/stackdriver/docs/instrumentation/choose-approach
- Cloud Run automatically provides Cloud Monitoring metrics such as request
  count, request latencies, CPU, memory, instance count, and concurrency; custom
  metrics can be added with OpenTelemetry/Prometheus or log-based metrics.
  Source: https://docs.cloud.google.com/run/docs/monitoring
- Langfuse SDKs are built on OpenTelemetry and can also receive OpenTelemetry
  spans, making Langfuse suitable as an LLMOps cockpit over a portable OTel
  spine.
  Source: https://langfuse.com/docs/observability/sdk/overview
- `mcp-firewall` presents itself as a security gateway for AI agents with policy
  enforcement, threat detection, audit logging, dashboarding, and compliance
  reports.
  Source: https://github.com/ressl/mcp-firewall

## Core architecture

The application emits one canonical telemetry model. Deployment profiles decide
where the signals go.

```text
Tessera runtime
  -> Telemetry Contract
  -> Privacy Gateway
  -> OpenTelemetry / structured logs / Prometheus metrics / audit events
  -> OpenTelemetry Collector
       -> cloud_gcp: Cloud Logging, Cloud Monitoring, Cloud Trace, audit GCS
       -> on_prem: Prometheus, Grafana, Tempo or Jaeger, Loki, Alertmanager
       -> llmops: Langfuse optional
       -> air_gapped: local signed evidence bundles and offline viewer
```

The important constraint is that Tessera's code should not branch deeply on
cloud versus on-premises. It should emit stable telemetry and evidence events;
the profile selects exporters, retention, sampling, alerting, and dashboard
links.

## Three planes

The architecture separates three planes because they serve different users.

### SRE plane

Audience: platform engineer, on-call operator.

Signals:

- liveness and readiness
- request count and latency
- p95 / p99 turn latency
- HTTP 5xx rate
- LLM backend reachability
- Collector/exporter health
- queue length and dropped telemetry
- SLO burn rate

Backends:

- GCP profile: Cloud Monitoring, Cloud Logging, Cloud Trace.
- On-prem profile: Prometheus, Grafana, Tempo/Jaeger, Loki, Alertmanager.

### LLMOps plane

Audience: ML engineer, agent engineer, evaluator.

Signals:

- LLM calls
- prompt version hash
- model name and deployment profile
- input/output token counts
- estimated cost
- retrieval document count
- citation coverage
- eval outcome correlation
- feedback and annotations
- prompt experiment ID
- dataset ID
- experiment cohort
- human review status
- promotion or rollback decision

Backend:

- Langfuse self-hosted or managed, optional.
- OpenTelemetry spans and metrics remain canonical.

### Audit plane

Audience: auditor, compliance, security, support lead.

Signals:

- guard decisions
- sensitive action evidence
- escalation decisions
- rejected paths
- authorization context
- evidence bundle
- policy hash
- prompt hash
- corpus hash
- audit access logs

Backends:

- local JSONL or Postgres in development
- Cloud Logging and GCS audit sink in GCP
- local signed evidence ledger in on-prem / air-gapped

## Deployment-aware profiles

Profiles are declared in configuration, not hardcoded throughout the codebase.

Proposed profile names:

- `local_dev`
- `demo_premium`
- `cloud_gcp_standard`
- `cloud_gcp_regulated`
- `on_prem_standard`
- `on_prem_airgapped`

Each profile declares:

- target assurance level
- exporters and destinations
- Langfuse enabled/disabled/optional
- raw prompt policy
- PII export policy
- retention
- sampling
- audit sink requirements
- evidence bundle requirements
- alert policies
- dashboard expectations
- conformance checks

Example:

```yaml
profile: cloud_gcp_regulated
assurance_level: L4

telemetry:
  collector: required
  raw_prompts: forbidden
  pii_export: forbidden
  langfuse: optional

evidence:
  bundle: required
  signature: required
  retention_days: 365

controls:
  guard_deny_audited: required
  regulatory_answer_cited: required
  sensitive_action_proof_valid: required
  cloud_onprem_parity: required
```

## Assurance levels

Observability should not be binary. Each deployment declares a target assurance
level and Tessera reports the gap.

```text
L0 Observed     logs, metrics, health
L1 Correlated   request_id, trace_id, conversation_id, turn_id
L2 Auditable    audit trail, guard decisions, retention, access logs
L3 Verifiable   signed evidence bundle, privacy proof, policy hashes
L4 Replayable   redacted replay, golden traces, policy diff, parity report
L5 Certifiable  external verifier, compliance pack, control coverage
```

Example dashboard output:

```text
Target: L4 Replayable
Current: L3 Verifiable
Missing:
- policy replay lab
- golden trace parity report
- external verifier CLI
```

## Telemetry Contract

Tessera needs a versioned telemetry contract. It should live in code and docs,
for example:

- `src/tessera/observability/schema.py`
- `docs/observability-contract.md`
- `src/tessera/observability/policy.yaml`

Canonical events:

```text
TurnStarted
IntentDetected
TargetResolved
PolicyEvaluated
ProofIssued
ToolExecutionStarted
ToolExecutionAllowed
ToolExecutionBlocked
AuditEmitted
EvidenceCommitted
TurnCompleted
```

Canonical spans:

```text
tessera.turn
tessera.langgraph.router
tessera.langgraph.planner
tessera.langgraph.product_lookup
tessera.langgraph.regulation_lookup
tessera.langgraph.account_lookup
tessera.langgraph.simulator
tessera.langgraph.reviewer
tessera.langgraph.reporter
tessera.guard.decision
tessera.retrieval.query
tessera.llm.call
tessera.memory.operation
tessera.escalation
```

Canonical metrics:

```text
tessera_agent_turns_total
tessera_agent_turn_duration_seconds
tessera_langgraph_node_duration_seconds
tessera_guard_decisions_total
tessera_escalations_total
tessera_retrieval_documents_total
tessera_citations_total
tessera_llm_tokens_total
tessera_llm_cost_eur_total
tessera_memory_degradations_total
tessera_language_mismatches_total
tessera_observability_completeness
tessera_proof_consensus
tessera_sensitive_action_transactions_total
```

Allowed attributes:

```text
deployment.target
observability.profile
assurance.level
request_id
trace_id
conversation_id_hash
turn_id
language
model
node
outcome
guard_verdict
rule_id
policy_hash
prompt_hash
corpus_hash
citation_count
retrieval_hit_count
estimated_cost_eur
proof_quality
proof_consensus
```

Forbidden attributes:

```text
raw_prompt
raw_completion
iban
pan
email
phone
access_token
secret
full_name
raw_account_id
raw_card_id
metric_label.conversation_id
metric_label.turn_id
```

High-cardinality identifiers may be trace attributes when redacted or hashed;
they must not become metric labels.

## Privacy Gateway

Every export passes through a Privacy Gateway:

- allowlist attributes
- stable hashing for correlation IDs
- PII pattern screening
- prompt and completion redaction by default
- secret scanning
- telemetry quarantine when unsafe
- explicit declassification workflow for sensitive incident review

Telemetry is a data exfiltration vector. The gateway treats it as one.

## Langfuse as LLM cockpit

Langfuse should be an optional LLMOps cockpit, not the foundation.

It is valuable for:

- readable agent traces
- sessions and conversations
- prompt management
- datasets
- experiments
- human feedback
- scoring and evaluations
- prompt/version metadata
- costs and latencies
- demos and investigations

It should not be required for:

- serving a request
- audit integrity
- SLO measurement
- evidence bundle generation
- privacy proof
- cloud/on-prem parity

If Langfuse disappears or is down:

- OpenTelemetry spans continue
- metrics continue
- structured logs continue
- audit events continue
- evidence bundles continue
- the dashboard marks `llmops_view=degraded`

This creates the desired split:

```text
OpenTelemetry = portable truth spine
Langfuse = polished LLMOps view
Audit trail = compliance proof
Dashboard = operational cockpit
```

## LLMOps control loop

Langfuse should be used fully where it is strong: prompt management, datasets,
experiments, feedback, scores, trace review, and LLM cost analysis. The design
constraint is that Tessera keeps canonical artifacts in the repository or in
its evidence store, so the system remains portable and reviewable without
Langfuse.

Canonical sources:

```text
Prompts:
  src/tessera/agent/prompts/{fr,de,en}.yaml

Eval dataset:
  eval/failures/*.json

Guard policy:
  src/tessera/guard/policy.yaml

Evidence:
  evidence_bundle.v1.json

Telemetry contract:
  docs/observability-contract.md
  src/tessera/observability/schema.py
```

Langfuse workbench roles:

```text
Prompt management:
  edit candidates, compare variants, review traces, collect feedback,
  prepare rollback decisions

Datasets:
  group eval cases, incident-derived samples, golden traces, parity scenarios,
  expose dataset UI and experiment runs

Experiments:
  run prompt A/B, model comparisons, retrieval-depth variants, guard-policy
  candidates, frontier-vs-local comparisons

Evaluation:
  score correctness, citation coverage, refusal quality, cost, latency,
  escalation behavior, and reviewer feedback
```

Promotion path:

```text
Langfuse experiment
  -> candidate selected
  -> export or diff
  -> pull request against YAML / eval JSON / policy YAML
  -> eval harness
  -> assurance conformance checks
  -> merge
  -> deployment manifest records prompt_hash / dataset_hash / policy_hash
```

This prevents a silent production change from a UI-only prompt edit. Langfuse
can be the workbench, but a deployable Tessera state is still code-reviewed,
versioned, tested, and auditable.

### Prompt management

Prompt management has two layers:

- Langfuse manages candidates, comparisons, annotations, trace review, and
  experiments.
- Tessera YAML prompts remain the canonical deployable prompt source.

Every turn should record:

```text
prompt_family
prompt_version
prompt_hash
experiment_id
experiment_variant
promotion_status
```

Raw prompts are forbidden in general telemetry. If a prompt snapshot is needed
for investigation, it must be redacted or attached to a controlled evidence
bundle under the profile's declassification workflow.

Prompt lineage must be queryable in both directions:

```text
prompt version
  -> prompt_hash
  -> Langfuse runs and scores
  -> eval scorecard result
  -> production traces
  -> evidence bundles
  -> promotion or rollback decision
```

A prompt rollback follows the same governance path as a promotion: a candidate
rollback is selected from Langfuse evidence, proposed as a PR against the YAML
prompt source, tested by the eval harness, checked by assurance conformance, and
then deployed with a new manifest.

### Datasets

Tessera should treat datasets as governed artifacts:

- `eval/failures/*.json` remains the canonical non-regression dataset.
- production incidents can create redacted dataset candidates.
- golden traces become datasets for observability regression.
- cloud/on-prem parity scenarios become datasets for deployment-profile
  comparison.
- Langfuse datasets can mirror or group these artifacts for experiment UX.

Dataset promotion path:

```text
production incident
  -> evidence bundle
  -> redaction check
  -> dataset candidate
  -> eval/failures/NN_short_name.json
  -> scorecard and assurance tests
```

No dataset may store raw PII. Dataset records carry hashes and evidence
references, not customer secrets.

### Experiments

Experiments should compare both answer quality and assurance quality.

Experiment dimensions:

- prompt variant
- model profile: frontier versus local
- retrieval depth
- reranking strategy
- guard policy candidate
- memory backend
- language: FR / DE / EN
- deployment profile: cloud versus on-premises

Experiment metrics:

- task pass rate
- safety pass rate
- citation coverage
- escalation correctness
- latency p95
- token and cost deltas
- guard deny false positives
- language mismatch rate
- observability completeness
- proof consensus
- evidence bundle completeness

Promotion rule:

```text
An experiment cannot be promoted only because answer quality improves.
It must also preserve privacy, audit, evidence, cloud/on-prem parity, and proof
SLOs for the target profile.
```

### Self-healing and degraded LLMOps

Self-healing must cover the LLMOps layer without putting it in the critical
path:

```text
Langfuse down:
  continue serving, keep OTel/audit/evidence, mark llmops_view=degraded

Collector down:
  buffer locally according to profile, prioritize audit and evidence

GCP exporter down:
  keep local/Collector queue, mark cloud_export=degraded

Audit sink down:
  regulated profiles fail closed or enter explicit critical degraded mode

Experiment metadata missing:
  continue the turn, record experiment_attribution=unknown, open evidence gap

Prompt hash mismatch:
  block promotion, emit assurance alert, require operator review
```

Self-healing is not silent recovery. Every fallback produces a structured event,
dashboard state, proof-quality impact, and runbook link.

## Proof-Carrying Tool Calls

This is the invention candidate.

Current agent systems often execute a tool call based on a policy verdict that
is recorded separately from the execution. The gap creates ambiguity: did the
tool execution correspond exactly to the policy decision, with the same
arguments and context?

Proof-Carrying Tool Calls close the gap. A sensitive tool execution carries a
short-lived decision proof.

Example proof:

```json
{
  "decision_id": "dec_01JZ...",
  "tool": "card_block",
  "argument_hash": "sha256:...",
  "context_hash": "sha256:...",
  "policy_hash": "sha256:...",
  "rule_id": "own_card_only",
  "verdict": "allowed",
  "reason_code": "actor_owns_target_card",
  "issued_at": "2026-06-07T10:00:00Z",
  "expires_at": "2026-06-07T10:00:30Z",
  "evidence_level": "auditable"
}
```

The tool adapter validates:

- proof is present for sensitive actions
- proof verdict is `allowed`
- proof has not expired
- tool name matches
- argument hash matches actual arguments
- context hash matches actor/target context
- policy hash matches active policy
- decision ID has not been replayed

Mismatch produces a blocked action, audit entry, trace span, and evidence gap.

Upstream PR candidate for `mcp-firewall`:

- stable `DecisionRecord` JSON schema
- `decision_id`
- `policy_hash`
- `rule_id`
- `reason_code`
- canonical argument hashing
- optional TTL
- redaction metadata
- OpenTelemetry hooks
- replay / mismatch tests

Tessera-specific layer:

- actor/intent/target evidence
- banking authorization chain
- causal and normative evidence
- action transactions
- evidence bundles
- DORA/GDPR/CNIL/BaFin control mapping

## Sensitive Action Registry

Sensitive actions are declared, not inferred ad hoc:

```yaml
actions:
  card_block:
    proof_required: true
    audit_required: true
    evidence_level: L3
    actor_scope: authenticated_customer
    target_scope: own_card_only
    replay_protection: required

  account_balance:
    proof_required: true
    audit_required: true
    evidence_level: L3
    target_scope: own_account_only

  ticket_escalate:
    proof_required: false
    audit_required: true
    evidence_level: L2
```

Action-level SLOs:

- 100% of `card_block` attempts have valid proof or explicit denial.
- 100% of third-party balance attempts are refused.
- 100% of sensitive denials are audited.
- 0 expired or replayed proofs are accepted.

## Action transactions

Sensitive actions are observed as transactions:

```text
BEGIN_ACTION
  intent_detected
  target_resolved
  policy_evaluated
  proof_issued
  tool_invoked
  result_observed
  audit_emitted
  evidence_committed
END_ACTION
```

States:

```text
planned
proof_required
proof_issued
execution_started
execution_succeeded
execution_failed
blocked
expired
replay_detected
evidence_committed
```

An action is complete only when execution, audit, and evidence are coherent.

## Event sourcing and Shadow Verifier

Dashboards are not the source of truth. Tessera emits a canonical event stream.

The Shadow Verifier consumes it and checks invariants out of band:

```text
No sensitive ToolExecutionStarted without valid ProofIssued.
No GuardDeny without AuditEmitted.
No regulatory answer without CitationEvidence.
No action transaction without transaction_id.
No expired proof accepted.
No argument hash mismatch accepted.
```

This makes observability independently checkable. The runtime can be wrong; the
verifier still flags gaps.

## Proof consensus

Sensitive decisions reconcile multiple sources:

```text
runtime event
OTel span
audit entry
tool result
evidence bundle
Langfuse run (optional)
```

Each source has a trust weight:

```text
signed audit: high
policy decision: high
tool result: high
evidence bundle: high
OTel span: medium
Langfuse run: optional/medium
dashboard cache: low
```

Example:

```text
Runtime: tool blocked
Audit: denied
OTel: guard span denied
Bundle: rejected_path present
Langfuse: tool not executed
Consensus: 5/5, consistent
```

Divergence taxonomy:

- `missing_audit`
- `span_without_audit`
- `audit_without_action`
- `tool_without_proof`
- `langfuse_mismatch`
- `bundle_unsigned`
- `policy_hash_mismatch`

## Evidence bundles

An evidence bundle is the portable audit object for a turn or action.

It is redacted, signed in regulated profiles, and versioned:

```json
{
  "schema": "tessera.evidence_bundle.v1",
  "turn_id": "...",
  "conversation_id_hash": "...",
  "profile": "cloud_gcp_regulated",
  "assurance_level": "L4",
  "trace_id": "...",
  "policy_hash": "sha256:...",
  "prompt_hash": "sha256:...",
  "corpus_hash": "sha256:...",
  "model": "vertex:...",
  "language": "fr",
  "decision_rationale": {},
  "authorization_chain": [],
  "rejected_paths": [],
  "proof_consensus": "5/5",
  "privacy_status": "redacted",
  "signature": "ed25519:..."
}
```

Bundles compose smaller evidence units:

- language detection evidence
- retrieval evidence
- guard decision evidence
- LLM call evidence
- citation evidence
- escalation evidence
- audit emission evidence
- proof-carrying tool call evidence

This makes gaps precise: missing citation evidence is different from missing
audit evidence.

## Causal and normative evidence

Tessera should not only show what happened. It should show why the decision was
made and whether it matched the expected policy.

Causal evidence:

```json
{
  "decision": "escalate",
  "primary_reason": "stolen_card_requires_human_handoff",
  "supporting_evidence": [
    "guard_decision_evidence",
    "escalation_evidence",
    "audit_emission_evidence"
  ],
  "rejected_paths": ["self_service_card_unblock"],
  "proof_quality": "complete"
}
```

Normative evidence:

```json
{
  "expected_behavior": "regulatory_answer_must_include_citation",
  "observed_behavior": "answer_with_2_citations",
  "compliance_verdict": "pass",
  "evidence_refs": ["citation_evidence", "retrieval_evidence"]
}
```

The audit question becomes answerable:

> Tessera did X, because of Y, and X matched policy Z. Here is the proof.

## Temporal assurance

Some guarantees are temporal:

```yaml
guard_deny_must_be_audited:
  when: guard.decision.outcome == "denied"
  must_happen_within: 2s
  required_events:
    - audit.emitted
    - metric.guard_denied.incremented

stolen_card_must_escalate:
  when: risk.category == "stolen_card"
  forbidden_events:
    - tool.card_unblock.called
  required_events:
    - escalation.created
    - audit.emitted
```

Tessera verifies not only that events exist, but that they happen in the right
order, in the right time window, without forbidden events.

## Assurance profiles as code

The long-term shape is a **Tessera Assurance Compiler**.

Input:

```text
assurance.yaml
telemetry_contract.yaml
observability_policy.yaml
sensitive_actions.yaml
control_mapping.yaml
```

Compiled outputs:

- runtime config
- OpenTelemetry Collector config
- Terraform alert/SLO expectations
- Grafana/GCP dashboard expectations
- Langfuse metadata
- CI conformance tests
- audit report
- evidence bundle schema
- runbook links

Runtime enforcement examples:

- regulated profile without audit sink: fail startup or explicit degraded mode
- Langfuse enabled without redaction gateway: refuse startup
- metric with high-cardinality label: test failure
- sensitive action without bundle: alert
- guard deny without audit: proof SLO violation

## Dynamic evidence depth

Tessera should not capture maximum telemetry by default. It should collect the
minimum necessary evidence, then deepen evidence according to risk.

Risk-aware behavior:

```text
simple question
  -> sampled trace, aggregate metrics

regulatory question
  -> citation evidence, prompt hash, retrieval evidence

card stolen / fraud / PII risk
  -> full trace, evidence bundle, audit, escalation evidence

prompt injection
  -> guard evidence, red-team tag, eval candidate, retention priority

observability degraded
  -> local buffer, dashboard degraded, increased proof monitoring
```

This reconciles GDPR minimization with DORA-style traceability.

## Dashboard and operator UX

The dashboard `/observability` should not replace GCP, Grafana, or Langfuse.
It should act as Tessera's mission control:

- active profile
- assurance target and current level
- exporter health
- Collector health
- Langfuse health
- audit sink health
- proof SLO status
- proof consensus
- observability completeness
- recent sensitive action transactions
- recent evidence gaps
- links to Cloud Trace / Grafana / Langfuse / audit entry
- button to generate a redacted evidence bundle

The UI should present proof in human language:

```text
Decision: escalated
Proof quality: complete
Audit: present
Trace: linked
Citations: 3
Privacy: redacted
Langfuse: optional, available
```

## Simulation and digital twin

The eval harness should expand from response correctness to assurance
correctness.

Simulation matrix:

```text
deployment profile: cloud_gcp / on_prem / air_gapped
language: FR / DE / EN
model: frontier / local
observability state: healthy / degraded
risk level: low / high / critical
```

Scenarios:

- own-card block
- third-party card block
- GDPR question with citations
- prompt injection
- Langfuse down
- Collector down
- audit sink down
- argument tampering
- proof replay
- policy hash mismatch

Output:

```text
assurance_twin_report.json
cloud_profile_score
on_prem_profile_score
proof_consensus
invariant_failures
privacy_findings
missing_evidence
recommended_fix
```

This becomes an Observability Digital Twin: a simulated environment for testing
the assurance layer before production.

## Compliance and governance

Controls should map to evidence:

```yaml
controls:
  pii_no_export:
    required_events:
      - telemetry.redaction.checked
    forbidden_attributes:
      - iban
      - pan
      - raw_prompt

  guard_deny_audited:
    required_events:
      - guard.decision
      - audit.emitted

  regulatory_answer_cited:
    required_evidence:
      - retrieval_evidence
      - citation_evidence
```

Evidence lifecycle:

- creation
- redaction
- signature
- storage
- access
- export
- retention
- erasure/anonymization
- legal hold
- deletion or crypto-erasure

Observing observability access is mandatory:

- who opened a bundle
- when
- why
- what role
- whether dual control was required

## Threat model for observability

Threats:

- PII leak through logs/traces
- prompt injection into log fields
- forged trace IDs
- high-cardinality metric attack
- replayed proof
- altered evidence bundle
- audit sink failure
- Langfuse compromise
- Collector outage
- dashboard cache divergence

Required defenses:

- Privacy Gateway
- allowlist attributes
- canonical hashing
- proof TTL
- replay detection
- signature and hash chain
- Shadow Verifier
- proof consensus
- telemetry kill switch
- local signed fallback

## Implementation roadmap

### V1: visible premium core

Goal: deliver a credible demo and code foundation without building the whole
assurance universe.

Deliverables:

- ADR 0010 and this architecture paper
- telemetry contract draft
- `ObservabilitySettings` profile fields
- OTel Collector profile config skeletons
- Langfuse optional config and health status
- Langfuse prompt/dataset/experiment metadata wiring
- Privacy Gateway utilities and tests
- spans for turn and LangGraph nodes
- metrics for node latency, escalation, retrieval, citations, LLM tokens/cost
- structured logging replacing `sys.stderr.write` on agent paths
- `/observability/status`
- dashboard `/observability`
- evidence bundle v1 generator
- conformance tests for PII, cardinality, `/metrics`, spans, audit correlation

### V2: proof-carrying actions

Deliverables:

- sensitive action registry
- proof-carrying tool call prototype
- canonical argument hashing
- action transaction IDs
- replay detection
- evidence bundle action section
- proof gap dashboard
- eval harness checks for proof and audit, not only final answer
- upstream `mcp-firewall` PR draft for decision evidence

### V3: assurance verification

Deliverables:

- Shadow Verifier
- invariant DSL
- proof consensus
- signed bundles
- assurance profiles as code
- LLMOps promotion gates
- simulation matrix
- golden traces
- cloud/on-prem parity report
- offline evidence viewer

### V4: continuous assurance

Deliverables:

- regulatory control graph
- external auditor mode
- evidence ledger
- assurance compiler
- policy replay lab
- digital twin reports
- proof-driven release gate

## V1 cut line

Do not implement everything at once. V1 should be:

```text
Telemetry Contract
Privacy Gateway
Dynamic cloud/on-prem profiles
Collector-first topology
Langfuse optional
LLMOps control loop
Agent/safety metrics
LangGraph spans
Evidence Bundle v1
/observability status and dashboard
Conformance tests
ADR
```

The invention work can start as a design spike:

```text
Proof-Carrying Tool Calls
Sensitive Action Registry
Action Transaction
Upstream mcp-firewall PR proposal
```

## Open questions

- Should proof-carrying tool calls live first in Tessera or be proposed directly
  to `mcp-firewall`?
- Should regulated profiles fail closed when the Collector is down, or continue
  with local signed buffer?
- What evidence can be stored under GDPR erasure versus legal hold?
- Should raw prompts ever be available under dual-control review, or should
  Tessera keep only redacted prompt snapshots?
- Which trace backend should be the default on-premises target: Tempo or Jaeger?
- Should the evidence bundle be stored in Postgres, object storage, or a local
  append-only JSONL ledger for V1?

## Completeness appendix

This appendix preserves the wider idea backlog from the design session. Some of
these items are already covered in the main architecture; others are deliberate
V2+ candidates so the V1 scope remains shippable.

### Assurance artifacts

- **OBOM / Observability Bill of Materials**: machine-readable inventory of
  exporters, destinations, retention, sampling, dashboards, alerts, privacy
  policy, evidence schemas, and telemetry contract versions.
- **Telemetry manifest**: signed deployment record containing commit, profile,
  prompt hashes, policy hash, corpus hash, exporter config, retention, and
  redaction policy.
- **Machine-readable compliance pack**: JSON/YAML package linking controls,
  evidence, hashes, signatures, retention, incidents, eval outcomes, and
  limitations.
- **Proof-carrying release**: release artifact that includes the telemetry
  contract, assurance profile, OBOM, golden traces, privacy proof, dashboard
  expectations, and evidence schemas.
- **Assurance debt register**: visible list of known evidence gaps, accepted
  limits, missing signatures, missing replay tooling, or non-blocking degraded
  integrations.

### Verification and trust

- **Independent verifier CLI**: a command such as `tessera verify-evidence`
  that validates a bundle without trusting the running service.
- **Telemetry transparency log**: append-only log of manifests, bundles,
  attestations, and audit reports, with hash chaining.
- **Time attestation**: signed timestamp metadata proving when evidence was
  produced.
- **Cross-backend reconciliation**: compare GCP, Grafana/Tempo, Langfuse,
  audit logs, and evidence bundles for the same turn.
- **Observation of non-events**: prove that forbidden events did not occur,
  such as no third-party balance tool call or no regulatory answer without
  citation.
- **Telemetry forgery detection**: detect forged trace IDs, events out of
  sequence, audit without parent span, span without audit, timestamp drift, or
  payloads that try to impersonate structured logs.

### Governance and audit UX

- **Trust Center local**: internal page exposing profile, OBOM, controls,
  retention, exporters, latest attestation, assurance score, and evidence
  status.
- **External auditor mode**: read-only view with redacted evidence, controls,
  retention, incidents, audit access logs, and proof quality.
- **Dual-control forensics**: sensitive bundle access requires operator request
  and auditor approval.
- **Observability access audit**: every trace, bundle, audit entry, or Langfuse
  session consultation is itself audited.
- **Legal hold versus GDPR erasure**: preserve minimal signed proof while
  deleting, anonymizing, or crypto-erasing customer data when required.
- **Evidence lifecycle**: explicit creation, redaction, signature, storage,
  consultation, export, retention, erasure, legal hold, and deletion states.
- **Assurance operating model**: owners, SLAs, runbooks, severity levels, proof
  requirements, and closure criteria for SRE, ML, compliance, audit, and
  support personas.

### Metrics, scores, and reporting

- **Time-to-evidence metric**: measure how quickly an operator can answer
  "why did this response happen?" from trace, audit, citations, prompt hash,
  policy hash, and bundle.
- **Evidence confidence**: classify bundles as `complete`, `partial`,
  `degraded`, or `untrusted`.
- **Why-sampled / why-retained**: record why a turn was retained, sampled, or
  minimized.
- **Trace quality score**: score whether logs, metrics, trace, audit, evidence,
  and Langfuse are linked.
- **Operational readiness score**: report cloud readiness, on-prem readiness,
  LLM trace completeness, audit integrity, privacy risk, and proof consensus.
- **Control coverage heatmap**: map GDPR, DORA, CNIL, and BaFin controls to
  observed evidence coverage.
- **Executive evidence report**: non-technical summary of traffic, escalations,
  PII status, p95 latency, cost, incidents, controls, and known gaps.
- **Assurance narrative generator**: human-readable explanation of period,
  incidents, proofs, risks, and corrective actions.

### Release and regression

- **Golden traces**: versioned expected traces for critical scenarios such as
  prompt injection, stolen card escalation, GDPR citation, and tool misuse.
- **Release assurance diff**: before merge, show spans, metrics, fields,
  labels, privacy changes, dashboard expectations, and proof coverage changes.
- **Observability readiness gate**: deployment is ready only if app, Collector,
  audit sink, and required telemetry destinations satisfy the active profile.
- **Proof error budget**: release gate or runtime strictness increases when too
  many proof gaps occur.
- **Evidence-to-commit closure**: incident cannot close until bundle, root
  cause, eval case, fix, commit, and post-fix result are linked.
- **Trace-to-eval**: convert redacted production incidents into
  `eval/failures/NN_short_name.json` candidates.
- **Counterfactual replay**: compare an incident against another model, prompt,
  policy, retrieval depth, or cloud/on-prem profile.

### Resilience and self-healing

- **Observability resilience mode**: if Collector, GCP exporter, Grafana,
  Langfuse, or audit destination fails, Tessera buffers, degrades explicitly,
  preserves audit priority, and reconciles later.
- **Telemetry backpressure policy**: reduce normal sampling under load while
  preserving incident, guard deny, escalation, and audit-critical evidence.
- **Observability failure-mode policy**: define what happens when Langfuse,
  Collector, metrics, audit sink, evidence signing, or privacy gateway fails.
- **Kill-switch policy**: if telemetry leakage is suspected, cut optional
  exporters, keep signed audit, alert P0, and enter minimal safe mode.
- **Vendor exit drills**: regularly simulate Langfuse, GCP exporter, Collector,
  Grafana, Tempo, audit bucket, or storage failure.
- **Chaos observability drills**: inject Ollama down, Vertex timeout, Postgres
  slow, Collector unavailable, audit sink inaccessible, retrieval empty, or
  corrupted evidence.

### Product and investigation UX

- **Evidence UX**: a story view that shows request, language, retrieval, guard,
  LLM, citations, audit, and bundle in chronological order.
- **Offline evidence viewer**: local viewer for signed bundles in air-gapped
  environments.
- **Evidence query language**: auditor-oriented queries such as guard denies
  on `card_block`, regulatory answers without citations, incidents without eval
  cases, or turns where Langfuse was degraded.
- **Trace-to-runbook**: given a turn or incident, surface the relevant runbook
  and the proof required before closure.
- **Automated RCA assistant**: produce likely cause, observed signals, runbook,
  evidence links, and candidate eval case from a `turn_id`.
- **Operator annotations**: audited annotations that can close incidents,
  create eval candidates, add Langfuse feedback, or link a fix commit.
- **Synthetic safe tenant**: permanent fake customer used for probes, demos,
  screenshots, chaos drills, and assurance simulation without real PII.

### Security and risk intelligence

- **Semantic risk taxonomy**: classify turns as PII, tool misuse,
  hallucination, citation gap, escalation failure, language mismatch, cost
  anomaly, or observability gap.
- **Risk-aware telemetry**: increase evidence depth for high-risk turns and
  minimize routine traffic.
- **Temporal attack detection**: detect multi-turn injection campaigns across
  language switching, base64, repeated probing, tool pressure, and policy
  bypass attempts.
- **Telemetry kill-chain detection**: detect attempts to inject logs, erase
  audit, overload metric cardinality, forge trace IDs, or corrupt evidence.
- **Differential privacy for analytics**: keep long-term product statistics
  useful without exposing individual user trajectories.
- **Prompt/corpus provenance**: every relevant turn records prompt hash, corpus
  hash, policy hash, model version, Tessera version, and deployment manifest.

### Compliance and evidence modeling

- **Regulatory control graph**: map DORA/GDPR/CNIL/BaFin control -> Tessera
  policy -> telemetry event -> evidence -> eval case -> runbook.
- **Assurance knowledge graph**: turn -> trace -> audit -> citation -> control
  -> risk -> incident -> eval -> fix.
- **Control-to-code traceability**: each control points to implementation,
  tests, metrics, and evidence.
- **Policy compiler**: compile declarative controls into redaction rules, tests,
  alerts, span requirements, and audit documentation.
- **Property-based observability testing**: generate variations across language,
  tool, target, audit state, Langfuse state, Collector latency, policy hash,
  argument tampering, and proof replay.
- **Temporal model checking, lightweight**: verify critical state machines such
  as `planned -> policy_evaluated -> proof_issued -> executed -> audited`.

## Final architecture sentence

Tessera Observability Assurance Layer turns traces, logs, metrics, audit events,
runtime guard decisions, Langfuse runs, and eval outcomes into a portable,
redacted, multi-source chain of proof for every sensitive banking-agent
decision, with dynamic GCP/on-prem profiles and a path to proof-carrying tool
calls upstreamed into `mcp-firewall`.
