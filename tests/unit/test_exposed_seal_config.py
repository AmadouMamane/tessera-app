"""ADR 0042 — exposed deployments earn, rather than print, “infalsifiable”."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.guard.seal import validate_exposed_seal_config
from tessera.settings import Environment, GuardSettings, Settings

if TYPE_CHECKING:
    from pathlib import Path


def _settings(
    *,
    environment: Environment,
    cert: Path | None = None,
    provider: str = "rfc3161",
    url: str | None = "https://tsa.example.test",
    qualified: bool = True,
    interval: int = 3600,
    staleness: int = 7200,
    verify_interval: int = 900,
) -> Settings:
    return Settings(
        environment=environment,
        guard=GuardSettings(
            seal_provider=provider,
            seal_tsa_url=url,
            seal_tsa_cert=cert,
            seal_tsa_qualified=qualified,
            seal_interval_s=interval,
            seal_staleness_budget_s=staleness,
            ledger_verify_interval_s=verify_interval,
        ),
    )


@pytest.mark.parametrize("environment", [Environment.LOCAL, Environment.CI])
def test_local_and_ci_keep_the_honest_no_seal_posture(environment: Environment) -> None:
    """Hermetic environments may run without an external trust service."""
    settings = Settings(environment=environment, guard=GuardSettings(seal_provider="none"))
    validate_exposed_seal_config(settings)


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_exposed_environments_accept_a_complete_qualified_posture(
    environment: Environment, tmp_path: Path
) -> None:
    """A qualified provider with a pinned, readable trust root earns the boot posture."""
    cert = tmp_path / "tsa-ca.pem"
    cert.write_text("test trust root", encoding="utf-8")

    validate_exposed_seal_config(_settings(environment=environment, cert=cert))


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"provider": "none"}, "SEAL_PROVIDER"),
        ({"url": "http://tsa.example.test"}, "absolute HTTPS"),
        ({"qualified": False}, "SEAL_TSA_QUALIFIED"),
        ({"interval": 0}, "SEAL_INTERVAL_S"),
        ({"staleness": 10_801}, "one and two seal intervals"),
        ({"verify_interval": 3_601}, "LEDGER_VERIFY_INTERVAL_S"),
    ],
)
def test_production_refuses_each_unearned_posture(
    override: dict[str, object], expected: str, tmp_path: Path
) -> None:
    """Every load-bearing part of the public claim is fail-closed."""
    cert = tmp_path / "tsa-ca.pem"
    cert.write_text("test trust root", encoding="utf-8")
    kwargs: dict[str, object] = {"environment": Environment.PRODUCTION, "cert": cert}
    kwargs.update(override)

    with pytest.raises(RuntimeError, match=expected):
        validate_exposed_seal_config(_settings(**kwargs))  # type: ignore[arg-type]


def test_production_refuses_a_missing_trust_root(tmp_path: Path) -> None:
    """A configured path is not evidence; the certificate must exist and be readable."""
    with pytest.raises(RuntimeError, match="readable pinned trust-root"):
        validate_exposed_seal_config(
            _settings(environment=Environment.PRODUCTION, cert=tmp_path / "missing.pem")
        )
