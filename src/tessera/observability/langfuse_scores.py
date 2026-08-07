"""Best-effort Langfuse mirror of GATING scores via the official SDK (ADR 0015 §Amend.1-2).

Langfuse is **not** a home of any score fact: the gating socle lives in owned Postgres
(§Amendment 2, Nature 1) and the online firehose in owned ClickHouse (§Correction 2b —
online rows get **no** score mirror; their *trace* already lives in Langfuse/Phoenix and
carries the drill-down). This module is the sync leg the amendments kept: it mirrors each
release-gating verdict as a Langfuse score for drill-down UX, using the **official SDK**
("voie 1", proven 2026-07-02 — the hand-rolled ingestion POST returned 201 yet never
materialised and is gone).

Anchoring: harness rows carry no trace, so each score anchors on ``session_id = run_id``
— the run's real identity, listable via Langfuse's v2 scores API (proven live: a
session-anchored score materialises and lists; an anchorless one is rejected 400). A
stable ``score_id`` (UUID5 of the unique gating key) makes re-mirroring idempotent, so
the boot-time sweep and backfill can re-send freely.

Strictly best-effort: never blocks or raises into the caller (the SDK batches on its own
background thread; ``flush()`` is the caller's option at CLI exit). Disabled with
``TESSERA_LANGFUSE_SCORES=0``; the unit suite stubs the client and stays offline.
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import TYPE_CHECKING, Any, Literal, Protocol

from tessera.observability.stack_components import base_url_for
from tessera.settings import env_setting

if TYPE_CHECKING:
    from tessera.observability.eval.gating_scores import GatingScoreRow

__all__ = ["flush_mirror", "gating_score_id", "mirror_gating_rows"]

# Fixed namespace for deterministic score ids — never regenerate, or dedup breaks.
_SCORE_NS = uuid.UUID("6f9c2d1e-8a4b-4f3a-9b6d-2e1c5a7d0b43")


class _ScoreClient(Protocol):
    """The one SDK surface this mirror uses (kept narrow so tests stub it flat)."""

    def create_score(
        self,
        *,
        name: str,
        value: float,
        session_id: str,
        score_id: str,
        data_type: Literal["NUMERIC", "CATEGORICAL", "BOOLEAN", "TEXT"],
        comment: str | None,
        metadata: dict[str, object],
    ) -> None: ...

    def flush(self) -> None: ...


class _SdkClient:
    """Thin wrapper pinning the SDK to the narrow protocol surface (strict-typed seam)."""

    def __init__(self, sdk: Any) -> None:  # the SDK's own type is overload-heavy
        self._sdk = sdk

    def create_score(
        self,
        *,
        name: str,
        value: float,
        session_id: str,
        score_id: str,
        data_type: Literal["NUMERIC", "CATEGORICAL", "BOOLEAN", "TEXT"],
        comment: str | None,
        metadata: dict[str, object],
    ) -> None:
        self._sdk.create_score(
            name=name,
            value=value,
            session_id=session_id,
            score_id=score_id,
            data_type=data_type,
            comment=comment,
            metadata=metadata,
        )

    def flush(self) -> None:
        self._sdk.flush()


_client: _ScoreClient | None = None


def _enabled() -> bool:
    """Whether score mirroring is on. Defaults on; set the env flag to ``0`` to disable."""
    return os.environ.get("TESSERA_LANGFUSE_SCORES", "1").lower() not in {"0", "false", "no", "off"}


def gating_score_id(row: GatingScoreRow) -> str:
    """Deterministic Langfuse score id for a gating row (stable across re-mirrors)."""
    key = f"{row.run_id}|{row.case_id}|{row.language}|{row.metric}"
    return str(uuid.uuid5(_SCORE_NS, key))


def _get_client() -> _ScoreClient | None:
    """The lazy SDK singleton — never constructed while disabled or under unit tests."""
    global _client
    if _client is not None:
        return _client
    try:
        from langfuse import Langfuse

        _client = _SdkClient(
            Langfuse(
                host=base_url_for("langfuse-web", env="LANGFUSE_HOST"),
                public_key=env_setting("LANGFUSE_PUBLIC_KEY", "pk-lf-claude-public"),
                secret_key=env_setting("LANGFUSE_SECRET_KEY", "sk-lf-claude-secret"),
            )
        )
    except Exception as exc:  # missing SDK/creds — mirroring is enrichment, never fatal
        sys.stderr.write(f"tessera.langfuse_scores: mirror unavailable: {exc}\n")
        return None
    return _client


def set_client(client: _ScoreClient | None) -> None:
    """Override the SDK client (tests inject a stub; ``None`` resets the singleton)."""
    global _client
    _client = client


def flush_mirror() -> None:
    """Drain the SDK batch if a client exists (CLI exits — backfill/sweep tools)."""
    if _client is not None:
        try:
            _client.flush()
        except Exception as exc:  # draining is best-effort, like everything here
            sys.stderr.write(f"tessera.langfuse_scores: flush failed: {exc}\n")


def mirror_gating_rows(rows: list[GatingScoreRow], *, flush: bool = False) -> int:
    """Mirror gating rows as session-anchored Langfuse scores; return the count handed off.

    Best-effort by construction: disabled, SDK-less, or unreachable → 0, never a raise.
    ``flush=True`` drains the SDK batch before returning (for CLI exits — the runner);
    the API path leaves batching to the SDK's background thread.
    """
    if not rows or not _enabled():
        return 0
    client = _get_client()
    if client is None:
        return 0
    mirrored = 0
    try:
        for row in rows:
            client.create_score(
                name=row.metric,
                value=row.score,
                session_id=row.run_id,
                score_id=gating_score_id(row),
                data_type="NUMERIC",
                comment=row.case_id,
                metadata={
                    "agent_id": row.agent_id,
                    "language": row.language,
                    "model": row.model,
                    "case_id": row.case_id,
                    "catalogue_version": row.catalogue_version,
                    "passed": row.passed,
                },
            )
            mirrored += 1
        if flush:
            client.flush()
    except Exception as exc:  # a mirror hiccup must never surface into the write path
        sys.stderr.write(f"tessera.langfuse_scores: mirror failed after {mirrored}: {exc}\n")
    return mirrored
