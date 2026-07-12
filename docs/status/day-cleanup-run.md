# Day cleanup run — 2026-07-12

Two deliberate cleanups, one branch and one merge each. Base: `origin/main` = `8a269a97`.

**CI is still billing-blocked**, so "CI is the second pass" does not hold. Each lot therefore
took **two consecutive full local `make gate` passes** — the only witness available.

| Lot | What | Hash |
|---|---|---|
| 1 | **P0.3 `sql-fstring`** — the class of interpolated SQL identifiers, closed | *this commit* |
| 2 | **A8** — ADR renumbering: the three live collisions dissolved | *pending* |

---

## Lot 1 — the SQL f-string class

### What the brief assumed, and what was actually there

The brief said seven sites, all interpolating internal identifiers, no user input — close the
class with one shared `safe_identifier`. That was right about the *shape* of the fix and
understated the *size* of the problem. Three things came out of reading the tree:

**1. The site list was longer than the audit's, and the `# noqa` census does not find it.**
`retrieval/store.py` splices `postgres.vector_table` into `CREATE TABLE` / `INSERT` / `SELECT`
and carries **no `# noqa: S608` at all** — because **ruff never flagged it**. S608's heuristic
misses indented multi-line `f"""` blocks. So the module that is the *primary* consumer of the
one identifier a deployment can actually set from the environment
(`TESSERA_POSTGRES__VECTOR_TABLE`) was invisible to every count anyone had made, including the
audit's. `observability/eval/gating_scores.py` had the same shape, and was found by the ratchet
rather than by reading.

Counting suppressions counts the places someone already noticed. It cannot count the class.

**2. There were already two divergent private validators, and both had the same bug.**
`observability/agent_scope.py` allowed `^[a-z_][a-z0-9_]*$`; `spine/adapters/clickhouse.py`
allowed `^[A-Za-z_][A-Za-z0-9_]*$`. One rule, two spellings, neither reused, and the second
admitted names the first rejected. Both used **`re.match`**, which with a `$` anchor still
accepts a **trailing newline** — `"documents\n"` passed both. Narrow, and precisely the kind of
*almost*-a-name the check exists to reject. The shared gate uses `fullmatch`; a test pins the
old behaviour next to the new one so the difference is on the record.

**3. `psycopg.sql.Identifier` — the strictly better tool — was already in the codebase.**
`memory/` and `api/settings_store.py` compose their queries as
`sql.SQL("… FROM {table} …").format(table=sql.Identifier(t))`: the *driver* quotes the name, no
interpolation happens in Python, and **no suppression is needed**. The f-string modules are
simply the ones that did not follow the house idiom. See "what this lot did not do".

### The fix

`src/tessera/sql.py` — one gate, a peer of `authz.py` / `secrets.py`:

- `safe_identifier(name)` — `fullmatch` on `[A-Za-z_][A-Za-z0-9_]*`, bounded at 63 characters
  (Postgres' `NAMEDATALEN - 1`: a name Postgres would silently **truncate** is refused, because
  a silently *different* table is worse than a loud failure);
- `safe_qualified_identifier(name)` — `database.table`, each part validated. ClickHouse
  addresses tables that way, and loosening the bare check to allow a dot would have been the
  wrong move.

Routed **at both ends**, deliberately:

- **at ingestion** — `PostgresSettings.vector_table` gets a pydantic validator, and
  `ClickHouseConfig.__post_init__` uses the shared gate. An unsafe value cannot exist in the
  process; the deployment refuses to boot instead of building a query around it;
- **at every interpolation site** — 12 modules, including the two the audit did not list. One
  rule, no exceptions: *the value spliced into the query is the value proven safe.*

Belt and braces on purpose. The boundary check means a bad value never gets in; the per-site
check means a refactor that changes where a name comes from cannot silently un-validate it.
Neither alone survives a careless edit.

### The `# noqa: S608` could NOT be removed — and that is not a dodge

The brief asked for them to go, on the grounds that the safety is now real and the lint no
longer needs muzzling. **They cannot go.** S608 is a *syntactic* rule: it fires on any f-string
that looks like SQL and has no way to see that the value was validated on the line above.
Verified rather than assumed — one suppression removed, `ruff check` red:

```
src/tessera/guard/ledger_store.py:226:31: S608 Possible SQL injection vector through
string-based query construction
```

What changed is that every suppression is now **earned**: the identifier really is validated,
and the comment says so instead of asserting "it's a constant, trust me". Deleting them would
have turned the gate red and bought nothing.

### The ratchet, and the bug inside the ratchet

`tests/unit/test_sql_identifier_class.py` fails if a module splices an identifier into an
f-string without importing the gate.

**The first version of it was broken, in the same way as the thing it polices.** It grepped the
source and exempted any module mentioning `sql.Identifier` — because `memory/`'s safe
`sql.SQL("… FROM {table} …")` templates are *textually identical* to a dangerous f-string. That
module-level exemption **whitewashed `retrieval/store.py`**, which composes its *schema* the
safe way (line 93) and its *table* with a raw f-string. Mutation-tested by reverting `store.py`
to its pre-fix shape: the ratchet went **green**. A ratchet with a module-level escape hatch
polices nothing while reading green — which is the exact failure mode logged in the A7 lot.

Rewritten on the **AST**: it looks only at `ast.JoinedStr`. An f-string is a JoinedStr; a
`sql.SQL(...)` template is a plain `Constant`. Same text, different node, no exemption needed.
Re-mutated: `store.py` reverted → **red**, naming the file. And it catches the multi-line
`CREATE TABLE IF NOT EXISTS {table}` shape that ruff does not.

### What this lot did NOT do (P1, logged)

**Migrate the ~30 f-string Postgres queries to `psycopg.sql.SQL` / `sql.Identifier`.** That is
the real end state: the driver composes and quotes the name, and the 30-odd `# noqa: S608`
suppressions genuinely disappear rather than being justified. It is already the idiom in
`memory/` and `api/settings_store.py`, so this is not a new pattern to invent — it is a pattern
to finish applying.

It was not done here because it **rewrites thirty live queries**, and the tier that would prove
them (integration, real Postgres) is deselected from the gate. Doing it blind, with no CI, on
the same day as a class fix, would have been trading a proven improvement for an unproven one.
The ratchet accepts either form, so the migration can land incrementally without a flag day.

### Gate

Twice-green: two consecutive `make gate` at `EXIT=0` — ruff, `ruff format --check`, mypy
(295 files), **1741 backend tests**, biome, tsc, 185 frontend tests.
