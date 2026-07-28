"""The observability READ endpoints serve concurrently, not one-at-a-time.

The dashboard fires ~25 reads at once. When the handlers were ``async def`` doing SYNCHRONOUS
DB I/O inline, every read blocked the single event loop, so N concurrent reads took Nx a single
read (measured on the live agent: 22 reads = 4.2 s sequential AND 3.9 s concurrent — zero gain).
The fix makes the blocking reads run OFF the loop, in Starlette's threadpool, so concurrent reads
run in parallel. These tests lock both halves:

* structural — the ledger-heavy read handlers are synchronous ``def`` (Starlette threadpools
  them); a regression back to ``async def`` (which would re-block the loop) fails here;
* behavioural — a ``def`` handler doing a blocking sleep runs concurrently under load, while the
  equivalent ``async def`` handler serializes. This is the exact before/after of the fix.
"""

from __future__ import annotations

import asyncio
import inspect
import time

import anyio.to_thread
import httpx
from fastapi import FastAPI

from tessera.api.routes import observability as obs

# Read handlers whose bodies do blocking ledger/score I/O — they MUST be synchronous so Starlette
# runs them in its threadpool instead of on the event loop. (A representative, load-bearing set:
# every one is fired by a SURVEILLER / time-rail page.)
_MUST_BE_SYNC = frozenset(
    {
        "/observability/data-range",
        "/observability/timeline",
        "/observability/least-privilege",
        "/observability/pii-leak",
        "/observability/toxicity",
        "/observability/firewall-efficacy",
        "/observability/refusal",
        "/observability/conformance",
        "/observability/anomalies",
        "/observability/reliability",
        "/observability/compliance",
        "/observability/proofs",
        "/observability/cost",
        "/observability/tool-validity",
    }
)


def _get_endpoints() -> dict[str, object]:
    out: dict[str, object] = {}
    for route in obs.router.routes:
        methods: set[str] = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", None)
        if "GET" in methods and path is not None:
            out[path] = getattr(route, "endpoint", None)
    return out


def test_ledger_heavy_reads_are_synchronous_so_they_run_off_the_event_loop() -> None:
    eps = _get_endpoints()
    for path in _MUST_BE_SYNC:
        assert path in eps, f"{path} missing from the observability router"
        endpoint = eps[path]
        assert not inspect.iscoroutinefunction(endpoint), (
            f"{path} is async def — its blocking DB read would serialize on the event loop; "
            "it must be a synchronous def so Starlette runs it in the threadpool"
        )


def test_the_vast_majority_of_reads_are_threadpool_synchronous() -> None:
    """A blunt floor: the read surface is overwhelmingly synchronous (threadpool-served)."""
    eps = _get_endpoints()
    sync = [p for p, fn in eps.items() if fn is not None and not inspect.iscoroutinefunction(fn)]
    # 106 were converted; keep a floor well below that so adding a legitimately-async read (async
    # psycopg) doesn't trip this, but a wholesale regression to async does.
    assert len(sync) >= 90, f"only {len(sync)} synchronous read handlers — reads are re-blocking"


def _drive(app: FastAPI, path: str, n: int) -> float:
    async def run() -> float:
        # Ensure the threadpool can admit all N at once (anyio's default is 40).
        anyio.to_thread.current_default_thread_limiter().total_tokens = max(40, n + 4)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            started = time.perf_counter()
            await asyncio.gather(*(client.get(path) for _ in range(n)))
            return time.perf_counter() - started

    return asyncio.run(run())


def test_sync_handlers_run_concurrently_and_async_ones_would_not() -> None:
    """The mechanism the fix relies on: a blocking ``def`` parallelizes; ``async`` serializes."""
    app = FastAPI()
    sleep_s = 0.15
    n = 10

    @app.get("/sync-read")
    def sync_read() -> dict[str, bool]:  # sync -> Starlette threadpool -> parallel
        time.sleep(sleep_s)
        return {"ok": True}

    @app.get("/async-read")
    async def async_read() -> (
        dict[str, bool]
    ):  # async -> ON the loop -> a blocking sleep serializes
        time.sleep(sleep_s)  # noqa: ASYNC251 (deliberately blocking, to show serialization)
        return {"ok": True}

    parallel = _drive(app, "/sync-read", n)
    serial = _drive(app, "/async-read", n)

    # N sync handlers each sleeping 0.15 s finish in ~one sleep (threadpool), not Nx.
    assert parallel < sleep_s * (n / 2), f"sync reads did not parallelize: {parallel:.2f}s"
    # The async equivalent blocks the loop and drains one-at-a-time — ~Nx slower.
    assert serial > sleep_s * (n - 2), f"async read did not serialize as expected: {serial:.2f}s"
    assert (
        serial > parallel * 3
    ), f"no concurrency gain: parallel={parallel:.2f}s serial={serial:.2f}s"
