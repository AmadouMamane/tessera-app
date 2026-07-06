# Signal wiring reconciliation — Phase 3

**Purpose.** Phase 2 (`tests/unit/observability/test_wiring_*.py`, 90 tests) proved
every Table A/B/C signal in `docs/design/signal-wiring-map.md` empirically —
determinism + source-sensitivity at the *route's* seam. This document is the
durable record of what that proof found: which signals are demoted, which are
partial, which were rehabilitated, and — for every demotion — a **proposed**
route-level fix. **No fix in this document has been executed.** This is a
review-gated reconciliation pass only: it records verdicts and proposes
remediation, so a human decides what to schedule. `docs/signal-catalog.yaml`
and any external audit spreadsheet are untouched by this document.

**A note on what `status: active` means going forward.** The catalog's
`status` field tracks *"this UI widget exists and renders"* — it is not being
repurposed to mean *"this is wired."* A demoted signal keeps `status: active`
in the catalog (the widget still renders, it just renders a number that never
moves). The honesty truth for *wiring* lives here and in the per-signal
`synthetic` badge in `src/tessera/observability/spine/capabilities.py` (Phase
3.2) — the same mechanism already used for `assistant`, `incidents`,
`curation`, etc. A dead signal must never be displayed as if it were a live
measurement; the badge is what prevents that, not the catalog `status` field.

---

## 1 — Demotions (proven DEAD; `status: active` today, should read as fixture)

| id | key | verdict | root cause (file:line) | proposed fix (NOT executed) |
|---|---|---|---|---|
| **64** | embedding-version-skew | **DEAD** (Phase 1) | `src/tessera/api/routes/observability.py` ~L2447-2452 builds `query` from the configured embedder, then sets `corpus = query` — an alias, not a read of the actual corpus embedder. `embedding_skew.py:detect_skew` itself is fine (Phase 1 proved the pure function moves when genuinely given a different corpus fingerprint). | Route should read the corpus's *actual* last-used embedder fingerprint (model id + dimension) from wherever the retrieval pipeline records it — e.g. a small durable record written by `retrieval/embeddings.py` at ingestion time — instead of aliasing the query's fingerprint. Until that record exists, `skew` cannot be computed honestly. |
| **134** | ai-act-disclosure-ux | **DEAD** (Phase 1) | `src/tessera/observability/disclosure.py`: `disclosure_status()` returns a hardcoded module constant (`DISCLOSURE_TEXT`) and a literal `enabled=True`; the route passes no runtime source at all. | `enabled` should read an actual per-locale/per-deployment disclosure-toggle (e.g. a config flag or a DB row set when the AI-disclosure banner is actually shown to a user), not a Python literal. Until that toggle exists, `enabled` cannot reflect reality — it can only ever read `True`. |
| **73** | embedding-inversion-risk | **DEAD-real-path** (Phase 2, corrected from an earlier mis-classification as fixed-corpus-probe) | `src/tessera/api/routes/observability.py` ~L2088-2105 calls `assess_inversion_risk(DEMO_MEMORIES, DEMO_PROBES, embedder=embed)` — both arguments are Python constants hardcoded in the route (named `DEMO_*`, never sourced from a file/store), and the result is memoised once per process (`_inversion_cache`). The route has never read the real memory store. `embedding_inversion.py:assess_inversion_risk` itself is fine (Phase 2's causal-proof leg shows it reacts correctly to genuinely different memories). | Route should read a real sample of stored memories (via the memory backend's persistent tier, `src/tessera/memory/persistent.py` per ADR 0007) instead of `DEMO_MEMORIES`, and either drop the process-level cache or scope it per-scan rather than globally, so repeated calls reflect the current store instead of the first call ever made. |

**Note on classification.** #73 was initially (first Phase 2 pass) filed as
Table C's weakest `fixed-corpus-probe` member, because a "reactive" probe
edited `DEMO_MEMORIES` directly and observed `recovery_rate` move, which was
read as "wired to a corpus." That reasoning does not hold: editing a
route-hardcoded Python literal to make an observable move proves nothing about
wiring — the same trick would make `disclosure.py`'s `enabled=True` literal
look "reactive" if you edited *that* constant directly. A genuine
fixed-corpus-probe (e.g. #13 firewall-roc, #123 failure-clustering) is driven
by a real *external* file — a policy, a gold set, a catalogue — not by a
constant baked into the route's own source. #73 has no such external source,
so it is corrected here to a third demotion, proven the same way as #64/#134:
perturb the real thing it's supposed to measure (the memory store), show no
movement, and separately show the pure aggregator is not the bug.

---

## 2 — Partial signals (proven WIRED, with a documented, empirically-verified floor)

| id | key | verdict | what's pinned | proposed fix (NOT executed) |
|---|---|---|---|---|
| **76** | ai-act-compliance | **WIRED, partial (floor 4/5)** | `src/tessera/api/routes/observability.py` ~L2344-2350 hardcodes `disclosure_enabled=True`, `escalation_available=True`, `data_governance_enabled=True` as route literals; `ai_act.py:assess_compliance` additionally hardcodes the Annex III obligation's `satisfied=True` internally. Only `audit_chain_verified` (from the real `verify_active_ledger()`) is a mobile input — Phase 2 proved this empirically with two dedicated adversarial probes, not just the map's footnote taken on faith. | `disclosure_enabled` should read the same real toggle proposed for #134 above (once it exists, these two fixes compose). `escalation_available` should check whether the escalation worker/tool is actually registered and reachable. `data_governance_enabled` should derive from the real GDPR erasure/consent signals (#180 `gdpr-erasure-telemetry`, #36 `consent-governance-ops` — both proven WIRED in Phase 2). Annex III's `satisfied` should be computed from the deployment's actual high-risk-use-case criteria instead of hardcoded inside the aggregator. |
| **124** | telemetry-to-roadmap | **WIRED overall; one sub-path DEAD** | The main signal (`n_items`) is genuinely wired — Phase 2 proved it moves with low-faithfulness turns. But the route never sets `RoadmapSignals.n_coverage_gaps`, so the `coverage_gap` roadmap item can never appear. Phase 2's causal proof confirms `build_roadmap` (the pure function) does surface a `coverage_gap` item when the field is set directly — the omission is entirely at the route. | Route should compute an actual coverage-gap count (e.g. aggregate #28 `corpus-coverage-gaps`' `covered=False` verdicts over the scoring window) and pass it as `RoadmapSignals(n_coverage_gaps=...)`. Until then, the `coverage_gap` roadmap item is dead weight — it is declared but structurally unreachable. |

**Why #124 gets no `capabilities.py` badge.** The `synthetic` flag is declared
*per signal id*, not per sub-item within a signal's payload — there is no
`roadmap` capability entry, and adding a whole-signal `synthetic=True` would
be dishonest in the other direction (`n_items` is real). The badge mechanism
cannot express "this signal is real except for one of its list items," so the
`coverage_gap` dead sub-path stays documented here and in code comments
(`roadmap.py` / the route), not in the spine.

---

## 3 — Rehabilitations (the original plan mis-identified these as fixtures; Phase 0/2 prove them real)

| id | key | what the plan claimed | what Phase 2 proved |
|---|---|---|---|
| **16** | shadow-traffic | Negative-control fixture candidate | **WIRED.** `shadow.py:run_shadow` replays real captured bundles through the real replay/eval path (`POST /observability/shadow`, `routes/observability.py:489-494`); `n_compared` moves when a new bundle is captured. **No capability entry currently references this endpoint at all** — it is neither mis-flagged nor positively badged. Two *different*, similarly-named entries must not be confused with it: `shadow_traffic` (synthetic — an unrelated, unimplemented "fleet-wide mirroring" tile) and `replay_shadow` (not synthetic — but this one backs a third, different endpoint, `GET /observability/replay-shadow` → `replay_shadow_mod.compute_replay_shadow_overview`, a replay-comparisons overview). Confirmed by direct route/capability cross-reference, not by name similarity. |
| **172** | siem-integration | Negative-control fixture candidate | **WIRED.** `siem.py:to_siem_events` maps real ledger deny/transform rows to SIEM-formatted events (`GET /observability/siem`, `routes/observability.py:2281-2284`); `n_events` moves with a live guard deny. **No capability entry currently references this endpoint either.** Do not confuse it with `evidence_export` (synthetic — a *different*, unimplemented evidence-pack export/SIEM-destination subsystem, not this event-mapping function). |

**On badging #16/#172 as positively "real":** unlike the three demotions in
Section 1, there is nothing to *correct* here — no existing flag mis-badges
either signal as synthetic. Adding a new, explicitly non-synthetic capability
entry for each is possible but optional (a presentation nicety, not a
correctness fix); left undone in this pass since it wasn't the ask.

---

## 4 — Scope and non-goals of this pass

- **No route-level behavior changes are made here.** Every "proposed fix" above is
  advisory, for a future, separately-reviewed batch.
- **`docs/signal-catalog.yaml` is not edited.** `status: active` stays as-is for
  every signal above — see the note in the Purpose section on what `status`
  means going forward.
- **No external audit spreadsheet is touched.**
- **Phase 3.2** (a separate, immediately-following change in this same review)
  badges the three Section 1 demotions — and, if it renders as its own UI
  element, the `coverage_gap` sub-item of #124 — as `synthetic` in
  `capabilities.py`, so the cockpit never presents them as live measurements.
  That is a **presentation-honesty fix**, not a behavior fix: it changes what
  badge a human sees, not what the route computes.
