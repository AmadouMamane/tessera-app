"""Phase 1 — validate the wiring harness and its negative control.

Six probes exercise every verdict path of :mod:`tests.support.wiring`:

* **3 reals that MUST move** — a quality pass-rate (``slo.good_rate``), the
  ``pii_leak`` rate, and a computed retrieval metric (``coverage.max_similarity``).
  Each proves ``WIRED``.
* **the negative control that MUST be flagged** — two ``status: active`` signals
  whose *route* wiring is dead (``embedding_skew`` freezes ``corpus = query``;
  ``disclosure.enabled`` is a hardcoded literal) come out ``DEAD``; one declared
  ``synthetic`` fixture (``assistant``) comes out ``FIXTURE_BY_DESIGN``.

The meta-assertion (:func:`tests.support.wiring.assert_flagged`) fails loudly if
any negative control is reported ``WIRED`` — the proof that the harness has teeth.

Every probe's ``compute`` reproduces the *route's* source-assembly, per
``docs/design/signal-wiring-map.md``; the negative controls embody the route's
freeze so perturbing the true source is provably ignored.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from tessera.observability.assistant import compute_assistant_overview
from tessera.observability.coverage import CoverageReport, measure_coverage
from tessera.observability.disclosure import DisclosureReport, disclosure_status
from tessera.observability.embedding_skew import (
    EmbeddingFingerprint,
    SkewReport,
    detect_skew,
)
from tessera.observability.pii_leak import PIILeakSummary, aggregate_leaks
from tessera.observability.slo import SLOReport, compute_slo
from tessera.observability.spine.capabilities import capability_for
from tests.support.wiring import (
    Probe,
    Verdict,
    assert_fixture_by_design,
    assert_flagged,
    assert_wired,
    evaluate,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# --------------------------------------------------------------------------- #
# Observers — payload -> scalar (cast keeps mypy --strict honest about the type)
# --------------------------------------------------------------------------- #


def _obs_slo_good_rate(payload: object) -> float:
    return cast("SLOReport", payload).good_rate


def _obs_leak_rate(payload: object) -> float:
    return cast("PIILeakSummary", payload).leak_rate


def _obs_max_similarity(payload: object) -> float:
    return cast("CoverageReport", payload).max_similarity


def _obs_skew(payload: object) -> bool:
    return cast("SkewReport", payload).skew


def _obs_disclosure_enabled(payload: object) -> bool:
    return cast("DisclosureReport", payload).enabled


def _obs_payload_size(payload: object) -> int:
    # A fixture's whole document is constant; its serialized length is a stable
    # scalar that no runtime-source perturbation can move.
    return len(json.dumps(cast("dict[str, object]", payload), sort_keys=True, default=str))


# --------------------------------------------------------------------------- #
# REAL #1 — quality SLO pass-rate. Route assembly (spine/signals._read_slo):
# faithfulness score rows -> compute_slo. Append sub-threshold rows -> good_rate ↓.
# --------------------------------------------------------------------------- #

_SLO_BASE: list[dict[str, object]] = [{"metric": "faithfulness", "score": 0.95} for _ in range(8)]


def _slo_compute(rows: list[dict[str, object]]) -> object:
    faithfulness = [
        float(cast("float", r["score"])) for r in rows if r.get("metric") == "faithfulness"
    ]
    return compute_slo(faithfulness)


def _slo_perturb(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    # Four failing turns (score < 0.80 threshold) enter at the score-store seam.
    failing: list[dict[str, object]] = [{"metric": "faithfulness", "score": 0.50} for _ in range(4)]
    return [*rows, *failing]


_slo_probe: Probe[list[dict[str, object]]] = Probe(
    key="quality-slo-error-budget#15",
    compute=_slo_compute,
    observe=_obs_slo_good_rate,
    base_source=_SLO_BASE,
    perturb=_slo_perturb,
    relation="down",
    seam="store",
    declared_class="real-store",
)

# --------------------------------------------------------------------------- #
# REAL #2 — output PII-leak rate. Route assembly: bundles -> (answer, source)
# turns -> aggregate_leaks. Inject a turn whose answer carries an email absent
# from its source (guard email pattern, policy.yaml L142) -> leak_rate ↑.
# --------------------------------------------------------------------------- #

_LEAK_BASE: list[tuple[str, str]] = [
    ("Votre solde est de 100 EUR.", "Question: quel est mon solde ? Context: compte credit Aurore"),
    ("Le taux du pret est de 3 pourcent.", "Question: quel taux ? Context: pret Aurore taux 3"),
]


def _leak_compute(turns: list[tuple[str, str]]) -> object:
    return aggregate_leaks(turns)


def _leak_perturb(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    leaked = ("Écrivez à eve.leak@fraud.example pour la suite.", "Question: bonjour, comment ça va")
    return [*turns, leaked]


_leak_probe: Probe[list[tuple[str, str]]] = Probe(
    key="output-pii-leak#38",
    compute=_leak_compute,
    observe=_obs_leak_rate,
    base_source=_LEAK_BASE,
    perturb=_leak_perturb,
    relation="up",
    seam="store",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# REAL #3 — corpus coverage gap. Route assembly: (question, bundle.context chunks)
# -> measure_coverage. A deterministic bag-of-words embedder isolates the wiring
# (chunks -> cosine -> max_similarity) from the real embedding backend. Swap the
# on-topic chunk for an off-topic one -> max_similarity ↓.
# --------------------------------------------------------------------------- #


async def _bow_embed(texts: Sequence[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder: cosine reflects shared tokens."""
    vocab = sorted({token for text in texts for token in text.lower().split()})
    index = {word: i for i, word in enumerate(vocab)}
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * len(vocab)
        for token in text.lower().split():
            vector[index[token]] += 1.0
        vectors.append(vector)
    return vectors


def _cov_compute(source: tuple[str, list[str]]) -> object:
    question, chunks = source
    return measure_coverage(question=question, chunks=chunks, embedder=_bow_embed)


def _cov_perturb(source: tuple[str, list[str]]) -> tuple[str, list[str]]:
    question, _ = source
    return (question, ["la meteo de demain sera ensoleillee sur paris"])


_cov_probe: Probe[tuple[str, list[str]]] = Probe(
    key="corpus-coverage-gaps#28",
    compute=_cov_compute,
    observe=_obs_max_similarity,
    base_source=("taux pret aurore", ["le taux du pret aurore est fixe"]),
    perturb=_cov_perturb,
    relation="down",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# NEGATIVE CONTROL #1 — embedding-version-skew (#64, status: active). The route
# (routes/observability.py ~L2447-2452) builds `query` from settings then sets
# `corpus = query` — an alias. compute embodies that freeze, so a genuinely
# different corpus embedder is ignored and `skew` stays False -> DEAD.
# --------------------------------------------------------------------------- #

_SKEW_BASE: dict[str, tuple[str, int]] = {
    "query": ("text-multilingual-embedding-002", 768),
    "corpus": ("text-multilingual-embedding-002", 768),
}


def _skew_compute(source: dict[str, tuple[str, int]]) -> object:
    q_model, q_dim = source["query"]
    query = EmbeddingFingerprint(model=q_model, dimension=q_dim)
    corpus = query  # the ROUTE's freeze — source["corpus"] is deliberately ignored
    return detect_skew(query=query, corpus=corpus)


def _skew_perturb(source: dict[str, tuple[str, int]]) -> dict[str, tuple[str, int]]:
    # A real corpus re-embedded by a different model at a different width.
    return {**source, "corpus": ("bge-m3", 1024)}


_skew_probe: Probe[dict[str, tuple[str, int]]] = Probe(
    key="embedding-version-skew#64",
    compute=_skew_compute,
    observe=_obs_skew,
    base_source=_SKEW_BASE,
    perturb=_skew_perturb,
    relation="changes",  # declared: skew flips when corpus != query
    seam="route-fixed",
    declared_class="real-computed",  # catalogue status: active -> nominally real -> DEAD
)

# --------------------------------------------------------------------------- #
# NEGATIVE CONTROL #2 — ai-act-disclosure-ux (#134, status: active). The route
# passes no runtime source; `disclosure_status` reads a hardcoded module constant
# and `enabled` is a literal True. No perturbation of runtime disclosure state can
# move it -> DEAD.
# --------------------------------------------------------------------------- #

_DISCLOSURE_BASE: dict[str, bool] = {"de_disclosure_live": True}


def _disclosure_compute(_source: dict[str, bool]) -> object:
    return disclosure_status()  # ignores the source, exactly like the route


def _disclosure_perturb(source: dict[str, bool]) -> dict[str, bool]:
    # Simulate a locale's disclosure being turned off at runtime.
    return {**source, "de_disclosure_live": False}


_disclosure_probe: Probe[dict[str, bool]] = Probe(
    key="ai-act-disclosure-ux#134",
    compute=_disclosure_compute,
    observe=_obs_disclosure_enabled,
    base_source=_DISCLOSURE_BASE,
    perturb=_disclosure_perturb,
    relation="changes",
    seam="route-fixed",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# NEGATIVE CONTROL #3 — assistant, a declared-synthetic reference fixture. The
# declared class is READ from the honesty contract (capabilities.py), not guessed,
# so an inert result is the *expected, honest* FIXTURE_BY_DESIGN, not a DEAD bug.
# --------------------------------------------------------------------------- #

_ASSISTANT_CLASS = "synthetic" if capability_for("assistant").synthetic else "real-computed"


def _assistant_compute(_source: list[object]) -> object:
    return compute_assistant_overview()  # canned document, ignores any source


def _assistant_perturb(source: list[object]) -> list[object]:
    return [*source, {"conversation": "a new live turn that a real signal would count"}]


_assistant_probe: Probe[list[object]] = Probe(
    key="assistant#synthetic",
    compute=_assistant_compute,
    observe=_obs_payload_size,
    base_source=[],
    perturb=_assistant_perturb,
    relation="up",
    seam="route-fixed",
    declared_class=_ASSISTANT_CLASS,
)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_real_signals_are_wired() -> None:
    """The three diverse real signals move with their source (WIRED)."""
    r_slo = assert_wired(_slo_probe)
    r_leak = assert_wired(_leak_probe)
    r_cov = assert_wired(_cov_probe)
    # Each moved in the predicted direction with a non-trivial delta.
    assert r_slo.delta < -0.2  # good_rate 1.0 -> 0.667
    assert r_leak.delta > 0.0  # leak_rate 0.0 -> 0.333
    assert r_cov.delta < -0.3  # max_similarity ~0.65 -> 0.0
    for result in (r_slo, r_leak, r_cov):
        print(f"REAL  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_embedding_skew_is_dead() -> None:
    """A route that aliases corpus=query kills the skew signal (DEAD)."""
    result = evaluate(_skew_probe)
    assert result.verdict is Verdict.DEAD, result.detail
    assert result.d0 == result.d1 == 0.0  # skew stays False despite a real embedder swap
    print(f"NEG   {result.key:32} {result.verdict.value:10} {result.detail}")


def test_disclosure_enabled_is_dead() -> None:
    """A hardcoded `enabled=True` literal cannot reflect runtime state (DEAD)."""
    result = evaluate(_disclosure_probe)
    assert result.verdict is Verdict.DEAD, result.detail
    assert result.d0 == result.d1 == 1.0
    print(f"NEG   {result.key:32} {result.verdict.value:10} {result.detail}")


def test_assistant_is_fixture_by_design() -> None:
    """A declared-synthetic reference fixture is honestly inert (FIXTURE_BY_DESIGN)."""
    assert capability_for("assistant").synthetic is True  # the declared-class source of truth
    result = assert_fixture_by_design(_assistant_probe)
    assert result.delta == 0.0
    print(f"NEG   {result.key:32} {result.verdict.value:10} {result.detail}")


def test_harness_has_teeth() -> None:
    """META: no negative control may come out WIRED, else the harness is toothless."""
    for result in (
        assert_flagged(_skew_probe),
        assert_flagged(_disclosure_probe),
        assert_flagged(_assistant_probe),
    ):
        assert result.verdict is not Verdict.WIRED
