"""AgentSpec v1 schema validation + manifest projection (ADR 0017 §3 + A1 + A2.2/A2.3).

The manifest is an API, not config: every block is validated with ``extra="forbid"`` and
a malformed block fails the load. These tests are the CI gate for that contract, plus the
level/descriptor projection the cockpit generates from the manifest.
"""

from __future__ import annotations

import dataclasses

import pytest

from tessera.agent.agentspec import (
    AGENTSPEC_VERSION,
    AgentObservabilitySpec,
    parse_observability,
)
from tessera.agent.registry import get_agent
from tessera.observability.agentspec_projection import (
    business_signal_descriptors,
    north_star_descriptor,
    observability_level,
)


def _valid_obs() -> dict[str, object]:
    """A minimal, fully valid observability block (mutate one field to probe rejection)."""
    return {
        "spec_version": AGENTSPEC_VERSION,
        "telemetry_capabilities": ["graph_topology"],
        "capabilities": [
            {
                "id": "draft_reminder",
                "label_key": "capability.draft_reminder",
                "output_artifacts": ["client_message_artifact"],
                "policies": ["contact_window_policy"],
                "external_effect_level": "requires_validation",
            }
        ],
        "policies": [
            {
                "id": "contact_window_policy",
                "label_key": "policy.contact_window",
                "version": "1.0.0",
                "severity": "blocking",
                "applies_to": ["draft_reminder"],
                "reason_codes": ["OUTSIDE_CONTACT_WINDOW"],
            }
        ],
        "workflows": [
            {
                "workflow_id": "recouvrement_collections_v1",
                "grammar": "workflow_grammar.v1",
                "scorer": "recouvrement.collections.v1",
            }
        ],
        "business_signals": [
            {
                "key": "contact_window_compliance",
                "source": "business_score",
                "level": "runtime",
                "unit": "ratio",
                "aggregation": "mean",
                "dimensions": ["agent", "time"],
                "engagement": "legal",
                "north_star": True,
            }
        ],
    }


# --- the manifest is an API (extra=forbid, closed vocabularies) ------------------


def test_valid_block_parses() -> None:
    spec = parse_observability(_valid_obs())
    assert isinstance(spec, AgentObservabilitySpec)
    assert spec.spec_version == AGENTSPEC_VERSION


def test_unknown_spec_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="spec_version"):
        parse_observability(_valid_obs() | {"spec_version": "agentspec.v2"})


def test_unknown_key_is_rejected() -> None:
    # extra="forbid": a typo is a load error, not a silently-dropped field.
    with pytest.raises(ValueError, match="observability block"):
        parse_observability(_valid_obs() | {"telemtry_capabilities": ["oops"]})


def test_unknown_external_effect_level_is_rejected() -> None:
    raw = _valid_obs()
    raw["capabilities"][0]["external_effect_level"] = "teleport"  # type: ignore[index]
    with pytest.raises(ValueError, match="external_effect_level"):
        parse_observability(raw)


def test_unknown_policy_severity_is_rejected() -> None:
    raw = _valid_obs()
    raw["policies"][0]["severity"] = "catastrophic"  # type: ignore[index]
    with pytest.raises(ValueError, match="severity"):
        parse_observability(raw)


def test_capability_label_key_namespace_is_enforced() -> None:
    raw = _valid_obs()
    raw["capabilities"][0]["label_key"] = "draft_reminder"  # type: ignore[index]
    with pytest.raises(ValueError, match="capability label_key"):
        parse_observability(raw)


def test_policy_label_key_namespace_is_enforced() -> None:
    raw = _valid_obs()
    raw["policies"][0]["label_key"] = "contact_window"  # type: ignore[index]
    with pytest.raises(ValueError, match="policy label_key"):
        parse_observability(raw)


def test_grammar_namespace_is_enforced() -> None:
    raw = _valid_obs()
    raw["workflows"][0]["grammar"] = "v1"  # type: ignore[index]
    with pytest.raises(ValueError, match="workflow grammar"):
        parse_observability(raw)


# --- A2.2 display-honesty: an outcome signal is undeclarable ---------------------


def test_outcome_level_signal_is_undeclarable() -> None:
    raw = _valid_obs()
    raw["business_signals"][0]["level"] = "outcome"  # type: ignore[index]
    with pytest.raises(ValueError, match="undeclarable"):
        parse_observability(raw)


# --- referential integrity + uniqueness ------------------------------------------


def test_policy_applies_to_unknown_capability_is_rejected() -> None:
    raw = _valid_obs()
    raw["policies"][0]["applies_to"] = ["ghost_capability"]  # type: ignore[index]
    with pytest.raises(ValueError, match="applies_to unknown capabilities"):
        parse_observability(raw)


def test_capability_references_unknown_policy_is_rejected() -> None:
    raw = _valid_obs()
    raw["capabilities"][0]["policies"] = ["ghost_policy"]  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown policies"):
        parse_observability(raw)


def test_two_north_stars_are_rejected() -> None:
    raw = _valid_obs()
    signals = list(raw["business_signals"])  # type: ignore[arg-type]
    second = dict(signals[0])
    second["key"] = "action_blocking_correctness"
    raw["business_signals"] = [signals[0], second]
    with pytest.raises(ValueError, match="north_star"):
        parse_observability(raw)


def test_duplicate_capability_id_is_rejected() -> None:
    raw = _valid_obs()
    caps = list(raw["capabilities"])  # type: ignore[arg-type]
    raw["capabilities"] = [caps[0], dict(caps[0])]
    with pytest.raises(ValueError, match="duplicate capability id"):
        parse_observability(raw)


# --- projection: level (computed from facts, never asserted) ---------------------


def test_recouvrement_reads_l1_ungoverned_l2_governed() -> None:
    agent = get_agent("recouvrement")
    assert observability_level(agent, governed=False) == "L1"
    assert observability_level(agent, governed=True) == "L2"


def test_unmanifested_agent_has_no_level() -> None:
    # honest-empty: absence of a manifest is None, never rendered as "L0".
    assert observability_level(get_agent("support-client"), governed=True) is None


def test_manifest_without_observable_contract_reads_l0() -> None:
    agent = get_agent("recouvrement")
    bare = parse_observability({"spec_version": AGENTSPEC_VERSION})
    l0_agent = dataclasses.replace(agent, observability=bare)
    assert observability_level(l0_agent, governed=True) == "L0"


# --- projection: generated business-signal descriptors ---------------------------


def test_descriptors_are_generated_from_the_manifest() -> None:
    agent = get_agent("recouvrement")
    descriptors = business_signal_descriptors(agent)
    assert len(descriptors) == len(agent.observability.business_signals)  # type: ignore[union-attr]
    # a business_score signal carries the bound scorer id.
    assert all(
        d["scorer"] == "recouvrement.collections.v1"
        for d in descriptors
        if d["source"] == "business_score"
    )


def test_north_star_descriptor_is_the_declared_one() -> None:
    star = north_star_descriptor(get_agent("recouvrement"))
    assert star is not None
    assert star["key"] == "contact_window_compliance"
    assert star["engagement"] == "legal"


def test_unmanifested_agent_has_no_descriptors() -> None:
    assert business_signal_descriptors(get_agent("support-client")) == []
