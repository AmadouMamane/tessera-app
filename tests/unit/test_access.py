"""Unit tests for the Roles & access overview (admin/roles-acces).

Exercise :func:`tessera.observability.access.compute_access_overview` and assert
that the payload is built from the real RBAC model (ROLE_CAPS + seeded accounts +
registry agents), with honest empty governance panels and no fabricated rows.
"""

from __future__ import annotations

from tessera.observability import access
from tessera.observability.rbac import ROLE_CAPS


def test_roles_mirror_role_caps() -> None:
    payload = access.compute_access_overview()
    ids = {r["id"] for r in payload["roles"]}
    assert ids == set(ROLE_CAPS)
    assert payload["total_roles"] == len(ROLE_CAPS)
    by_id = {r["id"]: r for r in payload["roles"]}
    for rid, meta in ROLE_CAPS.items():
        assert by_id[rid]["permissions"] == len(meta["caps"])  # type: ignore[arg-type]
        assert by_id[rid]["caps"] == list(meta["caps"])  # type: ignore[arg-type]


def test_type_partitions_privileged_vs_readonly() -> None:
    by_id = {r["id"]: r for r in access.compute_access_overview()["roles"]}
    assert by_id["admin"]["type"] == "systeme"
    assert by_id["superadmin"]["type"] == "systeme"
    assert by_id["auditor"]["type"] == "metier"


def test_each_role_carries_its_own_detail() -> None:
    for role in access.compute_access_overview()["roles"]:
        # members + distributions are computed per role so a row click can drive
        # the detail panel client-side.
        assert len(role["members"]) == role["users"]
        dist_total = sum(s["count"] for s in role["permission_dist"])
        assert dist_total == role["permissions"]
        assert role["owner"]  # real provenance string


def test_governance_panels_are_honestly_empty() -> None:
    payload = access.compute_access_overview()
    # No Phase-1 store for these, and one role per account => no SoD conflict.
    assert payload["pending_requests"] == []
    assert payload["sod_violations"] == []
    assert payload["inactive_accounts"] == []


def test_kpis_are_real_counts() -> None:
    kpis = {k["key"]: k for k in access.compute_access_overview()["kpis"]}
    assert kpis["roles"]["value"] == str(len(ROLE_CAPS))
    assert kpis["accounts"]["value"] == "3"
    # capabilities = size of the union of all caps
    union = {c for meta in ROLE_CAPS.values() for c in meta["caps"]}  # type: ignore[union-attr]
    assert kpis["capabilities"]["value"] == str(len(union))
    # sparkline series are real distributions, never flat-filled [v]*7
    assert all(len(k["series"]) <= len(ROLE_CAPS) + len(union) for k in kpis.values())


def test_top_roles_sorted_by_capability_count_desc() -> None:
    top = access.compute_access_overview()["top_roles"]
    values = [r["value"] for r in top]
    assert values == sorted(values, reverse=True)
    assert top[0]["name"] == "Super-admin"
