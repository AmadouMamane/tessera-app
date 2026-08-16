"""FastAPI application factory and uvicorn entry point.

The factory wires every cross-cutting concern in a single place:

* OTel tracing, Prometheus metrics, structlog logging.
* Bearer-token auth middleware (configured per environment).
* Request-ID propagation for cross-service correlation.
* CORS for the bundled dashboard.
* All routers (chat, audit, health).

The :func:`cli` entry point is exposed as the ``tessera`` console script in
``pyproject.toml`` — it boots uvicorn against the factory.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, Final

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from tessera import __version__
from tessera.agent.telemetry import install_runtime_provider
from tessera.api.config_overrides import ensure_overrides_schema
from tessera.api.leader import bootstrap_lock, try_become_leader
from tessera.api.limits import RequestSizeLimitMiddleware
from tessera.api.middleware import AuthMiddleware, RequestIdMiddleware
from tessera.api.operator import validate_operator_assertion_key
from tessera.api.ratelimit import RateLimitMiddleware
from tessera.api.routes import (
    audit,
    chat,
    health,
    invoke as invoke_routes,
    memory,
    observability as observability_routes,
    recouvrement_assistant,
    session as session_routes,
    settings as settings_routes,
)
from tessera.api.security import (
    SecurityHeadersMiddleware,
    require_bearer,
    validate_bearer_token,
)
from tessera.api.session import validate_session_signing_key
from tessera.api.settings_store import ensure_settings_schema
from tessera.guard.audit import validate_audit_chain_config
from tessera.guard.seal import validate_exposed_seal_config
from tessera.llm.ceiling import DailyCeilingReachedError
from tessera.memory.governance import ensure_consent_schema
from tessera.memory.persistent import ensure_longterm_schema
from tessera.memory.summary import ensure_summary_schema
from tessera.memory.transcript import ensure_transcript_schema
from tessera.observability import logging as obs_logging, metrics, traces
from tessera.observability.customer_feedback import ensure_customer_feedback_schema
from tessera.observability.eval.gating_scores import ensure_eval_gating_schema
from tessera.retrieval.citations import ensure_citation_schema
from tessera.retrieval.store import ensure_schema, get_pool
from tessera.settings import get_settings, unbound_env_overrides

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

__all__ = ["build_app", "cli"]


async def _ensure_online_score_store() -> None:
    """Bootstrap the owned ClickHouse online-score table, best-effort (§Correction 2b).

    Online scores are sampled monitoring telemetry — by the ADR's governing rule they are
    *not* load-bearing, so an absent obs stack must never block boot: the bootstrap is
    deferred (the write path re-ensures lazily) and logged, never fabricated.
    """
    import asyncio

    from tessera.observability.spine.adapters.base import SpineUnavailableError
    from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

    try:
        await asyncio.to_thread(ClickHouseAdapter().ensure_schema)
    except SpineUnavailableError as exc:
        obs_logging.get_logger("tessera.spine").warning(
            "clickhouse.ensure_deferred", error=str(exc)
        )


async def _reconcile_gating_archive() -> None:
    """Converge the report-file archive into the gating porteur at boot (ADR 0015 G4).

    Idempotent by the table's unique key (a re-sweep inserts nothing), bounded by the
    archive size, and best-effort: a sweep failure is logged, never blocks boot — the
    report files remain the archive and the next boot (or the backfill CLI) retries.
    """
    from tessera.observability.eval.gating_scores import ingest_gating_reports

    try:
        reports, inserted = await ingest_gating_reports()
    except Exception as exc:  # reconciliation must never block boot
        obs_logging.get_logger("tessera.spine").warning("gating.sweep_deferred", error=str(exc))
        return
    if inserted:
        obs_logging.get_logger("tessera.spine").info(
            "gating.sweep_recorded", reports=reports, rows_inserted=inserted
        )


async def _reconcile_audit_ledger() -> None:
    """Promote/reconcile the audit journal into the append-only Postgres ledger (§Amend.3).

    The backfill verifies the file chain FIRST and refuses a broken one; the unique hash
    makes a re-run free; a missed dual-write heals here. Best-effort at boot — the flat
    file remains canonical until the ``TESSERA_LEDGER_SOURCE`` cut, so a deferred sweep
    is honest, never blocking.
    """
    from tessera.guard.ledger_store import (
        backfill_ledger_from_file,
        drain_spool,
        ensure_audit_ledger_schema,
    )

    log = obs_logging.get_logger("tessera.ledger")
    audit_file = get_settings().guard.audit_file
    try:
        await ensure_audit_ledger_schema()
        # The promoted table is canonical (H2 cut): boot depends only on the schema + the
        # spool replay for durability. Replay entries spooled before a crash/outage so no
        # audit is lost across a restart.
        if not drain_spool():
            log.warning("ledger.spool_replay_deferred")
        # Legacy/escape only: a still-present flat file is reconciled into the table
        # (idempotent). Post-retirement the file is absent → no-op, NOT a boot dependency.
        if not audit_file.exists():
            return
        inserted, status = await backfill_ledger_from_file(audit_file)
    except Exception as exc:  # promotion must never block boot
        log.warning("ledger.promotion_deferred", error=str(exc))
        return
    if not status.verified:
        log.warning("ledger.file_chain_broken", broken_at=status.broken_at, length=status.length)
    elif inserted:
        log.info("ledger.promoted", rows_inserted=inserted, chain_length=status.length)


async def _start_seal_scheduler() -> asyncio.Task[None] | None:
    """Start the off-chrono Hica seal loop (ADR 0015 §Correction 3c). No-op under provider='none'.

    Logs ONE honest posture line at boot — provider + cadence when sealing, or "not sealing" —
    then, only when a real provider is configured, schedules a background task that seals the chain
    head every τ. The seal is best-effort and off every request path; a cycle failure warns and the
    loop survives. Design note §12. ``seal_posture`` is the single source of the sealing decision,
    so the log line and the scheduler can never disagree.
    """
    from tessera.guard.seal import run_seal_cycle, seal_posture

    log = obs_logging.get_logger("tessera.seal")
    posture = seal_posture()
    log.info("seal.posture", **posture)
    if not posture["sealing"]:
        return None
    cadence = posture["cadence_s"]
    interval = cadence if isinstance(cadence, int) else 3600

    async def _loop() -> None:
        while True:
            try:
                result = await asyncio.to_thread(run_seal_cycle)
                log.info(
                    "seal.cycle",
                    sealed=result.sealed,
                    state=result.state,
                    continuity=result.continuity,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a cycle failure must never kill the loop
                log.warning("seal.cycle_failed", error=str(exc))
            await asyncio.sleep(interval)

    return asyncio.create_task(_loop())


async def _start_canary_scheduler() -> list[asyncio.Task[None]]:
    """Start the off-chrono canary loops (ADR 0019 §I4). No-op unless enabled + a cadence declared.

    Logs ONE honest posture line at boot — enabled + which agents/cadences, or "not scheduling" —
    then, only when scheduling, starts one background loop per scheduled agent that drives a
    synthetic turn through its in_process_chat binding every cadence. The turns are stamped
    synthetic (so they never enter business metrics) and each emits one S1 event. Best-effort and
    off every request path; a cycle failure warns and the loop survives — the same family and
    hygiene as the seal scheduler. ``canary_posture`` is the single source of the decision, so the
    log line and the loops can never disagree.
    """
    from tessera.agent.canary import canary_posture, run_canary_cycle, scheduled_canaries

    log = obs_logging.get_logger("tessera.canary")
    posture = canary_posture()
    log.info("canary.posture", **posture)
    if not posture["scheduling"]:
        return []

    def _make_loop(agent_id: str, interval: int) -> asyncio.Task[None]:
        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                try:
                    result = await run_canary_cycle(agent_id)
                    log.info(
                        "canary.cycle",
                        agent_id=result.agent_id,
                        verdict=result.verdict,
                        duration_ms=round(result.duration_ms, 1),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # a cycle failure must never kill the loop
                    log.warning("canary.cycle_failed", agent_id=agent_id, error=str(exc))

        return asyncio.create_task(_loop())

    return [_make_loop(canary.agent_id, canary.cadence_s) for canary in scheduled_canaries()]


async def _start_ledger_verification_scheduler() -> asyncio.Task[None] | None:
    """Re-walk the WHOLE ledger chain at boot, then off-chrono — the claim the badge leans on.

    The integrity badge no longer re-hashes 25 634 rows per request (p50 was 1 093 ms on every
    cockpit page, and 1 828 ms on the ``?at=`` branch the overview polls every 15 s). It verifies
    only the rows above a persisted checkpoint, which the append-only trigger makes sound: a
    verified prefix cannot change.

    That soundness rests on the checkpoint having been earned. This loop is what earns it — and
    keeps earning it. It walks and re-hashes every row, resets the freshness clock, and the badge
    publishes that clock ("full chain checked 12 min ago · 412 entries verified since"). Without
    this, "verified" would rest on a proof nobody had re-done, which is an assumption wearing the
    clothes of a proof.

    Verifies FIRST and sleeps after (like the retention purge), so a process that has been down
    does not serve a badge backed by a checkpoint from before the outage.
    """
    from tessera.guard.ledger_checkpoint import run_full_verification
    from tessera.guard.ledger_store import ledger_source
    from tessera.settings import get_settings

    if ledger_source() != "postgres":
        return None  # file mode walks the whole journal on every read — nothing to checkpoint

    log = obs_logging.get_logger("tessera.ledger")
    interval = get_settings().guard.ledger_verify_interval_s
    log.info("ledger.verify_posture", verifying=interval > 0, interval_s=interval or None)
    if interval <= 0:
        return None

    async def _loop() -> None:
        while True:
            try:
                verdict = await asyncio.to_thread(run_full_verification)
                log.info(
                    "ledger.full_verification",
                    content_integrity=verdict.tree.content_integrity,
                    linear=verdict.tree.linear,
                    length=verdict.tree.length,
                    forks=verdict.tree.fork_count,
                    orphans=verdict.tree.orphan_count,
                    entries_walked=verdict.entries_verified_now,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a cycle failure must never kill the loop
                log.warning("ledger.full_verification_failed", error=str(exc))
            await asyncio.sleep(interval)

    return asyncio.create_task(_loop())


async def _start_memory_purge_scheduler() -> asyncio.Task[None] | None:
    """Start the off-chrono GDPR retention purge (ADR 0007 §Retention). No-op when disabled.

    Audit 2026-07-10, P1 `gdpr-retention`: ``purge_expired`` had **no caller**. ``ttl_for``
    bounded retention at *read* time while the rows lived on in Postgres indefinitely —
    retention enforced in the view, not in the store, which is not retention at all under
    GDPR Art. 5(1)(e). Personal data past its TTL was kept forever.

    Logs ONE honest posture line at boot — purging + cadence, or "not purging" — then, only
    when a cadence is configured, schedules a background task. Purges FIRST and sleeps after,
    so data that expired while the service was down is removed promptly rather than lingering
    a further τ. Best-effort and off every request path; a cycle failure warns and the loop
    survives. ``purge_posture`` is the single source of the decision, so the log line and the
    scheduler can never disagree — the same family and hygiene as the seal scheduler.
    """
    from tessera.memory.governance import purge_posture
    from tessera.memory.persistent import purge_expired

    log = obs_logging.get_logger("tessera.memory")
    posture = purge_posture()
    log.info("memory.purge_posture", **posture)
    if not posture["purging"]:
        return None
    cadence = posture["interval_s"]
    interval = cadence if isinstance(cadence, int) else 3600

    async def _loop() -> None:
        while True:
            try:
                deleted = await purge_expired()
                log.info("memory.purge_cycle", deleted=deleted)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a cycle failure must never kill the loop
                log.warning("memory.purge_failed", error=str(exc))
            await asyncio.sleep(interval)

    return asyncio.create_task(_loop())


async def _start_read_cache_warmer() -> asyncio.Task[None] | None:
    """Warm the per-worker read caches once at boot so the FIRST request never pays cold.

    The cockpit's heaviest reads build an in-process, head-invalidated cache on first touch:
    ``load_ledger_payloads_sync`` (~1 s cold → ~24 ms, the whole-ledger read the ai-act /
    guard-audit panels derive from) and the timeline rail (~2.1 s cold → ~30 ms). Those caches
    PERSIST across the 3 s memo TTL because the ledger is append-only (an unchanged ``max(seq)``
    guarantees an unchanged result), so ONE warm-up per worker is enough — after it, every request
    is warm. With N workers each holding its own in-process cache, a user's requests scatter across
    still-cold workers until all N are warm; this pays that cost off the request path at boot.

    Runs in EVERY worker — the cache is per-process, so unlike the singleton background loops (which
    are leader-gated per ADR 0044) this MUST NOT be. It is a one-shot, not a loop. Best-effort: a
    warm-up failure warns and is simply re-earned by the next real request. Postgres only — file
    mode has no such cache and re-walks the journal on every read regardless.
    """
    from tessera.guard.ledger_store import ledger_source

    if ledger_source() != "postgres":
        return None

    log = obs_logging.get_logger("tessera.warmup")

    async def _warm() -> None:
        import time

        from tessera.api.routes.audit import _read_entries_full_cached
        from tessera.api.routes.observability.console import observability_timeline
        from tessera.guard.ledger_store import load_ledger_payloads_sync

        started = time.perf_counter()
        warmed: list[str] = []
        # The whole-ledger cache first: the timeline rail's own read is cheaper once the shared
        # connection path is warm, and this is the read the ai-act / guard-audit panels reuse.
        # audit_entries is the ~2 s Pydantic validation of the whole chain that the audit-log page
        # (overview + windowed page) filters — warm it too, else that page's first hit on each
        # worker pays the full validation.
        for label, fn in (
            ("ledger_payloads", load_ledger_payloads_sync),
            ("timeline", observability_timeline),
            ("audit_entries", _read_entries_full_cached),
        ):
            try:
                await asyncio.to_thread(fn)
                warmed.append(label)
            except (
                Exception
            ) as exc:  # a warm-up failure must never matter — the request re-earns it
                log.warning("warmup.failed", cache=label, error=str(exc))
        log.info(
            "warmup.done", warmed=warmed, elapsed_ms=round((time.perf_counter() - started) * 1000)
        )

    return asyncio.create_task(_warm())


async def _start_stack_probe_scheduler() -> asyncio.Task[None] | None:
    """LEADER-only loop: probe the declared stack components on a cadence (ADR 0052 §Amendment 1).

    Without it the component journal only knows the minutes a cockpit happened to be open, and
    every availability figure is a true statement about a sliver — 1.3 % of the day, the day the
    history shipped. The loop probes FIRST and sleeps after (a fresh leader records immediately),
    goes through the same 15 s cache as the page's own reads (a beat landing just after a page
    poll reuses its observation), and stamps its liveness to a file each beat so the endpoint —
    served by ANY worker — can report `active`/`stale` from something the loop actually wrote
    rather than from configuration. Best-effort: a cycle failure warns and the loop survives.
    """
    from tessera.api.routes.observability.components import probe_for_scheduler
    from tessera.observability.probe_scheduler import probe_posture

    log = obs_logging.get_logger("tessera.stackprobe")
    posture = probe_posture()
    log.info("stack_probe.posture", **posture)
    if not posture["scheduling"]:
        return None
    cadence = posture["interval_s"]
    interval = cadence if isinstance(cadence, int) else 60

    async def _loop() -> None:
        while True:
            try:
                observed_at = await asyncio.to_thread(probe_for_scheduler)
                log.debug("stack_probe.cycle", observed_at=observed_at)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a cycle failure must never kill the loop
                log.warning("stack_probe.cycle_failed", error=str(exc))
            await asyncio.sleep(interval)

    return asyncio.create_task(_loop())


async def _start_read_snapshot_writer() -> asyncio.Task[None] | None:
    """LEADER-only loop: compute the hottest cockpit reads once and publish a shared snapshot.

    ADR 0046. chrome and fleet recomputed independently on every worker under the page's concurrent
    read burst, contending on each worker's GIL (~2.4 s each, though ~6 ms warm in isolation). The
    leader now computes them off every request path and writes ONE JSON snapshot to the shared state
    dir; every worker reads it. Leader-gated because it is a singleton background loop (ADR 0044): N
    workers writing the same file would be N times the compute for one file. Publishes FIRST then
    sleeps, so a freshly-elected leader does not serve an empty snapshot window longer than needed.
    Best-effort: a cycle failure warns and the loop survives; readers degrade to their own compute.
    """
    from tessera.observability.read_snapshot import (
        SNAPSHOT_INTERVAL_S,
        SNAPSHOT_REFRESH_CEILING_S,
        compute_snapshot_entries,
        snapshot_fingerprint,
        snapshot_needs_recompute,
        write_snapshot,
    )

    log = obs_logging.get_logger("tessera.snapshot")
    log.info(
        "read_snapshot.posture",
        interval_s=SNAPSHOT_INTERVAL_S,
        refresh_ceiling_s=SNAPSHOT_REFRESH_CEILING_S,
    )

    async def _loop() -> None:
        # Recompute the expensive (~2.8 s) snapshot only when its cheap fingerprint moves — the
        # ledger head advanced or the refresh ceiling elapsed — never on the blind interval alone
        # (ADR 0046). On a STABLE ledger this takes the leader from ~100 % CPU (a full recompute
        # every 3 s) to near-idle, which is what removes the intermittent flash on the fleet card.
        # Every cycle still RE-STAMPS the last snapshot so readers' TTL never expires and they never
        # fall through to a per-worker compute.
        last_fingerprint: tuple[int, int] | None = None
        last_entries: dict[str, dict[str, Any]] | None = None
        while True:
            try:
                fingerprint = await asyncio.to_thread(snapshot_fingerprint)
                if snapshot_needs_recompute(
                    last_fingerprint, fingerprint, last_entries is not None
                ):
                    last_entries = await compute_snapshot_entries()
                    last_fingerprint = fingerprint
                    log.info("read_snapshot.recomputed", fingerprint=fingerprint)
                # snapshot_needs_recompute returns True whenever last_entries is None, so past the
                # gate it is always populated — assert it for the type checker, never at runtime.
                assert last_entries is not None
                await asyncio.to_thread(write_snapshot, last_entries)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a cycle failure must never kill the loop
                log.warning("read_snapshot.cycle_failed", error=str(exc))
            await asyncio.sleep(SNAPSHOT_INTERVAL_S)

    return asyncio.create_task(_loop())


async def _start_singleton_work() -> list[asyncio.Task[None]]:
    """LEADER-only (ADR 0044): the one-time convergence sweeps + every off-chrono background loop.

    N concurrent sealers / purge loops / archive sweeps / snapshot writers are a correctness bug,
    not a scaling win, so they run on the single elected leader. Returns the started tasks — the
    schedulers that are a no-op under their posture return ``None`` and are dropped — for shutdown.
    """
    await _reconcile_gating_archive()  # ADR 0015 G4 — idempotent file→porteur sweep
    await _reconcile_audit_ledger()  # ADR 0015 §Amendment 3 — verified file→table copy
    started: list[asyncio.Task[None] | None] = [
        await _start_seal_scheduler(),  # ADR 0015 §Corr.3c — off-chrono
        *await _start_canary_scheduler(),  # ADR 0019 §I4 — off-chrono
        await _start_memory_purge_scheduler(),  # ADR 0007 §Retention — off-chrono
        await _start_ledger_verification_scheduler(),  # off-chrono chain walk
        await _start_read_snapshot_writer(),  # ADR 0046 — shared hot-read cache
        await _start_stack_probe_scheduler(),  # ADR 0052 §Am.1 — the watched history
    ]
    return [task for task in started if task is not None]


#: Upper bound on how long the LEADER blocks its own boot waiting for its read-cache warm-up before
#: proceeding. A normal warm-up is ~4 s; a slow/unreachable DB must never wedge boot, so an overrun
#: leaves the warmer running in the background (shielded) and the leader carries on.
_LEADER_WARM_BUDGET_S: Final = 15.0


async def _start_boot_background_work(
    is_leader: bool,
) -> tuple[asyncio.Task[None] | None, list[asyncio.Task[None]]]:
    """Start each worker's boot background work in the order that avoids leader warm-up contention.

    Every worker warms its own per-process read caches at boot (fire-and-forget on followers —
    nothing on them competes). On the LEADER we FINISH warming BEFORE starting the singleton
    snapshot writer: that writer's first cycle is heavy — it clusters the incidents core, validates
    the audit chain and fans out the batch panels — and, run concurrently with the warmer, contends
    for the read threadpool and the DB, stretching the leader's warm-up from ~4 s to ~20 s. During
    that window a per-agent SURVEILLER read landing on the still-cold leader re-materialises the
    whole 195 k-row ledger under the page's concurrent burst — the "sometimes several seconds" the
    operator sees after a restart. Warming first collapses that window to the warm-up itself, and
    also hands the snapshot writer an already-warm ledger cache. A warm-up that overruns the budget
    is left to finish in the background (shielded) so a slow DB can never wedge boot.

    Returns ``(warm_task, leader_tasks)`` for the lifespan to cancel on shutdown.
    """
    warm_task = await _start_read_cache_warmer()
    leader_tasks: list[asyncio.Task[None]] = []
    if is_leader:
        if warm_task is not None:
            with suppress(Exception):  # timeout or a warm-up error must never block boot
                await asyncio.wait_for(asyncio.shield(warm_task), _LEADER_WARM_BUDGET_S)
        leader_tasks = await _start_singleton_work()
    return warm_task, leader_tasks


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open + close the resources that outlive a single request."""
    from tessera.guard.ledger_store import ensure_audit_ledger_schema

    obs_logging.configure()
    traces.configure()
    # `extra="ignore"` means a mistyped override is dropped without a word, and the operator
    # goes on believing they changed a setting they did not (settings.unbound_env_overrides).
    # Boot is where that can still be caught.
    unbound = unbound_env_overrides()
    if unbound:
        obs_logging.get_logger("tessera.settings").warning(
            "settings.unbound_env_overrides", names=list(unbound)
        )
    # Leadership FIRST (ADR 0044), on a dedicated connection independent of the pool, so two
    # decisions can key off it: which worker binds the metrics port, and which worker runs the
    # singleton background loops. In the single-worker default the lone process trivially wins,
    # so both behave exactly as they did before multi-worker existed.
    leader_conn = await try_become_leader()
    is_leader = leader_conn is not None
    obs_logging.get_logger("tessera.leader").info(
        "leader.posture", is_leader=is_leader, workers=get_settings().api.workers
    )
    # Only the leader binds metrics_port; every worker still RECORDS via the multiprocess mmap
    # store, so the exposed counters aggregate across the whole process group (see metrics.py).
    metrics.configure(serve=is_leader)
    # Starlette runs synchronous (`def`) endpoints in this threadpool. The observability
    # READ handlers are synchronous so their blocking DB reads run off the event loop and
    # concurrent dashboard reads run in PARALLEL instead of serializing behind one loop.
    # Size it from settings (anyio's default is 40).
    import anyio.to_thread

    anyio.to_thread.current_default_thread_limiter().total_tokens = get_settings().api.read_threads
    pool = get_pool()
    warm_task: asyncio.Task[None] | None = None
    leader_tasks: list[asyncio.Task[None]] = []
    try:
        await pool.open()
        # Materialise every durable table in the active env schema at boot so a read never
        # falls through search_path to public (ADR 0014 invariant). Serialised across workers
        # by a blocking advisory lock (ADR 0044) so concurrent fresh workers do not race
        # CREATE ... IF NOT EXISTS to a catalogue duplicate-key error. Every worker runs it —
        # idempotent — so its own view has the tables before it serves the first read.
        async with bootstrap_lock():
            await ensure_schema()  # documents (pgvector)
            await ensure_transcript_schema()  # ADR 0007, Mechanism A
            await ensure_customer_feedback_schema()  # ADR 0041, customer CSAT store
            await ensure_summary_schema()  # ADR 0007, Tier 1
            await ensure_longterm_schema()  # ADR 0007, Tier 2
            await ensure_consent_schema()  # ADR 0007, governance
            await ensure_citation_schema()  # retrieval citation counters
            await ensure_settings_schema()  # persisted runtime flags
            await ensure_overrides_schema()  # ADR 0030 — governed operable-knob overrides
            await ensure_eval_gating_schema()  # ADR 0015 §Amendment 2 — gating socle (porteur)
            await ensure_audit_ledger_schema()  # ADR 0015 §Amend.3 — ledger table on every worker
            await _ensure_online_score_store()  # ADR 0015 §Correction 2b — best-effort
        # The one-time convergence SWEEPS and the off-chrono BACKGROUND LOOPS run on the
        # singleton leader ONLY (ADR 0044): N concurrent sealers / purge loops / archive
        # sweeps are a correctness bug, not a scaling win. Non-leader workers serve request
        # traffic against the schema the leader (and their own ensure block) materialised. The
        # helper also warms each worker's read caches — on the leader BEFORE the singleton
        # snapshot writer, so the two do not contend and stretch the leader's warm-up window.
        warm_task, leader_tasks = await _start_boot_background_work(is_leader)
        yield
    finally:
        for task in (warm_task, *leader_tasks):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        if leader_conn is not None:
            # Abdicate: closing the dedicated connection releases the session advisory lock,
            # so a respawned worker can re-acquire leadership on its next boot.
            with suppress(Exception):
                await leader_conn.close()
        await pool.close()


async def _daily_ceiling_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Turn ADR 0034's refusal into an answer the operator can act on.

    ``402 Payment Required`` — the only status that says what happened. Not 503 (nothing is
    unavailable), not 429 (nothing is rate-limited), and above all not 200 with an empty
    report: a probe that returns zeros when it was refused is indistinguishable from a probe
    that ran and found zeros.
    """
    ceiling = exc if isinstance(exc, DailyCeilingReachedError) else None
    return JSONResponse(
        status_code=402,
        content={
            "error": "daily_ceiling_reached",
            "detail": str(exc),
            "caller": ceiling.caller if ceiling else None,
            "model": ceiling.model if ceiling else None,
            "ceiling_eur": str(ceiling.ceiling_eur) if ceiling else None,
            "day_spend_eur": str(ceiling.day_spend_eur) if ceiling else None,
        },
    )


def build_app() -> FastAPI:
    """Construct the FastAPI application."""
    settings = get_settings()
    # Wire the agent runtime into the spine's telemetry ports (ADR 0017 §1): the
    # cockpit routes read runtime facts via get_runtime_provider() and never
    # import the runtime themselves. Absent in a cockpit-only deployment, where
    # the spine serves honest-empty defaults.
    install_runtime_provider()
    # Fail-closed config validation (ADR 0008/0009/0010): refuse to boot in
    # production without the real signing keys instead of silently degrading. The
    # customer-session key (ADR 0008/0009) and the operator-assertion key (ADR 0010
    # Phase B) are both required in prod; no-op in dev/CI.
    validate_session_signing_key()
    validate_operator_assertion_key()
    # The third member of the family, missing until the 2026-07-10 audit: an unset bearer
    # made require_bearer and AuthMiddleware no-ops, publishing audit/memory/settings.
    validate_bearer_token()
    # The fourth (ADR 0023, audit 2026-07-12 F-6): an exposed deployment whose audit_sink /
    # ledger_source combination cannot PERSIST the hash chain refuses to boot, rather than
    # emitting to the sink while silently chaining nothing into the opposable ledger.
    validate_audit_chain_config()
    # ADR 0042: staging/production are proof surfaces. They cannot boot with a cosmetic
    # "infalsifiable" promise: a qualified RFC 3161 TSA + pinned trust root are mandatory.
    # The live badge remains stricter and only greens after token verification succeeds.
    validate_exposed_seal_config()
    # Docs/OpenAPI are on for local dev, off in production, and can be closed
    # explicitly (expose_docs=False) on an internet-reachable non-prod agent.
    docs_on = settings.api.expose_docs and not settings.is_production()
    app = FastAPI(
        title="Tessera",
        version=__version__,
        description=(
            "Multilingual (FR/DE/EN) banking support LLM agent, grounded in EU "
            "regulatory corpora, with a first-party runtime guard on every tool call."
        ),
        docs_url="/docs" if docs_on else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_on else None,
        lifespan=_lifespan,
    )

    if settings.api.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["authorization", "content-type", "x-request-id"],
            allow_credentials=False,
        )

    # ADR 0034 — one refusal for every path that asked the ceiling and was told no. Registered
    # once here rather than caught in each probe route: six probes returning six shapes of
    # "empty report" is how a refusal comes to look like a measurement (ADR 0026). 402 Payment
    # Required is the one status that says what actually happened; the body names the ceiling,
    # the day's spend and WHO was refused, so the operator can act without reading a log.
    app.add_exception_handler(DailyCeilingReachedError, _daily_ceiling_handler)

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuthMiddleware)
    # Added last → outermost, so security headers cover every response,
    # including the 401s / 429s produced by inner middleware (ADR 0020).
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(health.router)
    app.include_router(chat.router)
    # Business-plane writes (ledger events, governed artifact transitions). The guard —
    # require_collections_operator — is declared on the router itself, like the cockpit
    # mutations router: a route added there cannot forget it. Audit 2026-07-12, P0 F-1:
    # this line used to mount the two POSTs with no dependency at all, while the BFF
    # attached the service bearer on the anonymous caller's behalf.
    app.include_router(recouvrement_assistant.router)
    # ADR 0019 §I3 — the declared cockpit→agent invocation seam. Like /chat it resolves the
    # operator assertion internally (no bearer gate); the route itself refuses a non-operator.
    app.include_router(invoke_routes.router)
    # Customer-facing session (demo login/logout) — public like /chat, no bearer
    # gate. It is the server-side source of auth_state the supervisor reads.
    app.include_router(session_routes.router)
    # Aggregate eval scores are a public surface (ADR 0009) — no bearer gate. The
    # SUBJECT-SCOPED reads inside this router (transcripts, session detail, memory
    # inventory, erasure footprints) are NOT public and never were meant to be: they
    # carry require_subject_reader on their own router (routes/observability/pii.py).
    # Audit 2026-07-12, P1 F-4 — this line's old comment said "public surface" flatly,
    # and the router obeyed it: `GET /observability/conversation-messages` served any
    # conversation's transcript to anyone.
    app.include_router(observability_routes.router)
    # Defence in depth: the read surfaces require the bearer token at the route level
    # too, not only via the global middleware (ADR 0020). The bearer is a FLOOR here, not
    # the gate — it says the call came from our frontend, never who made it (F-5). The
    # memory routers carry the identity guard themselves (require_operator for the GDPR
    # writes, require_subject_reader for the Art. 15 read), and /settings' write carries
    # require_superadmin.
    app.include_router(audit.router, dependencies=[Depends(require_bearer)])
    app.include_router(memory.router, dependencies=[Depends(require_bearer)])
    app.include_router(memory.read_router, dependencies=[Depends(require_bearer)])
    app.include_router(settings_routes.router, dependencies=[Depends(require_bearer)])

    # Drop the per-message ASGI "http send"/"http receive" child spans: the SSE
    # chat stream emits one send per token, which would bury the real
    # invoke_agent / retrieve / execute_tool spans under hundreds of noise spans
    # in Phoenix. The server request span (POST /chat) is kept as the trace root.
    FastAPIInstrumentor.instrument_app(app, exclude_spans=["send", "receive"])
    return app


def _prepare_multiprocess_metrics(state_dir: Path) -> None:
    """Set up the Prometheus multiprocess mmap directory before the workers spawn (ADR 0044).

    ``prometheus_client`` reads ``PROMETHEUS_MULTIPROC_DIR`` once, at import, to decide whether
    metric values live in per-pid mmap files (multi-worker) or in-process (single). uvicorn
    spawns each worker as a *fresh* interpreter that inherits this process's environment, so
    exporting the variable here — before ``uvicorn.run(workers=N)`` — is what puts every worker
    into multiprocess mode. The directory MUST be empty at start: leftover files from a previous
    run would be summed straight into every counter, inflating each by the last boot's totals.
    """
    import shutil

    shutil.rmtree(state_dir, ignore_errors=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(state_dir)


def cli() -> None:
    """Console-script entry point — boots the API via uvicorn."""
    import uvicorn

    settings = get_settings()
    workers = max(1, settings.api.workers)
    # Multi-worker only: switch Prometheus into multiprocess aggregation before the workers
    # spawn. Passing workers=None below is exactly what uvicorn already defaults to (single
    # process), so the single-worker path is byte-identical to the pre-ADR-0044 boot — no
    # multiproc metrics dir, no multiprocess supervisor.
    if workers > 1 and settings.observability.metrics_enabled:
        _prepare_multiprocess_metrics(settings.state_dir / "prometheus")
    uvicorn.run(
        "tessera.api.main:build_app",
        host=settings.api.host,
        port=settings.api.port,
        factory=True,
        workers=workers if workers > 1 else None,
        log_level=settings.observability.log_level.lower(),
        access_log=False,  # delegated to structlog via middleware
    )
