"""Boot the Tessera FastAPI app for local development.

Equivalent to ``uv run tessera`` (the console script) but lives at a path the
README quickstart can document plainly.
"""

from __future__ import annotations

import os
from pathlib import Path

from tessera.api.main import cli


def _load_process_env(path: Path) -> None:
    """Load simple KEY=VALUE entries so direct ``os.environ`` readers see dev flags."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    _load_process_env(Path(".env"))
    _load_process_env(Path(".env.local"))
    _load_process_env(Path("agent.secret.env"))
    cli()


if __name__ == "__main__":
    main()
