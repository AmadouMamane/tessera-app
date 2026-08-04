"""Closure tests for fixtures presented as real data.

Audit 2026-07-10, P0 ``fixture-as-real``:

- ``compliance_tabs.py`` declares itself "fixed, deterministic fixture data" for seven
  governance catalogues, but ``signal-registry.ts`` never registered ``compliance`` and
  the dashboard never rendered a provenance notice — while ``incidents-overview.tsx``
  renders it five times. The right pattern existed; it was not applied to the most
  regulatorily sensitive surface in the product.
- ``observability.py:1087`` serves "Historique de session agent" — a KPI strip, a trend
  and a score distribution that are fixed — as live operator telemetry.

Both fail against the pre-fix tree, where neither signal was declared at all
(``capability_for`` raises / ``isSynthetic`` returns ``False`` for an unknown id).

The over-flagging guard below matters as much as the flags themselves: the audit's
shorthand fix was ``compliance: cap(ORG, {synthetic: true})``, which would have stamped
"deterministic fixture" on a posture that ``compliance.py`` genuinely derives from real
runtime signals. Calling real data fake is the same class of dishonesty as the reverse.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.spine.capabilities import SignalProvenance, capability_for

if TYPE_CHECKING:
    import pytest


def test_compliance_catalogue_tabs_are_declared_synthetic() -> None:
    """The seven governance catalogues are fixtures and must be declared as such."""
    assert capability_for("compliance_catalog").synthetic is True
    assert capability_for("compliance_catalog").provenance is SignalProvenance.REFERENCE


def test_derived_compliance_posture_is_not_flagged_as_a_fixture() -> None:
    """Guard against over-flagging: the overview posture is really derived, not invented.

    ``compliance.py`` maps each control status from a real runtime signal (AI-Act
    obligations, schema conformance, citation validity, PII screening, refusal
    calibration, GDPR erasure coverage, firewall efficacy) against a threshold.
    Flagging it synthetic would be a lie in the other direction.
    """
    assert capability_for("compliance").synthetic is False


def test_agent_session_history_is_declared_synthetic() -> None:
    """The eval-session half of the history page is a fixture shaped like telemetry."""
    assert capability_for("agent_historique").synthetic is True
    assert capability_for("agent_historique").provenance is SignalProvenance.EVALUATION


async def test_the_history_route_stamps_its_fixture_half(monkeypatch: pytest.MonkeyPatch) -> None:
    """The served payload says it is a fixture — the UI can no longer read it as live.

    This is the assertion that actually closes the finding: before the fix the payload
    carried KPI/trend/distribution blocks with no marker at all, so the operator UI
    presented fixed numbers in the shape of telemetry.
    """
    # The handler moved to the `pii` surface module (audit 2026-07-12, F-4): its
    # `live_conversations` block is real transcript data, and a conversation `title` is the
    # customer's opening message — so the route now sits behind `require_subject_reader`.
    # Patch it where it lives, and call it through the package root re-export, as callers do.
    # (The guard is declared on the router, so a direct call still exercises the payload —
    # which is what this test is about; the refusal itself is proven in
    # `test_subject_reads_carry_auth.py`.)
    from tessera.api.routes import observability
    from tessera.api.routes.observability import pii

    async def _no_conversations(agent_id: str, limit: int = 50) -> list[object]:
        return []

    monkeypatch.setattr(pii.transcript, "list_conversations", _no_conversations)

    payload = await observability.observability_agent_historique(agent_id="tessera-support")

    assert payload["available"] is True
    assert payload["synthetic"] is True
    # The real half stays real, and separately labelled — the stamp must not smear it.
    assert payload["live_conversations"] == []
