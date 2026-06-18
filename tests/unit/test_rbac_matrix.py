"""Unit tests for the RBAC role x agent matrix (real roles x real agents)."""

from __future__ import annotations

from tessera.observability.rbac import ROLE_CAPS, rbac_matrix


def test_matrix_crosses_real_roles_with_real_agents() -> None:
    payload = rbac_matrix()
    roles = payload["roles"]
    agents = payload["agents"]
    assert isinstance(roles, list)
    assert isinstance(agents, list)
    # The enforced roles are mirrored (admin / auditor; superadmin is env-gated).
    role_ids = {r["role"] for r in roles}
    assert {"admin", "auditor"} <= role_ids <= set(ROLE_CAPS)
    # Every role has one cell per agent, org-scoped (no fabricated per-agent grant).
    for r in roles:
        assert r["agent_count"] == len(agents)
        assert len(r["cells"]) == len(agents)
        assert all(c["scope"] == "org" for c in r["cells"])


def test_scope_filters_agent_columns() -> None:
    payload = rbac_matrix("recouvrement")
    agents = payload["agents"]
    assert [a["id"] for a in agents] == ["recouvrement"]
    for r in payload["roles"]:
        assert [c["agent_id"] for c in r["cells"]] == ["recouvrement"]
