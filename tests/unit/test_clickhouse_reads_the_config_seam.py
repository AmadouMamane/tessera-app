"""The ClickHouse resolver reads the file operators are told to configure.

CLAUDE.md: *"Local development uses a gitignored `.env.local` derived from `.env.example`."*
`tessera.settings.Settings` honours that — `env_file=(".env", ".env.local")`. This one adapter
did not: it read `os.environ` alone and, finding nothing, fell back to the literal default
password `clickhouse`. So a host-side read got a 403 from a store that was up, healthy, and
answering the container perfectly.

That is not a cosmetic inconsistency. On 2026-08-05 it made every measurement taken from an agent
worktree BLIND, while the same code in the container saw 500 rows — and a blind read that
presents itself as an empty store is precisely the defect commit `e7184679` fixed one layer up.
The two halves belong together: the code no longer lies about not being able to read, and the
configuration no longer makes it unable to read for no reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.spine.adapters.clickhouse import (
    ClickHouseConfig,
    _dotenv_files,
    _dotenv_values,
)
from tessera.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _use_settings_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real dotenv declaration, which `conftest` neutralises suite-wide.

    That neutralisation is deliberate and correct — a test run must not pick up a developer's
    `.env.local`. It is restored here, in the four tests that are ABOUT the file, and nowhere
    else.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", (".env", ".env.local"))


def test_the_resolver_asks_settings_rather_than_keeping_its_own_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No second list to drift — and the suite's guard is inherited, not bypassed.

    Both halves matter. A private copy of the paths would diverge from `Settings` exactly as the
    release rules diverged from the release column; and it would silently undo `conftest`'s
    `env_file = None`, letting a developer's real credentials leak into a test run.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    assert _dotenv_files() == (), "with Settings reading no file, this must read none either"

    monkeypatch.setitem(Settings.model_config, "env_file", ("a.env", "b.env"))
    assert _dotenv_files() == ("a.env", "b.env")

    monkeypatch.setitem(Settings.model_config, "env_file", "solo.env")
    assert _dotenv_files() == ("solo.env",), "a single path is a path, not a sequence of chars"


def test_a_value_in_dotenv_reaches_the_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The assertion that was false: `.env.local` had no effect on this component."""
    _use_settings_files(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TESSERA_CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("TESSERA_CLICKHOUSE_URL", raising=False)
    (tmp_path / ".env.local").write_text(
        "TESSERA_CLICKHOUSE_PASSWORD=from-dotenv\nTESSERA_CLICKHOUSE_URL=http://host:18123\n",
        encoding="utf-8",
    )
    config = ClickHouseConfig.from_env()
    assert config.password == "from-dotenv"  # noqa: S105 — a literal written by this test
    assert config.url == "http://host:18123"


def test_the_process_environment_still_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deployed profiles resolve from Secret Manager into the environment (ADR 0014).

    If the file could override it, a stale `.env.local` left on a machine would silently
    outrank the injected secret — so this direction matters more than the one above.
    """
    _use_settings_files(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.local").write_text(
        "TESSERA_CLICKHOUSE_PASSWORD=from-dotenv\n", encoding="utf-8"
    )
    monkeypatch.setenv("TESSERA_CLICKHOUSE_PASSWORD", "from-environment")
    assert ClickHouseConfig.from_env().password == "from-environment"  # noqa: S105 — a literal


def test_no_dotenv_at_all_keeps_the_documented_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: the fallback must not become a hard requirement on a file."""
    monkeypatch.chdir(tmp_path)
    for name in ("URL", "USER", "PASSWORD", "DATABASE"):
        monkeypatch.delenv(f"TESSERA_CLICKHOUSE_{name}", raising=False)
    config = ClickHouseConfig.from_env()
    assert config.url == "http://localhost:18123"
    assert config.database == "tessera"


def test_the_parser_survives_the_shapes_a_dotenv_file_really_has(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Comments, blank lines, quotes, `export`, and `=` inside the value.

    A credential parsed wrong yields a 403 that looks exactly like a missing store — the very
    confusion this seam exists to end — so the shapes are exercised rather than assumed.
    """
    _use_settings_files(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.local").write_text(
        "\n# a comment\n\n"
        # The VALUE is the fixture: this test exists to prove the parser strips the quotes and
        # keeps the `=` signs inside them. gitleaks flagged it on 2026-08-05 — correctly by
        # shape, wrongly by fact. Annotated narrowly rather than by widening a rule that would
        # then miss a real one, and the annotation must sit on the SAME line as the finding:
        # put one line above, as it was first written, gitleaks ignores it entirely.
        'TESSERA_CLICKHOUSE_PASSWORD="quoted=with=equals"\n'  # gitleaks:allow
        "export TESSERA_CLICKHOUSE_USER=exported\n"
        "not a pair\n"
        "=orphan-value\n",
        encoding="utf-8",
    )
    values = _dotenv_values()
    assert values["TESSERA_CLICKHOUSE_PASSWORD"] == "quoted=with=equals"  # noqa: S105 — a literal
    assert values["TESSERA_CLICKHOUSE_USER"] == "exported"
    assert "" not in values, "a line with no name on the left is not a setting of the empty name"


def test_env_local_outranks_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same precedence as Settings: the `.local` overlay is the one an operator edits."""
    _use_settings_files(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TESSERA_CLICKHOUSE_PASSWORD", raising=False)
    (tmp_path / ".env").write_text("TESSERA_CLICKHOUSE_PASSWORD=base\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("TESSERA_CLICKHOUSE_PASSWORD=overlay\n", encoding="utf-8")
    assert ClickHouseConfig.from_env().password == "overlay"  # noqa: S105 — a literal
