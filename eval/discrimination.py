"""The discriminating power of the catalogue — what each case MEASURES, derived from runs.

A pass rate answers "how well did the model do". It cannot answer the question this
module exists for: **does this case measure the model at all?** Three measurements say it
does not, for most of the catalogue:

* the null control passes **122 of 174 runs** with no model and zero tokens
  (:mod:`eval.ratchet`) — 70% of the score is the deterministic guard/router layer;
* **15 of 63 cases** pass with an *empty* answer;
* five full passes each of ``llama3.2:3b`` and ``llama3.2:1b`` — a model one third its
  size — produce **overlapping** absolute-score distributions ([35,36,33,36,36] against
  [33,33,35,32,31] of 52): no bar separates them (:mod:`eval.contribution`).

So the catalogue is graded here the way a model is graded there — **on the delta**, and
against the same null floor. A case earns its place by *separating* things, and separation
is a measurement:

* **DEAD** — the null control passes every run of it and no model, in any pass, ever
  breaks it. It exercises the deterministic layer. It inflates the rate and tells you
  nothing about the model.
* **INVERTED** — the null control passes it and the **reference** model — the one that ships —
  **reproducibly breaks** it. The agent is *worse than silence* there, in production. These are
  the most valuable runs in the catalogue: they measure a real harm, not a missing capability.
  Keyed on the reference model alone: a run only the *weak* model breaks is not a harm (the
  deployed agent is fine on it), it is an excellent **discriminator**, and it is counted as one.
* **DISCRIMINATING** — the strong model passes it significantly more often than the weak
  one. "Significantly" is Fisher's exact test, one-tailed, Holm-corrected across the whole
  catalogue — not a glance at two numbers.
* **REVERSED** — the *weak* model passes it significantly more often. An anomaly, never a
  credit: reported so it cannot hide.
* **NON-DISCRIMINATING** — both models behave identically *and* deterministically: they
  both always close it (the model is measured against silence, but any model will do), or
  neither ever closes it (**unreached** — no model in hand has ever passed it).
* **UNDECIDED** — a difference was observed, and ``n`` cannot certify it. This is a
  **fact, not a blank**: the honest output of an underpowered experiment is a refusal to
  rule, and the remedy is more samples, not a firmer adjective.

**Instability is orthogonal, so it is a flag and not a bucket.** A run on which the same
model both passes and fails across its own passes measures sampling noise (T2, temperature
0.2, no seed). But a run can be unstable *and* separate the models sharply — the weak model
failing 8 of 15 passes where the strong model never fails is both noisy and highly
discriminating. Filing it under "unstable" would delete the most informative case in the
catalogue. Every run therefore carries ``unstable`` alongside its class, and the counts are
reported both ways.

**The power of the catalogue is a NUMBER, and it is pinned to a catalogue.** Every verdict
here is read off runs scored against one case set. The moment the catalogue moves, the
classification describes cases that no longer exist — so this module **refuses to rule**
(:attr:`CataloguePower.refusal`) rather than classifying as best it can. Unusable is not
the same as failed (ADR 0026): a refusal is the absence of a verdict, never a verdict of
zero.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from eval.ratchet import Baseline, catalogue_version, model_spoke, report_verdicts

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

__all__ = [
    "ALPHA",
    "MIN_REPRODUCED_BREAKS",
    "CasePower",
    "CataloguePower",
    "RunClass",
    "RunPower",
    "Sample",
    "classify",
    "fisher_greater",
    "holm_reject",
]

#: Family-wise error rate for the separation test. Holm-corrected across every run in the
#: catalogue, because 174 tests at an uncorrected 5% would manufacture ~9 discriminating
#: runs out of pure noise — and this module exists to stop exactly that kind of number.
ALPHA = 0.05

#: How many passes a model must break a floor-passing run in before the inversion is real.
#: The gate already draws this line (:mod:`eval.contribution`, Rule 1: "a break is only
#: fatal once **reproduced**"), and it is drawn here identically rather than re-argued —
#: a single break in n passes is a coin, not a finding.
MIN_REPRODUCED_BREAKS = 2

RunClass = Literal[
    "dead",
    "inverted",
    "discriminating",
    "reversed",
    "undecided",
    "non_discriminating",
]

#: Which classes count as "this run measures the model". The headline number of the whole
#: exercise is the size of this union — everything else is the deterministic layer, noise,
#: or a case no model in hand has ever moved.
MEASURES_THE_MODEL: frozenset[RunClass] = frozenset({"discriminating", "inverted"})


def fisher_greater(strong_pass: int, strong_n: int, weak_pass: int, weak_n: int) -> float:
    """One-tailed Fisher exact p for "the strong model passes this more often".

    The 2x2 table is ``[[strong_pass, strong_fail], [weak_pass, weak_fail]]`` and the
    p-value is the hypergeometric tail: the probability, with both margins fixed and no
    real difference between the models, of seeing the strong model pass **at least** this
    many times. Computed in exact integer arithmetic (:func:`math.comb`) — the counts are
    tiny and a float approximation of a number that decides a gate would be a poor trade.

    Args:
        strong_pass: Passes of the strong model.
        strong_n: Total passes the strong model ran.
        weak_pass: Passes of the weak model.
        weak_n: Total passes the weak model ran.

    Returns:
        The one-tailed p-value in ``[0, 1]``. Returns ``1.0`` when either arm is empty —
        no evidence is not evidence of no effect.
    """
    if strong_n <= 0 or weak_n <= 0:
        return 1.0
    total = strong_n + weak_n
    passes = strong_pass + weak_pass
    denominator = math.comb(total, passes)
    if denominator == 0:  # pragma: no cover  unreachable while both arms are non-empty
        return 1.0
    numerator = sum(
        math.comb(strong_n, x) * math.comb(weak_n, passes - x)
        for x in range(strong_pass, min(strong_n, passes) + 1)
        if 0 <= passes - x <= weak_n
    )
    return numerator / denominator


def holm_reject(pvalues: Sequence[float], *, alpha: float = ALPHA) -> tuple[bool, ...]:
    """Holm-Bonferroni: which hypotheses survive, correcting for multiplicity.

    174 independent tests at an uncorrected 5% expect ~9 false positives — enough to
    invent a discriminating subset out of noise. Holm controls the family-wise error rate
    (the chance of *even one* false positive) and is uniformly more powerful than plain
    Bonferroni, so it costs nothing to prefer it.

    **This is what n=5 could not pay for.** With five passes per arm the smallest p a
    perfect separation can produce is ``1/C(10,5) = 0.0040``, and the tightest Holm
    threshold over 174 tests is ``0.05/174 = 0.00029``. No run in a five-pass sweep can
    clear that — the experiment was underpowered to certify a *single* discriminating case,
    whatever the two columns of numbers looked like.

    Args:
        pvalues: One p-value per test, in the caller's order.
        alpha: The family-wise error rate.

    Returns:
        A rejection mask in the caller's order — ``True`` where the null (no difference)
        is rejected.
    """
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    m = len(pvalues)
    rejected = [False] * m
    for rank, idx in enumerate(order):
        if pvalues[idx] <= alpha / (m - rank):
            rejected[idx] = True
        else:
            break  # Holm stops at the first failure — nothing above it may be rejected.
    return tuple(rejected)


@dataclass(frozen=True, slots=True)
class Sample:
    """One model's repeated replays of the whole catalogue.

    Attributes:
        model: The model that answered — as witnessed by generated tokens, never by the
            report's ``model`` field (a dead backend still writes it).
        verdicts: One ``{case_id|language: passed}`` map per pass.
        catalogue_versions: The catalogue each pass was scored against. More than one
            distinct value means the sample spans a moved catalogue and cannot be pooled.
    """

    model: str
    verdicts: tuple[dict[str, bool], ...]
    catalogue_versions: tuple[str, ...]

    @property
    def n(self) -> int:
        """Number of passes in the sample."""
        return len(self.verdicts)

    def passes(self, key: str) -> int:
        """How many of this model's passes the given run passed."""
        return sum(1 for v in self.verdicts if v.get(key) is True)

    @classmethod
    def from_reports(cls, model: str, reports: Iterable[dict[str, Any]]) -> Sample:
        """Build a sample from parsed runner reports.

        Args:
            model: The model the reports are claimed to be from.
            reports: Parsed runner reports, one per pass.

        Returns:
            The pooled sample.

        Raises:
            ValueError: If any report carries no evidence a model ever spoke. A modelless
                pass scores the deterministic layer alone; pooling one into a model's
                sample would drag every count in this module toward the floor and read as
                a *measurement* of the model. The witness is tokens (:func:`model_spoke`),
                never the ``model`` field.
        """
        verdicts: list[dict[str, bool]] = []
        versions: list[str] = []
        for i, report in enumerate(reports):
            if not model_spoke(report):
                msg = (
                    f"{model}: pass {i + 1} generated 0 output tokens — no model answered. "
                    f"A modelless pass cannot be evidence about a model."
                )
                raise ValueError(msg)
            verdicts.append(report_verdicts(report))
            versions.append(str(report.get("catalogue_version") or ""))
        return cls(model=model, verdicts=tuple(verdicts), catalogue_versions=tuple(versions))


@dataclass(frozen=True, slots=True)
class RunPower:
    """What one ``case_id|language`` run measures.

    Attributes:
        key: The ``case_id|language`` run.
        case_id: The case the run belongs to.
        language: The language the run was scored in.
        floor_passes: Whether the null control (no model at all) passes this run.
        strong_passes: Passes of the strong model, of ``strong_n``.
        weak_passes: Passes of the weak model, of ``weak_n``.
        p_greater: One-tailed Fisher p for "the strong model is better here".
        p_less: One-tailed Fisher p for "the *weak* model is better here".
        klass: The verdict.
        unstable: Whether some model both passed and failed this run across its own
            passes — orthogonal to ``klass``, because a run can be noisy *and* decisive.
        breaks: How many passes each model broke this run in, when the floor passes it.
    """

    key: str
    case_id: str
    language: str
    floor_passes: bool
    strong_passes: int
    strong_n: int
    weak_passes: int
    weak_n: int
    p_greater: float
    p_less: float
    klass: RunClass
    unstable: bool
    strong_breaks: int
    weak_breaks: int

    @property
    def measures_the_model(self) -> bool:
        """Whether this run tells you anything about the model at all."""
        return self.klass in MEASURES_THE_MODEL


@dataclass(frozen=True, slots=True)
class CasePower:
    """What one case measures — the aggregate of its 1-3 language runs.

    A case is credited with the **strongest** evidence any of its language runs shows.
    A case that is dead in French and discriminating in German *does* measure the model:
    it measures it in German. Collapsing it to its weakest run would understate the
    catalogue, and averaging the classes of runs that mean different things would be
    arithmetic on adjectives.

    Attributes:
        case_id: The case.
        klass: The strongest class among its runs (see :data:`_CLASS_RANK`).
        languages: The languages the case was scored in.
        run_classes: The class of each language run, keyed by language.
        unstable: Whether any of its runs is unstable.
    """

    case_id: str
    klass: RunClass
    languages: tuple[str, ...]
    run_classes: dict[str, RunClass]
    unstable: bool

    @property
    def measures_the_model(self) -> bool:
        """Whether this case tells you anything about the model, in any language."""
        return self.klass in MEASURES_THE_MODEL


#: Strongest evidence first. A case is filed under the best thing any of its runs does.
#: ``inverted`` outranks ``discriminating`` because a reproduced harm is rarer and costs
#: more to lose; both are counted together in the headline, so the order below only decides
#: which label a case wears, never whether it is credited.
_CLASS_RANK: dict[RunClass, int] = {
    "inverted": 0,
    "discriminating": 1,
    "reversed": 2,
    "undecided": 3,
    "non_discriminating": 4,
    "dead": 5,
}


@dataclass(frozen=True, slots=True)
class CataloguePower:
    """The discriminating power of a whole catalogue, measured against a model pair.

    Attributes:
        refusal: Set iff the classification could not be made at all — the runs and the
            floor do not name the same catalogue. Every count is then left at zero rather
            than computed over a population that does not exist. **Not** a verdict of zero
            (ADR 0026).
        catalogue_version: The case set every input names.
        strong_model / weak_model: The pair the separation was measured against.
        strong_n / weak_n: Passes per arm — the honesty of every p-value below.
        runs: Per-run verdicts.
        cases: Per-case verdicts.
        alpha: The family-wise error rate the separation was certified at.
    """

    refusal: str | None
    catalogue_version: str
    strong_model: str
    weak_model: str
    strong_n: int
    weak_n: int
    alpha: float
    runs: tuple[RunPower, ...] = ()
    cases: tuple[CasePower, ...] = ()
    reasons: list[str] = field(default_factory=list)

    def run_counts(self) -> dict[RunClass, int]:
        """How many runs fall in each class."""
        counts: dict[RunClass, int] = dict.fromkeys(_CLASS_RANK, 0)
        for r in self.runs:
            counts[r.klass] += 1
        return counts

    def case_counts(self) -> dict[RunClass, int]:
        """How many cases fall in each class."""
        counts: dict[RunClass, int] = dict.fromkeys(_CLASS_RANK, 0)
        for c in self.cases:
            counts[c.klass] += 1
        return counts

    @property
    def discriminating_runs(self) -> int:
        """Runs that measure the model — the number the ratchet freezes."""
        return sum(1 for r in self.runs if r.measures_the_model)

    @property
    def discriminating_cases(self) -> int:
        """Cases that measure the model, in at least one language."""
        return sum(1 for c in self.cases if c.measures_the_model)

    @property
    def unstable_runs(self) -> int:
        """Runs on which some model both passed and failed across its own passes."""
        return sum(1 for r in self.runs if r.unstable)

    @property
    def unstable_cases(self) -> int:
        """Cases with at least one unstable run."""
        return sum(1 for c in self.cases if c.unstable)

    def render(self) -> str:
        """Multi-line human summary for the CI log."""
        if self.refusal is not None:
            return "\n".join(
                [
                    "[catalogue-power REFUSED] NOT CLASSIFIED",
                    f"  - {self.refusal}",
                    "  No class, no count and no power are reported: each would describe "
                    "cases that no",
                    "  longer exist. Re-measure against the current catalogue "
                    "(`make eval-power-write`).",
                ]
            )
        rc, cc = self.run_counts(), self.case_counts()
        return "\n".join(
            [
                f"[catalogue-power] {self.catalogue_version} — "
                f"{self.strong_model} (n={self.strong_n}) vs {self.weak_model} "
                f"(n={self.weak_n}), Holm alpha={self.alpha}",
                f"  cases  {len(self.cases):3}: "
                f"{cc['dead']} dead, {self.unstable_cases} unstable, "
                f"{cc['non_discriminating']} non-discriminating, "
                f"{cc['discriminating']} discriminating, {cc['inverted']} inverted, "
                f"{cc['undecided']} undecided, {cc['reversed']} reversed",
                f"  runs   {len(self.runs):3}: "
                f"{rc['dead']} dead, {self.unstable_runs} unstable, "
                f"{rc['non_discriminating']} non-discriminating, "
                f"{rc['discriminating']} discriminating, {rc['inverted']} inverted, "
                f"{rc['undecided']} undecided, {rc['reversed']} reversed",
                f"  MEASURE THE MODEL: {self.discriminating_cases}/{len(self.cases)} cases, "
                f"{self.discriminating_runs}/{len(self.runs)} runs",
            ]
        )


def _version_refusal(baseline: Baseline, strong: Sample, weak: Sample) -> str | None:
    """Why these runs and this floor cannot be pooled — or ``None`` if they can.

    Mirrors :func:`eval.ratchet.floor_mismatch`, and is strict for the same reason: an
    *unknown* version is not a matching one. A pass that never said which catalogue it was
    scored against cannot be shown to be judged by this floor.
    """
    if not baseline.catalogue_version:
        return (
            "the null floor does not name the catalogue it was captured against — it "
            "cannot be shown to judge these runs. Regenerate it (`make eval-null-write`)."
        )
    versions = {v for s in (strong, weak) for v in s.catalogue_versions}
    if not versions or any(not v for v in versions):
        return (
            "a pass does not name the catalogue it was scored against — it cannot be "
            "shown to be judged by this floor. Re-run it with a current runner."
        )
    if len(versions) > 1:
        return (
            f"the passes span more than one catalogue ({', '.join(sorted(versions))}) — "
            f"they cannot be pooled into one sample"
        )
    version = versions.pop()
    if version != baseline.catalogue_version:
        return (
            f"catalogue moved: the passes are {version!r}, the null floor is "
            f"{baseline.catalogue_version!r} — re-measure rather than classifying across "
            f"case sets"
        )
    return None


def classify(
    baseline: Baseline,
    strong: Sample,
    weak: Sample,
    *,
    alpha: float = ALPHA,
    min_reproduced: int = MIN_REPRODUCED_BREAKS,
) -> CataloguePower:
    """Classify every run of the catalogue by what it actually measures.

    The classification is a **pure function of the stored runs**: the same passes and the
    same floor always produce the same verdict, and nothing is read from the case files —
    a case that *declared* its own discriminating power would be making a claim, and this
    module exists to replace claims with measurements.

    Args:
        baseline: The committed null control — the floor, and the definition of the run set.
        strong: Repeated passes of the model the gate must ADMIT.
        weak: Repeated passes of the model the gate must REJECT.
        alpha: Family-wise error rate for the separation test.
        min_reproduced: Breaks needed before an inversion is real rather than a coin.

    Returns:
        A :class:`CataloguePower`. If the inputs do not name one catalogue, it carries a
        ``refusal`` and no counts — the classification was not made, which is not the same
        as a classification of zero.
    """
    refusal = _version_refusal(baseline, strong, weak)
    if refusal is not None:
        return CataloguePower(
            refusal=refusal,
            catalogue_version=baseline.catalogue_version,
            strong_model=strong.model,
            weak_model=weak.model,
            strong_n=strong.n,
            weak_n=weak.n,
            alpha=alpha,
        )

    keys = sorted(baseline.verdicts)

    # Every run is tested, in both directions, and the whole catalogue is ONE family: a
    # subset chosen after seeing the numbers would be a corrected p-value in name only.
    p_greater = [fisher_greater(strong.passes(k), strong.n, weak.passes(k), weak.n) for k in keys]
    p_less = [fisher_greater(weak.passes(k), weak.n, strong.passes(k), strong.n) for k in keys]
    reject_greater = holm_reject(p_greater, alpha=alpha)
    reject_less = holm_reject(p_less, alpha=alpha)

    runs: list[RunPower] = []
    for i, key in enumerate(keys):
        case_id, _, language = key.partition("|")
        floor = baseline.verdicts[key]
        s, w = strong.passes(key), weak.passes(key)
        strong_breaks = strong.n - s
        weak_breaks = weak.n - w
        unstable = (0 < s < strong.n) or (0 < w < weak.n)

        klass: RunClass
        if floor and strong_breaks >= min_reproduced:
            # The floor passes it and the REFERENCE model — the one that ships — reproducibly
            # breaks it. The agent is worse than silence here, in production. That is a real
            # harm, and it is the finding whether or not the two models happen to differ on
            # it, so it is checked before the separation test.
            #
            # Keyed on the STRONG model alone, deliberately. A run only the *weak* model
            # breaks is not a harm — the deployed agent is fine on it — it is an excellent
            # DISCRIMINATOR: the case catches a bad model by making it harmful. Calling that
            # an "inversion" would report a defect the product does not have, and would hide
            # the one thing the catalogue is starving for. It falls through to the separation
            # test below, which is where it belongs.
            klass = "inverted"
        elif reject_greater[i]:
            klass = "discriminating"
        elif reject_less[i]:
            klass = "reversed"
        elif floor and max(strong_breaks, weak_breaks) > 0:
            # A break was seen on a floor-passing run, and n cannot certify it: either the
            # reference model broke it once (an inversion candidate, not reproduced) or the
            # weak model broke it without separating significantly. Not dead — a model DID
            # touch it. The remedy is more passes, not a firmer adjective.
            klass = "undecided"
        elif floor:
            klass = "dead"
        else:
            # The floor fails it and no separation survived the correction. Two very
            # different reasons can put a run here, and collapsing them would hide the
            # only one that is actionable.
            both_deterministic = s in (0, strong.n) and w in (0, weak.n)
            same_outcome = (s > 0) == (w > 0)
            klass = (
                # Both models, every pass, the same verdict: they are indistinguishable
                # here — both always close it, or neither ever does (unreached).
                "non_discriminating"
                if both_deterministic and same_outcome
                # A difference WAS observed and n could not certify it. The remedy is more
                # passes, not a firmer adjective.
                else "undecided"
            )

        runs.append(
            RunPower(
                key=key,
                case_id=case_id,
                language=language,
                floor_passes=floor,
                strong_passes=s,
                strong_n=strong.n,
                weak_passes=w,
                weak_n=weak.n,
                p_greater=p_greater[i],
                p_less=p_less[i],
                klass=klass,
                unstable=unstable,
                strong_breaks=strong_breaks,
                weak_breaks=weak_breaks,
            )
        )

    cases = _aggregate_cases(runs)
    return CataloguePower(
        refusal=None,
        catalogue_version=baseline.catalogue_version,
        strong_model=strong.model,
        weak_model=weak.model,
        strong_n=strong.n,
        weak_n=weak.n,
        alpha=alpha,
        runs=tuple(runs),
        cases=cases,
        reasons=[],
    )


def _aggregate_cases(runs: Sequence[RunPower]) -> tuple[CasePower, ...]:
    """Fold per-language runs into per-case verdicts, keeping the strongest evidence."""
    by_case: dict[str, list[RunPower]] = {}
    for r in runs:
        by_case.setdefault(r.case_id, []).append(r)
    cases = [
        CasePower(
            case_id=case_id,
            klass=min((r.klass for r in group), key=lambda k: _CLASS_RANK[k]),
            languages=tuple(sorted(r.language for r in group)),
            run_classes={r.language: r.klass for r in sorted(group, key=lambda r: r.language)},
            unstable=any(r.unstable for r in group),
        )
        for case_id, group in sorted(by_case.items())
    ]
    return tuple(cases)


def measured_catalogue_version(power: CataloguePower) -> str:
    """Re-derive the catalogue identity from the cases actually classified.

    Never inherited: a classification that holds 63 cases *is* a 63-case classification,
    and one that holds 40 may not go on wearing the version string of the set it was cut
    from (the same trap :func:`eval.contribution.restrict_baseline` had to close).
    """
    return catalogue_version(c.case_id for c in power.cases)


# ---------------------------------------------------------------------------------------
# The evidence, and the ratchet that stops it drifting.
# ---------------------------------------------------------------------------------------
#
# The raw passes are gitignored scratch (`.eval-noise/`, ~200 KB each, thirty of them): a
# calibration pass is not a published result. But a classification nobody can recompute is
# an assertion, and this module exists to abolish assertions. So the **evidence the
# classifier actually consumes** is committed instead — the verdict matrix, which is
# exactly what :func:`eval.ratchet.report_verdicts` reduces a report to, plus the liveness
# witness (generated tokens) and the SHA-256 of the raw report each column came from.
#
# Nothing is lost in the reduction and nothing is smuggled in: CI re-derives the whole
# classification from the committed matrix, and anyone holding the raw passes can prove the
# matrix is theirs by re-hashing them.


@dataclass(frozen=True, slots=True)
class PassProvenance:
    """Where one column of the verdict matrix came from, and that a model really spoke."""

    model: str
    catalogue_version: str
    output_tokens: int
    sha256: str
    source: str


def sample_from_matrix(
    model: str, columns: Sequence[dict[str, Any]], provenance: Sequence[PassProvenance]
) -> Sample:
    """Rebuild a :class:`Sample` from the committed verdict matrix.

    The liveness witness survives the reduction: a column whose pass generated zero tokens
    is refused here exactly as :meth:`Sample.from_reports` refuses the report it came from.
    A matrix is a smaller artefact than a run, never a laxer one.

    Args:
        model: The model whose passes these are.
        columns: One ``{case_id|language: passed}`` map per pass.
        provenance: The matching provenance record for each pass.

    Returns:
        The pooled sample.

    Raises:
        ValueError: If a pass carries no evidence a model spoke, or if the provenance does
            not line up with the columns.
    """
    if len(columns) != len(provenance):
        msg = (
            f"{model}: {len(columns)} verdict column(s) but {len(provenance)} provenance "
            f"record(s) — the matrix cannot be shown to come from the runs it names"
        )
        raise ValueError(msg)
    for i, prov in enumerate(provenance):
        if prov.output_tokens <= 0:
            msg = (
                f"{model}: pass {i + 1} ({prov.source}) records 0 output tokens — no model "
                f"answered. A modelless pass cannot be evidence about a model."
            )
            raise ValueError(msg)
    return Sample(
        model=model,
        verdicts=tuple({str(k): bool(v) for k, v in c.items()} for c in columns),
        catalogue_versions=tuple(p.catalogue_version for p in provenance),
    )


def dump_samples(
    keys: Sequence[str],
    strong: Sample,
    weak: Sample,
    strong_prov: Sequence[PassProvenance],
    weak_prov: Sequence[PassProvenance],
    *,
    note: str = "",
) -> str:
    """Serialise the evidence: the key list once, then one bitstring per pass.

    ``'1'`` is a pass, ``'0'`` a failure, in the order of ``keys``. A 174-character line
    per pass rather than a 174-entry object: thirty passes stay a few kilobytes, and — the
    reason that matters — **a verdict that drifts shows up as one character in a diff**. A
    reviewer can see which run flipped. A 200 KB blob per pass hides exactly that.
    """

    def _bits(sample: Sample) -> list[str]:
        return ["".join("1" if v.get(k) else "0" for k in keys) for v in sample.verdicts]

    def _prov(records: Sequence[PassProvenance]) -> list[dict[str, Any]]:
        return [
            {
                "source": p.source,
                "sha256": p.sha256,
                "output_tokens": p.output_tokens,
                "catalogue_version": p.catalogue_version,
            }
            for p in records
        ]

    payload = {
        "kind": "discrimination_samples",
        "catalogue_version": strong.catalogue_versions[0] if strong.catalogue_versions else "",
        "note": note,
        "keys": list(keys),
        "strong": {"model": strong.model, "passes": _prov(strong_prov), "matrix": _bits(strong)},
        "weak": {"model": weak.model, "passes": _prov(weak_prov), "matrix": _bits(weak)},
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def load_samples(path: Path) -> tuple[list[str], Sample, Sample]:
    """Read the committed evidence back into ``(keys, strong, weak)``.

    Raises:
        ValueError: If the artefact is malformed, or if any pass records zero generated
            tokens — the liveness witness is enforced on the way in, not just on the way
            out.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("kind") != "discrimination_samples":
        msg = f"{path} is not a discrimination-samples artefact"
        raise ValueError(msg)
    keys = [str(k) for k in payload.get("keys") or ()]
    if not keys:
        msg = f"{path} names no runs"
        raise ValueError(msg)

    def _side(name: str) -> tuple[Sample, list[PassProvenance]]:
        side = payload.get(name) or {}
        model = str(side.get("model") or "")
        matrix = side.get("matrix") or []
        prov = [
            PassProvenance(
                model=model,
                catalogue_version=str(p.get("catalogue_version") or ""),
                output_tokens=int(p.get("output_tokens") or 0),
                sha256=str(p.get("sha256") or ""),
                source=str(p.get("source") or ""),
            )
            for p in side.get("passes") or []
        ]
        columns: list[dict[str, Any]] = []
        for row in matrix:
            bits = str(row)
            if len(bits) != len(keys):
                msg = (
                    f"{path}: a {name} pass has {len(bits)} verdicts for {len(keys)} runs — "
                    f"the matrix does not describe this catalogue"
                )
                raise ValueError(msg)
            columns.append({k: bits[i] == "1" for i, k in enumerate(keys)})
        return sample_from_matrix(model, columns, prov), prov

    strong, _ = _side("strong")
    weak, _ = _side("weak")
    return keys, strong, weak


def dump_power(power: CataloguePower, *, method: str = "") -> str:
    """Serialise a classification — every count derived, every run named."""
    payload = {
        "kind": "catalogue_power",
        "catalogue_version": power.catalogue_version,
        "strong_model": power.strong_model,
        "strong_n": power.strong_n,
        "weak_model": power.weak_model,
        "weak_n": power.weak_n,
        "alpha": power.alpha,
        "method": method,
        "power": {
            "discriminating_cases": power.discriminating_cases,
            "discriminating_runs": power.discriminating_runs,
            "total_cases": len(power.cases),
            "total_runs": len(power.runs),
            "unstable_cases": power.unstable_cases,
            "unstable_runs": power.unstable_runs,
        },
        "case_counts": power.case_counts(),
        "run_counts": power.run_counts(),
        "cases": {
            c.case_id: {
                "class": c.klass,
                "unstable": c.unstable,
                "languages": dict(sorted(c.run_classes.items())),
            }
            for c in power.cases
        },
        "runs": {
            r.key: {
                "class": r.klass,
                "floor_passes": r.floor_passes,
                "strong": f"{r.strong_passes}/{r.strong_n}",
                "weak": f"{r.weak_passes}/{r.weak_n}",
                "unstable": r.unstable,
                "p_greater": round(r.p_greater, 6),
            }
            for r in power.runs
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def load_power(path: Path) -> CataloguePower:
    """Read a committed classification back, for the ratchet to compare against."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("kind") != "catalogue_power":
        msg = f"{path} is not a catalogue-power artefact"
        raise ValueError(msg)
    runs = tuple(
        RunPower(
            key=str(key),
            case_id=str(key).partition("|")[0],
            language=str(key).partition("|")[2],
            floor_passes=bool(r.get("floor_passes")),
            strong_passes=int(str(r.get("strong", "0/0")).split("/")[0]),
            strong_n=int(payload.get("strong_n") or 0),
            weak_passes=int(str(r.get("weak", "0/0")).split("/")[0]),
            weak_n=int(payload.get("weak_n") or 0),
            p_greater=float(r.get("p_greater") or 1.0),
            p_less=1.0,
            klass=str(r.get("class") or "dead"),  # type: ignore[arg-type]
            unstable=bool(r.get("unstable")),
            strong_breaks=0,
            weak_breaks=0,
        )
        for key, r in (payload.get("runs") or {}).items()
    )
    return CataloguePower(
        refusal=None,
        catalogue_version=str(payload.get("catalogue_version") or ""),
        strong_model=str(payload.get("strong_model") or ""),
        weak_model=str(payload.get("weak_model") or ""),
        strong_n=int(payload.get("strong_n") or 0),
        weak_n=int(payload.get("weak_n") or 0),
        alpha=float(payload.get("alpha") or ALPHA),
        runs=runs,
        cases=_aggregate_cases(runs),
    )


@dataclass(frozen=True, slots=True)
class PowerVerdict:
    """The outcome of the power ratchet."""

    ok: bool
    refusal: str | None
    measured_cases: int
    measured_runs: int
    floor_cases: int
    floor_runs: int
    drift: tuple[str, ...] = ()
    reasons: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Multi-line human summary for the CI log."""
        if self.refusal is not None:
            return f"[catalogue-power REFUSED] NOT JUDGED\n  - {self.refusal}"
        verdict = "PASS" if self.ok else "BLOCK"
        head = (
            f"[catalogue-power {verdict}] the catalogue measures the model on "
            f"{self.measured_cases} case(s) / {self.measured_runs} run(s) "
            f"— floor {self.floor_cases} / {self.floor_runs}"
        )
        if self.ok:
            return head
        return head + "\n" + "\n".join(f"  - {r}" for r in self.reasons)


def check_power(
    power: CataloguePower,
    frozen: CataloguePower | None,
    *,
    floor_cases: int,
    floor_runs: int,
) -> PowerVerdict:
    """The ratchet: the catalogue's discriminating power is a number, and it may not fall.

    Two different failures, deliberately not collapsed:

    * **The power dropped.** Fewer cases measure the model than the frozen floor. Deleting
      a discriminating case, or blunting one until the models stop separating on it, turns
      this red. Adding a *dead* case cannot turn it red — nothing was lost — but it cannot
      hide either: the catalogue version moves, the classification is refused until it is
      re-measured, and the re-measured density falls in the diff for a human to see.
    * **The classification drifted.** The frozen per-run verdicts no longer match what the
      stored evidence produces. That means the *classifier* changed, or the evidence did,
      and either way the frozen number is describing something that is no longer there.

    Args:
        power: The classification re-derived from the committed evidence.
        frozen: The committed classification, or ``None`` to check the floor alone.
        floor_cases: The frozen high-water mark, in cases.
        floor_runs: The frozen high-water mark, in runs.

    Returns:
        A :class:`PowerVerdict`. A refusal (the catalogue moved) is **not** a failure: the
        power was not judged, which is the honest output of an expired witness.
    """
    if power.refusal is not None:
        return PowerVerdict(
            ok=False,
            refusal=power.refusal,
            measured_cases=0,
            measured_runs=0,
            floor_cases=floor_cases,
            floor_runs=floor_runs,
        )

    reasons: list[str] = []
    drift: tuple[str, ...] = ()
    if frozen is not None:
        was = {r.key: r.klass for r in frozen.runs}
        now = {r.key: r.klass for r in power.runs}
        drift = tuple(
            sorted(
                f"{k}: {was.get(k, '(absent)')} -> {now.get(k, '(absent)')}"
                for k in set(was) | set(now)
                if was.get(k) != now.get(k)
            )
        )
        reasons += [f"classification drifted: {d}" for d in drift]

    if power.discriminating_cases < floor_cases:
        reasons.append(
            f"the catalogue LOST discriminating power: {power.discriminating_cases} cases "
            f"measure the model, the frozen floor is {floor_cases}. A case that separates a "
            f"good model from a bad one is the scarcest thing in this repository — it does "
            f"not get removed silently."
        )
    if power.discriminating_runs < floor_runs:
        reasons.append(
            f"the catalogue LOST discriminating power: {power.discriminating_runs} runs "
            f"measure the model, the frozen floor is {floor_runs}."
        )

    return PowerVerdict(
        ok=not reasons,
        refusal=None,
        measured_cases=power.discriminating_cases,
        measured_runs=power.discriminating_runs,
        floor_cases=floor_cases,
        floor_runs=floor_runs,
        drift=drift,
        reasons=reasons,
    )
