"""Langfuse read adapter — traces & scores by metadata + time window (ADR 0015 §Migration C).

Langfuse owns *LLM detail*: eval scores on a trace, token/cost per call, the conversation
trace. Phase C reads per-agent scores/traces here filtered by ``metadata.agent_id`` + an
as-of-T ``toTimestamp`` window; the cockpit hot path never sums a number from raw traces
(that is Prometheus' job). Aggregates come from Prometheus, detail from Langfuse — never
mixed for the same number.

Self-hosted; the fixed local project keys are the documented env fallback (matching
``docker-compose.obs.claude.yml``) and resolve from Secret Manager in the deployed profile —
the browser never holds a key (only the backend talks to Langfuse). An unreachable Langfuse
raises :class:`SpineUnavailableError` → honest-empty, never a fabricated value.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.stack_components import base_url_for
from tessera.settings import env_setting
from tessera.urlfetch import urlopen_http

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope

__all__ = ["LangfuseAdapter", "LangfuseConfig"]


@dataclass(frozen=True, slots=True)
class LangfuseConfig:
    """Self-hosted Langfuse connection (fixed local keys; Secret Manager in prod)."""

    host: str
    public_key: str
    secret_key: str

    @classmethod
    def from_env(cls) -> LangfuseConfig:
        """Resolve from the environment defaults the Traces card already uses today.

        In the deployed profile (ADR 0014) these same names resolve from Secret Manager,
        never the repo — the backend reads them from the environment either way. Absent an
        injected ``LANGFUSE_HOST`` the address comes from the component's DECLARATION rather
        than a literal of this module's own: three files kept private copies of
        ``http://localhost:3900``, and the deployment that forgot to inject the real one got a
        plausible wrong answer instead of a loud missing one.
        """
        return cls(
            host=base_url_for("langfuse-web", env="LANGFUSE_HOST"),
            public_key=env_setting("LANGFUSE_PUBLIC_KEY", "pk-lf-claude-public"),
            secret_key=env_setting("LANGFUSE_SECRET_KEY", "sk-lf-claude-secret"),
        )


def _matches_agent(metadata: object, agent_id: str | None) -> bool:
    """Whether a row's metadata matches the scope's agent (None = org, matches all)."""
    if agent_id is None:
        return True
    if not isinstance(metadata, dict):
        return False
    return metadata.get("agent_id") == agent_id or metadata.get("tessera.agent_id") == agent_id


class LangfuseAdapter:
    """Query client for Langfuse traces/scores (ADR 0015 §Migration C)."""

    def __init__(self, config: LangfuseConfig | None = None, *, timeout_s: float = 0.8) -> None:
        self._config = config if config is not None else LangfuseConfig.from_env()
        self._timeout_s = timeout_s

    @property
    def config(self) -> LangfuseConfig:
        """The resolved Langfuse connection config (host + local project keys)."""
        return self._config

    def scores_by_metadata(self, scope: Scope, *, limit: int = 500) -> list[dict[str, object]]:
        """Eval scores at/before the scope's instant, filtered client-side by ``agent_id``.

        Langfuse's score list is time-bounded server-side (``toTimestamp``); the ``agent_id``
        metadata match is applied here (metadata is an indexed tag, but the public list API
        filters by name/time, so the dimension match is a bounded client-side pass).
        """
        params: dict[str, str] = {"limit": str(_clamp(limit))}
        if scope.at:
            params["toTimestamp"] = scope.at
        rows = _rows(self._get("/api/public/scores", params))
        return [r for r in rows if _matches_agent(r.get("metadata"), scope.agent_id)]

    def traces(self, scope: Scope, *, limit: int = 100) -> list[dict[str, object]]:
        """Recent traces for the scope, time- and ``limit``-bounded, agent-filtered.

        The window's lower bound is pushed to the API as ``fromTimestamp``, matching the
        upper one it has always sent. Filtering it here instead would silently interact with
        ``limit``: the newest ``limit`` traces get fetched first, so an in-Python floor would
        return fewer rows than the window holds and never say so.
        """
        params: dict[str, str] = {"limit": str(_clamp(limit)), "orderBy": "timestamp.desc"}
        if scope.at:
            params["toTimestamp"] = scope.at
        since, _ = scope.window()
        if since is not None:
            params["fromTimestamp"] = since.isoformat()
        rows = _rows(self._get("/api/public/traces", params))
        return [r for r in rows if _matches_agent(r.get("metadata"), scope.agent_id)]

    def trace_ids_for_conversation(self, conversation_id: str) -> list[str]:
        """Every Langfuse trace id whose ``sessionId`` is this conversation (erasure lookup).

        The turn root span sets ``sessionId = conversation_id`` (Phase C mapping), so a session
        filter recovers exactly the subject's traces — the PII-bearing rows GDPR erasure targets.
        """
        if not conversation_id:
            return []
        rows = _rows(
            self._get("/api/public/traces", {"sessionId": conversation_id, "limit": "100"})
        )
        return [str(row["id"]) for row in rows if row.get("id")]

    def delete_conversation(self, conversation_id: str) -> int:
        """Delete every Langfuse trace (and its scores) for a conversation; return the count.

        The subject's turns live in Langfuse traces (input/output/metadata), so a right-to-erasure
        request (GDPR Art. 17, ADR 0015 §Migration D) must reach here, not only the local file.
        Returns 0 when the subject has no traces (nothing to erase); an unreachable Langfuse
        raises :class:`SpineUnavailableError` so the caller can record it and retry.
        """
        trace_ids = self.trace_ids_for_conversation(conversation_id)
        if not trace_ids:
            return 0
        self._delete("/api/public/traces", {"traceIds": trace_ids})
        return len(trace_ids)

    def _get(self, path: str, params: dict[str, str]) -> dict[str, object]:
        url = f"{self._config.host}{path}?{urllib.parse.urlencode(params)}"
        token = base64.b64encode(
            f"{self._config.public_key}:{self._config.secret_key}".encode()
        ).decode()
        request = urllib.request.Request(  # noqa: S310 — self-hosted spine
            url, headers={"Authorization": f"Basic {token}"}
        )
        try:
            with urlopen_http(request, timeout=self._timeout_s) as response:
                payload = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            msg = f"langfuse unreachable at {self._config.host}: {exc}"
            raise SpineUnavailableError(msg) from exc
        return payload if isinstance(payload, dict) else {}

    def _delete(self, path: str, body: dict[str, object]) -> None:
        url = f"{self._config.host}{path}"
        token = base64.b64encode(
            f"{self._config.public_key}:{self._config.secret_key}".encode()
        ).decode()
        request = urllib.request.Request(  # noqa: S310 — self-hosted spine
            url,
            data=json.dumps(body).encode("utf-8"),
            method="DELETE",
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen_http(request, timeout=self._timeout_s):
                return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            msg = f"langfuse delete failed at {self._config.host}: {exc}"
            raise SpineUnavailableError(msg) from exc


def _clamp(limit: int) -> int:
    """Langfuse's public list API caps page size at 100 — a larger limit 400s."""
    return min(max(1, limit), 100)


def _rows(payload: dict[str, object]) -> list[dict[str, object]]:
    data = payload.get("data")
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
