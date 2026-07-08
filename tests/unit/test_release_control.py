"""Unit tests for the Release Control payload (per-agent eval-gate verdict)."""

from __future__ import annotations

from tessera.observability.release_control import compute_release_control


def test_summary_reconciles_with_rows() -> None:
    payload = compute_release_control()
    rows = payload["agents"]
    summary = payload["summary"]
    assert isinstance(rows, list)
    assert isinstance(summary, dict)
    # Every agent is classified exactly once.
    assert summary["total"] == len(rows)
    assert summary["total"] == summary["passing"] + summary["blocked"] + summary["not_run"]


def test_summary_counts_follow_the_lifecycle_tone() -> None:
    # §A2.4 single-truth: the KPI counts ARE the per-row state tallies, so an agent blocked
    # only by its observability level (state_tone "bad") can never be miscounted as "ready".
    payload = compute_release_control()
    rows = payload["agents"]
    summary = payload["summary"]
    assert isinstance(rows, list)
    assert isinstance(summary, dict)
    tones = [r["state_tone"] for r in rows]
    assert summary["passing"] == tones.count("good")
    assert summary["blocked"] == tones.count("bad")
    assert summary["not_run"] == tones.count("warn")


def test_scope_filters_to_one_agent() -> None:
    payload = compute_release_control("support-client")
    rows = payload["agents"]
    assert isinstance(rows, list)
    assert [r["agent_id"] for r in rows] == ["support-client"]
    # The verdict carries the policy-correct headline + a candidate version.
    release = rows[0]["release"]
    assert isinstance(release, dict)
    assert release["available"] is True
    assert release["verdict_label"]
    assert release["candidate_version"]
