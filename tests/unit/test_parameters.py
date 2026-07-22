"""The Parameters overview must derive every value from live config, not literals.

These assertions recompute the expected numbers from the same real sources
(:func:`get_settings`, :func:`load_policy`, the model catalogue) and check the
payload matches — so the test proves *derivation*, never a hard-coded snapshot.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from tessera.guard.decisions import load_policy
from tessera.observability.model_catalogue import available_model_ids
from tessera.observability.parameters import compute_parameters_overview
from tessera.settings import get_settings


def _kpi(payload: dict[str, object], key: str) -> str:
    for k in payload["kpis"]:  # type: ignore[union-attr]
        if k["key"] == key:  # type: ignore[index]
            return str(k["value"])  # type: ignore[index]
    raise AssertionError(f"missing KPI {key}")


def test_kpis_are_derived_from_the_live_policy_and_catalogue() -> None:
    policy = load_policy()
    n_deny = len(policy.prompt_injection_deny)
    n_transforms = len(policy.prompt_injection_transforms)
    n_pii = len(policy.pii_patterns)
    n_tools = len(policy.tools)
    n_security = n_deny + n_transforms + n_pii
    n_policies = n_tools + n_security

    payload = compute_parameters_overview("fr")

    assert _kpi(payload, "policies") == str(n_policies)
    assert _kpi(payload, "security_rules") == str(n_security)
    assert _kpi(payload, "models") == str(len(available_model_ids()))
    # Every KPI is a real integer count (never a fabricated "1 284"-style literal).
    for k in payload["kpis"]:
        assert str(k["value"]).isdigit()  # type: ignore[index]


def test_config_version_and_footer_track_the_real_policy() -> None:
    policy = load_policy()
    settings = get_settings()
    payload = compute_parameters_overview("fr")

    cv = payload["config_version"]
    assert cv["version"] == f"policy v{policy.version}"  # type: ignore[index]
    assert cv["env"] == settings.environment.value.capitalize()  # type: ignore[index]
    assert payload["footer"]["version"] == f"policy v{policy.version}"  # type: ignore[index]


def test_recent_params_carry_the_actual_settings_values() -> None:
    settings = get_settings()
    payload = compute_parameters_overview("fr")
    by_name = {p["name"]: p["value"] for p in payload["recent_params"]}  # type: ignore[index,union-attr]

    assert by_name["memory.backend"] == settings.memory.backend
    assert by_name["memory.history_window"] == str(settings.memory.history_window)
    assert by_name["api.rate_limit_chat"] == settings.api.rate_limit_chat
    assert by_name["guard.fail_closed"] == str(settings.guard.fail_closed).lower()


def test_recent_params_are_categorized_by_config_tab() -> None:
    payload = compute_parameters_overview("fr")
    tab_keys = {
        "general",
        "security",
        "data",
        "models",
        "access",
        "notifications",
        "integrations",
        "audit",
        "system",
    }
    cats = {p["category"] for p in payload["recent_params"]}  # type: ignore[index,union-attr]
    # Every param sits under a real config tab, and several categories are populated
    # (so the tab bar filters to real content, not empty tables everywhere).
    assert cats <= tab_keys
    assert {"security", "models", "access", "system", "integrations", "audit"} <= cats


def test_config_state_sums_to_configured_and_is_all_active() -> None:
    payload = compute_parameters_overview("fr")
    configured = int(_kpi(payload, "configured"))
    state = payload["config_state"]
    assert state["total"] == configured  # type: ignore[index]
    slices = {s["key"]: s["count"] for s in state["slices"]}  # type: ignore[index,union-attr]
    # Every live parameter is active; there is no draft/deprecated store (honest).
    assert slices["active"] == configured
    assert slices["inactive"] == 0
    assert slices["drafts"] == 0
    assert slices["deprecated"] == 0


def test_usage_policies_and_tool_allowlist_are_real() -> None:
    settings = get_settings()
    policy = load_policy()
    payload = compute_parameters_overview("fr")
    values = [u["value"] for u in payload["usage_policies"]]  # type: ignore[index,union-attr]

    assert settings.api.rate_limit_chat in values
    assert settings.api.rate_limit_chat_global in values
    assert f"{len(policy.tools)} outils" in values


def test_localization_switches_the_usage_policy_labels() -> None:
    fr = compute_parameters_overview("fr")
    de = compute_parameters_overview("de")
    en = compute_parameters_overview("en")
    # The free-text labels are localized; the derived values stay identical.
    fr_label = fr["usage_policies"][0]["name"]  # type: ignore[index]
    de_label = de["usage_policies"][0]["name"]  # type: ignore[index]
    en_label = en["usage_policies"][0]["name"]  # type: ignore[index]
    assert fr_label != de_label != en_label
    assert fr["usage_policies"][0]["value"] == en["usage_policies"][0]["value"]  # type: ignore[index]


def test_models_configured_come_from_the_real_catalogue() -> None:
    payload = compute_parameters_overview("fr")
    models = payload["models_configured"]  # type: ignore[index]
    names = {m["name"] for m in models}  # type: ignore[index,union-attr]
    # Exactly the catalogue's known model ids — no invented model list.
    assert names == available_model_ids()
    # Every role is a real enum value; at least one model serves under the profile.
    assert all(m["role"] in ("chat", "embedding") for m in models)  # type: ignore[index]
    active = {m["name"] for m in models if m["status"] == "active"}  # type: ignore[index]
    assert active and active <= names


# ── OT-01 · « mes paramètres d'il y a 3 h » — le fold as-of des overrides ──────


class TestOverrideRowsAsOf:
    """The governed overrides at T are a real fold of the ledger, never today's store."""

    @staticmethod
    def _entries() -> list[dict[str, object]]:
        def ev(hour: int, key: str, args: dict[str, object]) -> dict[str, object]:
            return {
                "target": f"config_overrides.{key}",
                "occurred_at": f"2026-07-22T{hour:02d}:00:00+00:00",
                "actor": "ops@tessera",
                "arguments": args,
            }

        return [
            ev(10, "llm.chat_model", {"value": "mistral:7b", "reason": "essai"}),
            ev(11, "llm.chat_model", {"value": "gemma3:27b", "reason": "quality"}),
            {"target": "operator_item.transition", "occurred_at": "2026-07-22T11:30:00+00:00"},
            ev(12, "llm.chat_model", {"reverted": True, "reason": "retour au socle"}),
            ev(13, "llm.chat_model", {"value": "llama3.3:70b", "reason": "final"}),
            ev(13, "guard.escalation_threshold", {"value": "0.4", "reason": "pilote"}),
        ]

    def _rows_at(self, monkeypatch: pytest.MonkeyPatch, hour: int) -> dict[str, str]:
        from tessera.observability import parameters as parameters_mod

        entries = self._entries()
        monkeypatch.setattr(parameters_mod, "read_ledger_entries", lambda **_kw: list(entries))
        rows = parameters_mod.override_rows_as_of(f"2026-07-22T{hour:02d}:30:00+00:00")
        return {r.key: r.value for r in rows}

    def test_the_last_write_at_or_before_t_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._rows_at(monkeypatch, 10) == {"llm.chat_model": "mistral:7b"}
        assert self._rows_at(monkeypatch, 11) == {"llm.chat_model": "gemma3:27b"}

    def test_a_revert_removes_the_override_back_to_base(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._rows_at(monkeypatch, 12) == {}

    def test_a_rewrite_after_the_revert_reinstalls_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._rows_at(monkeypatch, 13) == {
            "llm.chat_model": "llama3.3:70b",
            "guard.escalation_threshold": "0.4",
        }

    def test_the_row_carries_the_verified_author_and_the_real_instant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tessera.observability import parameters as parameters_mod

        entries = self._entries()
        monkeypatch.setattr(parameters_mod, "read_ledger_entries", lambda **_kw: list(entries))
        rows = parameters_mod.override_rows_as_of("2026-07-22T10:30:00+00:00")
        assert len(rows) == 1
        assert rows[0].author == "ops@tessera"
        assert rows[0].updated_at.isoformat() == "2026-07-22T10:00:00+00:00"
        assert rows[0].reason == "essai"


class TestPolicySocleAsOf:
    """The policy socle at T is read from git history — or an honest None."""

    @staticmethod
    def _seed_repo(tmp_path: Path) -> Path:
        """A throwaway repo with policy.yaml committed at two controlled instants."""
        repo = tmp_path / "repo"
        target = repo / "src" / "tessera" / "guard" / "policy.yaml"
        target.parent.mkdir(parents=True)
        base = Path("src/tessera/guard/policy.yaml").read_text(encoding="utf-8")

        def run(*args: str, date: str | None = None) -> None:
            env = dict(
                os.environ,
                GIT_AUTHOR_NAME="Alice",
                GIT_AUTHOR_EMAIL="alice@example.org",
                GIT_COMMITTER_NAME="Alice",
                GIT_COMMITTER_EMAIL="alice@example.org",
            )
            if date is not None:
                env["GIT_AUTHOR_DATE"] = date
                env["GIT_COMMITTER_DATE"] = date
            subprocess.run(  # noqa: S603 — fixed argv, throwaway repo
                ["git", "-C", str(repo), *args],  # noqa: S607
                check=True,
                capture_output=True,
                env=env,
            )

        repo.mkdir(exist_ok=True)
        run("init", "-q")
        target.write_text(base, encoding="utf-8")
        run("add", ".")
        run("commit", "-qm", "policy v1", date="2026-01-01T00:00:00Z")
        bumped = re.sub(r"^version:.*$", "version: 99", base, count=1, flags=re.M)
        assert bumped != base, "the fixture must actually change the version line"
        target.write_text(bumped, encoding="utf-8")
        run("add", ".")
        run("commit", "-qm", "policy v99", date="2026-06-01T00:00:00Z")
        return repo

    def test_the_commit_at_or_before_t_wins(self, tmp_path: Path) -> None:
        from tessera.observability import parameters as parameters_mod

        repo = self._seed_repo(tmp_path)
        first = parameters_mod.policy_socle_as_of("2026-03-01T00:00:00Z", repo_root=repo)
        assert first is not None
        assert first.version != "99"  # the June commit does not exist in March
        assert first.committed_by == "Alice"
        assert first.committed_at.year == 2026 and first.committed_at.month == 1

        second = parameters_mod.policy_socle_as_of("2026-07-01T00:00:00Z", repo_root=repo)
        assert second is not None
        assert second.version == "99"

    def test_cannot_say_is_none_never_empty(self, tmp_path: Path) -> None:
        from tessera.observability import parameters as parameters_mod

        repo = self._seed_repo(tmp_path)
        # Before the first commit: the file has no history at T.
        assert parameters_mod.policy_socle_as_of("2025-01-01T00:00:00Z", repo_root=repo) is None
        # No repository at all (a container image): cannot say.
        bare = tmp_path / "not-a-repo"
        bare.mkdir()
        assert parameters_mod.policy_socle_as_of("2026-07-01T00:00:00Z", repo_root=bare) is None
        # A malformed instant never raises.
        assert parameters_mod.policy_socle_as_of("not-a-date", repo_root=repo) is None

    def test_compute_reads_the_folded_policy_numbers(self) -> None:
        from tessera.observability import parameters as parameters_mod

        at_t = parameters_mod.PolicySocleAtT(
            version="9.9",
            n_deny=1,
            n_transforms=2,
            n_pii=3,
            n_tools=4,
            committed_at=datetime(2026, 6, 1, tzinfo=UTC),
            committed_by="Alice",
        )
        payload = parameters_mod.compute_parameters_overview("fr", policy_at=at_t)
        version = payload["config_version"]
        assert isinstance(version, dict)
        assert version["version"] == "policy v9.9"
        assert version["modified_by"] == "Alice"
        kpis = {k["key"]: k["value"] for k in payload["kpis"]}  # type: ignore[union-attr,index]
        assert kpis["policies"] == str(4 + 1 + 2 + 3)
        assert kpis["security_rules"] == str(1 + 2 + 3)
