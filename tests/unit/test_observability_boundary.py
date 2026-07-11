"""ADR 0017 §1 — the cockpit/agent import boundary, enforced as a ratchet.

The control plane (``tessera.observability`` + the cockpit read API) must not import
the agent runtime (``tessera.agent.*``) or ``langgraph``. Two seams are legitimately
allowed — the governed registry (the AgentSpec manifest seam, ADR 0012/0017 §3) and
the agent-id vocabulary (``tessera.agent.identity``).

The freeze list is **now empty**: ADR 0017 Phase E (step 6a) retired all five
original exceptions — ``instrument.py`` + ``graph_topology.py`` moved into
``tessera.agent.sdk`` (off the scanned tree) and the three route imports
(reporter/router/graph) moved behind the ``observability.spine.runtime`` port.
The assertion is **exact set equality**, so the test fails both when a NEW
forbidden import appears (the boundary would silently erode) and when a frozen
exception no longer exists (the freeze list must shrink with the fix — ratchet in
both directions). Do not add to ``_FROZEN_EXCEPTIONS`` without amending ADR 0017:
the control plane must never import the agent runtime again.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "tessera"

#: Module-name roots the control plane must not import.
_FORBIDDEN_ROOTS = ("langgraph", "tessera.agent")

#: Legitimate seams: the governed manifest registry and the agent-id vocabulary.
_ALLOWED_ROOTS = ("tessera.agent.registry", "tessera.agent.identity")

#: Frozen violations (path relative to ``src/tessera`` → imported modules).
#: **Empty** since ADR 0017 Phase E (step 6a): the control plane imports no part
#: of the agent runtime. A non-empty set here again means the boundary regressed.
_FROZEN_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset()


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
    # The route layer was a single observability.py until the god-router split (audit
    # 2026-07-10). Globbed, not named: the ratchet must cover EVERY module of the package,
    # or a forbidden import could re-enter the control plane through a new surface file and
    # the boundary would still read green.
    files.extend(sorted((_SRC / "api" / "routes" / "observability").rglob("*.py")))
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
