"""Unit tests for the Sources & memory overview (configurer/sources-memoire).

Assert the payload is assembled from the real data substrate - pgvector corpus
rows plus the two memory-table counters - and never from the former invented
Kafka / MySQL / EUR fixture. The pure ``_assemble`` is exercised with synthetic
pgvector rows and memory stats, so the test needs no Postgres.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability import sources as sm

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
    assert emb["model"] == "bge-m3"
    assert emb["distance"] == "cosine"
    assert emb["chunks"] == "5"  # 2 dora + 3 comptes
    assert emb["languages"] == "3"


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
