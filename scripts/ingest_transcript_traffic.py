"""Attribute REAL conversation exchanges to knowledge sources.

Unlike :mod:`scripts.generate_traffic` (which sends a fixed list of synthetic
questions through retrieval), this script reads the durable conversation
transcript (``conversation_messages`` -- Mechanism A of ADR 0007), pairs every
real user question with the assistant answer that followed it, and attributes
each exchange to the knowledge source its question actually retrieves
(``knn_search`` over the live store, cosine >= threshold).

The result is the same ``knowledge_traffic.json`` consumed by
:mod:`tessera.observability.knowledge`, but every "Reponses ancrees" entry now
carries the real user question AND the real grounded assistant answer, plus the
real ``created_at`` timestamp -- genuine request/response traces, not a probe.

Run::

    PYTHONPATH=.:src .venv/bin/python -m scripts.ingest_transcript_traffic
"""

from __future__ import annotations

import asyncio
import itertools
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from tessera.observability.knowledge import _SOURCE_META, _state_path
from tessera.retrieval.embeddings import embed
from tessera.retrieval.store import _connection, knn_search

if TYPE_CHECKING:
    from collections.abc import Sequence

_CORPORA = ("regulations", "credit_aurore")
_TOP_K = 5
_THRESHOLD = 0.55
_QUESTION_MAX = 140
_EXAMPLES_PER_SOURCE = 5
_WS = re.compile(r"\s+")


def _traffic_path() -> object:
    return _state_path().parent / "knowledge_traffic.json"


def _flatten(text: str) -> str:
    """Collapse whitespace in verbatim transcript text (no truncation)."""
    return _WS.sub(" ", text).strip()


def _clean(text: str, limit: int) -> str:
    """Collapse whitespace and truncate verbatim transcript text for display."""
    flat = _flatten(text)
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


class _Exchange:
    """One real user question paired with the assistant answer that followed."""

    __slots__ = ("answer", "count", "last_used", "question")

    def __init__(self, question: str, answer: str, when: datetime) -> None:
        self.question = question
        self.answer = answer
        self.last_used = when
        self.count = 1

    def merge(self, answer: str, when: datetime) -> None:
        self.count += 1
        if when >= self.last_used:
            self.last_used, self.answer = when, answer


async def _load_exchanges() -> list[_Exchange]:
    """Pair user->assistant turns from the transcript, deduped by question."""
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT conversation_id, id, role, content, created_at "
                "FROM conversation_messages ORDER BY conversation_id, id"
            )
            rows = list(await cur.fetchall())

    by_question: dict[str, _Exchange] = {}
    for prev, cur_row in itertools.pairwise(rows):
        if (
            prev["role"] != "user"
            or cur_row["role"] != "assistant"
            or prev["conversation_id"] != cur_row["conversation_id"]
        ):
            continue
        question = str(prev["content"]).strip()
        if not question:
            continue
        answer = _flatten(str(cur_row["content"]))
        when = cur_row["created_at"]
        key = _WS.sub(" ", question).strip().lower()
        existing = by_question.get(key)
        if existing is None:
            by_question[key] = _Exchange(_clean(question, _QUESTION_MAX), answer, when)
        else:
            existing.merge(answer, when)
    return list(by_question.values())


async def _grounded_categories(query_vec: Sequence[float]) -> set[str]:
    found: set[str] = set()
    for corpus in _CORPORA:
        for hit in await knn_search(
            query_embedding=list(query_vec), corpus=corpus, language=None, top_k=_TOP_K
        ):
            if hit.score < _THRESHOLD:
                continue
            meta = hit.metadata if isinstance(hit.metadata, dict) else {}
            cat = str(meta.get("category", ""))
            if cat in _SOURCE_META:
                found.add(cat)
    return found


def _assemble(
    per_cat: dict[str, list[_Exchange]],
) -> dict[str, dict[str, object]]:
    categories: dict[str, dict[str, object]] = {}
    for cat, items in per_cat.items():
        recent = sorted(items, key=lambda e: e.last_used, reverse=True)
        categories[cat] = {
            "count": sum(e.count for e in items),
            "last_used": recent[0].last_used.isoformat() if recent else "",
            "answers": [
                {
                    "text": e.question,
                    "answer": e.answer,
                    "time": e.last_used.isoformat(),
                }
                for e in recent[:_EXAMPLES_PER_SOURCE]
            ],
        }
    return categories


async def main() -> None:
    """Build knowledge_traffic.json from real transcript exchanges."""
    exchanges = await _load_exchanges()
    print(f"pairing {len(exchanges)} unique question/answer exchanges from the transcript...")
    if not exchanges:
        print("no transcript exchanges found; nothing written.")
        return

    vectors = await embed([e.question for e in exchanges])
    per_cat: dict[str, list[_Exchange]] = {cat: [] for cat in _SOURCE_META}
    for exchange, vec in zip(exchanges, vectors, strict=True):
        for cat in await _grounded_categories(vec):
            per_cat[cat].append(exchange)

    categories = _assemble(per_cat)
    payload = {
        "run_at": datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z"),
        "source": "transcript",
        "exchanges": sum(e.count for e in exchanges),
        "questions": len(exchanges),
        "categories": categories,
    }
    path = _traffic_path()
    path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore[attr-defined]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")  # type: ignore[attr-defined]
    grounded = sum(1 for c in categories.values() if c["count"])
    print(f"{grounded}/{len(_SOURCE_META)} sources grounded on real exchanges; wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
