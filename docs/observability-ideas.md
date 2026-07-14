# Observability — idea catalogue (200 ideas, 19 axes)

Companion to [ADR 0010 — Frontier-grade observability](decisions/0010-frontier-observability.md).
This is the **brainstorm radar**, not a commitment. ADR 0010 holds the decided
architecture (OTel `gen_ai.*` backbone + Collector, Arize Phoenix canonical
backend, `on_prem`/`gcp` profiles, sovereign judge, PII-safe traces) and the
Tier A/B/C differentiators (ideas **1–9**). Everything here extends that radar.

**The numbers are canonical IDs.** Cross-references in code, ADRs, and other
ideas (e.g. "ties #48") point at these. Do not renumber.

> **Transverse primitive (applies everywhere): OTel Baggage.** Propagate
> `language`, `tenant`, `consent`, `residency` as baggage through the whole
> trace so every signal below can be sliced by these dimensions for free.

## Axis index

| Axis | Ideas |
|------|-------|
| 1. Core differentiators (Tier A/B/C) | 1–9 |
| 2. Lineage, attribution & uncertainty | 10–14 |
| 3. Reliability engineering (SRE for LLM) | 15–17 |
| 4. Self-checking & guard signals | 18–19 |
| 5. Human, session & streaming signals | 20–22 |
| 6. Memory, security & sustainability | 23–25 |
| 7. Retrieval & RAG depth | 26–28 |
| 8. Agent & tool correctness | 29–31 |
| 9. Ops & cost frontier | 32–35 |
| 10. Compliance & multilingual | 36–39 |
| 11. Demo & DX (early) | 40–42 |
| 12. On-prem & infra depth | 43–45 |
| 13. Robustness & correctness | 46–48 |
| 14. Regulatory-banking specific | 49–51 |
| 15. Security depth | 52–53 |
| 16. Meta & human-loop | 54–56 |
| 17. Model behaviour (lab-grade) | 57–60 |
| 18. Dual-path frontier↔local | 61–64 |
| 19. Unit economics & product | 65–67 |
| 20. External-dependency reliability | 68–69 |
| 21. Multilingual quality | 70–71 |
| 22. Security & privacy frontier | 72–75 |
| 23. EU regulatory (AI Act) | 76–77 |
| 24. Model/training depth | 78–80 |
| 25. Eval rigour & meta | 81–84 |
| 26. Distributed-trace correctness | 85–86 |
| 27. Graph runtime correctness | 87–90 |
| 28. Telemetry-pipeline health | 91–94 |
| 29. Eval rigour, deeper | 95–97 |
| 30. User & lifecycle | 98–101 |
| 31. System & reusable artifact | 102–114 |
| 32. Organisational | 115–119 |
| 33. Data (what you do with telemetry) | 120–125 |
| 34. Developer experience | 126–130 |
| 35. Human / end-user UX | 131–136 |
| 36. Economic / product | 137–141 |
| 37. Pure research (publishable) | 142–147 |
| 38. Temporal / evolutionary | 148–152 |
| 39. Comparative / competitive | 153–157 |
| 40. Pedagogical | 158–164 |
| 41. Resilience / degradation | 165–170 |
| 42. Interoperability / ecosystem | 171–176 |
| 43. Obs-data governance | 177–181 |
| 44. Edge / real-time | 182–187 |
| 45. Multi-agent / swarm | 188–193 |
| 46. Formal / verification | 194–200 |
| 47. Temporal control (cockpit time rail) | 201 |

---

## 1. Core differentiators — Tier A/B/C (decided in ADR 0010)

**Tier A — demo-defining**
1. **Deterministic trace replay / regression-from-production** — capture enough (seed, retrieved context, tool responses, prompt version) to re-run a prod trace against a new model/prompt and diff behaviour.
2. **LLM-judge calibration & bias** — judge↔human agreement (Cohen's κ); position/verbosity/self-preference bias; small local judge vs large cloud judge.
3. **Tamper-evident audit + data-residency tagging** — hash-chained guard audit; `data.residency=eu` span tag routed EU-only by the Collector.

**Tier B — frontier-of-the-standard**
4. **OTel agent spans + content-as-events** — `invoke_agent`/`execute_tool`/`create_agent`; prompt/completion as PII-gated span events.
5. **Eval-as-telemetry** — round-trip eval scores into OTel metrics/spans; alert on quality drops in Grafana/Cloud Monitoring.
6. **Tiered cost-aware online eval** — heuristics on 100%, LLM judge on stratified sample + flagged; guard↔judge disagreement routes to human annotation.

**Tier C — depth**
7. **Per-language drift** — input/output distribution drift, separate FR/DE/EN.
8. **Context ROI + prompt-cache observability** — retrieval cost ↔ faithfulness; cache hit rates.
9. **Eval gates in CD** — canary + auto-rollback if online faithfulness drops.

## 2. Lineage, attribution & uncertainty
10. **Lineage / response SBOM** — per response, the full bill of materials: model, prompt, retrieved-doc, and guard-policy versions.
11. **Claim-level attribution / provenance graph** — link each claim to the chunk that caused it; a claim with no parent = structural hallucination.
12. **Uncertainty observability** — logprobs/entropy as a hallucination signal; high entropy on factual claims = route to judge.
13. **Firewall efficacy ROC** — TP/FP of the first-party guard over the failure corpus + real prod injections.
14. **End-to-end distributed trace + multilingual canaries** — W3C Trace Context front→BFF→agent→tools; continuous golden FR/DE/EN heartbeat conversations.

## 3. Reliability engineering (SRE for LLM)
15. **Quality SLOs + error budgets** — SLO on faithfulness with burn-rate alerts; a quality regression burns budget like latency.
16. **Shadow / mirror traffic** — duplicate prod to a candidate model in shadow; compare without user impact.
17. **Root-cause "what changed"** — auto-correlate a regression against deploys, model versions, prompt changes (from #10).

## 4. Self-checking & guard signals
18. **Self-consistency / ensemble disagreement** — sample N times, variance = uncertainty (complements #12).
19. **Guard decision explainability** — capture which guard rule fired as span attributes.

## 5. Human, session & streaming signals
20. **Human feedback validates the judge** — thumbs/escalation/re-ask correlated with judge scores; real humans calibrate the LLM judge (#2).
21. **Session-level / goal-completion eval** — did the whole conversation resolve the need? resolution-rate, turns-to-resolution.
22. **Streaming/TTFT observability** — time-to-first-token, inter-token latency, stall detection.

## 6. Memory, security & sustainability
23. **Memory observability (ADR 0007)** — reflector cold path, long-term hit/miss, stored-injection detection on read; span links across turns/sessions.
24. **Continuous red-teaming / jailbreak drift** — replay an adversarial corpus, track attack-success rate over time.
25. **Carbon / Green AI** — energy per inference, on-prem M1 vs cloud GPU (CSRD/ESG angle).

## 7. Retrieval & RAG depth
26. **Retrieval IR metrics online** — recall@k, MRR, nDCG via judge; chunk-utilisation / dead-context detection.
27. **Reranker & hybrid-search contribution** — reranker lift; lexical-vs-vector share (`reranking.py`, `hybrid_search.py`).
28. **Corpus coverage gaps** — queries falling in sparse embedding regions ("no docs on this").

## 8. Agent & tool correctness
29. **Hallucinated-tool / arg validation** — invented tools or malformed args (bad IBAN, impossible amount); tool-call validity rate.
30. **Multi-turn contradiction detection** — turn N contradicts turn N−3 (uses memory, ADR 0007).
31. **Token-budget allocation per node** — system/history/RAG/memory split per turn.

## 9. Ops & cost frontier
32. **Tail-based sampling** — keep 100% of error/flagged/slow traces, sample the rest.
33. **Cost anomaly detection = security signal** — forecast spend; an injection loop burning tokens shows here first.
34. **Online A/B/n experimentation** — serve traffic to prompt/model variants with stat-sig + guardrail metrics.
35. **Continuous profiling (4th OTel signal)** — pprof/Pyroscope on the on-prem hot path (inference, pgvector, embedding, rerank).

## 10. Compliance & multilingual
36. **Consent/governance ops dashboard** — Tier-2 writes blocked for missing consent, TTL purges, erasures fulfilled (ADR 0007).
37. **Language mis-routing / code-switch detection** — German query routed FR; code-switching.
38. **Output PII-leak rate** — model output contains PII absent from input (memorisation).
39. **Privacy budget / k-anonymity on public dashboards** — aggregate metrics can't re-identify (ADR 0009 public surface).

## 11. Demo & DX (early)
40. **Agent-trajectory time-travel UI ("session theater")** — step a trace turn-by-turn with docs/guard/tools.
41. **Golden-trace snapshot diffing in CI** — catch unintended agent-graph shape changes.
42. **Trace-to-repro CLI export** — a failing trace becomes a runnable script (no notebooks — CLAUDE.md).

## 12. On-prem & infra depth
43. **Model-load & Metal/KV-cache (Ollama M1)** — load time, Metal memory pressure, KV-cache use, cold-start.
44. **Capacity / token-demand forecasting** — drive Cloud Run autoscaling + pre-warm.
45. **Multi-region failover + Cloud SQL replication lag** — region health, failover events.

## 13. Robustness & correctness
46. **Robustness eval under noise** — typos, casing, unicode homoglyphs, misspelled IBANs, OCR noise.
47. **Schema/format conformance rate** — structured outputs (tool args, citation format) validity.
48. **Latency critical-path attribution** — decompose a turn: LLM vs retrieval vs rerank vs guard vs network.

## 14. Regulatory-banking specific
49. **Regulatory citation validity** — does "DORA Art. 28(3)" exist and say what's claimed (failure #05 live).
50. **Corpus freshness vs live regulations** — staleness of ingested DORA/CNIL/BaFin/GDPR.
51. **Locale-aware formatting correctness** — `€4 567,89` (FR) vs `€4.567,89` (DE), dates, numbers.

## 15. Security depth
52. **Poisoned-corpus / indirect-injection-via-RAG** — retrieved docs themselves carry injection (OWASP LLM).
53. **Semantic cache false-hit** — cache returns a close-but-wrong answer; correctness, not just hit-rate.

## 16. Meta & human-loop
54. **Eval-cost observability** — the LLM judge costs money; track eval spend.
55. **Annotation-queue health + inter-annotator agreement + escalation SLA** — backlog, time-to-annotate (ties `escalation.py`).
56. **Confidence-gated escalation calibration** — how uncertainty (#12/#18) drives escalation; tune the threshold.

## 17. Model behaviour (lab-grade)
57. **Reasoning-quality / thinking-ROI** — reasoning-token count, reasoning/answer ratio, does more thinking improve correctness.
58. **Refusal-rate calibration** — over-refusal (refuses legit banking) vs under-refusal (does the forbidden).
59. **Sycophancy detection** — agent validates a false user premise.
60. **Toxicity/harmful-output rate** — unsafe output frequency as an online metric.

## 18. Dual-path frontier↔local
61. **Cross-model consistency** — Gemini (Vertex) vs Llama (local) answer divergence; the sovereign path mustn't be quietly worse.
62. **Graceful-degradation observability** — frontier down → local fallback events + quality delta (`llm/router.py`).
63. **Intent-classification / router observability** — product/regulation/account mis-classification rate (`router.py`).
64. **Embedding-version skew** — query vs corpus embedding-version mismatch after a model change.

## 19. Unit economics & product
65. **Cost-per-resolution** — cost to resolve the issue (multi-turn), not cost-per-turn.
66. **Conversation funnel per language** — drop-off, intents leading to escalation, completion rates FR/DE/EN.
67. **Time-to-first-useful-answer** — beyond TTFT (#22), the first genuinely useful answer.

## 20. External-dependency reliability
68. **Tool downstream health + circuit-breaker** — `account_balance`/`card_block` external APIs: timeout/retry/breaker state.
69. **Anomalous-conversation detection** — unsupervised detection of long/looping/repetitive sessions.

## 21. Multilingual quality
70. **Cross-lingual answer consistency** — same semantic query FR/DE/EN should agree (differential testing).
71. **Readability/A11y per language** — reading grade level per language + dashboard a11y (ADR 0006/0009).

## 22. Security & privacy frontier
72. **Unicode steganography detection** — zero-width, bidi overrides, tag-chars carrying hidden instructions.
73. **Embedding inversion privacy risk** — stored vectors can leak source text; observe/mitigate on pgvector.
74. **Multi-tenant cross-tenant leakage** — tenant A's docs/memory surfacing for tenant B; per-tenant quotas.
75. **Watermark / AI-generated provenance** — output identifiable as AI-generated (AI Act transparency).

## 23. EU regulatory (AI Act)
76. **EU AI Act compliance observability** — transparency-disclosure rate, human-oversight events, risk-class logging.
77. **Localization completeness** — missing translations, next-intl default-locale fallbacks (ADR 0006).

## 24. Model/training depth
78. **Fine-tuning / LoRA: eval deltas + catastrophic forgetting** — a FR fine-tune degrading DE.
79. **Judge-model drift** — judge upgrade shifts scores → re-anchor calibration (#2).
80. **KV-cache fine-grained** — prefix reuse across turns, eviction patterns, memory budget (under #43).

## 25. Eval rigour & meta
81. **Ablation observability** — no-RAG / no-memory / no-rerank quality delta = each layer's worth.
82. **Golden-answer / ground-truth staleness** — eval references age as products/regs change (ties #50).
83. **Sampling-bias / stratification health** — is the online-eval sample representative (#6)?
84. **Cost of observability itself** — instrumentation overhead vs budget.

## 26. Distributed-trace correctness
85. **Span propagation under async/parallel** — parallel LangGraph nodes losing context → orphaned spans.
86. **Reproducibility hash / non-determinism detection** — same input → different trace structure (prereq of #1).

## 27. Graph runtime correctness
87. **Graph topology versioning** — alert on unintended node add/remove across deploys.
88. **Tool-call loop/oscillation detection** — same tool called in a cycle; cap it.
89. **Context truncation/overflow observability** — what got dropped on overflow — did we drop the relevant doc (complements #31)?
90. **Mid-stream guard retraction** — guard intervenes on already-streamed tokens (ADR 0007 interrupt design).

## 28. Telemetry-pipeline health
91. **Span cardinality explosion** — high-cardinality labels blow up the metrics backend (and bill).
92. **Instrumentation coverage + garbage-span detection** — "trace coverage"; missing required `gen_ai.*` attrs.
93. **Clock skew across distributed spans** — front→BFF→agent drift corrupting causal order.
94. **Synthetic/canary traffic tagging** — keep canaries (#14) out of prod metrics.

## 29. Eval rigour, deeper
95. **Multi-judge ensemble agreement** — judges' mutual agreement; disagreement = hard case (vs #18 which is the agent).
96. **Eval-rubric versioning / rubric drift** — attribute a score shift to rubric vs model.
97. **Active-learning yield** — fraction of annotated traces that became useful eval cases.

## 30. User & lifecycle
98. **Concept drift in user intent over time** — new product questions, seasonality (vs #7).
99. **Cross-session user journey** — a customer across sessions/days (needs long-term memory, ADR 0007).
100. **Escalation-quality human feedback loop** — did the human agree the escalation was warranted (calibrates #56)?
101. **Tool least-privilege observability** — tools used vs granted per role/context → over-provisioned permissions (ADR 0009 RBAC).

## 31. System & reusable artifact
102. **Plugin SDK** — `ObservabilityBackend`/`Evaluator` via entry-points, mirroring the `MemoryBackend` Protocol (ADR 0007).
103. **Span contract tests** — golden-span schema verified in CI; spans treated as a public API.
104. **OTel GenAI conformance suite** — assert valid `gen_ai.*` against spec; conformance badge.
105. **Threat-model-driven obs (top-down)** — derive signals from `docs/threat-model.md`, not bottom-up accretion.
106. **Multi-cloud portability proof** — same backbone exporting to AWS (X-Ray/CloudWatch) + Azure Monitor.
107. **Extract `tessera-otel-genai` OSS lib** — instrumentation + redaction + semconv helpers as a pip-installable package.
108. **Upstream contribution** — PR to OpenInference/OpenLLMetry/OTel GenAI SIG. *(Timing gated on explicit go-ahead.)*
109. **Sovereignty proof** — egress monitor proving zero customer data leaves the box in `on_prem`.
110. **TCO / cost model doc** — total cost on-prem vs GCP, with numbers.
111. **Observability error budget** — document what we accept *not* to see (sampling, redaction).
112. **5-min scripted demo arc** — injection → guard deny → eval → replay → fix.
113. **Session theater UI as demo centerpiece** — #40 as the on-screen interview object.
114. **Reference written artifact** — blog / arXiv-style note / talk on the whole assembly.

## 32. Organisational
115. **AI-specific incident playbooks** — hallucination spike, jailbreak, PII leak, cost runaway.
116. **Runbook-as-code** — each alert links to a versioned, tested runbook.
117. **Error-budget policy + review cadence** — what happens when the budget burns (deploy freeze); monthly review.
118. **Blameless postmortems with trace attached** — template embeds the failing trace + replay (#1).
119. **Game days / chaos engineering for LLM** — inject poisoned doc / degraded model / aval latency; observe resilience.

## 33. Data (what you do with telemetry)
120. **Telemetry lakehouse** — traces/evals/feedback in a warehouse (BigQuery/Iceberg) as analytical substrate.
121. **ML on traces** — train a failure predictor: flag a turn likely to fail before the judge runs.
122. **Trace as training data** — curated good traces → SFT/preference data for the local model (improvement flywheel, vs eval flywheel).
123. **Embedding-based failure clustering** — auto-cluster failures into the top themes.
124. **Telemetry → product roadmap** — mine unmet needs / corpus gaps (#28) into the backlog.
125. **Causal inference on interventions** — did the prompt change *cause* the lift (vs #34's A/B mechanics)?

## 34. Developer experience
126. **Local-first obs stack in one command** — `make obs-up`: Phoenix + Collector + Grafana, seeded.
127. **Developer CLI over obs** — `tessera trace/replay/eval <id>`.
128. **PR-level obs diff** — CI comment: "this PR changed faithfulness by −2%" (extends #9).
129. **Time-travel debugging** — step a trace like a debugger with span breakpoints (#1/#113 interactive).
130. **Record/replay test fixtures (VCR-style)** — real traces as deterministic CI fixtures (ties #86/#103).

## 35. Human / end-user UX
131. **User-facing confidence indicator** — surface uncertainty (#12/#18): "not sure — escalate?".
132. **Clickable verifiable citations** — each claim links to its source regulation/doc.
133. **"Why this answer?"** — user-facing reasoning/sources from the provenance graph (#11).
134. **AI Act disclosure UX** — design and observe the "you're talking to AI" disclosure (#76).
135. **User-correctable memory** — see/correct what the agent remembers (GDPR access + rectification, ADR 0007).
136. **Escalation transparency** — when/why escalated to a human, with ETA.

## 36. Economic / product
137. **Customer-facing FinOps dashboard** — a deploying bank sees *their* cost/usage/quality.
138. **Quality SLA contractual** — an SLA backed by the SLOs (#15); obs proves compliance.
139. **ROI view for the buyer** — deflection rate, cost saved vs human agents, time-to-resolution (#67).
140. **Tiered obs offering** — basic (aggregate) vs premium (traces/replay), via RBAC (ADR 0009).
141. **Carbon report deliverable** — #25 packaged as an ESG/CSRD report.

## 37. Pure research (publishable)
142. **Harness as citable benchmark** — the 40 failures + multilingual banking eval, published.
143. **Empirical study: small local vs large cloud judge** — publish the calibration data (#2).
144. **Sovereign-eval methodology** — formalise on-prem eval with a local judge as a reproducible method.
145. **Cross-lingual consistency findings** — empirical FR/DE/EN divergence in a regulated domain (#70).
146. **Negative results published** — what didn't work and why (CLAUDE.md honesty ethos).
147. **One-command reproducible artifact** — Docker + seed + eval reproducing every claim (conference "artifact evaluation").

## 38. Temporal / evolutionary
148. **Trace schema migration / registry** — migrate historical traces as `gen_ai.*` evolves.
149. **Observability-debt tracking** — backlog of stale/missing/redundant instrumentation.
150. **Long-horizon trend analysis** — months-scale quality/cost; catch slow degradation.
151. **Model-generation migration playbook** — repeatable migration eval across base-model upgrades (ties #1/#61).
152. **Seasonal re-baselining** — recompute "normal" so drift detection (#98) doesn't false-alarm.

## 39. Comparative / competitive
153. **Honest differentiation matrix** — vs AEGIS/DFAH/AgentAssay/Promptfoo/STING, gaps included.
154. **Head-to-head eval** — same failure suite through Promptfoo and Tessera; compare coverage.
155. **"Reused vs invented" map** — visualise the assembly (guard/Phoenix/OTel) vs the thin original layer.
156. **Migration-cost / lock-in quantified** — cost to swap Phoenix→Langfuse, native→Mem0 (proves ADR 0007 reversibility).
157. **Living competitive radar** — track where competitors add features Tessera lacks.

## 40. Pedagogical
158. **Codebase as teaching artifact** — annotated "how to build production agent obs" walkthrough.
159. **Decision "why" journal** — every non-obvious obs choice + trade-off (from `insights_tessera.md`).
160. **Failure museum** — each of the 40 failures as a teaching case.
161. **Interactive trace tutorials** — learn OTel GenAI by replaying real annotated traces.
162. **"Build-your-own" companion repo** — rebuild the obs layer from scratch in steps.
163. **Spaced-repetition deck from insights** — flashcards from `insights_tessera.md` (learning mode + interview prep).
164. **Talk/workshop material** — a workshop on observability for compliance-grounded agents.

## 41. Resilience / degradation (the obs of the obs)
165. **Meta-observability** — monitor the Collector, exporters, judge availability.
166. **Obs never blocks prod** — backend down → buffer/degrade, never block the agent.
167. **Backpressure & spill-to-disk** — bounded queues, disk spill when the backend lags; observe drop rate.
168. **Fail-open vs fail-closed redaction policy** — if redaction (#3) fails, drop the span or pass unredacted? (banking → fail-closed, decided not subjected).
169. **Adaptive sampling under load** — shed volume under stress, keep 100% of errors (#32).
170. **Blast-radius isolation** — the obs sidecar crashing must not crash the agent.

## 42. Interoperability / ecosystem
171. **Native alert integrations** — PagerDuty/Opsgenie/Slack/Teams for AI-specific alerts (#115).
172. **SIEM integration** — security signals to Splunk/Sentinel/Chronicle for the bank's SOC.
173. **APM bridge** — OTLP to Datadog/New Relic/Dynatrace the bank already runs (proves the backbone).
174. **Standard export formats** — OTLP, OpenMetrics, OCSF/ECS for security.
175. **Auto-tickets from failure clusters** — Jira/ServiceNow from #123.
176. **Webhooks for the flywheel** — external eval/annotation tools subscribe to flagged traces (#6).

## 43. Obs-data governance (RBAC on telemetry itself)
177. **RBAC on traces** — who can view a trace with customer context (extends ADR 0009 to telemetry)?
178. **Dynamic redaction by viewer role** — auditor sees more than visitor; redaction is per-role.
179. **Trace-access audit** — observe who viewed which trace (audit the auditors).
180. **GDPR erasure across telemetry** — `DELETE /memory/{id}` also purges the customer's traces/evals (ADR 0007).
181. **Legal-hold on traces** — freeze specific traces from TTL deletion under investigation (explicit conflict with #180's TTL, arbitrated).

## 44. Edge / real-time
182. **Voice/audio agent observability** — ASR/TTS latency, WER, turn-taking/barge-in timing.
183. **Sub-second budget decomposition** — per-component latency at ms/frame granularity (#48 at real-time grain).
184. **Stream cancellation observability** — wasted tokens/cost when a user interrupts mid-stream.
185. **Edge deployment (store-and-forward)** — intermittent telemetry, reconcile on reconnect.
186. **Real-time guardrail latency** — guard within the streaming budget vs the real-time SLO (extends #90).
187. **Jitter, not just mean** — p99/p99.9 latency variance for real-time UX.

## 45. Multi-agent / swarm
188. **Inter-agent communication observability** — messages between agents/sub-agents.
189. **Handoff tracing** — router→worker→tool delegation traced causally; detect handoff failures.
190. **Per-agent cost/quality attribution** — which agent/node carried the cost/latency/error (#48 per-agent).
191. **Deadlock/livelock detection** — agents waiting on each other (#88 at multi-agent scale).
192. **Emergent-behaviour detection** — collective patterns no single agent shows.
193. **Responsibility/accountability trace** — who is accountable in a multi-agent decision (regulatory).

## 46. Formal / verification (provable properties on traces)
194. **Invariants on traces** — assert always-true properties ("`card_block` always emits a guard decision first"); runtime verification.
195. **Temporal-logic monitoring (LTL/MTL)** — "PII redaction precedes any external export" checked against the trace stream.
196. **Provable guard coverage (zero bypass)** — formally prove every tool-call path passes the guard (answers the known language-pinning bypass).
197. **Property-based testing of behaviour** — generate inputs, assert invariants hold across all (Hypothesis-style) over traces.
198. **Conformance to a behavioural spec** — a formal "must / must-never" spec verified against the trace stream.
199. **Differential verification across versions** — prove v2 preserves v1's safety properties (regression of *properties*, #15).
200. **Model checking of the agent graph** — explore reachable LangGraph states for safety violations offline.

## 47. Temporal control (cockpit time rail)
201. **Temporal lineage timeline** — a single dated event stream powering the cockpit's time rail: quality points (online-eval scores), judge-model changes, agent-model deploys and clustered guard denials, derived from the score buffer + tamper-evident audit log. The rail reads every view at an instant T against a baseline (*vue = Registre(état) × Backend(valeurs à T)*); this timeline is the scrubber's event source. Extends "what changed" (#17) and lineage/SBOM (#10) into a continuous temporal axis. Endpoint: `GET /observability/timeline?at=`. *Status: active. The value-at-T (`?at=`) query parameter now ships across the score-, bundle- and audit-backed observability endpoints (see #202).*
202. **As-of-T read layer (durable event stores)** — the backend that lets every cockpit block read "à T" honestly (ADR 0011). Two durable append-only stores next to the audit log — `scores.jsonl` (online-eval scores) and `bundles.jsonl` (captured turns) — plus the tamper-evident audit log, all filtered by a single robust timestamp comparison (`occurred_before`, parses `Z` and `+00:00`). `GET /observability/{scores,slo,trend,timeline,toxicity,pii-leak,anomalies,cost,what-changed,funnel,playbooks,roadmap,conformance,tool-validity,ai-act}?at=<ISO>` recompute over events ≤ T; the live bundle buffer warms from its store after a restart so history survives. **Honesty rule:** a signal answers "à T" only if its source is persisted/append-only; fixed-corpus probes (firewall-efficacy, refusal) and the structural audit-chain check stay live by nature, badged "live" in history mode. *Status: active.*
