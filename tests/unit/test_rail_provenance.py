"""Provenance contract for the SR-01 rail consumers (docs/design/rail-data-provenance.md).

The cockpit stamps each block under the temporal rail with a mode badge ("À cet
instant" / "Sur la période"). This pins the *contract* that badge promises, at the
projection level (not just the row filter, which test_observability_asof.py covers):

* **variation** — changing T changes the PROJECTED metric (here the SLO good-rate),
  not merely the row count;
* **reproducibility** — same (scope, T) ⇒ byte-identical projection (registre §5/§9);
* **justified invariance** — the fixed-corpus probes (refusal / firewall) take no
  ``at`` at all, so they are constant by construction — honest only because the FE
  badges them live, never "reconstructed at T".
"""

from __future__ import annotations

import inspect
import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from tessera.observability.eval import scores as scores_mod
from tessera.observability.firewall_efficacy import compute_efficacy
from tessera.observability.refusal import compute_refusal_calibration
from tessera.observability.slo import compute_slo

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

# Two faithfulness scores ten seconds apart, and a cutoff between them: a bad one
# (0.2) before T, a good one (0.9) after T.
_T0 = "2026-06-12T10:00:00+00:00"
_T1 = "2026-06-12T10:00:10+00:00"
_CUT = "2026-06-12T10:00:05Z"


def _score(at: str, score: float) -> dict[str, object]:
    return {"scored_at": at, "metric": "faithfulness", "score": score, "language": "fr"}


def _good_rate(rows: list[dict[str, object]]) -> float:
    """Re-derive the SLO good-rate the way the /observability/slo route does."""
    faithfulness = [float(r["score"]) for r in rows if r.get("metric") == "faithfulness"]  # type: ignore[arg-type]
    # threshold=0.5 makes 0.2 a fail and 0.9 a pass regardless of the default.
    return compute_slo(faithfulness, threshold=0.5).good_rate


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "scores.jsonl"
    monkeypatch.setattr(scores_mod, "_scores_path", lambda: path)
    path.write_text(
        "\n".join(json.dumps(r) for r in (_score(_T0, 0.2), _score(_T1, 0.9))) + "\n",
        encoding="utf-8",
    )


def test_changing_t_changes_the_projected_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real projection: the SLO good-rate moves with T (not just the row count)."""
    _seed(tmp_path, monkeypatch)
    live = _good_rate(scores_mod.persisted_scores())  # [0.2, 0.9] → 1/2 good
    as_of = _good_rate(scores_mod.persisted_scores(_CUT))  # [0.2] only → 0/1 good
    assert live == 0.5
    assert as_of == 0.0
    assert as_of != live  # the badge "À cet instant" reflects a genuine as-of-T value


def test_same_mode_scope_t_is_reproducible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same (scope, T) ⇒ identical projection — re-derivable from the append-only log."""
    _seed(tmp_path, monkeypatch)
    assert scores_mod.persisted_scores(_CUT) == scores_mod.persisted_scores(_CUT)
    assert _good_rate(scores_mod.persisted_scores(_CUT)) == _good_rate(
        scores_mod.persisted_scores(_CUT)
    )


def test_as_of_subset_is_monotone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An earlier T can only ever reveal a subset — never more rows than live."""
    _seed(tmp_path, monkeypatch)
    assert len(scores_mod.persisted_scores(_CUT)) <= len(scores_mod.persisted_scores())


def test_fixed_corpus_probes_take_no_instant() -> None:
    """Refusal & firewall are current-policy probes: invariant to T BY CONSTRUCTION.

    They expose no ``at``/``as_of`` parameter, so they cannot pretend to reconstruct
    a past instant — which is why the cockpit marks them live (asOfCapable=false),
    never under an "À cet instant" badge (rail-data-provenance §3, invariant-justifié).
    """
    for fn in (compute_refusal_calibration, compute_efficacy):
        params = set(inspect.signature(fn).parameters)
        assert "at" not in params, fn.__name__
        assert "as_of" not in params, fn.__name__


def test_fixed_corpus_probe_is_deterministic() -> None:
    """A fixed-corpus probe over the current policy yields the same value every call."""
    a = asdict(compute_efficacy())
    b = asdict(compute_efficacy())
    assert a == b
