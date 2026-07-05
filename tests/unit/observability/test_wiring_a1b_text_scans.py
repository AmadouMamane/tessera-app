"""Phase 2 -- metamorphic wiring proof, Table A.1 second half (text-scan / LLM
judge signals): claim-attribution (#11), citation-validity (#49),
locale-formatting (#51), cross-lingual-consistency (#70), robustness-noise
(#46), sycophancy (#59), self-consistency (#18), why-this-answer (#133),
lineage-sbom (#10).

Every ``compute`` reproduces the *route's* source-assembly (``src/tessera/api/
routes/observability.py``), never the naked provider:

* #49/#51 -- the route builds ``(answer, context|language)`` turns straight
  from ``replay_mod.recent_bundles()`` into the aggregator; the seam is that
  argument list (``fn-arg``), no aliasing.
* #11/#133 -- the route splits ``bundle.context`` on blank lines into
  ``chunks`` (``chunks = [c for c in bundle.context.split("\\n\\n") if
  c.strip()]``, identical in both the ``/observability/provenance/{id}`` and
  ``/observability/why`` handlers) before calling ``attribute`` /
  ``build_explanation``; ``compute`` reproduces that exact split via
  ``_route_chunks``. Neither function accepts an injectable embedder (unlike
  ``coverage.measure_coverage``), so the embedding dependency is swapped by
  monkeypatching the module-level ``provenance.embed`` -- seam=fn-arg,
  test=unit+patch, the identical technique
  ``tests/unit/test_observability_provenance.py`` uses. ``build_explanation``
  calls the REAL (unpatched) ``attribute`` internally, so patching
  ``provenance.embed`` alone proves both signals wired through their true call
  chain -- no canned ``ProvenanceReport`` fixture is substituted anywhere.
* #70/#46/#59 -- the route calls the pure aggregator with the REAL
  backend/judge (Ollama) and no override; a deterministic fake stands in for
  that dependency, injected via the function's own ``backend=``/``judge=``
  parameter exactly as the route's call site allows -- the (question,
  context/answer, model) argument marshalling under test is identical to the
  route's. ``crosslingual`` and ``robustness`` accept both ``backend=`` and
  (for crosslingual) ``embedder=`` directly; sycophancy accepts ``judge=``.
* #18 -- ``consistency.measure_consistency`` has a ``backend=`` parameter
  (fn-arg, unit+fake, as declared) but, unlike crosslingual/coverage, NO
  ``embedder=`` parameter -- it calls the bare imported ``embed`` directly. Its
  embedding half is therefore monkeypatched exactly like #11/#133 (unit+patch),
  a small refinement of the map's uniform "unit+fake" label for this row: the
  *backend* seam is unit+fake as declared, the *embedder* seam is unit+patch.
* #10 -- lineage is built at chat time (``routes/chat.py:933``) from a fresh
  on-disk read of the prompt YAML (``lineage._PROMPTS_DIR / f"{language}.yaml"``
  via ``_short_hash``, uncached -- every call re-reads the file); a temp
  prompt directory stands in for the real one (seam=store, test=unit+temp).

Duplication invariant (map: "applies to all rate/mean rows in A & B") is added
for #49 (validity_rate), #51 (correctness_rate), #11 (grounded_fraction) and
#133 (confidence) -- all four are literal ratios/means over an enumerable,
duplicable population (turns for #49/#51; an answer's claims, reproducibly
doubled by duplicating the answer text, for #11/#133). Skipped, with a note at
the point of use, for #70/#18 (pairwise-cosine means over a FIXED-size internal
population -- doubling a cyclic sample series changes the pair-mixture and can
even move the mean, so asserting invariance would assert something false, not
merely "inapplicable") and #46 (mean over exactly the 3 hardcoded perturbation
kinds, not a caller-supplied series) and #59/#10 (a single-turn scalar / a
content hash -- no population at all).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast

import pytest

from tessera.llm.router import ChatResponse
from tessera.observability import consistency, lineage, provenance
from tessera.observability.citation_validity import CitationSummary, aggregate_citations
from tessera.observability.crosslingual import CrossLingualReport, measure_crosslingual
from tessera.observability.eval.judge import JudgeVerdict
from tessera.observability.eval.sycophancy import SycophancyReport, detect_sycophancy
from tessera.observability.locale_format import LocaleFormatSummary, aggregate_formatting
from tessera.observability.robustness import RobustnessReport, measure_robustness
from tessera.observability.why_answer import WhyExplanation, build_explanation
from tests.support.wiring import Probe, assert_invariant_ok, assert_wired

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from pathlib import Path

    from tessera.llm.router import ChatMessage

# --------------------------------------------------------------------------- #
# Observers -- payload -> scalar
# --------------------------------------------------------------------------- #


def _obs_grounded_fraction(payload: object) -> float:
    return cast("provenance.ProvenanceReport", payload).grounded_fraction


def _obs_validity_rate(payload: object) -> float:
    return cast("CitationSummary", payload).validity_rate


def _obs_correctness_rate(payload: object) -> float:
    return cast("LocaleFormatSummary", payload).correctness_rate


def _obs_xl_consistency(payload: object) -> float:
    return cast("CrossLingualReport", payload).consistency


def _obs_mean_similarity(payload: object) -> float:
    return cast("RobustnessReport", payload).mean_similarity


def _obs_sycophancy_score(payload: object) -> float:
    return cast("SycophancyReport", payload).score


def _obs_uncertainty(payload: object) -> float:
    return cast("consistency.ConsistencyReport", payload).uncertainty


def _obs_confidence(payload: object) -> float:
    return cast("WhyExplanation", payload).confidence


def _obs_prompt_version_numeric(payload: object) -> float:
    # prompt_version is a 12-hex-char content hash (categorical); coerce to a
    # numeric proxy so the harness's float-only `observe` can compare it under
    # relation="changes". 12 hex chars = 48 bits, exactly representable as a
    # float (53-bit mantissa) -- no precision loss, equality/inequality intact.
    return float(int(cast("lineage.Lineage", payload).prompt_version, 16))


# --------------------------------------------------------------------------- #
# Shared deterministic fakes (reused across >=2 signals below)
# --------------------------------------------------------------------------- #


async def _marker_embed(texts: Sequence[str]) -> list[list[float]]:
    """3-d embeddings keyed by a marker word -- identical technique to
    ``tests/unit/test_observability_provenance.py``'s ``_fake_embed``."""
    out: list[list[float]] = []
    for text in texts:
        if "alpha" in text:
            out.append([1.0, 0.0, 0.0])
        elif "beta" in text:
            out.append([0.0, 1.0, 0.0])
        else:
            out.append([0.0, 0.0, 1.0])
    return out


async def _bow_embed(texts: Sequence[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder: cosine reflects shared tokens.

    Identical technique to ``tests/unit/observability/test_wiring_a2_retrieval.py``'s
    ``_bow_embed`` (itself inherited from Phase 1's ``test_signal_wiring.py``
    ``_cov_probe``). Reused here (rather than re-imported) to keep this file
    self-contained per-signal-group.
    """
    vocab = sorted({token for text in texts for token in text.lower().split()})
    index = {word: i for i, word in enumerate(vocab)}
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * len(vocab)
        for token in text.lower().split():
            vector[index[token]] += 1.0
        vectors.append(vector)
    return vectors


def _route_chunks(context: str) -> list[str]:
    """Mirror the provenance/why routes' chunk split (observability.py
    ~L2752/~L1928): ``[c for c in bundle.context.split("\\n\\n") if c.strip()]``.
    """
    return [c for c in context.split("\n\n") if c.strip()]


# --------------------------------------------------------------------------- #
# #11 claim-attribution -- provenance.py:attribute
# Route (observability.py ~L2746-2755, GET /observability/provenance/{id}):
# chunks = _route_chunks(bundle.context); attribute(bundle.original_answer,
# chunks) -- real `embed` by default, no threshold override. `attribute` has no
# injectable embedder: monkeypatch `provenance.embed` (unit+patch), per
# tests/unit/test_observability_provenance.py.
# --------------------------------------------------------------------------- #

_PROV_CONTEXT = "alpha grounds this fact well in the corpus."
_PROV_GROUNDED_ANSWER = "The alpha rule clearly applies here."
_PROV_MIXED_ANSWER = (
    "The alpha rule clearly applies here. Totally unrelated gamma claim about weather here."
)


def _provenance_compute(source: tuple[str, str]) -> object:
    answer, context = source
    return provenance.attribute(answer, _route_chunks(context))


def _provenance_perturb(source: tuple[str, str]) -> tuple[str, str]:
    answer, context = source
    return (f"{answer} Totally unrelated gamma claim about weather here.", context)


_provenance_probe: Probe[tuple[str, str]] = Probe(
    key="claim-attribution#11",
    compute=_provenance_compute,
    observe=_obs_grounded_fraction,
    base_source=(_PROV_GROUNDED_ANSWER, _PROV_CONTEXT),
    perturb=_provenance_perturb,
    relation="down",
    seam="fn-arg",
    declared_class="real-computed",
)

# Duplication invariant: the MIXED (1 supported + 1 unsupported) answer is the
# non-degenerate base (grounded_fraction=0.5); duplicating the answer text
# duplicates its claims 1:1 with identical per-claim support, so the fraction
# is provably unchanged (2/4 == 1/2).
_provenance_dup_base: tuple[str, str] = (_PROV_MIXED_ANSWER, _PROV_CONTEXT)


def _provenance_dup_perturb(source: tuple[str, str]) -> tuple[str, str]:
    answer, context = source
    return (f"{answer} {answer}", context)


_provenance_dup_probe: Probe[tuple[str, str]] = Probe(
    key="claim-attribution#11-duplication",
    compute=_provenance_compute,
    observe=_obs_grounded_fraction,
    base_source=_provenance_dup_base,
    perturb=_provenance_dup_perturb,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_claim_attribution_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "embed", _marker_embed)
    result = assert_wired(_provenance_probe)
    assert result.d0 == pytest.approx(1.0)
    assert result.d1 == pytest.approx(0.5)
    print(f"WIRED {result.key:38} {result.detail}")


def test_claim_attribution_duplication_invariant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "embed", _marker_embed)
    result = assert_invariant_ok(_provenance_dup_probe)
    assert result.d0 == pytest.approx(0.5)
    print(f"INV   {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #49 citation-validity -- citation_validity.py:aggregate_citations
# Route (observability.py ~L2587-2591, GET /observability/citations):
# turns = [(b.original_answer, b.context) for b in recent_bundles()] ->
# aggregate_citations(turns). Pure, no I/O: fn-arg, unit.
# --------------------------------------------------------------------------- #

_CITATIONS_BASE: list[tuple[str, str]] = [
    (
        "Selon l'article 5 de DORA, le management body est responsable.",
        "Article 5 of the Digital Operational Resilience Act requires governance.",
    ),
]


def _citations_compute(turns: list[tuple[str, str]]) -> object:
    return aggregate_citations(turns)


def _citations_perturb(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    fabricated = (
        "DORA Article 999 requires a same-day incident report.",
        "Article 5 of DORA covers governance. Article 17 covers incident reporting.",
    )
    return [*turns, fabricated]


_citations_probe: Probe[list[tuple[str, str]]] = Probe(
    key="citation-validity#49",
    compute=_citations_compute,
    observe=_obs_validity_rate,
    base_source=_CITATIONS_BASE,
    perturb=_citations_perturb,
    relation="down",
    seam="fn-arg",
    declared_class="real-computed",
)

_CITATIONS_DUP_BASE: list[tuple[str, str]] = _citations_perturb(_CITATIONS_BASE)  # rate=0.5

_citations_dup_probe: Probe[list[tuple[str, str]]] = Probe(
    key="citation-validity#49-duplication",
    compute=_citations_compute,
    observe=_obs_validity_rate,
    base_source=_CITATIONS_DUP_BASE,
    perturb=lambda turns: turns * 2,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_citation_validity_wired() -> None:
    result = assert_wired(_citations_probe)
    assert result.d0 == pytest.approx(1.0)
    assert result.d1 == pytest.approx(0.5)
    print(f"WIRED {result.key:38} {result.detail}")


def test_citation_validity_duplication_invariant() -> None:
    result = assert_invariant_ok(_citations_dup_probe)
    assert result.d0 == pytest.approx(0.5)
    print(f"INV   {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #51 locale-formatting -- locale_format.py:aggregate_formatting
# Route (observability.py ~L2594-2598, GET /observability/locale-format):
# turns = [(b.original_answer, b.language) for b in recent_bundles()] ->
# aggregate_formatting(turns). Pure, no I/O: fn-arg, unit.
# --------------------------------------------------------------------------- #

_LOCALE_BASE: list[tuple[str, str]] = [("Le solde est de 4 567,89 €.", "fr")]


def _locale_compute(turns: list[tuple[str, str]]) -> object:
    return aggregate_formatting(turns)


def _locale_perturb(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    wrong = ("Votre solde est de 4,567.89 €.", "fr")  # en-grouped amount in an fr turn
    return [*turns, wrong]


_locale_probe: Probe[list[tuple[str, str]]] = Probe(
    key="locale-formatting#51",
    compute=_locale_compute,
    observe=_obs_correctness_rate,
    base_source=_LOCALE_BASE,
    perturb=_locale_perturb,
    relation="down",
    seam="fn-arg",
    declared_class="real-computed",
)

_LOCALE_DUP_BASE: list[tuple[str, str]] = _locale_perturb(_LOCALE_BASE)  # rate=0.5

_locale_dup_probe: Probe[list[tuple[str, str]]] = Probe(
    key="locale-formatting#51-duplication",
    compute=_locale_compute,
    observe=_obs_correctness_rate,
    base_source=_LOCALE_DUP_BASE,
    perturb=lambda turns: turns * 2,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_locale_formatting_wired() -> None:
    result = assert_wired(_locale_probe)
    assert result.d0 == pytest.approx(1.0)
    assert result.d1 == pytest.approx(0.5)
    print(f"WIRED {result.key:38} {result.detail}")


def test_locale_formatting_duplication_invariant() -> None:
    result = assert_invariant_ok(_locale_dup_probe)
    assert result.d0 == pytest.approx(0.5)
    print(f"INV   {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #70 cross-lingual-consistency -- crosslingual.py:measure_crosslingual
# Route (observability.py ~L1910-1919, POST /observability/crosslingual):
# measure_crosslingual(question=bundle.question, context=bundle.context,
# model=bundle.original_model) -- no backend/embedder override (real Ollama +
# real embed in prod). Both are fn-arg-injectable: fake backend + bag-of-words
# embedder isolate the wiring (unit+fake), languages left at the route's
# default (fr, de, en).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _XLSource:
    question: str
    context: str
    model: str
    diverge: bool


class _XLBackend:
    """Identical text on every call unless `diverge`; then the 2nd call (the
    route's default language order is fr, de, en -- so call #2 is "de")
    returns a disjoint-vocabulary answer. Counter-based stub, same shape as
    ``tests/unit/test_observability_crosslingual.py``'s ``_LangBackend``.
    """

    name = "stub"
    model = "stub-model"

    def __init__(self, *, diverge: bool) -> None:
        self._diverge = diverge
        self._i = 0

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        self._i += 1
        content = (
            "zebra quantum harbor lighthouse"
            if (self._diverge and self._i == 2)
            else "the fee schedule is the same across languages"
        )
        return ChatResponse(
            content=content,
            model=self.model,
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("unused by measure_crosslingual")


def _xl_compute(source: _XLSource) -> object:
    return measure_crosslingual(
        question=source.question,
        context=source.context,
        model=source.model,
        backend=_XLBackend(diverge=source.diverge),
        embedder=_bow_embed,
    )


def _xl_perturb(source: _XLSource) -> _XLSource:
    return replace(source, diverge=True)


_xl_probe: Probe[_XLSource] = Probe(
    key="cross-lingual-consistency#70",
    compute=_xl_compute,
    observe=_obs_xl_consistency,
    base_source=_XLSource(question="q", context="c", model="m", diverge=False),
    perturb=_xl_perturb,
    relation="down",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_cross_lingual_consistency_wired() -> None:
    """consistency falls when the stub backend's DE answer diverges.

    No duplication invariant: `consistency` is a mean over the 3 pairwise
    cosines of a FIXED 3-language population, not a caller-supplied series.
    Doubling a cyclic sample series changes the pair-mixture and can itself
    move a pairwise-mean (verified by hand for the analogous #18 case below) --
    asserting invariance here would assert something that is not generally
    true, so it is skipped rather than forced.
    """
    result = assert_wired(_xl_probe)
    assert result.d0 == pytest.approx(1.0)
    assert result.d1 == pytest.approx(1.0 / 3.0)
    print(f"WIRED {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #46 robustness-noise -- robustness.py:measure_robustness
# Route (observability.py ~L1859-1868, POST /observability/robustness):
# measure_robustness(question=bundle.question, context=bundle.context,
# model=bundle.original_model) -- no backend/judge override (real Ollama +
# real LLMJudge in prod). Both fn-arg-injectable: fake backend drifts on the
# noised variants (unit+fake); judge held constant so only mean_similarity
# (not faithfulness) is under test.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _RobustSource:
    question: str
    context: str
    model: str
    drift: bool


class _DriftBackend:
    """Stable on the first (clean-question, baseline) call; if `drift`, every
    subsequent call (the 3 noised variants) returns unrelated text. Counter-
    based stub, same shape as
    ``tests/unit/test_observability_robustness.py``'s ``_FixedBackend``.
    """

    name = "stub"
    model = "stub-model"

    def __init__(self, *, drift: bool) -> None:
        self._drift = drift
        self._i = 0

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        self._i += 1
        content = (
            f"unrelated drifting content variant number {self._i}"
            if (self._drift and self._i > 1)
            else "a stable grounded answer"
        )
        return ChatResponse(
            content=content,
            model=self.model,
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("unused by measure_robustness")


class _FixedJudge:
    """Constant faithfulness score -- isolates `mean_similarity`'s response to
    the backend drift. Same shape as
    ``tests/unit/test_observability_robustness.py``'s ``_FixedJudge``.
    """

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        return JudgeVerdict(metric=metric, score=0.8, rationale="", judge_model="stub-judge")


def _robust_compute(source: _RobustSource) -> object:
    return measure_robustness(
        question=source.question,
        context=source.context,
        model=source.model,
        backend=_DriftBackend(drift=source.drift),
        judge=_FixedJudge(),
    )


def _robust_perturb(source: _RobustSource) -> _RobustSource:
    return replace(source, drift=True)


_robust_probe: Probe[_RobustSource] = Probe(
    key="robustness-noise#46",
    compute=_robust_compute,
    observe=_obs_mean_similarity,
    base_source=_RobustSource(
        question="quel est le plafond", context="le plafond est 100000", model="m", drift=False
    ),
    perturb=_robust_perturb,
    relation="down",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_robustness_noise_wired() -> None:
    """mean_similarity falls once the drifting backend answers the 3 noised
    variants with unrelated text.

    No duplication invariant: mean_similarity averages exactly the 3 hardcoded
    perturbation kinds (`perturbations()`'s typos/homoglyph/uppercase) against
    ONE baseline -- a fixed-size internal aggregate, not a caller-supplied
    series with a natural "duplicate it" operation.
    """
    result = assert_wired(_robust_probe)
    assert result.d0 == pytest.approx(1.0)
    assert result.d1 < 0.5
    print(f"WIRED {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #59 sycophancy -- eval/sycophancy.py:detect_sycophancy
# Route (observability.py ~L1933-1942, POST /observability/sycophancy):
# detect_sycophancy(question=bundle.question, answer=bundle.original_answer,
# context=bundle.context) -- no judge override (real LLMJudge in prod). judge
# is fn-arg-injectable: a content-aware fake judge (same technique as
# tests/unit/observability/test_wiring_a4_routing.py's `_AnswerAwareJudge`,
# #95) scores strictly from the real `answer` argument the route passes
# through -- stronger proof than a judge whose score ignores its input.
# --------------------------------------------------------------------------- #


class _PremiseAwareJudge:
    """Scores high iff the answer's own text endorses the question's premise."""

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        score = 0.9 if "you're right, no fee applies" in answer.lower() else 0.1
        return JudgeVerdict(metric=metric, score=score, rationale="", judge_model="stub-judge")


_SYCO_QUESTION = "Since my account is already overdraft-protected, there's no fee, right?"
_SYCO_CONTEXT = "Compte non couvert par une protection de decouvert ; frais de 5 EUR."
_SYCO_CORRECTIVE_ANSWER = (
    "Actually, your account does not have overdraft protection; a 5 EUR fee applies."
)
_SYCO_SYCOPHANTIC_ANSWER = "You're right, no fee applies since your account is already protected."


def _syco_compute(answer: str) -> object:
    return detect_sycophancy(
        question=_SYCO_QUESTION, answer=answer, context=_SYCO_CONTEXT, judge=_PremiseAwareJudge()
    )


_syco_probe: Probe[str] = Probe(
    key="sycophancy#59",
    compute=_syco_compute,
    observe=_obs_sycophancy_score,
    base_source=_SYCO_CORRECTIVE_ANSWER,
    perturb=lambda _a: _SYCO_SYCOPHANTIC_ANSWER,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_sycophancy_wired() -> None:
    """score rises when the answer text itself endorses the false premise.

    No duplication invariant: score is a single-turn scalar judge verdict, not
    an aggregate over any population.
    """
    result = assert_wired(_syco_probe)
    assert result.d0 == pytest.approx(0.1)
    assert result.d1 == pytest.approx(0.9)
    print(f"WIRED {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #18 self-consistency -- consistency.py:measure_consistency
# Route (observability.py ~L1844-1856, POST /observability/consistency):
# measure_consistency(question=bundle.question, context=bundle.context,
# model=bundle.original_model, samples=payload.samples) -- no backend
# override (real Ollama in prod). backend is fn-arg-injectable (unit+fake);
# `measure_consistency` has NO embedder parameter (unlike crosslingual), so its
# embedding half is monkeypatched (unit+patch) exactly like #11/#133.
# --------------------------------------------------------------------------- #

_SCATTERED_ANSWERS: tuple[str, ...] = (
    "zebra quantum harbor",
    "silver mountain lighthouse",
    "velvet ocean canyon",
)


class _SamplingBackend:
    """Repeats one stable answer unless `scattered`, where each call returns a
    disjoint-vocabulary answer. Counter-based stub, same shape as
    ``tests/unit/test_observability_consistency.py``'s ``_RepeatBackend``.
    """

    name = "stub"
    model = "stub-model"

    def __init__(self, *, scattered: bool) -> None:
        self._scattered = scattered
        self._i = 0

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        content = (
            _SCATTERED_ANSWERS[self._i % len(_SCATTERED_ANSWERS)]
            if self._scattered
            else "a stable repeated answer"
        )
        self._i += 1
        return ChatResponse(
            content=content,
            model=self.model,
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("unused by measure_consistency")


def _consistency_compute(scattered: bool) -> object:
    return consistency.measure_consistency(
        question="q",
        context="c",
        model="m",
        samples=3,
        backend=_SamplingBackend(scattered=scattered),
    )


_consistency_probe: Probe[bool] = Probe(
    key="self-consistency#18",
    compute=_consistency_compute,
    observe=_obs_uncertainty,
    base_source=False,
    perturb=lambda _s: True,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_self_consistency_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    """uncertainty rises when the stub backend returns scattered samples.

    No duplication invariant: uncertainty is `1 - mean-pairwise-cosine` over
    `samples` internally-generated answers, not a caller-supplied series. Proof
    it would be UNSOUND to claim invariance here: with a 3-answer cycle
    [e0, e1, e2] (all pairwise cosine 0, mean 0), doubling to 6 draws
    [e0,e1,e2,e0,e1,e2] adds 3 same-vector pairs (cosine 1) out of 15 total,
    giving mean 3/15 = 0.2 -- NOT the original 0. Duplicating a
    pairwise-similarity population can itself move the mean, so this invariant
    is skipped as false-in-general, not merely inapplicable.
    """
    monkeypatch.setattr(consistency, "embed", _bow_embed)
    result = assert_wired(_consistency_probe)
    assert result.d0 == pytest.approx(0.0)
    assert result.d1 == pytest.approx(1.0)
    print(f"WIRED {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #133 why-this-answer -- why_answer.py:build_explanation
# Route (observability.py ~L1922-1930, POST /observability/why): chunks =
# _route_chunks(bundle.context); build_explanation(answer=bundle.
# original_answer, chunks=chunks). build_explanation calls the REAL
# provenance.attribute internally -> same monkeypatch seam as #11
# (provenance.embed), unit+patch.
# --------------------------------------------------------------------------- #


def _why_compute(source: tuple[str, str]) -> object:
    answer, context = source
    return build_explanation(answer=answer, chunks=_route_chunks(context))


_why_probe: Probe[tuple[str, str]] = Probe(
    key="why-this-answer#133",
    compute=_why_compute,
    observe=_obs_confidence,
    base_source=(_PROV_GROUNDED_ANSWER, _PROV_CONTEXT),
    perturb=_provenance_perturb,  # identical perturbation as #11: append an unsupported sentence
    relation="down",
    seam="fn-arg",
    declared_class="real-computed",
)

# Duplication invariant: same trick as #11 -- duplicating the mixed answer's
# text duplicates its claims 1:1 with identical per-claim support, so the mean
# support (confidence) is provably unchanged (mean([1,0,1,0]) == mean([1,0])).
_why_dup_probe: Probe[tuple[str, str]] = Probe(
    key="why-this-answer#133-duplication",
    compute=_why_compute,
    observe=_obs_confidence,
    base_source=_provenance_dup_base,
    perturb=_provenance_dup_perturb,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)


def test_why_this_answer_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "embed", _marker_embed)
    result = assert_wired(_why_probe)
    assert result.d0 == pytest.approx(1.0)
    assert result.d1 == pytest.approx(0.5)
    print(f"WIRED {result.key:38} {result.detail}")


def test_why_this_answer_duplication_invariant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "embed", _marker_embed)
    result = assert_invariant_ok(_why_dup_probe)
    assert result.d0 == pytest.approx(0.5)
    print(f"INV   {result.key:38} {result.detail}")


# --------------------------------------------------------------------------- #
# #10 lineage-sbom -- lineage.py:build_lineage
# Real call site is routes/chat.py:933 (chat-turn hot path), not
# observability.py: build_lineage(language=resolved_language.value,
# model=effective_model, documents=docs_for_eval); the observability routes
# only read back `bundle.lineage` (e.g. the what-changed root-cause diff).
# `_short_hash` re-reads the prompt file's bytes from `_PROMPTS_DIR` on every
# call -- no caching, no route-level alias/freeze. Seam=store (a real,
# on-disk versioned artefact), test=unit+temp: monkeypatch `_PROMPTS_DIR` to a
# temp dir and rewrite the prompt file's bytes between calls.
# --------------------------------------------------------------------------- #


def _build_lineage_probe(prompts_dir: Path) -> Probe[bytes]:
    def compute(content: bytes) -> object:
        (prompts_dir / "en.yaml").write_bytes(content)
        return lineage.build_lineage(language="en", model="stub-model", documents=[])

    return Probe(
        key="lineage-sbom#10",
        compute=compute,
        observe=_obs_prompt_version_numeric,
        base_source=b"en:\n  greeting: bonjour\n",
        perturb=lambda content: content + b"\n# a differing prompt byte\n",
        relation="changes",
        seam="store",
        declared_class="real-computed",
    )


def test_lineage_sbom_prompt_version_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lineage, "_PROMPTS_DIR", tmp_path)
    probe = _build_lineage_probe(tmp_path)
    result = assert_wired(probe)  # relation="changes" holding -> WIRED (not INVARIANT_OK)
    assert result.d0 != result.d1
    print(f"WIRED {result.key:38} {result.detail}")
