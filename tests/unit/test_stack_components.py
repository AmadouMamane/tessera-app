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
from typing import TYPE_CHECKING

from tessera.observability import stack_components as sc
from tessera.preflight import Verdict

if TYPE_CHECKING:
    import pytest


def test_exactly_the_twelve_the_operator_counted() -> None:
    """A ratchet on the number itself: a component may be added, never silently dropped."""
    assert len(sc.STACK_COMPONENTS) == 12, (
        "the stack is twelve components; if one was genuinely added or removed, change this "
        "number deliberately and say which, because the page's headline counts them"
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
