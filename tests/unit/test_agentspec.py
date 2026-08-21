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
    InvocationBinding,
    InvocationSpec,
    parse_observability,
    validate_quality_seam,
)
from tessera.agent.registry import get_agent
from tessera.observability.agentspec_projection import (
    business_signal_descriptors,
    declared_observability_level,
    north_star_descriptor,
    observability_level,
    quality_regime_descriptor,
)


def _valid_obs() -> dict[str, object]:
    """A minimal, fully valid observability block (mutate one field to probe rejection)."""
    return {
        "spec_version": AGENTSPEC_VERSION,
        "quality_regime": "business_scored",
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


# --- §3 Amendment 4: the declared quality regime ---------------------------------


def test_quality_regime_is_required_and_carries_no_default() -> None:
    # ADR 0024 applied to judgment: no default may put a ruler nobody chose behind an
    # agent's figures. The field stays required BY SCHEMA — this ratchet refuses a future
    # default as loudly as a missing declaration.
    raw = _valid_obs()
    del raw["quality_regime"]
    with pytest.raises(ValueError, match="quality_regime"):
        parse_observability(raw)
    assert AgentObservabilitySpec.model_fields["quality_regime"].is_required()


def test_unknown_quality_regime_is_rejected() -> None:
    with pytest.raises(ValueError, match="quality_regime"):
        parse_observability(_valid_obs() | {"quality_regime": "vibes"})


def test_unscored_requires_a_declared_reason() -> None:
    # A blind spot is declared with its reason, never silently (ADR 0026).
    raw = _valid_obs()
    raw["quality_regime"] = "unscored"
    raw["business_signals"] = []
    raw["workflows"][0] = {  # type: ignore[index]
        "workflow_id": "recouvrement_collections_v1",
        "grammar": "workflow_grammar.v1",
    }
    with pytest.raises(ValueError, match="requires quality_regime_reason_key"):
        parse_observability(raw)
    raw["quality_regime_reason_key"] = "quality_regime.reason.demo_no_reference"
    assert parse_observability(raw).quality_regime_reason_key is not None


def test_a_reason_on_a_scored_regime_is_rejected() -> None:
    raw = _valid_obs() | {"quality_regime_reason_key": "quality_regime.reason.demo_no_reference"}
    with pytest.raises(ValueError, match="must not set"):
        parse_observability(raw)


def test_reason_key_namespace_is_enforced() -> None:
    raw = _valid_obs()
    raw["quality_regime"] = "unscored"
    raw["business_signals"] = []
    raw["workflows"] = []
    raw["quality_regime_reason_key"] = "demo_no_reference"
    with pytest.raises(ValueError, match="quality_regime_reason_key must start"):
        parse_observability(raw)


def test_business_scored_requires_signals_and_a_bound_scorer() -> None:
    # A ruler with no producer scores nothing — both halves of the production chain must
    # be declared before the regime may claim them.
    no_signals = _valid_obs() | {"business_signals": []}
    with pytest.raises(ValueError, match="requires declared business_signals"):
        parse_observability(no_signals)
    no_scorer = _valid_obs()
    no_scorer["workflows"][0] = {  # type: ignore[index]
        "workflow_id": "recouvrement_collections_v1",
        "grammar": "workflow_grammar.v1",
    }
    with pytest.raises(ValueError, match="requires a workflow binding a scorer"):
        parse_observability(no_scorer)


def test_declared_signals_force_the_business_scored_regime() -> None:
    # The two rulers stay disjoint by construction: a scored plane may not hide its ruler
    # behind another regime (the defect already paid for — insights 361-363).
    with pytest.raises(ValueError, match="may not hide its ruler"):
        parse_observability(_valid_obs() | {"quality_regime": "llm_judged"})
    # And the producer alone forces it too: a bound scorer with no declared signals may
    # not sit under another regime either.
    with pytest.raises(ValueError, match="forces its ruler"):
        parse_observability(_valid_obs() | {"quality_regime": "llm_judged", "business_signals": []})


def test_llm_judged_requires_the_chat_seam() -> None:
    # Cross-block integrity (validate_quality_seam): the online judge is wired on the
    # in-process /chat seam only — a declared judge the declared transport cannot carry
    # is a load error, never a surface waiting for a judge that will never come.
    judged = parse_observability(
        _valid_obs() | {"quality_regime": "llm_judged", "business_signals": [], "workflows": []}
    )
    with pytest.raises(ValueError, match="in_process_chat"):
        validate_quality_seam(judged, InvocationSpec())
    validate_quality_seam(judged, InvocationSpec(binding=InvocationBinding.IN_PROCESS_CHAT))
    validate_quality_seam(None, InvocationSpec())  # un-manifested: nothing to contradict


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


def test_recouvrement_reads_l1_ungoverned_l2_governed_l3_business() -> None:
    # The DECLARED ladder — what the manifest reaches once its turns are observed.
    agent = get_agent("recouvrement")
    assert declared_observability_level(agent, governed=False) == "L1"
    assert declared_observability_level(agent, governed=True) == "L2"
    assert declared_observability_level(agent, governed=True, business_events=True) == "L3"


def test_unmanifested_agent_has_no_level() -> None:
    # honest-empty: absence of a manifest is None, never rendered as "L0". Every registry
    # agent now carries a manifest (step 7 Lot 0), so strip it to exercise the None path.
    unmanifested = dataclasses.replace(get_agent("support-client"), observability=None)
    assert declared_observability_level(unmanifested, governed=True) is None
    assert observability_level(unmanifested, governed=True, has_turn_evidence=True) is None


def test_qa_agents_declare_observable_contract_l1_ungoverned_l2_governed() -> None:
    # step 7 Lot 0: support-client + onboarding declare telemetry-only Q&A manifests (a
    # conversation workflow on the grammar + telemetry capabilities, NO scorer / capabilities
    # / business_signals). The level is COMPUTED, never tuned: L1 ungoverned, L2 governed.
    for aid in ("support-client", "onboarding"):
        agent = get_agent(aid)
        assert agent.observability is not None
        assert agent.observability.workflows and agent.observability.telemetry_capabilities
        assert not agent.observability.business_signals  # telemetry-only, no scored signals
        assert declared_observability_level(agent, governed=False) == "L1"
        assert declared_observability_level(agent, governed=True) == "L2"


def test_manifest_without_observable_contract_reads_l0() -> None:
    agent = get_agent("recouvrement")
    # The barest valid manifest still names its quality regime — required by schema.
    bare = parse_observability(
        {
            "spec_version": AGENTSPEC_VERSION,
            "quality_regime": "unscored",
            "quality_regime_reason_key": "quality_regime.reason.demo_no_reference",
        }
    )
    l0_agent = dataclasses.replace(agent, observability=bare)
    assert declared_observability_level(l0_agent, governed=True) == "L0"


def test_declared_but_unobserved_reads_l0() -> None:
    # ADR 0017 §F: "Observable" means the cockpit SEES turns, not that the manifest promises
    # them. A declared observable contract with no observed turns stays L0 (Registered).
    agent = get_agent("recouvrement")
    assert observability_level(agent, governed=True, has_turn_evidence=False) == "L0"
    assert observability_level(agent, governed=False, has_turn_evidence=True) == "L1"
    assert (
        observability_level(agent, governed=True, business_events=True, has_turn_evidence=True)
        == "L3"
    )


def test_the_declared_ladder_is_never_reachable_by_omission() -> None:
    """`has_turn_evidence` is required: a caller cannot obtain a computed rung by default.

    This is the guard for the over-claim the badge exposed — a defaulted `True` handed out
    computed-looking rungs that rested on nothing.
    """
    agent = get_agent("recouvrement")
    with pytest.raises(TypeError):
        observability_level(agent, governed=True)  # type: ignore[call-arg]
    # The declared rung stays reachable, but only by asking for it BY NAME.
    assert declared_observability_level(agent, governed=True) == "L2"


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


# --- projection: the declared quality regime (§3 Amendment 4) ---------------------


def test_quality_regime_descriptor_reads_the_declaration() -> None:
    # The single projector every quality surface reads — declaration, never inference.
    assert quality_regime_descriptor(get_agent("recouvrement")) == {
        "agent_id": "recouvrement",
        "regime": "business_scored",
        "reason_key": None,
    }
    assert quality_regime_descriptor(get_agent("support-client")) == {
        "agent_id": "support-client",
        "regime": "llm_judged",
        "reason_key": None,
    }
    assert quality_regime_descriptor(get_agent("hello-agent")) == {
        "agent_id": "hello-agent",
        "regime": "unscored",
        "reason_key": "quality_regime.reason.demo_no_reference",
    }


def test_unmanifested_agent_has_no_quality_regime_descriptor() -> None:
    unmanifested = dataclasses.replace(get_agent("support-client"), observability=None)
    assert quality_regime_descriptor(unmanifested) is None
