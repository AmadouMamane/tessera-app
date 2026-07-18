# 0034 — The daily LLM budget ceiling is an operable, governed knob

Date: 2026-07-18
Status: accepted
Extends: 0030 (operable knobs carry a governed override), 0024 (author + reason), 0026 (a witness interrogates the thing)

## Context

Tessera has carried a cost tracker since the LLM layer was written
(`tessera.llm.budget`): every backend records real token counts, a real
indicative EUR price table converts them, the model catalogue displays the
running total. And its module docstring claimed *"The API layer queries it once
per request to enforce per-conversation caps"* — **which was false**: no caller
anywhere enforces anything. The tracker was a meter with no breaker, and the
docstring attested a control that did not exist. This ADR builds the breaker
and corrects the attestation (ADR 0026: a claim in prose needs an enforcer).

Two gaps:

1. The tracker accumulates **since first start** — there is no notion of a day,
   so "€/day" cannot even be asked.
2. There is no operable ceiling: stopping a runaway spend requires a redeploy.

## Decision

1. **Two new org-wide knobs in the ADR 0030 closed registry** (same store, same
   superadmin write path, same author+reason attribution, same journal):
   - `llm.budget.daily_eur` — the daily ceiling, a positive decimal, validated
     at write time (refused, never stored). No override = **no ceiling** — the
     historical truth, shown as such.
   - `llm.budget.overrun` — the declared behaviour at overrun: `block`
     (the turn is refused with an honest customer-facing message) or
     `local_fallback` (the turn is served by the frozen base model when that
     base is zero-cost). No override = `block`: a ceiling someone set means
     *stop spending*, and silently swapping models is the surprising choice.
   Validation becomes **per-knob-family** in `set_override` — the registry was
   implicitly chat-model-only; the dispatch makes each family's value space
   explicit.

2. **The tracker learns what a day is.** `BudgetTracker` keeps per-day counters
   (Europe/Paris calendar day) beside the cumulative ones, persisted in the
   same JSON, rolled automatically on the first record or read of a new day.
   `BudgetSnapshot` carries both; no historical series is invented — yesterday
   is gone, which the catalogue says plainly.

3. **The breaker sits at the routing seam** (chat.py, beside the model / the
   sampling / the style / the escalation bar), and it gates **paid models
   only** (`model_is_paid` — nonzero price in the real table). When the day's
   spend has reached the ceiling and the turn's effective model is paid:
   - `local_fallback` **and** the frozen base is zero-cost → the turn serves
     the base model (stamped `tessera.budget.overrun=local_fallback`);
   - otherwise → the router short-circuits the graph exactly like an
     injection block: no LLM call, a localized `budget_exceeded` message from
     the YAML bundles as the final response
     (stamped `tessera.budget.overrun=block`).
   A `local_fallback` whose base is itself paid (frontier deploy) degrades to
   `block` — falling back onto a paid model is not a fallback.

4. **Fail-open reads, fail-closed writes** (ADR 0030 invariant): a store error
   at the seam means no ceiling is applied — loudly — because the frozen
   deploy without this feature is the known-good state; a write that cannot
   validate is refused.

5. **Said where it lives.** The `/configurer/modeles` registry panel gains the
   two knobs (kind-aware controls: a numeric input, a closed select — never
   free text); the catalogue KPIs gain the **day's real spend** and the
   ceiling with its overrun behaviour ("aucun plafond" when unset). The
   turn span records the overrun decision.

## What this deliberately does NOT do

- No per-conversation caps, no per-agent budgets, no monthly windows — one
  org-wide daily breaker. Finer accounting is a later ADR if the need is real.
- No cost *forecasting*: the breaker compares the day's **recorded** spend to
  the ceiling before the turn; the turn that crosses the line still completes
  (its cost is recorded and gates the next one). A pre-turn estimate would be
  an invented number.
- The eval runner keeps its own budget file (`TESSERA_BUDGET_FILE`) and is
  not gated: offline evaluation must never be silently truncated by a prod
  knob; its spend is visible in its own reports.

## Consequences

- The false docstring in `tessera.llm.budget` is corrected to describe what
  is actually enforced, and the enforcement now exists and is tested at the
  seam, the router, the tracker and the validators.
- The `knob_keys()` frozen-registry test grows the two budget keys — the
  registry stays closed, just larger.
