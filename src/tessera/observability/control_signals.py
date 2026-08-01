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

# Stable display order — mirrors OVERVIEW_CONTROLS in overview-dashboard.tsx.
#
# `refusal` became two rows on 2026-08-01: over-refusal (a legitimate question turned away,
# a utility cost) and under-refusal (a forbidden request carried out, a safety incident) are
# opposite failures, and the collapsed row rendered their maximum under a label naming neither.
# `error_budget` joined them: the overview used to colour the faithfulness row from
# `slo.breaching`, a multi-window burn-rate alarm it never displayed.
_CONTROL_ORDER: tuple[str, ...] = (
    "faithfulness",
    "errorBudget",
    "toxicity",
    "pii",
    "refusalOver",
    "refusalUnder",
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

# Control → the REAL surface that INVESTIGATES it, down to the tab and the focused signal.
#
# Until 2026-08-01 these were bare page paths, and the operator's complaint was exact:
# clicking "Investiguer" on *Calibration des refus* landed on Vue d'ensemble — the page the
# alarm was raised FROM — with the refusal row nowhere in sight. A drill-down that returns you
# to where you started is not navigation, it is a link that looks like one.
#
# Every route now names the tab (`?tab=`) and the signal to focus (`?signal=`, read by
# `webapp/frontend/lib/signal-focus.ts`, which re-plans the per-agent breakdown around it). The
# signal ids are the capability-registry spellings, the same strings `capabilities.py` declares
# — not the camelCase UI keys, so a rename on one side cannot silently produce a dead anchor.
_QUALITY = "/surveiller/qualite-ia?tab=signals&signal="
_CONTROL_ROUTE: dict[str, str] = {
    "faithfulness": f"{_QUALITY}slo",
    "errorBudget": f"{_QUALITY}error_budget",
    "toxicity": f"{_QUALITY}toxicity",
    "pii": f"{_QUALITY}pii_leak",
    "refusalOver": f"{_QUALITY}refusal_over",
    "refusalUnder": f"{_QUALITY}refusal_under",
    "conformance": f"{_QUALITY}conformance",
    "tools": f"{_QUALITY}tool_validity",
    "firewall": f"{_QUALITY}firewall",
}

# Why a control has no catalogue entry (honest, shown as a tooltip).
_CONTROL_REASON: dict[str, str] = {
    "toxicity": "live_policy_probe",
    "refusalOver": "live_calibration_probe",
    "refusalUnder": "live_calibration_probe",
    "errorBudget": "live_policy_probe",
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
