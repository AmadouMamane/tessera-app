"""Unit tests for the Historique (session history) payload assembler."""

from __future__ import annotations

from tessera.observability.agent_historique import _assemble
from tessera.observability.eval_data import CategoryStat, EvalSnapshot, SessionRow


def _session(case: str, lang: str, cat: str, *, passed: bool, dur: float) -> SessionRow:
    return SessionRow(
        case_id=case,
        language=lang,
        category=cat,
        title=f"Question {case}",
        passed=passed,
        needs_escalation=not passed,
        tools=("tool_a",) if passed else (),
        duration_ms=dur,
        input_tokens=100,
        output_tokens=50,
        response=f"Reponse pour {case}",
        started_at=f"2026-06-1{1 if passed else 2}T10:0{case[-1]}:00",
    )


def _snapshot() -> EvalSnapshot:
    sessions = (
        _session("c1", "fr", "prompt_injection", passed=True, dur=3000),
        _session("c2", "de", "prompt_injection", passed=False, dur=5000),
        _session("c3", "en", "pii_leak", passed=True, dur=2000),
        _session("c4", "fr", "pii_leak", passed=False, dur=4000),
    )
    cats = (
        CategoryStat(category="prompt_injection", total=2, passed=1),
        CategoryStat(category="pii_leak", total=2, passed=1),
    )
    return EvalSnapshot(
        model="llama3.2:3b",
        run_at="2026-06-12T10:00:00",
        catalogue_version="v1.0",
        total=4,
        passed=2,
        languages=(("fr", 2), ("de", 1), ("en", 1)),
        categories=cats,
        escalations=2,
        tool_invocations=2,
        sessions=sessions,
    )


def test_rows_carry_stable_keys_and_qa() -> None:
    payload = _assemble(_snapshot())
    table = payload["table"]
    assert table["total"] == 4  # type: ignore[index]
    rows = table["rows"]  # type: ignore[index]
    assert len(rows) == 4
    first = rows[0]
    # Stable keys for i18n-safe filtering + the detail panel.
    for key in ("category_key", "lang", "status_tone", "score_num", "question", "response"):
        assert key in first
    # Newest-first ordering (failed sessions are dated 06-12, after the passed 06-11).
    assert rows[0]["start_ts"] >= rows[-1]["start_ts"]


def test_status_and_score_tone_track_pass() -> None:
    rows = _assemble(_snapshot())["table"]["rows"]  # type: ignore[index]
    by_case = {r["sid"]: r for r in rows}
    passed = by_case["c1 / fr"]
    failed = by_case["c2 / de"]
    assert passed["status"] == "Réussie"
    assert passed["status_tone"] == "good"
    assert passed["score_num"] == 10
    assert failed["status"] == "Échec"
    assert failed["status_tone"] == "bad"
    assert failed["score_num"] == 0


def test_filter_options_are_localized_and_keyed() -> None:
    opts = _assemble(_snapshot())["filters"]["options"]  # type: ignore[index]
    lang_keys = {o["key"] for o in opts["lang"]}
    assert lang_keys == {"fr", "de", "en"}
    cat_keys = {o["key"] for o in opts["category"]}
    assert cat_keys == {"prompt_injection", "pii_leak"}
    status_keys = {o["key"] for o in opts["status"]}
    assert status_keys == {"good", "bad"}


def test_kpis_are_accented_and_real() -> None:
    kpis = {k["key"]: k for k in _assemble(_snapshot())["kpis"]}  # type: ignore[union-attr]
    assert kpis["messages"]["label"] == "Messages échangés"
    assert kpis["success"]["value"] == "50,0 %"
    assert kpis["answers"]["label"] == "Réponses générées"


def test_meta_and_detail_labels_present() -> None:
    payload = _assemble(_snapshot())
    assert payload["meta"]["model"] == "llama3.2:3b"  # type: ignore[index]
    labels = payload["detail_labels"]
    assert labels["tabs"][0] == "Résumé"  # type: ignore[index]
    assert "Échange" in labels["messages_title"]  # type: ignore[index]
