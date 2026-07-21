"""Executable contracts for local demo-server secret posture."""

from __future__ import annotations

import re
import stat
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MAKEFILE = _ROOT / "Makefile"


def _run_dev_secrets(workspace: Path) -> subprocess.CompletedProcess[str]:
    """Run only the isolated secret bootstrap target in a throwaway workspace."""
    (workspace / "webapp" / "frontend").mkdir(parents=True, exist_ok=True)
    return subprocess.run(  # noqa: S603
        ["make", "-f", str(_MAKEFILE), "dev-secrets"],  # noqa: S607
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )


def _value(path: Path, name: str) -> str:
    """Read one dotenv value without accepting duplicates silently."""
    matches = re.findall(rf"^{re.escape(name)}=(.+)$", path.read_text(), re.MULTILINE)
    assert len(matches) == 1
    return matches[0]


def test_dev_secrets_create_session_and_one_shared_operator_key(tmp_path: Path) -> None:
    """A fresh worktree becomes login- and operator-capable without tracked secrets."""
    result = _run_dev_secrets(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    root_env = tmp_path / ".env.local"
    front_env = tmp_path / "webapp" / "frontend" / ".env.local"
    agent_key = _value(root_env, "TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY")
    front_key = _value(front_env, "TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY")
    assert agent_key == front_key
    assert len(_value(front_env, "AUTH_SECRET")) >= 32
    assert stat.S_IMODE(root_env.stat().st_mode) == 0o600
    assert stat.S_IMODE(front_env.stat().st_mode) == 0o600


def test_dev_secrets_copy_a_one_sided_operator_key(tmp_path: Path) -> None:
    """Repairing a partial setup preserves the existing trust-boundary value."""
    (tmp_path / "webapp" / "frontend").mkdir(parents=True)
    known_key = "a" * 64
    (tmp_path / ".env.local").write_text(
        f"TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY={known_key}\n",
        encoding="utf-8",
    )

    result = _run_dev_secrets(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    front_env = tmp_path / "webapp" / "frontend" / ".env.local"
    assert _value(front_env, "TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY") == known_key


def test_dev_secrets_refuse_two_different_operator_keys(tmp_path: Path) -> None:
    """Two valid-looking but different keys must not produce a cosmetic green boot."""
    front_dir = tmp_path / "webapp" / "frontend"
    front_dir.mkdir(parents=True)
    (tmp_path / ".env.local").write_text(
        f"TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY={'a' * 64}\n",
        encoding="utf-8",
    )
    (front_dir / ".env.local").write_text(
        f"TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY={'b' * 64}\n",
        encoding="utf-8",
    )

    result = _run_dev_secrets(tmp_path)

    assert result.returncode != 0
    assert "keys differ" in result.stdout


def test_dev_up_bootstraps_secrets_and_reuses_primary_observability_credentials() -> None:
    """Agent previews share the running observability stack's canonical secret file."""
    makefile = _MAKEFILE.read_text(encoding="utf-8")

    assert re.search(r"^dev-up:\s+dev-secrets$", makefile, re.MULTILINE)
    assert "git rev-parse --git-common-dir" in makefile
    assert 'primary_obs_env="$$(dirname "$$common_dir")/$$obs_env"' in makefile
    assert 'TESSERA_CLICKHOUSE_PASSWORD="$${TESSERA_CLICKHOUSE_PASSWORD:-$$obs_ch_pw}"' in makefile


def test_dev_secret_files_are_gitignored() -> None:
    """The bootstrap may create credentials only where git refuses to track them."""
    for relative_path in (".env.local", "webapp/frontend/.env.local"):
        result = subprocess.run(  # noqa: S603
            ["git", "check-ignore", "-q", relative_path],  # noqa: S607
            cwd=_ROOT,
            check=False,
        )
        assert result.returncode == 0, f"{relative_path} is not gitignored"


def test_dev_secret_bootstrap_does_not_embed_literal_secret_values() -> None:
    """Only runtime randomness belongs in the tracked Makefile."""
    makefile = _MAKEFILE.read_text(encoding="utf-8")
    target = makefile.split("dev-secrets:", 1)[1].split("# ──", 1)[0]

    assert "openssl rand -hex 32" in target
    assert re.search(r"\b[0-9a-f]{64}\b", target) is None
