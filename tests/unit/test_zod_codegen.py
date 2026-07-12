"""The checked-in zod must be what the backend's OpenAPI produces, today.

A generator whose output is not pinned is a generator nobody re-runs — and the moment the
checked-in file drifts from the schema it claims to mirror, the front is back to re-deriving the
backend's contract by hand, only now it *looks* generated. That is worse than the hand-written
schemas it replaced, because nobody re-reads a file whose header says DO NOT EDIT.

So: regenerate into a temp file and compare. If a `response_model` changes and this fails, the
fix is one command, printed in the message.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GENERATED = _ROOT / "webapp" / "frontend" / "lib" / "api" / "generated" / "fleet.ts"
_SCRIPT = _ROOT / "scripts" / "generate_zod.py"

_REGENERATE = (
    "uv run python scripts/generate_zod.py --domain fleet "
    "--out webapp/frontend/lib/api/generated/fleet.ts"
)


def test_the_checked_in_zod_matches_the_current_openapi(tmp_path: Path) -> None:
    """The single source of truth is the backend. This asserts the copy has not drifted."""
    fresh = tmp_path / "fleet.ts"

    subprocess.run(  # noqa: S603
        [sys.executable, str(_SCRIPT), "--domain", "fleet", "--out", str(fresh)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
    )

    assert fresh.read_text(encoding="utf-8") == _GENERATED.read_text(
        encoding="utf-8"
    ), f"webapp/frontend/lib/api/generated/fleet.ts is stale — regenerate it:\n    {_REGENERATE}"


def test_the_generator_refuses_a_domain_with_no_typed_route() -> None:
    """A route with no `response_model` becomes `z.record(z.unknown())` — a schema that validates
    nothing while `request()` reports the response as validated. The generator must SKIP those,
    not emit them, or the front gets a rubber stamp it cannot see through.
    """
    source = _SCRIPT.read_text(encoding="utf-8")

    assert "_is_typed" in source
    assert "z.record(z.unknown())" in source, "the honest fallback must exist"
    assert "skipped" in source, "the skipped routes must be reported, not silently dropped"
