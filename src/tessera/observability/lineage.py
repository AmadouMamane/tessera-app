"""Response lineage / SBOM (ADR 0010, idea #10).

For a regulated agent, "why did it say that on March 3rd?" must be answerable.
Every answer therefore records its full bill of materials: the model that
produced it, a content hash of the active prompt, a content hash of the guard
policy, and the retrieved documents it was grounded in. Hash-versioning the
prompt and policy means a silent edit changes the recorded version.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Lineage", "build_lineage"]

# src/tessera/observability/lineage.py → parents[1] is the tessera package root.
_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "agent" / "prompts"


def _short_hash(path: Path) -> str:
    """Return a short content hash of ``path`` (``"unknown"`` if unreadable)."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "unknown"


@dataclass(frozen=True, slots=True)
class Lineage:
    """The bill of materials behind one answer."""

    model: str
    prompt_version: str
    guard_policy_version: str
    doc_sources: list[str]


def build_lineage(*, language: str, model: str, documents: Sequence[object]) -> Lineage:
    """Assemble the lineage for a turn.

    Args:
        language: The conversation language (selects the prompt file).
        model: The model that produced the answer.
        documents: The retrieved documents grounding the answer (objects with
            ``source``/``chunk_id`` attributes).

    Returns:
        The :class:`Lineage` bill of materials.
    """
    sources: list[str] = []
    for doc in documents:
        source = getattr(doc, "source", None)
        if not source:
            continue
        chunk_id = getattr(doc, "chunk_id", None)
        sources.append(f"{source}#{chunk_id}" if chunk_id else str(source))

    return Lineage(
        model=model,
        prompt_version=_short_hash(_PROMPTS_DIR / f"{language}.yaml"),
        guard_policy_version=_short_hash(get_settings().guard.policy_path),
        doc_sources=sources,
    )
