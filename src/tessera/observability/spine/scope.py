"""The first-class ``Scope`` value object (ADR 0015).

``Scope`` is the set of dimension filters a cockpit signal is read under. It is parsed
**once** per request (server: from query params via :meth:`Scope.from_query`; client:
from the URL via ``lib/scope.ts``) and generalises ADR 0011's as-of-T: the temporal
``at`` is one dimension of ``Scope``, not a separate mechanism. Adding a dimension later
(``language``, ``model``, ``environment``) is a field here, not a route sweep.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["Dimension", "Scope"]

_ALL_AGENTS = "all"  # the deduplicated org view (mirrors ``lib/agent-scope`` on the front)


class Dimension(str, Enum):
    """A slicing dimension a signal may or may not support."""

    AGENT = "agent"
    TIME = "time"
    LANGUAGE = "language"
    MODEL = "model"
    ENVIRONMENT = "environment"


@dataclass(frozen=True, slots=True)
class Scope:
    """An immutable set of dimension filters over the dimensioned fact model.

    ``agent_id`` of ``None`` is the org view (all agents, deduplicated). ``at`` of
    ``None`` is live; a set ``at`` is an as-of-T window end (ADR 0011). ``language`` /
    ``model`` / ``environment`` are additional filters (wired into the UI in Phase F).
    """

    at: str | None = None
    agent_id: str | None = None
    language: str | None = None
    model: str | None = None
    environment: str | None = None

    @classmethod
    def from_query(cls, params: Mapping[str, str | None]) -> Scope:
        """Parse a ``Scope`` from request query params.

        ``agent`` of ``"all"`` / empty maps to the org view (``agent_id=None``); any
        other value is a concrete agent id. ``at`` is the as-of-T instant. Blank values
        are dropped so a filter is never silently the empty string.

        Args:
            params: A mapping of query-param name to its raw string value (or ``None``).

        Returns:
            The parsed, normalised :class:`Scope`.
        """

        def _clean(value: str | None) -> str | None:
            if value is None:
                return None
            trimmed = value.strip()
            return trimmed or None

        agent_raw = _clean(params.get("agent"))
        agent_id = None if agent_raw is None or agent_raw == _ALL_AGENTS else agent_raw
        return cls(
            at=_clean(params.get("at")),
            agent_id=agent_id,
            language=_clean(params.get("language")),
            model=_clean(params.get("model")),
            environment=_clean(params.get("environment")),
        )

    @property
    def agent_param(self) -> str:
        """The ``?agent=`` wire value: the id, or ``"all"`` for the org view."""
        return self.agent_id if self.agent_id is not None else _ALL_AGENTS

    @property
    def filters(self) -> frozenset[Dimension]:
        """The dimensions this scope actively constrains (each with a non-None value)."""
        active: set[Dimension] = set()
        if self.at is not None:
            active.add(Dimension.TIME)
        if self.agent_id is not None:
            active.add(Dimension.AGENT)
        if self.language is not None:
            active.add(Dimension.LANGUAGE)
        if self.model is not None:
            active.add(Dimension.MODEL)
        if self.environment is not None:
            active.add(Dimension.ENVIRONMENT)
        return frozenset(active)

    def narrow_to(self, supported: frozenset[Dimension]) -> Scope:
        """Drop every filter the signal does not declare.

        This is what makes an unsupported dimension *impossible* to silently apply: the
        registry narrows the request scope to a signal's declared dimensions before the
        read, so a per-agent filter can never reach an org-wide signal's read path.
        """
        return Scope(
            at=self.at if Dimension.TIME in supported else None,
            agent_id=self.agent_id if Dimension.AGENT in supported else None,
            language=self.language if Dimension.LANGUAGE in supported else None,
            model=self.model if Dimension.MODEL in supported else None,
            environment=(self.environment if Dimension.ENVIRONMENT in supported else None),
        )

    def to_labels(self) -> dict[str, str]:
        """A label selector for the spine (Prometheus / Langfuse) — only set dimensions.

        The temporal ``at`` is *not* a label (it is a time-range bound, applied by the
        adapter), so it is intentionally absent here.
        """
        labels: dict[str, str] = {}
        if self.agent_id is not None:
            labels["agent_id"] = self.agent_id
        if self.language is not None:
            labels["language"] = self.language
        if self.model is not None:
            labels["model"] = self.model
        if self.environment is not None:
            labels["environment"] = self.environment
        return labels

    def key(self) -> str:
        """A stable, order-independent cache key for this scope (null-safe)."""
        return "|".join(
            f"{name}={value or ''}"
            for name, value in (
                ("at", self.at),
                ("agent", self.agent_id),
                ("lang", self.language),
                ("model", self.model),
                ("env", self.environment),
            )
        )
