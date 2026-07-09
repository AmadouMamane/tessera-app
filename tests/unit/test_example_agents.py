"""The examples' *absence* of imports is their assertion — so the gate checks it.

``examples/hello-agent`` and ``examples/turn-agent`` are the platform witnesses (see
``examples/README.md``). Each proves exactly one claim, and each proof rests on what the file
does **not** import:

- neither imports ``tessera`` — they demonstrate properties of agents the platform did not build;
- ``hello_agent`` speaks OTLP and opens no socket (publish-only, ADR 0017 §F);
- ``turn_agent`` serves HTTP and emits no telemetry (invocable, ADR 0019 §I3).

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


@pytest.mark.parametrize("path", [HELLO, TURN], ids=["hello-agent", "turn-agent"])
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


def test_the_negative_space_check_has_teeth() -> None:
    """A guard that cannot fail guards nothing: prove the extractor sees what it forbids."""
    assert _imported_roots(HELLO) & _TELEMETRY_MODULES, "hello-agent should speak OTLP"
    assert _imported_roots(TURN) & _SOCKET_MODULES, "turn-agent should serve HTTP"
