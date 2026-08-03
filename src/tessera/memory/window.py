"""Tier 0 — the sliding-window memory backend (the default).

The window keeps the last ``history_window`` user/assistant messages verbatim
and remembers nothing beyond the live thread. For the short conversations
typical of retail-banking support this is not a fallback but the *right*
default: it is lossless (no summary model to distort amounts or citations) and
free (no extra storage, no extra model call).

This module also owns the **format-directive stripping** that prevents a
one-shot instruction ("answer in two lines") from one turn bleeding into every
later turn through the injected history. That policy lives here, with the
recency policy, rather than in the reporter — the reporter only renders what a
backend returns.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Final

from tessera.memory.protocol import EntityLedger, MemoryContext
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.agent.state import ConversationMessage
    from tessera.memory.protocol import MemoryScope, TurnRecord

__all__ = ["WindowBackend", "strip_format_directives"]


# The unit a length directive is counted in. It used to be `\w+` — any word at all — so
# "you must answer in 30 days as required by GDPR Art. 12" had "answer in 30 days" cut out of
# it, and the model was handed a regulatory deadline with its deadline removed. A directive
# is only a directive when it counts something a *reply* is measured in.
_FORMAT_UNIT: Final[str] = (
    r"(?:lignes?|mots?|phrases?|caractères?|points?"
    r"|lines?|words?|sentences?|characters?|bullets?"
    r"|Zeilen?|Wörtern?|Sätzen?|Zeichen|Stichpunkten?)"
)

# Patterns that express format/length constraints in historical user messages.
# Stripped before injection so past one-shot instructions don't leak forward.
_FORMAT_DIRECTIVE_RE: Final[re.Pattern[str]] = re.compile(
    r"(\s*[-,;—]?\s*)?"
    r"("
    rf"réponds?\s+en\s+\d+\s+{_FORMAT_UNIT}"  # FR: réponds en 2 lignes / mots
    r"|réponse\s+courte"
    r"|en\s+bref"
    r"|brièvement"
    rf"|answer\s+in\s+\d+\s+{_FORMAT_UNIT}"  # EN: answer in 2 lines / words
    r"|briefly"
    r"|short\s+answer"
    rf"|antworte\s+in\s+\d+\s+{_FORMAT_UNIT}"  # DE: antworte in 2 Zeilen
    r"|kurze\s+Antwort"
    r"|in\s+\d+\s+Zeilen?"
    r")",
    re.IGNORECASE,
)


def strip_format_directives(content: str) -> str:
    """Remove format/length directives from a historical user message."""
    return _FORMAT_DIRECTIVE_RE.sub("", content).strip()


class WindowBackend:
    """Sliding-window backend — Tier 0, the default :class:`MemoryBackend`."""

    def __init__(self, *, history_window: int | None = None) -> None:
        """Initialise with an explicit window, or read it from settings.

        Args:
            history_window: Number of prior user/assistant messages to keep
                verbatim. When ``None``, ``settings.memory.history_window`` is
                used (read once at construction).
        """
        self._window = (
            history_window if history_window is not None else get_settings().memory.history_window
        )

    async def load(
        self,
        *,
        scope: MemoryScope,  # noqa: ARG002  part of the Protocol; unused at Tier 0
        messages: Sequence[ConversationMessage],
        query: str,  # noqa: ARG002  used by long-term tiers, not here
    ) -> MemoryContext:
        """Return the last ``history_window`` prior turns, directives stripped.

        The current user turn is the final element of ``messages`` and is
        excluded here — the reporter appends it separately as the live prompt.
        """
        prior = [m for m in messages[:-1] if m.role in ("user", "assistant")]
        windowed = prior[-self._window :] if self._window else []
        recent = [
            replace(m, content=strip_format_directives(m.content)) if m.role == "user" else m
            for m in windowed
        ]
        return MemoryContext(recent_verbatim=recent, summary=None, entities=EntityLedger())

    async def record(self, *, scope: MemoryScope, turn: TurnRecord) -> None:
        """No-op — the window retains nothing beyond the live thread."""

    async def forget(self, *, scope: MemoryScope) -> None:
        """No-op — there is no durable state to erase at Tier 0."""
