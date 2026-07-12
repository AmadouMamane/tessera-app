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
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from tessera import __version__
from tessera.agent.telemetry import install_runtime_provider
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
from tessera.memory.governance import ensure_consent_schema
from tessera.memory.persistent import ensure_longterm_schema
from tessera.memory.summary import ensure_summary_schema
from tessera.memory.transcript import ensure_transcript_schema
from tessera.observability import logging as obs_logging, metrics, traces
from tessera.observability.eval.gating_scores import ensure_eval_gating_schema
from tessera.retrieval.citations import ensure_citation_schema
from tessera.retrieval.store import ensure_schema, get_pool
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
            await asyncio.sleep(interval)
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


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open + close the resources that outlive a single request."""
    obs_logging.configure()
    traces.configure()
    metrics.configure()
    pool = get_pool()
    seal_task: asyncio.Task[None] | None = None
    purge_task: asyncio.Task[None] | None = None
    canary_tasks: list[asyncio.Task[None]] = []
    try:
        await pool.open()
        # Materialise every durable table in the active env schema at boot so a
        # read never falls through search_path to public (ADR 0014 invariant).
        await ensure_schema()  # documents (pgvector)
        await ensure_transcript_schema()  # ADR 0007, Mechanism A
        await ensure_summary_schema()  # ADR 0007, Tier 1
        await ensure_longterm_schema()  # ADR 0007, Tier 2
        await ensure_consent_schema()  # ADR 0007, governance
        await ensure_citation_schema()  # retrieval citation counters
        await ensure_settings_schema()  # persisted runtime flags
        await ensure_eval_gating_schema()  # ADR 0015 §Amendment 2 — gating socle (porteur)
        await _ensure_online_score_store()  # ADR 0015 §Correction 2b — best-effort
        await _reconcile_gating_archive()  # ADR 0015 G4 — idempotent file→porteur sweep
        await _reconcile_audit_ledger()  # ADR 0015 §Amendment 3 — verified file→table copy
        seal_task = await _start_seal_scheduler()  # ADR 0015 §Corr.3c — off-chrono; no-op if 'none'
        canary_tasks = await _start_canary_scheduler()  # ADR 0019 §I4 — off-chrono; idle by default
        purge_task = await _start_memory_purge_scheduler()  # ADR 0007 §Retention — off-chrono
        yield
    finally:
        for task in (seal_task, purge_task, *canary_tasks):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        await pool.close()


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
    # Docs/OpenAPI are on for local dev, off in production, and can be closed
    # explicitly (expose_docs=False) on an internet-reachable non-prod agent.
    docs_on = settings.api.expose_docs and not settings.is_production()
    app = FastAPI(
        title="Tessera",
        version=__version__,
        description=(
            "Multilingual (FR/DE/EN) banking support LLM agent, grounded in EU "
            "regulatory corpora and guarded by mcp-firewall."
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

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuthMiddleware)
    # Added last → outermost, so security headers cover every response,
    # including the 401s / 429s produced by inner middleware (ADR 0020).
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(recouvrement_assistant.router)
    # ADR 0019 §I3 — the declared cockpit→agent invocation seam. Like /chat it resolves the
    # operator assertion internally (no bearer gate); the route itself refuses a non-operator.
    app.include_router(invoke_routes.router)
    # Customer-facing session (demo login/logout) — public like /chat, no bearer
    # gate. It is the server-side source of auth_state the supervisor reads.
    app.include_router(session_routes.router)
    # Aggregate eval scores are a public surface (ADR 0009) — no bearer gate.
    app.include_router(observability_routes.router)
    # Defence in depth: the read surfaces require the bearer token at the route
    # level too, not only via the global middleware (ADR 0020).
    app.include_router(audit.router, dependencies=[Depends(require_bearer)])
    app.include_router(memory.router, dependencies=[Depends(require_bearer)])
    app.include_router(settings_routes.router, dependencies=[Depends(require_bearer)])

    # Drop the per-message ASGI "http send"/"http receive" child spans: the SSE
    # chat stream emits one send per token, which would bury the real
    # invoke_agent / retrieve / execute_tool spans under hundreds of noise spans
    # in Phoenix. The server request span (POST /chat) is kept as the trace root.
    FastAPIInstrumentor.instrument_app(app, exclude_spans=["send", "receive"])
    return app


def cli() -> None:
    """Console-script entry point — boots the API via uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "tessera.api.main:build_app",
        host=settings.api.host,
        port=settings.api.port,
        factory=True,
        log_level=settings.observability.log_level.lower(),
        access_log=False,  # delegated to structlog via middleware
    )
