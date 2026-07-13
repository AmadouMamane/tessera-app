# Perf run — the control plane observes itself, then treats itself

**Branch** `claude/fleet-perf-spans`, cut from `main` @ `2ed0920a`. Twice-green
(`make gate-twice`, one tree, machine-asserted). Measured on the real local ledger:
**25 716 entries**.

Previous lot (landed, `f2a7d3ee`): the integrity badge stopped re-hashing the chain on every
request — `/audit/integrity` 1 063 → 22 ms. This lot is the other half: the fleet.

---

## The numbers

Measured on a backend running the actual code of the branch (five passes, p50), against the real
ledger.

| | before | after | |
|---|---:|---:|---|
| `GET /observability/fleet` | **3 938 ms** | **430 ms** | **×9.2** |
| `GET /observability/chrome` — the header of **all 32 pages** | **3 725 ms** | **714 ms** | ×5.2 |
| `GET /healthz` **while one fleet request is in flight** | **3 639 ms** | **5 ms** | **×728** |
| `GET /healthz` at rest (the witness) | 2 ms | 2 ms | — |
| `GET /audit/integrity` (previous lot) | 34 ms | 20 ms | — |

The third row is the one that matters most and it was not in the diagnosis. A `/healthz` costing
2 ms at rest took **3.6 seconds** while a single fleet request was running: the reads were
synchronous inside an `async` route, so the event loop froze and **the whole server stopped**.
That is why the operator's `/audit/integrity` was erratic (1 169 → 7 270 ms) even though the
endpoint itself was already fixed — it was queued behind the browser's own polling. **Cost and
blocking are two different bugs, and making the reads cheap fixes only the first.**

### The trace cascade — the proof that the instrumentation earns its keep

```
BEFORE                                        AFTER
GET /observability/fleet   3 980 ms           GET /observability/fleet   436 ms
  (1 span · 0 children)                         ├─ conversation_messages.fleet_rollup  28 ms      3 rows
                                                ├─ audit_ledger.handoff_counts         19 ms      1 row
  Not one millisecond                           ├─ prometheus.instant                   4 ms      0 rows
  attributed to anything.                       ├─ audit_ledger.latest_of_type_by_agent 18 ms      1 row
                                                ├─ audit_ledger.length                  4 ms      1 row
                                                ├─ audit_ledger.rows_above              1 ms      0 rows
                                                ├─ … 26 more, all named
                                                ╰─ 588 rows materialised (was ~206 000)
```

**Ledger rows materialised per fleet request: ~206 000 → 3.**

Before: one full read for the integrity dot, one per agent for the canary verdicts (× 6), one for
the handoff counts. **Eight full reads of 25 716 rows, per request.** The original diagnosis said
six; it was eight.

---

## What was done

**Step 1 — instrument, before correcting.** Every control-plane store read now emits a span
carrying the store, the operation, the duration and — the field that carries the finding — **the
number of rows it materialised**. `tessera/observability/store_spans.py`. It counts rows
*materialised*, never rows *scanned*: an aggregate that groups 29 600 rows in the database and
returns 29 is the fix, and must not read as the offence.

**Step 2 — the fix.**

| was | is |
|---|---|
| `latest_canary_verdict(agent)` → load all 25 716 payloads, scan in Python. **Per agent.** | one indexed row (`(payload->>'type', payload->>'agent_id', seq DESC)`). Index Scan, **0.546 ms**. And `latest_canary_verdicts()` answers the whole fleet in **one** `DISTINCT ON`. |
| `_handoff_counts()` → read every entry to count a few dozen | `GROUP BY` in SQL |
| `_integrity_broken()` → `active_ledger_opposability()`: a full re-hash of the chain **plus** a third-party seal evaluation, of which the fleet used one boolean | `active_ledger_verdict()` — incremental, and it publishes *when the chain was last walked in full* |
| every read synchronous, inside an `async` route | `asyncio.to_thread` + `gather` — off the loop, and concurrently |

**The strong verifiers were deliberately left alone.** `verify_active_ledger` and
`active_ledger_tree_status` still walk the whole chain every time, and `active_ledger_opposability`
(the État à date verdict) still re-reads and re-hashes all 25 716 rows. That is not an oversight:
those produce the claim the product **asserts to a regulator**, and an assertion of that weight
re-reads what it asserts about. Six existing tests failed when a first draft routed them through
the checkpoint, and they were right to: `verify_active_ledger` returns a `ChainStatus` with **no
provenance**, so backing it silently with a cached proof would be "a checkpoint trusted in
silence" — which the checkpoint module's own docstring forbids. What was wrong was never those
functions; it was **the health dot and the header bell calling them** to extract one boolean.
A health dot asks a weaker question — *"is there a proven break?"* — and may pay a weaker price,
provided it says so. `active_ledger_verdict` hands back the age of the last full walk, unasked.

**Step 3 — the ratchet** (`tests/unit/test_ledger_read_budget.py`), on two levels:

* **A row budget.** The fixed request paths are driven against a 5 000-entry fake ledger and every
  read is counted through the real instrumentation. More than 100 rows in a single read → red.
  Mutation-tested: re-introducing the old full scan turns it red on both the fleet **and** the
  header bell; removing the mutation turns it green again.
* **A freeze.** The set of modules that *can* materialise an unbounded slice of the ledger is
  pinned by exact-set equality (AST). A new one cannot appear. Mutation-tested with a seventh
  reader: refused by name.

---

## What I refused to claim

**The `of_type('tessera.guard.audit')` change is a shape fix, not a cost fix.** Pushing the type
filter into SQL *reads* like a correction in the diff. It is not: `tessera.guard.audit` is
**24 250 of 25 716 rows — 94.3 %** of the chain (measured). It saves ~6 % and still hands the
caller the whole ledger. Both call sites stay on the owed list, and the comments say so.

The consequence is the ratchet's design rule: **`load_ledger_payloads_of_type` is not a bounded
reader.** It is bounded only when the type is *rare*, and the type the cockpit reads most is the
ledger. A ratchet keyed on the function *name* would have certified a full scan. **The row count
judges; the name never does.**

**The class is not closed everywhere, and I will not say it is.** What is true: no *new*
full-ledger read can appear, the fleet and the header no longer perform one, and **17 request
paths still do** — named, counted, and frozen in `_UNBOUNDED_CAPABLE`. The number is asserted in
CI so the debt is a figure that must be lowered, not a sentence in a document nobody re-reads.

---

## What the instrumentation found that nobody had asked for

This is the point of doing step 1 first. Each of these is a *measurement*, not a hypothesis.

1. **`/observability/chrome` — 3 725 ms, on every one of the 32 cockpit pages.** It was not in the
   diagnosis. The header's canary bell asked the ledger once *per agent*, and its integrity bell
   called the full opposability verdict. Now 714 ms.

2. **A full ledger read still survives on the chrome path** — `store.read audit_ledger.payloads_all
   · 361 ms · 25 716 rows`, from `incidents.open_incidents()`. Without the cascade I would have
   shipped chrome at 714 ms believing it clean. `incidents.py` already computes a 7-day window and
   then throws it away, filtering in Python. **A window would only halve it** (13 017 rows fall
   inside 7 days — 50.6 % of the chain), and there are **11 329 deny decisions** in that window, so
   the real fix is to push the per-day and per-rule counts into SQL. That is a lot, not an
   afterthought, and it is **not** what I did here.

3. **The same class, a third time, outside the ledger.** `operator_items.load` runs **once per
   agent** in the fleet (18, 121, 21, 91, 83, 80 ms — three of them returning *zero* rows), because
   `load_eval_snapshot(agent_id)` **parses every eval report in `eval/reports/` and filters by agent
   in Python**. Six agents, six full parses of the same files. It is now the dominant remaining cost
   of `/observability/fleet` and it is the next lot.

4. **The reference dev server was serving stale code.** It started 2026-07-12 at 23:56, *before*
   the integrity fix landed (2026-07-13, 08:32). `make dev-status` reports the git head of the
   **checkout**, not the code the **process** loaded — and the two had diverged. The operator's
   browser was still paying 1 087 ms for a badge that costs 20 ms on this branch. **A restart
   activates it.** (Confirmed by two independent witnesses: the process start time, and the
   latency itself matching the pre-fix number exactly.)

5. **A false green inside my own ratchet.** `ledger_checkpoint.py` does `from ... import
   _connect_sync`, which **copies the name** — so patching `ledger_store._connect_sync` left the
   checkpoint pointing at the *real* database. On this machine, where Postgres is up, the budget
   test measured the **production ledger** and passed for the wrong reason; on a machine without
   Postgres it would have exploded. The cold-checkpoint test caught it. A budget that silently
   reads production is not a budget.

---

## Owed, in order

1. **`incidents.open_incidents()`** — 25 716 rows on the header of every page. Push the day/rule
   counts into SQL. (~361 ms of chrome's 714.)
2. **`load_eval_snapshot(agent_id)`** — parses every eval report, once per agent. (~the dominant
   remaining cost of the fleet.)
3. **The 17 frozen offenders** — each answers a filtered question by reading the whole chain.
   `read_ledger_entries(since=…, until=…)` already exists and is already indexed; most of them
   only need to use it.
