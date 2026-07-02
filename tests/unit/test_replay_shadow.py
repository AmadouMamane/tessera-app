"""Unit tests for the Replay & shadow real core.

The payload must derive from the captured bundles, the durable replay journal
and the REAL eval run-to-run diffs — storeless metrics render "—" and the
shadow/export zones stay honest dashes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.observability import replay_shadow as rs, replay_store

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

NOW = datetime.now(UTC)


@dataclass(frozen=True)
class _Bundle:
    bundle_id: str
    agent_id: str
    original_model: str
    original_score: float
    captured_at: str


def _bundles() -> list[_Bundle]:
    return [
        _Bundle("b-aaaaaaaaaaaa", "support-client", "llama3.2:3b", 0.9, NOW.isoformat()),
        _Bundle(
            "b-bbbbbbbbbbbb",
            "onboarding",
            "llama3.2:3b",
            0.7,
            (NOW - timedelta(days=1)).isoformat(),
        ),
    ]


def _report(agent: str, run_at: str, cases: list[tuple[str, str, str, bool]]) -> dict[str, object]:
    sessions = [
        {"case_id": cid, "language": lang, "category": cat, "passed": passed}
        for cid, lang, cat, passed in cases
    ]
    passed = sum(1 for *_rest, ok in cases if ok)
    return {
        "agent_id": agent,
        "model": "llama3.2:3b",
        "run_at": run_at,
        "eval_set": "v43",
        "summary": {"total": len(cases), "passed": passed},
        "sessions": sessions,
    }


def _wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(rs, "recent_bundles", lambda: _bundles())
    reports = [
        _report(
            "support-client",
            "20260702T100000Z",
            [("01", "fr", "pii_leak", False), ("02", "fr", "hallucination", True)],
        ),
        _report(
            "support-client",
            "20260701T100000Z",
            [("01", "fr", "pii_leak", True), ("02", "fr", "hallucination", True)],
        ),
    ]
    paths = []
    for i, payload in enumerate(reports):
        import json

        path = tmp_path / f"r{i}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)
    monkeypatch.setattr(rs, "iter_report_files", lambda: paths)
    state = tmp_path / "replay_runs.json"
    monkeypatch.setattr(replay_store, "_state_path", lambda: state)
    monkeypatch.setattr(rs, "load_replay_runs", replay_store.load_replay_runs)


def test_replay_store_records_real_runs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = tmp_path / "replay_runs.json"
    monkeypatch.setattr(replay_store, "_state_path", lambda: state)
    replay_store.record_replay_run(
        "b-aaaaaaaaaaaa",
        agent_id="support-client",
        model="llama3.3:70b",
        score_delta=-0.25,
        similarity=0.8,
    )
    runs = replay_store.load_replay_runs()
    assert len(runs) == 1
    assert runs[0]["bundle_id"] == "b-aaaaaaaaaaaa"
    assert runs[0]["score_delta"] == -0.25
    assert runs[0]["at"]  # timestamped


def test_overview_derives_from_bundles_runs_and_diffs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire(monkeypatch, tmp_path)
    replay_store.record_replay_run(
        "b-aaaaaaaaaaaa",
        agent_id="support-client",
        model="llama3.3:70b",
        score_delta=-0.25,
        similarity=0.8,
    )
    payload = rs.compute_replay_shadow_overview("fr")
    kpi = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpi["sessions"] == "2"  # captured bundles
    assert kpi["requests"] == "1"  # ONE real executed replay
    # deviations = 1 critical replay + 1 newly-failed case (01.fr pass->fail)
    assert kpi["deviations"] == "2"
    for storeless in ("tokens", "cost", "proofs", "coverage"):
        assert kpi[storeless] == "—"
    # The newly-failed pii case lands in the confidentiality deviation type.
    types = {d["key"]: d["count"] for d in payload["deviation_by_type"]}
    assert types.get("confidentiality") == 1
    # Real run-to-run comparison with the exact newly-failed count.
    comps = payload["recent_comparisons"]
    assert len(comps) == 1
    assert comps[0]["deviations"] == 1
    assert "support-client" in comps[0]["label"]
    # Regression: pass rate 100% -> 50% = -50 pt, critical (pii) = 1.
    reg = payload["top_regressions"][0]
    assert reg["service"] == "support-client"
    assert reg["delta"] == "-50.0 pt"
    assert reg["critical"] == 1
    # Replayed bundle marked in sessions; distributions use safe slugs.
    sessions = {r["id"]: r["status"] for r in payload["recent_sessions"]}
    assert sessions["b-aaaaaaaaaaaa"[:12]] == "rejouee"  # ids display truncated
    assert {x["key"] for x in payload["by_model"]} == {"llama3_2_3b"}
    # Shadow/export tallies stay honest dashes (flagged subsystem).
    assert payload["proofs_exports"]["generated"] == "—"


def test_overview_without_history_is_honest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(rs, "recent_bundles", list)
    monkeypatch.setattr(rs, "iter_report_files", list)
    state = tmp_path / "replay_runs.json"
    monkeypatch.setattr(replay_store, "_state_path", lambda: state)
    monkeypatch.setattr(rs, "load_replay_runs", replay_store.load_replay_runs)
    payload = rs.compute_replay_shadow_overview("en")
    kpi = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpi["sessions"] == "0"
    assert kpi["deviations"] == "0"
    assert payload["recent_comparisons"] == []
    assert payload["baselines"] == []
