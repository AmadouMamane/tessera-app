"""The twelve components are declared, and asked the question they can actually answer.

The operator asked twice why "les 12 composants" were absent from
`/fr/surveiller/observabilite`. The twelve are the stack — Redis, ClickHouse, Postgres, MinIO
and the rest — and the page showed four KPI cards about the agent process instead.

Two properties are pinned here, and the second is the one that decides whether this surface is
worth anything.

**The list is declared, not discovered.** Reading it from the Docker daemon would answer a
neighbouring question (ADR 0026): a container can be `Up` while the process inside refuses every
connection, and a component that vanishes entirely is reported by a discovery loop as "nothing
wrong" — because it never knew to look for it. A declared list goes red on a disappearance.

**Unreachable is not down.** A name that does not resolve means *this probe cannot see from
here*, which is BLIND; a connection actively refused means *the component is down*, which is
FAIL. Collapsing the two would make the page announce an outage every time it is run from a
host outside the compose network — the loudest possible false alarm, and the fastest way to
teach an operator to ignore it.
"""

from __future__ import annotations

import socket
import urllib.error
from typing import TYPE_CHECKING

from tessera.observability import stack_components as sc
from tessera.preflight import Verdict

if TYPE_CHECKING:
    import pytest


def test_the_twelve_of_the_stack_plus_the_one_outside_it() -> None:
    """A ratchet on the number itself: a component may be added, never silently dropped.

    Twelve until 2026-08-16, then thirteen. The thirteenth is not one of the stack: the twelve
    are asked over the private compose network, so all twelve can be green while the public URL
    serves 502 — and for thirty-two hours on 2026-08-12 they were. `public-canonical` is the
    only row that answers *can a visitor reach us*.
    """
    assert len(sc.STACK_COMPONENTS) == 13, (
        "the stack is twelve components plus the public edge; if one was genuinely added or "
        "removed, change this number deliberately and say which, because the page's headline "
        "counts them"
    )
    internal = [c for c in sc.STACK_COMPONENTS if not c.optional_address]
    assert len(internal) == 12, "the twelve of the stack itself must stay twelve"


def test_only_the_public_edge_may_go_without_a_declared_address() -> None:
    """The exemption is one component wide, and stays that way.

    `optional_address` says "no address here is a fact about this deployment, not about the
    component". That is true of the public host — no domain is baked into the image — and of
    nothing inside the compose network, where an address that went missing WOULD be a defect.
    Left ungated, this flag is how a component quietly stops being watched.
    """
    optional = [c.key for c in sc.STACK_COMPONENTS if c.optional_address]
    assert optional == ["public-canonical"], (
        f"only the public edge may declare no address; got {optional}. A compose-internal "
        "component with no address is a bug, and marking it optional hides the bug."
    )


def test_no_component_is_declared_twice() -> None:
    """Two entries under one key would render one row and probe two things."""
    keys = [c.key for c in sc.STACK_COMPONENTS]
    assert len(set(keys)) == len(
        keys
    ), f"duplicate keys: {sorted({k for k in keys if keys.count(k) > 1})}"


def test_every_component_carries_a_role_and_an_address() -> None:
    """A row with no role is a container name, which is an artefact of the compose project."""
    for component in sc.STACK_COMPONENTS:
        assert component.role, f"{component.key} declares no role"
        if component.optional_address:
            # …and it must be EMPTY, not a guess. A plausible default here would be probed and
            # reported as a verdict about somebody else's deployment.
            assert not component.default_address, (
                f"{component.key} is optional-address but ships a default "
                f"({component.default_address!r}) — a guessed public host would be probed and "
                "answered for as though it were ours"
            )
        else:
            assert ":" in component.default_address, f"{component.key} has no host:port"
        if component.kind == "http":
            assert component.path.startswith("/"), (
                f"{component.key} is probed over HTTP but declares no health path; '/' on "
                "Grafana is a redirect to a login page and proves only that a server exists"
            )


def test_the_two_redis_instances_are_not_the_same_address() -> None:
    """The trap found while wiring this: `redis` resolves to the OBS instance from the agent.

    Labelling two rows differently while probing one host would report a dead component as
    healthy — the exact shape of lie this surface exists to remove.
    """
    by_key = {c.key: c.default_address for c in sc.STACK_COMPONENTS}
    assert by_key["redis"] != by_key["langfuse-redis"]


def test_an_address_that_does_not_resolve_is_blind_not_down() -> None:
    component = sc.StackComponent("x", "role", "no-such-host.invalid:6379", "tcp")
    check = sc.probe_stack([component])[0]
    assert check.verdict is Verdict.BLIND, (
        "an unresolvable name means this probe cannot see from here, not that the component is "
        f"down; got {check.verdict} — {check.detail}"
    )


def test_a_refused_connection_is_down() -> None:
    """The positive control for the test above: BLIND must not swallow a real outage."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # The socket is closed, so the port resolves and actively refuses — a component that is down.
    component = sc.StackComponent("x", "role", f"127.0.0.1:{port}", "tcp")
    check = sc.probe_stack([component])[0]
    assert check.verdict is Verdict.FAIL, f"got {check.verdict} — {check.detail}"


def test_an_address_with_no_port_is_blind_rather_than_guessed() -> None:
    component = sc.StackComponent("x", "role", "hostname-only", "tcp")
    check = sc.probe_stack([component])[0]
    assert check.verdict is Verdict.BLIND
    assert "no host:port" in check.detail


def test_the_address_is_overridable_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deployed profile injects addresses; a hard-coded service name would be true in one
    compose file only."""
    component = sc.StackComponent("langfuse-web", "role", "unused:1", "tcp")
    monkeypatch.setenv("TESSERA_STACK_LANGFUSE_WEB", "no-such-host.invalid:1234")
    assert sc._address(component) == "no-such-host.invalid:1234"


def test_a_probe_that_explodes_reports_a_blind_spot(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hole in the witness is never a verdict about the thing."""

    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("probe is broken")

    monkeypatch.setattr(sc, "_probe_tcp", boom)
    check = sc.probe_stack([sc.StackComponent("x", "role", "host:1", "tcp")])[0]
    assert check.verdict is Verdict.BLIND
    assert "probe could not run" in check.detail


# ─────────────────── the thirteenth: the public edge (ADR 0052 §Amendment 2) ───────────────────
#
# The incident it exists for: 2026-08-12, the front container came back from a host reboot with
# no `restart: unless-stopped` and served 502 for thirty-two hours. Every one of the twelve was
# green throughout — correctly, because every one of them was up. Nothing on the deployment ever
# asked the question a visitor asks.


def test_the_public_edge_is_asked_over_https_at_the_endpoint_that_names_the_build() -> None:
    """Not a health path: `/api/version` traverses edge → tunnel → front AND names the build.

    `http` would be redirected or refused at the edge and recorded as an outage on a component
    that is perfectly healthy — the false alarm that teaches an operator to stop reading.
    """
    edge = sc.component_for("public-canonical")
    assert edge.scheme == "https", "the public edge speaks HTTPS and nothing else"
    assert edge.path == "/api/version"
    assert edge.timeout_s > sc._TIMEOUT_S, (
        "a round trip that leaves the machine, crosses an edge and returns through a tunnel "
        "needs more than the 3 s that is generous for a socket on the same host; otherwise "
        "latency is recorded as downtime"
    )


def test_no_public_host_declared_is_blind_and_never_a_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a laptop, in CI, or on any deployment that publishes nothing.

    The two wrong answers are equally bad and opposite: OK would claim a public URL is reachable
    when none is declared, and FAIL would report an outage on a deployment that has no public
    URL to be out. `probe_failed` — what an un-guarded probe would raise on `https:///…` — is a
    third wrong answer: it says *our probe is broken*, sending an operator to fix the witness.
    """
    monkeypatch.delenv("TESSERA_STACK_PUBLIC_CANONICAL", raising=False)
    observation = sc.probe_stack_observations([sc.component_for("public-canonical")])[0]
    assert observation.check.verdict is Verdict.BLIND
    assert (
        observation.outcome == "uninterrogable"
    ), f"got {observation.outcome} — a missing declaration is not a broken probe"
    assert (
        "TESSERA_STACK_PUBLIC_CANONICAL" in observation.check.detail
    ), "the message must name the variable that would fix it, not merely say 'unknown'"
    assert observation.address == ""


def test_a_declared_public_host_is_actually_probed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The positive control for the test above: BLIND must not swallow a declared host.

    `.invalid` is reserved by RFC 2606 and never resolves, so this reaches the resolver and
    stops there — no network, and an unresolvable name is BLIND for the same reason it is
    everywhere else in this module.
    """
    monkeypatch.setenv("TESSERA_STACK_PUBLIC_CANONICAL", "no-such-host.invalid")
    observation = sc.probe_stack_observations([sc.component_for("public-canonical")])[0]
    assert observation.outcome != "uninterrogable", "a declared host must be interrogated"
    assert observation.address.startswith("https://no-such-host.invalid/api/version"), (
        f"probed {observation.address!r} — the scheme and path must both come from the "
        "declaration"
    )


def test_the_probe_identifies_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a real User-Agent, Cloudflare answers 403 to `Python-urllib/3.x`.

    That is not a hypothetical: `scripts/deploy_diff.py` carries the same header for the same
    reason, learned the same way. A probe missing it would read every proxied host as broken —
    permanently, confidently, and with an HTTP status to back it up.
    """
    seen: dict[str, str] = {}

    def capture(request: object, timeout: float = 0.0) -> object:
        seen.update(getattr(request, "headers", {}))
        raise urllib.error.URLError("stop here — the header is what is under test")

    monkeypatch.setattr(sc, "urlopen_http", capture)
    sc.probe_stack_observations([sc.StackComponent("x", "role", "h:1", "http", "/p")])
    # urllib title-cases header names on the Request object.
    assert seen.get("User-agent") == sc._PROBE_USER_AGENT, f"headers sent: {seen}"
