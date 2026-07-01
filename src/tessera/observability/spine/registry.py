"""Signal registry: capability-declared reads with an honoured/ignored report (ADR 0015).

A :class:`SignalSpec` binds a signal id to its declared capability and a ``read``
coroutine. Reading a signal **narrows** the request ``Scope`` to what the signal supports
and returns a :class:`ScopeReport` of what was honoured vs ignored — so the UI can badge an
unsupported filter instead of silently dropping it (make illegal states unrepresentable).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from tessera.observability.spine.adapters import SpineUnavailableError
from tessera.observability.spine.capabilities import CAPABILITIES, SignalCapability
from tessera.observability.spine.scope import Dimension, Scope

__all__ = [
    "ReadFn",
    "ScopeReport",
    "SignalRegistry",
    "SignalResult",
    "SignalSpec",
    "get_registry",
]

ReadFn = Callable[[Scope], Awaitable[object]]

# Per-signal upstream timeout: a slow/unreachable spine yields an honest-empty ``unavailable``
# signal rather than blocking the snapshot (ADR 0015 §Performance 7).
DEFAULT_TIMEOUT_S = 0.8


@dataclass(frozen=True, slots=True)
class SignalSpec:
    """A registered signal: its capability declaration + how to read it."""

    id: str
    capability: SignalCapability
    read: ReadFn

    @property
    def dimensions(self) -> frozenset[Dimension]:
        """The dimensions this signal declares support for."""
        return self.capability.dimensions

    @property
    def synthetic(self) -> bool:
        """Whether this signal is a deterministic fixture rather than real data."""
        return self.capability.synthetic


@dataclass(frozen=True, slots=True)
class ScopeReport:
    """What a read honoured / ignored — the data the UI badges from."""

    signal_id: str
    honoured: frozenset[Dimension]
    ignored: frozenset[Dimension]
    org_wide: bool
    synthetic: bool
    source: str
    unavailable: bool = False

    def as_dict(self) -> dict[str, object]:
        """Serialise the report for the snapshot payload / UI badges."""
        return {
            "honoured": sorted(d.value for d in self.honoured),
            "ignored": sorted(d.value for d in self.ignored),
            "org_wide": self.org_wide,
            "synthetic": self.synthetic,
            "source": self.source,
            "unavailable": self.unavailable,
        }


@dataclass(frozen=True, slots=True)
class SignalResult:
    """A signal's data plus the honesty report of how its scope was applied."""

    signal_id: str
    data: object
    report: ScopeReport

    def as_dict(self) -> dict[str, object]:
        """Serialise ``{data, report}`` for one signal in the snapshot payload."""
        return {"data": self.data, "report": self.report.as_dict()}


class SignalRegistry:
    """The declared signal set. Reads narrow scope to declared dimensions and report."""

    def __init__(self) -> None:
        self._specs: dict[str, SignalSpec] = {}

    def register(self, signal_id: str, read: ReadFn) -> None:
        """Register ``signal_id`` with its declared capability and read coroutine.

        Raises:
            KeyError: if ``signal_id`` has no capability declaration (every signal must
                declare its dimensions to be readable).
        """
        capability = CAPABILITIES.get(signal_id)
        if capability is None:
            msg = f"signal {signal_id!r} has no declared capability"
            raise KeyError(msg)
        self._specs[signal_id] = SignalSpec(id=signal_id, capability=capability, read=read)

    def get(self, signal_id: str) -> SignalSpec:
        """The registered spec for ``signal_id`` (raises ``KeyError`` if absent)."""
        return self._specs[signal_id]

    def ids(self) -> tuple[str, ...]:
        """Every registered signal id."""
        return tuple(self._specs)

    def registered(self, signal_id: str) -> bool:
        """Whether ``signal_id`` has a registered read."""
        return signal_id in self._specs

    def _report(self, spec: SignalSpec, scope: Scope, *, unavailable: bool) -> ScopeReport:
        supported = spec.dimensions
        return ScopeReport(
            signal_id=spec.id,
            honoured=scope.filters & supported,
            ignored=scope.filters - supported,
            org_wide=Dimension.AGENT not in supported,
            synthetic=spec.synthetic,
            source=spec.capability.source,
            unavailable=unavailable,
        )

    async def read(
        self, signal_id: str, scope: Scope, *, timeout_s: float = DEFAULT_TIMEOUT_S
    ) -> SignalResult:
        """Read one signal, narrowing scope to its declared dimensions.

        On timeout or an unreachable spine the data is ``None`` and the report is marked
        ``unavailable`` — an honest-empty state, never a fabricated zero.
        """
        spec = self.get(signal_id)
        narrowed = scope.narrow_to(spec.dimensions)
        unavailable = False
        data: object = None
        try:
            data = await asyncio.wait_for(spec.read(narrowed), timeout=timeout_s)
        except (TimeoutError, SpineUnavailableError):
            unavailable = True
        except Exception as exc:
            unavailable = True
            sys.stderr.write(f"tessera.spine.read[{signal_id}]: {exc}\n")
        return SignalResult(signal_id, data, self._report(spec, scope, unavailable=unavailable))


_registry: SignalRegistry | None = None


def get_registry() -> SignalRegistry:
    """The process-wide signal registry (populated by :mod:`spine.signals` on import)."""
    global _registry
    if _registry is None:
        _registry = SignalRegistry()
        # Import for the registration side effect; deferred to avoid an import cycle
        # (signals imports the registry).
        from tessera.observability.spine import signals as _signals

        _signals.register_all(_registry)
    return _registry
