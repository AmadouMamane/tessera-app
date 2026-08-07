"""The eval SWEEP over HTTP — the catalogue world this API could not see.

The evaluations view of ``/surveiller/qualite-ia`` read ``eval/reports/sweep/``,
``eval/baselines/`` and ``eval/failures/`` through the FILESYSTEM
(``webapp/frontend/lib/eval-sweep.ts``): the repo in dev, a bundle baked into the image in
production. Every other block of the same page reads this API. Two transports, two media, two
report populations — ADR 0051's chimera on one screen: a re-grade that lands moves half the
page and leaves the other half telling last month's story, and nothing on screen can say so
because the fields that would (``regraded_at``, the grader's sha) never crossed the wire.

This module gives the sweep ONE address. It reads the same artefacts the TypeScript loader
read — the runs, the committed floor, the discrimination measurement, the case catalogue —
and serves them WITH their provenance: when each run was re-judged, under which criteria sha,
and which runs that sha could not re-derive (the blind runs). What the front's zod schema
used to strip in silence is now the payload's point.

Nothing here recomputes a verdict. The floor travels as committed, never re-derived; the
discrimination artefact travels whole (its reader already refuses what it cannot parse); the
catalogue version is the runner's own arithmetic (``eval/runner.py::_catalogue_version``),
mirrored here exactly as ``eval-sweep.ts`` and pinned by test to the stamp the real reports
carry — so the screen can keep asking the one question no stamp answers alone: *is the case
set still the one this run was scored against?*
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.observability.eval.runs import default_reports_dir
from tessera.observability.eval_floor import CLASSIFICATION, NULL_BASELINE

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "SweepRun",
    "assemble_sweep",
    "catalogue_version_of",
    "compute_eval_sweep",
    "load_case_result",
    "load_run_document",
]

#: The sweep's runs — catalogue-wide reports, N models over ONE case set. A sibling of the
#: per-agent archive (``eval/reports/local/``) that :func:`iter_report_files` deliberately
#: does not see; this module is the one reader.
SWEEP_DIR = default_reports_dir() / "sweep"

#: The case catalogue — one JSON file per documented failure, ``_schema.json`` aside.
FAILURES_DIR = Path(__file__).resolve().parents[3] / "eval" / "failures"

#: Timestamped stems (``20260712T131902Z``) and ``latest`` are ALIASES of a model-named run.
_ALIAS_STEM = re.compile(r"^\d{8}T\d{6}Z$")


@dataclass(frozen=True, slots=True)
class SweepRun:
    """One run of the sweep: its facts, its verdicts, and WHO judged them, when.

    ``verdicts`` uses the harness's own key (``eval/ratchet.py::_key``,
    ``"<case_id>|<language>"``) so the floor and the run stay joinable without invention.
    The provenance trio (``regraded_at``, the criteria shas, the blind runs) is carried
    verbatim from the report: a re-grade changes the verdicts without changing ``run_at``,
    and a screen that shows only ``run_at`` cannot say the numbers moved today.
    """

    id: str
    model: str | None
    run_at: str | None
    catalogue_version: str | None
    summary: dict[str, object]
    cost: dict[str, object] | None
    duration_ms: float | None
    output_tokens: int
    verdicts: dict[str, bool]
    regraded_at: str | None = None
    regrade_note: str | None = None
    grader_criteria_sha: str | None = None
    grader_criteria_sha_partial: str | None = None
    grader_blind_runs: list[str] = field(default_factory=list)


def catalogue_version_of(ids: Iterable[str]) -> str:
    """The catalogue's version — mirror of ``eval/runner.py::_catalogue_version``.

    ``{count}-{sha256(sorted ids joined by newline)[:8]}``. Both sides sort ASCII ids, so
    both sides agree; ``test_eval_sweep_api`` pins this mirror to the stamp the committed
    reports actually carry, which is what keeps two implementations from becoming two answers.
    """
    sorted_ids = sorted(ids)
    digest = sha256("\n".join(sorted_ids).encode("utf-8")).hexdigest()[:8]
    return f"{len(sorted_ids)}-{digest}"


def _optional_str(value: object) -> str | None:
    """A non-empty string, or ``None`` — never the *text* of a missing value."""
    return value if isinstance(value, str) and value else None


def _str_list(value: object) -> list[str]:
    """The strings in a list, from an untrusted payload — never the text of a non-list."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _read_json(path: Path) -> dict[str, object] | None:
    """One JSON object from disk, or ``None`` — a malformed file is not a report."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _to_run(file_id: str, doc: dict[str, object]) -> SweepRun | None:
    """Build a :class:`SweepRun` from one report dict, or ``None`` if it is not a run."""
    summary = doc.get("summary")
    results = doc.get("results")
    if not isinstance(summary, dict) or not isinstance(results, list):
        return None

    verdicts: dict[str, bool] = {}
    duration_total = 0.0
    duration_seen = False
    for row in results:
        if not isinstance(row, dict):
            continue
        case_id, language, passed = row.get("case_id"), row.get("language"), row.get("passed")
        if isinstance(case_id, str) and isinstance(language, str) and isinstance(passed, bool):
            verdicts[f"{case_id}|{language}"] = passed
        duration = row.get("duration_ms")
        if isinstance(duration, int | float):
            duration_total += float(duration)
            duration_seen = True

    cost = doc.get("cost") if isinstance(doc.get("cost"), dict) else None
    output_tokens = 0
    if isinstance(cost, dict):
        raw_tokens = cost.get("output_tokens")
        if isinstance(raw_tokens, int | float):
            output_tokens = int(raw_tokens)

    return SweepRun(
        id=file_id,
        model=_optional_str(doc.get("model")),
        run_at=_optional_str(doc.get("run_at")),
        catalogue_version=_optional_str(doc.get("catalogue_version")),
        summary={str(k): v for k, v in summary.items()},
        cost={str(k): v for k, v in cost.items()} if isinstance(cost, dict) else None,
        duration_ms=duration_total if duration_seen else None,
        output_tokens=output_tokens,
        verdicts=verdicts,
        regraded_at=_optional_str(doc.get("regraded_at")),
        regrade_note=_optional_str(doc.get("regrade_note")),
        grader_criteria_sha=_optional_str(doc.get("grader_criteria_sha")),
        grader_criteria_sha_partial=_optional_str(doc.get("grader_criteria_sha_partial")),
        grader_blind_runs=_str_list(doc.get("grader_criteria_unstampable")),
    )


def _dedupe_aliases(loaded: list[tuple[str, SweepRun]]) -> list[SweepRun]:
    """One run per sampling event — the directory holds each run up to three times.

    A run appears as a timestamped copy, a model-named copy and ``latest.json``. They are
    ALIASES, not runs: counting them would report a three-model sweep as seven. Deduplicated
    by ``run_at``; the model-named file wins because its name is the only one an operator
    can read in a URL.
    """
    by_run_at: dict[str, SweepRun] = {}
    for file_id, run in sorted(loaded, key=lambda item: item[0]):
        key = run.run_at or file_id
        existing = by_run_at.get(key)
        existing_is_alias = existing is not None and (
            existing.id == "latest" or _ALIAS_STEM.fullmatch(existing.id) is not None
        )
        incoming_is_alias = file_id == "latest" or _ALIAS_STEM.fullmatch(file_id) is not None
        if existing is None or (existing_is_alias and not incoming_is_alias):
            by_run_at[key] = run
    return sorted(by_run_at.values(), key=lambda r: r.run_at or "", reverse=True)


def _case_schema_fields(schema_raw: dict[str, object] | None) -> list[str]:
    """The fields a case may declare (``_schema.json`` properties), or an honest empty."""
    if not isinstance(schema_raw, dict):
        return []
    properties = schema_raw.get("properties")
    return sorted(properties.keys()) if isinstance(properties, dict) else []


def assemble_sweep(
    reports: list[tuple[str, dict[str, object]]],
    floor_raw: dict[str, object] | None,
    power_raw: dict[str, object] | None,
    power_error: str | None,
    cases: list[dict[str, object]],
    schema_raw: dict[str, object] | None,
) -> dict[str, object]:
    """Assemble the sweep payload from already-loaded artefacts — pure, unit-testable.

    The référentiel is the newest run's ``catalogue_version``; runs stamped otherwise are
    held apart in ``off_referential`` rather than averaged in — their numbers are not
    comparable, and merging them would be exactly the "delta without its référentiel" the
    evaluations screen exists to refuse.
    """
    parsed = [(file_id, run) for file_id, doc in reports if (run := _to_run(file_id, doc))]
    runs = _dedupe_aliases(parsed)

    referential = runs[0].catalogue_version if runs else None
    on_ref = [r for r in runs if r.catalogue_version == referential]
    off_ref = [r for r in runs if r.catalogue_version != referential]

    case_ids = [cid for case in cases if isinstance(cid := case.get("id"), str)]
    current_version = catalogue_version_of(case_ids) if case_ids else None

    return {
        "catalogue_version": referential,
        "current_catalogue_version": current_version,
        "runs": [asdict(r) for r in on_ref],
        "off_referential": [asdict(r) for r in off_ref],
        "floor": floor_raw,
        "power": power_raw,
        "power_error": power_error,
        "catalogue": cases,
        "case_schema_fields": _case_schema_fields(schema_raw),
        "newest_run_at": runs[0].run_at if runs else None,
    }


def _load_reports() -> list[tuple[str, dict[str, object]]]:
    if not SWEEP_DIR.is_dir():
        return []
    out: list[tuple[str, dict[str, object]]] = []
    for path in sorted(SWEEP_DIR.glob("*.json")):
        doc = _read_json(path)
        if doc is not None:
            out.append((path.stem, doc))
    return out


def _load_catalogue() -> list[dict[str, object]]:
    if not FAILURES_DIR.is_dir():
        return []
    cases: list[dict[str, object]] = []
    for path in sorted(FAILURES_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        doc = _read_json(path)
        if doc is not None:
            cases.append(doc)
    return cases


def compute_eval_sweep() -> dict[str, object]:
    """Read the artefacts and assemble the payload (the route's one call)."""
    power_raw: dict[str, object] | None = None
    power_error: str | None = None
    if CLASSIFICATION.exists():
        power_raw = _read_json(CLASSIFICATION)
        if power_raw is None:
            # The artefact EXISTS and cannot be read. "Nobody has measured this" and "it was
            # measured and I cannot read it" are different facts (ADR 0026); the second one
            # travels as a reason, never as an absence.
            power_error = f"{CLASSIFICATION.name} exists but is not readable JSON"

    return assemble_sweep(
        reports=_load_reports(),
        floor_raw=_read_json(NULL_BASELINE) if NULL_BASELINE.exists() else None,
        power_raw=power_raw,
        power_error=power_error,
        cases=_load_catalogue(),
        schema_raw=_read_json(FAILURES_DIR / "_schema.json"),
    )


def load_run_document(run_id: str) -> dict[str, object] | None:
    """The COMPLETE report of one run — all results, responses included.

    What the operator-gated blocks need whole: the failure synthesis groups every failed
    result of the selected run, and grouping over a redacted list would be a weakness map
    with the weaknesses removed. Same resolution rule as :func:`load_case_result` — the id
    is matched against the stems the directory holds, never joined onto a path.
    """
    known = {path.stem: path for path in SWEEP_DIR.glob("*.json")} if SWEEP_DIR.is_dir() else {}
    path = known.get(run_id)
    doc = _read_json(path) if path is not None else None
    return doc if doc is not None and _to_run(run_id, doc) is not None else None


def load_case_result(run_id: str, case_id: str, language: str) -> dict[str, object] | None:
    """The FULL record of one (run, case, language) — the evidence behind one verdict.

    ``run_id`` arrives from a query string, so it is resolved against the stems the sweep
    directory actually holds instead of being joined onto a path: a
    ``?run_id=../../etc/passwd`` never reaches ``read_text``. Returns ``None`` for an
    unknown run, case or language — the route's 404, never an empty record.

    This is the one surface that carries ``final_response`` (the model's real words), which
    is why the route holding it requires a bearer while the aggregates above do not
    (ADR 0009: scores are showcase, weakness maps are operator material).
    """
    known = {path.stem: path for path in SWEEP_DIR.glob("*.json")} if SWEEP_DIR.is_dir() else {}
    path = known.get(run_id)
    doc = _read_json(path) if path is not None else None
    run = _to_run(run_id, doc) if doc is not None else None
    results = doc.get("results") if doc is not None else None
    if run is None or not isinstance(results, list):
        return None
    for row in results:
        if (
            isinstance(row, dict)
            and row.get("case_id") == case_id
            and row.get("language") == language
        ):
            meta = asdict(run)
            meta.pop("verdicts", None)  # the caller has them; 174 booleans add nothing here
            return {"run": meta, "result": row}
    return None
