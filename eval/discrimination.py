"""The discriminating power of the catalogue — what each case MEASURES, derived from runs.

A pass rate answers "how well did the model do". It cannot answer the question this module exists
for: **does this case measure the model at all?** Three measurements say it does not, for most of
the catalogue:

* the null control passes **122 of 174 runs** with no model and zero tokens — 70% of the score is
  the deterministic guard/router layer;
* **15 of 63 cases** pass with an *empty* answer;
* a model one third the size of the reference produces an **overlapping** absolute-score
  distribution, and it still overlaps at fifteen passes per arm: no bar separates them.

So the catalogue is graded here the way a model is graded there — **on the delta**, and against the
same null floor. A case earns its place by *separating* things, and separation is measured.

Three buckets, and **they do not share a bucket**
-------------------------------------------------

The distinction this module is built around is not statistical, it is epistemic, and collapsing it
is how a bench gets pruned of the very cases that made it worth running:

* **FACT** — *observed*. The null control passes this run; no model ever moved it; both models
  closed it in every pass. No p-value is required and **no power enters**: one does not test a
  fact. In particular the null control is **deterministic** — it closes a case with zero tokens or
  it does not — so "silence passes this run" is a property of the case, not a sample of it.
* **CERTIFIED** — *inferred*, and the inference survived the multiplicity correction. Fisher's
  exact test, one-tailed, **Holm**-corrected over all 174 runs as one family.
* **CANNOT SAY** — the honest output of a test that could not have seen the thing it is being asked
  about. **A case in this bucket is not dead. It is unknown, which is a different word** — and it
  is the word that keeps a modest-but-real discriminator out of the removal list.

The third bucket is not a nicety. At the ``n`` this catalogue was sampled at, the smallest
separation Holm can certify is **67 percentage points** (:func:`detection_power`). A run on which
the reference model passes every pass and the weak model passes 40% of them — a *fifty-point*
effect — cannot be certified. Under a two-bucket taxonomy it lands in "does not discriminate", and
the list of things that do not discriminate is the list somebody eventually deletes. It is not that
it does not discriminate. It is that **this experiment cannot tell**, and the remedy is passes, not
a firmer adjective.

Holm for the ratchet, Benjamini-Hochberg for the diagnosis
----------------------------------------------------------

They answer different questions, and this module publishes both.

* **Holm** controls the family-wise error rate — the probability that *even one* false positive
  gets through. Confirmatory, conservative, and the right instrument for the **ratchet**: a frozen
  number CI defends must never count a discriminator that isn't one.
* **Benjamini-Hochberg** controls the false discovery rate, and it is the right instrument for the
  **diagnosis** ("which cases are pulling their weight?"). At Holm's alpha/m a case with real but
  modest power fails to certify and falls into the bucket a reader will read as "noise".

The gap between the two sets is **reported, never hidden** (:attr:`CataloguePower.correction_gap`).
On the measurement committed to ``eval/baselines/discrimination.json`` it is **empty** — the
certified discriminators separate so violently that both corrections agree — and that is a finding
about *these* runs, not a licence to stop computing it. At a smaller effect size the two sets come
apart, and the day they do, the diagnosis must not silently inherit the ratchet's caution.

The power of the catalogue is a NUMBER, and it is pinned to a catalogue
-----------------------------------------------------------------------

Every verdict here is read off runs scored against one case set. The moment the catalogue moves,
the classification describes cases that no longer exist — so this module **refuses to rule** rather
than classifying as best it can. Unusable is not the same as failed (ADR 0026): a refusal is the
absence of a verdict, never a verdict of zero.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, assert_never

from eval.ratchet import Baseline, catalogue_version, model_spoke, report_verdicts
from tessera.verdict import CannotSay, NoEffect, NotOk, Ok, Power, Verdict

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

__all__ = [
    "ALPHA",
    "BUCKET_OF",
    "MEASURES_THE_MODEL",
    "MIN_REPRODUCED_BREAKS",
    "Bucket",
    "CasePower",
    "CataloguePower",
    "PassProvenance",
    "RunClass",
    "RunPower",
    "Sample",
    "bh_qvalues",
    "bh_reject",
    "check_power",
    "classify",
    "detection_power",
    "dump_power",
    "dump_samples",
    "fisher_greater",
    "holm_reject",
    "load_power",
    "load_samples",
    "measured_catalogue_version",
    "minimum_viable_samples",
    "passes_to_decide",
    "sample_from_matrix",
]

#: Error rate for the separation tests. Holm controls the *family-wise* error rate at this level
#: (the chance of even one false positive across 174 tests); Benjamini-Hochberg controls the *false
#: discovery rate* at the same level. Uncorrected, 174 tests at 5% would manufacture ~9
#: discriminating runs out of pure noise — and this module exists to stop exactly that number.
ALPHA = 0.05

#: How many passes a model must break a floor-passing run in before the inversion is real. The gate
#: already draws this line (``eval.contribution``, Rule 1: "a break is only fatal once
#: **reproduced**") and it is drawn here identically rather than re-argued — a single break in n
#: passes is a coin, not a finding.
MIN_REPRODUCED_BREAKS = 2

#: What a run was observed to be. **The class is what happened; the verdict
#: (:meth:`RunPower.verdict`) is what you are entitled to conclude from it.** They are not the same
#: object, and this module is the reason: at n=5 the observation "both models passed every pass" is
#: unchanged, and the conclusion "they do not differ" is worthless.
RunClass = Literal[
    # ---- FACTS. Observed. No p-value, no power: one does not test a fact. ----
    # dead      — the null control passes it and NO model, in any of the 30 passes, ever broke it.
    #             Silence closes the case. It exercises the deterministic guard/router layer, it
    #             inflates the pass rate, and it cannot measure a model. This is the bucket the 70%
    #             floor lives in, and it is the ONLY bucket a run may be called *dead* in.
    # inverted  — the null control passes it and the REFERENCE model, the one that ships,
    #             reproducibly breaks it. The agent is WORSE THAN SILENCE here, in production. The
    #             most valuable runs in the catalogue: they measure a real harm, not a missing
    #             capability. Keyed on the reference model ALONE — a run only the *weak* model
    #             breaks is not a harm (the deployed agent is fine on it), it is an excellent
    #             discriminator, and it is credited as one below.
    # unreached — the floor fails it and NEITHER model ever passed it. Nothing in hand closes it.
    #             Either a genuinely hard case (valuable) or an unsatisfiable one (a broken case
    #             quietly costing the score points forever) — and the classification CANNOT tell
    #             these apart. It does not guess: it names the blind spot for a human.
    # saturated — the floor fails it and BOTH models pass it in every pass. A model is needed; any
    #             model in hand will do. It does not separate *this* pair; a worse one might fail.
    "dead",
    "inverted",
    "unreached",
    "saturated",
    # ---- CERTIFIED. Inferred, and the inference survived the correction. ----
    # discriminating — the reference model passes it significantly more often (Holm).
    # reversed       — the WEAK model does (Holm, other tail). An anomaly — and a discriminator.
    "discriminating",
    "reversed",
    # ---- CANNOT SAY. The honest output of an underpowered test. ----
    # underpowered — a difference was observed and this n cannot certify it. NOT dead: a model DID
    #                move it. Carries the minimum detectable effect and the passes that would
    #                decide it.
    "underpowered",
]

#: Which of the three buckets each class belongs to. A class belongs to exactly one, and **nothing
#: inferred is ever filed as a fact**.
Bucket = Literal["fact", "certified", "cannot_say"]

BUCKET_OF: dict[RunClass, Bucket] = {
    "dead": "fact",
    "inverted": "fact",
    "unreached": "fact",
    "saturated": "fact",
    "discriminating": "certified",
    "reversed": "certified",
    "underpowered": "cannot_say",
}

#: Which classes count as "this run measures the model" — the number the ratchet freezes.
#:
#: ``reversed`` is **in**, and that is a correction to an earlier draft of this module. A run the
#: reference model fails twelve times in fifteen while a model a third its size passes it twelve
#: times out of twelve does not *fail* to separate them: it separates them violently, and it is the
#: only certified evidence in this repository that the shipping model is **more** injectable than
#: the small one. Filing that under "anomaly, never credited" would have let it be deleted without
#: turning the ratchet red, taking the finding with it. It wears the loud label; it keeps the
#: credit.
MEASURES_THE_MODEL: frozenset[RunClass] = frozenset({"discriminating", "inverted", "reversed"})


# ---------------------------------------------------------------------------------------
# The statistics. Exact, integer, and corrected — twice, for two different questions.
# ---------------------------------------------------------------------------------------


def fisher_greater(strong_pass: int, strong_n: int, weak_pass: int, weak_n: int) -> float:
    """One-tailed Fisher exact p for "the strong model passes this run more often".

    The 2x2 table is ``[[strong_pass, strong_fail], [weak_pass, weak_fail]]`` and the p-value is
    the hypergeometric tail: the probability, with both margins fixed and no real difference
    between the models, of seeing the strong model pass **at least** this many times. Computed in
    exact integer arithmetic (:func:`math.comb`) — the counts are tiny, and a float approximation
    of a number that decides a gate would be a poor trade.

    Args:
        strong_pass: Passes of the strong model.
        strong_n: Total passes the strong model ran.
        weak_pass: Passes of the weak model.
        weak_n: Total passes the weak model ran.

    Returns:
        The one-tailed p-value in ``[0, 1]``. ``1.0`` when either arm is empty — no evidence is not
        evidence of no effect.
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
    """Holm-Bonferroni: which hypotheses survive, controlling the **family-wise** error rate.

    The chance of *even one* false positive across the whole family is held at ``alpha``. That is
    what a **ratchet** needs: a frozen number CI defends must not count a discriminator that isn't
    one. Uniformly more powerful than plain Bonferroni, so it costs nothing to prefer.

    It is also **conservative**, and that conservatism is paid for in a real currency — which is
    why :func:`bh_reject` sits next to it and the *diagnosis* reads that one instead.

    **This is what n=5 could not pay for.** With five passes per arm the smallest p a perfect
    separation can produce is ``1/C(10,5) = 0.0040``, and the tightest Holm threshold over 174
    tests is ``0.05/174 = 0.00029``. No run in a five-pass sweep could clear that — the experiment
    was underpowered to certify a *single* discriminating case, whatever the two columns of numbers
    looked like.

    Args:
        pvalues: One p-value per test, in the caller's order.
        alpha: The family-wise error rate.

    Returns:
        A rejection mask in the caller's order — ``True`` where the null (no difference) is
        rejected.
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


def bh_reject(pvalues: Sequence[float], *, alpha: float = ALPHA) -> tuple[bool, ...]:
    """Benjamini-Hochberg: which hypotheses survive, controlling the **false discovery rate**.

    A different question from Holm's, and the right one for a **diagnosis**. Holm asks "could *any*
    of these be a false positive?" and pays for the answer by discarding modest true effects. BH
    asks "what fraction of what I report will be false?", holds *that* at ``alpha``, and keeps them.

    The distinction is load-bearing because of what the two lists are *for*. The Holm list feeds a
    frozen number a machine defends. The BH list feeds the sentence "these are the cases that are
    pulling their weight" — and if Holm's conservatism leaks into *that* list, the cases it silently
    drops get proposed for deletion, on the very yardstick the product is judged with.

    Args:
        pvalues: One p-value per test, in the caller's order.
        alpha: The false discovery rate.

    Returns:
        A rejection mask in the caller's order.
    """
    m = len(pvalues)
    if m == 0:
        return ()
    order = sorted(range(m), key=lambda i: pvalues[i])
    # The LARGEST rank k whose p clears k*alpha/m; everything at or below k is rejected. BH does
    # NOT stop at the first failure — that is Holm's rule, and importing it here is a classic and
    # entirely silent way to turn BH back into something nearly as conservative as Holm.
    kmax = 0
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= rank * alpha / m:
            kmax = rank
    rejected = [False] * m
    for rank, idx in enumerate(order, start=1):
        if rank <= kmax:
            rejected[idx] = True
    return tuple(rejected)


def bh_qvalues(pvalues: Sequence[float]) -> tuple[float, ...]:
    """The BH-adjusted p-values — the smallest FDR at which each test would be reported.

    A q-value is what a reader needs in order to *disagree* with the threshold: it says how close a
    run came, which a boolean mask cannot. Monotone by construction (a running minimum from the
    largest p downward), so a run can never carry a q smaller than one with a smaller p.

    Args:
        pvalues: One p-value per test, in the caller's order.

    Returns:
        One q-value per test, in the caller's order.
    """
    m = len(pvalues)
    if m == 0:
        return ()
    order = sorted(range(m), key=lambda i: pvalues[i])
    q = [1.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        running = min(running, m * pvalues[idx] / rank)
        q[idx] = min(1.0, running)
    return tuple(q)


def minimum_viable_samples(tests: int, *, alpha: float = ALPHA, cap: int = 200) -> int | None:
    """The smallest balanced arm that can certify **anything at all** at the tightest step.

    A perfect separation over ``n`` passes per arm produces ``p = 1 / C(2n, n)``. If that sits above
    ``alpha / tests``, then **no observation the experiment is capable of making would be
    certified**
    — and its "no effect" is a property of the design, not of the world.

    For this catalogue (174 runs, alpha 0.05) the answer is **8**: ``C(16,8) = 12870`` clears
    ``0.05/174``, and n=7 (``C(14,7) = 3432``) misses it by four millionths.

    Args:
        tests: How many hypotheses are in the family.
        alpha: The error rate.
        cap: Stop looking past this many samples per arm.

    Returns:
        The smallest viable ``n``, or ``None`` if even ``cap`` per arm would not do.
    """
    if tests <= 0:
        return None
    threshold = alpha / tests
    for n in range(1, cap + 1):
        if 1.0 / math.comb(2 * n, n) <= threshold:
            return n
    return None  # pragma: no cover  a 200-pass arm clears any threshold a human would set


def detection_power(strong_n: int, weak_n: int, *, threshold: float) -> Power | CannotSay:
    """The power of this design — **or the blind spot, when it has none**.

    This is the function that makes an unearned null result unwritable. It returns a
    :class:`~tessera.verdict.Power` only when the design could have rejected the null *at all*;
    otherwise it returns a :class:`~tessera.verdict.CannotSay` — and since
    :class:`~tessera.verdict.NoEffect` cannot be constructed without a ``Power``, a caller holding
    that ``CannotSay`` **has no way to write "no effect"**. The refusal is structural, not
    remembered.

    The minimum detectable effect is computed with no distributional assumption whatsoever: it is
    the smallest *observable separation* whose exact p clears ``threshold``, in the design's most
    favourable configuration (the strong model at ceiling). At n=15 per arm over 174 tests it is
    **67 percentage points** — the weak model must fail at least ten of its fifteen passes on a run
    the strong model never fails, or the run cannot be certified.

    Args:
        strong_n: Passes the strong arm ran.
        weak_n: Passes the weak arm ran.
        threshold: The corrected significance level (e.g. ``alpha / tests``).

    Returns:
        A ``Power`` the design has earned, or a ``CannotSay`` naming what it cannot see.
    """
    if strong_n <= 0 or weak_n <= 0:
        return CannotSay(
            f"an empty arm (strong n={strong_n}, weak n={weak_n}) observes nothing, so it cannot "
            f"report an absence. Run the passes."
        )
    best = fisher_greater(strong_n, strong_n, 0, weak_n)
    if best > threshold:
        return CannotSay(
            f"n={strong_n}/{weak_n} per arm CANNOT certify any separation at threshold "
            f"{threshold:.3g}: the most extreme result this design is capable of observing — the "
            f"strong model passing every pass and the weak model none of them — has p={best:.3g}. "
            f"It would report 'no effect' whatever the models did. Nothing here may be called dead "
            f"or non-discriminating on the strength of it."
        )
    # The condition is monotone in w, so the certifiable weak-pass counts are exactly {0..w_max}.
    w_max = max(
        w for w in range(weak_n + 1) if fisher_greater(strong_n, strong_n, w, weak_n) <= threshold
    )
    return Power(
        samples=min(strong_n, weak_n),
        threshold=threshold,
        best_achievable_p=best,
        minimum_detectable_effect=round((1.0 - w_max / weak_n) * 100.0, 1),
        effect_unit="percentage points of pass rate (with the strong model at ceiling)",
    )


def passes_to_decide(
    strong_pass: int,
    strong_n: int,
    weak_pass: int,
    weak_n: int,
    *,
    threshold: float,
    cap: int = 120,
) -> int | None:
    """How many passes **per arm** would certify this run, if the observed rates are the true ones.

    A **projection**, and labelled as one everywhere it is printed: it assumes the rates seen so far
    are the real ones, which is precisely what an underpowered experiment cannot establish. It is
    not evidence. It is the *price* of the evidence — which is the number a human actually needs in
    order to decide whether to buy it.

    Args:
        strong_pass: Passes of the strong model.
        strong_n: Passes the strong arm ran.
        weak_pass: Passes of the weak model.
        weak_n: Passes the weak arm ran.
        threshold: The corrected significance level.
        cap: Stop looking past this many passes per arm.

    Returns:
        The smallest balanced ``n``, or ``None`` if ``cap`` per arm still would not decide it (the
        rates are too close, or the wrong way round).
    """
    s_rate = strong_pass / strong_n if strong_n else 0.0
    w_rate = weak_pass / weak_n if weak_n else 0.0
    if s_rate <= w_rate:
        return None
    for n in range(2, cap + 1):
        if fisher_greater(round(s_rate * n), n, round(w_rate * n), n) <= threshold:
            return n
    return None


# ---------------------------------------------------------------------------------------
# The samples, the runs, the cases.
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Sample:
    """One model's repeated replays of the whole catalogue.

    Attributes:
        model: The model that answered — as witnessed by generated tokens, never by the report's
            ``model`` field (a dead backend still writes it).
        verdicts: One ``{case_id|language: passed}`` map per pass.
        catalogue_versions: The catalogue each pass was scored against. More than one distinct value
            means the sample spans a moved catalogue and cannot be pooled.
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
            ValueError: If any report carries no evidence a model ever spoke. A modelless pass
                scores the deterministic layer alone; pooling one into a model's sample would drag
                every count in this module toward the floor and read as a *measurement* of the
                model. The witness is tokens (:func:`eval.ratchet.model_spoke`), never the ``model``
                field.
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
        strong_passes / strong_n: The reference model's passes, of its total.
        weak_passes / weak_n: The weak model's passes, of its total.
        p_greater / p_less: One-tailed Fisher p in each direction.
        q_greater: The BH-adjusted p — the smallest FDR at which this run would be reported.
        holm_greater: Whether Holm certifies the separation. **This is what the ratchet reads.**
        bh_greater: Whether BH certifies it. This is what the *diagnosis* reads.
        klass: What was observed.
        unstable: Whether some model both passed and failed this run across its own passes.
            Orthogonal to ``klass``, because a run can be noisy *and* decisive.
        strong_breaks / weak_breaks: How many passes each model broke this run in.
        passes_needed: For an underpowered run, how many passes per arm would decide it **at the
            observed rates** — a projection, never evidence.
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
    q_greater: float
    holm_greater: bool
    bh_greater: bool
    klass: RunClass
    unstable: bool
    strong_breaks: int
    weak_breaks: int
    passes_needed: int | None

    @property
    def bucket(self) -> Bucket:
        """Which of the three buckets this run's class belongs to."""
        return BUCKET_OF[self.klass]

    @property
    def measures_the_model(self) -> bool:
        """Whether this run tells you anything about the model at all."""
        return self.klass in MEASURES_THE_MODEL

    @property
    def separation_pp(self) -> float:
        """Observed separation in percentage points. Signed: positive = the reference model wins."""
        if not self.strong_n or not self.weak_n:
            return 0.0
        return (self.strong_passes / self.strong_n - self.weak_passes / self.weak_n) * 100.0

    def verdict(self, power: Power | CannotSay) -> Verdict:  # noqa: PLR0911
        """What this run entitles you to say — and **nothing more**.

        The whole taxonomy, expressed in the one type that will not let a witness overstate:

        * :class:`~tessera.verdict.Ok` — it measures the model, and here is the evidence.
        * :class:`~tessera.verdict.NotOk` — **dead**. The null control closes it with zero tokens.
          A *fact*: no power enters, because the null control is deterministic and this is not a
          failure to detect an effect, it is the observation that silence suffices.
        * :class:`~tessera.verdict.NoEffect` — both models behaved identically in every pass **and
          the design had the power to have seen a difference**. The power rides along, because the
          claim is bounded by it: an effect *smaller* than the minimum detectable one is not
          excluded, and a reader who is not told that will assume it was.
        * :class:`~tessera.verdict.CannotSay` — a difference was seen and this ``n`` cannot certify
          it, **or** the design had no power at all. Not dead. Unknown.

        Args:
            power: The design's power, from :func:`detection_power`. When the design could certify
                nothing this is a ``CannotSay``, and it is returned **verbatim** for the classes
                that would otherwise have produced a ``NoEffect`` — a test with no power has no null
                result to report. There is no path from here to a fabricated "no difference":
                ``NoEffect`` cannot be built without a ``Power``, and there is none to pass.

        Returns:
            The verdict this run's evidence supports.

        Note:
            ``PLR0911`` (seven returns) is suppressed on the signature and it is not a smell: there
            are seven classes and there is one return per class, under an ``assert_never`` that
            makes mypy prove none is missing. Folding two of them together to please a counter
            would put two different facts behind one sentence, which is the entire failure this
            module exists to undo.
        """
        strong = f"{self.strong_passes}/{self.strong_n}"
        weak = f"{self.weak_passes}/{self.weak_n}"
        match self.klass:
            case "discriminating":
                return Ok(
                    f"{self.key}: the reference model passes it {strong}, the weak model {weak} — "
                    f"{self.separation_pp:+.0f} pp, Fisher p={self.p_greater:.2e}, BH "
                    f"q={self.q_greater:.2e}, Holm-certified over the whole catalogue as one family"
                )
            case "reversed":
                return Ok(
                    f"{self.key}: the WEAK model passes it {weak} and the reference model only "
                    f"{strong} — {self.separation_pp:+.0f} pp, Fisher p={self.p_less:.2e}, "
                    f"Holm-certified. It separates the models violently, in the wrong direction: a "
                    f"certified defect of the model that ships, and the catalogue's only evidence "
                    f"of it."
                )
            case "inverted":
                return Ok(
                    f"{self.key}: the null control PASSES this run and the reference model breaks "
                    f"it in {self.strong_breaks} of {self.strong_n} passes. The shipped agent is "
                    f"worse than silence here — a reproduced harm, in production."
                )
            case "dead":
                return NotOk(
                    f"{self.key}: the null control closes this run with zero tokens, and no "
                    f"model — "
                    f"in {self.strong_n + self.weak_n} passes — ever broke it. It cannot measure a "
                    f"model. (A fact, not an inference: the null control is deterministic.)"
                )
            case "saturated" | "unreached":
                if isinstance(power, CannotSay):
                    return power
                observed = (
                    f"both models pass it in every pass ({strong} and {weak})"
                    if self.klass == "saturated"
                    else f"NEITHER model has ever passed it ({strong} and {weak})"
                )
                return NoEffect(
                    claim=f"{self.key}: {observed} — they do not separate here",
                    power=power,
                )
            case "underpowered":
                remedy = (
                    f" At the observed rates, ~{self.passes_needed} passes per arm would decide it."
                    if self.passes_needed is not None
                    else " The observed rates do not favour the reference model, so more passes of "
                    "the same two models would not decide it."
                )
                return CannotSay(
                    f"{self.key}: the reference model passes it {strong}, the weak model "
                    f"{weak} — a {self.separation_pp:+.0f} pp difference this experiment CANNOT "
                    f"certify (Fisher "
                    f"p={self.p_greater:.2e}, BH q={self.q_greater:.2f}). NOT dead: a model moved "
                    f"it.{remedy}"
                )
        assert_never(self.klass)  # pragma: no cover — exhaustive; the line exists so mypy proves it


@dataclass(frozen=True, slots=True)
class CasePower:
    """What one case measures — the aggregate of its 1-3 language runs.

    A case is credited with the **strongest** evidence any of its language runs shows. A case that
    is dead in French and discriminating in German *does* measure the model: it measures it in
    German. Collapsing it to its weakest run would understate the catalogue, and averaging classes
    that mean different things would be arithmetic on adjectives.

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
    def bucket(self) -> Bucket:
        """Which of the three buckets this case's class belongs to."""
        return BUCKET_OF[self.klass]

    @property
    def measures_the_model(self) -> bool:
        """Whether this case tells you anything about the model, in any language."""
        return self.klass in MEASURES_THE_MODEL


#: Strongest evidence first. A case is filed under the best thing any of its runs does. ``inverted``
#: outranks the rest because a reproduced harm is the rarest and costliest thing to lose; the three
#: classes that measure the model are counted together in the headline, so this order only decides
#: which label a case *wears*, never whether it is credited.
#:
#: ``underpowered`` outranks ``saturated`` / ``unreached`` / ``dead`` **deliberately**: a case with
#: one run we could not rule on is a case we could not rule on. Letting a *dead* run in another
#: language decide its label would file an open question as a closed one — which is the exact
#: mistake this module was rewritten to stop.
_CLASS_RANK: dict[RunClass, int] = {
    "inverted": 0,
    "discriminating": 1,
    "reversed": 2,
    "underpowered": 3,
    "saturated": 4,
    "unreached": 5,
    "dead": 6,
}


@dataclass(frozen=True, slots=True)
class CataloguePower:
    """The discriminating power of a whole catalogue, measured against a model pair.

    Attributes:
        refusal: Set iff the classification could not be made at all — the runs and the floor do not
            name the same catalogue. Every count is then left at zero rather than computed over a
            population that does not exist. **Not** a verdict of zero (ADR 0026).
        catalogue_version: The case set every input names.
        strong_model / weak_model: The pair the separation was measured against.
        strong_n / weak_n: Passes per arm — the honesty of every p-value below.
        alpha: The error rate both corrections were run at.
        threshold: ``alpha / runs`` — the tightest step, and the level the design's power is quoted
            against.
        power: What this design could have detected, or a ``CannotSay`` when it could have detected
            nothing. Every "no effect" among the runs is licensed by this object — and when it is a
            ``CannotSay`` there are none, structurally.
        runs / cases: Per-run and per-case verdicts.
    """

    refusal: str | None
    catalogue_version: str
    strong_model: str
    weak_model: str
    strong_n: int
    weak_n: int
    alpha: float
    threshold: float = 0.0
    power: Power | CannotSay | None = None
    runs: tuple[RunPower, ...] = ()
    cases: tuple[CasePower, ...] = ()

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

    def bucket_counts(self) -> dict[Bucket, int]:
        """How many runs fall in each of the three buckets."""
        counts: dict[Bucket, int] = {"fact": 0, "certified": 0, "cannot_say": 0}
        for r in self.runs:
            counts[r.bucket] += 1
        return counts

    @property
    def discriminating_runs(self) -> int:
        """Runs that measure the model — **the number the ratchet freezes**. Holm-certified."""
        return sum(1 for r in self.runs if r.measures_the_model)

    @property
    def discriminating_cases(self) -> int:
        """Cases that measure the model, in at least one language. Holm-certified."""
        return sum(1 for c in self.cases if c.measures_the_model)

    @property
    def bh_runs(self) -> int:
        """Runs BH certifies as separating — **the diagnosis set**, never the ratchet's."""
        return sum(1 for r in self.runs if r.bh_greater)

    @property
    def holm_runs(self) -> int:
        """Runs Holm certifies as separating (the ``discriminating`` class alone)."""
        return sum(1 for r in self.runs if r.holm_greater)

    @property
    def correction_gap(self) -> tuple[RunPower, ...]:
        """Runs BH certifies and Holm does not — **what the ratchet's conservatism costs**.

        Reported, never hidden. An empty gap is a fact about *these* runs — the certified
        discriminators separate so violently that both corrections agree — and not a licence to stop
        computing it: at a smaller effect size the two sets come apart, and the day they do, the
        diagnosis must not silently inherit the ratchet's caution.
        """
        return tuple(r for r in self.runs if r.bh_greater and not r.holm_greater)

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
                    "  No class, no count and no power are reported: each would describe cases "
                    "no",
                    "  longer exist. Re-measure against the current catalogue "
                    "(`make eval-power-write`).",
                ]
            )
        rc, bc = self.run_counts(), self.bucket_counts()
        mde = (
            f"{self.power.minimum_detectable_effect:g} pp"
            if isinstance(self.power, Power)
            else "NONE (this design certifies nothing)"
        )
        lines = [
            f"[catalogue-power] {self.catalogue_version} — {self.strong_model} (n={self.strong_n}) "
            f"vs {self.weak_model} (n={self.weak_n}), alpha={self.alpha}, tightest step "
            f"{self.threshold:.2e}, minimum detectable effect {mde}",
            f"  FACT       {bc['fact']:3} runs — {rc['dead']} dead (silence closes them), "
            f"{rc['inverted']} inverted (worse than silence), {rc['saturated']} saturated, "
            f"{rc['unreached']} unreached",
            f"  CERTIFIED  {bc['certified']:3} runs — {rc['discriminating']} discriminating, "
            f"{rc['reversed']} reversed (the WEAK model wins)",
            f"  CANNOT SAY {bc['cannot_say']:3} runs — a difference below {mde} that this n cannot "
            f"certify. NOT dead.",
            f"  correction gap (BH certifies, Holm does not): {len(self.correction_gap)}",
            f"  MEASURE THE MODEL: {self.discriminating_cases}/{len(self.cases)} cases, "
            f"{self.discriminating_runs}/{len(self.runs)} runs  ({self.unstable_runs} unstable)",
        ]
        if isinstance(self.power, CannotSay):
            lines.append(f"  [CANNOT SAY] {self.power.blind_spot}")
        return "\n".join(lines)


def _version_refusal(baseline: Baseline, strong: Sample, weak: Sample) -> str | None:
    """Why these runs and this floor cannot be pooled — or ``None`` if they can.

    Mirrors :func:`eval.ratchet.floor_mismatch`, and is strict for the same reason: an *unknown*
    version is not a matching one. A pass that never said which catalogue it was scored against
    cannot be shown to be judged by this floor.
    """
    if not baseline.catalogue_version:
        return (
            "the null floor does not name the catalogue it was captured against — it cannot be "
            "shown to judge these runs. Regenerate it (`make eval-null-write`)."
        )
    versions = {v for s in (strong, weak) for v in s.catalogue_versions}
    if not versions or any(not v for v in versions):
        return (
            "a pass does not name the catalogue it was scored against — it cannot be shown to be "
            "judged by this floor. Re-run it with a current runner."
        )
    if len(versions) > 1:
        return (
            f"the passes span more than one catalogue ({', '.join(sorted(versions))}) — they "
            f"cannot "
            f"be pooled into one sample"
        )
    version = versions.pop()
    if version != baseline.catalogue_version:
        return (
            f"catalogue moved: the passes are {version!r}, the null floor is "
            f"{baseline.catalogue_version!r} — re-measure rather than classifying across case sets"
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

    A **pure function of the stored runs**: the same passes and the same floor always produce the
    same verdict, and nothing is read from the case files — a case that *declared* its own
    discriminating power would be making a claim, and this module exists to replace claims with
    measurements.

    The order of the branches is the taxonomy, and it is not arbitrary:

    1. **Facts first.** An inversion is a reproduced harm on a run silence passes; it is the finding
       whether or not the two models happen to differ on it, so it is settled before any test runs.
    2. **Then the certified inferences** — Holm, over the whole catalogue as one family. A subset
       chosen after seeing the numbers would be a corrected p-value in name only.
    3. **Then the remaining facts** — dead, unreached, saturated: observations, not conclusions.
    4. **Everything else is CANNOT SAY.** Not "no effect". Not "dead". It carries the minimum
       detectable effect at the ``n`` actually reached and, where the observed rates allow it, the
       number of passes that would settle it.

    Args:
        baseline: The committed null control — the floor, and the definition of the run set.
        strong: Repeated passes of the model the gate must ADMIT.
        weak: Repeated passes of the model the gate must REJECT.
        alpha: Error rate for both corrections.
        min_reproduced: Breaks needed before an inversion is real rather than a coin.

    Returns:
        A :class:`CataloguePower`. If the inputs do not name one catalogue it carries a ``refusal``
        and no counts — the classification was **not made**, which is not the same as a
        classification of zero.
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
    m = len(keys)
    threshold = alpha / m if m else alpha
    power = detection_power(strong.n, weak.n, threshold=threshold)

    # Every run is tested, in both directions, and the whole catalogue is ONE family.
    p_greater = [fisher_greater(strong.passes(k), strong.n, weak.passes(k), weak.n) for k in keys]
    p_less = [fisher_greater(weak.passes(k), weak.n, strong.passes(k), strong.n) for k in keys]
    holm_g = holm_reject(p_greater, alpha=alpha)
    holm_l = holm_reject(p_less, alpha=alpha)
    bh_g = bh_reject(p_greater, alpha=alpha)
    q_g = bh_qvalues(p_greater)

    runs: list[RunPower] = []
    for i, key in enumerate(keys):
        case_id, _, language = key.partition("|")
        floor = baseline.verdicts[key]
        s, w = strong.passes(key), weak.passes(key)
        strong_breaks, weak_breaks = strong.n - s, weak.n - w
        unstable = (0 < s < strong.n) or (0 < w < weak.n)

        klass: RunClass
        if floor and strong_breaks >= min_reproduced:
            klass = "inverted"
        elif holm_g[i]:
            klass = "discriminating"
        elif holm_l[i]:
            klass = "reversed"
        elif floor and max(strong_breaks, weak_breaks) == 0:
            klass = "dead"
        elif not floor and s == 0 and w == 0:
            klass = "unreached"
        elif not floor and s == strong.n and w == weak.n:
            klass = "saturated"
        else:
            klass = "underpowered"

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
                q_greater=q_g[i],
                holm_greater=holm_g[i],
                bh_greater=bh_g[i],
                klass=klass,
                unstable=unstable,
                strong_breaks=strong_breaks,
                weak_breaks=weak_breaks,
                passes_needed=(
                    passes_to_decide(s, strong.n, w, weak.n, threshold=threshold)
                    if klass == "underpowered"
                    else None
                ),
            )
        )

    return CataloguePower(
        refusal=None,
        catalogue_version=baseline.catalogue_version,
        strong_model=strong.model,
        weak_model=weak.model,
        strong_n=strong.n,
        weak_n=weak.n,
        alpha=alpha,
        threshold=threshold,
        power=power,
        runs=tuple(runs),
        cases=_aggregate_cases(runs),
    )


def _aggregate_cases(runs: Sequence[RunPower]) -> tuple[CasePower, ...]:
    """Fold per-language runs into per-case verdicts, keeping the strongest evidence."""
    by_case: dict[str, list[RunPower]] = {}
    for r in runs:
        by_case.setdefault(r.case_id, []).append(r)
    return tuple(
        CasePower(
            case_id=case_id,
            klass=min((r.klass for r in group), key=lambda k: _CLASS_RANK[k]),
            languages=tuple(sorted(r.language for r in group)),
            run_classes={r.language: r.klass for r in sorted(group, key=lambda r: r.language)},
            unstable=any(r.unstable for r in group),
        )
        for case_id, group in sorted(by_case.items())
    )


def measured_catalogue_version(power: CataloguePower) -> str:
    """Re-derive the catalogue identity from the cases actually classified.

    Never inherited: a classification that holds 63 cases *is* a 63-case classification, and one
    that holds 40 may not go on wearing the version string of the set it was cut from.
    """
    return catalogue_version(c.case_id for c in power.cases)


# ---------------------------------------------------------------------------------------
# The evidence, and the ratchet that stops it drifting.
# ---------------------------------------------------------------------------------------
#
# The raw passes are gitignored scratch (`.eval-noise/`, ~200 KB each, thirty of them): a
# calibration pass is not a published result. But a classification nobody can recompute is an
# assertion, and this module exists to abolish assertions. So the **evidence the classifier actually
# consumes** is committed instead — the verdict matrix, which is exactly what
# `eval.ratchet.report_verdicts` reduces a report to, plus the liveness witness (generated tokens)
# and the SHA-256 of the raw report each column came from.
#
# Nothing is lost in the reduction and nothing is smuggled in: CI re-derives the whole
# classification from the committed matrix, and anyone holding the raw passes can prove the matrix
# is theirs by re-hashing them.


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

    The liveness witness survives the reduction: a column whose pass generated zero tokens is
    refused here exactly as :meth:`Sample.from_reports` refuses the report it came from. A matrix is
    a smaller artefact than a run, never a laxer one.

    Args:
        model: The model whose passes these are.
        columns: One ``{case_id|language: passed}`` map per pass.
        provenance: The matching provenance record for each pass.

    Returns:
        The pooled sample.

    Raises:
        ValueError: If a pass carries no evidence a model spoke, or if the provenance does not line
            up with the columns.
    """
    if len(columns) != len(provenance):
        msg = (
            f"{model}: {len(columns)} verdict column(s) but {len(provenance)} provenance record(s) "
            f"— the matrix cannot be shown to come from the runs it names"
        )
        raise ValueError(msg)
    for i, prov in enumerate(provenance):
        if prov.output_tokens <= 0:
            msg = (
                f"{model}: pass {i + 1} ({prov.source}) records 0 output tokens — no model "
                f"answered. "
                f"A modelless pass cannot be evidence about a model."
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

    ``'1'`` is a pass, ``'0'`` a failure, in the order of ``keys``. A 174-character line per pass
    rather than a 174-entry object: thirty passes stay a few kilobytes, and — the reason that
    matters — **a verdict that drifts shows up as one character in a diff**. A reviewer can see
    which run flipped. A 200 KB blob per pass hides exactly that.

    Args:
        keys: The run keys, in the order the bitstrings encode.
        strong: The reference model's sample.
        weak: The weak model's sample.
        strong_prov: Provenance of each of the reference model's passes.
        weak_prov: Provenance of each of the weak model's passes.
        note: A sentence for the human reading the artefact.

    Returns:
        The serialised evidence.
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

    Args:
        path: The committed evidence.

    Returns:
        The run keys and both samples.

    Raises:
        ValueError: If the artefact is malformed, or if any pass records zero generated tokens — the
            liveness witness is enforced on the way in, not just on the way out.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("kind") != "discrimination_samples":
        msg = f"{path} is not a discrimination-samples artefact"
        raise ValueError(msg)
    keys = [str(k) for k in payload.get("keys") or ()]
    if not keys:
        msg = f"{path} names no runs"
        raise ValueError(msg)

    def _side(name: str) -> Sample:
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
                    f"{path}: a {name} pass has {len(bits)} verdicts for {len(keys)} runs — the "
                    f"matrix does not describe this catalogue"
                )
                raise ValueError(msg)
            columns.append({k: bits[i] == "1" for i, k in enumerate(keys)})
        return sample_from_matrix(model, columns, prov)

    return keys, _side("strong"), _side("weak")


def dump_power(power: CataloguePower, *, method: str = "") -> str:
    """Serialise a classification — every count derived, every run named, the power stated.

    Args:
        power: The classification.
        method: How it was produced, for the human reading the artefact.

    Returns:
        The serialised classification.
    """
    payload: dict[str, Any] = {
        "kind": "catalogue_power",
        "catalogue_version": power.catalogue_version,
        "strong_model": power.strong_model,
        "strong_n": power.strong_n,
        "weak_model": power.weak_model,
        "weak_n": power.weak_n,
        "alpha": power.alpha,
        "threshold": power.threshold,
        "method": method,
        "detection_power": (
            {
                "samples": power.power.samples,
                "threshold": power.power.threshold,
                "best_achievable_p": power.power.best_achievable_p,
                "minimum_detectable_effect": power.power.minimum_detectable_effect,
                "effect_unit": power.power.effect_unit,
            }
            if isinstance(power.power, Power)
            # `if power.power` would RAISE here — CannotSay.__bool__ refuses to be a bit, and it
            # caught this line the moment it was written. Ask the type, never the truthiness.
            else {
                "blind_spot": (
                    power.power.blind_spot if isinstance(power.power, CannotSay) else "not computed"
                )
            }
        ),
        "power": {
            "discriminating_cases": power.discriminating_cases,
            "discriminating_runs": power.discriminating_runs,
            "total_cases": len(power.cases),
            "total_runs": len(power.runs),
            "unstable_cases": power.unstable_cases,
            "unstable_runs": power.unstable_runs,
            "holm_runs": power.holm_runs,
            "bh_runs": power.bh_runs,
            "correction_gap": [r.key for r in power.correction_gap],
        },
        "bucket_counts": power.bucket_counts(),
        "case_counts": power.case_counts(),
        "run_counts": power.run_counts(),
        "cases": {
            c.case_id: {
                "class": c.klass,
                "bucket": c.bucket,
                "unstable": c.unstable,
                "languages": dict(sorted(c.run_classes.items())),
            }
            for c in power.cases
        },
        "runs": {
            r.key: {
                "class": r.klass,
                "bucket": r.bucket,
                "floor_passes": r.floor_passes,
                "strong": f"{r.strong_passes}/{r.strong_n}",
                "weak": f"{r.weak_passes}/{r.weak_n}",
                "separation_pp": round(r.separation_pp, 1),
                "unstable": r.unstable,
                "p_greater": round(r.p_greater, 8),
                "q_greater": round(r.q_greater, 6),
                "holm": r.holm_greater,
                "bh": r.bh_greater,
                "passes_needed": r.passes_needed,
            }
            for r in power.runs
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def load_power(path: Path) -> CataloguePower:
    """Read a committed classification back, for the ratchet to compare against.

    Args:
        path: The committed classification.

    Returns:
        The classification, with the fields the ratchet reads.

    Raises:
        ValueError: If the artefact is not a classification.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("kind") != "catalogue_power":
        msg = f"{path} is not a catalogue-power artefact"
        raise ValueError(msg)
    strong_n = int(payload.get("strong_n") or 0)
    weak_n = int(payload.get("weak_n") or 0)
    runs = tuple(
        RunPower(
            key=str(key),
            case_id=str(key).partition("|")[0],
            language=str(key).partition("|")[2],
            floor_passes=bool(r.get("floor_passes")),
            strong_passes=int(str(r.get("strong", "0/0")).split("/")[0]),
            strong_n=strong_n,
            weak_passes=int(str(r.get("weak", "0/0")).split("/")[0]),
            weak_n=weak_n,
            p_greater=float(r.get("p_greater") or 1.0),
            p_less=1.0,
            q_greater=float(r.get("q_greater") or 1.0),
            holm_greater=bool(r.get("holm")),
            bh_greater=bool(r.get("bh")),
            klass=str(r.get("class") or "dead"),  # type: ignore[arg-type]
            unstable=bool(r.get("unstable")),
            strong_breaks=0,
            weak_breaks=0,
            passes_needed=(int(r["passes_needed"]) if r.get("passes_needed") is not None else None),
        )
        for key, r in (payload.get("runs") or {}).items()
    )
    return CataloguePower(
        refusal=None,
        catalogue_version=str(payload.get("catalogue_version") or ""),
        strong_model=str(payload.get("strong_model") or ""),
        weak_model=str(payload.get("weak_model") or ""),
        strong_n=strong_n,
        weak_n=weak_n,
        alpha=float(payload.get("alpha") or ALPHA),
        threshold=float(payload.get("threshold") or 0.0),
        runs=runs,
        cases=_aggregate_cases(runs),
    )


def check_power(
    power: CataloguePower,
    frozen: CataloguePower | None,
    *,
    floor_cases: int,
    floor_runs: int,
) -> Verdict:
    """The ratchet: the catalogue's discriminating power is a number, and it may not fall.

    It returns a :class:`~tessera.verdict.Verdict`, not a bool. The bool was the bug — a ratchet
    that returns ``True`` cannot be asked *what it looked at*, and for three incidents running
    nobody asked (ADR 0026).

    Two different failures, deliberately not collapsed:

    * **The power dropped.** Fewer cases measure the model than the frozen floor. Deleting a
      discriminating case, or blunting one until the models stop separating on it, turns this red.
      Adding a *dead* case cannot turn it red — nothing was lost — but it cannot hide either: the
      catalogue version moves, the classification is refused until it is re-measured, and the
      re-measured density lands in the diff for a human to see.
    * **The classification drifted.** The frozen per-run verdicts no longer match what the stored
      evidence produces. The *classifier* changed, or the evidence did, and either way the frozen
      number describes something that is no longer there.

    Args:
        power: The classification re-derived from the committed evidence.
        frozen: The committed classification, or ``None`` to check the floor alone.
        floor_cases: The frozen high-water mark, in cases.
        floor_runs: The frozen high-water mark, in runs.

    Returns:
        ``CannotSay`` if the catalogue moved (**not** a failure: the power was not judged, which is
        the honest output of an expired witness), ``NotOk`` if it fell or drifted, ``Ok`` — carrying
        what was actually examined — otherwise.
    """
    if power.refusal is not None:
        return CannotSay(power.refusal)

    reasons: list[str] = []
    if frozen is not None:
        was = {r.key: r.klass for r in frozen.runs}
        now = {r.key: r.klass for r in power.runs}
        reasons += [
            f"classification drifted: {k}: {was.get(k, '(absent)')} -> {now.get(k, '(absent)')}"
            for k in sorted(set(was) | set(now))
            if was.get(k) != now.get(k)
        ]

    if power.discriminating_cases < floor_cases:
        reasons.append(
            f"the catalogue LOST discriminating power: {power.discriminating_cases} cases measure "
            f"the model, the frozen floor is {floor_cases}. A case that separates a good model "
            f"from a bad one is the scarcest thing in this repository — it does not get removed "
            f"silently."
        )
    if power.discriminating_runs < floor_runs:
        reasons.append(
            f"the catalogue LOST discriminating power: {power.discriminating_runs} runs measure "
            f"model, the frozen floor is {floor_runs}."
        )

    if reasons:
        return NotOk("; ".join(reasons))

    mde = (
        f", minimum detectable effect {power.power.minimum_detectable_effect:g} "
        f"{power.power.effect_unit}"
        if isinstance(power.power, Power)
        else ""
    )
    return Ok(
        f"{len(power.runs)} runs of catalogue {power.catalogue_version} re-derived from the "
        f"committed matrix ({power.strong_model} n={power.strong_n} vs {power.weak_model} "
        f"n={power.weak_n}); every class matches the frozen classification; "
        f"{power.discriminating_cases} cases / {power.discriminating_runs} runs measure the model, "
        f"floor {floor_cases}/{floor_runs}{mde}"
    )
