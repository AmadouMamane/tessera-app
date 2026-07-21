"""Unit tests for the Synthese dashboard payload assembler.

``agent_synthese._assemble`` is exercised with the governed registry agent + a
synthetic transcript dict + a synthetic S1-journal scan (the DB and the file
journal are abstracted by ``_fetch_transcript`` / ``_scan_journal``, so no
Postgres or audit file is needed here). The Synthese is **operational** (events
only): it asserts the 7-KPI strip, the honest empty states (CSAT / users), the
operational resolution rate, the routing-motive distribution, the AT-01 activity
feed, the operational alert thresholds and the wired CTA hrefs.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import pytest

from tessera.agent.registry import get_agent
from tessera.observability import agent_synthese as syn

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
AGENT = get_agent("support-client")


def _cfg() -> dict[str, object]:
    return {
        "name": "Support Client",
        "description": "SAV bancaire.",
        "owner": "Équipe Support",
        "timezone": "Europe/Paris",
        "default_language": "Français",
    }


def _tx() -> dict[str, object]:
    d1 = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)
    d2 = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    return {
        "totals": {
            "convs": 1008,
            "msgs": 2108,
            "turns": 1054,
            "answers": 1050,
            "escal_convs": 134,
            "lat_ms": 2340.0,
            "last_at": d2,
        },
        "daily": [
            {"day": d1, "convs": 4, "escal_convs": 1, "turns": 4, "lat_ms": 2000.0},
            {"day": d2, "convs": 5, "escal_convs": 0, "turns": 5, "lat_ms": 1800.0},
        ],
        "recent_convs": [
            {
                "conversation_id": "a",
                "ended": d2,
                "turns": 3,
                "first_q": "Quel est mon solde ?",
                "escalated": True,
            },
            {
                "conversation_id": "b",
                "ended": d1,
                "turns": 1,
                "first_q": "Bonjour",
                "escalated": False,
            },
        ],
        "recent_msgs": [
            {"role": "assistant", "content": "ok", "latency_ms": 1840.0, "created_at": d2},
            {"role": "user", "content": "hi", "latency_ms": None, "created_at": d2},
        ],
        "doc_count": 238,
        "cat_count": 15,
    }


def _journal(in_: int = 0, out: int = 0) -> dict[str, object]:
    return {
        "in": in_,
        "out": out,
        "routing": Counter({"stay": 3, "intent": 1}),
        "events": [
            {
                "when": datetime(2026, 6, 15, 9, 1, tzinfo=UTC),
                "label": "Conversation transférée",
                "detail": "Vers onboarding",
                "kind": "warn",
                "badge": "Handoff sortant",
            }
        ],
    }


def test_kpis_are_operational_with_honest_empty_states() -> None:
    payload = syn._assemble(AGENT, _cfg(), _tx(), _journal(in_=2, out=3), chain_ok=True, now=NOW)

    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert set(kpis) == {
        "conversations",
        "turns",
        "users",
        "resolution",
        "satisfaction",
        "latency",
        "handoffs",
    }
    # French-grouped integer counts.
    assert kpis["conversations"]["value"] == "1 008"
    assert kpis["turns"]["value"] == "1 054"
    # Both are real-source KPIs now (users via ADR 0040, CSAT via ADR 0041) and read "—"
    # here only because this fixture carries no subject_id and no votes.
    assert kpis["users"]["value"] == "—"
    assert kpis["satisfaction"]["value"] == "—"
    assert "aucun avis" in kpis["satisfaction"]["delta"]
    # Operational resolution = (1008-134)/1008 = 86,7%.
    assert kpis["resolution"]["value"] == "86,7%"
    # Latency from the transcript's measured latency_ms.
    assert kpis["latency"]["value"] == "2,3 s"
    # Handoffs total + breakdown from the S1 journal.
    assert kpis["handoffs"]["value"] == "5"
    assert kpis["handoffs"]["delta"] == "2 entrants / 3 sortants"
    # Conversations sparkline is the real daily series + "vs hier" delta.
    assert kpis["conversations"]["series"] == [4, 5]
    assert kpis["conversations"]["delta"] == "+25% vs hier"


def test_context_capabilities_and_repartition_are_sourced() -> None:
    payload = syn._assemble(AGENT, _cfg(), _tx(), _journal(), chain_ok=True, now=NOW)

    ctx = payload["context"]
    assert ctx["name"] == "Support Client"  # type: ignore[index]
    assert ctx["agentId"] == "support-client"  # type: ignore[index]
    fields = {f["label"]: f["value"] for f in ctx["fields"]}  # type: ignore[index]
    assert fields["Modèle principal"] == AGENT.model
    assert fields["Propriétaire"] == "Équipe Support"

    # Capabilities come from the agent's governed tool bindings (registry).
    caps = payload["capabilities"]["items"]  # type: ignore[index]
    assert "Consultation de solde" in caps and "Blocage de carte" in caps

    # Répartition is by routing motive (real S1 events): stay 3 / intent 1 -> 75 / 25.
    rep = payload["repartition"]
    assert rep["subtitle"] == "Par motif de routage"  # type: ignore[index]
    items = {i["label"]: i["pct"] for i in rep["items"]}  # type: ignore[index]
    assert items["Continuité de session"] == 75
    assert items["Changement d'intention"] == 25


def test_activity_feed_merges_transcript_and_journal_newest_first() -> None:
    payload = syn._assemble(AGENT, _cfg(), _tx(), _journal(out=1), chain_ok=True, now=NOW)
    rows = payload["activity"]["rows"]  # type: ignore[index]
    badges = [r["badge"] for r in rows]
    assert "Handoff sortant" in badges and "Réponse" in badges
    # The assistant response carries its real measured latency.
    resp = next(r for r in rows if r["badge"] == "Réponse")
    assert "1,8 s" in resp["detail"]


def test_alerts_use_real_thresholds() -> None:
    # Below thresholds -> no operational alert.
    quiet = syn._assemble(AGENT, _cfg(), _tx(), _journal(out=1), chain_ok=True, now=NOW)
    assert quiet["opAlerts"]["items"] == []  # type: ignore[index]

    # Broken chain + many outgoing handoffs -> two alerts.
    loud = syn._assemble(AGENT, _cfg(), _tx(), _journal(out=99), chain_ok=False, now=NOW)
    labels = [i["label"] for i in loud["opAlerts"]["items"]]  # type: ignore[index]
    assert "Handoffs sortants élevés" in labels
    assert "Chaîne d'audit rompue" in labels


def test_quick_access_and_meta_are_wired() -> None:
    payload = syn._assemble(AGENT, _cfg(), _tx(), _journal(), chain_ok=True, now=NOW)
    hrefs = {i["href"] for i in payload["quickAccess"]["items"]}  # type: ignore[index]
    assert "/agents/support-client/connaissances" in hrefs
    assert "/surveiller" in hrefs
    assert payload["meta"]["replayAt"] == "État à date"  # type: ignore[index]


def test_period_label_reflects_the_window() -> None:
    cases = [(7, "7 derniers jours"), (1, "24 dernières heures"), (None, "Tout l'historique")]
    for days, label in cases:
        payload = syn._assemble(
            AGENT, _cfg(), _tx(), _journal(), chain_ok=True, period_days=days, now=NOW
        )
        assert payload["meta"]["period"] == label  # type: ignore[index]


def test_users_kpi_counts_distinct_subjects_from_real_traffic() -> None:
    # ADR 0040: "Utilisateurs servis" is a real count(DISTINCT subject_id), not a stub.
    tx = _tx()
    tx["totals"]["subjects"] = 7  # type: ignore[index]
    payload = syn._assemble(AGENT, _cfg(), tx, _journal(), chain_ok=True, now=NOW)
    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["users"]["value"] == "7"
    assert "clients distincts" in kpis["users"]["delta"]


def test_users_kpi_is_honestly_empty_without_a_captured_identity() -> None:
    # An anonymous turn carries no subject ⇒ honest "—", never a fabricated count.
    payload = syn._assemble(AGENT, _cfg(), _tx(), _journal(), chain_ok=True, now=NOW)
    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["users"]["value"] == "—"
    assert "aucune identité" in kpis["users"]["delta"]


def test_csat_kpi_is_a_real_rate_from_captured_votes() -> None:
    # ADR 0041: satisfaction = count(up)/count(*) over real customer votes.
    tx = _tx()
    tx["csat"] = {"up": 8, "total": 10}  # type: ignore[index]
    payload = syn._assemble(AGENT, _cfg(), tx, _journal(), chain_ok=True, now=NOW)
    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["satisfaction"]["value"] == "80%"
    assert "8 / 10" in kpis["satisfaction"]["delta"]


def test_csat_kpi_is_honestly_empty_until_a_customer_votes() -> None:
    # No votes ⇒ honest "—", never assumed satisfaction.
    payload = syn._assemble(AGENT, _cfg(), _tx(), _journal(), chain_ok=True, now=NOW)
    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert kpis["satisfaction"]["value"] == "—"
    assert "aucun avis" in kpis["satisfaction"]["delta"]


def test_users_and_satisfaction_carry_a_metricinfo_explain() -> None:
    # A small-but-real number gets a MetricInfo so it is not read as a bug; a plain
    # count (conversations) carries none.
    tx = _tx()
    tx["totals"]["subjects"] = 3  # type: ignore[index]
    tx["csat"] = {"up": 1, "total": 1}  # type: ignore[index]
    payload = syn._assemble(AGENT, _cfg(), tx, _journal(), chain_ok=True, now=NOW)
    kpis = {k["key"]: k for k in payload["kpis"]}  # type: ignore[union-attr]
    assert "subject_id" in kpis["users"]["explain"]["how"]  # type: ignore[index]
    assert kpis["satisfaction"]["explain"]["source"]  # type: ignore[index]
    assert "explain" not in kpis["conversations"]


class _RecordingSynCursor:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def __aenter__(self) -> _RecordingSynCursor:
        return self

    async def __aexit__(self, *_a: object) -> bool:
        return False

    async def execute(self, sql: str, *_params: object) -> None:
        self._log.append(sql)

    async def fetchone(self) -> dict[str, object]:
        return {}

    async def fetchall(self) -> list[dict[str, object]]:
        return []


class _RecordingSynConn:
    def __init__(self, log: list[str]) -> None:
        self._log = log
        self.row_factory: object = None

    def cursor(self, *, row_factory: object | None = None) -> _RecordingSynCursor:
        assert row_factory is not None, "the reader must scope its row factory to the cursor"
        return _RecordingSynCursor(self._log)


class _RecordingSynConnCM:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def __aenter__(self) -> _RecordingSynConn:
        return _RecordingSynConn(self._log)

    async def __aexit__(self, *_a: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_fetch_transcript_reads_real_traffic_only_and_the_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Synthèse's transcript reads (conversations / tours / résolution / latence /
    # utilisateurs) must exclude operator TEST turns and count distinct clients (ADR 0040).
    log: list[str] = []
    monkeypatch.setattr(syn, "_connection", lambda: _RecordingSynConnCM(log))
    await syn._fetch_transcript("recouvrement", 1)
    tx_queries = [q for q in log if "conversation_messages" in q]
    assert tx_queries  # totals + daily + recent_convs + recent_msgs
    assert all("NOT synthetic" in q for q in tx_queries)
    assert any("count(DISTINCT subject_id)" in q for q in tx_queries)
