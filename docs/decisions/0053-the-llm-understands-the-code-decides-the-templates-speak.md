# 0053 — Recouvrement goes hybrid: the LLM understands, the code decides, the templates speak

- Status: accepted (validated by the operator, 2026-08-22)
- Date: 2026-08-22
- Supersedes: none
- Superseded by: none
- Relates to: [0010](0010-recouvrement-internal-operator-agent.md) (the operator agent this
  redesigns), [0017](0017-agent-observability-contract.md) §Amendment 4 (the declared quality
  regime this evolves), [0021](0021-eval-gate-on-measured-contribution.md) (contribution over the
  measured null floor — applied here to a classifier), [0026](0026-a-witness-interrogates-the-thing.md)
  (every new number below names its witness), [0030](0030-operable-knobs-carry-a-governed-override.md)
  (the switch and the threshold are governed knobs), [0034](0034-llm-budget-ceiling-is-an-operable-governed-knob.md)
  (the daily ceiling the new call answers to)

## Context

Recouvrement today calls **no LLM anywhere**. Verified in the tree, 2026-08-22:

- **Understanding** is regex over accent-stripped text: five `_has_*_intent` matchers plus
  `_parse_duration_months` / `_parse_time` in `src/tessera/agent/recouvrement.py`, arbitrated by
  the priority ladder in `route_recouvrement_intent`.
- **Speech** is approved, versioned templates (`src/tessera/recouvrement/message_templates.py`,
  provenance stamped via `DraftGenerationMetadata`, months spelled out so a regulated letter
  never depends on the host locale).
- **Money and acts** are deterministic code: `money.py` arithmetic, policy nodes, and the
  ten-signal `RecouvrementBusinessScorer` (`scoring.py:429`) with the honest
  `scored / unknown / not_applicable` vocabulary.
- Its declared ruler is `quality_regime: business_scored` (ADR 0017 §A4): template-assembled
  replies give LLM faithfulness no referent, so the online judge deliberately does not cover
  this plane.

The operator's verdict (2026-08-22, recorded in the steering dossier): this design is the right
*demonstration of the deterministic ruler* but not the target premium agent. The weak point is
precisely **understanding**; everything else is a strength to keep.

The weakness is measured, not aesthetic:

- **A bare verb was an intent.** `prepare` / `préparer` sat in the draft matcher with no object;
  "Résume ce dossier pour **préparer** l'action suivante" produced a reminder draft instead of a
  summary — reproduced on the deployed host on 2026-08-02, fix documented in the
  `_has_draft_intent` docstring. Word-list routing fails exactly this way, one list at a time.
- **The default branch is a guess wearing a confidence.** Any text no list matches routes to
  `check_contact_rule` at `0.72` — a number that looks like calibration and is a constant.
- **Three languages multiply every list.** Each matcher hand-carries FR/EN/DE synonyms;
  every phrasing not on a list is a silent misroute, and the lists cannot say what they miss.

One strength of the current router is load-bearing and **must survive the redesign**: a
`declaredIntent` from a pressed button routes with precedence and no classification — "a
declared capability is an ANSWER, not a hint" (`_declared_intent` docstring). The LLM only ever
runs where there is genuinely something to understand: free text.

## Decision

Recouvrement becomes a **three-layer hybrid**. One sentence per layer, then the binding detail:
**the LLM understands, the code decides, the templates speak.**

### 1. Layer 1 — the LLM understands (new)

A single LLM call per free-text turn produces a **schema-validated structured verdict** and
nothing else:

- `intent` — closed vocabulary: exactly the capability ids the agent's manifest declares
  (`agents.yaml` → `summarize_case`, `check_contact_rule`, `explain_payment_options`,
  `draft_reminder`, `propose_schedule`). The schema rejects anything outside the vocabulary; a
  new capability must be declared in the manifest before the classifier may name it.
- extracted fields — the slots the graph already consumes: amount, duration in months,
  requested date/time, tone. Absent is absent; the schema forbids invented fields.
- `confidence` — self-reported, and treated as such (see §6: the number that gates it is
  calibrated, never trusted).

**The LLM never speaks to the client.** Its output is consumed by the graph only; the visible
reply remains template-assembled (layer 3). This is a type-level property: the classifier
returns a validated object, not text, so there is no path from model prose to the operator.

**Model: the existing router seam, no new dependency** (operator decision, 2026-08-22).
`tessera.llm.router.get_chat_backend()` resolves by profile — Vertex on the frontier target,
Llama 3.3 70B via Ollama on-prem — so **both deployment targets keep a live layer 1** and the
call is metered by the budget tracker like every other LLM call. The prompt lives in YAML under
`src/tessera/agent/prompts/` per repository convention, versioned, and its version is stamped
into telemetry and bench reports.

**Deterministic fallback: the regex router is not scaffolding — it stays forever**, in three
roles: (a) the unconditional fallback when the LLM fails, times out, returns schema-invalid
output, or the daily ceiling is reached (ADR 0034 — a spent budget degrades understanding, it
never refuses the operator's turn); (b) the **null floor** the LLM must measurably beat to
justify its cost (ADR 0021, applied to a classifier: the regex IS the no-model baseline);
(c) the authoritative router during the shadow phase (§5).

Every turn records how it was understood: `intent_source ∈ {declared, llm, regex,
regex_fallback}` in the `INTENT_ROUTED` business event — the audit trail must be able to tell a
declared intent from a classified one from a degraded one, because only some of them can be
wrong in some ways.

### 2. Layer 2 — the code decides (unchanged)

Capabilities, business rules, policy nodes, schedule arithmetic, the ten business signals, the
output guard, surface authorization: **untouched**. Deterministic forever, by decision:
regulated texts, schedule arithmetic, business scoring, and the output guard are never
delegated to a model.

### 3. Layer 3 — the templates speak (unchanged)

Approved templates remain the **only** client-facing text. The later option — LLM tone
rephrasing **constrained by the approved template**, where the template becomes the judge's
REFERENT and template-fidelity becomes a metric that finally means something — is **named here
and explicitly out of scope**. It sits behind the guard and the escalation path and gets its
own ADR if opened. Naming it prevents two misreadings: that this ADR forbids it, and that this
ADR includes it.

### 4. Two rulers on two layers, never fused

⛔ The defect already paid for on the certifying matrix (insights 361–363) is the boundary of
this design:

- **The understanding ruler** judges layer 1: intent accuracy against a labeled set ×3
  languages on the offline bench (§7), plus online agreement telemetry during shadow. Its
  population is *classified turns*.
- **The money-and-acts ruler** judges layers 2–3: the ten deterministic business signals,
  unchanged. Its population is *business runs*.
- The two populations are disjoint and never share a denominator; no surface may show a single
  number that absorbs both. Any future cockpit surface for layer 1 speaks screen language
  (counts, plain words — never « barème / population / régime ») and carries its freshness and
  its blind spots (ADR 0026 / 0052).

**The declaration evolves — declared, never inferred (ADR 0017 §A4).** `business_scored`
remains the declared ruler of the spoken plane. The understanding layer gains its **own
explicit declaration** on `AgentObservabilitySpec` — an `understanding` block naming its mode
(`llm_structured` vs `deterministic`), its bench set, and its telemetry — with integrity rules
in the A4 shape: a graph that wires an LLM understanding node without declaring it is refused
at conformance, and a declaration with no wired node likewise (a witness interrogates the
thing). No default: an agent that understands with a model says so or does not load. Exact
field names are settled in the implementation slice, where the ADR 0017 §Amendment 5 text
lands with the code that makes it true.

### 5. Shadow first; the switch is a governed act (operator decision, 2026-08-22)

- **Phase S — shadow.** The LLM classifies **in parallel, off the hot path** (fired
  asynchronously; zero added latency to the operator); the regex remains authoritative. Each
  shadowed turn records, in the ledger: the regex verdict, the LLM verdict, `schema_valid`,
  agreement, and the LLM's latency. Cost stated plainly: during shadow, every call is paid and
  buys measurement only, no operator benefit.
- **The switch is a governed knob** (ADR 0030 family): flipping shadow → active is a journalled
  act with a named author, never a code edit. Its precondition is written on the knob: the
  offline bench shows the LLM beating the regex floor on the labeled set, and online agreement
  has been measured over real turns — the numbers read from bench reports and the ledger, never
  asserted.
- **Active mode.** The LLM's verdict routes the graph when it is schema-valid AND its
  confidence clears the threshold (§6); otherwise the regex routes. Declared intent keeps
  absolute precedence in every mode. In active mode the call is on the hot path and bounded by
  a timeout (a governed knob whose value is measured, not picked); timeout ⇒ regex, recorded.

### 6. The fallback rule is engraved; the threshold number is measured (operator decision, 2026-08-22)

Below the confidence threshold, layer 1 falls back to the regex. The ADR fixes the **rule**;
the **number** comes from calibration on the labeled bench during the shadow phase — the
threshold that maximizes net accuracy against the regex floor — and is then set as a governed
knob carrying its provenance (which bench run produced it). Self-reported LLM confidence is
notoriously miscalibrated; a hand-picked `0.7` would be a number nobody measured, and the
existing regex constants (0.93–0.96 / 0.82 / 0.72) live on a different, hand-written scale —
the two confidences are **never compared to each other**; agreement is measured on intents,
never on confidences.

Unconditional fallbacks, independent of any threshold: LLM error, timeout, schema-invalid
output, daily ceiling reached.

### 7. The bench — a labeled intent set ×3 languages, with the regex as the null floor

Layer 1 is unverifiable without a referent, so the referent is a deliverable **before** the
classifier (slice order, §Slices):

- **A new labeled artifact** — utterance, language, expected intent, expected fields,
  provenance — schema-validated like the failure catalogue. This is **not**
  `eval/sets/recouvrement.json`: that set asks the safety/regression question over the failure
  catalogue; this one asks "was the operator understood". Two questions, two artifacts.
- **Coverage floor**: enough cases per (language × intent) that per-intent accuracy is a real
  rate, not a count in disguise — a cell with n=1 may only ever be reported as a count.
  Translated cases are reviewed by a reader before they are labeled truth.
- **The runner calls the classifier directly** (package-level, like the eval harness — no HTTP,
  no auth) and always prints **two columns on the same set: the LLM and the regex**. A report
  that shows one column hides the floor. Reports land under `eval/reports/`, stamped with model
  id, prompt version, set version, and window (ADR 0052: a numbered surface names its origin
  and its absences).
- **Immediate side value, before any LLM lands**: the regex baseline over the labeled set is
  deterministic, so it becomes a gate ratchet at once — an edit to the regexes that silently
  drops their measured accuracy turns the gate red. The set pays for itself in slice 2.
- The gate itself never calls an LLM: LLM-column runs are operator-launched or scheduled, like
  every other harness run.

## Costs, named

1. **One LLM call per free-text turn.** Latency: none in shadow (async, off the hot path);
   bounded by the measured timeout in active mode. Spend: metered per backend/model by the
   budget tracker, gated by the org-wide daily ceiling (ADR 0034); ceiling reached ⇒ silent*
   degradation to regex — *silent to the client, loud in the ledger (`intent_source:
   regex_fallback`) and on the budget surfaces. At recouvrement's measured volume (67 business
   runs lifetime) the spend is negligible; the ceiling is the guard against the volume this
   design is built to invite.
2. **A labeled intent set ×3 languages.** Authoring and review effort, and it is the referent —
   mislabeled truth poisons both columns. Translation helps produce candidates; only review
   makes them labels.
3. **Measurement wired outside `chat.py`.** The online judge seam (`_run_online_eval`,
   `chat.py:164`, one call site) stays where it is: this ADR does **not** wire faithfulness
   onto template-assembled replies — that metric has no referent here and the score would be
   fabricated. The recouvrement plane is measured by its own witnesses instead: ledger
   telemetry (shadow agreement, `intent_source`, fallback counts) and the offline bench. The
   *generic* hole — any future LLM-speaking plane outside `chat.py` would be unjudged — is
   real, known, and **out of scope here**; it is named so nobody reads this ADR as having
   closed it.
4. **A second prompt surface to govern.** The classifier prompt is a versioned YAML artifact
   ×3 languages; its version travels with every score it influences.

## What this ADR refuses

- Fusing the two rulers into one number, on any surface, ever (insights 361–363).
- Letting the LLM produce client-visible text (that is layer 3's later, separate ADR).
- Judging template-assembled replies with faithfulness (a score without a referent).
- Deleting or bypassing the regex router (it is the floor, the parachute, and the shadow
  referee).
- Classifying a declared intent (a pressed button is an answer, not a hint).
- A confidence threshold or timeout chosen by feel (numbers come from the bench and are
  governed knobs).

## Slices (each = one green gate = one landing)

1. **This ADR**, validated by the operator. No code.
2. **The referent first**: labeled intent set ×3 languages + bench runner + the regex baseline
   measured and ratcheted. No LLM, no behaviour change — served answers are byte-identical.
3. **Layer 1 in shadow**: classifier behind the schema, async off the hot path, ledger
   telemetry, `understanding` declaration + ADR 0017 §Amendment 5 + conformance. Served
   routing still 100 % regex.
4. **Calibration and the switch**: threshold calibrated from shadow-phase bench runs, both
   knobs (mode, threshold) governed, flip on the operator's explicit go — on the numbers, read
   aloud.

Cockpit legibility for layer 1 (agreement, fallback counts, freshness on whatever surface
shows them) rides with slice 4 or a later slice, in screen language.

## Left open at implementation (named, not decided)

- Exact `understanding` field names on `AgentObservabilitySpec` (fixed by the §A5 text in
  slice 3).
- The timeout value (measured under the real backends, then governed).
- Set sizes per (language × intent) — bounded below by the "a rate needs an n" rule.
- Whether shadow classifies 100 % of turns or budget-bounded samples: start at 100 % (traffic
  is small and the ceiling already bounds spend); revisit only if the ledger shows the ceiling
  being reached.
