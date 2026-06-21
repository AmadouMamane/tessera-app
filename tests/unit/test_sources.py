"""Unit tests for the Sources & memory overview (configurer/sources-memoire).

Assert the payload is assembled from the real data substrate - pgvector corpus
rows plus the two memory-table counters - and never from the former invented
Kafka / MySQL / EUR fixture. The pure ``_assemble`` is exercised with synthetic
pgvector rows and memory stats, so the test needs no Postgres.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability import sources as sm
from tessera.retrieval.embeddings import embedding_model_name

NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)


def _row(cat: str, language: str, source: str, locator: str) -> dict[str, object]:
    return {
        "corpus": "regulations" if cat in {"dora", "gdpr", "bafin", "cnil"} else "credit_aurore",
        "source": source,
        "language": language,
        "metadata": {"category": cat, "locator": locator},
        "inserted_at": NOW,
    }


def _rows() -> list[dict[str, object]]:
    return [
        _row("dora", "en", "dora.pdf", "art.5"),
        _row("dora", "en", "dora.pdf", "art.6"),
        _row("comptes", "fr", "comptes_fr.json", "sec.1"),
        _row("comptes", "de", "comptes_de.json", "sec.1"),
        _row("comptes", "fr", "comptes_fr.json", "sec.2"),
    ]


def _ltm() -> sm._MemStat:
    stat = sm._MemStat()
    stat.rows = 10
    stat.subjects = 4
    stat.kinds = [("semantic", 10)]
    stat.last = NOW
    stat.first = NOW
    return stat


def _tx() -> sm._MemStat:
    stat = sm._MemStat()
    stat.rows = 20
    stat.conversations = 5
    stat.last = NOW
    stat.first = NOW
    return stat


def test_catalogue_is_corpus_plus_two_memory_stores() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    ids = [r["id"] for r in payload["sources"]]
    # two corpus categories + the two memory stores
    assert payload["total_sources"] == 4
    assert sm._LTM_ID in ids
    assert sm._TX_ID in ids
    # No invented fixture sources survive.
    names = " ".join(str(r["name"]) for r in payload["sources"]).lower()
    assert "kafka" not in names
    assert "mysql" not in names
    assert "salesforce" not in names


def test_kpis_are_real_counts() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpis["sources"] == "4"
    assert kpis["corpus"] == "2"
    assert kpis["chunks"] == "5"
    # dora=en, comptes=fr/de -> three distinct languages
    assert kpis["languages"] == "3"
    assert kpis["memory"] == "10"
    assert kpis["transcript"] == "20"
    assert kpis["conversations"] == "5"


def test_language_distribution_sums_to_corpus_chunks() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    total = sum(c["value"] for c in payload["cost_by_source"])
    assert total == 5  # 2 EN + 2 FR + 1 DE
    by_code = {c["name"]: c["value"] for c in payload["cost_by_source"]}
    assert by_code == {"EN": 2, "FR": 2, "DE": 1}


def test_type_donut_partitions_all_rows() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    counts = {s["key"]: s["count"] for s in payload["by_type"]}
    assert counts == {"regulation": 1, "product": 1, "memory": 1, "transcript": 1}
    assert sum(s["count"] for s in payload["by_type"]) == payload["total_sources"]


def test_citation_dash_without_probe_and_value_with_probe() -> None:
    no_probe = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    dora = next(r for r in no_probe["sources"] if r["id"] == "dora")
    assert dora["citation"] == "-"

    probe = {"categories": {"dora": {"citation": 80, "hits": 12}}, "_overall": {"citation": 80}}
    with_probe = sm._assemble(_rows(), _ltm(), _tx(), probe, lang="fr", now=NOW)
    dora2 = next(r for r in with_probe["sources"] if r["id"] == "dora")
    assert dora2["citation"] == "80%"


def test_memory_detail_uses_real_governance_ttl() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    ltm_row = next(r for r in payload["sources"] if r["id"] == sm._LTM_ID)
    assert ltm_row["volume"] == "10"
    assert ltm_row["classification"] == "confidential"
    gov = next(s for s in ltm_row["detail"]["sections"] if s["key"] == "governance")
    retention = {row["label"]: row["value"] for row in gov["rows"]}
    # semantic kind -> 365-day TTL from memory.governance
    assert "365" in next(v for k, v in retention.items() if "tention" in k or "ufbe" in k)


def test_detail_has_four_sections_and_description() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    selected = payload["selected"]
    assert selected is not None
    assert [s["key"] for s in selected["sections"]] == [
        "overview",
        "content",
        "usage",
        "governance",
    ]
    assert selected["description"]


def test_available_source_ids_include_memory_stores() -> None:
    ids = sm.available_source_ids()
    assert sm._LTM_ID in ids
    assert sm._TX_ID in ids
    assert "dora" in ids


def _fleet() -> list[dict[str, object]]:
    return [
        {
            "agent_id": "support-client",
            "name": "Support Client",
            "tone": "crit",
            "label": "BLOQUE",
            "passed": False,
        },
        {
            "agent_id": "onboarding",
            "name": "Onboarding",
            "tone": "good",
            "label": "OK",
            "passed": True,
        },
    ]


def _consumers() -> dict[str, list[dict[str, object]]]:
    fleet = _fleet()
    # regulations_dora consumed by support-client; credit_aurore by both.
    return {"regulations_dora": [fleet[0]], "credit_aurore": fleet}


def test_used_by_maps_corpus_consumers_onto_categories() -> None:
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, _consumers(), _fleet(), lang="fr", now=NOW
    )
    by_id = {r["id"]: r for r in payload["sources"]}
    # regulation category inherits its corpus (regulations_dora) -> one product
    assert by_id["dora"]["used_by"] == "Support Client"
    assert by_id["dora"]["consumer_ids"] == ["support-client"]
    # product category rolls up to credit_aurore -> all products
    assert by_id["comptes"]["used_by"] == "2 produits (tous)"
    assert by_id["comptes"]["used_by_count"] == 2


def test_memory_stores_are_shared_infra() -> None:
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, _consumers(), _fleet(), lang="fr", now=NOW
    )
    ltm_row = next(r for r in payload["sources"] if r["id"] == sm._LTM_ID)
    assert ltm_row["infra"] is True
    assert ltm_row["used_by"] == "Infra partagée (tous)"
    assert set(ltm_row["consumer_ids"]) == {"support-client", "onboarding"}


def test_used_by_detail_carries_regate_blast_radius() -> None:
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, _consumers(), _fleet(), lang="fr", now=NOW
    )
    dora = next(r for r in payload["sources"] if r["id"] == "dora")
    consumers = dora["detail"]["consumers"]
    # support-client is not passing -> exactly one consumer to re-validate
    assert consumers["regate_count"] == 1
    assert consumers["items"][0]["agent_id"] == "support-client"
    comptes = next(r for r in payload["sources"] if r["id"] == "comptes")
    # one of the two credit_aurore consumers is passing, one is not
    assert comptes["detail"]["consumers"]["regate_count"] == 1


def test_used_by_absent_when_no_consumer_data() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    dora = next(r for r in payload["sources"] if r["id"] == "dora")
    assert dora["used_by"] == "Aucun produit"
    assert dora["consumer_ids"] == []


def test_retention_and_embedding_are_real() -> None:
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    by_id = {r["id"]: r for r in payload["sources"]}
    assert by_id["dora"]["retention"] == "Permanente"
    assert by_id[sm._LTM_ID]["retention"] == "365 jours"  # semantic TTL
    assert by_id[sm._TX_ID]["retention"] == "Durable (transcript)"
    emb = payload["embedding"]
    assert emb["model"] == embedding_model_name()  # active backend, never hardcoded
    assert emb["distance"] == "cosine"
    assert emb["chunks"] == "5"  # 2 dora + 3 comptes
    assert emb["languages"] == "3"


def test_growth_attaches_to_memory_and_not_corpus() -> None:
    history = {
        sm._LTM_ID: [{"day": "2026-06-19", "count": 10}, {"day": "2026-06-20", "count": 12}],
    }
    payload = sm._assemble(_rows(), _ltm(), _tx(), {}, {}, [], history, lang="fr", now=NOW)
    by_id = {r["id"]: r for r in payload["sources"]}
    assert by_id[sm._LTM_ID]["growth"] == history[sm._LTM_ID]
    assert by_id[sm._TX_ID]["growth"] == []  # no history supplied for transcript
    assert by_id["dora"]["growth"] == []  # corpus has no time axis


def test_cost_is_real_and_negligible() -> None:
    # 5 chunks, ~small char volume -> on-prem 0, frontier sub-cent. Never the fixture.
    index_chars = {"dora": 24000, "comptes": 12000}
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, {}, [], {}, index_chars, lang="fr", now=NOW
    )
    assert payload["cost"]["active"].startswith("EUR 0")
    assert payload["cost"]["frontier"].startswith("EUR 0")
    # Per-corpus-row cost is a real estimate; memory rows have none.
    by_id = {r["id"]: r for r in payload["sources"]}
    assert by_id["dora"]["cost"].startswith("EUR")
    assert by_id[sm._LTM_ID]["cost"] == "-"


def test_lineage_is_the_real_source_to_answer_pipeline() -> None:
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, _consumers(), _fleet(), {}, {}, (False, 16411, 16410),
        lang="fr", now=NOW,
    )
    steps = {s["key"]: s["value"] for s in payload["lineage"]["steps"]}
    assert steps["corpus"] == "3 documents"  # dora.pdf + comptes_fr + comptes_de
    assert embedding_model_name() in steps["index"]
    assert "llama3.2:3b" in steps["agent"]  # real on-prem model
    assert steps["response"] == "20/06/2026 12:00"  # tx.last
    assert "16 411" in steps["proof"]  # the real audit length


def test_audit_chain_is_honest_when_broken() -> None:
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, {}, [], {}, {}, (False, 16411, 16410), lang="fr", now=NOW
    )
    audit = payload["audit"]
    assert audit["verified"] is False
    assert audit["tone"] == "crit"
    assert "16410" in audit["label"]  # honest break location, not a fake "intact"
    assert audit["length"] == "16 411"


def test_activity_feed_is_sources_and_memory_lifecycle() -> None:
    # Store-lifecycle events (PLATEFORME catalogue), NOT agent reasoning turns.
    events = [
        {"at": NOW, "kind": "corpus", "detail": 238},
        {"at": NOW, "kind": "memory", "actor": "b93406f4abcd"},
        {"at": NOW, "kind": "transcript", "actor": ""},
        {"at": None, "kind": "memory", "actor": "x"},  # dropped (no timestamp)
    ]
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, {}, _fleet(), {}, {}, None, events, lang="fr", now=NOW
    )
    items = payload["activity"]["items"]
    assert len(items) == 3  # the null-timestamp event is skipped
    by_text = {i["text"] for i in items}
    assert "Corpus indexé" in by_text
    assert "Souvenir mémorisé" in by_text
    assert "Transcription enrichie" in by_text
    # no agent-turn framing on this PLATEFORME page
    assert "Réponse générée" not in by_text
    corpus = next(i for i in items if i["text"] == "Corpus indexé")
    assert corpus["actor"] == "238 chunks"
    mem = next(i for i in items if i["text"] == "Souvenir mémorisé")
    assert mem["actor"] == "b93406f4"  # truncated subject id


def test_latency_annotates_the_lineage_and_cost_uses_the_gauge() -> None:
    # The transcript latency_ms is the Grafana turn-duration signal, persisted.
    payload = sm._assemble(
        _rows(), _ltm(), _tx(), {}, {}, _fleet(), {}, {}, (True, 1, None), [],
        (363, 4571.0), 0.0, lang="fr", now=NOW,
    )
    # latency annotates the source-to-answer lineage (part of the pipeline story)
    resp = next(s for s in payload["lineage"]["steps"] if s["key"] == "response")
    assert "4,6 s" in resp["value"]
    # cost.active comes from the live Prometheus gauge when provided (0 on-prem)
    assert payload["cost"]["telemetry"] is True
    assert payload["cost"]["active"].startswith("EUR 0")
    # the invented "suggestions" panel is gone
    assert "suggestions" not in payload


def test_corpus_of_maps_regulation_and_product() -> None:
    assert sm._corpus_of("dora") == "regulations_dora"
    assert sm._corpus_of("gdpr") == "regulations_gdpr"
    assert sm._corpus_of("comptes") == "credit_aurore"
    assert sm._corpus_of("cartes") == "credit_aurore"


def test_localization_switches_free_text() -> None:
    fr = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="fr", now=NOW)
    en = sm._assemble(_rows(), _ltm(), _tx(), {}, lang="en", now=NOW)
    assert fr["kpis"][0]["label"] == "Sources totales"
    assert en["kpis"][0]["label"] == "Total sources"
    fr_ltm = next(r for r in fr["sources"] if r["id"] == sm._LTM_ID)
    en_ltm = next(r for r in en["sources"] if r["id"] == sm._LTM_ID)
    assert fr_ltm["name"] == "Mémoire long terme"
    assert en_ltm["name"] == "Long-term memory"
