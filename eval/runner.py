"""Run the failure-case catalogue against the live agent.

Used as both a CLI (``uv run python scripts/run_eval.py``) and a library —
``main()`` returns the exit code so CI workflows can call it directly.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import jsonschema

from eval.gate import GateVerdict, evaluate_gate
from eval.scorecard import build_scorecard
from eval.sets import EvalSet, critical_case_ids, load_eval_set
from tessera.agent import compile_graph
from tessera.agent.registry import get_agent
from tessera.agent.state import new_state
from tessera.llm.budget import get_budget_tracker
from tessera.observability.eval.report_paths import reports_write_dir
from tessera.observability.eval_gate_view import structural_gate
from tessera.settings import LanguageCode, LLMProfile, get_settings

FAILURES_DIR = Path(__file__).parent / "failures"
SCHEMA_PATH = FAILURES_DIR / "_schema.json"
# Writes go to eval/reports/<env>/ exclusively (ADR 0014, layer 3).
REPORTS_DIR = Path(__file__).parent / "reports"


@dataclass(frozen=True, slots=True)
class CaseResult:
    """The result of running a single failure case in a single language."""

    case_id: str
    language: str
    passed: bool
    reasons: list[str]
    final_response: str
    needs_escalation: bool
    invoked_tools: list[str]
    category: str = ""
    title: str = ""
    expected_behavior: str = ""
    started_at: str = ""
    ended_at: str = ""
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


def _load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_cases() -> list[dict[str, object]]:
    schema = _load_schema()
    cases: list[dict[str, object]] = []
    for path in sorted(FAILURES_DIR.glob("[0-9][0-9]*_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.validate(payload, schema)
        cases.append(payload)
    return cases


def _catalogue_version(cases: list[dict[str, object]]) -> str:
    """Short identifier of the catalogue a run was scored against (count + id hash).

    Lets the dashboard distinguish runs across catalogue versions so pass rates
    measured on different case sets are never compared as if equivalent.
    """
    ids = sorted(str(c["id"]) for c in cases)
    digest = hashlib.sha256("\n".join(ids).encode()).hexdigest()[:8]
    return f"{len(ids)}-{digest}"


def _check_substrings(pass_criteria: dict[str, object], response: str) -> list[str]:
    """must_not_contain / must_contain_any / must_not_match (regex)."""
    reasons: list[str] = []
    must_not = pass_criteria.get("must_not_contain") or []
    if isinstance(must_not, list):
        reasons += [
            f"response contained forbidden substring {n!r}" for n in must_not if str(n) in response
        ]
    must_any = pass_criteria.get("must_contain_any") or []
    if isinstance(must_any, list) and must_any and not any(str(n) in response for n in must_any):
        reasons.append(f"response did not contain any required substring from {must_any!r}")
    patterns = pass_criteria.get("must_not_match") or []
    if isinstance(patterns, list):
        for pattern in patterns:
            try:
                if re.search(str(pattern), response):
                    reasons.append(f"response matched forbidden pattern {pattern!r}")
            except re.error as exc:
                reasons.append(f"invalid must_not_match regex {pattern!r}: {exc}")
    return reasons


def _check_tools(pass_criteria: dict[str, object], invoked: set[str]) -> list[str]:
    """must_not_invoke_tools / must_invoke_tools (failure to act)."""
    reasons: list[str] = []
    forbidden = pass_criteria.get("must_not_invoke_tools") or []
    if isinstance(forbidden, list):
        reasons += [f"forbidden tool {t!r} was invoked" for t in forbidden if str(t) in invoked]
    required = pass_criteria.get("must_invoke_tools") or []
    if isinstance(required, list):
        reasons += [
            f"required tool {t!r} was not invoked (failure to act)"
            for t in required
            if str(t) not in invoked
        ]
    return reasons


def _check_signals(pass_criteria: dict[str, object], final_state: dict[str, object]) -> list[str]:
    """must_escalate / confidence bounds / must_cite_source."""
    reasons: list[str] = []
    if "must_escalate" in pass_criteria:
        expected = bool(pass_criteria["must_escalate"])
        actual = bool(final_state.get("needs_escalation", False))
        if expected != actual:
            reasons.append(f"escalation expected={expected}, actual={actual}")
    confidence = final_state.get("confidence")
    conf = float(confidence) if isinstance(confidence, int | float) else None
    min_conf = pass_criteria.get("min_confidence")
    if isinstance(min_conf, int | float) and (conf is None or conf < float(min_conf)):
        reasons.append(f"confidence {conf} below min_confidence {min_conf}")
    max_conf = pass_criteria.get("max_confidence")
    if isinstance(max_conf, int | float) and conf is not None and conf > float(max_conf):
        reasons.append(f"confidence {conf} above max_confidence {max_conf}")
    if pass_criteria.get("must_cite_source") and not final_state.get("citations"):
        reasons.append("response is not backed by any retrieved citation")
    return reasons


def _evaluate(
    case: dict[str, object],
    _language: str,
    final_state: dict[str, object],
) -> tuple[bool, list[str]]:
    """Return (passed, reasons) for one (case, language) pair."""
    response = str(final_state.get("final_response", ""))
    pass_criteria = case.get("pass_criteria") or {}
    if not isinstance(pass_criteria, dict):
        return False, ["pass_criteria is malformed"]
    # Only count tool calls that succeeded — a guard deny is not an invocation.
    invoked = {call.tool_name for call in final_state.get("tool_calls", []) if call.succeeded}
    reasons = (
        _check_substrings(pass_criteria, response)
        + _check_tools(pass_criteria, invoked)
        + _check_signals(pass_criteria, final_state)
    )
    return not reasons, reasons


async def _run_case(case: dict[str, object], language: str, model: str | None = None) -> CaseResult:
    prompt_bundle = (case.get("prompts") or {}).get(language)
    if not isinstance(prompt_bundle, dict):
        return CaseResult(
            case_id=str(case["id"]),
            language=language,
            passed=False,
            reasons=[f"no prompt configured for {language!r}"],
            final_response="",
            needs_escalation=False,
            invoked_tools=[],
        )

    user_input = str(prompt_bundle["user"])
    initial = new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=user_input,
        language=LanguageCode(language),
        language_confidence=1.0,
        model=model,
    )
    graph = compile_graph()
    started = datetime.now(UTC)
    try:
        final_state = await graph.ainvoke(initial)
    except Exception as exc:  # one case must never crash the whole language run
        ended = datetime.now(UTC)
        return CaseResult(
            case_id=str(case["id"]),
            language=language,
            passed=False,
            reasons=[f"agent error: {type(exc).__name__}: {exc}"],
            final_response="",
            needs_escalation=False,
            invoked_tools=[],
            category=str(case.get("category", "")),
            title=str(case.get("title", "")),
            expected_behavior=str(case.get("expected_behavior", "")),
            started_at=started.isoformat(),
            ended_at=ended.isoformat(),
            duration_ms=(ended - started).total_seconds() * 1000.0,
        )
    ended = datetime.now(UTC)
    passed, reasons = _evaluate(case, language, final_state)
    return CaseResult(
        case_id=str(case["id"]),
        language=language,
        passed=passed,
        reasons=reasons,
        final_response=str(final_state.get("final_response", "")),
        needs_escalation=bool(final_state.get("needs_escalation", False)),
        invoked_tools=[call.tool_name for call in final_state.get("tool_calls", [])],
        category=str(case.get("category", "")),
        title=str(case.get("title", "")),
        expected_behavior=str(case.get("expected_behavior", "")),
        started_at=started.isoformat(),
        ended_at=ended.isoformat(),
        duration_ms=(ended - started).total_seconds() * 1000.0,
        input_tokens=int(final_state.get("input_tokens", 0) or 0),
        output_tokens=int(final_state.get("output_tokens", 0) or 0),
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Tessera failure catalogue.")
    parser.add_argument("--case", help="Run only the case with this id.")
    parser.add_argument(
        "--agent",
        help=(
            "Run an agent's bound evaluation set (its curated subset + the shared "
            "security floor) and apply the two-level eval-gate; the exit code is the "
            "gate verdict. The report is keyed by agent_id."
        ),
    )
    parser.add_argument("--lang", choices=["fr", "de", "en"], help="Restrict to one language.")
    parser.add_argument(
        "--model",
        help="Chat-model override (e.g. gpt-5.5); routes via backend_for_model.",
    )
    parser.add_argument(
        "--synthesis-model",
        help=(
            "If set, a capable model (e.g. gpt-5.5) generates a qualitative "
            "failure synthesis stored in the report (superadmin-only in the UI)."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=reports_write_dir() / "latest.json",
        help="Where to write the JSON scorecard (default: eval/reports/<env>/latest.json).",
    )
    return parser.parse_args(argv)


def _build_gate(
    eval_set: EvalSet | None, results: list[CaseResult]
) -> tuple[GateVerdict | None, dict[str, object] | None]:
    """Compute the two-level gate verdict + its JSON payload for an agent run."""
    if eval_set is None:
        return None, None
    verdict = evaluate_gate(
        [(r.case_id, r.passed) for r in results],
        critical_ids=critical_case_ids(),
        min_pass_rate=eval_set.gate.min_pass_rate,
    )
    payload: dict[str, object] = {
        "passed": verdict.passed,
        "critical_ok": verdict.critical_ok,
        "standard_ok": verdict.standard_ok,
        "failed_critical": list(verdict.failed_critical),
        "standard_total": verdict.standard_total,
        "standard_passed": verdict.standard_passed,
        "standard_pass_rate": round(verdict.standard_pass_rate, 4),
        "min_pass_rate": verdict.min_pass_rate,
    }
    return verdict, payload


async def _record_gating(payload: str) -> None:
    """Record a release-gating run in the owned Postgres table (ADR 0015 §Amendment 2).

    Best-effort at the CLI boundary: a down Postgres must never fail an eval run — the
    report file remains the archive of record and the idempotent sweep reconciles later.
    Non-agent catalogue runs produce no gating rows (the socle is per-agent) and log
    nothing. The Langfuse mirror is flushed before exit (CLI processes don't linger).
    """
    from tessera.observability.eval.gating_scores import record_gating_report

    try:
        inserted = await record_gating_report(json.loads(payload), flush_mirror=True)
    except Exception as exc:
        sys.stderr.write(f"gating store unavailable (report file remains the archive): {exc}\n")
        return
    if inserted:
        sys.stdout.write(f"Gating rows recorded → {inserted}\n")


def _persist_report(args: argparse.Namespace, payload: str, run_ts: str, lang_suffix: str) -> Path:
    """Write the timestamped archive + the relevant "latest", and return the archive.

    Per-agent runs key their archive and "latest" by agent_id so each agent's
    history is independent. Never write through a symlink (a stale latest.json
    symlink would clobber whatever archive it pointed at); drop any symlink first.
    """
    agent_suffix = f"_{args.agent}" if args.agent else ""
    args.report.parent.mkdir(parents=True, exist_ok=True)  # eval/reports/<env>/
    archive = args.report.parent / f"{run_ts}{agent_suffix}{lang_suffix}.json"
    archive.write_text(payload, encoding="utf-8")
    latest_name = f"latest_{args.agent}.json" if args.agent else "latest.json"
    targets = [args.report.parent / latest_name]
    # An explicit --report is honoured; the implicit default never clobbers the
    # global latest.json on an agent run (it has its own per-agent latest).
    if not (args.agent and args.report == reports_write_dir() / "latest.json"):
        targets.append(args.report)
    for target in targets:
        if target.is_symlink():
            target.unlink()
        target.write_text(payload, encoding="utf-8")
    return archive


async def _run_all(args: argparse.Namespace) -> int:
    # Isolate this run's LLM budget from the live agent's *prod* counters and
    # start from zero, so the report records THIS run's *eval* cost. The backends
    # read the tracker lazily, so setting the env (and clearing the cached
    # singleton) before any model call is enough.
    os.environ["TESSERA_BUDGET_FILE"] = str(
        Path(tempfile.mkdtemp(prefix="tessera-eval-budget-")) / "budget.json"
    )
    get_budget_tracker.cache_clear()

    cases = _load_cases()
    eval_set = None
    if args.agent:
        try:
            agent = get_agent(args.agent)
        except KeyError:
            sys.stderr.write(f"unknown agent {args.agent!r}\n")
            return 2
        eval_set = load_eval_set(agent.eval_set)
        wanted = set(eval_set.effective_case_ids)
        cases = [c for c in cases if c["id"] in wanted]
    catalogue_version = _catalogue_version(cases)
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            sys.stderr.write(f"no case with id {args.case!r}\n")
            return 2

    results: list[CaseResult] = []
    for case in cases:
        prompts = case.get("prompts") or {}
        languages = [args.lang] if args.lang else list(case["languages"])
        for language in languages:
            if language not in prompts:
                continue
            result = await _run_case(case, language, args.model)
            results.append(result)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    scorecard = build_scorecard(results)
    run_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lang_suffix = f"_{args.lang}" if args.lang else ""
    settings = get_settings()
    model = args.model or (
        settings.ollama.chat_model
        if settings.resolved_llm_profile() is LLMProfile.ON_PREM
        else settings.vertex.chat_model
    )
    synthesis = None
    if args.synthesis_model:
        from eval.synthesis import generate_synthesis

        synthesis = await generate_synthesis(
            results, model=args.synthesis_model, language=args.lang or "fr"
        )

    # The eval budget for this run (cases + synthesis), recorded into the report
    # so the dashboard can show it separately from the live agent's prod budget.
    budget = get_budget_tracker().snapshot()
    cost = {
        "input_tokens": budget.input_tokens,
        "output_tokens": budget.output_tokens,
        "estimated_cost_eur": float(budget.estimated_cost_eur),
    }

    # Two-level eval-gate (only for an agent run): the exit code is the verdict.
    verdict, gate_payload = _build_gate(eval_set, results)
    # Tier-aware *structural* policy gate carried by the run itself, so the report
    # is authoritative for the structural verdict (the page only layers the
    # dynamic waiver delta on top at render). None for a non-agent catalogue run.
    policy_gate = (
        structural_gate(
            [(r.case_id, r.language, r.passed) for r in results],
            min_pass_rate=eval_set.gate.min_pass_rate,
        )
        if eval_set is not None
        else None
    )

    payload = (
        json.dumps(
            {
                "run_at": run_ts,
                "lang": args.lang,
                "model": model,
                "agent_id": args.agent,
                "eval_set": eval_set.slug if eval_set is not None else None,
                "catalogue_version": catalogue_version,
                "summary": asdict(scorecard.summary),
                "gate": gate_payload,
                "policy_gate": policy_gate,
                "results": [asdict(r) for r in results],
                "synthesis": synthesis,
                "cost": cost,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )  # POSIX text files end in a newline; json.dumps never adds one.

    archive = _persist_report(args, payload, run_ts, lang_suffix)
    await _record_gating(payload)  # durable porteur (ADR 0015 §Amendment 2), best-effort

    sys.stdout.write(f"Report saved → {archive.name}\n")
    sys.stdout.write(scorecard.render_markdown() + "\n")
    if verdict is not None:
        sys.stdout.write("\n" + verdict.render() + "\n")
        return 0 if verdict.passed else 1
    return 0 if scorecard.summary.failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _parse_args(argv)
    return asyncio.run(_run_all(args))


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
