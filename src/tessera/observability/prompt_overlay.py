"""Per-agent system-prompt overlay with a two-person lifecycle (ADR 0037).

The YAML bundles remain the only home of the core system prompt. This store
holds the governed *overlay* — per-agent complementary directives — through a
propose (operator) → review (superadmin) lifecycle:

* a proposal is screened by the SAME injection guard that screens user input
  (limes, ADR 0029) at proposal time — a refused draft is never stored;
* only the APPROVED overlay ever serves (``resolve_prompt_overlay``, read at
  the chat routing seam);
* self-approval is refused — the reviewer must not be the proposer;
* approving an EMPTY draft is the governed way to retire the overlay.

Durable JSON next to the guard audit log, same pattern as the agent-config
store. Every transition names its author (ADR 0024) and lands in a capped
history; the governance-journal emission is the ROUTE's job.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final
from zoneinfo import ZoneInfo

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "MAX_OVERLAY_CHARS",
    "OverlayGuardRefusedError",
    "OverlayNotPendingError",
    "SelfApprovalError",
    "load_overlay_state",
    "propose_overlay",
    "resolve_prompt_overlay",
    "review_overlay",
]

_PARIS = ZoneInfo("Europe/Paris")
_HISTORY_LIMIT: Final = 20
MAX_OVERLAY_CHARS: Final = 2000

_REVIEW_ACTIONS: Final = ("approve", "reject", "revoke")


class OverlayGuardRefusedError(ValueError):
    """The injection guard refused the proposed text — refused, never stored."""


class OverlayNotPendingError(KeyError):
    """A review of a draft that does not exist — nothing changed, said loudly."""


class SelfApprovalError(PermissionError):
    """The reviewer is the proposer — a two-person rule with one person is none."""


def _store_path() -> Path:
    return get_settings().guard.audit_file.parent / "agent_prompt_overlay.json"


def _now() -> str:
    return datetime.now(_PARIS).isoformat()


def _load_all() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_all(store: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(store, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )


def load_overlay_state(agent_id: str = DEFAULT_AGENT_ID) -> dict[str, Any]:
    """The agent's overlay state: ``draft``, ``approved``, capped ``history``."""
    bucket = _load_all().get(agent_id, {})
    if not isinstance(bucket, dict):
        bucket = {}
    return {
        "draft": bucket.get("draft"),
        "approved": bucket.get("approved"),
        "history": list(bucket.get("history", []))[:_HISTORY_LIMIT],
    }


def _record(bucket: dict[str, Any], event: str, author: str, chars: int) -> None:
    history = [
        {"at": _now(), "event": event, "author": author, "chars": chars},
        *bucket.get("history", []),
    ]
    bucket["history"] = history[:_HISTORY_LIMIT]


def propose_overlay(agent_id: str, text: str, *, author: str) -> dict[str, Any]:
    """Store a draft overlay proposal (operator act, ADR 0037 §2).

    The text is screened by the SAME limes-backed injection guard that screens
    user input, at proposal time — fail-closed: a refused draft raises and is
    never stored. An empty text is a legal proposal (it proposes retirement).

    Raises:
        OverlayGuardRefusedError: The guard refused the text.
        ValueError: The text exceeds :data:`MAX_OVERLAY_CHARS`.
    """
    text = text.strip()
    if len(text) > MAX_OVERLAY_CHARS:
        raise ValueError(f"overlay text exceeds {MAX_OVERLAY_CHARS} characters — refused")
    if text:
        # Lazy import: guard.adapter pulls the agent package; keep this module
        # import-light (the audit-run circular-import trap).
        from tessera.guard.adapter import check_user_input

        check = check_user_input(text)
        if not check.allowed:
            raise OverlayGuardRefusedError(
                "the injection guard refused this overlay text — refused, never stored"
            )
    store = _load_all()
    bucket = store.get(agent_id)
    if not isinstance(bucket, dict):
        bucket = {}
    bucket["draft"] = {"text": text, "author": author, "at": _now()}
    _record(bucket, "proposed", author, len(text))
    store[agent_id] = bucket
    _save_all(store)
    return load_overlay_state(agent_id)


def review_overlay(agent_id: str, action: str, *, reviewer: str) -> dict[str, Any]:
    """Decide a pending draft, or revoke the serving overlay (superadmin act).

    ``approve`` promotes the draft (an empty draft retires the overlay);
    ``reject`` discards it; ``revoke`` retires the serving overlay with no
    draft involved. Self-approval is refused (ADR 0037 §2).

    Raises:
        ValueError: Unknown ``action``.
        OverlayNotPendingError: approve/reject with no pending draft.
        SelfApprovalError: The reviewer authored the pending draft.
    """
    if action not in _REVIEW_ACTIONS:
        raise ValueError(f"unknown review action {action!r} — one of {_REVIEW_ACTIONS}")
    store = _load_all()
    bucket = store.get(agent_id)
    if not isinstance(bucket, dict):
        bucket = {}
    draft = bucket.get("draft")
    if action == "revoke":
        bucket["approved"] = None
        _record(bucket, "revoked", reviewer, 0)
    else:
        if not isinstance(draft, dict):
            raise OverlayNotPendingError(agent_id)
        if action == "approve":
            if str(draft.get("author")) == reviewer:
                raise SelfApprovalError(
                    "the reviewer proposed this draft — a two-person rule needs two people"
                )
            text = str(draft.get("text", "")).strip()
            bucket["approved"] = (
                {
                    "text": text,
                    "author": str(draft.get("author", "")),
                    "approved_by": reviewer,
                    "at": _now(),
                }
                if text
                else None  # approving an empty draft is the governed retirement
            )
            _record(bucket, "approved", reviewer, len(text))
        else:
            _record(bucket, "rejected", reviewer, len(str(draft.get("text", ""))))
        bucket["draft"] = None
    store[agent_id] = bucket
    _save_all(store)
    return load_overlay_state(agent_id)


def resolve_prompt_overlay(agent_id: str = DEFAULT_AGENT_ID) -> str | None:
    """The APPROVED overlay text serving this agent, or ``None`` (ADR 0037 §3).

    Read once per turn at the routing seam. Fail-open to no overlay, loudly —
    the chat path never goes down for a knob, and the frozen base prompt is
    always valid on its own.
    """
    try:
        approved = load_overlay_state(agent_id).get("approved")
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.prompt_overlay: resolve: {exc}\n")
        return None
    if isinstance(approved, dict):
        text = str(approved.get("text", "")).strip()
        return text or None
    return None
