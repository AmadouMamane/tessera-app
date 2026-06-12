"""Unit tests for the as-of-T read layer (ADR 0011).

Covers the shared timestamp comparison, the durable score/bundle stores filtered
to an instant T, and the audit-backed signals' ``at`` parameter. These are the
mechanics behind the cockpit time rail's "every block reads à T".
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability import replay as replay_mod
from tessera.observability._asof import occurred_before
from tessera.observability.conformance import compute_conformance
from tessera.observability.eval import scores as scores_mod
from tessera.observability.tool_validity import compute_tool_validity

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

# Two instants ten seconds apart, and a cutoff between them.
_T0 = "2026-06-12T10:00:00+00:00"
_T1 = "2026-06-12T10:00:10+00:00"
_CUT = "2026-06-12T10:00:05Z"  # Z form, as the frontend sends it


class TestOccurredBefore:
    def test_none_cutoff_is_live(self) -> None:
        assert occurred_before(_T0, None) is True

    def test_before_and_after(self) -> None:
        assert occurred_before(_T0, _CUT) is True
        assert occurred_before(_T1, _CUT) is False

    def test_zulu_vs_offset_boundary(self) -> None:
        # Same instant expressed as +00:00 vs Z must compare equal (<=).
        assert occurred_before("2026-06-12T10:00:05+00:00", _CUT) is True

    def test_fails_open_on_garbage(self) -> None:
        assert occurred_before("not-a-date", _CUT) is True
        assert occurred_before(123, _CUT) is True  # non-str
        assert occurred_before(_T1, "not-a-date") is True  # bad cutoff → live


def _score(at: str, score: float, metric: str = "faithfulness") -> dict[str, object]:
    return {"scored_at": at, "metric": metric, "score": score, "language": "fr"}


def test_persisted_scores_filters_at_t(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "scores.jsonl"
    monkeypatch.setattr(scores_mod, "_scores_path", lambda: path)
    path.write_text(
        "\n".join(json.dumps(r) for r in (_score(_T0, 0.2), _score(_T1, 0.8))) + "\n",
        encoding="utf-8",
    )
    assert len(scores_mod.persisted_scores()) == 2
    as_of = scores_mod.persisted_scores(_CUT)
    assert len(as_of) == 1
    assert as_of[0]["score"] == 0.2  # only the earlier score is visible at T


def _bundle_row(bundle_id: str, at: str, conv: str = "conv-1") -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "captured_at": at,
        "conversation_id": conv,
        "language": "fr",
        "question": "q",
        "context": "c",
        "original_answer": "a",
        "original_model": "m",
        "original_score": 0.5,
        "lineage": None,
        "latency_ms": None,
    }


def test_persisted_bundles_filters_and_warms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "bundles.jsonl"
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: path)
    path.write_text(
        "\n".join(json.dumps(_bundle_row(f"b{i}", at)) for i, at in enumerate((_T0, _T1))) + "\n",
        encoding="utf-8",
    )
    saved = list(replay_mod._BUNDLES)
    try:
        # as-of-T filtering over the durable store
        assert len(replay_mod.persisted_bundles()) == 2
        assert len(replay_mod.persisted_bundles(_CUT)) == 1

        # the live buffer warms from the store after a (simulated) restart
        replay_mod._BUNDLES.clear()
        monkeypatch.setattr(replay_mod, "_WARMED", False)
        live = replay_mod.recent_bundles()
        assert len(live) == 2  # survived the restart via warm
    finally:
        replay_mod._BUNDLES.clear()
        replay_mod._BUNDLES.extend(saved)


def test_lineage_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tessera.observability.lineage import Lineage

    path = tmp_path / "bundles.jsonl"
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: path)
    row = _bundle_row("with-lineage", _T0)
    row["lineage"] = {
        "model": "llama3.2:3b",
        "prompt_version": "v1",
        "guard_policy_version": "v2",
        "doc_sources": ["DORA/art-5"],
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    bundles = replay_mod.persisted_bundles()
    assert len(bundles) == 1
    assert isinstance(bundles[0].lineage, Lineage)
    assert bundles[0].lineage.doc_sources == ["DORA/art-5"]


def _audit(target: str, outcome: str, at: str, **extra: object) -> dict[str, object]:
    return {
        "type": "tessera.guard.audit",
        "target": target,
        "outcome": outcome,
        "occurred_at": at,
        **extra,
    }


def test_conformance_at_t(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    log.write_text(
        "\n".join(
            json.dumps(e)
            for e in (
                _audit("account_balance", "allowed", _T0, arguments={"account_id": "AC-12345"}),
                _audit("account_balance", "allowed", _T1, arguments={"account_id": "AC-67890"}),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    assert compute_conformance(log).n_calls == 2
    assert compute_conformance(log, at=_CUT).n_calls == 1  # only the pre-T call counts


def test_tool_validity_at_t(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    log.write_text(
        "\n".join(
            json.dumps(e)
            for e in (
                _audit("account_balance", "allowed", _T0),
                _audit("account_balance", "allowed", _T1),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    assert compute_tool_validity(log).total == 2
    assert compute_tool_validity(log, at=_CUT).total == 1
