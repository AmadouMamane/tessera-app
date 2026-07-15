"""Unit tests for the System profile overview (admin/profil-systeme).

Assert the payload is built from the real runtime (platform, importlib.metadata,
settings, process uptime, file-presence health checks) — not a fabricated
data-center. The probes hit the real repo, so the assertions stay structural.
"""

from __future__ import annotations

import platform
from types import SimpleNamespace
from typing import TYPE_CHECKING, NoReturn

import tessera
from tessera.observability import system_profile as sp

if TYPE_CHECKING:
    import pytest


def test_kpis_report_the_real_runtime() -> None:
    kpis = {k["key"]: k for k in sp.compute_system_profile()["kpis"]}
    assert kpis["python"]["value"] == platform.python_version()
    assert kpis["platform"]["value"] == f"{platform.system()} {platform.machine()}"
    assert kpis["mode"]["value"] in {"On-premises", "Cloud"}
    # No fabricated CPU%/availability series — KPIs are real snapshot facts.
    assert all(k["series"] == [] for k in kpis.values())


def test_versions_come_from_installed_packages() -> None:
    versions = {v["name"]: v["version"] for v in sp.compute_system_profile()["versions"]}
    # The guard is first-party (ADR 0028): its version is Tessera's own,
    # never a third-party package presence.
    assert versions["Tessera guard (first-party)"] == tessera.__version__
    assert versions["Tessera guard (first-party)"] != "-"
    assert versions["Python"] == platform.python_version()


def test_health_checks_probe_real_artifacts() -> None:
    checks = {h["key"]: h["status"] for h in sp.compute_system_profile()["health_checks"]}
    # the repo ships these — and "firewall" is the MEASURED first-party
    # detector (ADR 0028): ok means F1 > 0 against the shipped corpus.
    for key in ("policy", "prompts", "corpus", "firewall"):
        assert checks[key] == "ok", key
    assert set(checks.values()) <= {"ok", "warn", "bad"}


def test_component_distribution_is_real_counts() -> None:
    res = sp.compute_system_profile()["resources"]
    by_key = {s["key"]: s["count"] for s in res["slices"]}
    assert by_key["tools"] == 5  # five LLM-callable tools
    assert by_key["prompts"] == 14
    assert sum(by_key.values()) > 0


def test_runtime_panel_uses_real_audit_facts() -> None:
    runtime = sp.compute_system_profile()["runtime"]
    assert runtime["audit_chain"] in {"Vérifiée", "Rupture détectée"}
    assert "uptime" in runtime and "started" in runtime


def test_firewall_badge_fails_closed_when_the_probe_is_blind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0028 §2: a badge that cannot measure leaves the green — warn, never ok."""

    def _blind() -> NoReturn:
        raise RuntimeError("corpus unreadable")

    monkeypatch.setattr(sp.firewall_efficacy, "compute_efficacy", _blind)
    checks = {h["key"]: h["status"] for h in sp.compute_system_profile()["health_checks"]}
    assert checks["firewall"] != "ok"


def test_firewall_badge_leaves_green_on_a_dead_detector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detector measuring F1 = 0 is a decoration; the badge may not stay green."""
    # A live limes detector (correct id) that nonetheless measures F1 = 0.
    monkeypatch.setattr(
        sp.firewall_efficacy,
        "compute_efficacy",
        lambda: SimpleNamespace(f1=0.0, detector_id="injection"),
    )
    checks = {h["key"]: h["status"] for h in sp.compute_system_profile()["health_checks"]}
    assert checks["firewall"] != "ok"
