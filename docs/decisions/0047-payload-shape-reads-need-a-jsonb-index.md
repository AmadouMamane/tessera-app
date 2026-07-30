# 0047 — The payload-shape reads are bounded by a jsonb index, not by a named filter

- Status: proposed
- Date: 2026-07-30
- Supersedes: none
- Superseded by: none
- Relates to: the read-budget ratchet (`tests/unit/test_ledger_read_budget.py`), [0011](0011-temporal-as-of-t-dimension.md) (as-of-T reads), [0015](0015-runtime-telemetry-spine-and-scope.md) (the telemetry spine that carries several of these reads)

## Context

The read-budget ratchet closed the class of unbounded whole-ledger reads: no NEW request path may
materialise the append-only ledger and filter it in Python, and the debt that predated the ratchet
is a number (`OWED_COUNT`) that may only go down. Five aggregate-shaped paths have since been pushed
into SQL — `count(*)` (system_profile), and `GROUP BY` + `count(*) FILTER (…)` over
`jsonb_array_elements(payload->'decisions')` (guard_explain, integrations, agent_garde_fous,
tool_validity). Each returns a handful of rows instead of the whole chain, was proven byte-identical
on the live ledger and a synthetic CTE, and lowered `OWED_COUNT`. It now stands at **10**.

**Those ten cannot be closed the same way, and this is not an oversight — it is a shape.** They do
not compute an aggregate; they return a *subset of payloads* selected by payload-shape predicates:

- `payload->>'target' = ?`, `payload->>'outcome' = ?`, `payload->>'actor_role' = ?`,
  `payload->>'scope' = ?`, `payload->>'policy_rule' = ?`, `payload->>'agent_id' = ?`,
  `payload->>'event_type' = ?`, and a free-text `q` substring over the payload.

The cardinality oracle that backs the ratchet (`tests/unit/_ledger_cardinality_fake.py`) judges a
bare `WHERE payload->>'x' = %s` as a **FULL read**, and it is right to: with no index on the jsonb
payload, Postgres must scan every row to evaluate the accessor. `read_ledger_entries(since=, until=)`
already bounds a read on the `occurred_at` **btree** index (a time window), and its own docstring
records the rest of the debt exactly:

> the eight payload-shape filters … still run in Python over the windowed rows, and therefore a SQL
> `LIMIT` cannot be pushed either — a `LIMIT 50` applied before those filters would return the wrong
> page, silently. Closing that needs the filters expressed over the jsonb payload (a GIN index); it
> is written up as an owed item rather than faked with a cap that reads like completeness.

The ten OWED paths are: `governance_feed`, `session_detail`, `conformance`, `etat_a_date`,
`policies`, `automations`, `automation_store`, `agent_lifecycle`,
`api/routes/observability/_common` and `observability/spine/adapters/current` (the last two share
the same cached-sync + Python-filter read of the guard-audit type, 94 % of the chain).

**Nothing about the current cockpit demands this.** The pages are already fast: head-keyed
incremental caches, per-worker memos, and the leader snapshot (ADR 0046) mask these reads in
practice. This ADR is **class-closure hardening for a ledger that will grow** (an append-only store
reaches 250 k rows), not a latency fix — which is precisely why it is *proposed*, not *accepted*: it
should be built when a measurement, or the row count, makes the debt felt, not before.

## Decision (proposed)

**Bound the payload-shape reads at the database with a jsonb index, express every active filter in
SQL, then push the `LIMIT` — turning "materialise all, filter in Python" into "the database returns
the page."** Concretely, when this is built:

1. **Index the payload.** Add an index on the ledger table's `payload` jsonb column. The default
   `jsonb_ops` GIN supports containment (`@>`) and existence (`?`); the equality filters above are
   the hot ones, so the plan is either:
   - rewrite each equality as **containment** — `payload @> '{"target":"user_input"}'` in place of
     `payload->>'target' = 'user_input'` — which a `jsonb_ops` GIN can use; **or**
   - add per-key **expression btree** indexes — `CREATE INDEX … ((payload->>'target'))` — for the
     handful of hot keys, leaving the accessor equality as written.

   The choice is a measurement (index size and write cost vs. the number of hot keys), not a
   preference, and it must be made against the real write pattern: this is the **hottest-written**
   table in the system (every guard decision appends), so index-maintenance-on-append and on-disk
   size are first-class costs to measure, not afterthoughts.

2. **Express the filters in SQL, completely, per path.** The `LIMIT` may be pushed **only** once
   *all* of a path's active filters live in SQL — a `LIMIT` above a residual Python filter returns
   the wrong page. So each path is converted whole or not at all.

3. **Add the seam, gated, byte-identical.** A new bounded reader in `ledger_store` (the sixth member
   of the family: `count_ledger_entries`, `guard_explain_scan`, `integrations_tool_scan`,
   `audit_rule_scan`, `tool_validity_scan`), postgres-only, with the flat-file source keeping the
   Python filter (no index there). Proven byte-identical on the live ledger and a synthetic CTE,
   exactly as the five landed conversions were.

4. **Teach the oracle what the index accelerates.** The ratchet's cardinality oracle currently
   calls *every* `payload->>'x' = %s` a full read — deliberately, because today none is indexed. The
   conversion must extend the oracle to recognise the specific indexed predicate shape as bounded
   (and nothing broader), then move the closed paths from `OWED` to a `file`-only capability and
   lower `OWED_COUNT`. Until the oracle can *see* the bound, it must keep reporting the read as full
   — a witness that cannot see may never report "ok" (ADR 0026).

## Consequences and traps

- **Write and storage cost on the busiest table.** A GIN index over a large jsonb column is not free
  to maintain on a high-append table, and it grows the on-disk footprint. This is the single fact
  that must be measured *first*; if it is prohibitive, the per-key expression-index route (index
  only the hot keys actually filtered on) is the fallback, and some cold keys may simply stay OWED.
- **Containment is not string equality in general.** `payload @> '{"target":"x"}'` is type-aware and
  path-aware; it matches `payload->>'target' = 'x'` for a scalar string at the top level, but the
  equivalence must be *reasoned and tested* per key (nested objects, arrays, and non-string JSON
  values differ), on the same byte-identical bar as every other conversion — never assumed because
  it "reads the same".
- **Free-text `q` needs a different index.** A jsonb containment GIN does not serve substring search;
  `q`-driven reads need a `pg_trgm` trigram (or full-text) index — a separate decision, a separate
  dependency, and a separate byte-identity argument. Paths whose only unbounded filter is `q` may
  remain OWED even after this, and that must be said plainly rather than papered over.
- **The as-of fail-open still applies.** Any path carrying an as-of cutoff must preserve
  `occurred_before`'s semantics as tool_validity did (parse `at` in Python so a malformed cutoff
  fails open; keep a null `occurred_at`; compare valid stamps as instants). A hard cast in the WHERE
  would turn a fail-open keep into a query error on a corrupt row.
- **A real migration.** The index is DDL on Cloud SQL and the local Postgres: idempotent, created
  `CONCURRENTLY` so it does not lock the append path, and asserted not to disturb the append-only
  trigger or the hash chain. `local`/`ci` and the file sink are unaffected.
- **Positioning.** An index is reuse of Postgres, not a new dependency — in keeping with
  "reuse, don't reinvent". A trigram index for `q` *is* a new capability (`pg_trgm`) and would need
  its own justification.
- **Acceptance criteria.** The chantier is done, per closed path, when: the SQL returns the same
  page as the Python filter byte-identical (live + synthetic CTE); the oracle recognises the bound;
  the path moves `OWED → file` and `OWED_COUNT` drops by one; and `EXPLAIN` shows the planner using
  the index (an index the planner ignores is not a bound — ADR 0026). Paths that cannot meet all
  four (notably `q`-only reads) stay named in the ratchet rather than force-closed.

## Status note

Not built. The five aggregate-shaped conversions are complete and the class is frozen against
regression; these ten are named, counted, and cannot multiply. This record exists so that whoever
picks the work up has the design, the traps (containment ≠ equality, `q` needs trigram, the LIMIT
ordering, the as-of fail-open), and the acceptance bar — and so that the decision to *defer* is
itself on the record, not a silent gap.
