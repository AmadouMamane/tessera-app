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

---

## Amendment 1 (2026-08-04) — the ceiling is asked by everything that spends, not only by `/chat`

**What was true until this date.** `POST /chat` resolved the policy and refused or degraded.
Nothing else did. Ten modules were frozen in `tests/unit/test_llm_paths_outside_the_ceiling.py`
as spending without ever asking — the summariser, the reflector, the corpus translator, the
judge and five observability probes. The breaker therefore bounded the *user-facing* turn and
nothing else, which is backwards: a probe replays a whole catalogue, and the user asks one
question.

**Nine were wired; the tenth was never a debt.** `observability/agent_configurations.py`
obtains a backend to read `backend.name` and the sampling it declares, and never calls it. The
detector counts *"names an LLM factory"*, not *"spends"*. It is now exempt by name and with
its reason, alongside `agent/reporter.py` — never by a pattern, because a rule broad enough to
excuse a descriptive read would excuse a spending one with it.

**The sync/async bridge the debt predicted was not needed**, and why is worth recording: nine
of the ten *obtain* their backend inside an `async` function. Only `eval/judge` obtains it in a
sync `__init__` — but it only *spends* in `score()`, which is `async`. The question to ask of a
spending path is where the money leaves, not where the client is built.

### The rule lives in one place

`tessera.llm.ceiling.resolve_spend_model(caller=…, model=…)` applies **the same** rule the
chat route applies, deliberately, so "over the ceiling" cannot come to mean two things. It
returns the model to actually use, or raises `DailyCeilingReachedError`. It fails open in the
same two ways: no stored ceiling (or an unreadable store) means no ceiling, and an unpriced
model is never gated.

**What is cached and what is not.** The policy is a Postgres read, cached for 30 s and
invalidated by the **override store** on every write — placed there rather than in the two
route handlers, because a third writer added later would otherwise leave an operator's new
ceiling unenforced for a TTL with nobody noticing. **The spend is never cached**: caching the
crossing would let a probe keep spending for a whole TTL after the breaker tripped.

### A refusal must read as a refusal

One exception handler answers **402 Payment Required** with the ceiling, the day's spend and
the `caller` that was refused. Not 503 — nothing is unavailable. Not 429 — nothing is
rate-limited. And above all not 200 with an empty report: six probes returning six shapes of
"no results" is precisely how a refusal comes to look like a measurement (ADR 0026).

**The two memory paths do the opposite, on purpose.** They run *after* the turn has been
answered, so raising there would turn a budget cap into an outage. They degrade and say so on
stderr — and `memory/summary` keeps the **previous** fold rather than saving an empty one:
writing an empty summary would discard everything older than the window, so a ceiling would
*delete* memory instead of declining to extend it.
