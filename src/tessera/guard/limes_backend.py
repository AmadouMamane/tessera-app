"""The limes injection-detection backend behind the guard seam (ADR 0028/0029).

Tessera consumes ``limes`` as the **single source of truth** for prompt-injection
detection (ADR 0029, "phase 2: Tessera consumes limes"). The regex patterns that
used to live in ``guard/policy.yaml`` were extracted into limes' own policy — the
``origin: tessera`` rules are those very patterns, and limes adds the
``origin: limes`` rules that close the measured hole (case
``08_prompt_injection_beneficiaire``: a ``SYSTEM:`` directive hidden inside a
quoted payee name). Tessera no longer keeps its own copy; it calls this module.

This is the declared backend the seam (:mod:`tessera.guard.adapter`, ADR 0028)
was built for. It maps a limes :class:`~limes.verdict.Verdict` to the guard's
allow/block decision under one non-negotiable rule inherited from limes and from
Tessera's own doctrine (ADR 0026/0027):

* ``Deny``      -> blocked (an injection was found);
* ``CannotSay`` -> **blocked** (fail-closed — a detector that could not look is a
  blind spot to refuse on, never a reason to pass);
* ``Allow``     -> allowed (the detector ran and found nothing).

The dependency runs one way only: Tessera imports limes, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from limes.detector import Context, Direction
from limes.detectors.injection import InjectionDetector
from limes.guard import decide
from limes.policy import InjectionPolicy, load_injection_policy
from limes.verdict import Allow, CannotSay, Deny

if TYPE_CHECKING:
    import re

__all__ = [
    "InjectionOutcome",
    "check_injection",
    "injection_rules",
    "injection_witness",
]


@dataclass(frozen=True, slots=True)
class InjectionOutcome:
    """The guard-facing result of one limes injection check.

    Attributes:
        blocked: ``True`` for ``Deny`` and ``CannotSay`` (fail-closed), ``False``
            only for ``Allow``.
        rule: The ``policy_rule`` recorded on the guard decision / audit entry.
        rationale: Human-readable reason, carrying the limes verdict's own text.
        detector_id: The limes detector that ran (``"injection"``).
        detector_version: Its version — pinned into the measurement's evidence.
        policy_hash: SHA-256 of the limes policy the detector ran under.
    """

    blocked: bool
    rule: str
    rationale: str
    detector_id: str
    detector_version: str
    policy_hash: str


@lru_cache(maxsize=1)
def _injection_policy() -> InjectionPolicy:
    """Return the process-wide compiled limes injection policy (loaded once)."""
    return load_injection_policy()


@lru_cache(maxsize=1)
def _detector() -> InjectionDetector:
    """Return the process-wide limes injection detector (policy compiled once)."""
    return InjectionDetector(_injection_policy())


def injection_rules() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Return ``(label, compiled pattern)`` for every limes injection rule.

    For surfaces that must report the RAW match location — e.g. RAG-poison
    forensics (:mod:`tessera.observability.corpus_injection`), which shows the
    operator *what* poisoned a chunk — that limes' detector deliberately redacts.
    The patterns are limes' own, the single source of truth (ADR 0029); this is
    the same rule set the detector runs, not a Tessera copy.
    """
    return tuple((rule.label, rule.pattern) for rule in _injection_policy().rules)


def injection_witness() -> tuple[str, str, str]:
    """Return ``(detector_id, detector_version, policy_hash)`` of the live detector.

    The badge and the efficacy report use this to prove that limes — not a
    fallback, not a bare package install — is the detector that produced a
    measurement.
    """
    detector = _detector()
    return detector.id, detector.version, detector.policy_hash


def check_injection(
    text: str,
    *,
    observed_at: str,
    actor: str | None = None,
    locale: str | None = None,
) -> InjectionOutcome:
    """Run the limes injection detector over ``text`` and map its verdict.

    Args:
        text: The raw user input to inspect (inbound leg).
        observed_at: ISO-8601 timestamp supplied by the caller (Tessera), never
            ``now()`` inside limes — the decision chain must re-derive on replay.
        actor: The session's asserted identity (``None`` when anonymous); the
            injection detector does not read it, but limes records it in context.
        locale: Optional locale hint for the content.

    Returns:
        An :class:`InjectionOutcome`. ``CannotSay`` maps to ``blocked=True``
        (fail-closed): a blind spot is never a pass.
    """
    detector = _detector()
    ctx = Context(policy_hash=detector.policy_hash, actor=actor, locale=locale)
    verdict = decide(Direction.INBOUND, text, ctx, [detector], observed_at=observed_at)

    if isinstance(verdict, Deny):
        return InjectionOutcome(
            blocked=True,
            rule="injection.limes.deny",
            rationale=f"limes injection detector: {verdict.reason}",
            detector_id=detector.id,
            detector_version=detector.version,
            policy_hash=detector.policy_hash,
        )
    if isinstance(verdict, CannotSay):
        return InjectionOutcome(
            blocked=True,
            rule="injection.limes.cannot_say",
            rationale=(
                f"limes injection detector could not see: {verdict.blind_spot} "
                "(fail-closed — a blind spot is refused, never passed)"
            ),
            detector_id=detector.id,
            detector_version=detector.version,
            policy_hash=detector.policy_hash,
        )
    if isinstance(verdict, Allow):
        return InjectionOutcome(
            blocked=False,
            rule="injection.limes.allow",
            rationale="limes injection detector ran and found no injection",
            detector_id=detector.id,
            detector_version=detector.version,
            policy_hash=detector.policy_hash,
        )
    # Unreachable: Verdict is a closed union (Allow | Deny | CannotSay).
    raise AssertionError(f"unexpected limes verdict type: {type(verdict).__name__}")
