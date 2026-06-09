"""Unit tests for response lineage / SBOM (ADR 0010, #10)."""

from __future__ import annotations

from types import SimpleNamespace

from tessera.observability.lineage import build_lineage


def test_build_lineage_collects_bill_of_materials() -> None:
    docs = [
        SimpleNamespace(source="DORA Art. 28", chunk_id="c1"),
        SimpleNamespace(source="GDPR", chunk_id=None),
    ]
    lineage = build_lineage(language="fr", model="llama3.3:70b", documents=docs)

    assert lineage.model == "llama3.3:70b"
    assert lineage.doc_sources == ["DORA Art. 28#c1", "GDPR"]
    # The fr prompt + guard policy exist in the repo → real content hashes.
    assert lineage.prompt_version != "unknown"
    assert len(lineage.prompt_version) == 12
    assert len(lineage.guard_policy_version) == 12


def test_build_lineage_skips_sourceless_docs() -> None:
    docs = [SimpleNamespace(source="", chunk_id="x"), SimpleNamespace(other=1)]
    lineage = build_lineage(language="en", model="m", documents=docs)
    assert lineage.doc_sources == []
