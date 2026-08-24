"""Phase F — the agent x time x language cube (ADR 0015 §Migration F), offline.

Proves the payoff: a store-derived signal slices by ``language`` end to end, the cube composes
with ``agent``, and — critically — a signal that does *not* declare ``LANGUAGE`` has the filter
**narrowed away** and reported ``ignored``, so "a language filter is shown but silently applied
to a signal that can't honour it" stays impossible. Adding the dimension was a field on ``Scope``
+ a registry declaration + a reader filter — no route sweep — which is exactly what this locks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.observability.spine.adapters import FakeSpineReader, set_reader
from tessera.observability.spine.scope import Dimension, Scope
from tessera.observability.spine.snapshot import compute_snapshot, reset_snapshot_cache

if TYPE_CHECKING:
    from collections.abc import Iterator

_AT = "2026-06-10T00:00:00+00:00"


def _score(agent: str, language: str, score: float) -> dict[str, object]:
    return {
        "scored_at": _AT,
        "metric": "faithfulness",
        "score": score,
        "agent_id": agent,
        "language": language,
        "model": "llama3.2:3b",
    }


@pytest.fixture(autouse=True)
def _seeded_reader() -> Iterator[None]:
    set_reader(
        FakeSpineReader(
            scores=[
                _score("support-client", "fr", 0.90),
                _score("support-client", "de", 0.50),
                # onboarding, not recouvrement: the scores plane is kept to agents that
                # DECLARE the judge (SnapshotContext filter, ADR 0017 §A4) — this file's
                # subject is dimension composition, so it seeds a declared-judged agent.
                _score("onboarding", "fr", 0.80),
            ]
        )
    )
    reset_snapshot_cache()
    yield
    set_reader(None)
    reset_snapshot_cache()


def _rows(snapshot: dict[str, object]) -> list[dict[str, object]]:
    signals = snapshot["signals"]  # type: ignore[index]
    return signals["scores"]["data"]["scores"]  # type: ignore[index]


async def test_language_slices_the_scores_signal() -> None:
    fr = await compute_snapshot(Scope(agent_id="support-client", language="fr"), ("scores",))
    reset_snapshot_cache()
    de = await compute_snapshot(Scope(agent_id="support-client", language="de"), ("scores",))
    assert [r["score"] for r in _rows(fr)] == [0.90]  # only the fr turn
    assert [r["score"] for r in _rows(de)] == [0.50]  # only the de turn — a different slice


async def test_cube_composes_agent_and_language() -> None:
    snap = await compute_snapshot(Scope(agent_id="onboarding", language="fr"), ("scores",))
    rows = _rows(snap)
    assert [r["agent_id"] for r in rows] == ["onboarding"]
    assert [r["language"] for r in rows] == ["fr"]  # agent AND language both applied


async def test_scores_report_honours_language() -> None:
    snap = await compute_snapshot(Scope(agent_id="support-client", language="fr"), ("scores",))
    report = snap["signals"]["scores"]["report"]  # type: ignore[index]
    assert "language" in report["honoured"]
    assert "language" not in report["ignored"]


def test_a_non_language_signal_narrows_language_away() -> None:
    # A signal that declares only {AGENT, TIME} (e.g. conformance) cannot apply a language
    # filter: narrow_to drops it, so the read never silently language-slices an org/ledger
    # signal — and the registry would report it 'ignored', not honoured.
    narrowed = Scope(agent_id="a", language="fr").narrow_to(
        frozenset({Dimension.AGENT, Dimension.TIME})
    )
    assert narrowed.language is None
    assert narrowed.agent_id == "a"  # the supported dimension survives
