"""Unit tests for CONFIGURER "used-by" (inverse of the AGENT instance binding)."""

from __future__ import annotations

import pytest

from tessera.observability.catalogue_consumers import KINDS, catalogue_consumers


def test_guardrails_inverts_registry_bindings() -> None:
    payload = catalogue_consumers("guardrails")
    items = payload["items"]
    assert isinstance(items, list)
    by_item = {i["item"]: i for i in items}
    # Real registry: standard is shared (support-client + onboarding + the three external
    # second-runtime agents hello-agent / turn-agent / duplex-agent, whose profiles take the
    # default binding), strict is recouvrement.
    assert by_item["standard"]["consumer_count"] == 5
    assert {c["agent_id"] for c in by_item["standard"]["consumers"]} == {
        "support-client",
        "onboarding",
        "hello-agent",
        "turn-agent",
        "duplex-agent",
    }
    assert by_item["strict"]["consumer_count"] == 1


def test_scope_filters_consumers() -> None:
    payload = catalogue_consumers("model", agent_scope="recouvrement")
    items = payload["items"]
    assert isinstance(items, list)
    # Only items recouvrement consumes, with only recouvrement listed.
    for item in items:
        ids = {c["agent_id"] for c in item["consumers"]}
        assert ids == {"recouvrement"}


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown catalogue kind"):
        catalogue_consumers("nonsense")


def test_known_kinds_are_inversible() -> None:
    for kind in KINDS:
        payload = catalogue_consumers(kind)
        assert isinstance(payload["items"], list)
