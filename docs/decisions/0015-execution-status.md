# ADR 0015 — execution status (autonomous run)

Single source of truth for **where the ADR 0015 implementation is**. The autonomous loop
(see ADR 0015 §Execution protocol) updates this file after every phase. A resuming session
reads this first, then continues the **next `pending` phase** — no re-work.

- **Protocol**: implement → full gate **twice green** + phase verification → commit + push
  (targeted staging, never `git add -A`) → update this file → auto-advance. No human gate.
- **Halt only** on: 3 failed repair attempts, a genuine external blocker (missing cred/infra),
  or an honesty conflict. Otherwise run A→F to completion.
- **Branch**: `feature/redesign` · **remote**: `origin/feature/redesign`.

## Phase ledger

| Phase | Scope (short) | Status | Commit | Notes |
|---|---|---|---|---|
| A | Scope object + registry + capabilities + snapshot endpoint + cache/single-flight (reads current stores) | ⬜ pending | — | kills the silent-ignore bug class; fast read model in place before any source swap |
| B | Complete stamping (EVAL_SCORE / GUARD_DECISIONS labels + span attrs + Langfuse scores) + Prometheus recording rules + "data available since" cutoff | ⬜ pending | — | |
| C | Read adapters (langfuse / prometheus / ledger) behind read(scope); aggregates→Prom, detail→Langfuse; shadow-run + parity per signal; contract tests; spine creds via Secret Manager | ⬜ pending | — | |
| D | Retire convenience jsonl (scores/bundles) after all signals flipped + baked; keep audit/S1 ledgers; erasure reaches spine + cache | ⬜ pending | — | |
| E | Four cards (traces / inbox / release / audit) + fixtures flagged synthetic / derived from spine | ⬜ pending | — | |
| F | Add language + model dimensions to Scope UI (no route sweep) — prove agent × time × language cube | ⬜ pending | — | |

Status legend: ⬜ pending · 🟡 in progress · ✅ done (twice-green + pushed) · ⛔ blocked (see notes).

## Log (newest first)

- _(seed)_ ADR 0015 written and pushed (Context → Decision → Architecture → Migration →
  Performance → Testing/migration/security → Execution protocol). Phase 1 per-agent wiring
  (transitional base) is live on the branch. **Next: Phase A.**
