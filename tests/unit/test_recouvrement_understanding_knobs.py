"""ADR 0053 slices 5-6 — the switch is a governed act, the threshold a measured number.

Three planes: the knob store (closed value spaces; 'active' unwritable without a stored
threshold, the threshold undeletable under 'active'), the resolver (shadow by default,
fail-open to shadow loudly, degradations spoken), and the graph (an accepted LLM verdict
routes as 'llm', a rejected attempt as 'regex_fallback', its fields preferred over the
digit parsers only when accepted). Plus the bench's threshold sweep — the calibration
read a governed write cites.
"""

from __future__ import annotations

from datetime import date

import pytest

from eval.intent_bench import (
    CaseVerdict,
    IntentCase,
    LlmCaseVerdict,
    _threshold_sweep,
)
from tessera.api import config_overrides
from tessera.api.config_overrides import (
    UNDERSTANDING_MODE_KEY,
    UNDERSTANDING_MODEL_KEY,
    UNDERSTANDING_THRESHOLD_KEY,
    UNDERSTANDING_TIMEOUT_KEY,
    KnobError,
    UnderstandingConfig,
    _interpret_understanding_rows,
    _validated_value,
    delete_override,
    resolve_understanding_config,
    set_override,
)
from tessera.observability import business_events as business_events_mod
from tessera.recouvrement.understanding import UnderstandingOutcome, UnderstandingVerdict


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    config_overrides._understanding_cache = None


# ── the knob store: closed value spaces, illegal states unrepresentable ────────────────


def test_mode_values_are_a_closed_set() -> None:
    assert _validated_value(UNDERSTANDING_MODE_KEY, "shadow") == "shadow"
    assert _validated_value(UNDERSTANDING_MODE_KEY, "active") == "active"
    with pytest.raises(KnobError, match="understanding mode"):
        _validated_value(UNDERSTANDING_MODE_KEY, "auto")


def test_threshold_lives_in_the_unit_interval() -> None:
    assert _validated_value(UNDERSTANDING_THRESHOLD_KEY, "0.75") == "0.75"
    for bad in ("1.5", "-0.1", "NaN", "huit"):
        with pytest.raises(KnobError):
            _validated_value(UNDERSTANDING_THRESHOLD_KEY, bad)


def test_timeout_is_bounded() -> None:
    assert _validated_value(UNDERSTANDING_TIMEOUT_KEY, "8") == "8"
    for bad in ("0", "-1", "61", "vite"):
        with pytest.raises(KnobError):
            _validated_value(UNDERSTANDING_TIMEOUT_KEY, bad)


async def test_active_is_unwritable_without_a_stored_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0053 §6: the flip cites a calibrated number or it does not happen."""

    async def _no_threshold(key: str) -> str | None:
        assert key == UNDERSTANDING_THRESHOLD_KEY
        return None

    monkeypatch.setattr(config_overrides, "_stored_value", _no_threshold)
    with pytest.raises(KnobError, match="requires a stored confidence threshold"):
        await set_override(
            UNDERSTANDING_MODE_KEY, "active", author="ops@credit-aurore.eu", reason="go live"
        )


async def test_threshold_is_undeletable_under_active_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The write guard's mirror: the illegal state cannot be reached sideways."""

    async def _active_mode(key: str) -> str | None:
        assert key == UNDERSTANDING_MODE_KEY
        return "active"

    monkeypatch.setattr(config_overrides, "_stored_value", _active_mode)
    with pytest.raises(KnobError, match="cannot be removed while understanding mode"):
        await delete_override(UNDERSTANDING_THRESHOLD_KEY)


# ── the resolver: shadow by default, degradations spoken ───────────────────────────────


def test_model_knob_shares_the_closed_catalogue() -> None:
    """The understanding model is validated by the same catalogue as the chat knobs."""
    assert _validated_value(UNDERSTANDING_MODEL_KEY, "gemma3:27b") == "gemma3:27b"
    with pytest.raises(KnobError, match="not in the catalogue"):
        _validated_value(UNDERSTANDING_MODEL_KEY, "mistral-uncatalogued:1b")


def test_panel_rows_carry_their_own_family_and_base() -> None:
    """ADR 0053 — the cockpit rows for the understanding knobs bind the right control.

    Until 2026-08-24 the four keys fell into the default ``model`` family: the panel
    labeled each row with the org fallback, offered the chat-model select for a mode,
    and announced the chat model as the base a revert would restore — three wrong
    answers on one governed surface.
    """
    from tessera.api.routes.settings import _knob_out
    from tessera.recouvrement.understanding import DEFAULT_TIMEOUT_S

    mode = _knob_out(UNDERSTANDING_MODE_KEY, None)
    assert (mode.kind, mode.options, mode.base) == ("choice", ["shadow", "active"], "shadow")

    threshold = _knob_out(UNDERSTANDING_THRESHOLD_KEY, None)
    assert (threshold.kind, threshold.options, threshold.base) == ("decimal", None, "—")

    timeout = _knob_out(UNDERSTANDING_TIMEOUT_KEY, None)
    assert (timeout.kind, timeout.base) == ("decimal", f"{DEFAULT_TIMEOUT_S:g}")

    # The shared catalogue select IS the right control for the model knob: its value
    # space is the same closed catalogue the chat-model rows edit against.
    assert _knob_out(UNDERSTANDING_MODEL_KEY, None).kind == "model"


def test_model_row_reaches_the_resolved_config() -> None:
    config = _interpret_understanding_rows(
        {UNDERSTANDING_MODEL_KEY: "gemma3:27b"}, default_timeout_s=8.0
    )
    assert config.model == "gemma3:27b"
    assert config.mode == "shadow"  # naming a model flips nothing by itself


def test_no_rows_resolve_to_shadow_defaults() -> None:
    config = _interpret_understanding_rows({}, default_timeout_s=8.0)
    assert config == UnderstandingConfig(mode="shadow", threshold=None, timeout_s=8.0)


def test_active_rows_resolve_with_their_threshold_and_timeout() -> None:
    config = _interpret_understanding_rows(
        {
            UNDERSTANDING_MODE_KEY: "active",
            UNDERSTANDING_THRESHOLD_KEY: "0.75",
            UNDERSTANDING_TIMEOUT_KEY: "5",
        },
        default_timeout_s=8.0,
    )
    assert config == UnderstandingConfig(mode="active", threshold=0.75, timeout_s=5.0)


def test_active_without_threshold_degrades_to_shadow_loudly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A legacy/hand-edited store cannot buy silent active mode (ADR 0026)."""
    config = _interpret_understanding_rows(
        {UNDERSTANDING_MODE_KEY: "active"}, default_timeout_s=8.0
    )
    assert config.mode == "shadow"
    assert "serving shadow" in capsys.readouterr().err


async def test_resolver_fails_open_to_shadow_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A turn is never blocked on the override store; the degradation is spoken."""

    async def _broken_schema() -> None:
        raise RuntimeError("store down")

    monkeypatch.setattr(config_overrides, "ensure_overrides_schema", _broken_schema)
    config = await resolve_understanding_config()
    assert config.mode == "shadow"
    assert "serving shadow" in capsys.readouterr().err


async def test_resolver_caches_within_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """One store read serves the TTL window; a write invalidates (same seam as the ceiling)."""
    reads = 0

    async def _counting_read() -> UnderstandingConfig:
        nonlocal reads
        reads += 1
        return UnderstandingConfig(mode="shadow", threshold=None, timeout_s=8.0)

    monkeypatch.setattr(config_overrides, "_read_understanding_config", _counting_read)
    await resolve_understanding_config()
    await resolve_understanding_config()
    assert reads == 1
    config_overrides._forget_cached_understanding()
    await resolve_understanding_config()
    assert reads == 2


# ── the graph: accepted verdict routes as llm, rejected attempt as regex_fallback ──────


@pytest.fixture
def _memory_ledger() -> None:
    business_events_mod.set_business_event_store(business_events_mod.InMemoryBusinessEventStore())


def _routing_state(llm_understanding: dict[str, object] | None) -> dict[str, object]:
    state: dict[str, object] = {
        "conversation_id": "conv-knobs",
        "turn_id": "turn-knobs",
        "case_id": "RC-2048",
        "message": "Découpe le montant dû en trois versements égaux",
        "surface": "dedicated-ui",
        "language": "fr",
        "model": "recouvrement_collections_v1",
        "environment": "dev",
    }
    if llm_understanding is not None:
        state["llm_understanding"] = llm_understanding
    return state


def test_an_accepted_verdict_routes_as_llm(_memory_ledger: None) -> None:
    from tessera.agent.recouvrement import route_recouvrement_intent

    routed = route_recouvrement_intent(
        _routing_state(
            {
                "accepted": True,
                "intent": "propose_schedule",
                "confidence": 0.91,
                "duration_months": 3,
                "requested_time": None,
            }
        )  # type: ignore[arg-type]
    )
    assert routed["intent"] == "propose_schedule"
    assert routed["intent_confidence"] == 0.91
    rows = business_events_mod.business_event_rows(
        agent_id="recouvrement", conversation_id="conv-knobs", turn_id="turn-knobs"
    )
    assert rows[-1]["payload"]["intent_source"] == "llm"


def test_a_rejected_attempt_routes_as_regex_fallback(_memory_ledger: None) -> None:
    """The model was tried and lost — the trail must say so, distinctly from plain regex."""
    from tessera.agent.recouvrement import route_recouvrement_intent

    routed = route_recouvrement_intent(
        _routing_state({"accepted": False, "intent": None, "confidence": None})  # type: ignore[arg-type]
    )
    # No word list matches this utterance: the router serves its default.
    assert routed["intent"] == "check_contact_rule"
    rows = business_events_mod.business_event_rows(
        agent_id="recouvrement", conversation_id="conv-knobs", turn_id="turn-knobs"
    )
    assert rows[-1]["payload"]["intent_source"] == "regex_fallback"


def test_no_attempt_routes_as_regex(_memory_ledger: None) -> None:
    from tessera.agent.recouvrement import route_recouvrement_intent

    route_recouvrement_intent(_routing_state(None))  # type: ignore[arg-type]
    rows = business_events_mod.business_event_rows(
        agent_id="recouvrement", conversation_id="conv-knobs", turn_id="turn-knobs"
    )
    assert rows[-1]["payload"]["intent_source"] == "regex"


def test_accepted_llm_fields_serve_and_rejected_ones_do_not(_memory_ledger: None) -> None:
    """'douze mois' becomes 12 through the model — but only an ACCEPTED model."""
    from tessera.agent.recouvrement import (
        RecouvrementCaseSnapshot,
        extract_recouvrement_slots,
    )

    case = RecouvrementCaseSnapshot(
        case_id="RC-2048",
        client="M. D.",
        amount_due_label="840,00 €",
        amount_due=840.0,
        days_late=32,
        missed_promise_date=date(2026, 6, 12),
        contact_window_start="08:00",
        contact_window_end="20:00",
        recommended_channel="appel sortant",
        alternative_channel="email de confirmation",
    )
    accepted_state = _routing_state(
        {
            "accepted": True,
            "intent": "propose_schedule",
            "confidence": 0.9,
            "duration_months": 12,
            "requested_time": None,
        }
    )
    accepted_state.update(
        {"case": case, "intent": "propose_schedule", "message": "Étale sur douze mois"}
    )
    slots = extract_recouvrement_slots(accepted_state)["slots"]  # type: ignore[arg-type,index]
    assert slots["requested_months"] == 12  # type: ignore[index]

    rejected_state = _routing_state({"accepted": False, "intent": None, "duration_months": 12})
    rejected_state.update(
        {"case": case, "intent": "propose_schedule", "message": "Étale sur douze mois"}
    )
    slots = extract_recouvrement_slots(rejected_state)["slots"]  # type: ignore[arg-type,index]
    assert slots["requested_months"] == 3  # the digit parser's fallback default


# ── the sweep: the calibration read a governed write cites ─────────────────────────────


def _case(case_id: str, expected: str) -> IntentCase:
    return IntentCase(
        id=case_id,
        language="fr",
        utterance="peu importe",
        expected_intent=expected,
        expected_fields={},
        provenance="hand_authored",
        note=None,
    )


def _llm_verdict(case: IntentCase, intent: str, confidence: float) -> LlmCaseVerdict:
    return LlmCaseVerdict(
        case=case,
        outcome=UnderstandingOutcome(
            status="verdict",
            verdict=UnderstandingVerdict(
                intent=intent, confidence=confidence, duration_months=None, requested_time=None
            ),
            detail=None,
            model="fake",
            prompt_version="v1",
            latency_ms=1.0,
        ),
        correct=intent == case.expected_intent,
        field_exact={},
    )


def _regex_verdict(case: IntentCase, intent: str) -> CaseVerdict:
    return CaseVerdict(
        case=case,
        predicted_intent=intent,
        matched=True,
        correct=intent == case.expected_intent,
        predicted_fields={},
        field_exact={},
    )


def test_threshold_sweep_finds_the_floor_that_keeps_good_verdicts_and_drops_bad_ones() -> None:
    """LLM right at 0.9, wrong at 0.4; regex right where the LLM is wrong: best t ∈ (0.4, 0.9]."""
    a, b = _case("a", "summarize_case"), _case("b", "draft_reminder")
    llm = [
        _llm_verdict(a, "summarize_case", 0.9),  # right, confident
        _llm_verdict(b, "propose_schedule", 0.4),  # wrong, hesitant
    ]
    regex = {"a": _regex_verdict(a, "check_contact_rule"), "b": _regex_verdict(b, "draft_reminder")}
    sweep = _threshold_sweep(llm, regex)
    suggested = sweep["suggested"]
    assert suggested["correct"] == 2  # type: ignore[index]
    assert 0.4 < float(suggested["threshold"]) <= 0.9  # type: ignore[arg-type,index]
    points = {point["threshold"]: point["correct"] for point in sweep["points"]}  # type: ignore[union-attr]
    assert points[0.0] == 1  # trusting everything keeps the hesitant wrong verdict
    assert points[1.0] == 1  # trusting nothing loses the confident right one
