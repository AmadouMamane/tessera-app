"""Control-plane store reads emit a span — the cockpit stops being a black box to itself.

The agent runtime is instrumented span by span. The control plane that judges it was not. The
Phoenix trace of the cockpit's slowest endpoint — ``GET /observability/fleet``, 3 938 ms — was
**one span, zero children**, and not one millisecond of it was attributed to anything. The HTTP
layer was auto-instrumented; the stores underneath it (Postgres, ClickHouse, Prometheus, the
ledger) emitted nothing at all. A governance platform that cannot explain its own latency is
applying to others a rule it exempts itself from.

Every control-plane read now goes through :func:`store_read`, which records four things:

* the **store** — ``postgres`` / ``clickhouse`` / ``prometheus`` / ``file``;
* the **operation** — the question, named: ``audit_ledger.payloads_all``;
* the **duration** — the span's own;
* the **row count** — and this is the field that carries the finding. Duration tells you a read
  was slow. The row count tells you *why*, and it is the only one that turns six full 29 600-row
  scans from one opaque four-second box into six named scans a reader can indict.

It counts rows **materialised**, never rows scanned. That distinction is the whole point: an
aggregate that groups 29 600 rows inside the database and hands back 29 is the *fix*, and must
not read as the offence. What hurts is what crosses the wire and lands in Python.

Two consumers of the one measurement:

* the **span**, for the operator's cascade in Phoenix;
* :func:`recording`, an in-process recorder, so "no request path may load the whole ledger" is a
  test with a number in it (``tests/unit/test_ledger_read_budget.py``) instead of a hope.

The tracer is *fetched*, never *configured*. An instrumentation seam that installed a tracer
provider would be deciding for the application that imports it. With no provider — the unit
suite — OpenTelemetry hands back a no-op tracer, the span costs nothing, and the recorder keeps
working: which is why the ratchet needs no collector to run.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from opentelemetry import trace

from tessera import __version__
from tessera.observability.semconv import (
    TESSERA_STORE,
    TESSERA_STORE_OPERATION,
    TESSERA_STORE_ROWS,
    TESSERA_STORE_TARGET,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["StoreRead", "recording", "store_read"]

_TRACER_NAME: Final = "tessera.control_plane"

#: Span-name prefix, so the cascade groups them at a glance in Phoenix.
_SPAN_PREFIX: Final = "store.read"


@dataclass(slots=True)
class StoreRead:
    """One control-plane store read: what was asked, and how much of the store came back."""

    store: str
    operation: str
    target: str | None = None
    #: Rows materialised. ``None`` = the read did not declare a count (never "zero").
    rows: int | None = None
    duration_ms: float = 0.0

    def rows_read(self, count: int) -> None:
        """Declare how many rows this read actually brought back into memory."""
        self.rows = count


_RECORDER: ContextVar[list[StoreRead] | None] = ContextVar("tessera_store_reads", default=None)


@contextmanager
def recording() -> Iterator[list[StoreRead]]:
    """Collect every store read performed inside the block — including in threads it spawns.

    ``asyncio.to_thread`` copies the calling context, so a read pushed off the event loop lands
    in the same list. That is not incidental: this lot moved the control plane's blocking reads
    into threads, and a budget that stopped counting them the moment they moved would have
    certified the very change it exists to police.
    """
    reads: list[StoreRead] = []
    token = _RECORDER.set(reads)
    try:
        yield reads
    finally:
        _RECORDER.reset(token)


@contextmanager
def store_read(store: str, operation: str, *, target: str | None = None) -> Iterator[StoreRead]:
    """Instrument one control-plane store read: a span, and a row count on it.

    Args:
        store: The store touched — ``postgres``, ``clickhouse``, ``prometheus``, ``file``.
        operation: The question, named. Appears verbatim as the span name in the cascade.
        target: The table / metric / file addressed.

    Yields:
        The :class:`StoreRead` to declare the row count on: ``read.rows_read(len(rows))``.
    """
    record = StoreRead(store=store, operation=operation, target=target)
    started = time.perf_counter()
    tracer = trace.get_tracer(_TRACER_NAME, __version__)
    with tracer.start_as_current_span(f"{_SPAN_PREFIX} {operation}") as span:
        try:
            yield record
        finally:
            record.duration_ms = (time.perf_counter() - started) * 1000.0
            span.set_attribute(TESSERA_STORE, store)
            span.set_attribute(TESSERA_STORE_OPERATION, operation)
            if target is not None:
                span.set_attribute(TESSERA_STORE_TARGET, target)
            if record.rows is not None:
                span.set_attribute(TESSERA_STORE_ROWS, record.rows)
            sink = _RECORDER.get()
            if sink is not None:
                sink.append(record)
