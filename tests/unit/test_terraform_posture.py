"""B4 — the deployed posture cannot silently reopen.

Audit 2026-07-10, **P0 `terraform-exposure`** (variables.tf:147 · cloud_run.tf:11/162 ·
armor.tf:126) and **P1 `secret-default`** (secrets.tf:38, :47).

The banking agent's Cloud Run service defaulted to ``allowed_invokers = ["allUsers"]`` with
``INGRESS_TRAFFIC_ALL``: the whole internet could invoke it on its run.app URL, bypassing the
frontend (the only intended caller) and with it Cloud Armor, which fronts only the load
balancer. Two secrets — the service bearer and the HMAC key over the compliance ledger —
defaulted to the literal string ``REPLACE_ME`` under ``ignore_changes``, so a forgotten
rotation shipped a publicly known constant and left audit entries forgeable by anyone who had
read this repository.

THIS IS A RATCHET, NOT A PROOF. Terraform is not installed in this environment and the gate
does not run ``terraform validate``; these tests read the HCL as text. They cannot tell you
the configuration is correct — only that the specific defaults which were shipped open have
not come back. The `.tf` changes themselves remain unverified by any tool, which is exactly
why lane B halts for human review instead of merging.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_TERRAFORM = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def _read(name: str) -> str:
    return (_TERRAFORM / name).read_text(encoding="utf-8")


def _default_of(hcl: str, variable: str) -> str:
    """The `default = ...` line of a named variable block."""
    block = re.search(
        rf'variable\s+"{re.escape(variable)}"\s*\{{(.*?)\n\}}',
        hcl,
        re.DOTALL,
    )
    assert block, f"variable {variable!r} not found"
    default = re.search(r"^\s*default\s*=\s*(.+)$", block.group(1), re.MULTILINE)
    assert default, f"variable {variable!r} has no default"
    return default.group(1).strip()


def test_the_agent_is_not_invocable_by_the_internet_by_default() -> None:
    """The finding: allowed_invokers defaulted to ["allUsers"] — the whole internet."""
    assert _default_of(_read("variables.tf"), "allowed_invokers") == "[]"


def test_ingress_does_not_default_to_the_open_internet() -> None:
    """INGRESS_TRAFFIC_ALL publishes run.app and walks around Cloud Armor."""
    assert "INGRESS_TRAFFIC_ALL" not in _default_of(_read("variables.tf"), "ingress")


def test_cloud_run_takes_its_ingress_from_the_variable() -> None:
    """It was hardcoded, so no override could have closed it."""
    cloud_run = _read("cloud_run.tf")
    assert "ingress  = var.ingress" in cloud_run
    assert 'ingress  = "INGRESS_TRAFFIC_ALL"' not in cloud_run


@pytest.mark.parametrize("secret", ["bearer_token", "audit_signing_key"])
def test_no_secret_ships_as_a_publicly_known_constant(secret: str) -> None:
    """REPLACE_ME + ignore_changes = a forgotten rotation ships a constant from a public repo.

    For `audit_signing_key` that is not a theoretical risk: it is the HMAC key over the
    compliance ledger. A guessable key makes the tamper-evidence decorative.
    """
    secrets_tf = _read("secrets.tf")
    assert f"random_password.{secret}.result" in secrets_tf
    assert f'resource "random_password" "{secret}"' in secrets_tf


def test_replace_me_is_gone_from_the_credential_secrets() -> None:
    """No credential may be seeded with a value that is written down in the repository."""
    secrets_tf = _read("secrets.tf")
    credential_placeholders = [
        line
        for line in secrets_tf.splitlines()
        if "REPLACE_ME" in line and not line.lstrip().startswith("#")
    ]
    assert credential_placeholders == []


def test_the_database_requires_tls() -> None:
    """The instance holds customer transcripts and long-term memory."""
    assert 'ssl_mode = "ENCRYPTED_ONLY"' in _read("postgres.tf")


def test_the_audit_bucket_retention_is_locked() -> None:
    """An audit trail that can be quietly shortened is not tamper-evident."""
    observability_tf = _read("observability.tf")
    assert "retention_policy" in observability_tf
    assert "is_locked        = true" in observability_tf
