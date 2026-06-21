"""Unit tests for the CONFIGURER model catalogue (real config + price table)."""

from __future__ import annotations

from tessera.observability import model_catalogue as mc


def _by_id(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    models = payload["models"]
    assert isinstance(models, list)
    return {str(m["id"]): m for m in models}


def test_catalogue_lists_priced_and_configured_models() -> None:
    payload = mc.build_model_catalogue("fr")
    by = _by_id(payload)
    # Priced frontier models from the budget table are present...
    assert "gemini-2.0-flash-001" in by
    assert by["gemini-2.0-flash-001"]["provider"] == "vertex-ai"
    # ...and the configured on-prem dev models (unpriced) too.
    assert "llama3.2:3b" in by
    assert "bge-m3" in by
    assert by["bge-m3"]["role"] == "embedding"


def test_active_models_flagged_for_the_resolved_profile() -> None:
    payload = mc.build_model_catalogue("fr")
    by = _by_id(payload)
    # Default profile is on-prem -> the ollama chat + embedding models are active.
    assert by["llama3.2:3b"]["status"] == "active"
    assert by["bge-m3"]["status"] == "active"
    # A non-active model is "available".
    assert by["gemini-2.0-flash-001"]["status"] == "available"


def test_pricing_is_real_from_the_budget_table() -> None:
    payload = mc.build_model_catalogue("en")
    by = _by_id(payload)
    # gemini-2.0-flash-001 = EUR 0.10 / 0.40 per million (from _PRICES).
    assert "0.10" in str(by["gemini-2.0-flash-001"]["price"])
    assert "0.40" in str(by["gemini-2.0-flash-001"]["price"])
    # On-prem models are free.
    assert "0" in str(by["llama3.2:3b"]["price"])


def test_kpis_and_detail_shape() -> None:
    payload = mc.build_model_catalogue("fr")
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}  # type: ignore[index,union-attr]
    assert kpis["chat"] == "llama3.2:3b"
    assert kpis["embed"] == "bge-m3"
    assert kpis["profile"] == "on_prem"
    by = _by_id(payload)
    detail = by["gemini-2.0-flash-001"]["detail"]
    assert isinstance(detail, dict)
    assert {s["key"] for s in detail["sections"]} == {"overview", "pricing", "usage"}  # type: ignore[index,union-attr]
    assert "consumers" in detail


def test_available_model_ids_covers_active_models() -> None:
    ids = mc.available_model_ids()
    assert {"llama3.2:3b", "bge-m3", "gemini-2.0-flash-001", "gpt-5.5"} <= ids
