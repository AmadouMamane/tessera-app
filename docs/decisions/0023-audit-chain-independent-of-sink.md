# 0023 — The audit chain is independent of the audit sink

- Status: accepted
- Date: 2026-07-12
- Deciders: Tessera maintainers
- Supersedes: none
- Related: 0015 (ledger opposability + Hica seal), 0020 (security hardening),
  `docs/status/audit-360-remediation-run.md` (F-6), `src/tessera/guard/audit.py`,
  `src/tessera/guard/ledger_store.py`

## Context

Tessera's central claim is opposability: every guard decision and business event lands in a
hash-chained, append-only, fork-proof ledger that a third party can verify (ADR 0015). That
claim is worth exactly as much as the guarantee that an entry *reaches* the chain.

The 2026-07-12 audit (F-6) found that it did not, under a supported configuration. The audit
emitter (`guard/audit.py`) has two orthogonal responsibilities that had become entangled in
one branch:

- **the sink** — where a *human-readable / observability copy* of an entry is written:
  `stdout` (dev), `cloud_logging` (documented as "used in staging and prod"), `file`, or
  `postgres`;
- **the ledger** — the *opposable store*: the promoted append-only Postgres table, fed by a
  durable fsync spool whose drain assigns the hash linkage under a `pg_advisory_xact_lock`
  (insert order = chain order, fork-free — ADR 0015 §Amendment 3).

The entanglement: the call that feeds the ledger (`enqueue_ledger_entry`) ran only inside
`if sink == "file"`. So with the baked default `TESSERA_LEDGER_SOURCE=postgres` **and** any
sink other than `file`:

- `cut = (ledger_source == postgres)` was true, so the in-process chaining branch was skipped
  (correct — post-cut the drain chains, not the emitter); **and**
- `sink != "file"`, so the spool was never fed.

The entry was written to `cloud_logging` (or `stdout`) and **never chained, never persisted to
the opposable ledger**. An operator following the documented staging configuration
(`audit_sink=cloud_logging`) turned opposability off without any signal that they had. And
`_emit_postgres` compounded it: a stub that silently fell back to `stdout`, so even choosing
the `postgres` sink explicitly persisted nothing to a table.

This is the same silent-degradation shape the project has fixed before — a missing secret that
opened a door instead of closing it (the bearer, ADR 0020; the default accounts, F-9). A
*transport* choice must never be able to disable a *store*.

## Decision

**The sink is a transport. The ledger is the chain. The two are independent, and the chain is
never a function of the sink.**

Three binding rules, implemented in `guard/audit.py`:

1. **Chaining and ledger persistence happen upstream of the sink, unconditionally.** Whether
   an entry is enqueued to the opposable ledger is decided *only* by whether the opposable
   chain is the canonical medium (`ledger_source == postgres` with dual-write on, or the
   pre-cut file mode where the flat file itself is the chain) — never by which sink carries
   the observability copy. Every sink now reaches the chain.

2. **A configuration that cannot persist the chain fails closed at boot, in an exposed
   posture, naming the culprit.** `validate_audit_chain_config()` runs at `build_app()`
   alongside the three existing fail-closed key checks (ADR 0020), and refuses to start a
   `staging`/`production` deployment whose `(audit_sink, ledger_source, dual_write)` triple
   cannot durably store the chain. The exemption is drawn exactly as narrowly as the bearer's
   — *not exposed*, not *not production* — so dev and CI keep their hermetic
   `TESSERA_LEDGER_DUAL_WRITE=0` loop. The refusal message names the offending settings and
   the fix.

3. **`_emit_postgres` never silently falls back to `stdout`.** The Postgres *persistence* is
   the ledger spool/drain, assigned upstream under the advisory lock; the `postgres` *sink* is
   therefore redundant when the ledger is active, and a no-op there — but if it is reached when
   the ledger is *not* persisting the entry, it raises loudly rather than pretending to write.
   Either the entry is stored (by the ledger, upstream) or the failure is audible.

### Why not "chain in-process for every sink"

Because that is precisely the fork bug ADR 0015 §Amendment 3 fixed: a per-process in-memory
head, extended by concurrent writers oblivious to each other, forks the chain. Post-cut the
drain is the *only* correct place to assign linkage. The fix routes every sink *to the drain*,
not *to a second in-process chainer*.

### Why fail-closed rather than "always force postgres"

Silently overriding an operator's `ledger_source=file` (the documented escape hatch until
`audit.log` is removed) would be its own hidden behaviour. The honest move is to refuse a
combination that cannot deliver the guarantee, and say why — the operator decides.

## Consequences

- An operator can no longer disable opposability by choosing a sink. `cloud_logging` in
  staging now carries the observability copy *and* the entry still lands, chained, in the
  ledger.
- A `staging`/`production` boot with an unchainable audit config refuses to start, exactly
  like a missing signing key. This is a new way for a misconfigured deploy to fail early —
  which is the point.
- Dev/CI are unchanged: `TESSERA_LEDGER_DUAL_WRITE=0` stays hermetic, and the check is inert
  outside exposed postures.
- A ratchet (`tests/unit/test_audit_chain_independent_of_sink.py`) asserts the invariant over
  **every** sink value: for each, an emitted entry is either enqueued to the ledger or the
  boot refuses the config — there is no third outcome, and the set of sinks is walked from the
  `Literal` type so a newly-added sink cannot skip the check.

### Out of scope (unchanged, deliberately)

The "Scellé · opposable" badge and the qualified-TSA question (ADR 0015 §Corr.3c / 0022) are
untouched. This ADR repairs the *mechanism* that makes an entry chainable; it does not
redefine the opposability *promise* or its external attestation.
