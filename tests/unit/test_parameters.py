"""The Parameters overview must derive every value from live config, not literals.

These assertions recompute the expected numbers from the same real sources
(:func:`get_settings`, :func:`load_policy`, the model catalogue) and check the
payload matches — so the test proves *derivation*, never a hard-coded snapshot.
"""

from __future__ import annotations

from tessera.guard.decisions import load_policy
from tessera.observability.model_catalogue import available_model_ids
from tessera.observability.parameters import compute_parameters_overview
from tessera.settings import get_settings


def _kpi(payload: dict[str, object], key: str) -> str:
    for k in payload["kpis"]:  # type: ignore[union-attr]
        if k["key"] == key:  # type: ignore[index]
            return str(k["value"])  # type: ignore[index]
    raise AssertionError(f"missing KPI {key}")


def test_kpis_are_derived_from_the_live_policy_and_catalogue() -> None:
    policy = load_policy()
    n_deny = len(policy.prompt_injection_deny)
    n_transforms = len(policy.prompt_injection_transforms)
    n_pii = len(policy.pii_patterns)
    n_tools = len(policy.tools)
    n_security = n_deny + n_transforms + n_pii
    n_policies = n_tools + n_security

    payload = compute_parameters_overview("fr")

    assert _kpi(payload, "policies") == str(n_policies)
    assert _kpi(payload, "security_rules") == str(n_security)
    assert _kpi(payload, "models") == str(len(available_model_ids()))
    # Every KPI is a real integer count (never a fabricated "1 284"-style literal).
    for k in payload["kpis"]:
        assert str(k["value"]).isdigit()  # type: ignore[index]


def test_config_version_and_footer_track_the_real_policy() -> None:
    policy = load_policy()
    settings = get_settings()
    payload = compute_parameters_overview("fr")

    cv = payload["config_version"]
    assert cv["version"] == f"policy v{policy.version}"  # type: ignore[index]
    assert cv["env"] == settings.environment.value.capitalize()  # type: ignore[index]
    assert payload["footer"]["version"] == f"policy v{policy.version}"  # type: ignore[index]


def test_recent_params_carry_the_actual_settings_values() -> None:
    settings = get_settings()
    payload = compute_parameters_overview("fr")
    by_name = {p["name"]: p["value"] for p in payload["recent_params"]}  # type: ignore[index,union-attr]

    assert by_name["memory.backend"] == settings.memory.backend
    assert by_name["memory.history_window"] == str(settings.memory.history_window)
    assert by_name["api.rate_limit_chat"] == settings.api.rate_limit_chat
    assert by_name["guard.fail_closed"] == str(settings.guard.fail_closed).lower()


def test_config_state_sums_to_configured_and_is_all_active() -> None:
    payload = compute_parameters_overview("fr")
    configured = int(_kpi(payload, "configured"))
    state = payload["config_state"]
    assert state["total"] == configured  # type: ignore[index]
    slices = {s["key"]: s["count"] for s in state["slices"]}  # type: ignore[index,union-attr]
    # Every live parameter is active; there is no draft/deprecated store (honest).
    assert slices["active"] == configured
    assert slices["inactive"] == 0
    assert slices["drafts"] == 0
    assert slices["deprecated"] == 0


def test_usage_policies_and_tool_allowlist_are_real() -> None:
    settings = get_settings()
    policy = load_policy()
    payload = compute_parameters_overview("fr")
    values = [u["value"] for u in payload["usage_policies"]]  # type: ignore[index,union-attr]

    assert settings.api.rate_limit_chat in values
    assert settings.api.rate_limit_chat_global in values
    assert f"{len(policy.tools)} outils" in values


def test_localization_switches_the_usage_policy_labels() -> None:
    fr = compute_parameters_overview("fr")
    de = compute_parameters_overview("de")
    en = compute_parameters_overview("en")
    # The free-text labels are localized; the derived values stay identical.
    fr_label = fr["usage_policies"][0]["name"]  # type: ignore[index]
    de_label = de["usage_policies"][0]["name"]  # type: ignore[index]
    en_label = en["usage_policies"][0]["name"]  # type: ignore[index]
    assert fr_label != de_label != en_label
    assert fr["usage_policies"][0]["value"] == en["usage_policies"][0]["value"]  # type: ignore[index]


def test_models_configured_come_from_the_real_catalogue() -> None:
    payload = compute_parameters_overview("fr")
    models = payload["models_configured"]  # type: ignore[index]
    names = {m["name"] for m in models}  # type: ignore[index,union-attr]
    # Exactly the catalogue's known model ids — no invented model list.
    assert names == available_model_ids()
    # Every role is a real enum value; at least one model serves under the profile.
    assert all(m["role"] in ("chat", "embedding") for m in models)  # type: ignore[index]
    active = {m["name"] for m in models if m["status"] == "active"}  # type: ignore[index]
    assert active and active <= names
