# 0041 — Customer satisfaction is a captured signal, never a proxy

Date: 2026-07-19
Status: accepted
Extends: 0040 (the transcript is the single witness of turns), 0026 (a witness interrogates the thing), 0008 (customer-plane auth), 0009 (the public aggregate surface)

## Context

The agent Synthèse's "Satisfaction moyenne" KPI read "CSAT non instrumenté" — an
honest empty state, because no customer-satisfaction signal was captured anywhere.
The audit for ADR 0040 confirmed there was no honest way to fill it from existing
data: the operator Console thumbs (`console_feedback`) are *operator* feedback, not
the customer's, and are not attributed per agent; the online-eval faithfulness
scores are real and agent-scoped but the Synthèse page's own contract bars eval
signals from it (the AT-01 trap, `agent_synthese.py` header). A real CSAT needs a
real **customer** signal — so we capture one, rather than relabel a proxy.

## Decision

**Customer satisfaction is a first-class captured signal: a 👍/👎 the customer
leaves on an assistant reply, stored durably, attributed to the agent that handled
the turn, and excluded when the turn was a test — the same real-traffic rule as the
transcript (ADR 0040). It is never inferred from another signal.**

1. **A durable, agent-attributed store.** `customer_feedback` (Postgres):
   `conversation_id`, `turn_id`, `agent_id`, `rating` (`up`/`down`), `synthetic`,
   `created_at`, one row per rated turn (a re-vote UPDATEs). The `agent_id` and
   `synthetic` are **inherited from the rated turn** (resolved from the transcript by
   `turn_agent_and_synthetic`), so a vote is attributed to the agent that actually
   answered and a vote on an operator TEST turn is itself excluded. Unlike the
   operator `console_feedback` JSON toggle, this is windowable and per-agent — the
   shape the Synthèse needs.

2. **A customer-plane, self-authenticating endpoint.** `POST /observability/customer-feedback`
   is bearer-less and takes no operator assertion (the customer is anonymous, a
   legitimate auth state — ADR 0008). It binds the write to a conversation with the
   signed **resume capability** the browser already holds from `turn.start`
   (`verify_resume_token`, the same gate as `GET /session/transcript`, audit P1 F-4),
   so nobody can rate an arbitrary conversation. It names **no author** and writes
   **no governance ledger entry** — it is customer telemetry, not a governed operator
   act (audit P0 F-1). It is declared in `test_mutation_routes_carry_auth`'s
   `SELF_AUTHENTICATING` set (the only ratchet a bearer-less customer POST touches),
   mounted off the `mutations` router and outside the governed prefixes.

3. **A real KPI, still honest when empty.** The Synthèse reads
   `count(rating='up') / count(*)` over `customer_feedback` for the agent, windowed
   and `NOT synthetic` (`_fetch_csat`), and renders "—" until a customer has actually
   voted. Both formerly-empty cells now have a real source (users via ADR 0040, CSAT
   via this ADR) and both still show an honest empty state rather than a fabricated
   number. The cell also carries a MetricInfo (what/how/source) so a small-but-real
   rate is not mistaken for a bug.

## Consequences

- The Synthèse's "Satisfaction moyenne" becomes a real customer-satisfaction rate
  once customers vote — a genuine signal, not a relabelled eval score.
- The widget lives on the **customer** chat only (`MessageBubble`, gated to the
  non-operator surface); the recouvrement operator console does not show it, and its
  CSAT stays honestly empty until a real customer signal exists there.
- The `customer_feedback` table joins the boot-time `ensure_*_schema` sweep, via the
  same idempotent DDL idiom (no migration tool).
- CSAT remains **opt-in by the customer**: no vote, no number. Silence is honest
  emptiness, never assumed satisfaction.
