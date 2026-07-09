"""Capability input schemas — the declaration a generated console form is rendered from.

ADR 0017 §A1.1 gave `Capability` an ``input_schema``: a path to a JSON Schema describing the
parameters the capability takes. Nothing read it. ADR 0019 §Amendment 1 A1.2 (c) makes it
load-bearing: the Console renders it as a **generated form**, so an agent gains a typed test
bench by *declaring*, never by anyone writing a form for it.

Two boundaries this module exists to hold:

* **The cockpit never reads an agent's repository.** Schemas resolve under this package's
  ``schemas/`` directory, next to the manifest that names them — an out-of-process agent is a
  foreign runtime, and the platform reads its *declaration*, not its source tree. (An external
  agent re-implements the same schema on its own side, exactly as ``examples/turn-agent`` hard-codes
  the wire keys rather than importing them.)
* **A form is generated, never guessed.** Only the JSON Schema subset the renderer actually
  supports is accepted, and a schema outside it is a load error rather than a half-rendered form.
  A declaration the cockpit cannot honour must fail loudly at the seam, not quietly in a browser.

Parameter validation lives here too, so the governed invocation seam refuses malformed params
before they reach the wire — the platform does not forward garbage it declared the shape of.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

__all__ = [
    "SUPPORTED_TYPES",
    "CapabilitySchemaError",
    "load_input_schema",
    "validate_params",
]

_SCHEMAS_DIR: Final = Path(__file__).resolve().parent / "schemas"

#: The JSON Schema primitive types the generated form knows how to render. Anything else is a
#: load error: a renderer that silently drops a field would let an operator submit a turn that
#: does not say what they think it says.
SUPPORTED_TYPES: Final[frozenset[str]] = frozenset({"string", "integer", "number", "boolean"})


class CapabilitySchemaError(ValueError):
    """A declared ``input_schema`` is missing, unreadable, or outside the renderable subset."""


def load_input_schema(relative_path: str) -> dict[str, object]:
    """Load and check the JSON Schema a capability declares in ``input_schema``.

    Args:
        relative_path: The manifest's ``input_schema`` value, e.g.
            ``schemas/propose_schedule.json``, resolved under this package (never against the
            process working directory, and never against an agent's own repository).

    Returns:
        The parsed schema.

    Raises:
        CapabilitySchemaError: The path escapes the schemas directory, the file is absent or not
            JSON, or the schema is outside the renderable subset (``type: object`` with a
            ``properties`` mapping whose every property declares a supported ``type``).
    """
    name = relative_path.removeprefix("schemas/")
    path = (_SCHEMAS_DIR / name).resolve()
    if not path.is_relative_to(_SCHEMAS_DIR) or "/" in name:
        msg = f"input_schema {relative_path!r} must name a file directly under schemas/"
        raise CapabilitySchemaError(msg)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        msg = f"input_schema {relative_path!r} declared but absent at {path}"
        raise CapabilitySchemaError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"input_schema {relative_path!r} is not valid JSON: {exc}"
        raise CapabilitySchemaError(msg) from exc
    return _check_renderable(relative_path, parsed)


def _check_renderable(relative_path: str, schema: object) -> dict[str, object]:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        msg = f"input_schema {relative_path!r} must be a JSON Schema of type 'object'"
        raise CapabilitySchemaError(msg)
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        msg = f"input_schema {relative_path!r} declares no properties — nothing to render"
        raise CapabilitySchemaError(msg)
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            msg = f"input_schema {relative_path!r}: property {name!r} is not an object"
            raise CapabilitySchemaError(msg)
        declared = prop.get("type")
        if declared not in SUPPORTED_TYPES:
            msg = (
                f"input_schema {relative_path!r}: property {name!r} declares type {declared!r}, "
                f"which the generated form cannot render (supported: {sorted(SUPPORTED_TYPES)})"
            )
            raise CapabilitySchemaError(msg)
    required = schema.get("required", [])
    if not isinstance(required, list) or any(key not in properties for key in required):
        msg = f"input_schema {relative_path!r}: 'required' names a property that does not exist"
        raise CapabilitySchemaError(msg)
    return schema


def validate_params(schema: dict[str, object], params: dict[str, object]) -> list[str]:
    """Return the violations of ``params`` against ``schema`` (empty ⇒ valid).

    Deliberately narrow: presence, unknown keys, and primitive type. The platform declared the
    shape, so it refuses to forward a turn that does not match it — but it does not grow a second
    JSON Schema implementation. Anything richer belongs in the agent, which owns its own contract.
    """
    properties = schema.get("properties")
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):  # pragma: no cover
        return ["schema is not renderable"]  # load_input_schema already refuses these

    violations = [f"unknown parameter {key!r}" for key in sorted(set(params) - set(properties))]
    violations += [f"missing required parameter {key!r}" for key in required if key not in params]
    for key, value in sorted(params.items()):
        prop = properties.get(key)
        if not isinstance(prop, dict):
            continue
        declared = prop.get("type")
        if not _matches(declared, value):
            violations.append(f"parameter {key!r} expects {declared}, got {type(value).__name__}")
    return violations


def _matches(declared: object, value: object) -> bool:
    if declared == "string":
        return isinstance(value, str)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "integer":
        # `bool` is an `int` in Python; a checkbox is not a count.
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    return False
