# 0017 — Agent observability contract, AgentSpec manifest & the L0–L3 conformance ladder

- Status: **accepted — implementation complete** (decision 2026-07-06; Phases A–F landed 2026-07-08). **TTO measured: L1 in 20m18s** (target ≤ ½ day) — see §Migration plan Phase F + its precision.
  **Amended 2026-07-06 (§Amendment 1: business capability model, per-capability Métier view,
  external-effect invariant, `product_surface` non-exposure rule). Amended 2026-07-06
  (§Amendment 2: typed envelope actor, the 3-level business-metric ladder, declared policy
  metadata, observability level gates release). Amended 2026-08-06 (§Amendment 3: L1 evidence
  is any recorded emission — the business-event ledger joins the Prometheus counter — bounded
  by a 30-day recency window; a store's blindness now reaches the L0→L1 decision). Amended
  2026-08-21 (§Amendment 4: the declared quality regime — every agent names the ruler that
  judges its production answers; `unscored` is a declaration carrying its reason, never an
  absence). Amended 2026-08-23 (§Amendment 5: the declared understanding layer — an agent
  that splits understanding from answering names how the understanding plane is ruled and
  the labeled referent that measures it; ADR 0053). Amended 2026-08-26 (§Amendment 6: the
  declared reformulation layer — an agent that lets a model rewrite the tone of its
  regulated letters declares the plane, its template-referent ruler and its labeled
  referent; ADR 0054).**
- Date: 2026-07-06
- Deciders: Tessera maintainers
- Related: 0008 (agent audience and surface), 0010 (Recouvrement internal operator agent),
  0010 (frontier observability), 0012 (agent registry and seed), 0015 (runtime telemetry
  spine & Scope — incl. Amendments 1–3), 0016 (business events fan-out contract),
  `docs/signal-catalog.yaml` (ids 41, 65, 76, 92, 94, 102, 103, 104, 107, 139, 190),
  `src/tessera/observability/business_events.py`, `src/tessera/observability/business_scoring.py`,
  `src/tessera/recouvrement/scoring.py`, `src/tessera/agent/agents.yaml`,
  the "ADR-001" vision draft (2026-07-06, chat-authored, outside the numbered corpus —
  harvested by §Amendment 1).

## Amendment 6 (2026-08-26) — the declared reformulation layer: the third ruler names itself

**ADR 0054 opens recouvrement's layer 3 — an LLM may rewrite the TONE of an approved letter,
with the template as REFERENT — which creates a third measured plane neither §A4's regimes nor
§A5's understanding block covers.** Its ruler is template-fidelity: a deterministic
must-survive checker (facts, amounts, dates, legal clauses, signature — verbatim or the exact
template ships instead) plus a fidelity judge calibrated against a human-labeled referent
before any threshold governs. Leaving that plane undeclared would recreate the defect A4 and
A5 each closed — a measured plane whose ruler no declaration names.

### A6.1 — Decision: an optional block, never a defaulted one

`AgentObservabilitySpec` gains `reformulation: {mode, bench_set}` —
`mode ∈ {template_referent}`. Optional because most agents have no reformulation plane (their
outbound wording is either template-assembled with no model near it, or model-native and
already ruled by §A4); an agent that opens layer 3 declares it, with no default. The
declaration says the plane EXISTS and names its referent; the runtime state (off / shadow /
active) is a GOVERNED KNOB (`recouvrement.reformulation.*`, ADR 0054 §5), never the manifest —
a deploy artifact must not flip a compliance-gated layer.

### A6.2 — Integrity

- `template_referent` ⇒ `bench_set` REQUIRED, refused at load: a reformulation layer without
  a labeled referent is unverifiable (ADR 0054 §4);
- the declared `bench_set` (`eval/reformulation/<set>.json`) must exist on disk and name the
  declaring agent — checked by the conformance suite
  (`tests/unit/test_recouvrement_shadow_reformulation.py`), since a spec validator must not
  touch the filesystem;
- the declaration and the wiring are held together by witnesses on the thing (ADR 0026): the
  conformance suite asserts the declaring agent's turn route spawns the layer-3 shadow seam,
  that OFF spends nothing, that only an approved-template, policy-unblocked draft is
  shadowed, and that the recorded row carries measurements and NEVER the candidate letter
  (an unapproved regulated text must not enter the ledger).

### A6.3 — Three rulers stay three

Reformulation telemetry rides the ledger as `message.generated` rows under
`message_kind: shadow_reformulation`, node `shadow_reformulation` — excluded from every
client-message consumer by the kind itself, presence-checked by no business signal, counted
by no business score. The reformulation ruler's numbers (checker pass rate, judge fidelity),
the understanding ruler's and the business ruler's never share a denominator (A4.3, A5.3,
insights 361–363).

## Amendment 5 (2026-08-23) — the declared understanding layer: a split plane names its own ruler

**ADR 0053 splits recouvrement into three layers — an LLM understands, code decides, templates
speak — which creates a plane §Amendment 4's regimes do not cover.** `quality_regime:
business_scored` rules the SPOKEN plane (money and acts, ten deterministic signals). The new
understanding layer is judged by a different ruler entirely: intent accuracy against a labeled
set (`eval/intents/<set>.json`, ratcheted at n≥8 per language/intent cell) plus the shadow
agreement telemetry in the business-event ledger (node `shadow_understanding`). Leaving that
plane undeclared would recreate the exact defect A4 closed — a measured plane whose ruler no
declaration names.

### A5.1 — Decision: an optional block, but never a defaulted one

`AgentObservabilitySpec` gains `understanding: {mode, bench_set}` —
`mode ∈ {deterministic, llm_structured}`. Optional because most agents have no understanding
layer distinct from their answering plane (the three chat-native agents ARE one LLM plane
end-to-end); an agent that does split the planes declares how the understanding one is ruled,
with no default (the ADR 0024 rule again: no ruler nobody chose).

### A5.2 — Integrity

- `llm_structured` ⇒ `bench_set` REQUIRED, refused at load: an LLM understanding without a
  labeled referent is unverifiable (ADR 0053 §7), and an unverifiable plane may not declare
  itself measured;
- the declared `bench_set` must exist on disk and name the declaring agent — checked by the
  conformance suite, since a spec validator must not touch the filesystem;
- the declaration and the wiring are held together by witnesses on the thing (ADR 0026): the
  conformance suite asserts the declaring agent's turn route actually spawns the shadow seam,
  and the shadow tests assert the classifier's closed vocabulary IS the manifest's capability
  ids, read from the registry at call time — a manifest change reaches the classifier's schema
  with no human in the loop.

### A5.3 — The two rulers stay two

Understanding telemetry rides the ledger as `intent.routed` rows under node
`shadow_understanding` — presence-checked by no business signal, counted by no business
score. The understanding ruler's numbers (bench accuracy, shadow agreement) and the business
ruler's numbers (the ten signals) never share a denominator, per A4.3 and insights 361–363.

## Amendment 4 (2026-08-21) — the declared quality regime: every agent names the ruler that judges it

**The cockpit runs two disjoint quality rulers, and no declaration said which agent answers to
which.** The online LLM judge (`faithfulness` / `grounding` / `hallucination`, wired on the
in-process `/chat` seam, writing `tessera.eval_online_scores`) covers `support-client` and
`onboarding`. The deterministic business scorers (per-signal `scored` / `unknown` /
`not_applicable`, ADR 0017 §A2.2) cover `recouvrement`. The three demo agents are covered by
neither. Measured consequence on the served stack (2026-08-21): the quality page's "0 of N judged
responses" read as *nothing else is measured*, while a second plane was measured by a stricter
ruler two clicks away — 20 business runs, ten deterministic scores each, already rendered on the
Métier view.

### A4.1 — Decision: declared, never inferred

`AgentObservabilitySpec` gains a **required** `quality_regime` field —
`llm_judged` · `business_scored` · `unscored` — plus `quality_regime_reason_key`. No default, on
purpose: a default would put a ruler nobody chose behind an agent's quality figures (the ADR 0024
rule, applied to judgment instead of authorship). An inference (`has eval_set?` `has signals?`)
was rejected because it can drift silently when the schema evolves; a declaration is refused at
load when it contradicts the rest of the manifest.

### A4.2 — Integrity: the illegal states are unrepresentable

- declared `business_signals` **or** a scorer-bound workflow ⇒ the regime MUST be
  `business_scored` — a scored plane may not hide its ruler (the two-rulers defect already paid
  for on the certifying matrix);
- `business_scored` ⇒ non-empty `business_signals` AND a scorer-bound workflow — a ruler with no
  producer scores nothing;
- `unscored` ⇒ a `quality_regime.`-namespaced reason key, resolved in **every** locale catalogue
  (same three-catalogue gate as capability/policy labels) — a blind spot is declared with its
  reason in the reader's language, never silently (ADR 0026);
- `llm_judged` ⇒ `invocation.binding: in_process_chat` (cross-block, checked at registry load:
  the judge is wired on one seam; a declared judge the declared transport cannot carry is a
  promise no line of code keeps).

### A4.3 — One projector, every surface

`quality_regime_descriptor()` (agentspec_projection) is the single read path. Quality surfaces
render populations **grouped by regime and never sharing a denominator**: a rate that absorbed
`amount_consistency` into `faithfulness` would be a number nobody can interpret, looking more
complete than either truth. The conformance ratchet refuses any registry agent without an
`observability` block — an agent arriving without a declared ruler is a red gate, never an
invisible row on a quality page.

## Amendment 3 (2026-08-06) — L1 evidence is *any* recorded emission, bounded by a recency window; the store's blindness reaches L0→L1 too

**§4 defines L1 as "the cockpit observes the agent emitting turns". It never defined what
looking means, and the implementation answered with one route's counter.**

### A3.1 — The defect, measured

`tessera_agent_turns_total` is incremented in `src/tessera/api/routes/chat.py` and nowhere else.
`recouvrement` serves its turns over `/recouvrement-assistant/message`, so the counter never
named it. `observability_level()` returns `L0` *before* it reads business events, so its **1281
timestamped business events** — the only real business evidence in the system, spanning
2026-07-06 to 2026-08-05, capability-stamped, all under `recouvrement_collections_v1` — were
never consulted. The agent required L3, declared L3, computed L0, and was blocked.

**The one agent in the fleet producing evidence was the one the door refused for want of
evidence.** This is ADR 0026's shape precisely: the witness interrogated the *neighbourhood*
(`/chat`, the neighbour of the route actually serving the turn) rather than the thing (the agent).

### A3.2 — Decision: two sources, one meaning

A turn is proven by **either** the Prometheus turn counter **or** a distinct `turn_id` carrying a
timestamped event in the business-event ledger.

The §4 rule *"computed from passing gates, never asserted"* is untouched, and the argument must
be stated because widening evidence is exactly where over-claim enters: **both are emissions the
agent makes and a store records.** Neither is a declaration. What widens is what counts as
looking, not what counts as proof. The ledger read inherits the ADR 0019 §4 synthetic exclusion
from the read seam, so a canary turn can never manufacture the evidence that unlocks a rung.

### A3.3 — The window is not optional

Business events live six months. Read unbounded, the ledger would answer *"has this agent ever
emitted?"* and an agent dead since July would read as observed until January — trading a false
negative for a false positive. The ledger read is therefore bounded by a **30-day recency
window** (`turn_evidence.RECENCY_WINDOW`), chosen against its neighbour rather than picked: it is
the usual Prometheus retention, so the two sources answer over comparable horizons.

Consequence, stated rather than discovered: **an agent that stops emitting falls back to L0 once
the window passes it.** Evidence expires. Surfaces must word this as *observed recently*.

### A3.4 — One source's silence no longer proves absence

Before this amendment the counter's silence *was* the answer. With a second source able to
contradict it, an agent is `dormant` only when **both** stores answered and neither holds a turn;
if either is blind the verdict is `unverifiable`. Otherwise a ClickHouse outage would quietly
demote an agent that is emitting fine.

This extends `facts_readable` from the L2→L3 decision to **L0→L1**: the business-event store now
carries turn evidence, so its outage must reach every rung it feeds. A blind spot that demotes
only some decisions is the same over-claim wearing a smaller hat.

### A3.5 — The route counts its own turn, and a ratchet keeps it that way

`/recouvrement-assistant/message` now increments the counter (successes *and* failures, as
`/chat` does). Deriving evidence from the ledger fixes this case; it does not close the class —
the next agent served outside `/chat` and emitting no business events would hit the same wall in
silence. `tests/unit/test_a_route_that_serves_a_turn_counts_it.py` refuses any route module that
invokes an agent turn without reaching the counter, with a frozen exemption set for routes whose
turns are counted elsewhere (`/agents/{id}/invoke`, which drives a real HTTP turn to the agent's
own route). `recouvrement_assistant.py` has now been found outside a `/chat` seam three times —
input guard (2026-07-21), durable transcript (ADR 0040), this counter — and three instances of
one class is not three bugs.

### A3.6 — This amendment FREES an agent

`recouvrement` moves L0 → L3 and satisfies its required L3. **A change that unblocks must be read
harder than one that blocks**, because nothing downstream complains when it is wrong — the same
caution owed to the two grader widenings of 2026-08-04/05. What was verified: the rows must carry
a real `capability_id` (L3's own evidence) *and* a `turn_id` inside the window (L1's); the counter
is explicitly silent in the test that proves it; stale events alone leave the agent at L0; a blind
store yields no rung at all.

### A3.7 — What freeing an agent revealed downstream

The caution in §A3.6 earned its keep within the hour. With `recouvrement` at L3, the **fleet
card** said L2 while `resolve_level_state` said L3 — two surfaces, one question, two answers.

`fleet.py` had never passed `business_events=` to `observability_level`, so its computed rung was
**capped at L2 by construction**: it could not express L3 whatever an agent emitted. That cap was
unfalsifiable for as long as every agent short-circuited to L0 for want of turn evidence, which
is exactly the property that made it survive. Found on the live stack by asking the HTTP surface,
not by a test.

Both facts now come from **one** ledger read (`business_capabilities.fleet_ledger_facts`) rather
than two: the fleet needs the capability stamps and the turn evidence together, and two
whole-ledger reads that can disagree with each other is the shape this codebase keeps paying for.
The rule this instance confirms: **a correction that unblocks obliges a re-check of every surface
downstream of it**, because the surfaces that were agreeing on a floor stop agreeing the moment
the floor lifts.

### Migration impact

- Frozen tests asserting `recouvrement = L0` go red and are updated with the argument written at
  the place of the number. `tests/unit/test_level_resolution.py` stubs the evidence verdict whole
  and so is unaffected in meaning; its stubs now take `**_k` so a future source cannot silently
  turn them into a different test.
- The `L3 déclaré · L0 prouvé` legend stops diverging **for `recouvrement`**. It keeps its
  examples — `onboarding` and `support-client` remain L2 declared / L0 computed — so the legend is
  not broken, only less populated.
- **Nothing is visible without a rebuild** (ADR 0051): the level is computed inside the agent
  image.

## Amendment 1 (2026-07-06) — Capability becomes a first-class contract object; the per-capability Métier view; the external-effect invariant; the `product_surface` non-exposure rule

**Status: accepted.** Source: the "ADR-001" vision draft independently re-derived most of
0016/0017 (Agent Blueprint ≈ AgentSpec, Event Spine ≈ the 0016 fan-out, Metric Registry ≈
`business_signals`, Product/Control plane ≈ 0008/0010 audience-surface-auth) — convergent
validation. This amendment harvests its four genuine contributions; its three regressions
against settled decisions are recorded in §Alternatives considered (appended there).

### A1.1 — The business capability model (AgentSpec)

The unit of business function is the **capability** — the formalisation of the existing
`active_task` concept (`summary`, `draft_reminder`, `propose_schedule`, `check_contact_rule`,
`explain_priority`, …). The AgentSpec gains a typed `capabilities` block; the §3 key
`capabilities` (telemetry panels) is **renamed `telemetry_capabilities`** to free the name.

```yaml
capabilities:
  - id: propose_schedule
    label_key: capability.propose_schedule       # i18n key — sweep-gated like all labels
    input_schema: schemas/propose_schedule.json
    output_artifacts: [schedule_proposal]
    policies: [schedule_requires_validation]     # ids + reason codes ONLY — implementations
                                                 # stay in the domain package (0016 rule)
    eval_packs: [schedule_validation]
    external_effect_level: requires_validation   # none | draft | requires_validation | external_action
```

`external_effect_level` is the load-bearing field: a **static declaration** of how far a
capability may reach outside the system, verified at runtime by §A1.3. A generic YAML policy
*engine* is explicitly not adopted (see appended alternatives): policies remain deterministic
code in domain packages; the manifest declares their **ids and reason codes** so the cockpit
can render them without knowing the domain.

### A1.2 — `capability_id` joins the envelope and the read model

`BusinessEvent` gains an **optional `capability_id`** field. Additive and optional → the
envelope stays `business_event.v1` (no version bump); events emitted before the field read
honestly as `capability_id IS NULL`. The ClickHouse table (§5) gains the column (inline ⚠
marker there), and `capability_id` joins the declared cockpit filter dimensions (extending the
0016 §Consequences dimension list). This single field is what makes the per-capability view
(§A1.4) an aggregation, not a new pipeline.

### A1.3 — The external-effect invariant (signal 194's first real case)

Binding rule: **an artifact or action whose capability declares `external_effect_level ∈
{requires_validation, external_action}` must be preceded, within the same case/turn chain, by
`validation.requested` and a validating decision — or terminate as `action.blocked`.** The
invariant is *declared* by the manifest and *verified* over the event/ledger chain (the chain's
total order is the proof medium — 0015 §Corr.3b). It surfaces in **Prouver** as "effets
externes : prouvés validés / empêchés"; a violation is an incident-grade signal, never a
silently rendered row. This is the first concrete instance of signal 194 (`trace-invariants`),
and it is what "prove the non-action" means for a regulated agent.

### A1.4 — The Métier tab's primary view is the per-capability table

Columns: volume, conformity %, validation-required %, blocked %, external effects prevented,
trend — aggregated from grammar events + business scores, **per declared capability**. The runs
table (§6.2) becomes the **drill-down** beneath it. AT-01 boundary restated: this table renders
in the **Métier tab only** — never in Synthèse (operational ≠ métier), never merged into
Évaluations (judged ≠ deterministic).

### A1.5 — `product_surface` and the non-exposure rule, generalised

The AgentSpec gains `product_surface: {route, shell}`. Binding rule, generalising 0010 Phase C
from recouvrement to every agent: **a product surface never exposes Tessera, the cockpit,
traces, prompts, models, scores, evals or guard internals.** The product plane executes the
métier; the cockpit governs the behaviour; the AgentSpec is where that boundary is *declared*
per agent — and the split never turns the cockpit into the collaborator's daily tool.

### A1.6 — Outcome & attribution metrics: named as the v1.1 target, not implemented

The draft's `business.action.sent` / `business.outcome.received` events and its attribution
metric schema (numerator / denominator / join on `artifact_id`, fallback `case_id`, attribution
window) are the right *target* — and exactly the grammar-v1.1 extension §2 already gates. They
require a real send channel and a real outcome feed, neither of which exists (0010: *"Tessera
has no collections-case backend, and a demo must not invent one"*). When a real feed lands,
v1.1 adds `action.executed|failed` and `outcome.received`, and `business_signals` gains a
`source: event_ratio` declaration (numerator / denominator / join_key / window). Implementing
them today would be fabricated data — rejected on the honesty rule, kept as the named target.

### Migration impact

Phase B ships the capability model + the `telemetry_capabilities` rename + the envelope field;
Phase C ships the per-capability table (primary view) + runs drill-down + the Prouver invariant
surface; the invariant *checker* is a Phase E conformance test (a property over emitted
chains). Phase F's acceptance is unchanged.

## Amendment 2 (2026-07-06) — typed envelope actor; the 3-level business-metric ladder; declared policy metadata; the observability level gates release

**Status: accepted.** Source: the "ADR-003" and "ADR-005" vision drafts (2026-07-06,
chat-authored, outside the numbered corpus). Their remaining regressions — the staged
PG→Kafka→BigQuery event pipeline and the YAML policy engine — stay rejected (§Alternatives,
one line appended). Their runtime-contract material is harvested by **ADR 0018**.

### A2.1 — The envelope `actor` gets a closed vocabulary

`BusinessEvent.actor` is today a free string defaulting to `"system"`. It becomes a closed
vocabulary: `system | external_customer | internal_collaborator | operator`. Additive
narrowing — existing rows are all `system`, so the envelope stays `business_event.v1`. The
distinction is load-bearing for the ladder below: a `human_action`-level fact is exactly an
event whose actor is human.

### A2.2 — Every business signal declares its level (the 3-level ladder)

`business_signals` entries gain `level: runtime | human_action | outcome`:

| Level | Measures | Example (recouvrement) | Exists today? |
|---|---|---|---|
| `runtime` | the agent did its job correctly | relance générée conforme, règle vérifiée, blocage hors plage | yes — grammar events + scores |
| `human_action` | a human used the artifact | brouillon inséré, soumis à validation, validé | partially — `artifact.status_changed` + A2.1 actor |
| `outcome` | the real-world result | paiement reçu, promesse tenue, échéancier accepté | **no — v1.1, gated (§A1.6)** |

The Métier tab groups its KPIs by level. **Display honesty rule (binding):** an `outcome`
signal is never presented as real-time — it renders with its consolidation horizon
("estimé J+7 / consolidé J+14") from the declared attribution window; and an `outcome`
signal is **undeclarable** until the real feed exists (§A1.6 discipline — the manifest
validator rejects it).

### A2.3 — Policy metadata is declared; implementations stay code

The AgentSpec gains a `policies` block of **metadata only**:

```yaml
policies:
  - id: contact_window_policy
    label_key: policy.contact_window
    version: 1.0.0
    severity: blocking          # blocking | warning
    applies_to: [check_contact_rule, draft_reminder, prepare_client_message]
    reason_codes: [out_of_contact_window]
```

The garde-fous tab renders policies, versions, reason codes and block volumes from this
metadata + grammar events, without knowing the domain. Implementations remain deterministic
code in the domain package (§A1.1 stands; the YAML *engine* stays rejected). **Gate
condition (L2):** every `severity: blocking` policy is covered by ≥ 1 eval case; a blocking
policy without eval coverage fails the conformance gate. Waivers follow the existing
governed rules (`eval_waivers.py`: Tier 0 never effective).

### A2.4 — The observability level becomes a release-gate condition

The release gate (`/agir/release-control`, `agent_lifecycle` / `agent_release`) gains two
conditions, unifying the vision draft's five gates with the L0–L3 ladder instead of running
two gate systems:

1. **No production below L2** — an agent whose guard/audit/eval facts the cockpit cannot
   see is not releasable, whatever its scores.
2. **L3 required when it matters** — an agent declaring capabilities with
   `external_effect_level ∈ {requires_validation, external_action}` must be **L3** (its
   §A1.3 invariant must be *verifiable*, which requires its business events to flow).

The draft's lifecycle (Draft → Configured → Evaluated → Shadow → Limited → Production →
Monitored) is **not** adopted as a new state machine — the existing release states +
lifecycle module remain; the L-level is a *condition*, not a parallel lifecycle.

### A2.5 — v1.1 candidate list, extended (still gated on reality)

Appended to §2's candidates, never added speculatively: `capability.failed` (the grammar
has **no failure verb** today — a real gap; failure currently lives only in span status),
`capability.started` (only if a real duration/abandon fact needs it; the turn span already
carries latency), and the human-action verbs (`artifact.inserted|submitted|reported|escalated`)
— to be resolved in v1.1 **either** as canonical statuses on `artifact.status_changed` (+
A2.1 actor) **or** as event names, whichever keeps the grammar smallest. `outcome.received`
/ `action.executed|failed` unchanged from §A1.6.

### Migration impact

A2.1 + A2.3 land with Phase B (manifest + envelope work); A2.2 lands with Phase C (Métier
tab); A2.4 lands with Phase E (conformance) touching `agent_release`; A2.5 changes nothing
now.

## Context

Two workstreams converged on the same seam from opposite sides:

1. **The read side is already store-decoupled.** ADR 0015 executed A→G5 on
   `feature/redesign`: `Scope`, the `SignalSpec` registry with declared dimensions, the
   batched snapshot endpoint, read adapters (prometheus / postgres / clickhouse / langfuse /
   ledger), per-fact source flips. The cockpit no longer knows *where* a technical fact
   lives.
2. **The write side already has a generic business envelope.** ADR 0016 defined
   `BusinessEvent` v1 and its fan-out (OTel span events, Prometheus counters, audit ledger
   when opposable, replay bundles, a `BusinessEventStore` read-model port). The
   `BusinessScoringRegistry` keeps domain scoring rules in domain packages
   (`recouvrement.collections.v1` emits six deterministic business scores).

Yet three couplings remain, and one of them is *growing*:

- **Process coupling.** The observability API lives in the same FastAPI process as the
  agents. `InMemoryBusinessEventStore` and the remaining ring buffers are readable only
  in-process: an agent running anywhere else is invisible to the cockpit *by construction*.
- **Undeclared instrumentation boundary.** `instrument.py` and `graph_topology.py` are
  LangGraph-specific (`graph_topology` names `langgraph` in a type hint; `instrument`
  wraps LangGraph nodes). The code is correct; the boundary is implicit — nothing marks it
  as "the LangGraph adapter of a contract", so nothing stops the next module from deepening
  the dependency.
- **Per-agent wiring (the growing one).** Commit `e6bd8ca` ("expose recouvrement runs in
  cockpit") added `/observability/recouvrement-runs` with `agent_id` / `workflow_id`
  hardcoded server-side, a hardcoded `recouvrement` entry in the dashboard `TAB_DEFS`, a
  bespoke `fetchRecouvrementRuns`, and a 430-line `RecouvrementRunsPanel`. This is
  **O(agents × panels)** — the exact bug class ADR 0015 made *unrepresentable* for
  dimensions (silent-ignore, hand-placed honesty), reintroduced for business signals. At
  one business agent the cost is invisible; at ten it is the architecture.

The fleet is about to grow. This ADR settles what must be true so that **agent N+1 — any
runtime, any domain — becomes technically *and* functionally observable with zero cockpit
change, at equal or higher quality than today.**

## Governing rule

> **Agents publish; the cockpit reads the spine; nobody queries an agent.**

This extends 0015's one-canonical-source rule and 0016's fan-out to a plane split: agents
are the **data plane**, the spine (OTel collector → Phoenix/Langfuse, Prometheus, owned
Postgres/ClickHouse, the audit ledger) is the **telemetry plane**, the cockpit is the
**control plane** and consumes *only* spine ports. The contract below is **data-plane, not
API-plane**: an agent is integrated by what it *emits and declares*, never by an API the
cockpit would have to call (a federation of agent APIs would recreate the availability
coupling and the loss of as-of-T that 0015 rejected when it demoted Langfuse).

**The platform's own SLO — Time-to-Observability (TTO):** elapsed time from scaffolding a
new agent to its full cockpit presence. Targets: **L1 ≤ ½ day, L3 ≤ 2 days, cockpit diff =
0 lines.** TTO is measured per onboarding and recorded; a platform that misses it has a
regression, exactly like a perf budget (0015 §Performance discipline, applied to the
platform itself).

## Decision

### 1. The Agent Observability Contract (the port named by signal 102)

An agent is **cockpit-observable** iff it satisfies five obligations:

| # | Obligation | Medium | Today |
|---|---|---|---|
| 1 | Spans | OTel, GenAI + Tessera semconv, stamped with the full `Scope` dimension set (`agent_id`, `language`, `model`, `conversation_id`, `turn_id`, `environment`) | exists (`semconv.py`, 0015 §B) |
| 2 | Metrics | Prometheus, labels ⊆ Scope dimensions, low-cardinality (never per-case/conversation labels) | exists |
| 3 | Business events | `BusinessEvent` v1 envelope (0016), conforming to the workflow grammar (§2) | exists |
| 4 | Opposable facts | **authenticated, guaranteed write to the owned hash-chained ledger — never best-effort transport** | exists in-process; remote path = outbox (§7, Phase E) |
| 5 | Declaration | an `AgentSpec` manifest entry (§3) | **new** |

The port keeps the name the catalog gave it: **`ObservabilityBackend`** (signal 102,
`plugin-sdk`). The cockpit consumes only spine ports — `SignalSpec.read(scope)`, the
snapshot, `BusinessEventStore`, the store adapters. Obligation 4 is 0015's *own what gates
or proves; best-effort what you sample or observe* extended to **transport**: telemetry may
ride OTLP best-effort; proof may not.

**The boundary is enforced, not conventional.** An `import-linter` contract in CI forbids
`tessera.observability.*` and the cockpit routes from importing `tessera.agent.*` (and
`langgraph`) — the same "make the illegal state unrepresentable" move as 0015's registry,
applied to the module graph. The deployment split (a separate `cockpit-api` reading only
spine stores) becomes a deploy decision, never a rewrite; it is *not* exercised now
(modular monolith retained at n=3).

### 2. The workflow grammar becomes a versioned spec

The 13 `BusinessEventName` values are the platform's real generative asset: a
**domain-agnostic workflow grammar** —

```
case.context_loaded → intent.routed → slots.extracted → business_rule.checked
→ policy.decision_made → artifact.created|updated|status_changed
→ validation.requested → action.requested|prepared|blocked → message.generated
```

Functionally onboarding agent N+1 means **mapping its domain onto this grammar**: its
vocabularies (`reason_codes`, `artifact_type`, policy rule ids) stay in its package (0016
rule, restated); its `BusinessScorer` registers; its KPIs are declared (§3). The Métier
surfaces (§6) render the grammar, never the domain — a "fraude" or "KYC" agent tomorrow is
a vocabulary and a scorer, not a panel.

This ADR promotes the grammar from "known names" to a **versioned spec**:

- `grammar_version = workflow_grammar.v1`, carried on the envelope alongside
  `schema_version` (envelope shape) — the two version independently.
- **Extension rule:** a new event *name* enters the grammar only through an amendment to
  this ADR, with a strict payload schema and a fan-out classification. Domain constants
  never enter the grammar. Nothing is added speculatively.
- **Named v1.1 candidates (deliberately NOT added now):** outcome verbs `action.executed`
  / `action.failed`, and a terminal `workflow.completed` (which would give "runs" a real
  terminator instead of the current turn-grouping). They are added the day a real agent
  executes real actions — recouvrement today only *prepares* them, and inventing outcome
  events for actions that cannot occur would violate the honesty rule.
- **Payload privacy rule (new, binding):** strict payload schemas must be **PII-free by
  construction** — identifiers are references (`case_id`, `artifact_id`, template ids),
  never free text carrying personal data. Free text belongs to the trace (Langfuse), which
  has its own PII/erasure regime; business events are long-retention dimensional telemetry
  and must stay erasure-cheap (§5).

### 3. AgentSpec — the manifest is the single onboarding artifact

The registry entry (`agents.yaml`, ADR 0012) grows an `observability` block and becomes the
**AgentSpec** — one declarative artifact from which everything downstream is *generated*.
A manifest is an API, not config: `spec_version`, JSON-schema/pydantic validation as a CI
gate, explicit migrations.

```yaml
- id: recouvrement
  # … existing identity / audience / surface / auth (0008, 0010) …
  product_surface: { route: /produit/recouvrement, shell: credit_aurore_internal }  # ⚠ §Amendment 1 (A1.5)
  observability:
    spec_version: agentspec.v1
    telemetry_capabilities: [graph_topology, tools, memory]  # ⚠ renamed (§A1.1); panels render iff declared
    capabilities: [ … ]        # ⚠ §Amendment 1 (A1.1) — typed business capabilities, external_effect_level
    policies: [ … ]            # ⚠ §Amendment 2 (A2.3) — declared metadata; implementations stay code
    workflows:
      - workflow_id: recouvrement_collections_v1
        grammar: workflow_grammar.v1
        scorer: recouvrement.collections.v1          # BusinessScoringRegistry id
    business_signals:
      - key: contact_window_compliance
        source: business_score                       # or business_event (counted)
        level: runtime               # ⚠ §Amendment 2 (A2.2) — runtime | human_action | outcome
        unit: ratio
        aggregation: mean
        dimensions: [agent, time]
        engagement: legal          # projects onto Conformité (catalog rule: page + fiche)
        north_star: true           # the ONE fleet-card chip
      - key: sensitive_actions_blocked
        source: business_event     # count of action.blocked
        unit: count
        aggregation: sum
        dimensions: [agent, time]
```

**Generated from the manifest** (never hand-written per agent): backend `SignalSpec`
entries and the frontend `signal-registry.ts` mirror; the fleet-card north-star chip; the
Métier tab contents; the À traiter item sources; capability-gated panels (an agent that
does not declare `graph_topology` simply gets no topology panel — the same honest mechanics
as the org-wide badges); Prometheus recording rules for the declared aggregations (keeps
rule sprawl and cardinality budgeted at the source); i18n keys (the existing
`i18n-missing-sweep` becomes a gate on manifest-declared labels); the conformance test
matrix (§4).

### 4. The L0–L3 conformance ladder — quality that scales without human review

| Level | The agent provides | CI gate (machine, not review) | The cockpit unlocks |
|---|---|---|---|
| **L0 Registered** | a valid AgentSpec | schema validation | fleet card (honest-empty) + level badge |
| **L1 Observable** | spans + metrics with full dimension stamping | span-contract tests (signals 103/104) | technical tabs: synthèse, fiabilité, coût |
| **L2 Governed** | guard→ledger events, eval gating runs, release states | gating harness green (0015 Nature 1) | sécurité, release, audit surfaces |
| **L3 Business** | grammar events + registered scorer + `business_signals` | grammar conformance + scorer determinism tests | Métier tab, À traiter items, north-star chip, Conformité projection |

The cockpit **displays the level**, and a level is *computed from passing gates, never
asserted* — honesty as the incentive to climb (the Backstage-scorecard pattern, applied to
observability). Three quality nets attach **automatically at onboarding**, generated from
the manifest — this is how the fleet gets *more* quality than today, because these stop
being artisanal:

- **scheduled canary turns** (signal 94) per agent, with freshness surfaced ("dernier
  canary vert il y a X min") — a broken pipeline is seen before an operator misses data;
- **instrumentation coverage vs the contract** (signal 92) — "this agent emits 96 % of
  required attributes", which also defends the ladder against trivially-gamed emissions;
- **golden traces** in CI (signal 41), seeded from the agent's eval set.

### 5. The business read-model home: owned ClickHouse

0016 §Consequences reserved the decision: *"if a future product requires a durable
historical business-event read model … it must implement the `BusinessEventStore` port with
an owned indexed store and record that store decision here or in a follow-up ADR."* The
multi-agent cockpit is that product; this is the follow-up ADR. By the 0015 governing rule
(and exactly the Corr.2b reasoning): business events are **dimensional, traffic-driven
monitoring telemetry** → **owned ClickHouse, direct insert**; the opposable facet already
lives in the Postgres ledger (fan-out unchanged); aggregates remain Prometheus.

```sql
CREATE TABLE tessera.business_events (
    occurred_at      DateTime64(3),
    agent_id         LowCardinality(String),
    workflow_id      LowCardinality(String),
    capability_id    LowCardinality(String),  -- ⚠ §Amendment 1 (A1.2); '' when pre-amendment
    event_name       LowCardinality(String),
    conversation_id  String,
    turn_id          String,
    case_id          String,
    artifact_id      String,
    artifact_type    LowCardinality(String),
    artifact_status  LowCardinality(String),
    decision         LowCardinality(String),
    reason_codes     Array(LowCardinality(String)),
    actor            LowCardinality(String),
    surface          LowCardinality(String),
    language         LowCardinality(String),
    model            LowCardinality(String),
    environment      LowCardinality(String),
    schema_version   LowCardinality(String),
    event_version    UInt16,
    grammar_version  LowCardinality(String),
    payload          String                -- JSON; strict-schema validated at write time
) ENGINE = MergeTree
ORDER BY (agent_id, workflow_id, event_name, occurred_at)
PARTITION BY toYYYYMM(occurred_at)
TTL toDateTime(occurred_at) + INTERVAL 6 MONTH;   -- aligned with eval_online_scores
```

`InMemoryBusinessEventStore` is demoted to the local/test default (never a prod read path).
GDPR erasure reaches this table by `conversation_id` (mirrors the G4 owned-store purge);
the §2 payload privacy rule is what keeps that erasure cheap and complete.

### 6. Where business metrics surface — five existing surfaces, zero new pages

1. **Flotte (`/agents`)** — one **north-star chip** per agent card (`north_star: true`) +
   a pending-business-items count. **Never an org aggregate of heterogeneous business
   KPIs** — units are incomparable across agents; chips per agent, no sum.
2. **Fiche agent — new tab « Métier »** (between Synthèse and Évaluations): KPI strip (the
   declared business scores, current value + trend), the runs table, drill-down run →
   grammar-event timeline → artifacts, decisions, blocked actions with `reason_codes`.
   **⚠ §Amendment 1 (A1.4): the tab's primary view is the per-capability table (volume,
   conformity %, validation-required %, blocked %, effects prevented, trend); the runs table
   becomes its drill-down.**
   Two deliberate exclusions: **not in Synthèse** (the AT-01 rule extends: operational ≠
   métier) and **not merged into Évaluations** (separate by nature: LLM-judged quality vs
   deterministic workflow conformity).
3. **À traiter** — `validation.requested` and `action.blocked` become `OperatorItems`
   (second item source beside eval runs; `agent_id` present since 0015 Phase E),
   deep-linking to the run in the Métier tab. This is where business observability becomes
   *actionable*.
4. **Surveiller · Conformité — selective projection, not default.** The catalog already
   has the mechanism ("a signal appears on its `page` and on the fiche of its `entite` —
   same data, two projections"): a business signal declared `engagement: legal`
   (`contact_window_compliance`, `validation_required_compliance` — contact windows in
   collections are a regulatory constraint) *also* renders on Conformité, Scope-filtered
   like everything else. Others stay Métier-only. Nothing leaks to Qualité IA / Sécurité.
5. **Prouver — already wired.** Auditable events reach the hash-chained ledger via the
   0016 fan-out and appear filtered by `agent_id`; `état-à-date` replays them as-of-T for
   free (the envelope carries timestamp + dimensions).

**Removals (the e6bd8ca unwind):** the hardcoded `recouvrement` tab in `TAB_DEFS`;
`fetchRecouvrementRuns`; the server-side hardcoded `agent_id`/`workflow_id`. The 430-line
panel is **salvaged, not discarded**: it becomes the first instance of the generic
`<WorkflowRunsPanel>`, and the route generalises to
`/observability/business/runs?workflow_id=…&agent=…` — dimension filters only, never
payload inference (0016, restated).

**Catalog change:** add `metier` to the `page:` vocabulary of `signal-catalog.yaml`;
signals 65 (`cost-per-resolution`), 139 (`roi-view-buyer`), 190
(`per-agent-attribution`) are candidates to re-home there.

### 7. The SDK: two profiles, one wire

- **In-process profile** — `tessera-agent-sdk` (Python package): `instrument.py`,
  `graph_topology.py` and the typed emitters move here; **LangGraph is the reference
  adapter**, not a cockpit dependency. Graph-specific signals become declared
  *capabilities* (§3). This is signal 107 (`tessera-otel-genai` lib extraction) begun
  in-repo.
- **Remote profile** — pure OTLP: the existing collector routes traces →
  Phoenix/Langfuse, business span-events → the ClickHouse pipeline (§5), metrics →
  Prometheus. An agent in another process or language needs no Python import to reach L1.
  **Binding exception:** opposable facts never travel best-effort — an authenticated
  outbox write to the ledger (obligation 4).
- **The SDK ships its testkit**: the span-contract and grammar-conformance suites any
  agent repo runs in CI — the L1/L3 gates are a `pip install`, not a bespoke setup.
- **The paved road**: a `tessera agent new` scaffold generates package skeleton, AgentSpec
  stub, eval-set stub and wired conformance tests; a minimal `hello-agent` reference
  implementation is kept green in CI as executable documentation.

## Migration plan (ordered; each phase independently shippable; twice-green gate discipline)

- **A — Freeze the boundary.** `import-linter` contract (cockpit ⊄ `tessera.agent.*` /
  `langgraph`); generalise the recouvrement route + panel (kill the three hardcodes);
  stamp `grammar_version`. Gate: pixel/data parity of today's recouvrement runs rendered
  through the generic components.
- **B — AgentSpec v1.** Schema + CI validation + generation of `SignalSpec`s / frontend
  mirror / level badge (L0–L2 computed from existing facts). Recouvrement declares the
  first manifest.
- **C — Business surfaces.** Métier tab + fleet chip + À traiter source + Conformité
  projection, all manifest-driven. Gate: recouvrement fully re-homed; hardcoded tab
  deleted; recouvrement reads L3.
- **D — Durable read-model.** ClickHouse table + dual-write → backfill (replay bundles +
  in-memory seed) → shadow parity → flip `BusinessEventStore` reads → in-memory demoted to
  test default. Erasure path probe-proven (G4 pattern).
- **E — SDK extraction + quality nets.** Move instrumentation into the SDK; span-contract
  + grammar-conformance suites (signals 103/104); canary turns (94) + coverage signal (92)
  generated per agent from the manifest.
- **F — Second-runtime proof (the acceptance test) — LANDED 2026-07-08.** A minimal
  out-of-process demo agent (`examples/hello-agent/`, OTLP profile, no LangGraph, **zero
  `tessera` import**) reaches **L1** with a **zero AGENT-SPECIFIC cockpit diff**. **TTO
  measured: 20m18s** (target L1 ≤ ½ day). Acceptance verified end-to-end: hello-agent → collector
  → Prometheus (`tessera_agent_turns_total{agent_id="hello-agent"}` = live turns) → the fleet
  card computes **L1 from that real fact**; the span-contract testkit passes against its
  emission; `webapp/` and the agent-specific control plane are untouched.

  **§Phase-F precision (recorded at closure).** The L1 gate surfaced a real gap: the §7
  remote-profile ingestion — an agent's spans/metrics reaching a store the resolver reads — was
  named here but never built, so L1 was a manifest-only projection (a badge *asserted*, not
  *computed* from emission — a §4 violation). Closing it is a **generic platform completion**, a
  one-time capital cost, NOT per-agent onboarding — therefore: (1) the acceptance is refined to
  **zero AGENT-SPECIFIC cockpit diff** (generic completions in `observability/` are allowed and
  **off the TTO chrono**; any `if agent_id == …` is forbidden and fails it); (2) the TTO measures
  hello-agent's **marginal** onboarding on the completed platform. Per §A2.4 + 0015 Amendment 1
  (a *gating* fact must not read a best-effort third-party store — Langfuse was rejected for
  exactly that), the completion is a **Prometheus turn-count read**: `observability_level` gains
  `has_turn_evidence`, sourced from `tessera_agent_turns_total` via the existing Prometheus
  adapter, gated (`TESSERA_LEVEL_TURN_EVIDENCE`) and honest-empty; the collector re-exports
  remote OTLP metrics to Prometheus (config).

  > **Correction (2026-07-09, ratified in `0017-execution-status.md`).** This paragraph first read
  > "evidence-*unknown* is trusted, never treated as absence". That was the over-claim class this
  > project forbids: a silent store made a *declared* rung render as a *computed* one. Evidence-
  > unknown is now **no proof** — a computed rung never rests on an assumption. Nothing is hidden
  > by refusing to guess: the caller also reads what the manifest declares, and the badge renders
  > the attenuated "L{n} declared · no evidence" variant, distinguishing `unverifiable` (store off
  > or unreachable) from `dormant` (store read, agent has emitted nothing). See
  > `observability/turn_evidence.py` and `webapp/frontend/lib/level-badge.ts`.
  **Platform-completion commits (off-chrono):** `58d8b720` (evidence-path ruling), `42b25e57`
  (resolver + `observability/turn_evidence.py`), `639b6403` (collector/prometheus config). The
  honest accounting: the FIRST external agent flushes out these one-time gaps; the standing
  acceptance property is that the SECOND onboards zero-diff.

Sequencing note: A–C are cockpit-side and belong with the redesign UI after the branch
reconciliation; D–F touch runtime + infra. Targeted staging only, never `git add -A`
(0015 §Execution protocol applies).

## Consequences

**Positive.** Adding an agent = manifest + SDK + gates: TTO in hours/days, zero cockpit
diff; business observability is first-class without a parallel system (same spine, same
Scope, same honesty machinery); the silent-ignore bug class stays unrepresentable because
business signals ride the same registry; quality *increases* while scaling because
canaries, coverage and golden traces attach systematically instead of artisanally; the
control plane becomes separately deployable at will.

**Negative / costs.** The manifest + generators are new machinery with a real maintenance
duty; ClickHouse gains a second owned table (schema evolution to manage); grammar
versioning is a governance cost (every extension is an ADR amendment — deliberate
friction); the ladder could be gamed by minimal emissions — mitigated by the coverage
signal and golden traces; the SDK split adds a package boundary to maintain.

**Neutral.** LangGraph remains the only in-tree runtime; nothing in this ADR forces a
second one — Phase F merely proves the seam. The ledger, gating scores and Prometheus
homes are untouched (0015 Amendments 1–3 stand).

## Alternatives considered

- **Federation — the cockpit queries each agent's API.** N availability couplings, no
  as-of-T, per-agent auth surface; recreates the convenience-path smell over the network.
  Rejected — consistent with 0015 demoting Langfuse as a read source.
- **Hardcoded per-agent panels (the e6bd8ca status quo).** Fastest for agent #1,
  O(agents) forever, triple i18n drift, hand-maintained honesty. Rejected; the panel is
  salvaged as the generic component's first instance.
- **Plugin UI SDK (Backstage-style: agents ship React panels).** Maximal flexibility,
  heavy security/governance (third-party code in the operator console), premature at
  n = 3. Deferred — the manifest covers ~90 % of rendering needs; a `custom_panel` slot
  remains the future escape hatch.
- **Abstracting the agent engine (wrapping LangGraph).** Framework invention — forbidden
  by the project thesis. We standardise **telemetry**, not runtimes.
- **A message bus (Kafka/NATS) for business events.** No measured backpressure fact
  demands it; the collector + direct owned-store writes suffice. Revisit only on evidence.

Appended by §Amendment 1 — from the "ADR-001" vision draft, rejected:

- **Staged metric store ("Postgres/Timescale V1 → ClickHouse or BigQuery at scale").** The
  build-twice pattern 0015 §Corr.2b explicitly withdrew — ClickHouse already runs in the stack
  and is the decided home (§5); BigQuery is the external warehouse 0015 §Alternatives rejected.
- **Staged event transport ("Postgres events → Kafka/PubSub/NATS at scale").** Restates the
  bus-without-a-fact roadmap rejected above; the 0016 fan-out + collector are the transport.
- **A parallel event taxonomy** (`agent.capability.completed`, `agent.policy.blocked`, …)
  without the envelope — no `schema_version`, no classification, no fan-out homes, no extension
  rule. Adopting it would fork the event model. Its needs are met by `capability_id` on the v1
  envelope (§A1.2) and the gated v1.1 grammar names (§A1.6).
- **A generic YAML policy engine.** Premature genericity; deterministic policies remain code in
  domain packages (0016 rule), with **ids + reason codes declared** in the AgentSpec so the
  cockpit renders them — the draft's own §7 ("ces règles appartiennent à des services métier
  dédiés") agrees with this resolution.
- **(§Amendment 2, from the "ADR-003" draft)** The staged event pipeline "Postgres
  `agent_events` + materialized views → Kafka/PubSub/NATS + stream processor →
  ClickHouse/BigQuery/Timescale" — restates both regressions at once (build-twice store +
  bus-without-a-fact); same rejection, the 0016 fan-out into the §5 owned store is the
  pipeline.

## Open questions

- Fleet-card density at ~30 agents: grouping by a `domaine` dimension (a `Scope`
  extension) and card virtualisation — design when the fleet approaches double digits.
- Retention: the 6-month TTL matches `eval_online_scores`, but `engagement: legal` signals
  may need longer *aggregate* horizons — decide whether recording rules + the ledger cover
  the legal need or the TTL diverges per classification.
- Whether L2 requires the full gating catalogue or a floor case-count for young agents
  (`gate_min_pass_rate` exists — is there a "provisional L2"?).
- Phase F demo agent: runtime choice (candidate: plain FastAPI + httpx, ~200 lines, no
  LangGraph) and where it lives (in-repo example vs companion repo — ties to signal 162).
- (§Amendment 1) Outcome-feed source for the v1.1 attribution metrics — webhook vs batch
  import vs manual operator confirmation — decided with the first real send channel; until
  then `event_ratio` signals stay undeclarable.
