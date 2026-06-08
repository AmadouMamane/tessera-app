# 0010 — Frontier-grade LLM/agent observability (OTel backbone, dual deployment)

- Status: accepted, **to be implemented in full**
- Date: 2026-06-08
- Deciders: Tessera maintainers
- Branch: `feature/observability_claude_powered` (branched from
  `kebab/dashboard-auth-rbac`, **not** from `feature/observability_refinement`)
- Related: 0005 (tools vs workers), 0007 (agent memory), 0008 (security
  hardening), 0009 (dashboard auth/RBAC), `docs/eval.md`, `docs/on_prem.md`,
  `docs/threat-model.md`
- Idea radar: `docs/observability-ideas.md` (200 ideas, 46 sub-axes; canonical
  IDs referenced as `#N` from here)

## Context

### What exists today (the baseline on this branch)

Observability on this branch is *classical telemetry*, not LLM/agent
observability:

- **Traces** — OpenTelemetry SDK exporting to Cloud Trace **or** an OTLP HTTP
  collector **or** a console fallback (`src/tessera/observability/traces.py`).
- **Metrics** — Prometheus, four series only (`tessera_agent_turns_total`,
  `tessera_agent_turn_duration_seconds`, `tessera_guard_decisions_total`,
  `tessera_llm_estimated_cost_eur`) on `:9090` (`metrics.py`).
- **Logs** — structlog, JSON in prod / console in dev (`logging.py`).
- **GCP** — log retention, an audit-trail log sink to GCS, and the
  `guard_denies` log-based metric, plus the start of a Cloud Monitoring
  dashboard and alert policies (`infra/terraform/observability.tf`).

This answers *"what happened"*. It does not answer the questions a
compliance-grounded banking agent must answer: *was the answer grounded? did the
agent take the right trajectory? is quality regressing? can we prove the audit
trail wasn't tampered with?*

### Branch caveat (load-bearing)

The Langfuse v3 / "Time Travel Replay" work (commit `a3b89bb`) lives on
`feature/observability_refinement` and is **not** on this branch. We deliberately
**do not reuse it** ("repartir propre"): it becomes, at most, prior art. The
architecture below treats Langfuse as one possible *exporter*, not as a
foundation. The decision was made consciously to avoid inheriting a
vendor-shaped design when the whole point is a vendor-neutral backbone.

### What "frontier of the research" means here (2026)

Three things beyond classical traces/metrics/logs:

1. **OTel GenAI Semantic Conventions** (`gen_ai.*`) as the vendor-neutral
   convergence point. OpenLLMetry (Traceloop) and OpenInference (Arize) both
   emit OTel-compatible spans. *Instrument once, export anywhere.* This matches
   Tessera's standing positioning: "the value is in the assembly, not the
   invention."
2. **The trace → dataset → eval flywheel.** Production traces that fail an
   *online* evaluation are auto-curated into the offline non-regression harness.
   This closes the loop with the existing `eval/` harness (the 40 documented
   failures). It is the core of "eval-driven development."
3. **Agent-*trajectory* evaluation**, not just final-answer scoring: tool-call
   correctness, step efficiency, loop detection, and RAG faithfulness/citation
   along the path (RAGAS-style metrics).

### Priority for this iteration

**Interview demo** (targeting frontier AI labs): maximise both the technical
"wow" and the defensibility of the narrative (sovereign on-prem *and* GCP
mastery). Breadth of a coherent story is weighted over exhaustive depth on any
single axis — but the user's stated intent is to **implement the full scope**,
phased per the day-twenty discipline (cut, never extend).

## Decision

### The backbone is OpenTelemetry, not a vendor

The canonical backbone is **OpenTelemetry + the GenAI Semantic Conventions,
routed through an OpenTelemetry Collector.** Application code emits vendor-neutral
`gen_ai.*` spans; the Collector decides where they go. Langfuse, Phoenix, Cloud
Trace, and Vertex are *interchangeable backends downstream*.

```
LangGraph nodes / tools / RAG / guard
        │  (gen_ai.* spans + span events; agent spans: invoke_agent / execute_tool)
        ▼
  OTel Collector  ──►  [PII-redaction processor]  ──┐
        │                                            │
   profile = on_prem                            profile = gcp
        ▼                                            ▼
 Arize Phoenix (self-host)                  Cloud Trace + GMP
 + Grafana LGTM (Loki/Tempo/Mimir)          + Cloud Logging / Log Analytics
 + judge = Llama 3.3 70B (local, sovereign) + Vertex AI Gen AI Eval Service
                                            + BigQuery (analytics sink) + Looker Studio
```

Without this backbone there would be two instrumentations to maintain and no
architecture story. With it, the two deployment profiles come essentially for
free — they differ only in Collector configuration.

### Canonical LLM-observability backend: Arize Phoenix

We pick **one** canonical backend to avoid diluting the narrative, and it is
**Arize Phoenix**:

- **OTel-native** (OpenInference conventions) — reinforces the backbone thesis.
- **Light self-host** — a single container; the sovereign profile starts in
  seconds on Apple Silicon, which matters for a live demo.
- **Eval/RAG strength** — built-in LLM-as-judge and RAG metrics (hallucination,
  QA-correctness, retrieval-relevance) feed the flywheel directly into `eval/`.

**Langfuse is demoted to an optional fan-out exporter.** Because every backend
consumes OTel, adding Langfuse later (for its ops UI: sessions, cost,
human-annotation queue) is a one-line Collector exporter, not a rewrite. We do
not run it by default; we keep the door open. This *is* the decoupling thesis in
practice.

| | Phoenix (canonical) | Langfuse (optional later) |
|---|---|---|
| Role | eval/dev-time, RAG, drift | ops UI: sessions, cost, annotation |
| When | during the `eval/` harness, online eval | prod ops, if/when wanted |
| Self-host | single container | PG + Clickhouse + Redis + MinIO |

**On conventions:** target the **official OTel `gen_ai.*`** semconv as the goal,
leaning on OpenInference/OpenLLMetry instrumentation where it already aligns. The
bet is on the standard, not on a single vendor's convention.

### Two deployment profiles, one setting

| Layer | `on_prem` (sovereign) | `gcp` (mastery) |
|-------|-----------------------|-----------------|
| Collection | OTel Collector | OTel Collector → Cloud Trace |
| LLM traces | **Phoenix** (self-host) | Cloud Trace + BigQuery export |
| Metrics | Prometheus + Grafana | **Managed Service for Prometheus (GMP)** |
| Logs/infra | Loki + Tempo (LGTM) | Cloud Logging + Log Analytics (BQ) |
| **Eval / judge** | **Llama 3.3 70B local** = sovereign judge | **Vertex AI Gen AI Eval Service** (Gemini judge) |
| Dashboards | Grafana | Cloud Monitoring + Looker Studio |

A single validated setting selects the profile, mirroring the
`deployment_mode` pattern from ADR 0008 (`cloud_run` / `on_prem`).

### The two sovereignty/EU differentiators (always on)

- **The sovereign judge.** In `on_prem`, the LLM-as-judge runs on the local
  Llama 3.3 70B: *no customer data leaves the premises to be evaluated.* For EU
  banking this is the DORA/GDPR argument that a cloud judge cannot make.
- **PII-safe traces by design.** A redaction processor in the OTel Collector
  (IBAN/amount regexes + Microsoft Presidio) scrubs spans **before** any backend
  receives them. Observability never becomes a leak channel — continuous with
  the posture of `guard/`. Redaction is also implemented in-process
  (`observability/redaction.py`) as defence in depth.

### The frontier differentiators to implement

Grouped by leverage. The user's intent is to implement all of them; the day-
twenty discipline governs the *order*, not the *scope*.

**Tier A — the demo-defining differentiators**

1. **Deterministic trace replay / regression-from-production.** Capture enough
   in each trace (seed, retrieved context, tool responses, prompt version) to
   **re-run a production trace against a new model/prompt and diff the
   behaviour**. Every real conversation becomes a regression test. Combined with
   the flywheel: prod trace → replay against `claude-opus-4-8` vs local Llama →
   faithfulness diff. Supersedes the "time travel" idea from the other branch
   with a rigorous, OTel-grounded version. → `observability/replay.py`.
2. **LLM-judge calibration & bias.** Do not trust the judge blindly: measure
   **judge↔human agreement** (Cohen's κ on an annotated sample) and track known
   judge biases — position bias, verbosity bias, self-preference. The sovereign
   angle: show that a *small, well-calibrated local judge* rivals a large cloud
   judge, biases quantified. → `observability/eval/calibration.py`.
3. **Tamper-evident audit + data-residency tagging.** Hash-chain the
   `guard/audit` trail (each decision chained to the previous → a tamper-evident,
   provable log) and tag every span with `data.residency=eu`, which the
   Collector routes EU-only. An observability layer that is itself a compliance
   artefact — unique for a banking demo. Extends `guard/audit.py`.

**Tier B — frontier-of-the-standard architecture moves**

4. **Adopt the OTel *agent* spans**, not only LLM-call spans: `invoke_agent`,
   `execute_tool`, `create_agent` (experimental in the GenAI semconv) on the
   LangGraph nodes and tools. Capture prompt/completion content as **span events
   with an opt-in, PII-gated capture flag** (the direction the OTel GenAI SIG
   took, vs span attributes). → `observability/semconv.py`, `instrument.py`.
5. **Eval-as-telemetry.** Round-trip eval scores back into OTel as
   metrics/spans, so faithfulness, groundedness, and tool-accuracy become time
   series in Grafana / Cloud Monitoring with **alerts when a score drops**. A
   quality regression can page an on-call, not just a latency spike. →
   `observability/eval/scores.py`.
6. **Cost-aware (tiered) online eval.** Cheap heuristics/guardrails on **100%**
   of traffic; the LLM judge on a **stratified sample + 100% of flagged traces**.
   **Disagreement between the guard and the judge becomes the signal** that
   routes a trace to human annotation (active learning / hard-example mining). →
   `observability/eval/online.py`.

**Tier C — depth signals**

7. **Per-language drift** (Tessera-specific, multilingual): input *and* output
   distribution drift, separately for FR/DE/EN — catches new injection patterns
   or a regression after a model swap. Uses Phoenix embedding-drift. →
   `observability/drift.py`.
8. **Context ROI + prompt-cache observability.** Correlate retrieval cost ↔
   faithfulness (does expensive context actually improve groundedness?); expose
   prompt-cache hit rates.
9. **Eval gates in CD.** `eval.yml` runs the harness; the next step is **canary +
   auto-rollback if online faithfulness drops below a threshold**. Eval becomes a
   deployment gate, not a report read after the fact.

### The flywheel, concretely

```
prod turn  →  OTel trace (gen_ai.* + agent spans)
   └─ online eval (tiered): guardrails 100%, LLM judge on sample + flagged
        ├─ scores round-tripped into OTel  (eval-as-telemetry, Tier B/5)
        ├─ guard↔judge disagreement → human annotation queue  (Tier B/6)
        └─ confirmed failures → eval/failures/NN_*.json  (curated regression case)
   └─ replay harness re-runs curated traces against candidate model/prompt (Tier A/1)
```

## Structure changes to the canonical tree

This ADR extends `src/tessera/observability/` and adds Collector/infra wiring.
The shape below becomes canonical for the observability surface (the rest of the
tree is unchanged):

```
src/tessera/observability/
├── __init__.py
├── profiles.py        # deployment-profile selection (on_prem / gcp)
├── traces.py          # existing — migrated to gen_ai.* semconv
├── metrics.py         # existing — extended (latency p50/p95/p99, cache hits)
├── logging.py         # existing
├── semconv.py         # gen_ai.* attribute + agent-span helpers
├── instrument.py      # LangGraph node + tool instrumentation (invoke_agent/execute_tool)
├── redaction.py       # in-process PII redaction (defence in depth)
├── replay.py          # deterministic trace replay / regression-from-prod   (Tier A/1)
├── drift.py           # per-language input/output drift                     (Tier C/7)
└── eval/
    ├── __init__.py
    ├── judge.py        # LLM-as-judge (sovereign Llama / Vertex)
    ├── calibration.py  # judge↔human agreement, bias detection             (Tier A/2)
    ├── online.py       # tiered, cost-aware online eval                     (Tier B/6)
    ├── scores.py       # eval-as-telemetry round-trip                       (Tier B/5)
    └── flywheel.py     # trace → eval/failures curation

infra/observability/
└── otel-collector/
    ├── collector.onprem.yaml    # exporters: Phoenix, Tempo, Loki, Prometheus
    └── collector.gcp.yaml       # exporters: Cloud Trace, GMP, Cloud Logging, BQ

docker-compose.yml     # + phoenix, otel-collector, grafana/LGTM services
infra/terraform/observability.tf  # + GMP, Vertex Gen AI Eval, BigQuery sink, Looker
```

New settings on `ObservabilitySettings` (validated in `settings.py`):

```python
profile: Literal["on_prem", "gcp"] = "on_prem"
otel_collector_endpoint: str | None = None
content_capture: bool = False          # opt-in, PII-gated span events
phoenix_endpoint: str | None = None
judge_model: str | None = None         # sovereign local Llama / Vertex Gemini
online_eval_sample_rate: float = 0.1   # stratified sample; flagged traces always judged
```

## Rollout (day-twenty discipline: cut order, not scope)

1. **Phase 1 — backbone.** Migrate `traces.py` to `gen_ai.*`; stand up the OTel
   Collector; add the `profile` setting. Highest leverage, lowest surface.
2. **Phase 2 — on_prem profile.** Phoenix in `docker-compose`; sovereign local
   judge wired to the harness; agent spans (Tier B/4).
3. **Phase 3 — gcp profile.** GMP + Vertex Gen AI Eval + BigQuery sink in
   Terraform.
4. **Phase 4 — flywheel + eval-as-telemetry** (Tier B/5, B/6) wired to
   `eval/failures/`.
5. **Phase 5 — Tier A differentiators**: replay-regression (A/1), judge
   calibration (A/2), tamper-evident audit + residency tagging (A/3).
6. **Phase 6 — Tier C**: per-language drift (C/7), context ROI + cache (C/8),
   eval gates in CD (C/9).

If the schedule slips, cut from the bottom: Tier C first, then the second
differentiator, never the backbone.

## Consequences

- **New dependencies / services.** OpenTelemetry Collector (sidecar/service);
  Arize Phoenix (self-host, `on_prem`); OTel GenAI instrumentation
  (OpenInference/OpenLLMetry); Microsoft Presidio (PII redaction). GCP-side:
  Managed Service for Prometheus, Vertex AI Gen AI Evaluation Service, a BigQuery
  dataset + Looker Studio. Each is justified by reuse-over-reinvention; none is a
  new framework.
- **The backbone is portable by construction.** One instrumentation, swappable
  backends — adding Langfuse or any OTLP backend later is configuration.
- **Observability becomes a compliance artefact**, not just an ops tool:
  PII-safe traces, a tamper-evident audit chain, EU data-residency routing, and a
  sovereign judge that keeps evaluation data on-prem. This is the EU banking
  semantics the project sells, made concrete.
- **Eval and ops merge.** Quality scores live in the same telemetry as latency
  and cost, alertable and gateable on deploy.
- **Costs / explicit non-goals.** We do **not** invent a new observability or
  eval framework, and we do **not** run Langfuse and Phoenix in parallel by
  default (redundant; one canonical backend). Self-modifying anything from
  telemetry is out of scope, consistent with ADR 0007. The mandatory upstream
  `mcp-firewall` PR is tracked separately and is **not** part of this ADR.
- This ADR adds the observability package shape and the
  `infra/observability/otel-collector/` directory to the canonical tree;
  contributors treat the layout above as canonical for this surface.

## References

- OpenTelemetry GenAI Semantic Conventions — `gen_ai.*` spans, agent spans
  (`invoke_agent` / `execute_tool` / `create_agent`), content-as-events.
- OpenInference (Arize) and OpenLLMetry (Traceloop) — OTel-compatible GenAI
  instrumentation.
- Arize Phoenix — OSS LLM observability + evaluation; RAG metrics; embedding
  drift.
- Langfuse v3 — evaluated as an optional fan-out exporter (prior art on
  `feature/observability_refinement`).
- LLM-as-a-judge literature — judge bias (position, verbosity, self-preference)
  and judge↔human agreement (Cohen's κ); RAGAS (faithfulness, context/answer
  relevance).
- Google Cloud — Managed Service for Prometheus, Vertex AI Gen AI Evaluation
  Service, Cloud Trace, Log Analytics, BigQuery.
- Microsoft Presidio — PII detection/redaction for the Collector processor.
