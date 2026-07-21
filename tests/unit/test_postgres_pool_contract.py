"""Static ratchets for process-wide PostgreSQL pool isolation."""

from __future__ import annotations

import ast
from pathlib import Path


def test_application_never_mutates_a_connection_row_factory() -> None:
    """A cursor may choose its row shape; a pooled connection never may.

    A connection-level assignment survives checkout and leaks ``dict_row`` or
    ``tuple_row`` into an unrelated reader.  This AST ratchet catches the
    dangerous operation independently of variable naming and code formatting.
    """
    source_root = Path("src/tessera")
    offenders: list[str] = []
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(target, ast.Attribute) and target.attr == "row_factory"
                for target in targets
            ):
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], (
        "row_factory must be set on conn.cursor(row_factory=...), never on a "
        f"pooled connection: {offenders}"
    )
