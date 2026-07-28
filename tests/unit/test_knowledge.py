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


def _assemble_default(
    *, lang: str = "fr", state: dict | None = None, trace: dict | None = None
) -> dict:
    probe = {
        "categories": {"dora": {"citation": 10.0, "hits": 17}},
        "_overall": {"coverage": 93, "citation": 10, "hitrate": 66},
    }
    return k._assemble(
        _sample_rows(), state or {}, probe, {}, lang, now=datetime.now(UTC), trace=trace
    )


def _ledger_entry(target: str, occurred: str, actor: str, args: dict) -> dict:
    return {"target": target, "occurred_at": occurred, "actor": actor, "arguments": args}


class TestSourceStateTraces:
    """The S1 fold behind the per-source journal (OT-01 — the substrate the registry owed)."""

    def test_folds_only_its_targets_grouped_per_source_and_bounds_the_read(
        self, monkeypatch
    ) -> None:
        seen_kwargs: dict = {}

        def _entries(*_a, **kwargs):
            seen_kwargs.update(kwargs)
            return [
                _ledger_entry(
                    "config_overrides.llm.chat_model", "2026-07-01T10:00:00+00:00", "x", {}
                ),
                _ledger_entry(
                    "knowledge_source.cnil",
                    "2026-07-02T10:00:00+00:00",
                    "amadou",
                    {"active": False, "was_active": True},
                ),
                _ledger_entry(
                    "knowledge_source.cnil",
                    "2026-07-03T10:00:00+00:00",
                    "admin",
                    {"attached": False, "was_attached": True},
                ),
                _ledger_entry("knowledge_source.dora", "not-an-instant", "admin", {"active": True}),
            ]

        monkeypatch.setattr(k, "read_ledger_entries_by_target_prefix", _entries)
        traces = k.source_state_traces()
        assert "until" in seen_kwargs, "the ledger read must be bounded at the seam"
        assert set(traces) == {"cnil"}, "foreign targets and unplaceable entries claim no place"
        acts = traces["cnil"]
        assert [a["by"] for a in acts] == ["amadou", "admin"]
        assert acts[0]["active"] is False
        assert acts[1]["attached"] is False

    def test_belt_holds_the_bound_even_when_the_seam_returns_more(self, monkeypatch) -> None:
        # File mode hands back the whole journal whatever the kwargs — the belt filters.
        entries = [
            _ledger_entry("knowledge_source.cnil", "2026-07-02T10:00:00", "a", {"active": False}),
            _ledger_entry(
                "knowledge_source.cnil", "2026-07-10T10:00:00+00:00", "b", {"active": True}
            ),
        ]
        monkeypatch.setattr(k, "read_ledger_entries_by_target_prefix", lambda *_a, **_kw: entries)
        bound = datetime(2026, 7, 5, tzinfo=UTC)
        traces = k.source_state_traces(until=bound)
        assert [a["by"] for a in traces.get("cnil", [])] == [
            "a"
        ], "an act after T must not appear in a trace bounded at T (naive instants normalized)"

    def test_detail_journal_lists_acts_newest_first_localized(self) -> None:
        trace = {
            "dora": [
                {
                    "at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
                    "by": "amadou",
                    "attached": None,
                    "active": False,
                },
                {
                    "at": datetime(2026, 7, 3, 11, 30, tzinfo=UTC),
                    "by": "admin",
                    "attached": False,
                    "active": None,
                },
            ]
        }
        payload = _assemble_default(trace=trace)
        dora = next(d for d in payload["details"] if d["key"] == "dora")
        journal = dora["attachment"]["journal"]
        assert [ev["by"] for ev in journal] == ["admin", "amadou"], "newest act first"
        assert journal[0]["action"] == "Détachée"
        assert journal[1]["action"] == "Désactivée"
        assert journal[0]["at"] == "03/07/2026 11:30"
        gdpr = next(d for d in payload["details"] if d["key"] == "gdpr")
        assert gdpr["attachment"]["journal"] == [], "no journalled act yet — an honest empty"

    def test_detail_journal_is_none_when_the_ledger_could_not_be_read(self) -> None:
        payload = _assemble_default(trace=None)
        dora = next(d for d in payload["details"] if d["key"] == "dora")
        assert (
            dora["attachment"]["journal"] is None
        ), "a witness that cannot see reports a blind spot, never an empty trace"
        assert dora["attachment"]["journal_unavailable"]


def test_source_state_of_defaults_and_reads_the_store(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(k, "_state_path", lambda: tmp_path / "knowledge_state.json")
    assert k.source_state_of("cnil") == {"attached": True, "active": True}
    k.set_source_state("cnil", active=False)
    assert k.source_state_of("cnil") == {"attached": True, "active": False}
