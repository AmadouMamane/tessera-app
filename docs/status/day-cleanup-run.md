# Day cleanup run — 2026-07-12

Two deliberate cleanups, one branch and one merge each. Base: `origin/main` = `8a269a97`.

**CI is still billing-blocked**, so "CI is the second pass" does not hold. Each lot therefore
took **two consecutive full local `make gate` passes** — the only witness available.

| Lot | What | Hash |
|---|---|---|
| 1 | **P0.3 `sql-fstring`** — the class of interpolated SQL identifiers, closed | *this commit* |
| 2 | **A8** — ADR renumbering | **HALTED, not merged** — see below |

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

---

## Lot 2 — ADR renumbering: **HALTED, not merged**

The brief's own guardrail was *"HALT if a single reference is ambiguous — we do not guess in the
decision registry."* It was reached. The work is **stashed, not lost**
(`git stash list` → *"LOT2 adr-renumber — HALTED"*), and the adjudication — the expensive part —
is written up in **[`adr-renumber-evidence.md`](adr-renumber-evidence.md)**.

### What happened, in order

**The direction was wrong, and the operator changed it.** The brief kept `recouvrement` at 0010
because it is "the most referenced by the security work". True — but over the whole tree,
`frontier-observability` is referenced **183 times to recouvrement's 52**, it is the senior
(2026-06-08 vs 06-22), and `docs/decisions/README.md`'s own committed plan says the opposite.
Every rewrite is a chance to make the record lie, so the low-count sense should move. Asked;
operator inverted it. Final mapping in the evidence file.

**Then the automated pass produced a lie.** It rewrote, in `docs/production-posture.md`:

```
-  ## 4. The audit ledger (ADR 0015)
+  ## 4. The audit ledger (ADR 0022)
```

The audit ledger is the **spine's** subject. The pass saw the word *seal* nearby and re-pointed
a heading at the seal design note. That is a decision record asserting something false — which
this repo's own doctrine calls a **defect**, where a duplicate number is only an **annoyance**.

The root cause is worth keeping: **the seal was DECIDED in ADR 0015 (§Correction 3c, the spine)
and only DESIGNED in the annex.** So a bare `ADR 0015` beside the word "seal" means *the spine* —
the opposite of the obvious reading. `guard/seal.py`, `guard/audit.py`, `settings.py` are all
correct as they stand.

**And one reference cannot be resolved at all:**

```python
class SandboxDefaults:
    """Live defaults for the Console sandbox playground (ADR 0010 Phase C)."""
```

The *Console* is the cockpit (frontier). *Phase C* is recouvrement's phase letter. Nothing —
not the file, not the commit, not the dates — settles it. That is the HALT.

### Two findings that outlast the lot

**References wrap across lines.** `api/operator.py:77` and `lib/auth/roles.ts:70` end a line with
`ADR` and begin the next with `0010 Phase C`. No grep sees them, so **every count is an
undercount** — the index's "138", the audit's, and my own 245. A rename pass that verifies with
`grep` will report "0 remaining" while the record still lies. Same family as lot 1's discovery
that ruff's S608 cannot see an indented multi-line f-string: a syntactic check with a shape it
cannot see.

**The ADR bodies cross-reference each other.** `0009-dashboard-auth-rbac` and
`0013-entry-routing-by-audience` both cite `ADR 0010 Phase B/C` in their own text. Skipping
`docs/decisions/` — the natural instinct, since those are the files being renamed — leaves the
decision record contradicting itself.

### What is now known, and cheap

The evidence file carries the **structural discriminators**, which are strong and were not
obvious:

* frontier numbers its rollout **Phase 1..6** and its features by **canonical idea IDs**
  (`docs/observability-ideas.md`: *"Companion to ADR 0010 … the numbers are canonical IDs"*);
  recouvrement numbers its rollout **Phase A/B/C** and has no ideas. Disjoint by construction.
* **Creation dates settle the rest** — anything written before 2026-06-22 predates the second
  0008 and the second 0010 and is therefore unambiguous. Where dates collide, the origin commit
  does: `session.py:88`'s `(ADR 0008/0009)` was written by the commit that *created*
  `0008-agent-audience-and-surface.md`.

**And 0015 turns out to be free**: the seal annex is referenced **only by filename** — zero bare
references mean it. `0015 → 0022` is a rename plus five links, and shrinks the frozen set from
three to two on its own.

### Recommendation

Do them **separately, smallest first**: `0015` (provably safe, do it any time) → `0008` (75 refs,
the date test resolves nearly all) → `0010` (245+, wrapped refs, and needs a human ruling on
`SandboxDefaults` first). **`0010` should not be attempted while CI is down** — there is no
independent witness for a semantic rewrite of the project's memory.

The ratchet in `tests/unit/test_adr_hygiene.py` is unchanged and still freezes the three
collisions. It has not gone stale: nothing was renumbered.

---

## Lot 2 bis — the renumbering, reduced scope (2026-07-12)

The HALT above was right, and it made the retry cheap: the adjudication was already written, and
the one reference that stopped the first attempt turned out **not to be ambiguous at all**.

| | Move | Refs rewritten | What settled it |
|---|---|---|---|
| **0015** | `hica-seal-design-note` → **0022** | **0** bare + 6 filename links | The annex is referenced **only by filename** — the seal was *decided* in the spine (§Amendment 3 / §Correction 3c) and only *designed* in the annex |
| **0008** | `security-hardening` → **0020** | **25** | The **creation dates**: 2026-05-31 vs 2026-06-22 — a reference written before the cutoff can only mean the older ADR. Proof, not heuristic |
| **0010** | `recouvrement` → 0021 | — | **HELD FOR CI.** 245+ refs, some wrapped across lines. First live item waiting on CI's return |

### `spine/runtime.py` was a LIE, not an ambiguity — and that is a better outcome

The reference that halted the first attempt:

```python
class SandboxDefaults:
    """Live defaults for the Console sandbox playground (ADR 0010 Phase C)."""
```

`Phase C` exists only in the recouvrement ADR, where it names the **business** console
(`dedicated-ui`) — and **ADR 0013 forbids exactly this payload** (a system prompt, a guard-rule
count) on a business surface. The docstring cited the one decision record that rules its own
behaviour **out**. Not a stale number: a **false reference**.

Corrected to cite what actually governs the cockpit Console — **ADR 0019 §2 (increment I2)**, the
Console as a generated surface — plus the security seam's `sandbox_overrides_allowed` (overrides
honoured only for `COCKPIT_EMBEDDED` + `OPERATOR`). **Its own commit** (`11f4d3d8`): a lie being
corrected must not read as collateral of a rename, or the next reader cannot tell the two apart.

**The lesson generalises.** When a reference resists every discriminator, consider that it may be
*wrong* rather than *ambiguous*. A renumbering sweep is an unusually good detector of false
citations — it forces someone to read what each one actually claims.

### A fourth reference form, found here

ADR front-matter cites by **bare number with a gloss**, and never with the `ADR` prefix:

```
- Related: 0006 (locale-prefixed routing), 0008 (security hardening),
```

An `ADR\s*0008` sweep misses it entirely. The gloss makes each one self-disambiguating —
`0008 (security hardening)` moves, `0008 (audience/surface/auth)` stays — but only if you look for
the form at all. Three such references moved; three stayed.

### Verification

**Bidirectional**, because one direction proves nothing. Asserted, over the whole tree:

* no `ADR 0008` remains in a security-hardening context (**0 leaks**), and
* no `ADR 0020` appeared in an audience/surface context (**0 false moves**).

Plus: zero dangling filename links; the ratchet **mutation-tested both ways** — a new duplicate
fails it, and a stale entry left in the frozen set fails it too.

### The ratchet, re-frozen

`_FROZEN_COLLISIONS = {"0010"}`. Two of three dissolved. `0010` is documented **as debt waiting on
CI** — in the ratchet's own docstring, in `docs/decisions/README.md`, and in
`adr-renumber-evidence.md`. It is the **first live trigger** of the "CI is absent, therefore this
is forbidden" rule: rewriting the project's memory semantically, at 245+ references, with no
independent witness, is precisely what a bounded tolerance of a missing CI must refuse.

### Gate

Twice-green: two consecutive `make gate` at `EXIT=0` — 1741 backend tests, mypy 295 files, ruff,
biome, tsc, 185 frontend tests.
