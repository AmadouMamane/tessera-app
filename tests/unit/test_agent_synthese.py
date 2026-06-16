"""Unit tests for the Synthese dashboard payload assembler.

`agent_synthese._assemble` is exercised with a synthetic eval snapshot + a
synthetic transcript dict (the DB layer is abstracted by `_fetch_transcript`,
so no Postgres is needed here). Asserts the KPI strip, profile, language mix,
recent-conversation mapping, timeline ordering, alert tone and the wired CTA
hrefs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tessera.observability import agent_synthese as syn
from tessera.observability.eval_data import CategoryStat, EvalSnapshot, SessionRow

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _session(case_id: str, category: str, *, passed: bool, lang: str, ms: float) -> SessionRow:
    return SessionRow(
        case_id=case_id,
        language=lang,
        category=category,
        title=f"{case_id} title",
        passed=passed,
        needs_escalation=not passed,
        tools=("account_balance",) if not passed else (),
        duration_ms=ms,
        input_tokens=10,
        output_tokens=20,
        response="r",
        started_at=(NOW - timedelta(minutes=int(ms))).isoformat(),
    )


def _snap() -> EvalSnapshot:
    sessions = [
        _session("01", "pii_leak", passed=False, lang="fr", ms=1000),
        _session("02", "pii_leak", passed=True, lang="de", ms=2000),
        _session("03", "hallucination", passed=True, lang="en", ms=3000),
        _session("04", "hallucination", passed=False, lang="fr", ms=4000),
    ]
    return EvalSnapshot(
        model="llama3.2:3b",
        run_at="2026-06-16T07:51:00+00:00",
        catalogue_version="Failure Catalogue v1",
        total=4,
        passed=2,
        languages=(("fr", 2), ("de", 1), ("en", 1)),
        categories=(
            CategoryStat(category="pii_leak", total=2, passed=1),
            CategoryStat(category="hallucination", total=2, passed=1),
        ),
        escalations=2,
        tool_invocations=2,
        sessions=tuple(sessions),
    )


def _tx() -> dict[str, object]:
    d1 = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)
    d2 = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    return {
        "totals": {"convs": 1008, "msgs": 2108, "turns": 1054, "last_at": d2},
        "daily": [
            {"day": d1, "convs": 4, "msgs": 8, "turns": 4},
            {"day": d2, "convs": 5, "msgs": 10, "turns": 5},
        ],
        "recent_convs": [
            {"conversation_id": "a", "ended": d2, "turns": 3, "first_q": "Quel est mon solde ?",
             "escalated": True},
            {"conversation_id": "b", "ended": d1, "turns": 1, "first_q": "Bonjour",
             "escalated": False},
        ],
        "recent_msgs": [
            {"role": "assistant", "content": "ok", "created_at": d2},
            {"role": "user", "content": "hi", "created_at": d2},
        ],
        "newest_doc": {"locator": "Catalogue 2026", "inserted_at": d1},
        "doc_count": 238,
        "cat_count": 15,
    }


def test_assemble_is_real_and_well_formed() -> None:
    payload = syn._assemble(_snap(), _tx(), chain_ok=True, now=NOW)

    # KPI strip: 7 tiles, all real values from the two sources.
    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert set(kpis) == {
        "conversations", "turns", "resolution", "latency", "errors", "sources", "messages",
    }
    assert kpis["conversations"]["value"] == "1008"
    assert kpis["turns"]["value"] == "1054"
    assert kpis["messages"]["value"] == "2108"
    assert kpis["sources"]["value"] == "15"
    assert "238 fragments" in kpis["sources"]["delta"]
    # resolution = 2/4 = 50,0%
    assert kpis["resolution"]["value"] == "50,0%"
    # transcript sparkline is the real daily series
    assert kpis["conversations"]["series"] == [4, 5]
    # last-vs-previous bucket delta: (5-4)/4 = +25%
    assert kpis["conversations"]["delta"] == "+25% vs jour precedent"


def test_profile_and_language_mix_are_sourced() -> None:
    payload = syn._assemble(_snap(), _tx(), chain_ok=True, now=NOW)
    fields = {f["label"]: f["value"] for f in payload["profile"]["fields"]}  # type: ignore[union-attr]
    assert fields["Modele principal"] == "llama3.2:3b"
    assert fields["Connaissances"] == "15 sources / 238 fragments"
    assert fields["Conversations"] == "1008"
    assert payload["profile"]["ctaHref"] == "/agent/configurations"  # type: ignore[index]

    # Channels relabelled to the real eval language mix.
    chan = payload["channels"]
    assert "langue" in chan["title"].lower()  # type: ignore[index]
    labels = [i["label"] for i in chan["items"]]  # type: ignore[index]
    assert "Francais" in labels and "Allemand" in labels


def test_conversations_timeline_alerts_and_ctas() -> None:
    payload = syn._assemble(_snap(), _tx(), chain_ok=False, now=NOW)

    rows = payload["conversations"]["rows"]  # type: ignore[index]
    assert rows[0]["status"] == "escalade"  # escalated heuristic
    assert rows[0]["user"] == "3 echanges"
    assert rows[1]["user"] == "1 echange"  # singular

    # Timeline events are sorted newest-first: the latest transcript activity
    # (15/06) leads, ahead of the older repo file mtimes.
    labels = [r["label"] for r in payload["timeline"]["rows"]]  # type: ignore[index]
    assert labels[0] == "Derniere conversation"
    assert "Prompts mis a jour" in labels

    # Audit-chain alert reflects the broken chain.
    chain_alert = next(
        i for i in payload["alerts"]["items"] if i["label"] == "Chaine d'audit"  # type: ignore[index]
    )
    assert chain_alert["value"] == "Rompue" and chain_alert["tone"] == "crit"

    # Quick-config items are real navigable links.
    hrefs = {i["href"] for i in payload["quick_config"]["items"]}  # type: ignore[index]
    assert "/agent/connaissances" in hrefs and "/agent/garde-fous" in hrefs


def test_chain_ok_alert_is_good() -> None:
    payload = syn._assemble(_snap(), _tx(), chain_ok=True, now=NOW)
    chain_alert = next(
        i for i in payload["alerts"]["items"] if i["label"] == "Chaine d'audit"  # type: ignore[index]
    )
    assert chain_alert["value"] == "Intacte" and chain_alert["tone"] == "good"
