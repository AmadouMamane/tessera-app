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
    monkeypatch.setattr(c, "_load_overrides", dict)
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
        lambda: {
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
    assert parallel["value"] == "Desactivee"
    assert payload["tags"]["tags"] == ["x", "y"]
    lang = next(f for f in payload["identity"]["right"] if f.get("key") == "default_language")
    assert lang["value"] == "Anglais"
    summary_lang = next(r for r in payload["summary"]["rows"] if r["label"] == "Langue")
    assert summary_lang["value"] == "Anglais"


def test_editable_flag_separates_real_from_readonly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "_load_overrides", dict)
    payload = c.compute_agent_configurations()
    # The model name is read-only (no key); the fallback strategy is editable.
    model_left = payload["model"]["left"][0]
    assert model_left["editable"] is False
    fallback = next(f for f in payload["model"]["right"] if f.get("key") == "fallback_strategy")
    assert fallback["editable"] is True
