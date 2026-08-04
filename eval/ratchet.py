"""The eval ratchet — what stops a harness result from drifting or lying.

The catalogue is replayed against a *real* agent, so its score mixes two very
different layers: the deterministic guard/router short-circuits (which need no
model at all) and the model's own behaviour. Measured on 2026-07-12, a run with
**no reachable LLM** still scores 122/174 — 70% of the catalogue is closed
before a token is ever generated. Two consequences drive this module:

* **A pass rate is not a model score.** The floor is the null run, not zero, so a
  bar set below that floor cannot fail anything. The ratchet's job is to compare
  a run against the *right* reference, not against 0%.
* **A run can silently lose its model.** With Ollama unreachable, the runner does
  not crash: every case completes, the report still records ``model:
  "llama3.2:3b"`` (the *configured* model, not evidence of a call), and the
  scorecard reads a clean 70%. The ``model`` field is therefore worthless as
  proof. The only honest witness that a model spoke is **token usage**.

Hence the two checks below:

* :func:`check_null_control` — the modelless control, pinned by **exact match**.
  It runs in ~5s with no services, so CI can afford it on every push. It is a
  true regression gate on the whole deterministic layer: any change in the guard,
  the router or the criteria moves a case and fails the check. Improvements fail
  it too, on purpose — a deliberate improvement is a baseline update, and the
  diff is the evidence.
* :func:`check_model_run` — a monotone ratchet on a model replay: no case that
  passed in the baseline may fail, the pass count may not drop, and the run must
  carry a liveness witness so a null run can never be reported as a model verdict.

The functions are pure — they take parsed report/baseline dicts — so they are
unit-testable without a model, and mutation-testable (a ratchet that cannot fail
polices nothing).
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

__all__ = [
    "Baseline",
    "RatchetVerdict",
    "baseline_from_report",
    "grader_criteria_sha",
    "grader_criteria_sha_for",
    "CATALOGUE_DIR",
    "catalogue_on_disk",
    "catalogue_version",
    "check_model_run",
    "check_null_control",
    "dump_baseline",
    "floor_mismatch",
    "load_baseline",
    "model_spoke",
    "report_verdicts",
]

BaselineKind = Literal["null_control", "model_run"]

#: Separator for the ``case_id|language`` keys of a baseline's verdict map.
_KEY_SEP = "|"


def catalogue_version(case_ids: Iterable[str]) -> str:
    """The ``count-hash`` identity of a set of cases.

    **The one definition.** The runner stamps every report with it, and the ratchet and
    the contribution gate compare against it — so if two of them computed it their own
    way, a floor and a run could name the same catalogue by different strings, or worse,
    different catalogues by the same one. It lives here, and the runner imports it.

    Derived from the case ids alone: a catalogue that gains, loses or renames a case gets
    a new identity, and nothing that was measured against the old one can be compared to
    it without saying so.

    Args:
        case_ids: The ids of the cases in the set (order and duplicates are irrelevant).

    Returns:
        ``"<count>-<8 hex>"`` — e.g. ``"63-071edbdc"`` for the full catalogue.
    """
    ids = sorted(set(case_ids))
    digest = hashlib.sha256("\n".join(ids).encode()).hexdigest()[:8]
    return f"{len(ids)}-{digest}"


#: Where the catalogue actually lives. Every artefact in this repository *claims* a
#: ``catalogue_version``; exactly one function is allowed to go and **look**.
CATALOGUE_DIR: Final = Path(__file__).resolve().parent / "failures"


def grader_criteria_sha(category: str, failures: Path = CATALOGUE_DIR) -> str:
    """The content identity of one category's grading criteria. **The one definition.**

    ``catalogue_version`` tracks *which* cases exist — their ids — and nothing else. It is
    deliberately blind to *what a case asserts*: edit a ``pass_criteria`` and the id, hence
    the catalogue version, is unchanged. That blindness is a hole. On 2026-07-14 (ADR 0028
    §5) four injection cases had a refusal token purged from ``must_contain_any`` — a token
    the attack text itself contained, so a model echoing it *while obeying* scored a pass.
    The grader's meaning changed under every frozen measurement, and not one pin moved: the
    catalogue version was the same string, the stored verdict matrix the same bits, the
    classification reproducible from that matrix. A self-consistent fossil.

    This hashes the ``pass_criteria`` of every case in ``category``, so a measurement can pin
    the grader it was taken under and a witness can refuse — loudly — a baseline graded by a
    grader that no longer exists. It ends in the case files, never in another artefact.

    Args:
        category: The failure category to hash (e.g. ``"prompt_injection"``).
        failures: The catalogue directory. Defaults to the real one.

    Returns:
        ``"<count>-<12 hex>"`` over the sorted ``id -> pass_criteria`` pairs of the category.
    """
    return _criteria_sha(
        _criteria_pairs(failures, keep=lambda case: case.get("category") == category)
    )


def grader_criteria_sha_for(case_ids: Iterable[str], failures: Path = CATALOGUE_DIR) -> str:
    """The same identity, over an arbitrary set of cases rather than a whole category.

    A release is graded per **eval set**, not per category, and the comparison that matters is
    between one agent's runs and the null floor restricted to exactly those runs. Scoping the
    identity to the ids being compared keeps a criteria edit elsewhere in the catalogue from
    invalidating a comparison it has no bearing on — while still making an edit *inside* the set
    the loud refusal it must be.

    Args:
        case_ids: The ids compared (order and duplicates are irrelevant). Ids absent from the
            catalogue are ignored; the count in the returned string says how many were found.
        failures: The catalogue directory. Defaults to the real one.

    Returns:
        ``"<count>-<12 hex>"`` over the sorted ``id -> pass_criteria`` pairs of those cases.
    """
    wanted = set(case_ids)
    return _criteria_sha(_criteria_pairs(failures, keep=lambda case: str(case.get("id")) in wanted))


def _criteria_pairs(failures: Path, *, keep: Callable[[dict[str, Any]], bool]) -> list[str]:
    r"""``id \x1f canonical(pass_criteria)`` for every kept case. The one reader of the terminus."""
    pairs: list[str] = []
    for path in sorted(failures.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        case = json.loads(path.read_text(encoding="utf-8"))
        if not keep(case):
            continue
        criteria = json.dumps(case.get("pass_criteria", {}), sort_keys=True, ensure_ascii=False)
        pairs.append(f"{case['id']}\x1f{criteria}")
    return pairs


#: Names in :mod:`eval.runner` that DECIDE whether a criterion is met. Their source is folded
#: into the criteria identity below.
_GRADER_DECIDERS: Final[tuple[str, ...]] = (
    "_claim_is_asserted",
    "_is_refused_restatement",
    "_check_substrings",
    "_check_required_alternatives",
    "_NEGATION_MARKERS",
    "_ATTRIBUTION_FRAMES",
    "_REFUSAL_MARKERS",
    "_TRAILING_NEGATION_WINDOW",
    "_SENTENCE_BREAKS",
)


def _grader_code_sha() -> str:
    """Identity of the CODE that applies the criteria, not of the criteria text.

    ``catalogue_version`` hashes case **ids** and is blind to what any case asserts; that
    blindness cost three agents their release on 2026-08-04, and the fix was to hash the
    ``pass_criteria`` too. This is the SAME blindness one level deeper, and it bit on
    2026-08-04 as well: ``must_not_assert``'s meaning lives in ``_claim_is_asserted``, so
    widening what counts as a denial changes every verdict that criterion ever produced — and
    moved neither hash. A frozen null floor and a fresh agent report could then be graded by
    two different rulers wearing the same number, which is exactly the comparison ADR 0028 §5
    says must refuse rather than conclude.

    Only the DECIDING names are hashed, not the whole module: a docstring fix or a new report
    field must not invalidate every recorded measurement, or the refusal becomes noise and the
    next person learns to re-stamp past it.

    A name that disappears is recorded as ``<gone>`` rather than skipped — deleting a decider
    is a grader change too, and a silent skip would hide the largest one there is.
    """
    from eval import runner

    parts: list[str] = []
    for name in _GRADER_DECIDERS:
        obj = getattr(runner, name, None)
        if obj is None:
            parts.append(f"{name}\x1f<gone>")
            continue
        try:
            parts.append(f"{name}\x1f{inspect.getsource(obj)}")
        except (OSError, TypeError):
            # A constant, not a function: its VALUE is the rule.
            parts.append(f"{name}\x1f{obj!r}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:12]


def _criteria_sha(pairs: list[str]) -> str:
    material = "\n".join(sorted(pairs)) + "\n\x1e" + _grader_code_sha()
    digest = hashlib.sha256(material.encode()).hexdigest()[:12]
    return f"{len(pairs)}-{digest}"


#: Where a frozen measurement records the grader it was taken under.
PROVENANCE_PATH: Final = Path(__file__).resolve().parent / "baselines" / "grader_provenance.json"


def grader_remeasure_owed(
    category: str = "prompt_injection",
    provenance: Path = PROVENANCE_PATH,
) -> str | None:
    """Return the declared reason a frozen measurement is stale, or ``None`` when it is not.

    :func:`grader_criteria_sha` detects that the criteria moved; this reports what the
    provenance file *declares* about it. The distinction is the whole point: a comparison
    between a null floor graded by today's criteria and model passes graded by last month's
    is not a weaker measurement, it is a different question — and answering it anyway
    produces a number that looks like power and is not (ADR 0026, ADR 0027's ``CannotSay``).

    Args:
        category: The failure category whose provenance to read.
        provenance: The provenance file. Defaults to the committed one.

    Returns:
        The declared reason when ``remeasure_owed`` is set, otherwise ``None``.
    """
    if not provenance.exists():
        return None
    record = json.loads(provenance.read_text(encoding="utf-8")).get(category) or {}
    if not record.get("remeasure_owed"):
        return None
    return str(record.get("reason") or f"{category}: a re-measure is owed")


def catalogue_on_disk(failures: Path = CATALOGUE_DIR) -> str | None:
    """Ask the CASE FILES which catalogue this is. **The end of every derived chain.**

    This function exists because a ratchet in this repository was **green with two of its three
    certified discriminators deleted from disk** (2026-07-13). Deleting
    ``eval/failures/26_citation_fabrication_cjue.json`` removed the ``+100 pp`` and ``+87 pp``
    runs — two of the three the catalogue has — and ``make eval-power`` reported ``[OK]``, exit 0.

    Everything it read agreed with everything else it read. The committed verdict matrix held 63
    cases' worth of columns; the committed null floor named 63 cases; the frozen classification
    named 63 cases; all three carried ``catalogue_version = "63-071edbdc"``; all three were
    mutually consistent — **and all three were fossils.** Not one of them had ever opened
    ``eval/failures/``.

    **A self-consistent chain of artefacts proves nothing about the world.** A system in which
    every artefact derives its identity from another artefact is perfectly coherent *and*
    perfectly fossilisable. Somewhere the chain has to **end**, in exactly one witness that opens
    the source — and this is it. ``tests/unit/test_catalogue_chain_terminates.py`` enumerates
    every artefact that carries a ``catalogue_version`` and fails if any chain of them can reach a
    verdict without passing through here.

    Args:
        failures: The catalogue directory. Defaults to the real one.

    Returns:
        The ``count-hash`` identity of the case files — or **``None``**, which is a *blind spot*
        and never an empty catalogue. ``catalogue_version([])`` is a perfectly good string
        (``"0-e3b0c442"``): a caller that computed it would have compared two hashes and refused
        for the wrong reason — or, worse, matched an equally empty floor and **passed**.
    """
    if not failures.is_dir():
        return None
    ids = [p.stem for p in sorted(failures.glob("*.json")) if not p.stem.startswith("_")]
    return catalogue_version(ids) if ids else None


@dataclass(frozen=True, slots=True)
class Baseline:
    """A committed reference a later run is judged against.

    Attributes:
        kind: ``null_control`` (no model may speak) or ``model_run``.
        model: The model the baseline was captured with. For a null control this
            is the *configured* model that was never called — informational only,
            never used as proof that a model ran.
        catalogue_version: The ``count-hash`` of the case set the baseline was
            captured against. A mismatch means the catalogue moved and the
            baseline must be regenerated rather than silently reinterpreted.
        verdicts: ``{"<case_id>|<language>": passed}`` for every run.
        note: Free-form provenance (how it was captured).
        grader_criteria_sha: The identity of the CRITERIA the baseline was measured under.
            ``catalogue_version`` above cannot see a criteria edit — it hashes ids — so without
            this a baseline re-measured under new criteria and a run graded under the old ones
            compare as the same measurement. Empty means the baseline predates the stamp, which
            is *unknown*, not "current".
    """

    kind: BaselineKind
    model: str
    catalogue_version: str
    verdicts: dict[str, bool]
    note: str = ""
    grader_criteria_sha: str = ""

    @property
    def verdicts_case_ids(self) -> set[str]:
        """The distinct case ids the verdict map covers (its keys are ``case_id|language``)."""
        return {key.split(_KEY_SEP, 1)[0] for key in self.verdicts}

    @property
    def total(self) -> int:
        """Number of (case, language) runs in the baseline."""
        return len(self.verdicts)

    @property
    def passed(self) -> int:
        """Number of runs that passed in the baseline."""
        return sum(1 for ok in self.verdicts.values() if ok)


@dataclass(frozen=True, slots=True)
class RatchetVerdict:
    """The outcome of a ratchet check.

    ``regressions`` and ``improvements`` are both movements away from the
    baseline; which of them is fatal depends on the check (exact for the null
    control, monotone for a model run).
    """

    ok: bool
    kind: BaselineKind
    regressions: tuple[str, ...] = ()
    improvements: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()
    baseline_passed: int = 0
    run_passed: int = 0
    total: int = 0
    reasons: list[str] = field(default_factory=list)

    def render(self) -> str:
        """One-line human summary for the CI log."""
        verdict = "PASS" if self.ok else "BLOCK"
        head = (
            f"[ratchet {verdict}] {self.kind}: "
            f"{self.run_passed}/{self.total} vs baseline {self.baseline_passed}/{self.total}"
        )
        if self.ok:
            return head
        return head + "\n" + "\n".join(f"  - {r}" for r in self.reasons)


def _key(case_id: str, language: str) -> str:
    return f"{case_id}{_KEY_SEP}{language}"


def report_verdicts(report: dict[str, Any]) -> dict[str, bool]:
    """Extract ``{"<case_id>|<language>": passed}`` from a runner report."""
    results = report.get("results") or []
    return {
        _key(str(r["case_id"]), str(r["language"])): bool(r["passed"])
        for r in results
        if isinstance(r, dict)
    }


def model_spoke(report: dict[str, Any]) -> bool:
    """Whether a model actually generated anything during the run.

    The report's ``model`` field is the *configured* model and is written even
    when no backend was reachable, so it proves nothing. Generated tokens do: a
    run that produced zero output tokens never got an answer out of a model,
    whatever it claims to have been configured with.
    """
    cost = report.get("cost") or {}
    return int(cost.get("output_tokens", 0) or 0) > 0


def baseline_from_report(report: dict[str, Any], *, kind: BaselineKind, note: str = "") -> Baseline:
    """Capture a report as a baseline (used by ``--write`` to refresh a reference).

    ``grader_criteria_sha`` travels. It did not until 2026-08-04, and the loss was silent and
    exactly backwards: ``load_baseline`` READ the field, so a baseline refreshed by ``--write``
    came back with an empty ruler — a floor that cannot name the criteria that judged it, which
    is the unfalsifiable state the stamp was introduced to end. Refreshing the reference is the
    one moment the ruler is certainly known, and it was the one moment it was dropped.
    """
    return Baseline(
        kind=kind,
        model=str(report.get("model") or ""),
        catalogue_version=str(report.get("catalogue_version") or ""),
        verdicts=report_verdicts(report),
        note=note,
        grader_criteria_sha=str(report.get("grader_criteria_sha") or ""),
    )


def load_baseline(path: Path) -> Baseline:
    """Read a baseline from disk.

    Raises:
        ValueError: If the file is not a well-formed baseline.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"baseline {path} is not a JSON object"
        raise ValueError(msg)
    kind = payload.get("kind")
    if kind not in ("null_control", "model_run"):
        msg = f"baseline {path} has an unknown kind {kind!r}"
        raise ValueError(msg)
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, dict) or not verdicts:
        msg = f"baseline {path} has no verdicts"
        raise ValueError(msg)
    return Baseline(
        kind=kind,
        model=str(payload.get("model") or ""),
        catalogue_version=str(payload.get("catalogue_version") or ""),
        verdicts={str(k): bool(v) for k, v in verdicts.items()},
        note=str(payload.get("note") or ""),
        grader_criteria_sha=str(payload.get("grader_criteria_sha") or ""),
    )


def dump_baseline(baseline: Baseline) -> str:
    """Serialise a baseline to the on-disk JSON form (stable key order).

    ``grader_criteria_sha`` is written whenever it is known. Its absence here was the second
    half of the same silent loss described in :func:`baseline_from_report`: even once the
    Baseline object carried the ruler, the serialiser did not emit it, so a ``--write`` still
    produced a floor that could not say what judged it. Omitted when empty rather than written
    as ``""`` — a baseline predating the stamp genuinely does not know its ruler, and an empty
    string is a claim to know it is nothing.
    """
    payload: dict[str, Any] = {
        "kind": baseline.kind,
        "model": baseline.model,
        "catalogue_version": baseline.catalogue_version,
    }
    if baseline.grader_criteria_sha:
        payload["grader_criteria_sha"] = baseline.grader_criteria_sha
    payload |= {
        "note": baseline.note,
        "totals": {"total": baseline.total, "passed": baseline.passed},
        "verdicts": dict(sorted(baseline.verdicts.items())),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _compare(
    baseline: Baseline, run: dict[str, bool]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return (regressions, improvements, missing, unexpected)."""
    regressions = tuple(
        sorted(k for k, was_ok in baseline.verdicts.items() if was_ok and run.get(k) is False)
    )
    improvements = tuple(
        sorted(k for k, was_ok in baseline.verdicts.items() if not was_ok and run.get(k) is True)
    )
    missing = tuple(sorted(k for k in baseline.verdicts if k not in run))
    unexpected = tuple(sorted(k for k in run if k not in baseline.verdicts))
    return regressions, improvements, missing, unexpected


def floor_mismatch(baseline: Baseline, report: dict[str, Any]) -> str | None:
    """Why this baseline cannot judge this run — or ``None`` if it can.

    A baseline is a **witness**, and a witness expires. It records the verdicts of one
    catalogue; the moment the case set moves, every number derived from it — a regression,
    a contribution, a lift — is computed against a population that no longer exists. The
    check is therefore a precondition of grading at all, not one finding among others.

    **Strict on purpose: an unknown version is not a matching one.** The first version of
    this check read ``if baseline.catalogue_version and version and version != ...``, so an
    *empty* version on either side skipped the comparison and the ratchet read green — it
    compared a baseline of unknown provenance against a run from an unknown catalogue and
    called them equal. Absence of a version is absence of proof, and this gate answers the
    question it was asked ("can this floor judge this run?") rather than the neighbouring
    one it can answer more easily ("do two strings differ?").

    Args:
        baseline: The committed reference.
        report: A parsed runner report.

    Returns:
        A one-line reason the comparison is void, or ``None`` when both sides name the
        same catalogue.
    """
    version = str(report.get("catalogue_version") or "")
    if not baseline.catalogue_version:
        return (
            "the baseline does not name the catalogue it was captured against — it cannot "
            "be shown to judge this run. Regenerate it (`make eval-null-write`)."
        )
    if not version:
        return (
            "the run does not name the catalogue it was scored against — it cannot be shown "
            "to be judged by this baseline. Re-run it with a current runner."
        )
    if version != baseline.catalogue_version:
        return (
            f"catalogue moved: run is {version!r}, baseline is "
            f"{baseline.catalogue_version!r} — regenerate the baseline rather than "
            f"comparing across case sets"
        )
    return None


def _catalogue_reasons(baseline: Baseline, report: dict[str, Any]) -> list[str]:
    reason = floor_mismatch(baseline, report)
    return [reason] if reason else []


def check_null_control(report: dict[str, Any], baseline: Baseline) -> RatchetVerdict:
    """Check a modelless control run against its baseline, by **exact match**.

    The control is the deterministic layer's regression gate: it needs no model,
    no Postgres and no secrets, so CI can run it on every push. Any movement in
    either direction fails — an improvement is a real change to the guard or the
    criteria and must land as a deliberate baseline update, with the diff as its
    evidence.

    A run in which a model *did* speak is rejected outright: it is not a control,
    and scoring it against the control's baseline would be meaningless.

    Args:
        report: A parsed runner report (``eval/reports/<env>/*.json``).
        baseline: The committed null-control baseline.

    Returns:
        A :class:`RatchetVerdict`; ``ok`` iff the run reproduces the baseline exactly.
    """
    run = report_verdicts(report)
    reasons = _catalogue_reasons(baseline, report)
    if model_spoke(report):
        reasons.append(
            "a model generated tokens during the null control — this is not a "
            "modelless run; point the runner at an unreachable backend "
            "(TESSERA_OLLAMA_HOST=http://127.0.0.1:59999)"
        )
    regressions, improvements, missing, unexpected = _compare(baseline, run)
    reasons += [f"regressed (passed in baseline, fails now): {k}" for k in regressions]
    reasons += [f"improved (failed in baseline, passes now): {k}" for k in improvements]
    reasons += [f"missing from the run: {k}" for k in missing]
    reasons += [f"not in the baseline: {k}" for k in unexpected]
    if improvements and not (regressions or missing or unexpected):
        reasons.append(
            "the deterministic layer got better — refresh the baseline "
            "(`make eval-null-write`) and commit the diff"
        )
    run_passed = sum(1 for ok in run.values() if ok)
    return RatchetVerdict(
        ok=not reasons,
        kind="null_control",
        regressions=regressions,
        improvements=improvements,
        missing=missing,
        unexpected=unexpected,
        baseline_passed=baseline.passed,
        run_passed=run_passed,
        total=baseline.total,
        reasons=reasons,
    )


def check_model_run(report: dict[str, Any], baseline: Baseline) -> RatchetVerdict:
    """Check a model replay against its baseline — monotone, plus a liveness witness.

    Fails when a case that passed in the baseline now fails, when the overall pass
    count drops, or when the run carries no evidence that a model ever answered.
    That last check is the one that matters most in practice: a dead backend does
    not crash the runner, so without it a modelless 70% would be filed as a model
    result.

    Improvements are welcome and do not fail the check, but they do not update the
    baseline either — refresh it deliberately so the gain is recorded.

    Args:
        report: A parsed runner report.
        baseline: The committed baseline for this model.

    Returns:
        A :class:`RatchetVerdict`; ``ok`` iff nothing regressed and a model spoke.
    """
    run = report_verdicts(report)
    reasons = _catalogue_reasons(baseline, report)
    if not model_spoke(report):
        reasons.append(
            f"no model spoke: the run generated 0 output tokens yet reports "
            f"model={report.get('model')!r}. A modelless run scores the "
            f"deterministic layer alone and must never be filed as a model verdict."
        )
    regressions, improvements, missing, unexpected = _compare(baseline, run)
    reasons += [f"regressed (passed in baseline, fails now): {k}" for k in regressions]
    reasons += [f"missing from the run: {k}" for k in missing]
    run_passed = sum(1 for ok in run.values() if ok)
    if run_passed < baseline.passed:
        reasons.append(
            f"pass count dropped: {run_passed} < {baseline.passed} (baseline)",
        )
    return RatchetVerdict(
        ok=not reasons,
        kind="model_run",
        regressions=regressions,
        improvements=improvements,
        missing=missing,
        unexpected=unexpected,
        baseline_passed=baseline.passed,
        run_passed=run_passed,
        total=baseline.total,
        reasons=reasons,
    )
