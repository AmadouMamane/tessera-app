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

THIS IS A RATCHET, NOT A PROOF. These tests read the HCL as text and only prevent known
deployment regressions. The blocking CI job additionally runs Terraform 1.8.5 ``fmt`` and
``validate``; the release workflow's environment-scoped ``plan`` is the final provider/GCP
contract before apply.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_TERRAFORM = Path(__file__).resolve().parents[2] / "infra" / "terraform"
_ROOT = _TERRAFORM.parents[1]


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


def test_secret_manager_access_is_scoped_per_secret() -> None:
    """Neither runtime may inherit project-wide access to every secret in the project."""
    main_tf = _read("main.tf")
    secrets_tf = _read("secrets.tf")
    assert "roles/secretmanager.secretAccessor" not in main_tf
    assert 'resource "google_secret_manager_secret_iam_member" "runtime_access"' in secrets_tf
    assert (
        'resource "google_secret_manager_secret_iam_member" "frontend_runtime_access"' in secrets_tf
    )


@pytest.mark.parametrize(
    "name",
    [
        "AUTH_SECRET",
        "TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY",
        "TESSERA_AUTH_ADMIN_PASSWORD",
        "TESSERA_AUTH_AUDITOR_PASSWORD",
        "TESSERA_AUTH_COLLECTIONS_PASSWORD",
    ],
)
def test_frontend_runtime_secrets_are_injected(name: str) -> None:
    assert f'name = "{name}"' in _read("cloud_run_frontend.tf")


def test_exposed_agent_is_configured_for_a_qualified_external_seal() -> None:
    cloud_run = _read("cloud_run.tf")
    assert 'name  = "TESSERA_GUARD__SEAL_PROVIDER"' in cloud_run
    assert 'value = "rfc3161"' in cloud_run
    assert 'name  = "TESSERA_GUARD__SEAL_TSA_QUALIFIED"' in cloud_run
    assert 'value = "true"' in cloud_run
    assert 'mount_path = "/var/run/secrets/tessera"' in cloud_run
    assert "data.google_secret_manager_secret.seal_tsa_cert" in cloud_run


def test_release_workflow_builds_and_deploys_both_images() -> None:
    deploy = (_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert "infra/docker/Dockerfile.agent" in deploy
    assert "infra/docker/Dockerfile.frontend" in deploy
    assert "provenance: true" in deploy
    assert "sbom: true" in deploy
    assert '-var "image=${{ steps.image.outputs.agent_image }}"' in deploy
    assert '-var "frontend_image=${{ steps.image.outputs.frontend_image }}"' in deploy
    assert "TESSERA_SEAL_TSA_CERT_SECRET_ID" in deploy
    assert "TESSERA_SEAL_TSA_URL" in deploy


def test_ci_validates_terraform_before_e2e() -> None:
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "terraform fmt -check -recursive infra/terraform" in ci
    assert "terraform init -backend=false" in ci
    assert "terraform validate" in ci
