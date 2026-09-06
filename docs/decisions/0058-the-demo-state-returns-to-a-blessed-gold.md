# 58. The demo state returns to a blessed gold

Date: 2026-09-06

## Status

Accepted.

## Context

The login gate is theatrical by design ([ADR 0009](0009-dashboard-auth-rbac.md), audit
F-9): the banner displays the demo credentials, and a visitor holding one of those accounts is
a real operator — `MUTATION_ROLES` admits every operator role, so visitors can propose a
release, flip a garde-fou, decide a curation, erase a synthetic conversation. That is the
demonstration working: every act is attributed and journaled (ADR 0024). But the repository is
about to be public, and a vandalized showcase stays vandalized until someone repairs it by
hand — with no reference to repair *to*.

The one thing a repair may never do is rewrite history. `seed_demo.py` is not this tool (it
seeds the retrieval corpus, nothing a visitor mutates). And a naive "restore everything"
would amputate `audit_spool.jsonl` and its sibling journals — manufacturing a past in the one
project whose thesis is that the journal is the witness.

The state layout makes an honest reset possible: every governed store is a file in the agent
state directory, and the design already separates state from history
(`operator_items_state.json` has its append-only twin `operator_items_transitions.jsonl`).

## Decision

**A blessed gold, a declared partition, a witnessed and journaled return** — implemented in
`scripts/demo_gold.py`, orchestrated by `make demo-gold-snapshot` / `demo-gold-verify` /
`demo-reset REASON=…`.

1. **The partition is declared file by file, in one place.** *Operational state* (returned to
   gold): garde-fous rule state, armed automation rules and approvals, curation decisions,
   incidents, inbox/à-faire item state, recouvrement cases, agent config, prompt-overlay
   proposals, knowledge source state, client space, console feedback, état-à-date snapshots,
   evidence packs. *Preserved* (never touched): the audit spool, every `*_transitions.jsonl` /
   `*_runs` / measurement journal, component phases, budget (money is history), infra liveness
   files, derived caches, and this tool's own journal. **A file the partition does not name is
   refused, never guessed** — and `tests/unit/test_demo_gold_partition.py` scans the code for
   state-file literals so a new store cannot ship unclassified.

2. **`snapshot` blesses.** The current operational files *and recorded absences* become gold,
   with a digest over the canonical manifest.

3. **`reset` is a governed act that proves its result.** It requires a declared `--reason`
   (ADR 0024 applies to resets too; the actor is the declared machine actor
   `demo-gold-reset`, never a default naming a person), restores gold, then **re-reads the
   state directory and compares digests** — the verdict comes from the thing, never from the
   intention (ADR 0026). Every invocation, refusals and failures included, appends one line
   to `demo_resets.jsonl` — append-only, like every other journal.

4. **The verdict is taken on a quiet tree.** The make recipes stop the agent before snapshot
   and reset and restart it after; `demo-gold-verify` reads the live tree and says so — a
   drift verdict there is a hint to re-check stopped, not a fact. `make` flattens exit codes
   (ADR 0051): call the script directly when the number matters (0 ok · 1 refused/drift ·
   2 cannot say).

5. **The banner declares the ephemerality before the gesture.** The login demo block says, in
   all three languages: visitor actions are ephemeral, the state returns to its reference,
   every act stays journaled. The theater stays honest.

## What this does not cover (named, not hidden)

* Surfaces folded from the guard ledger (a pending release request left by a visitor) are not
  files: they are handled through the governed path — decline them — never by editing state.
* Postgres is out of the gold on purpose: what is mutable there is subject data
  (conversations, memory — an erasure is an erasure, even of synthetic data), governed acts,
  or measurements. None of it may be rewritten by a reset.
* `eval_waivers.jsonl` is a journal and is preserved: a waiver a visitor added is revoked
  through the governed path, not amputated.
* Nothing schedules the reset. The cadence (nightly, or on observation) is an operator
  decision; the banner's "periodically" is honest for both. Wiring `demo_resets.jsonl` into
  the cockpit's audit surface is a follow-up.

## Consequences

Vandalism becomes one more line of history plus a clean state — both truths coexist. The
operator's reference acts live in the gold; visitor acts live in the journals forever,
attributed, as the living demonstration the theatrical gate was built for.
