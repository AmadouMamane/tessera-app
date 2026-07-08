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
