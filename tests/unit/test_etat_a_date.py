"""Unit tests for the point-in-time reconstruction assembler.

`etat_a_date._assemble` is exercised with synthetic pgvector rows + an audit
aggregate + a stub policy + a config context + an anchored original response (no
DB / no file I/O). Asserts the as-of windowing of knowledge accessibility, the
real "diff vs current state" lines, the original-response card and the snapshot
record.
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


def _ctx(audit_total: int = 15000, prompt_after: bool = False) -> ead._Context:
    # prompt_mtime after T iff prompt_after, to drive the prompt diff line.
    prompt_mtime = datetime(2026, 6, 14, 9, 0, tzinfo=UTC) if prompt_after else datetime(
        2026, 6, 3, 9, 0, tzinfo=UTC
    )
    return ead._Context(
        model="llama3.2:3b",
        temperature=0.3,
        profile="Standard souverain",
        prompt_mtime=prompt_mtime,
        policy_mtime=datetime(2026, 5, 29, 11, 34, tzinfo=UTC),
        run_dt=datetime(2026, 6, 16, 5, 51, tzinfo=UTC),
        catalogue="Catalogue v1",
        audit_total=audit_total,
    )


def _row(cat: str, lang: str, ins: datetime) -> dict[str, Any]:
    return {
        "source": f"{cat}.pdf",
        "language": lang,
        "metadata": {"category": cat},
        "inserted_at": ins,
    }


def _rows() -> list[dict[str, Any]]:
    early = datetime(2026, 5, 28, 22, 0, tzinfo=UTC)
    late = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)  # only accessible for T >= 14 June
    return [
        _row("dora", "fr", early),
        _row("dora", "en", early),
        _row("gdpr", "fr", early),
        _row("comptes", "fr", late),
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


def _original() -> dict[str, Any]:
    return {
        "answer": "Le financement en 4 fois est possible sous reserve.",
        "ts": datetime(2026, 6, 10, 16, 18, tzinfo=UTC),
        "conv": "95ab9122-0000-0000-0000-000000000000",
        "question": "Puis-je financer mon achat en 4 fois ?",
    }


def _assemble(audit_total: int = 15000) -> dict[str, object]:
    return ead._assemble(
        _rows(),
        _audit(),
        _StubPolicy(),
        _ctx(audit_total=audit_total),
        _original(),
        T_MID,
        now=NOW,
    )


def test_knowledge_windowing_and_table_at_t() -> None:
    payload = _assemble()
    table = {r["key"]: r for r in payload["table"]["rows"]}  # type: ignore[index]
    assert table["dora"]["status"] == "accessible"
    assert table["comptes"]["status"] == "pending"  # 14 June ingest > T (12 June)
    assert table["comptes"]["status_label"] == "Pas encore indexée"
    # the table carries the normative columns
    assert "version" in table["dora"] and "accessible_until" in table["dora"]


def test_guardrails_diff_is_a_real_two_point_count() -> None:
    # audit_total (now) = 15 000 ; decisions at T = 100 -> 14 900 logged after T.
    payload = _assemble(audit_total=15_000)
    gr = payload["guardrails"]
    rows = {r["label"]: r["value"] for r in gr["rows"]}  # type: ignore[index]
    assert rows["Bundle de politiques"] == "Guardrails Banking v2"
    diff = gr["diff"]  # type: ignore[index]
    changed = next(d for d in diff if "14 900 décisions" in d["text"])
    assert changed["kind"] == "changed"


def test_prompt_diff_reflects_mtime_vs_t() -> None:
    after = ead._assemble(
        _rows(), _audit(), _StubPolicy(), _ctx(prompt_after=True), _original(), T_MID, now=NOW
    )
    assert any(  # type: ignore[index]
        d["kind"] == "changed" and "modifié après T" in d["text"]
        for d in after["prompt_model"]["diff"]
    )
    before = _assemble()
    assert any(  # type: ignore[index]
        d["kind"] == "unchanged" and "inchangé depuis T" in d["text"]
        for d in before["prompt_model"]["diff"]
    )


def test_original_card_is_the_real_transcript_turn() -> None:
    o = _assemble()["original"]
    assert o["available"] is True  # type: ignore[index]
    assert o["question"].startswith("Puis-je financer")  # type: ignore[index]
    # session = short conversation id; ref_code derived from the answer timestamp
    assert o["session"] == "SES-95AB9122"  # type: ignore[index]
    assert o["ref_code"] == "RES-2026-06-10-1818"  # type: ignore[index]


def test_no_original_when_absent() -> None:
    payload = ead._assemble(
        _rows(), _audit(), _StubPolicy(), _ctx(), None, T_MID, now=NOW
    )
    assert payload["original"]["available"] is False  # type: ignore[index]


def test_reconstructed_and_integrity_ids() -> None:
    payload = _assemble()
    assert payload["reconstructed"]["snapshot_id"] == "SNAP-2026-06-12-0200"  # type: ignore[index]
    assert payload["integrity"]["test_query"] == "2/3 sources"  # type: ignore[index]


def test_snapshot_record_captures_headline_figures() -> None:
    rec = ead._snapshot_record(_rows(), _audit(decisions=15484), T_MID, NOW)
    assert rec["ref_code"] == "RES-2026-06-12-0200"
    assert "2 sources" in rec["summary"]
    assert "15 484 decisions guard" in rec["summary"]
    assert len(rec["id"]) == 12
