"""ADR 0017 §1 — the cockpit/agent import boundary, enforced as a ratchet.

The control plane (``tessera.observability`` + the cockpit read API) must not import
the agent runtime (``tessera.agent.*``) or ``langgraph``. Two seams are legitimately
allowed — the governed registry (the AgentSpec manifest seam, ADR 0012/0017 §3) and
the agent-id vocabulary (``tessera.agent.identity``).

Every *existing* violation is frozen below as a named exception (slated for ADR 0017
Phase E — the SDK extraction). The assertion is **exact set equality**, so the test
fails both when a NEW forbidden import appears (the boundary would silently erode)
and when an exception disappears (the freeze list must shrink with the fix — ratchet
in both directions). Do not extend ``_FROZEN_EXCEPTIONS`` without amending ADR 0017.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "tessera"

#: Module-name roots the control plane must not import.
_FORBIDDEN_ROOTS = ("langgraph", "tessera.agent")

#: Legitimate seams: the governed manifest registry and the agent-id vocabulary.
_ALLOWED_ROOTS = ("tessera.agent.registry", "tessera.agent.identity")

#: Existing violations, frozen (path relative to ``src/tessera`` → imported modules).
#: Owed to ADR 0017 Phase E (instrumentation moves into the agent SDK).
_FROZEN_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("observability/graph_topology.py", "langgraph.graph"),
        ("observability/graph_topology.py", "tessera.agent.state"),
        ("api/routes/observability.py", "tessera.agent.graph"),
    }
)


def _matches(name: str, roots: tuple[str, ...]) -> bool:
    return any(name == root or name.startswith(root + ".") for root in roots)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
    return modules


def _control_plane_files() -> list[Path]:
    files = sorted((_SRC / "observability").rglob("*.py"))
    files.append(_SRC / "api" / "routes" / "observability.py")
    return files


def test_control_plane_never_imports_the_agent_runtime() -> None:
    violations: set[tuple[str, str]] = set()
    for path in _control_plane_files():
        rel = path.relative_to(_SRC).as_posix()
        for module in _imported_modules(path):
            if _matches(module, _ALLOWED_ROOTS):
                continue
            if _matches(module, _FORBIDDEN_ROOTS):
                violations.add((rel, module))
    new = violations - _FROZEN_EXCEPTIONS
    fixed = _FROZEN_EXCEPTIONS - violations
    assert not new, (
        "New control-plane → agent-runtime imports (ADR 0017 §1 boundary): "
        f"{sorted(new)}. The cockpit reads the spine; it never imports the runtime. "
        "Move the logic behind a spine port, or amend ADR 0017 before extending the freeze."
    )
    assert not fixed, (
        f"Frozen boundary exceptions no longer exist: {sorted(fixed)}. "
        "Shrink _FROZEN_EXCEPTIONS accordingly — the ratchet must tighten."
    )
