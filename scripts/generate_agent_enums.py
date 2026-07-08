"""Generate the per-agent intent enums from the AgentSpec capabilities (ADR 0018 §C).

Writes the committed backend ``Literal`` module and frontend union for each agent
that declares capabilities. Run after changing an agent's ``capabilities`` block;
``tests/unit/test_agent_enum_codegen.py`` fails until the committed files match.

    uv run python scripts/generate_agent_enums.py
"""

from __future__ import annotations

from pathlib import Path

from tessera.agent.codegen import (
    backend_path,
    capability_ids,
    frontend_path,
    render_backend_enums,
    render_frontend_enums,
)

# Agents whose per-agent intent enums are generated (those that declare capabilities).
_AGENTS = ("recouvrement",)

_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for agent_id in _AGENTS:
        if not capability_ids(agent_id):
            print(f"skip {agent_id}: no declared capabilities")
            continue
        for rel, render in (
            (backend_path(agent_id), render_backend_enums),
            (frontend_path(agent_id), render_frontend_enums),
        ):
            path = _ROOT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(agent_id), encoding="utf-8")
            print(f"wrote {rel}")


if __name__ == "__main__":
    main()
