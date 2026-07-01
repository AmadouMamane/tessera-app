"""Best-effort Langfuse score emission (ADR 0015 §Migration B).

Mirrors each online-eval verdict as a Langfuse **score** on the turn's trace, so eval
quality is queryable per-trace in Langfuse — filterable by ``agent_id`` / ``language`` /
``model`` (the dimensions carried in the score metadata). It is strictly best-effort: the
durable score log (``scores.jsonl`` → Prometheus / the spine) stays the system of record;
Langfuse is an *additional* index for trace-level drill-down.

Safety: emission never blocks or raises into the turn. The POST runs on a short-lived
daemon thread with a small timeout and swallows every error, so a slow or absent spine
degrades silently — never a fabricated score, never a stalled response. When there is no
recording trace (``trace_id is None``, e.g. offline unit tests), it is a no-op, so the
existing suite stays offline and fast.

Credentials are the self-hosted local project keys already present in the env (matching
``docker-compose.obs.claude.yml``); in a deployed profile they resolve from Secret Manager.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from uuid import uuid4

__all__ = ["build_score_event", "emit_langfuse_score"]

_HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3900")
_PUBLIC = os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-claude-public")
_SECRET = os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-claude-secret")
_TIMEOUT_S = float(os.environ.get("TESSERA_LANGFUSE_SCORE_TIMEOUT", "1.5"))


def _enabled() -> bool:
    """Whether score mirroring is on. Defaults on; set the env flag to ``0`` to disable."""
    return os.environ.get("TESSERA_LANGFUSE_SCORES", "1").lower() not in {"0", "false", "no", "off"}


def build_score_event(
    *,
    trace_id: str,
    name: str,
    value: float,
    agent_id: str | None,
    language: str | None,
    model: str | None,
    comment: str | None,
) -> dict[str, object]:
    """Build the Langfuse ingestion ``score-create`` event (pure — unit-testable)."""
    metadata: dict[str, object] = {}
    if agent_id:
        metadata["agent_id"] = agent_id
    if language:
        metadata["language"] = language
    if model:
        metadata["model"] = model
    body: dict[str, object] = {
        "traceId": trace_id,
        "name": name,
        "value": value,
        "dataType": "NUMERIC",
    }
    if comment:
        body["comment"] = comment
    if metadata:
        body["metadata"] = metadata
    return {
        "id": uuid4().hex,
        "type": "score-create",
        "timestamp": datetime.now(UTC).isoformat(),
        "body": body,
    }


def _post(event: dict[str, object]) -> None:
    payload = json.dumps({"batch": [event]}).encode()
    token = base64.b64encode(f"{_PUBLIC}:{_SECRET}".encode()).decode()
    request = urllib.request.Request(  # noqa: S310 — fixed local/self-hosted spine URL
        f"{_HOST}/api/public/ingestion",
        data=payload,
        method="POST",
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S):  # noqa: S310
            return
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        # Best-effort: a slow/absent spine must never surface — the durable log is canonical.
        return


def emit_langfuse_score(
    *,
    trace_id: str | None,
    name: str,
    value: float,
    agent_id: str | None = None,
    language: str | None = None,
    model: str | None = None,
    comment: str | None = None,
) -> None:
    """Mirror one eval verdict as a Langfuse score on its trace (best-effort, non-blocking).

    A no-op when there is no recording trace or when disabled. Otherwise the POST runs on a
    daemon thread so ``emit_score`` returns immediately.
    """
    if trace_id is None or not _enabled():
        return
    event = build_score_event(
        trace_id=trace_id,
        name=name,
        value=value,
        agent_id=agent_id,
        language=language,
        model=model,
        comment=comment,
    )
    threading.Thread(target=_post, args=(event,), daemon=True).start()
