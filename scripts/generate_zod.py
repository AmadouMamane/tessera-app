"""OpenAPI -> zod codegen. The front stops re-deriving the backend's contract by hand.

Audit 2026-07-10, **P1.4 `untyped-api`** and **P2 `validation-gap`**. Today the backend declares
no response contract (10 ``response_model`` on ~174 routes) and the front re-implements it in
5 700 lines of hand-written zod. Two independent statements of one truth: they can only drift,
and they have — see ``docs/status/backend-typing-run.md``.

This emits the front's schemas **from the backend's own OpenAPI**, so there is one source of
truth and the drift becomes impossible rather than merely unlikely. It is deliberately small and
readable rather than a dependency: the shapes Tessera emits are objects, arrays, scalars and
``anyOf`` unions, and a 150-line generator that we can read beats a package we cannot.

Run against a domain (the routes already carrying ``response_model``)::

    uv run python scripts/generate_zod.py --domain fleet \\
        --out webapp/frontend/lib/api/generated/fleet.ts

The output is checked in, and a test asserts it is up to date — a generator whose output is not
pinned is a generator nobody re-runs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

_SCALARS = {
    "string": "z.string()",
    "integer": "z.number().int()",
    "number": "z.number()",
    "boolean": "z.boolean()",
}


_IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _key(name: str) -> str:
    """Quote an object key only when it is not a bare JS identifier.

    The gate runs `biome check`, and biome's formatter strips redundant quotes. A generator whose
    output the formatter immediately rewrites is a generator that can never be pinned: the
    up-to-date ratchet and the formatter would fight on every run. So emit what biome would.
    """
    return name if _IDENTIFIER.fullmatch(name) else json.dumps(name)


def zod_for(schema: dict[str, Any], comps: dict[str, Any], seen: set[str]) -> str:  # noqa: PLR0911
    """One OpenAPI schema node -> one zod expression.

    Ten returns, one per OpenAPI shape. Collapsing them into a dispatch table would hide the
    one thing a reader needs: the exhaustive list of what this generator does and does NOT
    understand. The final `z.unknown()` is the honest fallback — it says "the backend did not
    declare this", which is true and checkable, rather than inventing a shape.
    """
    if "$ref" in schema:
        return f"{ref_name(schema['$ref'])}Schema"

    if "anyOf" in schema or "oneOf" in schema:
        members = schema.get("anyOf") or schema["oneOf"]
        # `T | null` is zod's `.nullable()`, not a union with a null member.
        non_null = [m for m in members if m.get("type") != "null"]
        nullable = len(non_null) < len(members)
        if len(non_null) == 1:
            inner = zod_for(non_null[0], comps, seen)
            return f"{inner}.nullable()" if nullable else inner
        union = ", ".join(zod_for(m, comps, seen) for m in non_null)
        expr = f"z.union([{union}])"
        return f"{expr}.nullable()" if nullable else expr

    if schema.get("const") is not None or "const" in schema:
        return f"z.literal({json.dumps(schema['const'])})"

    kind = schema.get("type")
    if kind == "array":
        return f"z.array({zod_for(schema.get('items', {}), comps, seen)})"
    if kind == "object":
        props = schema.get("properties")
        if not props:
            return "z.record(z.unknown())"
        required = set(schema.get("required", []))
        fields = []
        for name, sub in props.items():
            expr = zod_for(sub, comps, seen)
            if name not in required:
                expr += ".optional()"
            fields.append(f"  {_key(name)}: {expr},")
        return "z.object({\n" + "\n".join(fields) + "\n})"
    if kind == "null":
        return "z.null()"
    if kind in _SCALARS:
        return _SCALARS[kind]
    # No type at all: the backend said `object`. Say so, honestly, rather than inventing a shape.
    return "z.unknown()"


def emit(spec: dict[str, Any], routes: list[str]) -> str:
    comps: dict[str, Any] = spec.get("components", {}).get("schemas", {})

    # Which component schemas does this domain actually reach? Emit those and nothing else.
    wanted: set[str] = set()

    def reach(node: Any) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                name = ref_name(node["$ref"])
                if name not in wanted:
                    wanted.add(name)
                    reach(comps.get(name, {}))
            for v in node.values():
                reach(v)
        elif isinstance(node, list):
            for v in node:
                reach(v)

    roots: dict[str, dict[str, Any]] = {}
    for path in routes:
        op = spec["paths"][path]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        roots[path] = schema
        reach(schema)

    # Emit dependencies before dependents (zod is evaluated eagerly, so order is load-bearing).
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in ordered or name in visiting:
            return
        visiting.add(name)
        deps: list[str] = []

        def collect(node: Any) -> None:
            if isinstance(node, dict):
                if "$ref" in node:
                    deps.append(ref_name(node["$ref"]))
                for v in node.values():
                    collect(v)
            elif isinstance(node, list):
                for v in node:
                    collect(v)

        collect(comps.get(name, {}))
        for d in deps:
            visit(d)
        visiting.discard(name)
        ordered.append(name)

    for name in sorted(wanted):
        visit(name)

    out: list[str] = [
        "// GENERATED by scripts/generate_zod.py from the backend's OpenAPI. DO NOT EDIT.",
        "//",
        "// The backend's `response_model` is the single source of truth for these shapes. Before",
        "// this file, the front re-derived them by hand — and the two statements drifted: the",
        "// hand-written AccessOverviewSchema REJECTED the backend's own `{available:false}`",
        "// degrade, so the page broke on the exact response that exists to keep it alive.",
        "//",
        "// Re-generate:  uv run python scripts/generate_zod.py --domain fleet \\",
        "//                 --out webapp/frontend/lib/api/generated/fleet.ts",
        'import { z } from "zod";',
        "",
    ]
    for name in ordered:
        out.append(f"export const {name}Schema = {zod_for(comps[name], comps, set())};")
        out.append("")
    for path, schema in roots.items():
        const = re.sub(r"\W", "", "".join(p.title() for p in path.rsplit("/", 1)[-1].split("-")))
        out.append(f"/** GET {path} */")
        out.append(f"export const {const}ResponseSchema = {zod_for(schema, comps, set())};")
        out.append(f"export type {const}Response = z.infer<typeof {const}ResponseSchema>;")
        out.append("")
    return "\n".join(out)


def _is_typed(spec: dict[str, Any], path: str) -> bool:
    """True when the route's 200 response actually names a model (a `$ref`), not `dict`."""
    op = spec["paths"].get(path, {}).get("get")
    if not op:
        return False
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    return "$ref" in json.dumps(schema)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True, help="the route domain to emit (e.g. fleet)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    from fastapi import FastAPI

    from tessera.api.routes.observability import fleet as fleet_routes, router

    app = FastAPI()
    app.include_router(router)
    spec = app.openapi()

    domains = {
        "fleet": [route.path for route in fleet_routes.router.routes],  # type: ignore[attr-defined]
    }
    # A route counts as TYPED only if its 200 schema names a model. Every route has a
    # `response_model` in FastAPI's eyes — the untyped ones just inherit `dict[str, object]`,
    # which becomes `z.record(z.unknown())`: a schema that validates nothing while looking like
    # it does. Emitting those would hand the front a rubber stamp, which is worse than no schema
    # at all, because `request()` would report the response as validated.
    routes = sorted(p for p in domains[args.domain] if _is_typed(spec, p))
    skipped = sorted(p for p in domains[args.domain] if not _is_typed(spec, p))
    if not routes:
        msg = f"domain {args.domain!r} has no typed route yet — add response_model= first"
        raise SystemExit(msg)
    if skipped:
        print(f"skipped {len(skipped)} route(s) with no declared model (would emit z.unknown):")
        for p in skipped:
            print(f"  - {p}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(emit(spec, routes), encoding="utf-8")
    _biome_format(args.out)
    print(f"{args.out}: {len(routes)} route(s), {len(args.out.read_text().splitlines())} lines")


def _biome_format(target: Path) -> None:
    """Let biome canonicalise the output — the gate runs `biome check`, so it has the last word.

    Without this the generator and the formatter disagree on whitespace, the checked-in file is
    formatted by whoever touched it last, and the up-to-date ratchet fails for a reason that has
    nothing to do with the contract. Emit exactly what the gate expects.
    """
    frontend = Path(__file__).resolve().parents[1] / "webapp" / "frontend"
    subprocess.run(
        ["corepack", "pnpm", "exec", "biome", "format", "--write", str(target.resolve())],
        cwd=frontend,
        check=True,
        capture_output=True,
    )


if __name__ == "__main__":
    main()
