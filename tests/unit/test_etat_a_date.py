"""Unit tests for the point-in-time reconstruction assembler.

`etat_a_date._assemble` is exercised with synthetic pgvector rows + an audit
aggregate + a stub policy (no DB / no file I/O). Asserts the as-of windowing of
both knowledge accessibility (chunks indexed at or before T) and the guard
figures, plus the table/integrity/timeline/policies shaping.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tessera.observability import etat_a_date as ead

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
T_MID = "2026-06-12T00:00:00+00:00"


@dataclass
class _StubPolicy:
    version: int = 2
    prompt_injection_deny: tuple[str, ...] = ("a", "b", "c")
    pii_patterns: tuple[str, ...] = ("x", "y")
    tools: tuple[str, ...] = ("t1", "t2", "t3", "t4", "t5")


def _row(cat: str, lang: str, ins: datetime) -> dict[str, Any]:
    return {
        "source": f"{cat}.pdf",
        "language": lang,
        "metadata": {"category": cat},
        "inserted_at": ins,
    }


def _rows() -> list[dict[str, Any]]:
    early = datetime(2026, 5, 28, 22, 0, tzinfo=UTC)  # ingested before any T tested
    late = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)  # ingested AFTER T_MID
    return [
        _row("dora", "fr", early),
        _row("dora", "en", early),
        _row("gdpr", "fr", early),
        _row("comptes", "fr", late),  # only accessible for T >= 14 June
    ]


def _audit(decisions: int = 100, blocked: int = 90) -> ead._AuditAsOf:
    scan = ead._AuditAsOf()
    scan.decisions = decisions
    scan.blocked = blocked
    scan.allowed = decisions - blocked
    scan.rules = {"prompt_injection.deny_patterns", "tool.account_balance.allow"}
    scan.first_at = datetime(2026, 6, 10, 15, 46, tzinfo=UTC)
    scan.last_at = datetime(2026, 6, 11, 9, 0, tzinfo=UTC)
    return scan


def test_knowledge_windowing_at_t() -> None:
    # At T = 12 June: the 'late' (14 June) comptes source is not yet accessible.
    payload = ead._assemble(_rows(), _audit(), _StubPolicy(), T_MID, now=NOW)
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["sources"] == "2"  # dora + gdpr (comptes not yet indexed)
    assert kpis["documents"] == "3"  # 3 early chunks
    assert kpis["decisions"] == "100"
    assert kpis["blocked"] == "90"

    table = {r["key"]: r for r in payload["table"]["rows"]}  # type: ignore[index]
    assert table["dora"]["status"] == "accessible"
    assert table["comptes"]["status"] == "pending"
    assert table["comptes"]["status_label"] == "Pas encore indexee"


def test_full_window_when_t_is_after_all_ingests() -> None:
    payload = ead._assemble(_rows(), _audit(), _StubPolicy(), "2026-06-15T00:00:00+00:00", now=NOW)
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["sources"] == "3"  # all three sources now indexed
    assert kpis["documents"] == "4"
    assert kpis["coverage"] == "100 %"


def test_live_means_everything_accessible() -> None:
    payload = ead._assemble(_rows(), _audit(), _StubPolicy(), None, now=NOW)
    assert payload["meta"]["as_of"] is None  # type: ignore[index]
    assert payload["meta"]["as_of_label"] == "Maintenant (live)"  # type: ignore[index]
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["sources"] == "3"


def test_policies_and_ref_code_are_sourced() -> None:
    payload = ead._assemble(_rows(), _audit(), _StubPolicy(), T_MID, now=NOW)
    pol = {r["label"]: r["value"] for r in payload["policies"]["rows"]}  # type: ignore[index]
    assert pol["Garde-fous"] == "v2"
    assert pol["Motifs d'injection bloques"] == "3"
    assert pol["Motifs PII surveilles"] == "2"
    assert pol["Outils sous controle"] == "5"
    assert pol["Regles declenchees jusqu'a T"] == "2"
    assert payload["meta"]["ref_code"] == "RES-2026-06-12-0200"  # type: ignore[index]


def test_timeline_is_newest_first_and_bounded() -> None:
    payload = ead._assemble(_rows(), _audit(), _StubPolicy(), "2026-06-15T00:00:00+00:00", now=NOW)
    rows = payload["timeline"]["rows"]  # type: ignore[index]
    assert len(rows) <= ead._MAX_TIMELINE
    assert any("guard" in r["label"].lower() for r in rows)


def test_snapshot_record_captures_headline_figures() -> None:
    rec = ead._snapshot_record(_rows(), _audit(decisions=15484, blocked=15187), T_MID, NOW)
    assert rec["as_of"] == "2026-06-12T00:00:00+00:00"
    assert rec["ref_code"] == "RES-2026-06-12-0200"
    # at T = 12 June only the 3 early chunks (2 sources) are accessible.
    assert "2 sources" in rec["summary"]
    assert "3 fragments" in rec["summary"]
    assert "15 484 decisions guard" in rec["summary"]
    assert len(rec["id"]) == 12


def test_snapshots_section_renders_saved_records() -> None:
    saved = [
        {
            "id": "abc123",
            "saved_at": "2026-06-16T10:00:00+00:00",
            "as_of": "2026-06-12T00:00:00+00:00",
            "as_of_label": "12/06/2026, 02:00",
            "ref_code": "RES-2026-06-12-0200",
            "summary": "2 sources - 3 fragments - 100 decisions guard",
        }
    ]
    payload = ead._assemble(_rows(), _audit(), _StubPolicy(), T_MID, saved, now=NOW)
    rows = payload["snapshots"]["rows"]  # type: ignore[index]
    assert len(rows) == 1
    assert rows[0]["ref_code"] == "RES-2026-06-12-0200"
    assert rows[0]["saved_label"] != "-"  # saved_at parsed and formatted
