"""Backfill the durable citation counters from *real* Phoenix retrieval spans.

The live source of per-source citation rates is now Postgres: every real
retrieval records one query plus its cited categories
(:func:`tessera.retrieval.citations.record_retrieval_query`), and the Sources &
memory dashboard reads those counters back. This script is the **backfill /
repair tool**: it reconstructs the per-day counters from the ``retrieve
<corpus>`` spans real agent turns emitted into Phoenix, so history captured
before the counters existed (or lost data) can be rebuilt.

The reconstruction is idempotent — each day present in Phoenix is *replaced*
(see :func:`tessera.retrieval.citations.backfill_daily`). Do not run it for the
current day while live writes are accumulating there.

Run (collector + Phoenix up, after some real /chat turns)::

    PYTHONPATH=.:src .venv/bin/python -m scripts.phoenix_retrieval

Environment:
    PHOENIX_BASE_URL    Phoenix base URL (default http://localhost:16006).
    PHOENIX_PROJECT     Phoenix project name (default "default").
    PHOENIX_LOOKBACK_H  Only count spans started within the last N hours
                        (default: all spans in the project).
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta

import httpx

from tessera.observability.knowledge import _SOURCE_META
from tessera.observability.semconv import TESSERA_RETRIEVAL_CATEGORIES
from tessera.retrieval import citations

_RETRIEVAL_ATTR = TESSERA_RETRIEVAL_CATEGORIES
_PAGE = 1000


def _base_url() -> str:
    return os.environ.get("PHOENIX_BASE_URL", "http://localhost:16006").rstrip("/")


def _project() -> str:
    return os.environ.get("PHOENIX_PROJECT", "default")


def _cutoff() -> datetime | None:
    raw = os.environ.get("PHOENIX_LOOKBACK_H")
    if not raw:
        return None
    return datetime.now(UTC) - timedelta(hours=float(raw))


def _span_day(span: dict[str, object], cutoff: datetime | None) -> date | None:
    """Return the span's UTC start date, or ``None`` if missing/older than cutoff."""
    raw = span.get("start_time")
    if not isinstance(raw, str):
        return None
    try:
        started = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if cutoff is not None and started < cutoff:
        return None
    return started.astimezone(UTC).date()


def _fetch_retrieval_spans(
    client: httpx.Client, cutoff: datetime | None
) -> list[tuple[date, list[str]]]:
    """Return ``(day, cited_categories)`` per retrieval span.

    Pages through the Phoenix REST span API and keeps only spans carrying the
    ``tessera.retrieval.categories`` attribute — the agent's real retrieval
    queries. The attribute is a comma-joined, already-thresholded category list.
    """
    url = f"{_base_url()}/v1/projects/{_project()}/spans"
    cursor: str | None = None
    out: list[tuple[date, list[str]]] = []
    while True:
        params: dict[str, str | int] = {"limit": _PAGE}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(url, params=params)
        resp.raise_for_status()
        body = resp.json()
        for span in body.get("data", []):
            attrs = span.get("attributes", {})
            if _RETRIEVAL_ATTR not in attrs:
                continue
            day = _span_day(span, cutoff)
            if day is None:
                continue
            raw = str(attrs.get(_RETRIEVAL_ATTR, ""))
            cats = [c for c in raw.split(",") if c in _SOURCE_META]
            out.append((day, cats))
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return out


def _aggregate_by_day(
    spans: list[tuple[date, list[str]]],
) -> dict[date, tuple[int, int, dict[str, int]]]:
    """Group spans into ``day -> (queries, queries_with_hit, hits_by_category)``."""
    queries: Counter[date] = Counter()
    with_hit: Counter[date] = Counter()
    hits: dict[date, Counter[str]] = defaultdict(Counter)
    for day, cats in spans:
        queries[day] += 1
        cited = set(cats)
        if cited:
            with_hit[day] += 1
        for cat in cited:
            hits[day][cat] += 1
    return {day: (queries[day], with_hit[day], dict(hits[day])) for day in queries}


async def _backfill(per_day: dict[date, tuple[int, int, dict[str, int]]]) -> None:
    await citations.ensure_citation_schema()
    for day in sorted(per_day):
        queries, with_hit, hits = per_day[day]
        await citations.backfill_daily(
            day, queries=queries, queries_with_hit=with_hit, hits=dict(hits)
        )


def main() -> None:
    """Query Phoenix, reconstruct per-day citation counters, and backfill Postgres."""
    cutoff = _cutoff()
    with httpx.Client(timeout=30.0) as client:
        spans = _fetch_retrieval_spans(client, cutoff)

    if not spans:
        sys.stderr.write(
            "no retrieval spans found in Phoenix - run some real /chat turns first "
            "(and check PHOENIX_BASE_URL / PHOENIX_LOOKBACK_H). Nothing backfilled.\n"
        )
        raise SystemExit(1)

    per_day = _aggregate_by_day(spans)
    asyncio.run(_backfill(per_day))
    total = sum(q for q, _, _ in per_day.values())
    print(f"backfilled {total} real retrieval spans across {len(per_day)} day(s) into Postgres")
    for day in sorted(per_day):
        queries, with_hit, hits = per_day[day]
        print(f"  {day}: {queries} queries, {with_hit} with a hit, {len(hits)} categories cited")


if __name__ == "__main__":
    main()
