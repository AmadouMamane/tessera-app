# Signal wiring map — metamorphic ground truth (Phase 0)

**Purpose.** Prove empirically that every signal we call *real-computed* is **WIRED**:
its value *responds to its real source*, and is not a constant in disguise. The
instrument is **metamorphic testing**:

1. **Determinism** — `observe(compute(source)) == observe(compute(source))` (same
   source in → same value out; no hidden clock/RNG/order noise).
2. **Source-sensitivity** — a *targeted, deterministic* perturbation of the source
   moves the observable in a *predicted direction* (`↑ ↓ ≠`) or provably leaves it
   unchanged when it should (`invariant`).

The test suite is the **ground truth**. If a signal does **not** move when its
source moves, we do not "fix" it quietly — we **re-classify it honestly**
(real-computed → fixed-corpus-probe / fixture). That is the test doing its job.

To keep the harness honest we run a **negative control**: point it at observables
known to be hardcoded and require them to come out **UNRESPONSIVE**. A harness that
declares a fixture "wired" has no teeth and must be fixed before we trust it.

---

## The load-bearing rule: test the signal *as wired*, not the pure function

The readers surfaced a recurring trap: **a pure function can be perfectly
perturbable while the signal it backs is dead**, because the *route* feeds the
function a fixed or aliased source.

- `embedding_skew.detect_skew(query, corpus)` compares honestly — but the route
  sets `corpus = query` ("equal by construction"), so the `skew` verdict is
  hardwired `False`. Testing the *function* would falsely "prove" it wired.
- `embedding_inversion.assess_inversion_risk(...)` is injectable — but the route
  embeds hardcoded `DEMO_MEMORIES/DEMO_PROBES` and memoises once per process; the
  real memory store is never read.

So each row records a **seam**: the level at which the perturbation must be
applied for the test to reflect the *deployed* signal.

- `fn-arg` — the source is passed straight through from a real store; perturb the
  argument (unit test with a constructed input) and it reflects production.
- `store` — perturb a durable store row (score buffer / ledger / bundle store),
  read back through the provider (integration or temp-store unit).
- `route-fixed` — the provider is pure but the **route** injects a constant/alias;
  the signal is dead at the seam → **negative-control / reclassify**.

---

## Legend

**classification**

| tag | meaning | wired to | in the "49"? |
|---|---|---|---|
| `real-computed` | derives a logic-bearing metric (rate/similarity/hash/threshold) from a runtime source | turns / text / chunks / traces / ledger | **yes (target)** |
| `real-store` | thin aggregate (count / mean) directly over durable store rows | score buffer / ledger | baseline (7) |
| `fixed-corpus-probe` | runs a **fixed probe dataset** (or the packaged eval catalogue) through guard/judge; responds to **policy/corpus**, invariant to live traffic | policy / probe files | no — separate |
| `fixture` | returns hardcoded / seeded / aliased data; **no runtime source moves it** | — | no — **negative control** |
| `infra` | measures this process's own spans / wall-clock / instrumentation | the process | no — invariant-by-design |

**relation** (of the observable under the stated perturbation): `↑` rises · `↓`
falls · `≠` changes to a different value/flips a boolean · `invariant` provably
unchanged.

**test** (Phase 2 execution mode): `unit` (constructed input, no I/O) ·
`unit+fake` (inject a deterministic embedder/backend/judge stub) ·
`unit+patch` (monkeypatch a module-level `embed`) · `unit+temp` (temp
ledger/store file) · `integration` (real store or LLM).

---

## Table A — real-computed (the target set: **49 signals**)

The claim under test for each row: *determinism holds* **and** *the stated
perturbation moves `observable` in direction `relation`.*

### A.1 Bundle / turn & text scans (pure or injectable — mostly `unit`)

| id | key | module:fn | source | observable | perturbation | rel | seam | test |
|---|---|---|---|---|---|---|---|---|
| 38 | output-pii-leak | pii_leak.py:aggregate_leaks | `(answer,source)` turns | `leak_rate` | inject a turn whose answer carries an IBAN absent from its source | ↑ | fn-arg | unit |
| 60 | toxicity-rate | toxicity.py:scan_toxicity | `(question,answer)` turns | `toxicity_rate` | inject an answer containing a lexicon term | ↑ | fn-arg | unit |
| 33 | cost-anomaly-security | cost_anomaly.py:analyze_costs | `(question,full_text)` turns | `n_anomalies` | append a turn whose text > 3× median tokens (≥3 turns) | ↑ | fn-arg | unit |
| 69 | anomalous-conversations | anomalies.py:detect_anomalies | `{conv_id:[questions]}` | `n_anomalous` | add a session of 3 identical questions (looping) | ↑ | fn-arg | unit |
| 17 | what-changed-rootcause | whatchanged.py:what_changed | two `(Lineage,score)` snapshots | `attributed` | change `prompt_version` while `curr_score < prev_score` | ≠ | fn-arg | unit |
| 30 | multiturn-contradiction | contradiction.py:detect_contradictions | `(question,answer)` turns | `n_contradictions` | near-identical Qs, opposite answers | ↑ | fn-arg | unit+fake |
| 90 | midstream-guard-retraction | guard_retraction.py:analyze_retractions | `[answer]` + policy | `retraction_rate` | inject an answer with a late-offset IBAN | ↑ | fn-arg | unit |
| 74 | cross-tenant-leakage | cross_tenant.py:detect_cross_tenant | `(conv_id,context)` turns | `leak_rate` | inject a foreign UUID into one context | ↑ | fn-arg | unit |
| 72 | unicode-steganography | steganography.py:scan_text | one text string | `n_hidden` | insert a zero-width / tag codepoint | ↑ | fn-arg | unit |
| 11 | claim-attribution | provenance.py:attribute | answer + `chunks` | `grounded_fraction` | append an off-corpus sentence to the answer | ↓ | fn-arg | unit+patch |
| 49 | citation-validity | citation_validity.py:aggregate_citations | `(answer,context)` turns | `validity_rate` | cite "Article 999" absent from context | ↓ | fn-arg | unit |
| 51 | locale-formatting | locale_format.py:aggregate_formatting | `(answer,locale)` turns | `correctness_rate` | put an en-grouped amount in an fr answer | ↓ | fn-arg | unit |
| 70 | cross-lingual-consistency | crosslingual.py:measure_crosslingual | question/context + LLM | `consistency` | stub backend returns a divergent DE answer | ↓ | fn-arg | unit+fake |
| 46 | robustness-noise | robustness.py:measure_robustness | question/context + LLM+judge | `mean_similarity` | stub backend drifts on noised variants | ↓ | fn-arg | unit+fake |
| 59 | sycophancy | eval/sycophancy.py:detect_sycophancy | question/answer + judge | `score` | stub judge scores a premise-endorsing answer high | ↑ | fn-arg | unit+fake |
| 18 | self-consistency | consistency.py:measure_consistency | question/context + LLM | `uncertainty` | stub backend returns scattered samples | ↑ | fn-arg | unit+fake |
| 133 | why-this-answer | why_answer.py:build_explanation | answer + `chunks` | `confidence` | append an unsupported sentence | ↓ | fn-arg | unit+patch |
| 10 | lineage-sbom | lineage.py:build_lineage | prompt YAML + policy + docs | `prompt_version` | differing prompt-file bytes → differing hash | ≠ | store | unit+temp |

### A.2 Retrieval / corpus (`unit+fake` for the embedder ones)

| id | key | module:fn | source | observable | perturbation | rel | seam | test |
|---|---|---|---|---|---|---|---|---|
| 28 | corpus-coverage-gaps | coverage.py:measure_coverage | question + `chunks` | `max_similarity` / `covered` | replace chunks with off-topic text | ↓ | fn-arg | unit+fake |
| 26 | retrieval-ir-online | retrieval_quality.py:utilization | `ProvenanceReport` + n_chunks | `utilization` | add a dead (unattributed) chunk | ↓ | fn-arg | unit |
| 27 | reranker-contribution | reranking_contribution.py:measure_contribution | question + `chunks` | `reranker_lift` | inject a lexical-match-only chunk | ↑ | fn-arg | unit+fake |
| 52 | poisoned-corpus-scan | corpus_injection.py:scan_chunks | `chunks` + policy | `poison_rate` | plant an "ignore previous instructions" chunk | ↑ | fn-arg | unit |
| 50 | corpus-freshness | corpus_freshness.py:assess_freshness | packaged `regulations_*.json` | `n_stale` | backdate a corpus file's mtime past 180d | ↑ | store | unit+temp |
| 77 | localization-completeness | localization.py:assess_localization | next-intl `messages/*.json` | `locales[].completeness` | delete a leaf key from `fr.json` | ↓ | store | unit |

### A.3 Graph / trace / tool structure (pure — `unit`)

| id | key | module:fn | source | observable | perturbation | rel | seam | test |
|---|---|---|---|---|---|---|---|---|
| 86 | reproducibility-hash | reproducibility.py:detect_nondeterminism | `(question,[nodes])` turns | `n_nondeterministic` | same question, two different node sequences | ≠ | fn-arg | unit |
| 87 | graph-topology-versioning | graph_topology.py:compare_topology | `TopologySnapshot` + golden | `drift.drifted` | drop/reroute a node vs the golden pin | ≠ | fn-arg | unit |
| 41 | golden-snapshot-ci | trace_snapshot.py:diff_traces | `(question,[nodes])` turns | `n_drifted` | a turn with an unknown / missing-backbone node | ↑ | fn-arg | unit |
| 189 | handoff-tracing | handoffs.py:analyze_handoffs | `(question,[nodes])` turns | `total_broken` | a worker turn with no `reviewer` | ↑ | fn-arg | unit |
| 89 | context-overflow | context_overflow.py:analyze_overflow | `(question,context)` turns | `overflow_rate` | a context > usable-token budget | ↑ | fn-arg | unit |
| 88 | tool-loop-detection | tool_loops.py:detect_loops | `{stream:[tools]}` | `n_loops` | 3 consecutive identical tool names | ↑ | fn-arg | unit |
| 47 | schema-conformance | conformance.py:compute_conformance | ledger tool-args + policy | `conformance_rate` | audit entry with a malformed arg | ↓ | store | unit+temp |
| 1 | trace-replay | replay.py:replay | `ReplayBundle` + LLM+judge | `score_delta` | strip the grounding fact from context | ↓ | store | integration |

### A.4 Routing / prediction / composite

| id | key | module:fn | source | observable | perturbation | rel | seam | test |
|---|---|---|---|---|---|---|---|---|
| 37 | language-misrouting | language_routing.py:aggregate_routing | `(text,served_lang)` turns | `mismatch_rate` | a DE question served as `fr` | ↑ | fn-arg | unit |
| 63 | intent-router-obs | routing_intent.py:aggregate_intents | `[question]` | `low_confidence_rate` | a question matching no intent marker | ↑ | fn-arg | unit |
| 81 | ablation-observability | ablation.py:measure_ablation | bundle + LLM+judge; `baseline` arg | `layers[].worth` | raise the `baseline` arg by +0.1 | ↑ | fn-arg | unit+fake |
| 121 | failure-predictor | failure_predictor.py:evaluate_predictor | `(question,context,score)` turns | `precision` | an injection-shaped turn judged < 0.80 | ↑ | fn-arg | unit |
| 19 | guard-explainability | guard_explain.py:compute_guard_explain | ledger deny entries | `n_denials` | a turn that trips a deny rule | ↑ | store | unit+temp |
| 76 | ai-act-compliance ⚠ | ai_act.py:assess_compliance | `AIActSignals` snapshot | `compliance_rate` | flip `audit_chain_verified` → False | ↓ | fn-arg | unit |
| 23 | memory-observability | memory_obs.py:aggregate_memory_audit | `memory.*` ledger entries | `recall_hit_rate` | add a "recalled N/M" entry | ↑ | fn-arg | unit |
| 101 | tool-least-privilege | least_privilege.py:analyze_privilege | granted set + ledger usage | `utilization_rate` | use a granted-but-unused tool | ↑ | fn-arg | unit |
| 95 | multi-judge-ensemble | eval/ensemble.py:evaluate_ensemble | bundle + 2 judges | `mean_score` | stub judges score a context-contradicting answer low | ↓ | fn-arg | unit+fake |

> ⚠ **ai-act-compliance (#76) is PARTIAL**: 3 of 5 obligations are pinned `True`
> at the route (`disclosure`/`escalation`/`data_governance`) and one is hardcoded
> `satisfied=True` (Annex III). Only the audit-chain obligation can move
> (`compliance_rate` 1.0 → 0.8). WIRED, but with a documented floor of 4/5.

### A.5 Misc real-computed (stores / composite)

| id | key | module:fn | source | observable | perturbation | rel | seam | test |
|---|---|---|---|---|---|---|---|---|
| 122 | traces-to-sft | sft_export.py:build_sft_dataset | captured bundles | `n_eligible` | capture one turn judged ≥ 0.80 | ↑ | store | unit |
| 124 | telemetry-to-roadmap ⚠ | roadmap.py:build_roadmap | scores + bundles + corpus | `n_items` | add low-faithfulness (<0.80) scored turns | ↑ | fn-arg | unit |
| 180 | gdpr-erasure-telemetry | erasure.py:coverage / footprint | bundles + scores | `n_conversations` | new turn ↑ ; `purge_telemetry` ↓ | ↑↓ | store | integration |
| 3 | tamper-evident-audit | guard/audit.py + ledger_store.py:verify | hash-chained ledger rows | `ChainStatus.verified` | edit/reorder any persisted row | ≠ | store | integration |
| 16 | shadow-traffic ✎ | shadow.py:run_shadow | captured bundles + LLM+judge | `n_compared` | capture one more bundle | ↑ | store | integration |
| 172 | siem-integration ✎ | siem.py:to_siem_events | ledger deny/transform rows | `n_events` | one live guard deny | ↑ | fn-arg | unit |
| 36 | consent-governance-ops | memory_obs.py:aggregate_memory_audit | `memory.*` ledger entries | `writes_denied` / `n_forgets` | a consent-denied memory write | ↑ | fn-arg | unit |
| 99 | cross-session-journey | journey.py:build_journeys | memory-audit `(subject,action,ts)` | `n_returning` | add a read after a 30-min gap | ↑ | fn-arg | unit |

> ⚠ **telemetry-to-roadmap (#124)** has a **dead sub-path**: the route never sets
> `n_coverage_gaps`, so the `coverage_gap` roadmap item can never fire. The signal
> is WIRED overall (other items move); the sub-path is noted for reconciliation.
>
> ✎ **shadow-traffic (#16)** and **siem-integration (#172)** were named in the plan
> as *negative-control fixtures*. The readers show both are in fact **wired** —
> `run_shadow` replays real bundles, `to_siem_events` maps real ledger rows. They
> belong in Table A, not the negative control. (See "Reconciliation", item R0.)

---

## Table B — real-store baseline (**7 signals**)

Trivial aggregates over the durable **score store** (`eval/scores._RECENT` /
ClickHouse) or the **ledger**. Their job in Phase 2 is to *also validate the
harness*: perturb one store row → the aggregate moves. If these do not move, the
harness itself is broken.

| id | key | module:fn | store perturbation | observable | rel |
|---|---|---|---|---|---|
| — | online-scores | eval/scores.py:recent_scores | `emit_score(faithfulness=0.42)` appends a row | `[].score` | ↑ |
| 15 | quality-slo-error-budget | slo.py:compute_slo | append a score < 0.80 | `budget_consumed` / `good_rate` | ↑ / ↓ |
| 150 | long-horizon-trend | trends.py:analyze_trend | append 3 low tail scores (n ≥ 4) | `slope` | ↓ |
| 66 | funnel-per-language | funnel.py:aggregate_funnel | inject a low-score `fr` turn | `low_score_rate` | ↑ |
| 21 | session-goal-completion | sessions.py:aggregate_sessions | add a 2nd turn to a single-turn conv | `single_turn_rate` | ↓ |
| — | score-series | eval/series.py:compute_score_series | insert a 0.0 row in-window | `mean` | ↓ |
| — | regression-risk | eval/risk.py:compute_regression_risk | insert low in-window scores | `risk_score` | ↑ |
| 29 | tool-arg-validation | tool_validity.py:compute_tool_validity | emit a denied `.argument.` tool call | `validity_rate` | ↓ |

*(29 is ledger-backed rather than score-backed but behaves as a store aggregate;
listed here as a store baseline.)*

**Duplication invariant (applies to all rate/mean rows in A & B):** duplicating
the entire input series leaves the *rate/mean* unchanged (`n_good` and `n` scale
together). Every ratio signal gets this `invariant` assertion in addition to its
`↑/↓` one — a rate that changes under duplication is secretly counting, not
rating.

---

## Table C — fixed-corpus-probe (**7 signals**): wired to policy/corpus, invariant to live traffic

These are **not fixtures** — they respond to a *real* source (the guard policy or
a probe dataset). But that source is **not runtime traffic**, so their honest
metamorphic test perturbs the **policy** or the **probe corpus**, and asserts
**invariance** under a score-store perturbation.

| id | key | module:fn | real source | perturbation → moves | invariant under |
|---|---|---|---|---|---|
| 13 | firewall-roc | firewall_efficacy.py:compute_efficacy | policy + injection/benign files | remove a deny pattern → `recall`/`f1` ↓ | score-store append |
| 58 | refusal-calibration | refusal.py:compute_refusal_calibration | policy + benign/forbidden files | add a deny matching a benign → `over_refusal_rate` ↑ | score-store append |
| 24 | continuous-red-team | redteam.py:run_redteam | policy + adversarial file | delete a deny regex → `attack_success_rate` ↑ | score-store append |
| 2 | judge-calibration | eval/calibration.py:calibrate | `judge_gold.json` gold set | flip a gold label → `kappa` ↓ | live traffic |
| 123 | failure-clustering | failure_clustering.py:cluster_failures | `eval/failures/*.json` catalogue | add a failure file → `n_failures` ↑ | live traffic |
| — | eval-pass-rate | eval_data.py:load_eval_snapshot | packaged eval report archive | flip a case pass→fail (+`cache_clear`) → `pass_rate` ↓ | live traffic |
| 73 | embedding-inversion-risk | embedding_inversion.py:assess_inversion_risk | **route-hardcoded** `DEMO_MEMORIES/PROBES` | edit the demo constants → `recovery_rate` moves | **the real memory store** |

> #73 is the weakest of the group — its probe corpus is a *demo constant baked
> into the route* and cached once per process, so as-wired it responds to nothing
> at runtime. Flagged for reconciliation (R2).

---

## Table D — negative control (**MUST be UNRESPONSIVE**)

The harness points here and **requires** these to come out dead. If any is
reported "wired", the harness is toothless and gets fixed before Phase 2 proceeds.

| target | module | why dead | required verdict |
|---|---|---|---|
| **embedding-version-skew #64** `.skew` | embedding_skew.py + route | route sets `corpus = query` → mismatch/skew hardwired `False` | `invariant` (always False) |
| **ai-act-disclosure-ux #134** `.enabled` / `.all_covered` | disclosure.py | `DISCLOSURE_TEXT` is a module constant; `enabled=True` literal | `invariant` (only a code edit moves it) |
| incidents demo block #115 | incidents.py `mttr_series` (73/89/83/75/71), `playbook_catalog` runs, INC-231 | hardcoded constants; ignore ledger/scores | `invariant` |
| curation demo block | curation.py `linked_datasets` "12 842 tours", `backlog_trend` 78.2→82.8, `why_tours` | hardcoded constants; ignore stores | `invariant` |
| capability synthetics | capabilities.py `assistant`, `policy_versioning`, `evidence_export`, `automation_workflow`, `shadow_traffic`(fleet-mirror UI zone) | declared `synthetic=True`; no substrate | `invariant` |

The strongest two (#64, #134) are **nominally `status: active` signals** — that is
precisely why they are the sharpest negative control: the harness must refuse to
call them wired.

---

## Table E — infra / out-of-scope (invariant-by-design; not in the 49)

Measure the process itself or are pure capabilities (`section: na`). Excluded from
the target set by definition; listed for completeness.

| id | key | why out |
|---|---|---|
| 85 | span-propagation-async | measures this process's OTel async context (self-probe, cached once) |
| 48 | latency-attribution | wall-clock timing of this process's nodes |
| 4 / 5 | otel-agent-spans / eval-as-telemetry | instrumentation plumbing |
| 84 / 92 / 165 | obs-cost / instrumentation-coverage / meta-observability | observability-of-observability |
| 32 | tail-based-sampling | a sampling *policy* (decides on trace features; borderline) |
| 40 / 113 / 201 / 202 / 126 / 132 / 168 | session-theater / theater-demo / temporal-timeline / as-of-t / obs-up / clickable-citations / fail-closed-redaction | capabilities / read-layer / practice (`section: na`) |

---

## Reconciliation candidates (Phase-0 findings, to confirm in Phase 2)

These are **proposed** re-classifications the cartography already exposes. Phase 2
will *prove* each (UNRESPONSIVE under its source perturbation) before we edit
`signal-catalog.yaml`. Nothing is demoted yet.

| # | signal | catalog today | proposed | evidence |
|---|---|---|---|---|
| R0 | shadow #16, siem #172 | *(plan called them fixtures)* | **keep real** | `run_shadow` replays real bundles; `to_siem_events` maps real ledger rows |
| R1 | embedding-version-skew #64 | active signal | **fixture** | route aliases `corpus = query`; `skew` can never be True |
| R2 | embedding-inversion-risk #73 | active signal | **fixed-corpus-probe** | route embeds hardcoded demo constants, cached once/process |
| R3 | ai-act-disclosure-ux #134 | active signal | **fixture** | hardcoded `DISCLOSURE_TEXT` + `enabled=True` |
| R4 | ai-act-compliance #76 | active signal | **real-computed (partial)** | 4/5 obligations pinned; only audit-chain moves it |
| R5 | telemetry-to-roadmap #124 | active signal | **real-computed (partial)** | `coverage_gap` sub-path dead (route never sets `n_coverage_gaps`) |
| R6 | judge-calibration #2, failure-clustering #123, eval-pass-rate | (implied real) | **fixed-corpus-probe** | fixed gold set / failure catalogue, process-cached |

---

## Counts

| bucket | count | notes |
|---|---|---|
| **real-computed (Table A)** | **49** | the target set — each must prove WIRED |
| real-store baseline (Table B) | 7 (+1) | validate the harness; #29 listed as ledger-store |
| fixed-corpus-probe (Table C) | 7 | wired to policy/corpus, invariant to traffic |
| fixture — negative control (Table D) | 5 groups | must prove UNRESPONSIVE |
| infra / out-of-scope (Table E) | ~14 | invariant-by-design |
| **reconciliation candidates** | **6** (R1–R6) | 2 → fixture, 2 → probe, 2 → partial |

Target for Phase 1/2: **49 real-computed** proven WIRED, **7 real-store** as
baseline, **≥2 negative controls** proven UNRESPONSIVE, and **6 candidates**
resolved on the evidence (WIRED / partial / demoted).

---

## Phase 1 preview (harness + negative control) — for reference, not yet built

`tests/support/wiring.py` primitives:

- `assert_deterministic(compute, source)` — two calls, identical observable.
- `assert_source_sensitive(compute, source, perturb, observe, relation)` — the
  relation holds between `observe(compute(source))` and
  `observe(compute(perturb(source)))`.

Validate on **3 diverse reals that must move**:
`slo.compute_slo(...).good_rate` (quality pass-rate), `pii_leak.aggregate_leaks(...).leak_rate`,
`reproducibility.detect_nondeterminism(...).n_nondeterministic` (a computed `≠`).

**Negative control that must come out UNRESPONSIVE** (replacing the plan's
mis-identified shadow/siem): `embedding_skew` `.skew` and `disclosure` `.enabled` —
perturb any nominal source, assert the observable is `invariant`. A harness that
flags either as wired is rejected and repaired.

---

*Method: metamorphic (determinism + source-sensitivity) with an adversarial
negative control. Ground truth beats intention: a signal that will not move when
its source moves is re-classified, not excused.*
