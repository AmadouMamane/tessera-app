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
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

HELLO = _EXAMPLES / "hello-agent" / "hello_agent.py"
TURN = _EXAMPLES / "turn-agent" / "turn_agent.py"
DUPLEX = _EXAMPLES / "duplex-agent" / "duplex_agent.py"

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


def test_the_negative_space_check_has_teeth() -> None:
    """A guard that cannot fail guards nothing: prove the extractor sees what it forbids."""
    assert _imported_roots(HELLO) & _TELEMETRY_MODULES, "hello-agent should speak OTLP"
    assert _imported_roots(TURN) & _SOCKET_MODULES, "turn-agent should serve HTTP"
