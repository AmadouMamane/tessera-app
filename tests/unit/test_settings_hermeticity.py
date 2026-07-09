"""The unit suite resolves settings exactly as CI does — never as the operator's machine.

``Settings`` reads a gitignored ``.env.local`` for local development. CI has no such file, so a
suite that inherits it asserts two different things depending on where it runs: the shipped
defaults in CI, the operator's local overrides on a workstation. Both directions are harmful — a
flipped switch turns a green suite red (this is how ADR 0019 §I4's canary master switch, enabled
for go-and-observe, broke ``test_posture_idle_by_default``), and a stale override can turn a red
suite green, which is worse.

``conftest._isolated_env`` cuts the file out. These are the ratchets that keep it cut.
"""

from __future__ import annotations

import os

from tessera.settings import Settings, get_settings

# Every override the suite depends on is pinned in `_isolated_env`, in the open. Nothing may be
# inherited from a file on disk.


def test_settings_do_not_read_the_dotenv_files() -> None:
    assert Settings.model_config["env_file"] is None


def test_shipped_defaults_hold_regardless_of_the_operators_env_local() -> None:
    # The canary master switch is the canonical case: an operator running the scheduler locally
    # sets TESSERA_OBSERVABILITY__CANARY_SCHEDULER_ENABLED=1 in `.env.local`. The suite must still
    # see the shipped default.
    assert get_settings().observability.canary_scheduler_enabled is False


def test_a_real_environment_variable_still_wins() -> None:
    # Cutting the file must not cut the *environment*: `_isolated_env` pins its overrides through
    # real env vars, and deployments configure Tessera the same way.
    assert os.environ["TESSERA_ENVIRONMENT"] == "ci"
    assert get_settings().environment.value == "ci"
