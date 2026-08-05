"""Observability routes — the stack's components, as the preflight witness sees them.

``/fr/surveiller/observabilite`` rendered four KPI cards whose only health inputs were
``/healthz`` and ``/readyz``: two probes about the agent process, collapsed into one green dot.
Its own contextual help promised something else — *"commencez par la composante indisponible ou
dégradée, puis lisez sa dernière vérification et les dépendances touchées"* — and the link that
leads there is labelled *"Voir les composants santé"*. There were no components on it.

The consequence was not cosmetic. On 2026-08-05 ``tessera.preflight`` reported ClickHouse
``FAIL`` (``403 AUTHENTICATION_FAILED``) while that page showed everything operational, because
nothing it rendered could go red for a dependency. A page that cannot express a dependency
failure is not a monitoring page.

This exposes the prober that already existed and was wired to nothing but a CLI.
:func:`tessera.preflight.run_preflight` interrogates each dependency **by its own adapter**
(ADR 0026 — the eval archive through the loader the dashboards call, Postgres through the
ledger's ``connect``, ClickHouse/Prometheus/Ollama through theirs), never a neighbour, and it
distinguishes three outcomes where a dashboard usually has two:

* ``ok``    — it looked, and the answer was good;
* ``fail``  — it looked, and the answer was bad;
* ``blind`` — it could not look at all, which is **not** ``ok`` and not ``fail``.

That third state is the reason this endpoint is worth having rather than a green/red boolean.

**Cost.** These are live probes — a socket to Postgres, an HTTP round-trip to ClickHouse and
Prometheus, a model-list call to Ollama with a 4 s ceiling. The dashboard polls, so the result
is cached for :data:`_TTL_S` and computed off the event loop. The cache stores the *observation
time* alongside the report and the payload publishes it: a component list that does not say
when it was last checked invites the reader to assume "now", which is the failure this whole
surface exists to stop.
"""

from __future__ import annotations

import asyncio
import time
from threading import Lock
from typing import Final

from fastapi import APIRouter, Depends

from tessera.api.security import require_bearer
from tessera.preflight import PreflightReport, Verdict, run_preflight

router = APIRouter()

#: Seconds a probe result is reused. Short enough that an operator watching a component come
#: back sees it within one poll, long enough that a 10 s dashboard poll does not open a
#: Postgres connection and four sockets per viewer.
_TTL_S: Final = 15.0

#: Wall clock, not monotonic: the value is PUBLISHED to a browser that will render it as a
#: time, so it has to mean something outside this process.
_cache: tuple[float, PreflightReport] | None = None
_cache_lock = Lock()

#: What each check actually interrogates — the evidence, so a reader can tell a dependency
#: being down from a probe that never ran. Keyed by ``Check.name``; an unknown name degrades to
#: no subtitle rather than to a guess.
_INTERROGATES: Final[dict[str, str]] = {
    "eval-package": "import eval, import eval.runner",
    "eval-reports": "the report loader the dashboards call",
    "app-factory": "build_app()",
    "operator-key": "the operator assertion signing key",
    "postgres": "ln.connect — the ledger store's own connection",
    "clickhouse": "the ClickHouse adapter's own HTTP read",
    "prometheus": "the Prometheus adapter's own query",
    "ollama": "the chat backend's model list",
}

_HEADLINE: Final[dict[int, str]] = {0: "clear", 1: "fail", 2: "blind"}


def _probe() -> tuple[float, PreflightReport]:
    """Run the preflight, off the event loop, at most once per TTL."""
    global _cache
    with _cache_lock:
        cached = _cache
        if cached is not None and (time.time() - cached[0]) < _TTL_S:
            return cached
    # Deliberately outside the lock: a probe takes seconds, and holding the lock across it
    # would serialise every concurrent reader behind one round-trip. The worst case is two
    # concurrent probes on a cold cache, which is cheaper than a queue of blocked requests.
    observed_at = time.time()
    report = run_preflight()
    with _cache_lock:
        _cache = (observed_at, report)
    return _cache


@router.get("/observability/components", dependencies=[Depends(require_bearer)])
async def observability_components() -> dict[str, object]:
    """Every declared component, what was interrogated, and what it answered.

    Returns:
        ``components`` — one entry per check, each carrying ``name``, ``verdict``
        (``ok``/``fail``/``blind``/``skip``), ``detail`` (the probe's own evidence) and
        ``interrogates``; ``verdict`` — the headline (``clear``/``fail``/``blind``), which is
        ``blind`` whenever any check could not look, never ``clear``; and ``observed_at``, the
        instant the probe actually ran, which is NOT the instant of this request.
    """
    observed_at, report = await asyncio.to_thread(_probe)
    return {
        "observed_at": observed_at,
        "verdict": _HEADLINE[report.exit_code],
        "counts": {
            "total": len(report.checks),
            "ok": sum(1 for c in report.checks if c.verdict is Verdict.OK),
            "fail": len(report.failures),
            "blind": len(report.blind),
        },
        "components": [
            {
                "name": check.name,
                "verdict": check.verdict.value,
                "detail": check.detail,
                "interrogates": _INTERROGATES.get(check.name, ""),
            }
            for check in report.checks
        ],
    }
