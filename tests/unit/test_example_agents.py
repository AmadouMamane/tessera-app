"""The examples' *absence* of imports is their assertion — so the gate checks it.

``examples/hello-agent``, ``examples/turn-agent`` and ``examples/duplex-agent`` are the platform
witnesses (see ``examples/README.md``). Each proves exactly one claim, and each proof rests on what
the file does — or pointedly does not — import:

- none imports ``tessera`` — they demonstrate properties of agents the platform did not build;
- ``hello_agent`` speaks OTLP and opens no socket (publish-only, ADR 0017 §F);
- ``turn_agent`` serves HTTP and emits no telemetry (invocable, ADR 0019 §I3);
- ``duplex_agent`` does **both**, and only that composition makes the proof loop close
  (ADR 0019 §Amendment 1 A1.2).

Add ``import opentelemetry`` to ``turn_agent`` "just to debug" and the second-runtime proof
evaporates with no test turning red. This module is that test: it reads the source, never
imports it, and asserts the negative space.

The negative space has a second half. A manifest is a *promise* about the source, and nothing
made the two meet: ``turn-agent`` declared ``telemetry_capabilities: [turns]`` while importing
no telemetry module at all. ``test_manifest_declares_only_the_telemetry_the_source_emits``
closes that seam.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

HELLO = _EXAMPLES / "hello-agent" / "hello_agent.py"
TURN = _EXAMPLES / "turn-agent" / "turn_agent.py"
DUPLEX = _EXAMPLES / "duplex-agent" / "duplex_agent.py"

#: The manifest entry each source file is the implementation of.
_DECLARED_AS = {HELLO: "hello-agent", TURN: "turn-agent", DUPLEX: "duplex-agent"}

# Modules that would betray each witness's claim if imported.
_SOCKET_MODULES = frozenset({"socket", "socketserver", "http", "http.server", "fastapi", "flask"})
_TELEMETRY_MODULES = frozenset({"opentelemetry", "prometheus_client"})


def _imported_roots(path: Path) -> set[str]:
    """Every module named by an ``import`` / ``from ... import`` in ``path``.

    Returns both the dotted name and its root package, so ``http.server`` matches ``http``.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names | {name.split(".", 1)[0] for name in names}


@pytest.mark.parametrize(
    "path", [HELLO, TURN, DUPLEX], ids=["hello-agent", "turn-agent", "duplex-agent"]
)
def test_example_agent_never_imports_tessera(path: Path) -> None:
    """The second-runtime claim: an agent Tessera did not build, using none of its code."""
    offenders = {name for name in _imported_roots(path) if name.split(".", 1)[0] == "tessera"}
    assert not offenders, f"{path.name} must not import tessera — found {sorted(offenders)}"


def test_hello_agent_opens_no_socket() -> None:
    """hello-agent is publish-only (ADR 0017 §F): it emits, it never serves."""
    offenders = _imported_roots(HELLO) & _SOCKET_MODULES
    assert not offenders, (
        "hello_agent.py must expose no endpoint — its honest-empty console and `binding: none` "
        f"depend on it; found {sorted(offenders)}"
    )


def test_turn_agent_emits_no_telemetry() -> None:
    """turn-agent is invocable-only (ADR 0019 §I3): it serves, it never publishes.

    This keeps the invocation plane provably free of any observability dependency — the
    separation ADR 0019's governing rule rests on.
    """
    offenders = _imported_roots(TURN) & _TELEMETRY_MODULES
    assert not offenders, (
        "turn_agent.py must emit no telemetry — the invocation plane carries no observability "
        f"dependency; found {sorted(offenders)}"
    )


def test_duplex_agent_both_serves_and_publishes() -> None:
    """duplex-agent is the integration witness: it is the ONLY example that does both.

    Its whole claim is the composition. Losing either half would make it a duplicate of one of
    the other two, and the proof loop — invoke it, watch its own telemetry raise its computed
    level — would silently stop being demonstrated by anything.
    """
    roots = _imported_roots(DUPLEX)
    assert roots & _SOCKET_MODULES, "duplex-agent must serve HTTP (it is invocable)"
    assert roots & _TELEMETRY_MODULES, "duplex-agent must emit telemetry (it is observable)"


def test_the_existing_witnesses_stay_minimal() -> None:
    """ADR 0019 §A1.2 (d): duplex-agent's arrival must not enrich hello- or turn-agent.

    Their emptiness is part of the platform's test surface. If the new witness could only be
    built by lending the old ones a capability, the examples directory has started becoming a zoo.
    """
    assert not _imported_roots(HELLO) & _SOCKET_MODULES
    assert not _imported_roots(TURN) & _TELEMETRY_MODULES


@pytest.mark.parametrize(
    "path", [HELLO, TURN, DUPLEX], ids=["hello-agent", "turn-agent", "duplex-agent"]
)
def test_manifest_declares_only_the_telemetry_the_source_emits(path: Path) -> None:
    """An agent never declares a telemetry capability it has no code to honour.

    ``telemetry_capabilities`` is what the fleet reads to decide an agent is *observable* — the
    contract, not the evidence. ``turn-agent`` declared ``[turns]`` and imported no telemetry
    module: the only thing then standing between that manifest and an observable-looking agent
    was the absence of turn evidence, which is a fact about the metrics store, not about the
    agent. The two must agree in **both** directions — a binding-only agent promising activity
    it cannot publish, and an emitting agent whose manifest hides it, are the same defect.

    Both declarations are checked, because both are promises about spans. A ``workflows`` entry
    binds the *grammar* the agent's spans follow; declaring one while emitting nothing is the
    same over-claim one rung down, and it is invisible in the level badge (which already reads
    L0 from either field being empty).
    """
    from tessera.agent.registry import get_agent

    spec = get_agent(_DECLARED_AS[path]).observability
    emits = bool(_imported_roots(path) & _TELEMETRY_MODULES)
    for field, declared in (
        ("telemetry_capabilities", bool(spec and spec.telemetry_capabilities)),
        ("workflows", bool(spec and spec.workflows)),
    ):
        assert declared == emits, (
            f"{_DECLARED_AS[path]}: the manifest {'declares' if declared else 'declares no'} "
            f"{field} while the source {'imports' if emits else 'imports no'} telemetry module "
            "— an agent declares the telemetry it emits, nothing more"
        )


def test_the_negative_space_check_has_teeth() -> None:
    """A guard that cannot fail guards nothing: prove the extractor sees what it forbids."""
    assert _imported_roots(HELLO) & _TELEMETRY_MODULES, "hello-agent should speak OTLP"
    assert _imported_roots(TURN) & _SOCKET_MODULES, "turn-agent should serve HTTP"
