"""Calibrate the input-side PAN mask over the real conversation transcript.

The merge gate of docs/design/pii-input-redaction.md §5.1: before the mask is
allowed anywhere near user text, it replays over **every persisted
conversation message** (all environment schemas of the local Postgres) and
produces a reviewable report:

* ``masked`` — every span the mask would rewrite, with a context excerpt, for
  manual span-by-span review (the zero-false-positive proof);
* ``unmasked_candidates`` — every 13-19 digit run the broad candidate pattern
  sees that the gates then *decline* (Luhn failure, IBAN context, leading
  zero), bucketed by reason, so the must-not-mask population is reviewable
  line by line rather than asserted in the abstract.

It also freezes deduplicated fixtures into ``tests/unit/fixtures/pan_corpus.json``
so the reviewed behaviour is pinned by the unit suite from then on
(``tests/unit/test_pan_corpus_fixtures.py``).

Run::

    uv run python -m scripts.calibrate_pan_mask
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from tessera.guard.redaction import _PAN_INPUT_CANDIDATE, _iban_context, _luhn_valid, mask_pan
from tessera.settings import get_settings

_EXCERPT_RADIUS = 60
_REPORT_PATH = Path("eval/reports/local/pan_input_calibration.json")
_FIXTURES_PATH = Path("tests/unit/fixtures/pan_corpus.json")


class MaskedSpan(TypedDict):
    """One rewrite the mask performed, with review context."""

    schema: str
    row_id: int
    role: str
    span: str
    masked_as: str
    excerpt: str


class UnmaskedCandidate(TypedDict):
    """One card-shaped digit run the gates declined, with the reason."""

    schema: str
    row_id: int
    role: str
    run: str
    reason: str
    excerpt: str


def _excerpt(text: str, start: int, end: int) -> str:
    lo = max(0, start - _EXCERPT_RADIUS)
    hi = min(len(text), end + _EXCERPT_RADIUS)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi]}{suffix}".replace("\n", " ")


def _decline_reason(text: str, start: int, digits: str) -> str:
    if _iban_context(text, start):
        return "iban_context"
    if digits.startswith("0"):
        return "leading_zero"
    if not _luhn_valid(digits):
        return "luhn_fail"
    return "masked"


def _scan_row(
    schema: str, row_id: int, role: str, content: str
) -> tuple[list[MaskedSpan], list[UnmaskedCandidate]]:
    """Classify every card-shaped candidate in one transcript row."""
    masked_spans: list[MaskedSpan] = []
    declined: list[UnmaskedCandidate] = []
    result = mask_pan(content)
    pos = 0
    while True:
        match = _PAN_INPUT_CANDIDATE.search(content, pos)
        if match is None:
            break
        start, end = match.span()
        digits = "".join(char for char in match.group(0) if char.isdigit())
        reason = _decline_reason(content, start, digits)
        if reason == "masked":
            masked_spans.append(
                MaskedSpan(
                    schema=schema,
                    row_id=row_id,
                    role=role,
                    span=match.group(0),
                    masked_as=f"XXXX XXXX XXXX {digits[-4:]}",
                    excerpt=_excerpt(content, start, end),
                )
            )
        else:
            declined.append(
                UnmaskedCandidate(
                    schema=schema,
                    row_id=row_id,
                    role=role,
                    run=match.group(0),
                    reason=reason,
                    excerpt=_excerpt(content, start, end),
                )
            )
        pos = end
    if masked_spans and not result.changed:  # pragma: no cover - coherence guard
        raise RuntimeError(f"scan/mask disagreement on {schema} row {row_id}")
    return masked_spans, declined


def _discover_schemas(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT n.nspname AS schema
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'conversation_messages' AND c.relkind = 'r'
        ORDER BY 1;
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def main() -> None:
    """Replay the mask over the whole transcript and write report + fixtures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=_REPORT_PATH)
    parser.add_argument("--fixtures", type=Path, default=_FIXTURES_PATH)
    args = parser.parse_args()

    dsn = str(get_settings().postgres.dsn)
    masked: list[MaskedSpan] = []
    declined: list[UnmaskedCandidate] = []
    per_schema: dict[str, dict[str, int]] = {}
    with psycopg.connect(dsn) as conn:
        schemas = _discover_schemas(conn)
        for schema in schemas:
            query = sql.SQL("SELECT id, role, content FROM {table} ORDER BY id;").format(
                table=sql.Identifier(schema, "conversation_messages")
            )
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                rows = cur.fetchall()
            user_rows = sum(1 for row in rows if row["role"] == "user")
            per_schema[schema] = {"rows": len(rows), "user_rows": user_rows}
            for row in rows:
                row_masked, row_declined = _scan_row(
                    schema, int(row["id"]), str(row["role"]), str(row["content"])
                )
                masked.extend(row_masked)
                declined.extend(row_declined)

    reasons: dict[str, int] = {}
    for item in declined:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "schemas": per_schema,
        "rows_scanned": sum(s["rows"] for s in per_schema.values()),
        "user_rows": sum(s["user_rows"] for s in per_schema.values()),
        "masked_count": len(masked),
        "declined_by_reason": reasons,
        "masked": masked,
        "unmasked_candidates": declined,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    # Freeze deduplicated fixtures: the reviewed corpus behaviour becomes a
    # permanent unit-suite assertion (mask exactly these, never those).
    masked_fixtures = sorted({(m["span"], m["masked_as"], m["excerpt"]) for m in masked})
    declined_fixtures = sorted({(d["run"], d["reason"], d["excerpt"]) for d in declined})
    fixtures = {
        "source": "scripts/calibrate_pan_mask.py — real-transcript replay",
        "generated_at": report["generated_at"],
        "rows_scanned": report["rows_scanned"],
        "user_rows": report["user_rows"],
        "masked": [
            {"span": span, "masked_as": masked_as, "excerpt": excerpt}
            for span, masked_as, excerpt in masked_fixtures
        ],
        "unmasked": [
            {"run": run, "reason": reason, "excerpt": excerpt}
            for run, reason, excerpt in declined_fixtures
        ],
    }
    args.fixtures.parent.mkdir(parents=True, exist_ok=True)
    args.fixtures.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n")

    print(f"schemas: {per_schema}")
    print(f"rows scanned: {report['rows_scanned']} (user: {report['user_rows']})")
    print(f"masked spans: {len(masked)}  |  declined: {reasons}")
    print(f"report: {args.report}")
    print(f"fixtures: {args.fixtures}")


if __name__ == "__main__":
    main()
