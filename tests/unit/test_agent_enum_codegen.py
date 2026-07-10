"""Enum codegen conformance (ADR 0018 §C) — the generate-and-diff gate.

The per-agent intent enums are generated from the AgentSpec capabilities. This
test fails whenever the committed backend ``Literal`` / frontend union drifts from
what the generator would produce for the live manifest, so a capabilities change
that forgets to regenerate is caught in CI:

    uv run python scripts/generate_agent_enums.py
"""

from __future__ import annotations

from pathlib import Path

from tessera.agent.codegen import (
    backend_path,
    capability_ids,
    frontend_path,
    render_backend_enums,
    render_frontend_enums,
)
from tessera.agent.generated.recouvrement_enums import RECOUVREMENT_CAPABILITY_IDS
from tessera.agent.registry import get_agent

_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_committed_backend_enums_match_regeneration() -> None:
    rel = backend_path("recouvrement")
    assert _read(rel) == render_backend_enums(
        "recouvrement"
    ), f"{rel} is stale — run `uv run python scripts/generate_agent_enums.py`"


def test_committed_frontend_enums_match_regeneration() -> None:
    rel = frontend_path("recouvrement")
    assert _read(rel) == render_frontend_enums(
        "recouvrement"
    ), f"{rel} is stale — run `uv run python scripts/generate_agent_enums.py`"


def test_generated_ids_equal_the_manifest_capabilities() -> None:
    spec = get_agent("recouvrement").observability
    assert spec is not None
    manifest_ids = tuple(sorted(cap.id for cap in spec.capabilities))
    # The generator's view and the committed constant both equal the manifest.
    assert capability_ids("recouvrement") == manifest_ids
    assert manifest_ids == RECOUVREMENT_CAPABILITY_IDS


def test_recouvrement_intent_vocabulary_is_stable() -> None:
    # Regression pin: the five declared recouvrement capabilities (ADR 0010/0017).
    assert RECOUVREMENT_CAPABILITY_IDS == (
        "check_contact_rule",
        "draft_reminder",
        "explain_payment_options",
        "propose_schedule",
        "summarize_case",
    )


def test_artifact_type_capabilities_map_every_declared_output() -> None:
    """The artifact-type vocabulary is a manifest fact, not a frontend union (ADR 0018 §C)."""
    from tessera.agent.codegen import artifact_type_capabilities

    pairs = dict(artifact_type_capabilities("recouvrement"))
    assert pairs == {
        "case_summary_v1": "summarize_case",
        "client_message_artifact": "draft_reminder",
        "contact_rule_v1": "check_contact_rule",
        "payment_options_v1": "explain_payment_options",
        "reminder_draft_v1": "draft_reminder",
        "schedule_proposal_v2": "propose_schedule",
    }
    # Every declared artifact resolves to a declared capability — no dangling right-hand side.
    assert set(pairs.values()) <= set(RECOUVREMENT_CAPABILITY_IDS)


def test_manifest_declares_every_artifact_type_the_agent_emits() -> None:
    """The gap this slice closed: `reminder_draft_v1` was emitted but never declared.

    The frontend knew an artifact type the manifest did not, which is exactly what forces a
    hand-written enum. Scanning the emitter keeps the declaration honest as the agent grows.

    `authorization_denial_v1` is deliberately exempt: a refusal is not a capability's *output*,
    it is what happens instead of one, and attaching it to a capability would be a lie about
    what that capability produces. Named here rather than silently skipped.
    """
    import re

    from tessera.agent.codegen import artifact_type_capabilities

    non_capability_outputs = {"authorization_denial_v1"}
    source = (_ROOT / "src" / "tessera" / "agent" / "recouvrement.py").read_text(encoding="utf-8")
    # Anchored on artifact context (`"type": "x"` / `artifact_type = "x"`), plus the ternary
    # else-branch that hid `reminder_draft_v1` from every simpler scan.
    emitted = set(re.findall(r'(?:"type"|artifact_type)\s*[:=]\s*"([a-z][a-z0-9_]*)"', source))
    emitted |= set(
        re.findall(r'artifact_type\s*=\s*"[^"]+"\s*if\s+[^\n]*?else\s+"([a-z][a-z0-9_]*)"', source)
    )
    # A scan that finds nothing would pass vacuously. It finds seven today.
    assert len(emitted) == 7, f"the emitter scan drifted; found {sorted(emitted)}"

    declared = {artifact for artifact, _ in artifact_type_capabilities("recouvrement")}
    undeclared = emitted - declared - non_capability_outputs
    assert not undeclared, f"agent emits artifact types the manifest never declares: {undeclared}"
