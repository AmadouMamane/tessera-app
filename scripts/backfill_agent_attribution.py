"""Backfill ``agent_id`` onto historical online-eval scores and replay bundles.

Online-eval scores (``scores.jsonl``) and replay bundles (``bundles.jsonl``) only
started carrying ``agent_id`` once the chat path threaded the responding agent into
``emit_score`` / ``capture_bundle``. Rows captured before that have no attribution,
so per-agent SLO / trend / cost would read empty for history.

Each row does carry a ``conversation_id``, and the durable transcript records which
agent answered each conversation (``transcript.last_agent_for``). This one-shot joins
the two and writes ``agent_id`` onto every resolvable row. It is **honest**: a row
whose conversation cannot be resolved (no conversation_id, or the conversation is not
in the transcript) is left with ``agent_id = None`` — org-only, never guessed. It is
**idempotent**: rows already tagged are kept as-is and the join is only run for the
rest, so re-running changes nothing.

Run from the repo root with the same env the backend uses::

    PYTHONPATH=src:. uv run python scripts/backfill_agent_attribution.py
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING

from tessera.memory import transcript
from tessera.observability.eval.scores import _scores_path
from tessera.observability.replay import _bundles_path

if TYPE_CHECKING:
    from pathlib import Path


async def _resolve_agent(conversation_id: str | None, cache: dict[str, str | None]) -> str | None:
    """Resolve a conversation's responding agent, memoised; ``None`` if unknown."""
    if not conversation_id:
        return None
    if conversation_id in cache:
        return cache[conversation_id]
    try:
        parsed = uuid.UUID(conversation_id)
    except ValueError:
        cache[conversation_id] = None
        return None
    try:
        agent = await transcript.last_agent_for(parsed)
    except Exception:  # transcript may be unreachable for a stray row
        agent = None
    cache[conversation_id] = agent
    return agent


async def _backfill_file(path: Path, cache: dict[str, str | None]) -> tuple[int, int, int]:
    """Rewrite ``path`` (a JSONL store) with ``agent_id`` filled where resolvable.

    Returns ``(total_rows, already_tagged, newly_tagged)``.
    """
    if not path.exists():
        return (0, 0, 0)
    rows: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except ValueError:
            # best-effort: skip a malformed JSONL row — non-gating backfill parse (0015)
            continue

    total = len(rows)
    already = sum(1 for r in rows if r.get("agent_id"))
    newly = 0
    for row in rows:
        if row.get("agent_id"):  # idempotent: never overwrite an existing attribution
            continue
        agent = await _resolve_agent(
            row.get("conversation_id") if isinstance(row.get("conversation_id"), str) else None,
            cache,
        )
        # Write the key in both cases so the row's schema is stable; only a real
        # resolution counts as a new attribution.
        row["agent_id"] = agent
        if agent:
            newly += 1

    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row) + "\n")
    tmp.replace(path)
    return (total, already, newly)


async def main() -> None:
    """Backfill both durable stores and print a per-store + per-agent summary."""
    cache: dict[str, str | None] = {}
    for label, path in (("scores", _scores_path()), ("bundles", _bundles_path())):
        total, already, newly = await _backfill_file(path, cache)
        print(f"{label}: {path}")
        print(f"  rows={total} already_tagged={already} newly_tagged={newly}")

    # Per-agent attribution summary across both stores (what the cockpit will read).
    counts: dict[str | None, int] = {}
    for path in (_scores_path(), _bundles_path()):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except ValueError:
                # best-effort: skip a malformed JSONL row in the tally — non-gating (0015)
                continue
            key = row.get("agent_id")
            counts[key] = counts.get(key, 0) + 1
    print("attribution across both stores:")
    for key in sorted(counts, key=lambda k: (k is None, str(k))):
        label = key if key is not None else "<org-only / unresolved>"
        print(f"  {label}: {counts[key]}")


if __name__ == "__main__":
    asyncio.run(main())
