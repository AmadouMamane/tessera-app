"""Phase A spine reader over the current stores (ADR 0015 §Migration A).

This is the degraded ``local`` source: it reads the existing ``scores.jsonl`` /
``bundles.jsonl`` convenience stores and the tamper-evident guard ledger through the
existing store functions *unchanged*, so a snapshot signal is byte-parity with its route.
ADR 0015 §Migration D keeps a thin, clearly-labelled local reader like this for a
degraded-offline mode after the spine becomes the system of record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability import replay as replay_mod
from tessera.observability.eval.scores import persisted_scores, recent_scores

if TYPE_CHECKING:
    from tessera.observability.replay import ReplayBundle
    from tessera.observability.spine.scope import Scope

__all__ = ["CurrentStoresReader"]


class CurrentStoresReader:
    """Reads the current convenience stores + the tamper-evident audit ledger.

    Mirrors the route helpers exactly: ``persisted_scores`` when an as-of-T instant is
    set, the live ring otherwise; ``recent_bundles`` (which itself falls back to the
    durable store under ``at``); and the guard audit log filtered to guard entries.
    """

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Eval score rows for the scope (durable log as-of-T, else the live ring).

        ``agent`` + as-of-T are pushed into the store read; ``language`` / ``model`` are
        applied here (the rows carry both), so the same store read serves every language
        slice of the agent x time x language cube (ADR 0015 §Migration F).
        """
        rows = (
            persisted_scores(scope.at, scope.agent_id)
            if scope.at
            else recent_scores(scope.agent_id)
        )
        if scope.language is not None:
            rows = [r for r in rows if r.get("language") == scope.language]
        if scope.model is not None:
            rows = [r for r in rows if r.get("model") == scope.model]
        return rows

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Captured turn bundles for the scope (as-of-T + agent, then language / model)."""
        rows = replay_mod.recent_bundles(scope.at, scope.agent_id)
        if scope.language is not None:
            rows = [b for b in rows if b.language == scope.language]
        if scope.model is not None:
            rows = [b for b in rows if b.original_model == scope.model]
        return rows

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:  # noqa: ARG002
        """The whole guard audit ledger (scope filter is applied downstream by signals)."""
        return _read_audit_ledger()

    def gating_scores(self, scope: Scope) -> list[dict[str, object]]:
        """Release-gating rows from the report-file archive (the current gating store).

        Reads the env-aware report files (ADR 0014 layer 3) through the same pure
        report→rows mapping the Postgres write path uses, so the file view and the owned
        table serve one shape — the G4 parity precondition. Files are parsed once per
        ``(path, mtime)`` and cached (the archive is immutable timestamped files), so the
        hot path never re-parses megabytes of JSON per snapshot.
        """
        from tessera.observability._asof import occurred_before

        rows = [r for r in _gating_archive_rows() if occurred_before(r.get("scored_at"), scope.at)]
        if scope.agent_id is not None:
            rows = [r for r in rows if r.get("agent_id") == scope.agent_id]
        if scope.language is not None:
            rows = [r for r in rows if r.get("language") == scope.language]
        if scope.model is not None:
            rows = [r for r in rows if r.get("model") == scope.model]
        return rows


# (path, mtime_ns) → that file's gating rows. Archive files are immutable (timestamped
# names; only latest*.json is rewritten), so the cache is correct by construction and
# bounded by the number of report files.
_GATING_CACHE: dict[str, tuple[int, list[dict[str, object]]]] = {}


def _gating_archive_rows() -> list[dict[str, object]]:
    """Every gating row in the env's report archive, oldest→newest, mtime-cached."""
    import json

    from tessera.observability.eval.gating_scores import (
        gating_row_dict,
        gating_rows_from_report,
    )
    from tessera.observability.eval.report_paths import iter_report_files

    rows: list[dict[str, object]] = []
    seen_runs: set[str] = set()
    for path in sorted(iter_report_files()):
        try:
            stat_ns = path.stat().st_mtime_ns
        except OSError:
            # skip a report file that vanished/permission-flipped mid-scan — non-gating read (0015)
            continue
        key = str(path)
        cached = _GATING_CACHE.get(key)
        if cached is None or cached[0] != stat_ns:
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # Cache a corrupt gating report as empty (avoids re-reading it every scan) —
                # non-gating current-view read; the gate reads reports elsewhere (0015).
                _GATING_CACHE[key] = (stat_ns, [])
                continue
            parsed = (
                [gating_row_dict(r) for r in gating_rows_from_report(report)]
                if isinstance(report, dict)
                else []
            )
            _GATING_CACHE[key] = (stat_ns, parsed)
        file_rows = _GATING_CACHE[key][1]
        if not file_rows:
            continue
        run_id = str(file_rows[0].get("run_id"))
        if run_id in seen_runs:  # latest_<agent>.json duplicates its timestamped archive
            continue
        seen_runs.add(run_id)
        rows.extend(file_rows)
    rows.sort(key=lambda r: str(r.get("scored_at") or ""))
    return rows


def _read_audit_ledger() -> list[dict[str, object]]:
    """Guard-audit entries from the ACTIVE ledger source (§Amendment 3 cut switch).

    ``file`` (default) parses the flat journal exactly as the routes do; ``postgres``
    reads the promoted append-only table — the cut, only ever enabled after
    ``shadow_verify_ledger`` holds (never flip a ledger read before its chain verifies).
    Both return only ``type == tessera.guard.audit`` rows, unfiltered; downstream signals
    apply the scope filter via :mod:`tessera.observability.spine.adapters.ledger`.
    """
    import json

    from tessera.guard.ledger_store import ledger_source, load_ledger_payloads_of_type
    from tessera.settings import get_settings

    if ledger_source() == "postgres":
        import psycopg

        from tessera.observability.spine.adapters.base import SpineUnavailableError

        try:
            # Filtered in SQL rather than in Python. Be clear about what this is NOT: the
            # guard-audit rows are **94 % of the chain** (24 250 of 25 716, measured), so pushing
            # the type filter down saves ~6 % and this read still materialises the whole ledger
            # for practical purposes. It is the right SHAPE, not a fix. The cost fix is a bounded
            # read (a window, or pagination), and it is OWED — see the frozen offender list in
            # tests/unit/test_ledger_read_budget.py. A type filter is only cheap when the type is
            # rare, and this one is the ledger.
            return list(load_ledger_payloads_of_type("tessera.guard.audit"))
        except psycopg.Error as exc:
            msg = f"promoted ledger unreachable: {exc}"
            raise SpineUnavailableError(msg) from exc

    path = get_settings().guard.audit_file
    entries: list[dict[str, object]] = []
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                # skip a corrupt JSONL line while reading audit entries — non-gating read (0015)
                continue
            if isinstance(obj, dict) and obj.get("type") == "tessera.guard.audit":
                entries.append(obj)
    return entries
