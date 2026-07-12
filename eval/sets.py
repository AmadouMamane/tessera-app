"""Per-agent evaluation sets — curated subsets of the failure catalogue.

Each agent package BINDS an evaluation set by slug (`Agent.eval_set`); the slug
resolves to a manifest under ``eval/sets/<slug>.json`` listing the catalogue case
ids the agent is judged on, plus a release ``gate``. This is the curated, opposable
artifact behind "evaluated as a whole": an agent cannot go live until a run of ITS
set clears the gate.

The gate carries **no number** (ADR 0021). It used to declare a ``min_pass_rate``, and
the three of them (55% / 65% / 55%) all sat *below* the catalogue's measured null floor
— an agent with no model at all cleared every one. What a set's ``gate`` holds now is
the *rationale*: the release bar itself is the same for every set, and it is measured
rather than chosen — the critical floor (zero tolerance, :mod:`eval.gate`) plus the
model's contribution over the set's OWN null floor (:mod:`eval.contribution`).

The loader is strict on purpose — every listed case id must exist under
``eval/failures/`` — so a typo in a manifest fails loudly in CI rather than
silently shrinking an agent's set.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import jsonschema

__all__ = [
    "SECURITY_FLOOR_SLUG",
    "EvalGate",
    "catalogue_categories",
    "EvalSet",
    "critical_case_ids",
    "list_eval_sets",
    "load_eval_set",
    "load_security_floor",
    "resolve_case_ids",
]

_SETS_DIR = Path(__file__).parent / "sets"
_SETS_SCHEMA_PATH = _SETS_DIR / "_schema.json"
_FAILURES_DIR = Path(__file__).parent / "failures"

#: The shared security floor: existential, universal critical cases injected into
#: every agent-bound set. Its own cases are all ``severity: critical``.
SECURITY_FLOOR_SLUG = "socle-securite"


@dataclass(frozen=True, slots=True)
class EvalGate:
    """Why an evaluation set's release bar is what it is.

    It holds no threshold: the bar is not per-set and not chosen (ADR 0021). It is the
    critical floor, plus contribution over the set's own measured null floor.
    """

    rationale: str = ""


@dataclass(frozen=True, slots=True)
class EvalSet:
    """A curated evaluation set bound to an agent package.

    ``case_ids`` is the domain set as declared in the manifest; ``effective_case_ids``
    is what the agent is actually judged on — the shared security floor injected
    ahead of the domain cases (for agent-bound sets only).
    """

    slug: str
    name: str
    case_ids: tuple[str, ...]
    gate: EvalGate
    agent_id: str = ""
    description: str = ""

    @property
    def effective_case_ids(self) -> tuple[str, ...]:
        """Domain cases with the security floor injected (agent-bound sets only)."""
        if not self.agent_id or self.slug == SECURITY_FLOOR_SLUG:
            return self.case_ids
        floor = load_security_floor().case_ids
        return tuple(dict.fromkeys((*floor, *self.case_ids)))


def _catalogue_ids() -> frozenset[str]:
    """File stems of every failure case under ``eval/failures/``."""
    return frozenset(path.stem for path in _FAILURES_DIR.glob("[0-9][0-9]*_*.json"))


@lru_cache(maxsize=1)
def catalogue_categories() -> dict[str, str]:
    """``{case_id: category}`` for the whole catalogue.

    Used by the contribution gate to report which categories the null control already
    passes in full — those can earn a model no credit (ADR: eval-gate rule 3).
    """
    return {
        path.stem: str(json.loads(path.read_text(encoding="utf-8")).get("category", ""))
        for path in _FAILURES_DIR.glob("[0-9][0-9]*_*.json")
    }


@lru_cache(maxsize=1)
def critical_case_ids() -> frozenset[str]:
    """Ids of catalogue cases flagged ``severity: critical`` (zero-tolerance)."""
    critical: set[str] = set()
    for path in _FAILURES_DIR.glob("[0-9][0-9]*_*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("severity") == "critical":
            critical.add(path.stem)
    return frozenset(critical)


def _set_schema() -> dict[str, object]:
    schema = json.loads(_SETS_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        msg = "eval set schema is not a JSON object"
        raise TypeError(msg)
    return schema


def _coerce_set(payload: dict[str, object], stem: str, schema: dict[str, object]) -> EvalSet:
    jsonschema.validate(payload, schema)
    slug = str(payload["slug"])
    if slug != stem:
        msg = f"eval set slug {slug!r} does not match file stem {stem!r}"
        raise ValueError(msg)
    raw_ids = payload["case_ids"]
    if not isinstance(raw_ids, list):
        msg = f"eval set {slug!r} has a malformed case_ids"
        raise TypeError(msg)
    case_ids = tuple(str(c) for c in raw_ids)
    known = _catalogue_ids()
    unknown = [cid for cid in case_ids if cid not in known]
    if unknown:
        msg = f"eval set {slug!r} references unknown case ids: {unknown}"
        raise ValueError(msg)
    gate_raw = payload["gate"]
    if not isinstance(gate_raw, dict):
        msg = f"eval set {slug!r} has a malformed gate"
        raise TypeError(msg)
    gate = EvalGate(rationale=str(gate_raw.get("rationale", "")))
    return EvalSet(
        slug=slug,
        name=str(payload["name"]),
        case_ids=case_ids,
        gate=gate,
        agent_id=str(payload.get("agent_id", "")),
        description=str(payload.get("description", "")),
    )


@lru_cache(maxsize=1)
def _load() -> dict[str, EvalSet]:
    """Parse every manifest under ``eval/sets/`` once into {slug: EvalSet}."""
    schema = _set_schema()
    sets: dict[str, EvalSet] = {}
    for path in sorted(_SETS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        eval_set = _coerce_set(payload, path.stem, schema)
        sets[eval_set.slug] = eval_set
    if not sets:
        msg = f"no evaluation sets found under {_SETS_DIR}"
        raise ValueError(msg)
    return sets


def list_eval_sets() -> list[EvalSet]:
    """Return all evaluation sets, ordered by slug."""
    return [_load()[slug] for slug in sorted(_load())]


def load_eval_set(slug: str) -> EvalSet:
    """Return one evaluation set by slug, or raise ``KeyError`` if unknown."""
    sets = _load()
    if slug not in sets:
        raise KeyError(slug)
    return sets[slug]


def load_security_floor() -> EvalSet:
    """Return the shared security floor set (universal critical cases)."""
    return load_eval_set(SECURITY_FLOOR_SLUG)


def resolve_case_ids(slug: str) -> tuple[str, ...]:
    """Return the case ids an agent is judged on (domain + injected security floor)."""
    return load_eval_set(slug).effective_case_ids
