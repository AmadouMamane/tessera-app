"""Layer-3 reformulation bench (ADR 0054): the checker column, and optionally the LLM one.

Measures two things against the labeled referent (``eval/reformulation/recouvrement.json``):

* the **checker column** — deterministic, free, runs anywhere: does
  :func:`tessera.recouvrement.reformulation.check_must_survive` agree with every human
  label (faithful rewrites pass, every seeded violation is caught), and does the
  closed-vocabulary gate refuse exactly the adversarial tone instructions? This column is
  the referent's own integrity measure and is pinned by
  ``tests/unit/test_reformulation_referent_ratchet.py``.
* the **LLM column** (``--llm`` — spends real calls): for every generate-gated case, draft
  a reformulation with the live backend, then hold it to the SAME deterministic checker
  (and, with ``--judge``, score its fidelity with the judge). This is the measurement
  slice 4's threshold calibration will cite (ADR 0054 §5).

Templates are rendered through the REAL production helpers (``recouvrement_template`` +
clause renderers), never re-implemented here — the bench interrogates the thing
(ADR 0026). ``--report`` publication is deliberate, never a side effect.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import jsonschema

from tessera.recouvrement.message_templates import (
    RecouvrementLanguage,
    TemplateKind,
    recouvrement_template,
    render_missed_promise_clause,
    render_schedule_sentence,
)
from tessera.recouvrement.reformulation import (
    DEFAULT_TIMEOUT_S,
    FidelityCheck,
    check_must_survive,
    gate_tone_instruction,
    judge_template_fidelity_llm,
    reformulate_tone_llm,
)

__all__ = [
    "DEFAULT_SET_PATH",
    "REFORMULATION_DIR",
    "CandidateVerdict",
    "LlmReformulationVerdict",
    "ReformulationCandidate",
    "ReformulationCase",
    "ReformulationSet",
    "build_report",
    "load_reformulation_set",
    "main",
    "render_case_template",
    "score_checker_column",
    "score_llm_column",
]

REFORMULATION_DIR = Path(__file__).parent / "reformulation"
DEFAULT_SET_PATH = REFORMULATION_DIR / "recouvrement.json"
_SCHEMA_PATH = REFORMULATION_DIR / "_schema.json"


@dataclass(frozen=True, slots=True)
class ReformulationCandidate:
    """One labeled candidate rewrite: what a reviewer says about its fidelity."""

    id: str
    label: str
    violation: str | None
    text: str
    provenance: str


@dataclass(frozen=True, slots=True)
class ReformulationCase:
    """One referent case: a template context, a tone instruction, labeled candidates."""

    id: str
    language: str
    template_kind: str
    context: dict[str, object]
    tone_instruction: str
    expected_gate: str
    candidates: tuple[ReformulationCandidate, ...]
    provenance: str


@dataclass(frozen=True, slots=True)
class ReformulationSet:
    """The validated referent, with a sha256 so every report names what it measured."""

    agent_id: str
    set_version: str
    sha256: str
    cases: tuple[ReformulationCase, ...]


def load_reformulation_set(path: Path | None = None) -> ReformulationSet:
    """Load and validate the labeled reformulation set.

    Strict like the intent-set loader: a set that does not validate, or carries a
    duplicate case id, fails loudly here rather than silently shrinking the
    referent downstream.

    Args:
        path: Set file to load; defaults to :data:`DEFAULT_SET_PATH`.

    Returns:
        The validated set with a sha256 over its canonical JSON.

    Raises:
        jsonschema.ValidationError: If the file does not match ``_schema.json``.
        ValueError: If two cases share an id.
    """
    set_path = path or DEFAULT_SET_PATH
    raw = json.loads(set_path.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(raw, schema)
    document = cast(dict[str, object], raw)
    cases: list[ReformulationCase] = []
    seen_ids: set[str] = set()
    for entry in cast(list[dict[str, object]], document["cases"]):
        case_id = str(entry["id"])
        if case_id in seen_ids:
            msg = f"duplicate reformulation case id {case_id!r} — a duplicate names nothing"
            raise ValueError(msg)
        seen_ids.add(case_id)
        candidates = tuple(
            ReformulationCandidate(
                id=str(c["id"]),
                label=str(c["label"]),
                violation=str(c["violation"]) if "violation" in c else None,
                text=str(c["text"]),
                provenance=str(c["provenance"]),
            )
            for c in cast(list[dict[str, object]], entry["candidates"])
        )
        cases.append(
            ReformulationCase(
                id=case_id,
                language=str(entry["language"]),
                template_kind=str(entry["template_kind"]),
                context=dict(cast(dict[str, object], entry["context"])),
                tone_instruction=str(entry["tone_instruction"]),
                expected_gate=str(entry["expected_gate"]),
                candidates=candidates,
                provenance=str(entry["provenance"]),
            )
        )
    digest = hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return ReformulationSet(
        agent_id=str(document["agent_id"]),
        set_version=str(document["set_version"]),
        sha256=digest,
        cases=tuple(cases),
    )


def render_case_template(case: ReformulationCase) -> str:
    """Render the case's approved template through the REAL production helpers."""
    language = cast(RecouvrementLanguage, case.language)
    template = recouvrement_template(cast(TemplateKind, case.template_kind), language)
    promise_raw = case.context.get("missed_promise_date")
    promise = date.fromisoformat(str(promise_raw)) if promise_raw else None
    return template.render(
        {
            "client": str(case.context["client"]),
            "case_id": str(case.context["case_id"]),
            "amount_due_label": str(case.context["amount_due_label"]),
            "days_late": case.context["days_late"],
            "missed_promise_clause": render_missed_promise_clause(promise, language),
            "schedule_sentence": render_schedule_sentence(
                case.context.get("requested_months"),
                case.context.get("monthly_amount_label"),
                language,
            ),
        }
    )


def _checker_context(case: ReformulationCase) -> dict[str, str]:
    return {
        "client": str(case.context["client"]),
        "case_id": str(case.context["case_id"]),
        "amount_due_label": str(case.context["amount_due_label"]),
    }


@dataclass(frozen=True, slots=True)
class CandidateVerdict:
    """The checker's answer on one labeled candidate, and whether it agrees with the label."""

    case: ReformulationCase
    candidate: ReformulationCandidate
    check: FidelityCheck
    agrees: bool


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """Whether the closed-vocabulary gate agrees with the case's expected outcome."""

    case: ReformulationCase
    refused: bool
    agrees: bool


def score_checker_column(
    cases: tuple[ReformulationCase, ...],
) -> tuple[list[CandidateVerdict], list[GateVerdict]]:
    """Run the deterministic checker and the gate over the whole referent."""
    candidate_verdicts: list[CandidateVerdict] = []
    gate_verdicts: list[GateVerdict] = []
    for case in cases:
        refused = gate_tone_instruction(case.tone_instruction) is None
        gate_verdicts.append(
            GateVerdict(
                case=case,
                refused=refused,
                agrees=refused == (case.expected_gate == "refuse_instruction"),
            )
        )
        if case.expected_gate != "generate":
            continue
        template_text = render_case_template(case)
        for candidate in case.candidates:
            check = check_must_survive(
                template_text,
                candidate.text,
                language=case.language,
                context=_checker_context(case),
            )
            candidate_verdicts.append(
                CandidateVerdict(
                    case=case,
                    candidate=candidate,
                    check=check,
                    agrees=check.ok == (candidate.label == "faithful"),
                )
            )
    return candidate_verdicts, gate_verdicts


@dataclass(frozen=True, slots=True)
class LlmReformulationVerdict:
    """One live generation, held to the deterministic checker (and optionally the judge)."""

    case: ReformulationCase
    status: str
    checker_ok: bool | None
    checker_failures: tuple[str, ...]
    fidelity: float | None
    judge_status: str | None
    latency_ms: float
    model: str


def score_llm_column(
    cases: tuple[ReformulationCase, ...],
    *,
    timeout_s: float,
    concurrency: int,
    model: str | None,
    judge: bool,
) -> list[LlmReformulationVerdict]:
    """Generate a reformulation per generate-gated case and hold it to the checker.

    Spends real model calls (one per case, two with ``--judge``); adversarial cases
    are deliberately skipped — their measurement IS the gate column.
    """
    generate_cases = [case for case in cases if case.expected_gate == "generate"]

    async def _one(case: ReformulationCase, gate: asyncio.Semaphore) -> LlmReformulationVerdict:
        async with gate:
            template_text = render_case_template(case)
            outcome = await reformulate_tone_llm(
                template_text,
                tone_instruction=case.tone_instruction,
                language=case.language,
                timeout_s=timeout_s,
                model=model,
            )
            checker_ok: bool | None = None
            failures: tuple[str, ...] = ()
            fidelity: float | None = None
            judge_status: str | None = None
            if outcome.status == "candidate" and outcome.text is not None:
                check = check_must_survive(
                    template_text,
                    outcome.text,
                    language=case.language,
                    context=_checker_context(case),
                )
                checker_ok = check.ok
                failures = check.failures
                if judge:
                    judgement = await judge_template_fidelity_llm(
                        template_text,
                        outcome.text,
                        language=case.language,
                        timeout_s=timeout_s,
                        model=model,
                    )
                    judge_status = judgement.status
                    fidelity = judgement.fidelity
            return LlmReformulationVerdict(
                case=case,
                status=outcome.status,
                checker_ok=checker_ok,
                checker_failures=failures,
                fidelity=fidelity,
                judge_status=judge_status,
                latency_ms=outcome.latency_ms,
                model=outcome.model,
            )

    async def _run() -> list[LlmReformulationVerdict]:
        gate = asyncio.Semaphore(max(1, concurrency))
        return list(await asyncio.gather(*(_one(case, gate) for case in generate_cases)))

    return asyncio.run(_run())


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(fraction * (len(ordered) - 1)))
    return round(ordered[index], 1)


def _checker_counts(verdicts: list[CandidateVerdict]) -> dict[str, object]:
    faithful = [v for v in verdicts if v.candidate.label == "faithful"]
    violations = [v for v in verdicts if v.candidate.label == "violates"]
    return {
        "candidates": len(verdicts),
        "label_agreement": sum(1 for v in verdicts if v.agrees),
        "faithful_n": len(faithful),
        "faithful_pass": sum(1 for v in faithful if v.check.ok),
        "violations_n": len(violations),
        "violations_caught": sum(1 for v in violations if not v.check.ok),
    }


def build_report(
    referent: ReformulationSet,
    candidate_verdicts: list[CandidateVerdict],
    gate_verdicts: list[GateVerdict],
    llm_verdicts: list[LlmReformulationVerdict] | None = None,
) -> dict[str, object]:
    """Assemble the report; the LLM column is honestly absent unless a run measured it."""
    languages = sorted({case.language for case in referent.cases})
    by_language = {
        language: _checker_counts([v for v in candidate_verdicts if v.case.language == language])
        for language in languages
    }
    by_violation: dict[str, dict[str, int]] = {}
    for verdict in candidate_verdicts:
        kind = verdict.candidate.violation
        if kind is None:
            continue
        bucket = by_violation.setdefault(kind, {"n": 0, "caught": 0})
        bucket["n"] += 1
        bucket["caught"] += 0 if verdict.check.ok else 1
    disagreements = [f"{v.case.id}/{v.candidate.id}" for v in candidate_verdicts if not v.agrees]
    llm_column: dict[str, object]
    if llm_verdicts is None:
        llm_column = {
            "status": "not_run",
            "reason": (
                "the LLM column only exists when a run measured it (--llm); "
                "this column must never carry a fabricated number"
            ),
        }
    else:
        latencies = [v.latency_ms for v in llm_verdicts]
        scored = [v.fidelity for v in llm_verdicts if v.fidelity is not None]
        llm_column = {
            "status": "measured",
            "n": len(llm_verdicts),
            "candidates": sum(1 for v in llm_verdicts if v.status == "candidate"),
            "checker_pass": sum(1 for v in llm_verdicts if v.checker_ok is True),
            "failures_by_status": {
                status: sum(1 for v in llm_verdicts if v.status == status)
                for status in sorted({v.status for v in llm_verdicts})
            },
            "judge_scored": len(scored),
            "judge_fidelity_min": min(scored) if scored else None,
            "latency_ms_p50": _percentile(latencies, 0.5),
            "latency_ms_max": _percentile(latencies, 1.0),
            "models": sorted({v.model for v in llm_verdicts if v.model}),
            "checker_failures": {
                f"{v.case.id}": list(v.checker_failures)
                for v in llm_verdicts
                if v.checker_ok is False
            },
        }
    return {
        "schema_version": "reformulation_bench.v1",
        "run_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "agent_id": referent.agent_id,
        "set_version": referent.set_version,
        "set_sha256": referent.sha256,
        "columns": {
            "checker": {
                "status": "measured",
                "checker": "tessera.recouvrement.reformulation.check_must_survive",
                "overall": _checker_counts(candidate_verdicts),
                "by_language": by_language,
                "by_violation": by_violation,
                "gate": {
                    "n": len(gate_verdicts),
                    "agreement": sum(1 for v in gate_verdicts if v.agrees),
                    "refused": sum(1 for v in gate_verdicts if v.refused),
                },
                "disagreements": disagreements,
            },
            "llm": llm_column,
        },
    }


def _print_report(report: dict[str, object]) -> None:
    columns = cast(dict[str, dict[str, object]], report["columns"])
    checker = columns["checker"]
    overall = cast(dict[str, object], checker["overall"])
    gate = cast(dict[str, object], checker["gate"])
    print(
        f"reformulation bench — set {report['set_version']} "
        f"(sha {str(report['set_sha256'])[:12]}) · run {report['run_at']}"
    )
    print(
        f"  checker: {overall['label_agreement']}/{overall['candidates']} labels agreed · "
        f"faithful {overall['faithful_pass']}/{overall['faithful_n']} pass · "
        f"violations {overall['violations_caught']}/{overall['violations_n']} caught"
    )
    print(f"  gate: {gate['agreement']}/{gate['n']} agreed ({gate['refused']} refused)")
    llm = columns["llm"]
    if llm.get("status") == "measured":
        print(
            f"  llm: {llm['candidates']}/{llm['n']} candidates · "
            f"checker pass {llm['checker_pass']} · p50 {llm['latency_ms_p50']} ms · "
            f"models {llm['models']}"
        )
    else:
        print("  llm: not run (--llm to measure — spends real calls)")


def main(argv: list[str] | None = None) -> int:
    """Run the bench and optionally publish the JSON report."""
    parser = argparse.ArgumentParser(description="Recouvrement layer-3 reformulation bench")
    parser.add_argument(
        "--set",
        dest="set_path",
        type=Path,
        default=None,
        help=f"labeled set to score (default: {DEFAULT_SET_PATH})",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="write the JSON report to this path (publication is deliberate, never a side effect)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="also generate live reformulations against the profile backend (spends real calls)",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="with --llm: also score each candidate with the fidelity judge (a second call)",
    )
    parser.add_argument(
        "--llm-timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"per-call bound for the LLM column, seconds (default {DEFAULT_TIMEOUT_S})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="concurrent LLM calls (default 2 — a letter is a long generation)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="model override for the LLM column (candidate measurement); default: profile base",
    )
    args = parser.parse_args(argv)
    referent = load_reformulation_set(args.set_path)
    candidate_verdicts, gate_verdicts = score_checker_column(referent.cases)
    llm_verdicts = (
        score_llm_column(
            referent.cases,
            timeout_s=args.llm_timeout,
            concurrency=args.concurrency,
            model=args.llm_model,
            judge=args.judge,
        )
        if args.llm
        else None
    )
    report = build_report(referent, candidate_verdicts, gate_verdicts, llm_verdicts)
    _print_report(report)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"  report written: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
