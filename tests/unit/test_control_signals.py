"""Unit tests for the control → catalogue-signal resolver (overview enrichment #1).

The resolver grounds each overview control in the LIVE signal catalogue: the five
catalogued controls get their real signal id/name/category + a drill-down route; the
two live policy probes (toxicity, refusal) are honestly reported as non-catalogued
with a reason — never an invented id.
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
    assert faith["route"] == "/surveiller/qualite-ia"
    assert faith["catalogued"] is True
    assert faith["reason"] is None
    assert by_id["pii"]["signal_id"] == "SIG-001"
    assert by_id["firewall"]["signal_name"] == "prompt_injection_bypass"


def test_live_probes_are_honestly_uncatalogued(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    by_id = _resolve(monkeypatch)
    for control_id, reason in (
        ("toxicity", "live_policy_probe"),
        ("refusal", "live_calibration_probe"),
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
        "toxicity",
        "pii",
        "refusal",
        "conformance",
        "tools",
        "firewall",
    }
    assert all(str(c["route"]).startswith("/surveiller/") for c in by_id.values())


def test_missing_catalogue_entry_is_not_invented(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # An empty catalogue must not fabricate ids — catalogued controls fall back honest.
    monkeypatch.setattr(cs_mod, "compute_signal_catalogue", lambda _lang: {"signals": []})
    by_id = {c["id"]: c for c in cs_mod.compute_control_signals("fr")["controls"]}
    assert by_id["faithfulness"]["signal_id"] is None
    assert by_id["faithfulness"]["catalogued"] is False
    # The route still resolves (navigation never depends on the catalogue).
    assert by_id["faithfulness"]["route"] == "/surveiller/qualite-ia"
