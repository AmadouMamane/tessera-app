"""Resolve the overview "Contrôles critiques" rows to their real catalogue signal.

Each control on the SURVEILLER Vue d'ensemble
(``webapp/frontend/components/overview/overview-dashboard.tsx`` ``buildControls``)
measures a signal. This module grounds each control in the **live signal
catalogue** (``signal_catalogue.compute_signal_catalogue``) so the cockpit can show
the real technical signal id / name + a drill-down to its investigation surface —
the normative "Action recommandée / Case" intent, realised honestly as navigation.

Honesty (Tessera positioning, never a fixture): the control → catalogue-signal
**name** association is a factual mapping (the *faithfulness* control measures the
``hallucination_rate`` signal). The signal **id** and **category** are read from the
live catalogue at request time, so they cannot drift into a lie. Two controls —
*toxicity* and *refusal* — are **live policy probes** that are deliberately NOT in
the eval catalogue; they are reported as ``catalogued: false`` with an honest reason,
never an invented id.
"""

from __future__ import annotations

from tessera.observability.signal_catalogue import compute_signal_catalogue

__all__ = ["compute_control_signals"]

# Stable display order — mirrors buildControls() on the frontend.
_CONTROL_ORDER: tuple[str, ...] = (
    "faithfulness",
    "toxicity",
    "pii",
    "refusal",
    "conformance",
    "tools",
    "firewall",
)

# Control → its catalogue signal NAME (the stable key; the SIG-id is positional and
# resolved live). Only the eval-catalogued controls appear here.
_CONTROL_SIGNAL_NAME: dict[str, str] = {
    "faithfulness": "hallucination_rate",
    "pii": "pii_leak_rate",
    "conformance": "policy_violation_rate",
    "tools": "tool_misuse_rate",
    "firewall": "prompt_injection_bypass",
}

# Control → a REAL existing SURVEILLER investigation route (drill-down). Every
# control gets one, even the non-catalogued probes (the page exists regardless).
_CONTROL_ROUTE: dict[str, str] = {
    "faithfulness": "/surveiller/qualite-ia",
    "toxicity": "/surveiller/securite-privacy",
    "pii": "/surveiller/securite-privacy",
    "refusal": "/surveiller/qualite-ia",
    "conformance": "/surveiller/conformite",
    "tools": "/surveiller/securite-privacy",
    "firewall": "/surveiller/securite-privacy",
}

# Why a control has no catalogue entry (honest, shown as a tooltip).
_CONTROL_REASON: dict[str, str] = {
    "toxicity": "live_policy_probe",
    "refusal": "live_calibration_probe",
}


def compute_control_signals(lang: str = "fr") -> dict[str, object]:
    """Map each overview control to its live-catalogue signal + drill-down route.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the catalogue lookup.

    Returns:
        A JSON-serialisable mapping ``{"controls": [...]}``; each entry carries the
        control ``id``, the resolved ``signal_id`` / ``signal_name`` / ``category``
        (``None`` when the control is a non-catalogued live probe), the real
        drill-down ``route`` and a ``catalogued`` flag (+ a ``reason`` when false).
    """
    catalogue = compute_signal_catalogue(lang)
    signals = catalogue.get("signals", [])
    by_name: dict[str, dict[str, object]] = {}
    if isinstance(signals, list):
        for sig in signals:
            if isinstance(sig, dict):
                by_name[str(sig.get("name", ""))] = sig

    controls: list[dict[str, object]] = []
    for control_id in _CONTROL_ORDER:
        name = _CONTROL_SIGNAL_NAME.get(control_id)
        sig = by_name.get(name) if name else None
        controls.append(
            {
                "id": control_id,
                "signal_id": sig.get("id") if sig else None,
                "signal_name": name if sig else None,
                "category": sig.get("category") if sig else None,
                "route": _CONTROL_ROUTE[control_id],
                "catalogued": sig is not None,
                "reason": None if sig else _CONTROL_REASON.get(control_id),
            }
        )
    return {"controls": controls}
