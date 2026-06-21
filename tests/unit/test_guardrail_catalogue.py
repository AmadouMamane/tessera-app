"""Unit tests for the CONFIGURER platform guardrail catalogue (real policy)."""

from __future__ import annotations

from tessera.observability import guardrail_catalogue as gc


def test_catalogue_lists_bound_guardrail_blocks() -> None:
    payload = gc.build_guardrail_catalogue("fr")
    blocks = payload["blocks"]
    assert isinstance(blocks, list)
    ids = {str(b["id"]) for b in blocks}
    # The registry binds the standard + strict guardrail profiles.
    assert {"standard", "strict"} <= ids


def test_composition_is_real_from_policy() -> None:
    payload = gc.build_guardrail_catalogue("en")
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}  # type: ignore[index,union-attr]
    # Real counts from guard/policy.yaml: 5 guarded tools, >=1 deny + PII pattern.
    assert kpis["tools"] == "5"
    assert int(kpis["deny"]) > 0
    assert int(kpis["pii"]) > 0
    assert kpis["version"].startswith("v")


def test_block_detail_has_composition_coverage_logging() -> None:
    payload = gc.build_guardrail_catalogue("fr")
    blocks = {str(b["id"]): b for b in payload["blocks"]}  # type: ignore[union-attr]
    detail = blocks["standard"]["detail"]
    assert isinstance(detail, dict)
    assert {s["key"] for s in detail["sections"]} == {"composition", "coverage", "logging"}  # type: ignore[index,union-attr]
    # Used-by carries the consuming agents + a re-gate count.
    assert detail["consumers"]["count"] >= 1  # type: ignore[index,call-overload]


def test_available_guardrail_ids() -> None:
    assert {"standard", "strict"} <= gc.available_guardrail_ids()
