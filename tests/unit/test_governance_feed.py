"""Unit tests for the governed-activity feed (overview enrichment #2).

Covers: only real S1 governance events surface (guard denials are excluded);
consecutive identical routings collapse with a count; as-of-T filtering; and
model/prompt/policy version changes from bundle lineage become deploy events.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability import governance_feed as gov_mod, replay as replay_mod

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_T0 = "2026-06-12T10:00:00+00:00"
_T1 = "2026-06-12T10:00:10+00:00"
_T2 = "2026-06-12T10:00:20+00:00"
_T3 = "2026-06-12T10:00:30+00:00"


def _routing(at: str, agent: str, reason: str, h: str) -> dict[str, object]:
    return {
        "type": "tessera.agent.routing",
        "occurred_at": at,
        "agent_id": agent,
        "reason": reason,
        "handoff": False,
        "actor": "system",
        "hash": h,
    }


def _handoff(at: str, frm: str, to: str, h: str) -> dict[str, object]:
    return {
        "type": "tessera.agent.handoff",
        "occurred_at": at,
        "agent_id": to,
        "from_agent": frm,
        "to_agent": to,
        "reason": f"intent->{to}",
        "actor": "system",
        "hash": h,
    }


def _denial(at: str) -> dict[str, object]:
    return {
        "type": "tessera.guard.audit",
        "occurred_at": at,
        "target": "user_input",
        "outcome": "denied",
    }


def _seed_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "audit.log"
    rows = [
        _routing(_T0, "support-client", "stay->support-client", "h0"),
        _routing(_T1, "support-client", "stay->support-client", "h1"),
        _routing(_T2, "support-client", "stay->support-client", "h2"),
        _handoff(_T3, "support-client", "onboarding", "h3"),
        _denial(_T2),  # guard denial — MUST be excluded
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(gov_mod, "_audit_path", lambda: path)
    # No bundles by default (no deploys); point the lineage source at an empty file.
    empty = tmp_path / "bundles.jsonl"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: empty)


def test_excludes_guard_denials_and_collapses_routings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_audit(tmp_path, monkeypatch)
    feed = gov_mod.compute_governance_feed()
    # Guard denial excluded; 3 identical routings collapse to one; + the handoff.
    assert feed.by_kind == {"handoff": 1, "routing": 1}
    assert feed.total == 2
    routing = next(e for e in feed.events if e["kind"] == "routing")
    assert routing["count"] == 3
    handoff = next(e for e in feed.events if e["kind"] == "handoff")
    assert handoff["from_agent"] == "support-client"
    assert handoff["to_agent"] == "onboarding"
    # Newest-first: the handoff (T3) leads.
    assert feed.events[0]["kind"] == "handoff"


def test_as_of_filters_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_audit(tmp_path, monkeypatch)
    # A cutoff between the first and second routing: only one routing is visible.
    feed = gov_mod.compute_governance_feed(at="2026-06-12T10:00:05Z")
    assert feed.by_kind == {"routing": 1}
    assert feed.total == 1
    assert feed.events[0]["count"] == 1


def _bundle_row(bundle_id: str, at: str, model: str) -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "captured_at": at,
        "conversation_id": "c",
        "language": "fr",
        "question": "q",
        "context": "c",
        "original_answer": "a",
        "original_model": model,
        "original_score": 0.5,
        "lineage": {
            "model": model,
            "prompt_version": "v1",
            "guard_policy_version": "p1",
            "doc_sources": [],
        },
        "latency_ms": None,
    }


def test_lineage_model_change_becomes_a_deploy_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = tmp_path / "audit.log"
    audit.write_text("", encoding="utf-8")
    monkeypatch.setattr(gov_mod, "_audit_path", lambda: audit)
    bundles = tmp_path / "bundles.jsonl"
    bundles.write_text(
        "\n".join(
            json.dumps(r)
            for r in (
                _bundle_row("b0", _T0, "llama3.2:3b"),
                _bundle_row("b1", _T1, "llama3.3:70b"),  # model CHANGE → one deploy event
            )
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: bundles)
    feed = gov_mod.compute_governance_feed()
    assert feed.by_kind == {"deploy_model": 1}
    deploy = feed.events[0]
    assert deploy["detail"] == "llama3.3:70b"
    assert deploy["actor"] == "system"
