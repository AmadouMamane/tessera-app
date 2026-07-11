"""Ingestion lineage — an S1, hash-chained, append-only store of index runs.

The **version** of a knowledge source is the ingestion run that produced its
pgvector index: which embedding model + dimension, which chunking config, how
many chunks, and what triggered it. The **history** of a source is the sequence
of those runs (re-embed / re-index). This is *data lineage*, not a file repo: a
re-embed with a new model is a new version even though the corpus text is
unchanged — so the worldclass unit is corpus x embedding model x index.

Append-only and hash-chained like the guard audit log
(:func:`tessera.guard.audit.verify_audit_chain`) and the eval waivers
(:mod:`tessera.observability.eval_waivers`) — same S1 family. Stored as JSONL
next to the guard audit log so it survives restarts and is **deploy-safe** (no
runtime ``.git`` dependency, no DB): a line is written at each real ingestion
run from :func:`tessera.corpus.ingestion.ingest_path`. The store starts empty —
the OT-01 history then renders an honest empty state, never fabricated runs.

The store is pure I/O so it can be unit-tested and seeded without a database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = [
    "IngestionRun",
    "latest_run_for_corpus",
    "lineage_path",
    "load_ingestion_runs",
    "record_ingestion_run",
    "runs_for_corpus",
    "verify_lineage_chain",
]

_GENESIS_HASH = "0" * 64


def lineage_path() -> Path:
    """The durable JSONL store, next to the guard audit log (same S1 family)."""
    return get_settings().guard.audit_file.parent / "ingestion_lineage.jsonl"


@dataclass(frozen=True, slots=True)
class IngestionRun:
    """One append-only ingestion/index run — a source's version stamp."""

    run_id: str
    corpus: str
    language: str
    embedding_model: str
    embedding_dimension: int
    chunk_target_chars: int
    chunk_overlap_chars: int
    chunk_count: int
    documents: int
    trigger: str
    recorded_at: str
    prev_hash: str
    hash: str


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_core(core: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()


def _last_hash(runs: list[IngestionRun]) -> str:
    return runs[-1].hash if runs else _GENESIS_HASH


def _run_core(run: IngestionRun, prev_hash: str) -> dict[str, Any]:
    """The hashed body of a run (everything except its own ``hash``)."""
    return {
        "type": "tessera.corpus.ingestion_run",
        "version": 1,
        "run_id": run.run_id,
        "corpus": run.corpus,
        "language": run.language,
        "embedding_model": run.embedding_model,
        "embedding_dimension": run.embedding_dimension,
        "chunk_target_chars": run.chunk_target_chars,
        "chunk_overlap_chars": run.chunk_overlap_chars,
        "chunk_count": run.chunk_count,
        "documents": run.documents,
        "trigger": run.trigger,
        "recorded_at": run.recorded_at,
        "prev_hash": prev_hash,
    }


def _coerce_run(obj: Mapping[str, Any]) -> IngestionRun | None:
    try:
        return IngestionRun(
            run_id=str(obj["run_id"]),
            corpus=str(obj["corpus"]),
            language=str(obj.get("language", "")),
            embedding_model=str(obj.get("embedding_model", "")),
            embedding_dimension=int(obj.get("embedding_dimension", 0)),
            chunk_target_chars=int(obj.get("chunk_target_chars", 0)),
            chunk_overlap_chars=int(obj.get("chunk_overlap_chars", 0)),
            chunk_count=int(obj.get("chunk_count", 0)),
            documents=int(obj.get("documents", 0)),
            trigger=str(obj.get("trigger", "")),
            recorded_at=str(obj.get("recorded_at", "")),
            prev_hash=str(obj.get("prev_hash", _GENESIS_HASH)),
            hash=str(obj.get("hash", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_ingestion_runs() -> list[IngestionRun]:
    """Read every ingestion run in chain order (oldest first)."""
    path = lineage_path()
    if not path.exists():
        return []
    runs: list[IngestionRun] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            # best-effort: skip a malformed ingestion-run JSONL line — non-gating read (0015)
            continue
        if isinstance(obj, dict):
            run = _coerce_run(obj)
            if run is not None:
                runs.append(run)
    return runs


def verify_lineage_chain() -> bool:
    """Recompute the hash chain end to end; any tamper breaks it."""
    prev = _GENESIS_HASH
    for run in load_ingestion_runs():
        if run.prev_hash != prev or run.hash != _hash_core(_run_core(run, prev)):
            return False
        prev = run.hash
    return True


def runs_for_corpus(corpus: str) -> list[IngestionRun]:
    """Every run for ``corpus`` (newest first)."""
    return [r for r in reversed(load_ingestion_runs()) if r.corpus == corpus]


def latest_run_for_corpus(corpus: str) -> IngestionRun | None:
    """The most recent run for ``corpus``, or ``None`` if it was never ingested."""
    runs = runs_for_corpus(corpus)
    return runs[0] if runs else None


def record_ingestion_run(
    *,
    corpus: str,
    language: str,
    embedding_model: str,
    embedding_dimension: int,
    chunk_target_chars: int,
    chunk_overlap_chars: int,
    chunk_count: int,
    documents: int,
    trigger: str,
) -> IngestionRun:
    """Append a real ingestion run, hash-chained onto the prior tail.

    Called once per ``ingest_path`` so the lineage history is built from real
    runs only. Returns the persisted run.
    """
    runs = load_ingestion_runs()
    prev = _last_hash(runs)
    now = datetime.now(UTC).isoformat()
    stub = IngestionRun(
        run_id=f"ING-{len(runs) + 1:04d}",
        corpus=corpus,
        language=language,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        chunk_target_chars=chunk_target_chars,
        chunk_overlap_chars=chunk_overlap_chars,
        chunk_count=chunk_count,
        documents=documents,
        trigger=trigger,
        recorded_at=now,
        prev_hash=prev,
        hash="",
    )
    digest = _hash_core(_run_core(stub, prev))
    run = replace(stub, hash=digest)
    path = lineage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({**_run_core(run, prev), "hash": digest}, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")
    return run
