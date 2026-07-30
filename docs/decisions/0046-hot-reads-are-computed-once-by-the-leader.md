# 0046 — The hottest cockpit reads are computed once by the leader, shared by all workers

- Status: accepted
- Date: 2026-07-29
- Supersedes: none
- Superseded by: none
- Relates to: [0044](0044-the-agent-runs-as-many-processes.md) (multi-process agent, leader election), [0045](0045-full-local-co-locates-the-front-with-the-agent.md) (full-local co-location)

## Context

ADR 0044 made the agent run as N uvicorn workers to break the GIL ceiling. Each worker holds its
own in-process memo for the heavy observability reads (chrome, fleet, timeline, the ledger
payloads). That per-worker cache is correct but has a cost the single-process design did not:

- **Scatter.** A cockpit page fires ~14 read requests at once. The BFF's connections round-robin
  across the N workers, so a single user's burst lands on workers whose memo is cold or expired.
  With a 3 s TTL and 4 workers, a browsing user rarely hits a warm one for every card.
- **Concurrent recompute storms.** When the memo expires, several workers recompute the SAME
  payload simultaneously — and the heaviest reads (chrome fans out over its own 6-thread pool,
  fleet aggregates the whole fleet) contend on each worker's GIL with the other 13 requests in the
  same burst. Measured live (full-local, 4 workers): chrome and fleet each inflated to ~2.4 s
  under the concurrent burst although each is ~6 ms warm in isolation.

The per-endpoint fixes that preceded this ADR (ai-act checkpoint verdict, guard-audit read from
the cached whole-ledger read, the boot warmer, the incidents memo) made every read fast *warm and
in isolation*. What remained was structural: the same payload, recomputed independently by N
workers, on the request path, under concurrency.

## Decision

The hottest cockpit reads are **computed once, by the leader, off the request path, and shared with
every worker through a single file snapshot.**

- The leader (the worker that won the ADR 0044 advisory lock) runs one background loop that
  periodically computes the default-locale hot reads (chrome per locale; the fleet rollup for the
  default period) and atomically writes them as ONE JSON document to the shared state dir
  (`state_dir/read_snapshot.json`). The state dir is already the durable sink and is a shared bind
  mount across all workers, so no new transport and **no new dependency** is introduced — the
  substrate is the filesystem the agent already uses, and `atomic_write_text` (ADR 0044) already
  gives crash-safe, torn-write-free publication.
- Every worker's read endpoint, on the LIVE path, reads the snapshot first: a fresh entry is
  returned as-is (a ~ms file read + JSON parse), and only a **miss** — no snapshot yet (leader not
  up), a stale one (leader fell behind its own freshness budget), an unreadable one, or a
  non-precomputed argument combination (a non-default locale/period, an as-of-T read) — falls
  through to the pre-existing in-process memo and compute. The fallback is why this is purely
  additive: correctness never depends on the snapshot existing.

Freshness is the leader's loop interval; the worker's staleness bound is a small multiple of it, so
a single missed cycle does not blank the cards — it serves the last snapshot until it ages out,
then computes. This is the same freshness contract the 3 s memo already offered, now honoured once
instead of N times.

Why the leader, not lazy write-through: a lazy shared memo (any worker computes on miss, writes the
file) still recomputes on the request path the first time after each expiry, and under the
concurrent burst several workers race to do it — the exact contention this ADR removes. Computing
in the leader's background loop takes the heavy compute off every request path entirely.

Why file, not Redis: `tessera-redis` exists but is not wired into the agent, and adding it to the
read hot path is a new dependency and a new failure mode that Tessera's positioning
("reuse, don't reinvent; minimal, well-cited dependencies") asks us to justify — and the shared
bind-mounted state dir already does the job. If a future deployment splits workers across hosts
(no shared filesystem), the snapshot's read/write seam is where a Redis backend would slot in.

## Consequences

- The hottest reads stop scattering and stop storming: the leader computes each once per interval;
  workers read a file. chrome/fleet leave the request path's contention budget.
- One more leader-only background loop (ADR 0044 already gates loops to the leader; per-worker
  concerns like the boot warmer stay per-worker). Its cost is bounded and off every request path.
- A new shared artifact (`read_snapshot.json`) in the state dir. It is a CACHE, never a source of
  truth: it is derived, best-effort, and every reader degrades to computing when it is absent or
  stale. It carries only public-aggregate reads — never subject-scoped or PII surfaces.
- Scope of this first increment: chrome (all locales) and the fleet rollup for the default period.
  Timeline and the ai-act/guard-audit reads are already served fast by their own persistent
  incremental caches + the boot warmer, so they stay as they are; they can be added to the snapshot
  behind the same seam if a future measurement shows them scattering.

## Amendment (2026-07-30) — the writer recomputes only when the content could have changed

The first increment ran the leader loop on a **blind interval**: it recomputed the whole snapshot
every `SNAPSHOT_INTERVAL_S` (3 s) unconditionally. As the snapshot grew to also carry the batch
panels, the inbox, the incidents overview (deny-ledger clustering) and the audit overview/page, one
full recompute measured **~2.8 s warm** — longer than the interval itself. On a STABLE ledger the
leader was therefore pinned at ~100 % CPU recomputing byte-identical content, and that contention
delayed the client fleet card's fetch enough to reintroduce an intermittent **flash** — the very
scatter/storm this ADR set out to remove, now moved from the request path onto the leader.

The fix keeps the mechanism and refines *when* it fires. The snapshot content is derived from the
append-only ledger, so an unchanged head (`ledger_store.ledger_head_seq` — one indexed `max(seq)`
row, sub-millisecond) proves it byte-identical. The leader now takes a cheap **fingerprint**
`(ledger_head_seq, ceiling_bucket)` each cycle and recomputes only when it moves — the head
advanced, or a refresh **ceiling** (`SNAPSHOT_REFRESH_CEILING_S`, 60 s) elapsed. The ceiling is the
backstop for the two things the head does not witness: wall-clock windows (fleet `d7`, incidents
`until=now`) and any non-ledger mutation (business_events, operator items). When the fingerprint is
stable the leader does NOT recompute — it only **re-stamps** the last snapshot's timestamp so
readers' `SNAPSHOT_TTL_S` never expires and they never fall through to a per-worker compute. A file
ledger source (no cheap head) or a probe failure yields a `None` fingerprint, which forces the
pre-amendment behavior (recompute every cycle): the change is purely additive and fail-open.

Result: on a stable ledger the leader recomputes at most once per ceiling instead of every interval
(a ~20× cut) and stays near-idle rather than pinned. It also improves the scaling shape — a blind
interval recompute fires regardless of activity, a head-keyed one does not fire at all while the
ledger is quiet. Honesty on what this does NOT fix: when the head *does* move, one recompute is
still O(ledger); bounding the individual reads (fleet, chrome, incidents) in SQL is the separate
read-budget chantier (ADR 0047 + the P1 conversions), which makes each recompute cheap too.
