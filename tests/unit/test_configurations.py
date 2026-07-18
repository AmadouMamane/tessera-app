"""Unit tests for the Agent Configurations payload + persistence logic.

Exercise the coercion, the defaults-over-overrides merge and the editable-field
descriptors without touching the durable file (``_load_overrides`` is
monkeypatched). ``compute_agent_configurations`` reads repo-backed settings but
no DB, so it runs in the unit suite — the ADR 0031 runtime-effectiveness block
(which WOULD read the override store) is stubbed hermetic here; its own logic
is covered in ``test_sampling_effective.py``.
"""

from __future__ import annotations

import pytest

from tessera.observability import agent_configurations as c


@pytest.fixture(autouse=True)
def _hermetic_serving(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep compute() off the real override store (ADR 0030 read is a DB read)."""

    async def _stub(_slug: str) -> tuple[str, str, tuple[str, ...], str]:
        return (
            "llama3.2:3b",
            "ollama",
            ("temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty"),
            "base",
        )

    monkeypatch.setattr(c, "_serving_effectiveness", _stub)


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
    # ADR 0032 — top-k is integer-valued: rounded on save, clamped to [0, 100].
    assert c._coerce("top_k", 40.6) == 41.0
    assert c._coerce("top_k", 500) == 100.0


def test_coerce_none_means_unset() -> None:
    # ADR 0031 — None is "unset": the parameter is not sent, the backend
    # default serves. It is a legal stored value for every slider.
    assert c._coerce("temperature", None) is None
    assert c._coerce("top_p", None) is None
    # An unparseable value on a None-default slider stays unset, never invented.
    assert c._coerce("top_p", "bad") is None


def test_available_keys_include_language() -> None:
    keys = c.available_config_keys()
    assert "default_language" in keys
    assert "temperature" in keys
    assert "tags" in keys


async def test_compute_uses_defaults_when_no_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = await c.compute_agent_configurations()
    tone = next(s for s in payload["behavior"]["selects"] if s["key"] == "tone")
    assert tone["value"] == "Professionnel"
    assert tone["editable"] is True
    assert "Amical" in tone["options"]
    # ADR 0031 — the displayed default is the RUNTIME truth (0.2), and the
    # unset sliders say so instead of inventing a number.
    temp = next(s for s in payload["behavior"]["sliders"] if s["key"] == "temperature")
    assert temp["num"] == 0.2
    assert temp["pct"] == 20
    assert temp["unset"] is False
    assert temp["overridden"] is False
    top_p = next(s for s in payload["behavior"]["sliders"] if s["key"] == "top_p")
    assert top_p["unset"] is True
    assert "num" not in top_p
    assert top_p["value"] == "Défaut backend"


async def test_compute_merges_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
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
    payload = await c.compute_agent_configurations()
    tone = next(s for s in payload["behavior"]["selects"] if s["key"] == "tone")
    assert tone["value"] == "Amical"
    temp = next(s for s in payload["behavior"]["sliders"] if s["key"] == "temperature")
    assert temp["num"] == 1.0  # clamped
    assert temp["pct"] == 100
    assert temp["overridden"] is True
    parallel = next(f for f in payload["routing"]["right"] if f.get("key") == "parallel_tools")
    assert parallel["value"] == "Désactivée"
    assert payload["tags"]["tags"] == ["x", "y"]
    lang = next(f for f in payload["identity"]["right"] if f.get("key") == "default_language")
    assert lang["value"] == "Anglais"
    summary_lang = next(r for r in payload["summary"]["rows"] if r["label"] == "Langue")
    assert summary_lang["value"] == "Anglais"


async def test_runtime_block_names_backend_and_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    # ADR 0031 §4 — the page derives which sliders the serving backend applies
    # and says which do not, instead of letting a slider pretend.
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})

    async def _vertex(_slug: str) -> tuple[str, str, tuple[str, ...], str]:
        return "gemini-2.0-flash", "vertex-ai", ("temperature", "top_p", "top_k"), "org"

    monkeypatch.setattr(c, "_serving_effectiveness", _vertex)
    payload = await c.compute_agent_configurations()
    runtime = payload["behavior"]["runtime"]
    assert runtime["backend"] == "vertex-ai"
    assert runtime["model"] == "gemini-2.0-flash"
    assert runtime["applied"] == ["temperature", "top_p", "top_k"]
    assert runtime["not_applied"] == ["frequency_penalty", "presence_penalty"]
    freq = next(s for s in payload["behavior"]["sliders"] if s["key"] == "frequency_penalty")
    assert freq["applied"] is False
    temp = next(s for s in payload["behavior"]["sliders"] if s["key"] == "temperature")
    assert temp["applied"] is True


async def test_selects_say_how_they_take_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0032 — every behaviour control is honest about its effectiveness.

    Tone/detail wear the prompt-injection badge, max length wears its declared
    hard cap, and top-k is the fifth slider (integer steps, unset by default).
    """
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = await c.compute_agent_configurations()
    selects = {s["key"]: s for s in payload["behavior"]["selects"]}
    assert selects["tone"]["badge"] == "Injecté au prompt"
    assert selects["detail"]["badge"] == "Injecté au prompt"
    assert selects["max_length"]["badge"] == "≤ 2048 tokens"  # Moyenne, the default
    sliders = [s["key"] for s in payload["behavior"]["sliders"]]
    assert sliders == ["temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty"]
    top_k = next(s for s in payload["behavior"]["sliders"] if s["key"] == "top_k")
    assert top_k["unset"] is True
    assert top_k["step"] == 1.0
    assert top_k["max"] == 100.0
    # The runtime note covers the selects too — the page says the whole story.
    assert "max_output_tokens" in payload["behavior"]["runtime"]["note"]


async def test_max_length_badge_follows_the_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {"max_length": "Courte"})
    payload = await c.compute_agent_configurations()
    max_length = next(s for s in payload["behavior"]["selects"] if s["key"] == "max_length")
    assert max_length["badge"] == "≤ 512 tokens"


async def test_escalation_block_says_where_the_default_comes_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0033 — unset shows the ORG default (settings), never an invented bar."""
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = await c.compute_agent_configurations()
    block = payload["behavior"]["escalation"]
    slider = block["slider"]
    assert slider["key"] == "escalation_threshold"
    assert slider["unset"] is True
    assert slider["unset_label"].startswith("Défaut org (")
    assert "ADR 0033" in block["note"]


async def test_escalation_block_shows_the_agent_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {"escalation_threshold": 0.85})
    payload = await c.compute_agent_configurations()
    slider = payload["behavior"]["escalation"]["slider"]
    assert slider["unset"] is False
    assert slider["num"] == 0.85
    assert slider["overridden"] is True
    assert "unset_label" not in slider


async def test_memory_block_says_the_org_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0036 — unset tier/window name the ORG defaults, never copied values."""
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = await c.compute_agent_configurations()
    block = payload["behavior"]["memory"]
    select = block["select"]
    assert select["key"] == "memory_backend"
    assert select["value"] == "Défaut org"
    assert str(select["badge"]).startswith("org : ")
    assert "Fenêtre (Tier 0)" in select["options"]
    slider = block["slider"]
    assert slider["key"] == "memory_window"
    assert slider["unset"] is True
    assert str(slider["unset_label"]).startswith("Défaut org (")
    assert slider["min"] == 2.0
    assert "ADR 0036" in block["note"]


async def test_retrieval_block_says_the_per_lookup_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0035 — unset depth names BOTH historical defaults, never one number."""
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = await c.compute_agent_configurations()
    block = payload["behavior"]["retrieval"]
    slider = block["slider"]
    assert slider["key"] == "retrieval_top_k"
    assert slider["unset"] is True
    assert slider["unset_label"] == "Défaut par recherche (4 produit / 6 réglementaire)"
    assert slider["min"] == 1.0
    assert slider["step"] == 1.0
    toggle = block["toggle"]
    assert toggle["key"] == "retrieval_rerank"
    assert toggle["on"] is True  # reranking ON is the historical truth
    assert "ADR 0035" in block["note"]


async def test_model_rows_show_the_effective_model_with_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ADR 0030 — the Modèle section and the Modèle actif card show the EFFECTIVE
    # serving model with its provenance, never the frozen base alone: an active
    # override must be visible on the agent's own page.
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})

    async def _overridden(_slug: str) -> tuple[str, str, tuple[str, ...], str]:
        return "gpt-5.5", "openai", (), "agent"

    monkeypatch.setattr(c, "_serving_effectiveness", _overridden)
    payload = await c.compute_agent_configurations()
    main_row = payload["model"]["left"][0]
    assert main_row["value"] == "gpt-5.5"
    assert main_row["badge"] == "OpenAI · Override agent"
    assert main_row["editable"] is False  # still read-only: the knob lives in the registry
    card = payload["active_model"]
    assert card["name"] == "gpt-5.5"
    assert "Override agent" in card["provider"]


async def test_model_rows_say_base_when_nothing_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = await c.compute_agent_configurations()  # hermetic stub: base provenance
    main_row = payload["model"]["left"][0]
    assert main_row["value"] == "llama3.2:3b"
    assert "Base" in str(main_row["badge"])


async def test_editable_flag_separates_real_from_readonly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(c, "_load_overrides", lambda *_a: {})
    payload = await c.compute_agent_configurations()
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

    def _capture(keys: list[str], *_a: object, **_kw: object) -> None:
        if keys:
            log.insert(0, {"at": "2026-06-17T08:00:00+02:00", "keys": keys})

    monkeypatch.setattr(c, "_record_change", _capture)

    changed = c.set_agent_config({"tone": "Amical"}, author="probe")
    assert changed == ["tone"]
    assert log[0]["keys"] == ["tone"]
    # Saving the same value again records nothing (no real change).
    log.clear()
    assert c.set_agent_config({"tone": "Amical"}, author="probe") == []
    assert log == []


def test_change_log_entry_names_its_author(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ADR 0024/0031 — a save that changes runtime behaviour names its author;
    # absence stays honest (no default that names somebody).
    from pathlib import Path

    from tessera.settings import get_settings

    monkeypatch.setattr(c, "_history_path", lambda: Path(str(tmp_path)) / "h.json")
    c._record_change(["temperature"], "recouvrement", author="superadmin")
    c._record_change(["tone"], "recouvrement", author=None)
    entries = c._load_change_log()
    assert entries[1]["author"] == "superadmin"
    assert "author" not in entries[0]
    rows = c._build_history(get_settings().guard.policy_path)
    saved = [r for r in rows if r["actor"] == "Console"]
    assert any("par superadmin" in r["label"] for r in saved)


def test_build_history_is_real_sources_only() -> None:
    from tessera.settings import get_settings

    items = c._build_history(get_settings().guard.policy_path)
    assert items, "real config file mtimes should always yield rows"
    # No invented actor: every row is either a console save or a Git source.
    assert all(it["actor"] in {"Console", "Dépôt (Git)"} for it in items)
    assert any("mis à jour" in it["label"] for it in items)


async def test_model_section_is_read_only_with_a_registry_link() -> None:
    payload = await c.compute_agent_configurations()
    model = payload["model"]
    # The model itself is read-only here (defined in the registry), never editable.
    for field in [*model["left"], *model["right"]]:  # type: ignore[index]
        if field["label"].startswith(("Modèle", "Version")):
            assert field["editable"] is False
    # Only the fallback strategy is editable, and it is a bounded select.
    strat = next(f for f in model["right"] if f.get("key") == "fallback_strategy")  # type: ignore[index]
    assert strat["kind"] == "select"
    assert model["link"]["href"] == "/configurer/modeles"  # type: ignore[index]


async def test_governed_flag_tracks_production() -> None:
    # Local dev is not governed; the flag exists for the prod release-control flow.
    assert (await c.compute_agent_configurations())["governed"] is False
