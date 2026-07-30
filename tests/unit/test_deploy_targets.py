"""The deploy-targets config parses, and the anti-divergence witness actually judges (ADR 0048).

`scripts/deploy_diff.py` fetches /api/version on every declared host and returns a verdict by exit
code. The network fetch is not unit-testable, but the two things that make it a WITNESS rather than
decoration are: the config it reads has the shape it assumes, and the pure `verdict` maps
observations to the right exit code — match (0), divergence (1), or blind (2) when it cannot see
every host. ADR 0026: a witness that cannot see may never report "ok".
"""

from __future__ import annotations

from scripts.deploy_diff import (
    EXIT_BLIND,
    EXIT_DIVERGENT,
    EXIT_OK,
    _build_request,
    hosts_for,
    load_targets,
    verdict,
)


def test_shipped_targets_yaml_parses_and_has_the_assumed_shape() -> None:
    cfg = load_targets()
    assert cfg.domain and cfg.canonical and cfg.image
    assert cfg.primary in cfg.targets
    assert {"onprem", "gcp"} <= set(cfg.targets)
    for spec in cfg.targets.values():
        assert {"subdomain", "front", "agent_url"} <= set(spec)


def test_request_carries_a_real_user_agent_not_python_urllib() -> None:
    # Cloudflare 403s the default Python-urllib UA; without a real one the witness goes blind.
    req = _build_request("onprem.amadoumamane.fr")
    assert req.full_url == "https://onprem.amadoumamane.fr/api/version"
    ua = req.get_header("User-agent") or ""
    assert ua and "python-urllib" not in ua.lower()


def test_hosts_include_both_targets_and_the_canonical_switch() -> None:
    cfg = load_targets()
    hosts = hosts_for(cfg)
    values = set(hosts.values())
    assert f"{cfg.targets['onprem']['subdomain']}.{cfg.domain}" in values
    assert f"{cfg.targets['gcp']['subdomain']}.{cfg.domain}" in values
    assert f"{cfg.canonical}.{cfg.domain}" in values  # the public host, the switch


def test_all_hosts_same_real_sha_is_a_match() -> None:
    obs = {"onprem": "abc123", "gcp": "abc123", "canonical(onprem)": "abc123"}
    code, _ = verdict("amadoumamane.fr", obs)
    assert code == EXIT_OK


def test_a_stale_canonical_is_a_named_divergence() -> None:
    # exactly the "an old version is still served" situation the operator flagged
    obs = {"onprem": "new456", "gcp": "new456", "canonical(onprem)": "old000"}
    code, message = verdict("amadoumamane.fr", obs)
    assert code == EXIT_DIVERGENT
    assert "old000" in message and "canonical(onprem)" in message


def test_an_unreachable_host_is_blind_never_ok() -> None:
    obs = {"onprem": "abc123", "gcp": None, "canonical(onprem)": "abc123"}
    assert verdict("amadoumamane.fr", obs)[0] == EXIT_BLIND


def test_an_unstamped_dev_build_is_blind() -> None:
    obs = {"onprem": "dev", "gcp": "abc123", "canonical(onprem)": "abc123"}
    assert verdict("amadoumamane.fr", obs)[0] == EXIT_BLIND


def test_an_unset_domain_is_blind() -> None:
    obs = {"onprem": "abc123", "gcp": "abc123"}
    assert verdict("CHANGE-ME.example", obs)[0] == EXIT_BLIND
