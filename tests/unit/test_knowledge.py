"""Unit tests for the Connaissances payload assembly (no DB, no I/O).

Exercise the pure helpers and :func:`tessera.observability.knowledge._assemble`
with synthetic pgvector rows: localization (fr/de/en), the real Volume share,
stable logic keys (status_tone/type_tone), the probe hit count, and the durable
attach/detach state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tessera.observability import knowledge as k


def _row(cat: str, source: str, language: str, *, locator: str = "art.1", days: int = 0) -> dict:
    inserted = datetime.now(UTC) - timedelta(days=days)
    return {
        "corpus": "regulations" if cat in {"dora", "gdpr"} else "credit_aurore",
        "source": source,
        "language": language,
        "metadata": {"category": cat, "locator": locator, "language": language},
        "inserted_at": inserted,
    }


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("fr", "RGPD - Protection des données"),
        ("de", "DSGVO - Datenschutz"),
        ("en", "GDPR - Data protection"),
        ("xx", "RGPD - Protection des données"),  # unknown -> French fallback
    ],
)
def test_source_name_localized(lang: str, expected: str) -> None:
    assert k._source_name("gdpr", lang) == expected


def test_t_fallback_to_french() -> None:
    assert k._t("col_volume", "fr") == "Volume"
    assert k._t("col_volume", "de") == "Volumen"
    assert k._t("type_reg", "xx") == "Réglementation"  # unknown locale -> fr


def test_rows_chunks_label_is_german_only_for_de() -> None:
    assert k.rows_chunks_label(3, 2, "fr") == "3 chunks / 2 documents"
    assert k.rows_chunks_label(3, 2, "en") == "3 chunks / 2 documents"
    assert k.rows_chunks_label(3, 2, "de") == "3 Chunks / 2 Dokumente"


def test_freshness_localized() -> None:
    now = datetime(2026, 6, 16, tzinfo=UTC)
    assert k._freshness(now, now, "fr") == "Aujourd'hui"
    assert k._freshness(now, now, "de") == "Heute"
    assert k._freshness(now, now - timedelta(days=3), "fr") == "il y a 3 j"
    assert k._freshness(now, now - timedelta(days=3), "de") == "vor 3 T"
    assert k._freshness(now, now - timedelta(days=3), "en") == "3d ago"


def _sample_rows() -> list[dict]:
    # dora: 6 chunks / 2 docs ; gdpr: 4 chunks / 1 doc -> total 10 chunks.
    rows = [_row("dora", f"dora-{i}", "fr") for i in range(3)]
    rows += [_row("dora", f"dora-de-{i}", "de") for i in range(3)]
    rows += [_row("gdpr", "gdpr-1", "en") for _ in range(4)]
    return rows


def test_assemble_volume_is_real_corpus_share() -> None:
    payload = _assemble_default()
    rows = {r["key"]: r for r in payload["table"]["rows"]}  # type: ignore[index]
    # 6/10 and 4/10 of the indexed chunks.
    assert rows["dora"]["coverage"] == 60
    assert rows["gdpr"]["coverage"] == 40
    assert sum(r["coverage"] for r in payload["table"]["rows"]) == 100  # type: ignore[index]


def test_assemble_carries_stable_keys_and_hits() -> None:
    payload = _assemble_default()
    dora = next(r for r in payload["table"]["rows"] if r["key"] == "dora")  # type: ignore[index]
    assert dora["type_tone"] == "reg"
    assert dora["status_tone"] == "good"
    assert dora["hits"] == 17  # absolute probe hit count, surfaced from the probe
    assert dora["citation"] == "10%"
    assert set(dora["langs"]) == {"de", "fr"}


@pytest.mark.parametrize(
    ("lang", "volume_col", "coverage_kpi"),
    [
        ("fr", "Volume", "Couverture des sources"),
        ("de", "Volumen", "Quellenabdeckung"),
        ("en", "Volume", "Source coverage"),
    ],
)
def test_assemble_localizes_columns_and_kpis(lang: str, volume_col: str, coverage_kpi: str) -> None:
    payload = _assemble_default(lang=lang)
    assert payload["table"]["columns"][3] == volume_col  # type: ignore[index]
    coverage = next(kpi for kpi in payload["kpis"] if kpi["key"] == "coverage")  # type: ignore[index]
    assert coverage["label"] == coverage_kpi


def test_assemble_detached_source_moves_to_attachable() -> None:
    payload = _assemble_default(state={"gdpr": {"attached": False, "active": True}})
    keys = {r["key"] for r in payload["table"]["rows"]}  # type: ignore[index]
    assert "gdpr" not in keys
    assert any(item["key"] == "gdpr" for item in payload["attachable"])  # type: ignore[index]


def test_assemble_detail_usage_localized_with_hits() -> None:
    payload = _assemble_default(lang="en")
    dora = next(d for d in payload["details"] if d["key"] == "dora")  # type: ignore[index]
    assert dora["tabs"] == ["Usage", "Grounded answers", "Parameters"]
    labels = [u["label"] for u in dora["usage"]]
    assert "Queries that cited" in labels
    assert "Corpus share" in labels


def test_set_source_state_round_trip(tmp_path, monkeypatch) -> None:
    state_file = tmp_path / "knowledge_state.json"
    monkeypatch.setattr(k, "_state_path", lambda: state_file)
    assert k._load_state() == {}
    k.set_source_state("dora", attached=False)
    assert k._load_state()["dora"]["attached"] is False
    k.set_source_state("dora", attached=True, active=False)
    reloaded = k._load_state()["dora"]
    assert reloaded["attached"] is True
    assert reloaded["active"] is False


def _assemble_default(*, lang: str = "fr", state: dict | None = None) -> dict:
    probe = {
        "categories": {"dora": {"citation": 10.0, "hits": 17}},
        "_overall": {"coverage": 93, "citation": 10, "hitrate": 66},
    }
    return k._assemble(_sample_rows(), state or {}, probe, {}, lang, now=datetime.now(UTC))
