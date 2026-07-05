"""Metamorphic wiring-proof harness (Phase 1).

Proves that a signal is **WIRED** to its real source: its observable *moves* when
the source moves, and *provably does not* when it should not. The instrument is
metamorphic testing — two relations over the same provider:

1. **Determinism** — ``observe(compute(base))`` twice yields the same scalar. A
   value that drifts on a re-run is noise, not a signal (``NONDETERMINISTIC``).
2. **Source-sensitivity** — a targeted, deterministic ``perturb`` of the source
   moves the observable in a *predicted* direction (``up`` / ``down`` /
   ``changes``) or provably leaves it unchanged (``invariant``).

**The teeth.** A :class:`Probe`'s ``compute`` must reproduce the *route's*
source-assembly — its aliases and freezes — **not** call the naked provider. The
perturbation enters at the seam the route uses (``Probe.seam``). Consequence: a
route-fixed signal (e.g. ``embedding_skew``, whose route sets ``corpus = query``)
stays inert under perturbation and comes out ``DEAD`` — exactly as it should. If a
probe perturbed the *pure function's* argument instead of the real seam, the
harness would lie to itself and rubber-stamp a dead signal as wired.

**Two honest kinds of "unresponsive".** A signal that does not move splits by its
*declared class*, never by a guess:

* declared real (catalogue ``status: active`` / non-synthetic) but inert →
  ``DEAD`` — a bug: it claims to measure something it does not.
* declared ``synthetic`` (``capabilities.py`` / audit class) and inert →
  ``FIXTURE_BY_DESIGN`` — honest: a demonstration fixture, correctly labelled.

See ``docs/design/signal-wiring-map.md`` for the per-signal cartography this
harness executes.
"""

from __future__ import annotations

import asyncio
import inspect
import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Generic, Literal, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "Probe",
    "Relation",
    "Verdict",
    "WiringResult",
    "assert_dead",
    "assert_fixture_by_design",
    "assert_flagged",
    "assert_invariant_ok",
    "assert_wired",
    "evaluate",
]

S = TypeVar("S")

#: The expected effect of a probe's perturbation on its observable.
Relation = Literal["up", "down", "changes", "invariant"]

# Absolute tolerance for scalar comparison. Scores live in 0..1 and counts are
# integers, so a tolerance well below any real delta separates "moved" from noise.
_EPS = 1e-9

# ``declared_class`` values that mark an honest, expected fixture rather than a
# bug-death. Sourced from ``capabilities.py`` (``synthetic=True``) or the audit
# classification — never inferred from the value itself.
_SYNTHETIC_CLASSES = frozenset({"synthetic", "fixture"})


class Verdict(str, Enum):
    """The outcome of evaluating one :class:`Probe`."""

    WIRED = "WIRED"  # relation satisfied — the observable moved as predicted
    INVARIANT_OK = "INVARIANT_OK"  # relation="invariant" held — provably unchanged
    DEAD = "DEAD"  # declared real but inert when movement was expected
    FIXTURE_BY_DESIGN = "FIXTURE_BY_DESIGN"  # declared synthetic and inert — honest
    NONDETERMINISTIC = "NONDETERMINISTIC"  # observe(compute(base)) is not stable
    # Soundness guards (should not fire for a well-designed probe, but must never
    # be silently folded into WIRED/DEAD):
    WRONG_DIRECTION = "WRONG_DIRECTION"  # moved, but not in the predicted direction
    RESPONSIVE_UNEXPECTED = "RESPONSIVE_UNEXPECTED"  # relation="invariant" but it moved


@dataclass(frozen=True, slots=True)
class Probe(Generic[S]):
    """A single wiring claim, evaluated against its *route-faithful* assembly.

    Attributes:
        key: Stable identifier (e.g. ``"output-pii-leak#38"``).
        compute: ``source -> payload``. MUST reproduce the route's source-assembly
            (aliases/freezes included), not call the bare provider. May return a
            coroutine; it is awaited by :func:`evaluate`.
        observe: ``payload -> scalar`` (``bool`` / ``int`` / ``float``) — the one
            number under test.
        base_source: The baseline source.
        perturb: ``base_source -> perturbed source``, the change injected at
            ``seam``. Deterministic.
        relation: The predicted effect on ``observe`` (``up``/``down``/``changes``/
            ``invariant``).
        seam: Where the perturbation enters (``fn-arg`` / ``store`` /
            ``route-fixed``) — documentation of the wiring level under test.
        declared_class: The signal's declared class (``real-computed`` /
            ``real-store`` / ``fixed-corpus-probe`` / ``synthetic`` / ``infra``),
            which decides ``DEAD`` vs ``FIXTURE_BY_DESIGN``.
    """

    key: str
    compute: Callable[[S], object]
    observe: Callable[[object], object]
    base_source: S
    perturb: Callable[[S], S]
    relation: Relation
    seam: str
    declared_class: str


@dataclass(frozen=True, slots=True)
class WiringResult:
    """The verdict and evidence for one evaluated :class:`Probe`."""

    key: str
    verdict: Verdict
    d0: float  # observed baseline scalar
    d1: float  # observed scalar after perturbation
    delta: float  # d1 - d0
    relation: Relation
    seam: str
    declared_class: str
    detail: str


def _run(value: object) -> object:
    """Resolve a compute result, awaiting it if the provider is async."""
    if inspect.iscoroutine(value):
        return cast("object", asyncio.run(value))
    return value


def _scalar(value: object) -> float:
    """Coerce an observable to a float (bool -> 0/1); reject non-scalars."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"observe() must return a scalar (bool/int/float), got {type(value).__name__}")


def _observe(probe: Probe[S], source: S) -> float:
    """Run the route-faithful compute over ``source`` and read the scalar."""
    return _scalar(probe.observe(_run(probe.compute(source))))


def _relation_holds(relation: Relation, d0: float, d1: float) -> bool:
    """Whether ``d1`` relates to ``d0`` as ``relation`` predicts."""
    if relation == "up":
        return d1 > d0 + _EPS
    if relation == "down":
        return d1 < d0 - _EPS
    if relation == "changes":
        return not math.isclose(d0, d1, abs_tol=_EPS)
    return math.isclose(d0, d1, abs_tol=_EPS)  # invariant


def evaluate(probe: Probe[S]) -> WiringResult:
    """Evaluate ``probe``: determinism first, then source-sensitivity.

    Returns:
        A :class:`WiringResult`. The verdict is derived purely from the observed
        movement and the probe's ``declared_class`` — never from a guess about
        whether the signal "should" be real.
    """
    base = probe.base_source
    d0 = _observe(probe, base)
    d0_again = _observe(probe, base)
    if not math.isclose(d0, d0_again, abs_tol=_EPS):
        return WiringResult(
            key=probe.key,
            verdict=Verdict.NONDETERMINISTIC,
            d0=d0,
            d1=d0_again,
            delta=d0_again - d0,
            relation=probe.relation,
            seam=probe.seam,
            declared_class=probe.declared_class,
            detail=f"observe(compute(base)) not stable: {d0:.6g} vs {d0_again:.6g}",
        )

    d1 = _observe(probe, probe.perturb(base))
    delta = d1 - d0
    moved = not math.isclose(d0, d1, abs_tol=_EPS)
    holds = _relation_holds(probe.relation, d0, d1)

    if probe.relation == "invariant":
        verdict = Verdict.INVARIANT_OK if holds else Verdict.RESPONSIVE_UNEXPECTED
    elif holds:
        verdict = Verdict.WIRED
    elif not moved:
        verdict = (
            Verdict.FIXTURE_BY_DESIGN
            if probe.declared_class in _SYNTHETIC_CLASSES
            else Verdict.DEAD
        )
    else:
        verdict = Verdict.WRONG_DIRECTION

    detail = (
        f"d0={d0:.6g} d1={d1:.6g} Δ={delta:+.6g} "
        f"rel={probe.relation} seam={probe.seam} class={probe.declared_class}"
    )
    return WiringResult(
        key=probe.key,
        verdict=verdict,
        d0=d0,
        d1=d1,
        delta=delta,
        relation=probe.relation,
        seam=probe.seam,
        declared_class=probe.declared_class,
        detail=detail,
    )


def assert_wired(probe: Probe[S]) -> WiringResult:
    """Assert the probe proves WIRED; return the result (with deltas)."""
    result = evaluate(probe)
    assert (
        result.verdict is Verdict.WIRED
    ), f"{probe.key}: expected WIRED, got {result.verdict.value} — {result.detail}"
    return result


def assert_invariant_ok(probe: Probe[S]) -> WiringResult:
    """Assert the probe's observable is provably unchanged (relation=invariant)."""
    result = evaluate(probe)
    assert (
        result.verdict is Verdict.INVARIANT_OK
    ), f"{probe.key}: expected INVARIANT_OK, got {result.verdict.value} — {result.detail}"
    return result


def assert_dead(probe: Probe[S]) -> WiringResult:
    """Assert a *declared-real* signal is inert — a wiring bug (DEAD)."""
    result = evaluate(probe)
    assert (
        result.verdict is Verdict.DEAD
    ), f"{probe.key}: expected DEAD, got {result.verdict.value} — {result.detail}"
    return result


def assert_fixture_by_design(probe: Probe[S]) -> WiringResult:
    """Assert a *declared-synthetic* signal is inert — an honest fixture."""
    result = evaluate(probe)
    assert (
        result.verdict is Verdict.FIXTURE_BY_DESIGN
    ), f"{probe.key}: expected FIXTURE_BY_DESIGN, got {result.verdict.value} — {result.detail}"
    return result


def assert_flagged(probe: Probe[S]) -> WiringResult:
    """Meta-assertion for a negative control: it must NOT come out WIRED.

    If a fixture/route-fixed signal is reported WIRED, the harness has no teeth and
    must be repaired before it is trusted to audit the real signals.
    """
    result = evaluate(probe)
    assert result.verdict in {Verdict.DEAD, Verdict.FIXTURE_BY_DESIGN}, (
        f"HARNESS TOOTHLESS: negative control {probe.key} came out "
        f"{result.verdict.value}, expected DEAD or FIXTURE_BY_DESIGN — {result.detail}"
    )
    return result
