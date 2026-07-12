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
local loop depends on. **Staging does not**, on the operator's call of 2026-07-12: a staging
agent is routinely internet-reachable, and an unset bearer there publishes exactly the same
ledger, GDPR surface and runtime settings as it would in production. The line is drawn at
*exposed*, not at *production*.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.api.security import _missing_bearer_message, validate_bearer_token
from tessera.settings import Environment, get_settings

if TYPE_CHECKING:
    import pytest as _pytest


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    get_settings.cache_clear()


@pytest.mark.parametrize("environment", [Environment.PRODUCTION, Environment.STAGING])
def test_a_deployed_agent_without_a_bearer_refuses_to_start(
    monkeypatch: _pytest.MonkeyPatch, environment: Environment
) -> None:
    """The finding, closed: no bearer on an exposed agent is a hard boot failure.

    Pre-fix, production booted happily and served /audit, /memory and /settings to the
    internet. **Staging did so even after the first fix** — ``is_production()`` was the test,
    and staging is not production. It is, however, on the internet, which is the only property
    the bearer cares about.
    """
    monkeypatch.setenv("TESSERA_ENVIRONMENT", environment.value)
    monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError) as excinfo:
        validate_bearer_token()

    assert str(excinfo.value) == _missing_bearer_message(environment)
    # The message must name the posture it refused, or the operator reading a crashed
    # container's logs cannot tell which deployment they misconfigured.
    assert environment.value in str(excinfo.value)


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_a_deployed_agent_with_a_bearer_starts(
    monkeypatch: _pytest.MonkeyPatch, environment: str
) -> None:
    """The correctly-configured deployment is unaffected."""
    monkeypatch.setenv("TESSERA_ENVIRONMENT", environment)
    monkeypatch.setenv("TESSERA_API__BEARER_TOKEN", "a-real-secret")
    get_settings.cache_clear()

    validate_bearer_token()  # must not raise


@pytest.mark.parametrize("environment", ["local", "ci"])
def test_dev_and_ci_still_boot_without_secret_material(
    monkeypatch: _pytest.MonkeyPatch, environment: str
) -> None:
    """The documented posture, preserved — and now drawn as narrowly as it can be.

    Guards against over-correcting: demanding a bearer everywhere would break the local loop
    and CI, which is exactly the pressure that produces a re-loosened check later. `local` and
    `ci` are the only two postures that are genuinely not reachable from outside, so they are
    the only two exempted.
    """
    monkeypatch.setenv("TESSERA_ENVIRONMENT", environment)
    monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
    get_settings.cache_clear()

    validate_bearer_token()  # must not raise


def test_every_environment_is_classified_exposed_or_not() -> None:
    """A new Environment member must be a deliberate call, not a default into the exemption.

    Adding, say, `PREVIEW` to the enum would silently land on the permissive side of this
    check — a new internet-reachable posture booting with no bearer, which is the exact shape
    of the bug being closed. This fails until someone classifies it.
    """
    from tessera.api.security import _BEARER_REQUIRED_ENVIRONMENTS

    exempt = {Environment.LOCAL, Environment.CI}

    assert set(Environment) == _BEARER_REQUIRED_ENVIRONMENTS | exempt


def test_the_boot_check_runs_in_build_app() -> None:
    """A check nothing calls is not a check. Pin it to the composition root."""
    import inspect

    from tessera.api import main

    source = inspect.getsource(main.build_app)
    assert "validate_bearer_token()" in source
