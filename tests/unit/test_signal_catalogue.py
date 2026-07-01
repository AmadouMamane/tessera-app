"""Unit tests for the Signal catalogue payload assembler (pure, no I/O)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from tessera.guard.decisions import Policy
from tessera.observability.eval_data import CategoryStat, EvalSnapshot, SessionRow
from tessera.observability.signal_catalogue import _assemble


def _session(case: str, lang: str, cat: str, *, passed: bool) -> SessionRow:
    return SessionRow(
        case_id=case,
        language=lang,
        category=cat,
        title=f"Question {case}",
        passed=passed,
        needs_escalation=not passed,
        tools=(),
        duration_ms=1000.0,
        input_tokens=10,
        output_tokens=5,
        response="r",
        started_at="2026-06-16T05:51:00",
    )


def _snapshot() -> EvalSnapshot:
    sessions = (
        _session("a", "fr", "pii_leak", passed=True),
        _session("b", "de", "pii_leak", passed=False),
        _session("c", "en", "pii_leak", passed=False),
        _session("d", "fr", "hallucination", passed=False),
        _session("e", "fr", "language_mixing", passed=True),
    )
    cats = (
        CategoryStat(category="pii_leak", total=10, passed=3),
        CategoryStat(category="hallucination", total=12, passed=1),
        CategoryStat(category="language_mixing", total=4, passed=4),
    )
    return EvalSnapshot(
        model="llama3.2:3b",
        run_at="20260616T055117Z",
        catalogue_version="v1.0",
        total=26,
        passed=8,
        languages=(("fr", 3), ("de", 1), ("en", 1)),
        categories=cats,
        escalations=0,
        tool_invocations=0,
        sessions=sessions,
    )


def _policy() -> Policy:
    return Policy(
        version=1,
        tools={},
        prompt_injection_deny=(re.compile("x"), re.compile("y")),
        prompt_injection_transforms=(),
        pii_patterns=(re.compile("z"),),
    )


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, tzinfo=UTC)


def test_one_signal_per_present_category_sorted_by_severity() -> None:
    payload = _assemble(_snapshot(), _policy(), _now(), "fr")
    signals = payload["signals"]
    assert payload["total_signals"] == 3  # type: ignore[index]
    # pii_leak (critical) ranks before hallucination/language_mixing.
    assert signals[0]["name"] == "pii_leak_rate"  # type: ignore[index]
    assert signals[0]["severity"] == "critical"  # type: ignore[index]


def test_quality_is_real_pass_rate_and_status_reflects_sample_size() -> None:
    by_name = {s["name"]: s for s in _assemble(_snapshot(), _policy(), _now(), "fr")["signals"]}  # type: ignore[union-attr]
    assert by_name["pii_leak_rate"]["quality"] == 30  # 3/10
    assert by_name["hallucination_rate"]["quality"] == 8  # round(1/12*100)
    # Under-sampled category (< 8 cases) shows as "evaluation", not "active".
    assert by_name["language_routing_error"]["status"] == "evaluation"
    assert by_name["pii_leak_rate"]["status"] == "active"


def test_guard_rows_only_for_guard_sourced_signals() -> None:
    by_name = {s["name"]: s for s in _assemble(_snapshot(), _policy(), _now(), "fr")["signals"]}  # type: ignore[union-attr]
    # pii_leak is guard-enforced -> real policy composition surfaced.
    guard = by_name["pii_leak_rate"]["detail"]["guard"]
    assert {"label": "Motifs de blocage", "value": "2"} in guard
    assert {"label": "Motifs PII", "value": "1"} in guard
    # hallucination is eval-only -> no guard composition.
    assert by_name["hallucination_rate"]["detail"]["guard"] == []


def test_distribution_and_outcome_match_real_sessions() -> None:
    by_name = {s["name"]: s for s in _assemble(_snapshot(), _policy(), _now(), "fr")["signals"]}  # type: ignore[union-attr]
    detail = by_name["pii_leak_rate"]["detail"]
    dist = {b["label"]: b["count"] for b in detail["distribution"]}
    assert dist == {"FR": 1, "DE": 1, "EN": 1}
    outcome = {b["label"]: b["count"] for b in detail["outcome"]}
    assert outcome == {"Réussis": 3, "Échecs": 7}  # 3 passed of 10


def test_kpis_and_provenance_are_derived() -> None:
    payload = _assemble(_snapshot(), _policy(), _now(), "fr")
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["total"] == "3"
    assert kpis["active"] == "2"
    assert kpis["evaluation"] == "1"
    assert kpis["critical"] == "1"
    assert payload["sources"] == ["Eval", "Guard"]
    assert payload["run_at"] == "16/06/2026"
