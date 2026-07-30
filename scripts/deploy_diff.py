"""Deploy-diff — the anti-divergence witness for the two deployment targets (ADR 0048).

Fetches ``GET /api/version`` from every live host (the two targets AND the canonical public host)
and returns a verdict BY EXIT CODE:

* ``0`` — every reachable host serves the same real build SHA. Match.
* ``1`` — the served SHAs diverge (named). This is the "an old version is still served" bug, caught.
* ``2`` — blind: a host is unreachable, un-stamped (``sha=dev``), or the domain is unset. A witness
  that cannot see every host may never report "ok" (ADR 0026).

Reads ``infra/deploy/targets.yaml`` (non-secret wiring only). No network write. The pure
:func:`verdict` is unit-tested without a network so the witness is proven to actually judge.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_TARGETS_PATH = Path(__file__).resolve().parents[1] / "infra" / "deploy" / "targets.yaml"
_PLACEHOLDER_SHAS = frozenset({"", "dev", "unknown"})

EXIT_OK = 0
EXIT_DIVERGENT = 1
EXIT_BLIND = 2

#: A parity claim needs at least two hosts to compare — one host proves nothing about divergence.
_MIN_HOSTS_TO_COMPARE = 2


@dataclass(frozen=True)
class Targets:
    """The parsed, validated deploy-targets config."""

    domain: str
    canonical: str
    primary: str
    image: str
    targets: dict[str, dict[str, str]]


def load_targets(path: Path = _TARGETS_PATH) -> Targets:
    """Parse and validate ``targets.yaml``; raise ``ValueError`` on any missing/ill-shaped field."""
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    for key in ("domain", "canonical", "primary", "image", "targets"):
        if key not in raw:
            raise ValueError(f"{path}: missing required key '{key}'")
    tgts_raw = raw["targets"]
    if not isinstance(tgts_raw, dict) or not tgts_raw:
        raise ValueError(f"{path}: 'targets' must be a non-empty mapping")
    targets: dict[str, dict[str, str]] = {}
    for name, spec in tgts_raw.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: target '{name}' must be a mapping")
        for field_name in ("subdomain", "front", "agent_url"):
            if field_name not in spec:
                raise ValueError(f"{path}: target '{name}' is missing '{field_name}'")
        targets[str(name)] = {str(k): str(v) for k, v in spec.items()}
    if str(raw["primary"]) not in targets:
        raise ValueError(f"{path}: primary '{raw['primary']}' is not a declared target")
    return Targets(
        domain=str(raw["domain"]),
        canonical=str(raw["canonical"]),
        primary=str(raw["primary"]),
        image=str(raw["image"]),
        targets=targets,
    )


def hosts_for(cfg: Targets) -> dict[str, str]:
    """Map each label to its fully-qualified host: the two targets plus the canonical switch."""
    hosts = {name: f"{spec['subdomain']}.{cfg.domain}" for name, spec in cfg.targets.items()}
    hosts[f"canonical({cfg.primary})"] = f"{cfg.canonical}.{cfg.domain}"
    return hosts


def _fetch_sha(host: str, timeout: float = 5.0) -> str | None:
    """Return the ``sha`` from ``https://<host>/api/version``, or ``None`` if unreachable."""
    url = f"https://{host}/api/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — https to our host
            payload: Any = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    sha = payload.get("sha")
    return sha if isinstance(sha, str) else None


def verdict(domain: str, observations: dict[str, str | None]) -> tuple[int, str]:
    """Pure verdict from ``label -> sha`` (``None`` = unreachable). No network — unit-testable."""
    if "CHANGE-ME" in domain:
        return EXIT_BLIND, f"domain is unset ('{domain}') — set it in targets.yaml. CannotSay."
    if len(observations) < _MIN_HOSTS_TO_COMPARE:
        return EXIT_BLIND, "fewer than two hosts to compare. CannotSay."
    unreachable = sorted(h for h, s in observations.items() if s is None)
    if unreachable:
        return EXIT_BLIND, f"unreachable: {', '.join(unreachable)} — cannot compare. CannotSay."
    placeholders = sorted(h for h, s in observations.items() if s in _PLACEHOLDER_SHAS)
    if placeholders:
        return EXIT_BLIND, (
            f"un-stamped (sha in {sorted(_PLACEHOLDER_SHAS)}): {', '.join(placeholders)} "
            f"— parity cannot be verified. CannotSay."
        )
    shas = {s for s in observations.values() if s is not None}
    if len(shas) == 1:
        return EXIT_OK, f"all {len(observations)} hosts serve {next(iter(shas))}. Match."
    detail = ", ".join(f"{h}={s}" for h, s in sorted(observations.items()))
    return EXIT_DIVERGENT, f"DIVERGENCE: the hosts serve different builds -> {detail}"


def main() -> int:
    """Fetch every host's served SHA, print the evidence, and return the verdict exit code."""
    cfg = load_targets()
    hosts = hosts_for(cfg)
    observations = {label: _fetch_sha(host) for label, host in hosts.items()}
    for label, host in sorted(hosts.items()):
        print(f"  {label:22} https://{host}/api/version -> {observations[label]}")
    code, message = verdict(cfg.domain, observations)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
