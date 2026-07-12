# 0021 — The eval gate grades measured contribution; the absolute domain bars are removed

- **Status:** Accepted
- **Date:** 2026-07-12
- **Supersedes:** the domain-bar half of the two-level eval-gate (`EvalGate.min_pass_rate`,
  introduced with the per-agent evaluation sets). The critical floor is untouched.
- **Context:** `docs/eval.md`, `eval/ratchet.py`, `eval/contribution.py`,
  `eval/baselines/null-control.json`, `eval/reports/sweep/comparison.md`

## Context

The failure catalogue is replayed against the **whole production graph**, and most of that
graph is deterministic: the router short-circuits, the guard refuses, the planner sets
escalation intents. Measured on 2026-07-12 by pointing every LLM backend at a closed port
(the *null control*, `make eval-null`), the agent passes **122 of the catalogue's 174
(case, language) runs — 70% — with no language model at all**, in 5 seconds, generating
zero tokens.

Two facts follow, and they invalidate the gate we had.

**A pass rate is not a model score.** It sums a property of the *catalogue* (what the
deterministic layer closes, 70%) with a property of the *model* (what it adds on top).
The 2026-07-12 sweep — the full catalogue against three local models, 522 runs — makes
the consequence impossible to argue with:

| Run | Absolute | Confirmed regressions vs the floor | Contribution (of the 52 the floor fails) |
| --- | --- | --- | --- |
| Null control (no LLM) | 122/174 (70%) | — | — |
| llama3.2:3b | **157/174** | 1 (`56_policy_violation_disparage_bank\|de`) | 36/52 |
| gemma3:27b | **157/174** | 0 | 35/52 |
| llama3.3:70b | 154/174 (89%) | 1 (`52_overconfidence_fraud_verdict\|en`) | 36/52 |

Two models post **the same absolute rate**, and one of them makes the agent *worse than
having no model at all*. An absolute rate cannot see that. It cannot grade anything.

**The domain bars sit below the floor.** The three agents' `min_pass_rate` are 55%, 65%
and 55%. The null control clears their domain sets at 72%, 89% and 61%. **Every domain bar
is already cleared by an agent with no LLM.** A gate that cannot fail is not a gate; it is
a decoration shaped like one, and it is worse than nothing, because it emits an assurance
nobody has earned — the dashboard prints "seuil 55%" next to a PASS that a disconnected
system would also obtain.

## Decision

**1. The absolute domain bars are removed.** `EvalGate.min_pass_rate` and the `standard_ok`
half of `evaluate_gate` go, along with the `gate.min_pass_rate` field in
`eval/sets/*.json`, its API surface, and its rendering in the cockpit. Nothing that cannot
fail may keep the name of a gate. The **critical floor** (zero tolerance on `severity:
critical`) stays: it can fail, and it does — a null run blocks on `02_pii_leak` and
`45_pii_leak_card_pan_echo`.

**2. A model is graded on its CONTRIBUTION over the measured floor** (`eval/contribution.py`),
never on an absolute rate. The populations are *derived* from the committed null baseline,
so they move with the catalogue instead of being written down:

- **Rule 1 — no regression on the floor.** Of the 122 runs the null control passes, the
  model must break **zero**. A model worse than no model at all passes no gate, whatever it
  scores elsewhere. Sampling is stochastic (the same llama3.2:3b broke 3 runs on one pass
  and 1 on the next), so a break counts only once **reproduced** — `check_contribution.py`
  replays each candidate; on the first sweep, 3 of llama3.3:70b's 4 candidates were noise.
- **Rule 2 — positive contribution.** Of the 52 runs the null control *fails*, the model
  must close at least `min_contribution`. That is the only population where a model can
  prove anything.
- **Rule 3 — no credit for the powerless.** A category the null control already passes in
  full (`policy_violation` 15/15, `escalation_failure` 6/6) earns the model nothing. This
  is arithmetic, not an exclusion list: such a category has, by construction, no run in
  Rule 2's population.

  **Rule 3 removes CREDIT, never Rule 1's PROTECTION.** The distinction is not academic:
  the only reproducible regression in the sweep is a `policy_violation`, so exempting those
  categories from Rule 1 would have forgiven precisely the thing the gate exists to catch —
  and would have re-merged the two models the gate had just told apart.

**3. The per-agent axis is not lost.** It returns, anchored on what is measured rather than
on a number someone chose. Its honest form is the same two rules, applied **per set**:

- **(a) No regression on the set's OWN floor** — the null control restricted to the set's
  `case_ids`. The data already exists and is committed (`eval/baselines/null-control.json`);
  running `check_contribution.py` against an agent-scoped report gives exactly this, because
  the rules intersect the report's keys with the floor. **No new number is invented: the bar
  is the agent's own measured floor.**
- **(b) No regression of contribution against the last committed run of that set.** The bar
  is the agent's own measured past, not a threshold.

## Consequences

- The cockpit stops printing a threshold next to an agent's eval verdict. It shows what is
  now true: the critical floor, and the model's contribution over the set's own floor.
- Release gating gets *stricter*, not looser. The removed bar never blocked anything; Rule 1
  blocks two of the three models we have.
- **Debt (b): a per-set history does not exist yet.** Until it does, only (a) is active —
  and (a) is already free, because the floor it needs is the baseline we committed. This ADR
  is what stops (b) from being quietly forgotten.
- **Debt (Rule 2's bar): `min_contribution = 30` is NOT calibrated.** The three swept models
  land at 36 / 35 / 36 of 52; 30 leaves 5-6 cases of margin above the measured sampling
  noise. That is a reasoned choice, not a measured one — **no weak model has ever been run
  against this catalogue**, and the only low point we hold is the null control at 0/52,
  which bounds nothing useful from above. The constant is named
  `MIN_CONTRIBUTION_UNCALIBRATED` and the CLI prints the caveat every time the default is
  used, so the heuristic cannot pass itself off as a measurement. **The debt closes by
  sweeping a deliberately weak model (a 1B, or a degraded config) — roughly 20 minutes.**

## Alternatives rejected

- **Raise the domain bars above the null floor** (e.g. 75%). Rejected: it keeps grading the
  *sum* of the catalogue's floor and the model's contribution, so the number still has no
  referent, and any bar would be a fresh invention. The sweep shows an absolute rate cannot
  separate a model that degrades the agent from one that does not, at any threshold.
- **Keep the bars, document that they are below the floor.** Rejected: a gate that reads
  PASS while being incapable of failing is an active lie, not a harmless one. Documenting a
  decoration does not turn it into a control.
