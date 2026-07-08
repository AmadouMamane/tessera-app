"""Scheduled canary invocation + synthetic isolation (ADR 0019 §I4).

Hermetic — no LLM, no live ledger. The production invoker (``InProcessChatInvoker``) drives the
real graph, so like the seal's ``Rfc3161Provider`` it is an integration/live concern; here a
``_FakeInvoker`` stands in so the cycle, the posture decision, the S1 emission, the descriptor
freshness feed, and the synthetic-metrics exclusion are exercised in isolation.

The load-bearing acceptance is §4: a synthetic canary turn's events must NEVER enter business
metrics — proven at both the emit-time counter guard and the read seam every business surface
flows through.
"""

from __future__ import annotations

from types import SimpleNamespace

from tessera.agent import canary
from tessera.guard import audit
from tessera.guard.audit import CANARY_INVOCATION_TYPE
from tessera.observability import business_events as be, quality_nets as qn
from tessera.observability.quality_nets import canary_descriptor


class _FakeInvoker:
    """A canary invoker double: returns a configurable outcome, never touches the graph."""

    def __init__(
        self, *, ok: bool = True, error: str | None = None, duration_ms: float = 1.0
    ) -> None:
        self._ok = ok
        self._error = error
        self._duration = duration_ms

    async def invoke(
        self, agent_id: str, *, conversation_id: str, turn_id: str
    ) -> canary.CanaryTurnOutcome:
        return canary.CanaryTurnOutcome(ok=self._ok, duration_ms=self._duration, error=self._error)


# ── scheduled selection + posture (the single source of the scheduling decision) ──


def test_scheduled_canaries_is_recouvrement_only() -> None:
    # Only recouvrement declares a cadence (the meaningful business-metrics target); the QA
    # agents declare in_process_chat with no cadence, hello-agent is `none`.
    scheduled = {s.agent_id: s.cadence_s for s in canary.scheduled_canaries()}
    assert scheduled == {"recouvrement": 3600}


def test_posture_idle_by_default() -> None:
    # The master switch is OFF by default: a cadence is declared but nothing fires (no behaviour
    # change), and the posture line says so — the scheduler idles, honestly.
    posture = canary.canary_posture()
    assert posture["enabled"] is False
    assert posture["scheduling"] is False
    assert posture["scheduled"] == [{"agent_id": "recouvrement", "cadence_s": 3600}]


def test_posture_schedules_when_operator_enables_it() -> None:
    settings = SimpleNamespace(observability=SimpleNamespace(canary_scheduler_enabled=True))
    posture = canary.canary_posture(settings)  # type: ignore[arg-type]
    assert posture["enabled"] is True
    assert posture["scheduling"] is True  # enabled AND a cadence is declared


# ── the cycle: one invocation → verdict + exactly one S1 event ────────────────────


async def test_run_canary_cycle_green_emits_one_s1(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(audit, "emit_canary_invocation", lambda **kw: captured.update(kw))
    result = await canary.run_canary_cycle("recouvrement", invoker=_FakeInvoker(ok=True))
    assert result.verdict == "green"
    assert result.binding == "in_process_chat"
    assert captured["agent_id"] == "recouvrement"
    assert captured["verdict"] == "green"
    assert captured["binding"] == "in_process_chat"
    # The audited ids are the ones the invocation actually used (reconstructable in État à date).
    assert captured["conversation_id"] == result.conversation_id
    assert captured["turn_id"] == result.turn_id


async def test_run_canary_cycle_red_still_emits_s1(monkeypatch) -> None:
    # A failed invocation is RED, never a fabricated green — and it STILL emits an S1 event: the
    # invocation happened, and a governed act (even a failed one) lives in the ledger.
    captured: dict[str, object] = {}
    monkeypatch.setattr(audit, "emit_canary_invocation", lambda **kw: captured.update(kw))
    result = await canary.run_canary_cycle(
        "recouvrement", invoker=_FakeInvoker(ok=False, error="boom")
    )
    assert result.verdict == "red"
    assert result.error == "boom"
    assert captured["verdict"] == "red"
    assert captured["error"] == "boom"


def test_emit_canary_invocation_stamps_synthetic_in_the_ledger(monkeypatch) -> None:
    # Hermetic: capture the entry at the chain-append seam (no real file write — the S1 chain
    # itself is exercised by the audit-chain suite).
    captured: dict[str, object] = {}
    monkeypatch.setattr(audit, "_append_to_chain", lambda entry, *_a, **_k: captured.update(entry))
    audit.emit_canary_invocation(
        agent_id="recouvrement",
        binding="in_process_chat",
        verdict="green",
        conversation_id="conv-canary",
        turn_id="turn-canary",
    )
    assert captured["type"] == CANARY_INVOCATION_TYPE
    assert captured["synthetic"] is True  # a reader can never mistake a probe for a real turn
    assert captured["agent_id"] == "recouvrement"
    assert captured["verdict"] == "green"


# ── freshness feeds the existing descriptor (via the durable S1 entry) ────────────


def test_canary_s1_feeds_descriptor_synthetic_run(monkeypatch) -> None:
    # The descriptor reads the latest canary S1 entry for the agent; stand one in and assert it
    # surfaces as the synthetic-run facet (the real ledger read is the audit suite's concern).
    monkeypatch.setattr(
        qn,
        "_latest_canary_run",
        lambda agent_id: {
            "type": CANARY_INVOCATION_TYPE,
            "agent_id": agent_id,
            "occurred_at": "2026-07-08T12:00:00+00:00",
            "verdict": "green",
        },
    )
    descriptor = canary_descriptor("recouvrement")
    assert descriptor is not None
    assert descriptor["cadence_s"] == 3600  # the declared cadence rides the descriptor
    run = descriptor["synthetic_run"]
    assert isinstance(run, dict)
    assert run["status"] == "green"
    assert run["ran_at"] == "2026-07-08T12:00:00+00:00"


def test_descriptor_reports_never_when_no_canary_ran(monkeypatch) -> None:
    # No canary S1 entry ⇒ the synthetic-run facet is honestly `never`, distinct from the
    # real-telemetry `status` — the two freshnesses never blur.
    monkeypatch.setattr(qn, "_latest_canary_run", lambda agent_id: None)  # noqa: ARG005
    descriptor = canary_descriptor("recouvrement")
    assert descriptor is not None
    assert descriptor["synthetic_run"] == {
        "status": "never",
        "ran_at": None,
        "age_seconds": None,
        "error": None,
    }


# ── §4 acceptance: a synthetic turn NEVER enters business metrics ─────────────────


class _SpyCounter:
    """Counts ``inc`` calls through the labels()→inc() chain the real Prometheus counter uses."""

    def __init__(self) -> None:
        self.incs = 0

    def labels(self, **_kwargs: object) -> _SpyCounter:
        return self

    def inc(self, amount: float = 1.0) -> None:
        self.incs += 1


def _metric_event(*, synthetic: bool) -> be.BusinessEvent:
    return be.BusinessEvent(
        event_name="test.metric_probe",
        timestamp="2026-07-08T12:00:00+00:00",
        agent_id="recouvrement",
        conversation_id="c",
        turn_id="t",
        synthetic=synthetic,
        classification=be.BusinessEventClassification(metric_input=True),
    )


def test_synthetic_event_never_moves_a_business_counter(monkeypatch) -> None:
    spy = _SpyCounter()
    monkeypatch.setattr(be, "BUSINESS_EVENTS_TOTAL", spy)
    be._emit_metrics(_metric_event(synthetic=True))
    assert spy.incs == 0  # guarded at emit: a canary probe never moves a business counter


def test_non_synthetic_metric_event_does_move_the_counter(monkeypatch) -> None:
    # Control: without the synthetic mark, the very same event DOES count — proving the guard is
    # what excludes synthetic, not some unrelated no-op.
    spy = _SpyCounter()
    monkeypatch.setattr(be, "BUSINESS_EVENTS_TOTAL", spy)
    be._emit_metrics(_metric_event(synthetic=False))
    assert spy.incs >= 1


def test_synthetic_event_excluded_from_business_reads() -> None:
    be.reset_business_event_store()
    be.record_business_event(
        event_name=be.BusinessEventName.INTENT_ROUTED,
        agent_id="canary-probe-agent",
        conversation_id="c1",
        turn_id="t1",
        synthetic=True,
    )
    # The one read seam every business surface (Métier, scores, signals, coverage) flows through.
    assert be.business_event_rows(agent_id="canary-probe-agent") == []
    included = be.business_event_rows(agent_id="canary-probe-agent", include_synthetic=True)
    assert len(included) == 1
    assert included[0]["synthetic"] is True


def test_synthetic_turn_context_stamps_and_excludes() -> None:
    be.reset_business_event_store()
    # The scheduler wraps the whole turn; an event emitted with NO explicit synthetic arg inherits
    # the mark from the context — the graph's emitters need no change.
    with be.synthetic_turn():
        be.record_business_event(
            event_name=be.BusinessEventName.INTENT_ROUTED,
            agent_id="ctx-agent",
            conversation_id="c2",
            turn_id="t2",
        )
    assert be.business_event_rows(agent_id="ctx-agent") == []
    assert be.is_synthetic_turn() is False  # the mark is scoped to the context, restored on exit


def test_non_synthetic_event_is_visible() -> None:
    be.reset_business_event_store()
    be.record_business_event(
        event_name=be.BusinessEventName.INTENT_ROUTED,
        agent_id="real-agent",
        conversation_id="c3",
        turn_id="t3",
    )
    rows = be.business_event_rows(agent_id="real-agent")
    assert len(rows) == 1
    assert rows[0]["synthetic"] is False
