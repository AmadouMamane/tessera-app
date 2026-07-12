"""Deployment-aware secret resolution (ADR 0020).

Tessera resolves secrets very differently depending on where it runs, and this
module is the single seam that hides the difference from the rest of the code.

Providers (selected by ``TESSERA_SECRETS__PROVIDER``):

* ``env`` (default) — read from the process environment. On Cloud Run, GCP
  **Secret Manager** is mounted into the environment by the container start-up
  wrapper, so "env" *is* Secret Manager there. This keeps the cloud path free of
  any GCP client at runtime.
* ``gcp`` — read directly from GCP **Secret Manager** via the official client
  (lazy import). Useful when secrets are not pre-mounted as env vars.
* ``vault`` — the on-prem **premium** and recommended path: HashiCorp **Vault**
  / **OpenBao** via ``hvac`` (lazy import). Dynamic secrets, short-lived leases,
  rotation, and an audit log. The on-prem premium compose wires it by default.
* ``sops`` — the on-prem **standard / lighter** option: a SOPS+age encrypted
  file (``secrets.enc.yaml``) decrypted on demand by the ``sops`` binary. GitOps
  friendly, no server to run.

The point is not to implement any cryptography here — every backend delegates to
a battle-tested tool — but to make "where does a secret come from" an explicit,
swappable, deployment-aware decision rather than scattered ``os.environ`` reads.
"""

from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["SecretProvider", "get_secret_provider", "resolve_secret"]


class SecretProvider(Protocol):
    """A source of named secrets. Implementations must never log secret values."""

    def get(self, name: str) -> str | None:
        """Return the secret value for ``name`` or ``None`` if absent."""
        ...


class EnvSecretProvider:
    """Read secrets from the process environment (Cloud Run default).

    On Cloud Run the start-up wrapper materialises Secret Manager secrets as env
    vars, so this provider transparently covers the managed path.
    """

    def get(self, name: str) -> str | None:
        return os.environ.get(name)


class GcpSecretManagerProvider:
    """Read secrets directly from GCP Secret Manager (lazy client)."""

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id

    @lru_cache(maxsize=64)  # noqa: B019 — provider is a process-wide singleton
    def get(self, name: str) -> str | None:
        from google.cloud import secretmanager  # lazy: cloud-only dependency

        client = secretmanager.SecretManagerServiceClient()
        path = f"projects/{self._project_id}/secrets/{name}/versions/latest"
        try:
            response = client.access_secret_version(name=path)
        except Exception:  # not found / no access → treat as absent
            return None
        return response.payload.data.decode("utf-8")


class SopsSecretProvider:
    """On-prem standard: decrypt a SOPS+age file with the pinned ``sops`` binary.

    The whole file is decrypted once and cached in-process. We shell out to
    ``sops`` rather than reimplement age decryption — never hand-roll crypto.
    """

    def __init__(self, path: str) -> None:
        self._path = path

    @lru_cache(maxsize=1)  # noqa: B019 — provider is a process-wide singleton
    def _decrypted(self) -> Mapping[str, str]:
        try:
            completed = subprocess.run(  # noqa: S603 — fixed argv, no shell, pinned binary
                ["sops", "--decrypt", "--output-type", "json", self._path],  # noqa: S607
                capture_output=True,
                check=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return {}
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {}
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def get(self, name: str) -> str | None:
        return self._decrypted().get(name)


class VaultSecretProvider:
    """On-prem premium: read from HashiCorp Vault / OpenBao via hvac (lazy).

    Reads ``<mount>/data/<path>`` (KV v2) and returns the field matching the
    requested name. Dynamic secrets and rotation are Vault's job, not ours.
    """

    def __init__(self, url: str, token: str, mount: str, path: str) -> None:
        self._url = url
        self._token = token
        self._mount = mount
        self._path = path

    @lru_cache(maxsize=1)  # noqa: B019 — provider is a process-wide singleton
    def _data(self) -> Mapping[str, str]:
        import hvac  # lazy: on-prem-premium-only dependency

        client = hvac.Client(url=self._url, token=self._token)
        try:
            resp = client.secrets.kv.v2.read_secret_version(
                path=self._path, mount_point=self._mount
            )
        except Exception:
            return {}
        data = resp.get("data", {}).get("data", {})
        return {str(k): str(v) for k, v in data.items()}

    def get(self, name: str) -> str | None:
        return self._data().get(name)


@lru_cache(maxsize=1)
def get_secret_provider() -> SecretProvider:
    """Build the configured secret provider (process-wide singleton).

    Falls back to the env provider for any misconfiguration so that a broken
    secret backend degrades to "secret absent" rather than crashing start-up;
    callers already handle ``None`` (a missing optional secret).
    """
    sec = get_settings().secrets
    provider = sec.provider
    if provider == "gcp" and sec.gcp_project_id:
        return GcpSecretManagerProvider(sec.gcp_project_id)
    if provider == "sops" and sec.sops_file:
        return SopsSecretProvider(sec.sops_file)
    if provider == "vault" and sec.vault_url and sec.vault_token is not None:
        return VaultSecretProvider(
            url=sec.vault_url,
            token=sec.vault_token.get_secret_value(),
            mount=sec.vault_mount,
            path=sec.vault_path,
        )
    return EnvSecretProvider()


def resolve_secret(name: str) -> str | None:
    """Resolve a single named secret through the configured provider."""
    return get_secret_provider().get(name)
