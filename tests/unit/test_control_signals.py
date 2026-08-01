"""Unit tests for the control → catalogue-signal resolver (overview enrichment #1).

The resolver grounds each overview control in the LIVE signal catalogue: the five
catalogued controls get their real signal id/name/category + a drill-down route; the
live policy probes (toxicity, the two refusal faces, the error budget) are honestly
reported as non-catalogued with a reason — never an invented id.

The route assertions carry the operator complaint that produced them: clicking
"Investiguer" on *Calibration des refus* used to land on Vue d'ensemble, the page the
alarm was raised from. A drill-down must name the TAB and the SIGNAL, or it returns you
to where you started.
"""

from __future__ import annotations

from tessera.observability import control_signals as cs_mod

# A fixture catalogue mirroring the real signal names the resolver maps onto.
_FAKE_CATALOGUE: dict[str, object] = {
    "signals": [
        {"id": "SIG-001", "name": "pii_leak_rate", "category": "securite"},
        {"id": "SIG-002", "name": "prompt_injection_bypass", "category": "securite"},
        {"id": "SIG-003", "name": "policy_violation_rate", "category": "conformite"},
        {"id": "SIG-006", "name": "hallucination_rate", "category": "qualite"},
        {"id": "SIG-007", "name": "tool_misuse_rate", "category": "securite"},
    ]
}


def _resolve(monkeypatch) -> dict[str, dict[str, object]]:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cs_mod, "compute_signal_catalogue", lambda _lang: _FAKE_CATALOGUE)
    payload = cs_mod.compute_control_signals("fr")
    return {c["id"]: c for c in payload["controls"]}  # type: ignore[index,union-attr]


def test_catalogued_controls_resolve_to_real_signal(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    by_id = _resolve(monkeypatch)
    faith = by_id["faithfulness"]
    assert faith["signal_id"] == "SIG-006"
    assert faith["signal_name"] == "hallucination_rate"
    assert faith["category"] == "qualite"
    assert faith["route"] == "/surveiller/qualite-ia?tab=signals&signal=slo"
    assert faith["catalogued"] is True
    assert faith["reason"] is None
    assert by_id["pii"]["signal_id"] == "SIG-001"
    assert by_id["firewall"]["signal_name"] == "prompt_injection_bypass"


def test_live_probes_are_honestly_uncatalogued(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    by_id = _resolve(monkeypatch)
    for control_id, reason in (
        ("toxicity", "live_policy_probe"),
        ("refusalOver", "live_calibration_probe"),
        ("refusalUnder", "live_calibration_probe"),
        ("errorBudget", "live_policy_probe"),
    ):
        c = by_id[control_id]
        assert c["catalogued"] is False
        assert c["signal_id"] is None
        assert c["signal_name"] is None
        assert c["reason"] == reason
        # Even a non-catalogued probe still has a real drill-down route.
        assert isinstance(c["route"], str)
        assert c["route"].startswith("/surveiller/")


def test_every_control_present_with_a_route(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    by_id = _resolve(monkeypatch)
    assert set(by_id) == {
        "faithfulness",
        "errorBudget",
        "toxicity",
        "pii",
        "refusalOver",
        "refusalUnder",
        "conformance",
        "tools",
        "firewall",
    }
    assert all(str(c["route"]).startswith("/surveiller/") for c in by_id.values())


def test_every_route_names_a_tab_and_a_signal(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The complaint, as an assertion: a drill-down that lands on a page is not a drill-down.

    Before 2026-08-01 every route was a bare page path, so "Investiguer" on a refusal breach
    opened Vue d'ensemble — the surface that raised the alarm — with the refusal row nowhere
    on it. Naming the tab and the signal is what makes the link go somewhere.
    """
    by_id = _resolve(monkeypatch)
    for control_id, control in by_id.items():
        route = str(control["route"])
        assert "?tab=" in route, f"{control_id} routes to a page, not to a view: {route}"
        assert "&signal=" in route, f"{control_id} names no signal to focus: {route}"


def test_focused_signal_ids_are_the_capability_registry_spellings(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`?signal=` must name a DECLARED signal, or the focus silently does nothing.

    `signalSupports()` on the frontend turns an unknown id into `false`, so a typo here would
    not raise — it would quietly mask the per-agent lens and read as "this signal is org-wide".
    Interrogate the declaration itself rather than a copy of it (ADR 0026).
    """
    from tessera.observability.spine.capabilities import CAPABILITIES

    declared = set(CAPABILITIES)
    for control_id, control in _resolve(monkeypatch).items():
        focused = str(control["route"]).split("&signal=")[1]
        assert focused in declared, (
            f"{control_id} focuses «{focused}», which capabilities.py does not declare — "
            "the lens would silently mask itself"
        )


def test_missing_catalogue_entry_is_not_invented(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # An empty catalogue must not fabricate ids — catalogued controls fall back honest.
    monkeypatch.setattr(cs_mod, "compute_signal_catalogue", lambda _lang: {"signals": []})
    by_id = {c["id"]: c for c in cs_mod.compute_control_signals("fr")["controls"]}
    assert by_id["faithfulness"]["signal_id"] is None
    assert by_id["faithfulness"]["catalogued"] is False
    # The route still resolves (navigation never depends on the catalogue).
    assert by_id["faithfulness"]["route"] == "/surveiller/qualite-ia?tab=signals&signal=slo"
