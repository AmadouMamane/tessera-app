"""Unit tests for the S1 ingestion-lineage store (corpus/lineage.py)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tessera.corpus import lineage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _isolate_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the lineage store at a temp file so tests never touch the real one."""
    monkeypatch.setattr(lineage, "lineage_path", lambda: tmp_path / "ingestion_lineage.jsonl")


def _record(corpus: str = "regulations", *, model: str = "bge-m3", chunks: int = 12) -> None:
    lineage.record_ingestion_run(
        corpus=corpus,
        language="en",
        embedding_model=model,
        embedding_dimension=1024,
        chunk_target_chars=800,
        chunk_overlap_chars=150,
        chunk_count=chunks,
        documents=3,
        trigger="test",
    )


def test_record_and_load_roundtrip() -> None:
    assert lineage.load_ingestion_runs() == []
    _record(chunks=10)
    _record(chunks=20)
    runs = lineage.load_ingestion_runs()
    assert [r.run_id for r in runs] == ["ING-0001", "ING-0002"]
    assert runs[0].chunk_count == 10
    assert runs[1].embedding_model == "bge-m3"


def test_chain_is_hash_linked_and_verifies() -> None:
    _record()
    _record()
    assert lineage.verify_lineage_chain() is True
    runs = lineage.load_ingestion_runs()
    assert runs[0].prev_hash == "0" * 64  # genesis
    assert runs[1].prev_hash == runs[0].hash  # linked


def test_tampering_breaks_the_chain() -> None:
    _record(chunks=10)
    _record(chunks=20)
    path = lineage.lineage_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["chunk_count"] = 999  # edit a recorded fact, keep the old hash
    lines[0] = json.dumps(first, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert lineage.verify_lineage_chain() is False


def test_runs_for_corpus_is_newest_first_and_scoped() -> None:
    _record(corpus="regulations", chunks=1)
    _record(corpus="credit_aurore", chunks=2)
    _record(corpus="regulations", chunks=3)
    reg = lineage.runs_for_corpus("regulations")
    assert [r.chunk_count for r in reg] == [3, 1]  # newest first, credit excluded
    assert lineage.latest_run_for_corpus("regulations").chunk_count == 3
    assert lineage.latest_run_for_corpus("unknown") is None
