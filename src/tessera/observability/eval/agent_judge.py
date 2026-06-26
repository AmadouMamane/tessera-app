"""Per-agent judge metrics, replayed offline over each agent's run (Phase 4b).

``scripts/backfill_agent_judge.py`` replays the real local judge over each
agent's stored answers (``final_response`` in its per-agent report under
``eval/reports/``) and writes the per-agent means to
``eval/reports/_agent_judge.json``. This module loads that cache so the API can
attach real Faithfulness / Grounding / Hallucination scores to the per-agent
Evaluations page — scores that genuinely differ per agent because each is judged
on its OWN run over its OWN curated set.

Absent cache (backfill not run yet) yields an empty mapping, and the dashboard
reports ``null`` for those columns — never a fabricated score.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tessera.observability.eval.report_paths import resolve_report_file

__all__ = [
    "AgentJudge",
    "AgentJudgeReport",
    "default_cache_path",
    "load_agent_judge",
]


@dataclass(frozen=True, slots=True)
class AgentJudge:
    """Mean judge scores for one agent (each in [0, 1], higher is better)."""

    agent_id: str
    faithfulness: float | None
    grounding: float | None
    hallucination: float | None
    n: int


@dataclass(frozen=True, slots=True)
class AgentJudgeReport:
    """The per-agent judge cache plus provenance."""

    judge_model: str | None
    context_basis: str | None
    agents: dict[str, AgentJudge]

    def for_agent(self, agent_id: str) -> AgentJudge | None:
        """Return the judged scores for one agent, or None when absent."""
        return self.agents.get(agent_id)


def default_cache_path() -> Path:
    """Repo path of the per-agent judge cache."""
    return Path(__file__).resolve().parents[4] / "eval" / "reports" / "_agent_judge.json"


def _opt_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def load_agent_judge(path: Path | None = None) -> AgentJudgeReport:
    """Load the per-agent judge cache, or an empty report when it is absent."""
    cache = path or resolve_report_file("_agent_judge.json")
    if not cache.exists():
        return AgentJudgeReport(judge_model=None, context_basis=None, agents={})
    try:
        obj = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AgentJudgeReport(judge_model=None, context_basis=None, agents={})
    if not isinstance(obj, dict):
        return AgentJudgeReport(judge_model=None, context_basis=None, agents={})
    raw_agents = obj.get("agents")
    agents: dict[str, AgentJudge] = {}
    if isinstance(raw_agents, dict):
        for agent_id, entry in raw_agents.items():
            if not isinstance(entry, dict):
                continue
            n_val = entry.get("n")
            agents[str(agent_id)] = AgentJudge(
                agent_id=str(agent_id),
                faithfulness=_opt_float(entry.get("faithfulness")),
                grounding=_opt_float(entry.get("grounding")),
                hallucination=_opt_float(entry.get("hallucination")),
                n=int(n_val) if isinstance(n_val, int) else 0,
            )
    return AgentJudgeReport(
        judge_model=str(obj.get("judge_model")) if obj.get("judge_model") else None,
        context_basis=str(obj.get("context_basis")) if obj.get("context_basis") else None,
        agents=agents,
    )
