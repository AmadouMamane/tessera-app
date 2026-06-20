"""Unit tests for the connectors and users cockpit datasets.

These assert the pages are sourced from the real model, not invented:
- connectors mirror the frozen Tessera stack and reflect the active runtime mode;
- users mirror the real seeded operator accounts + RBAC capabilities.
"""

from __future__ import annotations

from tessera.observability import connectors as cx, users as us
from tessera.observability.rbac import ROLE_CAPS


def test_connectors_cover_the_real_stack() -> None:
    payload = cx.compute_connectors()
    names = {str(c["name"]) for c in payload["connectors"]}
    # The real frozen stack must be present.
    assert any("Ollama" in n for n in names)
    assert any("Vertex AI" in n for n in names)
    assert any("pgvector" in n for n in names)
    assert "mcp-firewall" in names
    # Exactly one LLM path is active at a time (on-prem XOR frontier).
    llm = [c for c in payload["connectors"] if c["id"] in {"CX-LLM-LOCAL", "CX-LLM-FRONTIER"}]
    actives = [c for c in llm if c["status"] == "active"]
    assert len(actives) == 1


def test_connectors_distribution_sums_to_total() -> None:
    payload = cx.compute_connectors()
    assert sum(s["count"] for s in payload["distribution"]) == len(payload["connectors"])


def test_users_mirror_seeded_accounts_and_rbac() -> None:
    payload = us.compute_users()
    users = payload["users"]
    usernames = {str(u["username"]) for u in users}
    assert usernames == {"admin", "auditor", "superadmin"}
    # Capabilities must come from the real RBAC model, not be invented.
    for u in users:
        assert list(u["caps"]) == list(ROLE_CAPS[str(u["role"])]["caps"])
        assert u["scope"] == "org"  # honest org-wide scope (Phase 1)
