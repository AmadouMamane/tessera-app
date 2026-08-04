"""The limes secret-egress backend behind the guard's output leg (ADR 0049).

The outbound mirror of :mod:`tessera.guard.limes_backend` (which owns the inbound
injection leg). It adds the one outbound capability Tessera did not have: a
**secret block**. A credential (an AWS/Stripe/GitHub/Google/Slack key, a PEM
private key, a JWT) in the answer never leaves — Tessera had *nothing* for this,
the null control was the state of the art. Detection is delegated to limes'
``secrets-egress`` detector; Tessera keeps no second copy of the rules (ADR 0029).

Scope, and why it is exactly this:

* **Secrets, not PII.** Tessera already masks PII on the outbound leg
  (:func:`tessera.guard.redaction.apply_output_guard` / ``StreamingRedactor`` —
  the very regex baseline limes' ``pii-egress`` was measured against, and the owner
  of the PCI last-four display and the harness cases). Running ``pii-egress`` here
  would either replace that display with a full ``[REDACTED]`` or double-guard with
  ordering hazards, for marginal checksum recall. So this backend runs
  ``secrets-egress`` only; PII stays with the first-party guard.
* **On the RAW answer, before the regex guard.** The regex PII guard's broad IBAN
  shape can graze a substring *inside* a secret (``…ONLY0000…`` reads as an ``LY``
  IBAN) and mangle it, after which the secret rule no longer matches. So the secret
  check must see the answer before the regex touches it — the caller runs this
  first (ADR 0049).

Disposition: a secret ``Deny`` blocks; ``CannotSay`` (a detector that could not
look) blocks — fail-closed, exactly as the inbound leg. There is no redact leg: a
credential is never masked-around, it is withheld whole.

The dependency runs one way only: Tessera imports limes, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from limes.detectors.secrets_egress import SecretsEgressDetector
from limes.transports.in_process import Egress, Guard
from limes.transports.redaction import Action, EgressPolicy, OnEgressFinding
from limes.verdict import CannotSay

__all__ = [
    "EgressOutcome",
    "check_egress",
    "egress_witness",
]


@dataclass(frozen=True, slots=True)
class EgressOutcome:
    """The guard-facing result of one limes secret-egress check.

    Attributes:
        blocked: ``True`` when a secret fired or the detector could not look
            (``CannotSay``); the answer must be withheld, never sent.
        rule: The ``policy_rule`` recorded on the guard decision / audit entry.
        rationale: Human-readable reason, carrying limes' own text.
        policy_hash: SHA-256 of the limes egress policy the detector ran under.
    """

    blocked: bool
    rule: str
    rationale: str
    policy_hash: str


@lru_cache(maxsize=1)
def _policy_hash() -> str:
    """SHA-256 of the packaged limes egress policy the detector runs under."""
    return SecretsEgressDetector().policy_hash


@lru_cache(maxsize=1)
def _guard() -> Guard:
    """Return the process-wide limes secret-egress guard (detector + block once)."""
    secrets = SecretsEgressDetector()
    return Guard(
        [secrets],
        policy_hash=secrets.policy_hash,
        egress=EgressPolicy(
            default=OnEgressFinding.BLOCK,
            by_kind={"secret": OnEgressFinding.BLOCK},
        ),
    )


def egress_witness() -> tuple[str, str]:
    """Return ``(id, version)`` of the live secret-egress detector.

    Proves that limes — not a fallback — produced an egress decision.
    """
    secrets = SecretsEgressDetector()
    return secrets.id, secrets.version


def _outcome(egress: Egress, policy_hash: str) -> EgressOutcome:
    """Map a limes :class:`Egress` to the guard-facing :class:`EgressOutcome`."""
    if egress.action is not Action.BLOCK:
        return EgressOutcome(
            blocked=False,
            rule="egress.limes.allow",
            rationale="limes secret-egress ran and found no credential to block",
            policy_hash=policy_hash,
        )
    if isinstance(egress.verdict, CannotSay):
        return EgressOutcome(
            blocked=True,
            rule="egress.limes.cannot_say",
            rationale=(
                f"limes secret-egress could not see: {egress.reason} "
                "(fail-closed — a blind spot is refused, never passed)"
            ),
            policy_hash=policy_hash,
        )
    return EgressOutcome(
        blocked=True,
        rule="egress.limes.secret.block",
        rationale=f"limes secret-egress blocked the response: {egress.reason}",
        policy_hash=policy_hash,
    )


def check_egress(
    text: str,
    *,
    observed_at: str,
    actor: str | None = None,
    locale: str | None = None,
) -> EgressOutcome:
    """Run the limes secret-egress detector over ``text`` and map the disposition.

    Args:
        text: The outbound content about to reach the user (the RAW final answer,
            before the first-party regex guard, ADR 0049).
        observed_at: ISO-8601 timestamp supplied by the caller (Tessera), never
            ``now()`` inside limes — the decision chain must re-derive on replay.
        actor: The session's asserted identity (``None`` when anonymous); limes
            records it in context.
        locale: Optional locale hint for the content.

    Returns:
        An :class:`EgressOutcome`. ``blocked`` maps a secret ``Deny`` and a
        ``CannotSay`` (fail-closed); the caller withholds the answer on a block.
    """
    egress = _guard().check_egress(text, actor=actor, observed_at=observed_at, locale=locale)
    return _outcome(egress, _policy_hash())
