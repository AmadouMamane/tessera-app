"""``/observability/slo`` — the ``by_language`` slices (ADR 0017 §Amendment 4 follow-up).

One judged plane, three sub-populations: the route slices the SAME faithfulness rows by
the language each score row carries — one read, one window — so the cockpit can show
where multilingual quality diverges. These tests pin the two promises: every slice counts
exactly its own language's verdicts, and a language nobody spoke reads ``n=0`` (never a
fabricated rate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.api.routes.observability import signals

if TYPE_CHECKING:
    import pytest


def _score(language: str, value: float, metric: str = "faithfulness") -> dict[str, object]:
    return {"metric": metric, "score": value, "language": language}


def test_each_language_slice_counts_exactly_its_own_verdicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _score("fr", 0.95),
        _score("fr", 0.10),
        _score("de", 0.90),
        # Another metric's row belongs to no slice — the SLO is over faithfulness only.
        _score("fr", 0.05, metric="relevancy"),
    ]
    monkeypatch.setattr(signals, "_scores_for", lambda *_a, **_k: list(rows))

    payload = signals.observability_slo()

    assert payload["n"] == 3  # the headline covers the whole judged plane
    by_language = payload["by_language"]
    assert isinstance(by_language, dict)
    assert set(by_language) == {"fr", "de", "en"}
    assert by_language["fr"]["n"] == 2
    assert by_language["de"]["n"] == 1
    # The slices partition the plane: no verdict counted twice, none dropped.
    assert sum(slice_["n"] for slice_ in by_language.values()) == payload["n"]
    for slice_ in by_language.values():
        assert slice_["n_good"] <= slice_["n"]


def test_a_language_nobody_spoke_reads_n_zero_never_a_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(signals, "_scores_for", lambda *_a, **_k: [_score("fr", 0.95)])

    by_language = signals.observability_slo()["by_language"]
    assert isinstance(by_language, dict)
    assert by_language["en"] == {"n": 0, "n_good": 0, "good_rate": 0.0}
