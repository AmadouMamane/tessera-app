"""Unit tests for the Agent Configurations payload + persistence logic.

Exercise the coercion, the defaults-over-overrides merge and the editable-field
descriptors without touching the durable file (``_load_overrides`` is
monkeypatched). ``compute_agent_configurations`` reads repo-backed settings but
no DB, so it runs in the unit suite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability import agent_configurations as c

if TYPE_CHECKING:
    import pytest


def test_coerce_types() -> None:
    assert c._coerce("parallel_tools", "yes") is True
    assert c._coerce("parallel_tools", False) is False
    assert c._coerce("name", 123) == "123"
    assert c._coerce("tags", ["a", "b"]) == ["a", "b"]
    assert c._coerce("tags", "notalist") == c._DEFAULTS["tags"]


def test_coerce_clamps_sliders() -> None:
    assert c._coerce("temperature", 5.0) == 1.0  # clamped to max 1.0
    assert c._coerce("temperature", -1.0) == 0.0
    assert c._coerce("frequency_penalty", 5.0) == 2.0  # max 2.0
    assert c._coerce("temperature", "bad") == c._DEFAULTS["temperature"]


def test_available_keys_include_language() -> None:
    keys = c.available_config_keys()
    assert "default_language" in keys
    assert "temperature" in keys
    assert "tags" in keys


def test_compute_uses_defaults_when_no_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = c.compute_agent_configurations()
    tone = next(s for s in payload["behavior"]["selects"] if s["key"] == "tone")
    assert tone["value"] == "Professionnel"
    assert tone["editable"] is True
    assert "Amical" in tone["options"]
    temp = next(s for s in payload["behavior"]["sliders"] if s["key"] == "temperature")
    assert temp["num"] == 0.3
    assert temp["pct"] == 30


def test_compute_merges_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        c,
        "_load_overrides",
        lambda *_a: {
            "tone": "Amical",
            "temperature": 5.0,  # out of range -> clamped to 1.0
            "parallel_tools": False,
            "tags": ["x", "y"],
            "default_language": "Anglais",
        },
    )
    payload = c.compute_agent_configurations()
    tone = next(s for s in payload["behavior"]["selects"] if s["key"] == "tone")
    assert tone["value"] == "Amical"
    temp = next(s for s in payload["behavior"]["sliders"] if s["key"] == "temperature")
    assert temp["num"] == 1.0  # clamped
    assert temp["pct"] == 100
    parallel = next(f for f in payload["routing"]["right"] if f.get("key") == "parallel_tools")
    assert parallel["value"] == "Désactivée"
    assert payload["tags"]["tags"] == ["x", "y"]
    lang = next(f for f in payload["identity"]["right"] if f.get("key") == "default_language")
    assert lang["value"] == "Anglais"
    summary_lang = next(r for r in payload["summary"]["rows"] if r["label"] == "Langue")
    assert summary_lang["value"] == "Anglais"


def test_editable_flag_separates_real_from_readonly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = c.compute_agent_configurations()
    # The model name is read-only (no key); the fallback strategy is editable.
    model_left = payload["model"]["left"][0]
    assert model_left["editable"] is False
    fallback = next(f for f in payload["model"]["right"] if f.get("key") == "fallback_strategy")
    assert fallback["editable"] is True


def test_change_log_records_only_real_changes(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    state: dict[str, object] = {}
    log: list[dict[str, object]] = []
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: dict(state))
    monkeypatch.setattr(c, "_save_overrides", lambda s, *_a: state.update(s))
    monkeypatch.setattr(c, "_load_change_log", lambda: list(log))
    monkeypatch.setattr(c, "_history_path", lambda: Path(str(tmp_path)) / "h.json")

    def _capture(keys: list[str], *_a: object) -> None:
        if keys:
            log.insert(0, {"at": "2026-06-17T08:00:00+02:00", "keys": keys})

    monkeypatch.setattr(c, "_record_change", _capture)

    c.set_agent_config({"tone": "Amical"})
    assert log[0]["keys"] == ["tone"]
    # Saving the same value again records nothing (no real change).
    log.clear()
    c.set_agent_config({"tone": "Amical"})
    assert log == []


def test_build_history_is_real_sources_only() -> None:
    from tessera.settings import get_settings

    items = c._build_history(get_settings().guard.policy_path)
    assert items, "real config file mtimes should always yield rows"
    # No invented actor: every row is either a console save or a Git source.
    assert all(it["actor"] in {"Console", "Dépôt (Git)"} for it in items)
    assert any("mis à jour" in it["label"] for it in items)


def test_model_section_is_read_only_with_a_registry_link() -> None:
    payload = c.compute_agent_configurations()
    model = payload["model"]
    # The model itself is read-only here (defined in the registry), never editable.
    for field in [*model["left"], *model["right"]]:  # type: ignore[index]
        if field["label"].startswith(("Modèle", "Version")):
            assert field["editable"] is False
    # Only the fallback strategy is editable, and it is a bounded select.
    strat = next(f for f in model["right"] if f.get("key") == "fallback_strategy")  # type: ignore[index]
    assert strat["kind"] == "select"
    assert model["link"]["href"] == "/configurer/modeles"  # type: ignore[index]


def test_governed_flag_tracks_production() -> None:
    # Local dev is not governed; the flag exists for the prod release-control flow.
    assert c.compute_agent_configurations()["governed"] is False
