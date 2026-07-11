"""B3 — the bearer no longer fails OPEN.

Audit 2026-07-10, **P0 `auth-fail-open`** — security.py:80 · middleware.py:68 · main.py:265.

The session signing key and the operator assertion key each already refused to boot when
absent in production. The bearer did not. Left unset it made ``require_bearer`` return early
and ``AuthMiddleware`` a no-op — publishing the audit ledger, the memory surface (GDPR data)
and the runtime settings endpoints to anyone who asked.

The failure pointed the wrong way: a *missing secret opened the doors*. A deployment that
forgot one environment variable was wide open and said nothing. That is the definition of
fail-open, and it is the one property a security control may never have.

Dev and CI stay reachable with no secret material — the documented posture, which the whole
local loop depends on. Only production refuses to start.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.api.security import _MISSING_BEARER_IN_PROD, validate_bearer_token
from tessera.settings import get_settings

if TYPE_CHECKING:
    import pytest as _pytest


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    get_settings.cache_clear()


def test_production_without_a_bearer_refuses_to_start(monkeypatch: _pytest.MonkeyPatch) -> None:
    """The finding, closed: no bearer in prod is a hard boot failure, not a silent no-op.

    Pre-fix this booted happily and served /audit, /memory and /settings to the internet.
    """
    monkeypatch.setenv("TESSERA_ENVIRONMENT", "production")
    monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError) as excinfo:
        validate_bearer_token()

    assert str(excinfo.value) == _MISSING_BEARER_IN_PROD


def test_production_with_a_bearer_starts(monkeypatch: _pytest.MonkeyPatch) -> None:
    """The correctly-configured production deployment is unaffected."""
    monkeypatch.setenv("TESSERA_ENVIRONMENT", "production")
    monkeypatch.setenv("TESSERA_API__BEARER_TOKEN", "a-real-secret")
    get_settings.cache_clear()

    validate_bearer_token()  # must not raise


@pytest.mark.parametrize("environment", ["local", "ci", "staging"])
def test_dev_and_ci_still_boot_without_secret_material(
    monkeypatch: _pytest.MonkeyPatch, environment: str
) -> None:
    """The documented posture, preserved.

    Guards against over-correcting: demanding a bearer everywhere would break the local
    loop and CI, which is exactly the pressure that produces a re-loosened check later.
    """
    monkeypatch.setenv("TESSERA_ENVIRONMENT", environment)
    monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
    get_settings.cache_clear()

    validate_bearer_token()  # must not raise


def test_the_boot_check_runs_in_build_app() -> None:
    """A check nothing calls is not a check. Pin it to the composition root."""
    import inspect

    from tessera.api import main

    source = inspect.getsource(main.build_app)
    assert "validate_bearer_token()" in source
