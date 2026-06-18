"""Bootstrap the Evaluations demo data on a fresh environment.

``eval/reports`` and the governed waiver store are **runtime artifacts** (the
reports are gitignored; the waiver journal lives in the guard audit directory),
so a freshly deployed environment serves an *empty* Evaluations page. This script
makes it populated and reproducible in one idempotent step:

1. run the agent's **FR/DE/EN** evaluation (the candidate run);
2. seed the **governed waivers** bound to that run (idempotent).

It is wired into ``make bootstrap`` for local setup and is the documented post-
deploy step for the demo (see ``docs/runbook.md``). The eval-gate verdict is
*expected* to BLOCK for the demo (the small model fails the socle), so a non-zero
gate exit is not treated as an error here.

Usage: ``PYTHONPATH=src uv run python scripts/bootstrap_eval_demo.py [agent_id]``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import seed_eval_waivers  # sibling script (scripts/ is on sys.path)
from eval.runner import main as run_eval_main


def main(argv: list[str]) -> int:
    """Run the agent eval then seed its governed waivers (default: support-client)."""
    agent = argv[0] if argv else "support-client"
    sys.stdout.write(f"[bootstrap] running FR/DE/EN evaluation for {agent!r}...\n")
    # The exit code is the eval-gate verdict; a BLOCK (non-zero) is the expected
    # demo outcome, so we deliberately do not abort on it.
    gate_code = run_eval_main(["--agent", agent])
    sys.stdout.write(f"[bootstrap] eval done (gate exit={gate_code}); seeding waivers...\n")
    seed_eval_waivers.main([agent])
    sys.stdout.write("[bootstrap] Evaluations demo data ready.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
