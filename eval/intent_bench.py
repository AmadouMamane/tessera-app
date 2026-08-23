"""Offline intent bench for Recouvrement layer-1 understanding (ADR 0053 §7).

Two columns on the same labeled set: the deterministic regex baseline (the null
floor, ADR 0021 applied to a classifier) and — once slice 3 wires it — the LLM
classifier. This slice runs the regex column only; the LLM column reports itself
absent rather than carrying a fabricated number (ADR 0026: a witness that cannot
see never says "ok").

The regex column scores the ROUTER'S answer, never the matcher's silence: a case
no word list matches routes to :data:`tessera.agent.recouvrement.DEFAULT_TEXT_INTENT`,
exactly as ``route_recouvrement_intent`` does for a turn with no drawer context,
and the report counts those defaults separately.

Run ``uv run python -m eval.intent_bench`` to print the table. ``--report PATH``
additionally writes the JSON report — writing a report is a deliberate act of
publication, never a side effect. Reports belong under ``eval/reports/intent_bench/``,
a directory the gating-report sweep does not read (its globs are non-recursive
over ``eval/reports/<env>/`` and the flat root).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import jsonschema

from tessera.agent.recouvrement import (
    DEFAULT_TEXT_INTENT,
    classify_recouvrement_text,
    extract_recouvrement_text_fields,
)
from tessera.recouvrement.understanding import (
    DEFAULT_TIMEOUT_S,
    UnderstandingOutcome,
    classify_intent_llm,
)

__all__ = [
    "DEFAULT_SET_PATH",
    "INTENTS_DIR",
    "CaseVerdict",
    "IntentCase",
    "IntentSet",
    "LlmCaseVerdict",
    "build_report",
    "load_intent_set",
    "main",
    "score_llm_column",
    "score_regex_column",
]

INTENTS_DIR = Path(__file__).parent / "intents"
DEFAULT_SET_PATH = INTENTS_DIR / "recouvrement.json"
_SCHEMA_PATH = INTENTS_DIR / "_schema.json"

#: The two field keys the labeled set may carry (mirrors the set schema).
_FIELD_KEYS = ("duration_months", "requested_time")


@dataclass(frozen=True, slots=True)
class IntentCase:
    """One labeled utterance: what a human reader understands the operator to ask."""

    id: str
    language: str
    utterance: str
    expected_intent: str
    expected_fields: dict[str, object]
    provenance: str
    note: str | None


@dataclass(frozen=True, slots=True)
class IntentSet:
    """The loaded, schema-validated labeled set, with its content digest."""

    agent_id: str
    set_version: str
    sha256: str
    cases: tuple[IntentCase, ...]


@dataclass(frozen=True, slots=True)
class CaseVerdict:
    """One classifier column's answer to one labeled case."""

    case: IntentCase
    predicted_intent: str
    matched: bool
    correct: bool
    predicted_fields: dict[str, object]
    field_exact: dict[str, bool]


def load_intent_set(path: Path | None = None) -> IntentSet:
    """Load and validate the labeled intent set.

    Strict on purpose, like the eval-set loader: a set that does not validate, or
    that carries a duplicate case id, fails loudly here rather than silently
    shrinking the referent downstream.

    Args:
        path: Set file to load; defaults to :data:`DEFAULT_SET_PATH`.

    Returns:
        The validated set with a sha256 over its canonical JSON, so every report
        can name exactly which referent produced its numbers.

    Raises:
        jsonschema.ValidationError: If the file does not match ``_schema.json``.
        ValueError: If two cases share an id.
    """
    set_path = path or DEFAULT_SET_PATH
    raw = json.loads(set_path.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(raw, schema)
    document = cast(dict[str, object], raw)
    raw_cases = cast(list[dict[str, object]], document["cases"])
    cases: list[IntentCase] = []
    seen_ids: set[str] = set()
    for entry in raw_cases:
        case_id = str(entry["id"])
        if case_id in seen_ids:
            msg = f"duplicate intent case id {case_id!r} — a duplicated referent names nothing"
            raise ValueError(msg)
        seen_ids.add(case_id)
        cases.append(
            IntentCase(
                id=case_id,
                language=str(entry["language"]),
                utterance=str(entry["utterance"]),
                expected_intent=str(entry["expected_intent"]),
                expected_fields=dict(cast(dict[str, object], entry.get("expected_fields", {}))),
                provenance=str(entry["provenance"]),
                note=str(entry["note"]) if "note" in entry else None,
            )
        )
    digest = hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return IntentSet(
        agent_id=str(document["agent_id"]),
        set_version=str(document["set_version"]),
        sha256=digest,
        cases=tuple(cases),
    )


def score_regex_column(cases: tuple[IntentCase, ...]) -> list[CaseVerdict]:
    """Score the deterministic regex classifier — the router's actual answer.

    ``matched`` records whether a word list answered; when none did, the verdict
    is the router's default (:data:`DEFAULT_TEXT_INTENT`), scored as the answer
    the operator would have received. Field exactness is judged only on the keys
    the case labels: an unlabeled field claims nothing and scores nothing.

    Args:
        cases: The labeled cases to score.

    Returns:
        One verdict per case, in set order.
    """
    verdicts: list[CaseVerdict] = []
    for case in cases:
        text_verdict = classify_recouvrement_text(case.utterance)
        matched = text_verdict is not None
        predicted_intent = text_verdict[0] if text_verdict is not None else DEFAULT_TEXT_INTENT
        predicted_fields = extract_recouvrement_text_fields(case.utterance)
        field_exact = {
            key: predicted_fields.get(key) == expected
            for key, expected in case.expected_fields.items()
        }
        verdicts.append(
            CaseVerdict(
                case=case,
                predicted_intent=predicted_intent,
                matched=matched,
                correct=predicted_intent == case.expected_intent,
                predicted_fields=predicted_fields,
                field_exact=field_exact,
            )
        )
    return verdicts


@dataclass(frozen=True, slots=True)
class LlmCaseVerdict:
    """The LLM column's answer to one labeled case (ADR 0053 slice 3)."""

    case: IntentCase
    outcome: UnderstandingOutcome
    correct: bool
    field_exact: dict[str, bool]


def score_llm_column(
    cases: tuple[IntentCase, ...],
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    concurrency: int = 4,
    model: str | None = None,
) -> list[LlmCaseVerdict]:
    """Score the LLM classifier over the same referent, a few cases at a time.

    Runs the REAL classifier (:func:`classify_intent_llm` — same prompt, same
    backend seam, same schema as the shadow), so the column measures the thing
    that would serve, never a bench-only re-implementation (ADR 0026). Failures
    (timeout / schema_invalid / llm_error / budget_ceiling) score as incorrect
    in the raw column and are counted by kind; the active-mode composition
    (LLM verdict, else regex) is derived in :func:`build_report`.

    Args:
        cases: The labeled cases to score.
        timeout_s: Per-call bound on the model.
        concurrency: How many calls run at once (be kind to a local model).

    Returns:
        One verdict per case, in set order.
    """

    async def _run() -> list[LlmCaseVerdict]:
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def _one(case: IntentCase) -> LlmCaseVerdict:
            async with semaphore:
                outcome = await classify_intent_llm(
                    case.utterance, language=case.language, timeout_s=timeout_s, model=model
                )
            verdict = outcome.verdict
            predicted_fields: dict[str, object] = {}
            if verdict is not None:
                if verdict.duration_months is not None:
                    predicted_fields["duration_months"] = verdict.duration_months
                if verdict.requested_time is not None:
                    predicted_fields["requested_time"] = verdict.requested_time
            field_exact = {
                key: predicted_fields.get(key) == expected
                for key, expected in case.expected_fields.items()
            }
            return LlmCaseVerdict(
                case=case,
                outcome=outcome,
                correct=verdict is not None and verdict.intent == case.expected_intent,
                field_exact=field_exact,
            )

        return list(await asyncio.gather(*(_one(case) for case in cases)))

    return asyncio.run(_run())


def _counts(verdicts: list[CaseVerdict]) -> dict[str, object]:
    """Counts for one population: n, correct, defaulted, and the derived rate."""
    n = len(verdicts)
    correct = sum(1 for verdict in verdicts if verdict.correct)
    defaulted = sum(1 for verdict in verdicts if not verdict.matched)
    return {
        "n": n,
        "correct": correct,
        "defaulted": defaulted,
        "accuracy": round(correct / n, 4) if n else None,
    }


def _llm_counts(verdicts: list[LlmCaseVerdict]) -> dict[str, object]:
    """Counts for one LLM-column population: n, correct, failures by kind, rate."""
    n = len(verdicts)
    correct = sum(1 for verdict in verdicts if verdict.correct)
    return {
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else None,
    }


def _llm_column(
    verdicts: list[LlmCaseVerdict], regex_verdicts: list[CaseVerdict]
) -> dict[str, object]:
    """The measured LLM column, plus the active-mode composition (LLM verdict, else regex)."""
    languages = sorted({v.case.language for v in verdicts})
    failures: dict[str, int] = {}
    for verdict in verdicts:
        if verdict.outcome.status != "verdict":
            failures[verdict.outcome.status] = failures.get(verdict.outcome.status, 0) + 1
    fields: dict[str, dict[str, object]] = {}
    for key in _FIELD_KEYS:
        labeled = [v for v in verdicts if key in v.case.expected_fields]
        if labeled:
            fields[key] = {
                "n": len(labeled),
                "exact": sum(1 for v in labeled if v.field_exact.get(key, False)),
            }
    regex_by_id = {v.case.id: v for v in regex_verdicts}
    composed_correct = 0
    for verdict in verdicts:
        if verdict.outcome.status == "verdict":
            composed_correct += int(verdict.correct)
        else:
            fallback = regex_by_id.get(verdict.case.id)
            composed_correct += int(fallback.correct) if fallback is not None else 0
    models = sorted({v.outcome.model for v in verdicts if v.outcome.model})
    prompt_versions = sorted({v.outcome.prompt_version for v in verdicts})
    latencies = sorted(v.outcome.latency_ms for v in verdicts)
    return {
        "status": "measured",
        "classifier": "tessera.recouvrement.understanding.classify_intent_llm",
        "models": models,
        "prompt_versions": prompt_versions,
        "overall": _llm_counts(verdicts),
        "by_language": {
            language: _llm_counts([v for v in verdicts if v.case.language == language])
            for language in languages
        },
        "failures": failures,
        "fields": fields,
        "latency_ms": {
            "p50": round(latencies[len(latencies) // 2], 1) if latencies else None,
            "max": round(latencies[-1], 1) if latencies else None,
        },
        "with_regex_fallback": {
            "n": len(verdicts),
            "correct": composed_correct,
            "accuracy": round(composed_correct / len(verdicts), 4) if verdicts else None,
        },
        "threshold_sweep": _threshold_sweep(verdicts, regex_by_id),
        "misrouted_case_ids": [v.case.id for v in verdicts if not v.correct],
    }


def _threshold_sweep(
    verdicts: list[LlmCaseVerdict], regex_by_id: dict[str, CaseVerdict]
) -> dict[str, object]:
    """Composed correctness (LLM above t, else regex) for every candidate threshold.

    This is the ADR 0053 §6 calibration read: the RULE (below the threshold, the
    regex serves) is engraved; the NUMBER a governed write stores is the lowest
    threshold maximising the composed count on a measured run — cited, never
    picked. The sweep travels in the report so the citation is checkable.
    """
    points: list[dict[str, object]] = []
    best_threshold = 0.0
    best_correct = -1
    for step in range(21):
        threshold = step / 20
        correct_at = 0
        for verdict in verdicts:
            confident = (
                verdict.outcome.status == "verdict"
                and verdict.outcome.verdict is not None
                and verdict.outcome.verdict.confidence >= threshold
            )
            if confident:
                correct_at += int(verdict.correct)
            else:
                fallback = regex_by_id.get(verdict.case.id)
                correct_at += int(fallback.correct) if fallback is not None else 0
        points.append({"threshold": threshold, "correct": correct_at})
        if correct_at > best_correct:
            best_correct = correct_at
            best_threshold = threshold
    return {
        "points": points,
        "suggested": {"threshold": best_threshold, "correct": best_correct},
    }


def build_report(
    intent_set: IntentSet,
    verdicts: list[CaseVerdict],
    llm_verdicts: list[LlmCaseVerdict] | None = None,
) -> dict[str, object]:
    """Assemble the two-column report; an absent column names itself absent.

    Every number travels with its population (overall / by language / by cell),
    cells stay COUNTS (a rate on a small n is a count in disguise), and the
    report names its referent (set version + sha) and its window (one run, its
    timestamp) — ADR 0026/0052 applied to a harness artifact.

    Args:
        intent_set: The referent the verdicts were scored against.
        verdicts: The regex column's verdicts over that referent.
        llm_verdicts: The LLM column's verdicts, when that column ran; ``None``
            keeps the column honestly absent.

    Returns:
        The report document (``intent_bench.v1``).
    """
    languages = sorted({case.language for case in intent_set.cases})
    intents = sorted({case.expected_intent for case in intent_set.cases})
    by_language = {
        language: _counts([v for v in verdicts if v.case.language == language])
        for language in languages
    }
    by_cell: dict[str, dict[str, object]] = {}
    for language in languages:
        for intent in intents:
            cell = [
                v
                for v in verdicts
                if v.case.language == language and v.case.expected_intent == intent
            ]
            if cell:
                by_cell[f"{language}/{intent}"] = {
                    "n": len(cell),
                    "correct": sum(1 for v in cell if v.correct),
                }
    fields: dict[str, dict[str, object]] = {}
    for key in _FIELD_KEYS:
        labeled = [v for v in verdicts if key in v.case.expected_fields]
        if labeled:
            fields[key] = {
                "n": len(labeled),
                "exact": sum(1 for v in labeled if v.field_exact.get(key, False)),
            }
    misrouted = [v.case.id for v in verdicts if not v.correct]
    return {
        "schema_version": "intent_bench.v1",
        "run_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "agent_id": intent_set.agent_id,
        "set_version": intent_set.set_version,
        "set_sha256": intent_set.sha256,
        "columns": {
            "regex": {
                "status": "measured",
                "classifier": "tessera.agent.recouvrement.classify_recouvrement_text",
                "overall": _counts(verdicts),
                "by_language": by_language,
                "by_cell": by_cell,
                "fields": fields,
                "misrouted_case_ids": misrouted,
            },
            "llm": (
                _llm_column(llm_verdicts, verdicts)
                if llm_verdicts is not None
                else {
                    "status": "not_run",
                    "reason": (
                        "the LLM column only exists when a run measured it (--llm); "
                        "this column must never carry a fabricated number"
                    ),
                }
            ),
        },
    }


def _format_counts(label: str, counts: dict[str, object]) -> str:
    """One human line for one population's counts."""
    accuracy = counts["accuracy"]
    rate = f" ({float(cast(float, accuracy)) * 100:.1f} %)" if accuracy is not None else ""
    return (
        f"{label}: {counts['correct']}/{counts['n']} correct{rate}, "
        f"{counts['defaulted']} answered by default"
    )


def _print_report(report: dict[str, object]) -> None:
    """Print the two-column table; the absent column prints its absence."""
    regex_column = cast(dict[str, object], cast(dict[str, object], report["columns"])["regex"])
    llm_column = cast(dict[str, object], cast(dict[str, object], report["columns"])["llm"])
    overall = cast(dict[str, object], regex_column["overall"])
    print(
        f"[intent-bench] {report['agent_id']} · set {report['set_version']} "
        f"(sha {str(report['set_sha256'])[:12]}) · run {report['run_at']}"
    )
    print("  column regex — " + _format_counts("overall", overall))
    for language, counts in cast(dict[str, dict[str, object]], regex_column["by_language"]).items():
        print("    " + _format_counts(language, counts))
    for key, stats in cast(dict[str, dict[str, object]], regex_column["fields"]).items():
        print(f"    field {key}: {stats['exact']}/{stats['n']} exact")
    misrouted = cast(list[str], regex_column["misrouted_case_ids"])
    if misrouted:
        print(f"    misrouted ({len(misrouted)}): " + ", ".join(misrouted))
    if llm_column["status"] != "measured":
        print(f"  column llm — {llm_column['status']}: {llm_column['reason']}")
        return
    overall_llm = cast(dict[str, object], llm_column["overall"])
    composed = cast(dict[str, object], llm_column["with_regex_fallback"])
    print(
        "  column llm — "
        + _format_llm_counts("overall", overall_llm)
        + f" · models {llm_column['models']}"
    )
    for language, counts in cast(dict[str, dict[str, object]], llm_column["by_language"]).items():
        print("    " + _format_llm_counts(language, counts))
    failures = cast(dict[str, int], llm_column["failures"])
    if failures:
        print("    failures: " + ", ".join(f"{kind} {n}" for kind, n in sorted(failures.items())))
    for key, stats in cast(dict[str, dict[str, object]], llm_column["fields"]).items():
        print(f"    field {key}: {stats['exact']}/{stats['n']} exact")
    latency = cast(dict[str, object], llm_column["latency_ms"])
    print(f"    latency ms: p50 {latency['p50']} · max {latency['max']}")
    print("    " + _format_llm_counts("with regex fallback (active-mode composition)", composed))
    sweep = cast(dict[str, object], llm_column["threshold_sweep"])
    suggested = cast(dict[str, object], sweep["suggested"])
    print(
        f"    threshold sweep suggests: {suggested['threshold']} "
        f"(composed {suggested['correct']}/{composed['n']})"
    )


def _format_llm_counts(label: str, counts: dict[str, object]) -> str:
    """One human line for one LLM-column population's counts."""
    accuracy = counts["accuracy"]
    rate = f" ({float(cast(float, accuracy)) * 100:.1f} %)" if accuracy is not None else ""
    return f"{label}: {counts['correct']}/{counts['n']} correct{rate}"


def main(argv: list[str] | None = None) -> int:
    """Run the bench and optionally publish the JSON report.

    Args:
        argv: CLI arguments; ``None`` reads ``sys.argv``.

    Returns:
        Process exit code (0 — the bench measures, the ratchet judges).
    """
    parser = argparse.ArgumentParser(description="Recouvrement layer-1 intent bench (ADR 0053)")
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
        help="also run the LLM column against the live profile backend (spends real calls)",
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
        default=4,
        help="concurrent LLM calls (default 4 — be kind to a local model)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="model override for the LLM column (candidate measurement); default: profile base",
    )
    args = parser.parse_args(argv)
    intent_set = load_intent_set(args.set_path)
    verdicts = score_regex_column(intent_set.cases)
    llm_verdicts = (
        score_llm_column(
            intent_set.cases,
            timeout_s=args.llm_timeout,
            concurrency=args.concurrency,
            model=args.llm_model,
        )
        if args.llm
        else None
    )
    report = build_report(intent_set, verdicts, llm_verdicts)
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
