"""Seed governed eval-gate waivers from the agent's real evaluation run.

Reads the agent's latest report, classifies each ``(case_id, language)`` failure
by tier, and seeds realistic governed waivers (S1, hash-chained) bound to that
run as the *candidate version*. Idempotent — safe to re-run.

Usage: ``PYTHONPATH=src uv run python scripts/seed_eval_waivers.py [agent_id]``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tessera.observability.eval_data import load_agent_or_global_snapshot
from tessera.observability.eval_tiers import tier_for
from tessera.observability.eval_waivers import (
    effective_waivers,
    seed_demo_waivers,
    verify_waiver_chain,
)


def main(argv: list[str]) -> int:
    """Seed waivers for ``agent_id`` (default: support-client)."""
    agent_id = argv[0] if argv else "support-client"
    snap = load_agent_or_global_snapshot(agent_id)
    candidate = snap.run_at
    failing_t1: list[tuple[str, str]] = []
    failing_t0: list[tuple[str, str]] = []
    for session in snap.sessions:
        if session.passed:
            continue
        tier = tier_for(session.case_id)
        if tier == "T1":
            failing_t1.append((session.case_id, session.language))
        elif tier == "T0":
            failing_t0.append((session.case_id, session.language))

    written = seed_demo_waivers(
        candidate_version=candidate,
        agent_id=snap.agent_id or agent_id,
        failing_t1=failing_t1,
        failing_t0=failing_t0,
    )
    sys.stdout.write(f"candidate={candidate} wrote {written} waiver event(s)\n")
    sys.stdout.write(f"chain verified: {verify_waiver_chain()}\n")
    for ew in effective_waivers(candidate):
        sys.stdout.write(
            f"  {ew.event.event_id} {ew.tier} {ew.event.case_id}/{ew.event.language} "
            f"-> {ew.status} (active={ew.active})\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
