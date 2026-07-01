"""Backfill ``agent_id`` onto historical Langfuse traces (ADR 0015 §Testing 2).

Stamping is forward-only: traces only carry ``tessera.agent_id`` from the moment the chat
path started stamping the turn's root span (ADR 0015 §Migration B). Older traces have no
attribution, so a per-agent Langfuse filter reads empty for that history. This is the mirror
of ``scripts/backfill_agent_attribution.py`` (which backfills the jsonl stores): it joins a
trace to its conversation and stamps the resolved agent back onto the trace's metadata.

The join is ``trace → conversation_id → transcript.last_agent_for → agent_id``. It is
**honest**: a trace whose conversation cannot be resolved (no conversation id exposed, or the
conversation is not in the transcript) is left org-only, never guessed. It is **idempotent**:
a trace already carrying ``agent_id`` is skipped. It is **best-effort**: an unreachable spine
prints a warning and exits cleanly, never fabricating.

Run from the repo root with the same env the backend uses::

    PYTHONPATH=src:. uv run python scripts/backfill_langfuse_traces.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime

from tessera.memory import transcript

_HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3900")
_PUBLIC = os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-claude-public")
_SECRET = os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-claude-secret")
_TIMEOUT_S = 8.0

# Trace fields that may carry the conversation id, in preference order — OTel maps
# gen_ai.conversation.id / tessera.* onto trace metadata or the sessionId.
_CONVERSATION_KEYS = ("conversation_id", "gen_ai.conversation.id", "conversationId")


def trace_conversation_id(trace: dict[str, object]) -> str | None:
    """Extract a conversation id from a Langfuse trace (metadata / sessionId), or ``None``."""
    session_id = trace.get("sessionId")
    if isinstance(session_id, str) and session_id:
        return session_id
    metadata = trace.get("metadata")
    if isinstance(metadata, dict):
        for key in _CONVERSATION_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def trace_agent_id(trace: dict[str, object]) -> str | None:
    """The agent already stamped on a trace (metadata/tessera), or ``None`` if unattributed."""
    metadata = trace.get("metadata")
    if isinstance(metadata, dict):
        for key in ("agent_id", "tessera.agent_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(f"{_PUBLIC}:{_SECRET}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _fetch_traces(limit: int) -> list[dict[str, object]]:
    url = f"{_HOST}/api/public/traces?limit={max(1, limit)}&orderBy=timestamp.desc"
    request = urllib.request.Request(url, headers=_auth_header())  # noqa: S310 — self-hosted
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:  # noqa: S310
        payload = json.load(response)
    raw = payload.get("data") if isinstance(payload, dict) else None
    return [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []


def _upsert_agent(trace_id: str, agent_id: str) -> None:
    """Stamp ``agent_id`` onto a trace via an idempotent ingestion trace-create (upsert)."""
    event = {
        "id": uuid.uuid4().hex,
        "type": "trace-create",
        "timestamp": datetime.now(UTC).isoformat(),
        "body": {"id": trace_id, "metadata": {"agent_id": agent_id}},
    }
    data = json.dumps({"batch": [event]}).encode()
    request = urllib.request.Request(  # noqa: S310 — self-hosted spine
        f"{_HOST}/api/public/ingestion",
        data=data,
        method="POST",
        headers={**_auth_header(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S):  # noqa: S310
        return


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
    except Exception:
        agent = None
    cache[conversation_id] = agent
    return agent


async def main(limit: int = 500) -> None:
    """Backfill agent attribution onto Langfuse traces and print a summary."""
    try:
        traces = _fetch_traces(limit)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        sys.stderr.write(f"langfuse unreachable at {_HOST}: {exc}\n")
        return

    cache: dict[str, str | None] = {}
    total = len(traces)
    already = 0
    newly = 0
    unresolved = 0
    for trace in traces:
        trace_id = trace.get("id")
        if not isinstance(trace_id, str):
            continue
        if trace_agent_id(trace):
            already += 1
            continue
        agent = await _resolve_agent(trace_conversation_id(trace), cache)
        if agent is None:
            unresolved += 1
            continue
        try:
            _upsert_agent(trace_id, agent)
            newly += 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            sys.stderr.write(f"upsert failed for trace {trace_id}: {exc}\n")

    print(f"langfuse traces: {_HOST}")
    print(f"  total={total} already_tagged={already} newly_tagged={newly} unresolved={unresolved}")


if __name__ == "__main__":
    asyncio.run(main())
