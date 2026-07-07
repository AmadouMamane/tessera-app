"""AgentSpec conformance — the manifest is bound to the real subsystems (ADR 0017 §3/§4).

Two cross-checks that keep the manifest honest as it is generated-from, not decorative:

1. every ``source: business_score`` signal a manifest declares is actually PRODUCED by the
   scorer the manifest binds — so a declared KPI can never be a signal that no code emits;
2. every manifest-declared ``label_key`` (capabilities + policies) EXISTS in every locale
   catalogue — the "i18n-missing-sweep becomes a gate on manifest-declared labels" rule
   (§3), enforced statically in the Python CI gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tessera.agent.registry import BusinessSignalSource, list_agents
from tessera.recouvrement.scoring import RecouvrementBusinessScorer

if TYPE_CHECKING:
    from collections.abc import Mapping

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MESSAGES_DIR = _REPO_ROOT / "webapp" / "frontend" / "messages"
_LOCALES = ("fr", "en", "de")

# Scorers keyed by the id an AgentSpec workflow binds — the manifest declares the id, this
# map proves it resolves to a real scorer whose produced keys back the declared signals.
_SCORERS_BY_ID = {RecouvrementBusinessScorer.scorer_id: RecouvrementBusinessScorer()}

# A minimal event set that makes each scorer's ``supports`` true, so ``score`` returns its
# full metric key set (each metric fn returns a row unconditionally, ADR 0017 §A2.2).
_PROBE_ROWS = [
    {
        "agent_id": "recouvrement",
        "workflow_id": "recouvrement_collections_v1",
        "event_name": "case.context_loaded",
    }
]


def _manifested_agents() -> list[object]:
    return [a for a in list_agents() if a.observability is not None]


def test_at_least_recouvrement_is_manifested() -> None:
    ids = {a.id for a in _manifested_agents()}  # type: ignore[attr-defined]
    assert "recouvrement" in ids


def test_declared_business_scores_are_produced_by_the_bound_scorer() -> None:
    for agent in _manifested_agents():
        spec = agent.observability  # type: ignore[attr-defined]
        scorer_ids = {w.scorer for w in spec.workflows if w.scorer}
        produced: set[str] = set()
        for scorer_id in scorer_ids:
            assert scorer_id in _SCORERS_BY_ID, (
                f"agent {agent.id!r} binds unknown scorer {scorer_id!r}"  # type: ignore[attr-defined]
            )
            scorer = _SCORERS_BY_ID[scorer_id]
            produced |= {s.metric for s in scorer.score(_PROBE_ROWS)}
        declared = {
            s.key for s in spec.business_signals if s.source is BusinessSignalSource.BUSINESS_SCORE
        }
        missing = declared - produced
        assert not missing, (
            f"agent {agent.id!r} declares business_score signals its scorer never produces: "
            f"{sorted(missing)}"
        )


def _resolve(catalogue: Mapping[str, object], dotted_key: str) -> object | None:
    node: object = catalogue
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


@pytest.mark.parametrize("locale", _LOCALES)
def test_manifest_label_keys_exist_in_every_locale(locale: str) -> None:
    catalogue = json.loads((_MESSAGES_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    missing: list[str] = []
    for agent in _manifested_agents():
        spec = agent.observability  # type: ignore[attr-defined]
        label_keys = [c.label_key for c in spec.capabilities] + [p.label_key for p in spec.policies]
        for key in label_keys:
            resolved = _resolve(catalogue, key)
            if not isinstance(resolved, str) or not resolved:
                missing.append(f"{agent.id}:{key}")  # type: ignore[attr-defined]
    assert not missing, f"manifest label_keys missing in {locale}.json: {missing}"
