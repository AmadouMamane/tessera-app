"""The control-plane read seam: what it puts on the span, and what it must never do.

The finding this closes is not a slow query. It is that the observability platform could not
explain its own slowest endpoint: the Phoenix trace of a 3 938 ms ``GET /observability/fleet``
was ONE span with ZERO children, and not a millisecond of it was attributed to anything.

So the contract is pinned here, because a row count that silently stops being emitted would take
the read-budget ratchet down with it — it counts through this seam.
"""

from __future__ import annotations

import asyncio

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tessera.observability.semconv import (
    TESSERA_STORE,
    TESSERA_STORE_OPERATION,
    TESSERA_STORE_ROWS,
    TESSERA_STORE_TARGET,
)
from tessera.observability.store_spans import recording, store_read


def _exporter() -> InMemorySpanExporter:
    """A provider whose spans we can read back.

    ``trace.set_tracer_provider`` is a once-per-process global, so this attaches an in-memory
    processor to whatever provider is already installed rather than fighting it.
    """
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


class TestTheSpan:
    def test_the_span_carries_the_store_the_operation_and_the_row_count(self) -> None:
        """The row count is the field that carries the finding, so it is the field that is pinned.

        Duration says a read was slow. The row count says WHY, and it is the only one that makes
        six full 29 600-row scans legible as six full scans instead of one opaque four-second box.
        """
        exporter = _exporter()

        with store_read("postgres", "audit_ledger.payloads_all", target="audit_ledger") as read:
            read.rows_read(25_716)

        span = next(s for s in exporter.get_finished_spans() if s.name.startswith("store.read"))
        assert span.name == "store.read audit_ledger.payloads_all"
        assert span.attributes is not None
        assert span.attributes[TESSERA_STORE] == "postgres"
        assert span.attributes[TESSERA_STORE_OPERATION] == "audit_ledger.payloads_all"
        assert span.attributes[TESSERA_STORE_TARGET] == "audit_ledger"
        assert span.attributes[TESSERA_STORE_ROWS] == 25_716

    def test_an_uncounted_read_says_nothing_rather_than_claiming_zero(self) -> None:
        """A read that never declared a count must not be recorded as having read NOTHING.

        "I did not count" and "I read no rows" are different facts, and a budget that confused
        them would wave through exactly the read that forgot to instrument itself.
        """
        exporter = _exporter()

        with store_read("clickhouse", "business_events.rows"):
            pass

        span = next(
            s for s in exporter.get_finished_spans() if s.name == "store.read business_events.rows"
        )
        assert span.attributes is not None
        assert TESSERA_STORE_ROWS not in span.attributes

    def test_the_seam_never_installs_a_tracer_provider(self) -> None:
        """Instrumentation observes; it does not decide for the application that imports it.

        ``store_spans`` is imported by ``tessera.guard.ledger_store`` — the audit ledger. If
        importing the ledger configured a tracer provider (and therefore an exporter, and
        therefore a network destination), the guard would be shipping telemetry off-box because
        somebody read a row. It fetches a tracer; it never configures one.
        """
        import inspect

        from tessera.observability import store_spans

        source = inspect.getsource(store_spans)
        assert "set_tracer_provider" not in source
        assert (
            "traces.configure" not in source
            and "from tessera.observability import traces" not in source
        )


class TestTheRecorder:
    def test_reads_are_recorded_with_their_duration(self) -> None:
        with recording() as reads, store_read("prometheus", "prometheus.instant") as read:
            read.rows_read(6)

        assert len(reads) == 1
        assert reads[0].store == "prometheus"
        assert reads[0].rows == 6
        assert reads[0].duration_ms >= 0.0

    def test_a_read_inside_a_thread_still_lands_in_the_recorder(self) -> None:
        """This lot pushed the control plane's blocking reads into ``asyncio.to_thread``.

        ``contextvars`` are copied into the worker, so the read is still counted. If they were
        not, the row budget would have quietly stopped policing every read that moved off the
        event loop — certifying the very change it exists to check.
        """

        def read_something() -> None:
            with store_read("postgres", "audit_ledger.payloads_all") as read:
                read.rows_read(25_716)

        async def drive() -> None:
            await asyncio.to_thread(read_something)

        with recording() as reads:
            asyncio.run(drive())

        assert [r.rows for r in reads] == [25_716]

    def test_nothing_is_recorded_outside_a_recording_block(self) -> None:
        """The recorder is opt-in: a production read must not accumulate in a process-wide list."""
        with store_read("postgres", "audit_ledger.payloads_all") as read:
            read.rows_read(1)

        with recording() as reads:
            pass

        assert reads == []
