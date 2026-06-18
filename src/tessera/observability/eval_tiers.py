"""Three-tier classification of failure-catalogue cases (eval-gate policy §2).

The binding policy (``docs/design/eval-gate-policy.md``) grades every critical
failure into one of three tiers:

* **Tier 0 — cœur non-dérogeable**: the curated security floor
  (``eval/sets/socle-securite.json``). PII réelle exfiltrée, hard-stop
  réglementaire, jailbreak existentiel. **No waiver, ever** — so a waiver can
  never be *effective* on a T0 case (the ``T0 ∩ dérogations = ∅`` invariant).
* **Tier 1 — critique dérogeable**: high-stakes cases *outside* the floor,
  blocking by default, levable only under a governed waiver. Enumerated in
  ``eval/tiers.yaml`` (curated, versioned).
* **Tier 2 — domaine gradé**: everything else, judged against the set's
  ``min_pass_rate``.

This module is the single source of truth for ``tier_for(case_id)``. T0 is
derived from the socle (never duplicated), T1 from the versioned YAML, T2 is the
remainder — so the three tiers partition the catalogue with no overlap.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from eval.sets import load_security_floor

__all__ = [
    "Tier",
    "TierMap",
    "is_waivable",
    "load_tier_map",
    "tier_for",
]

Tier = Literal["T0", "T1", "T2"]

_TIERS_YAML = Path(__file__).resolve().parents[3] / "eval" / "tiers.yaml"

# Human-facing French labels + the policy's "waivable" property per tier.
_TIER_LABEL: dict[Tier, str] = {
    "T0": "Cœur non-dérogeable",
    "T1": "Critique dérogeable",
    "T2": "Domaine gradé",
}
_TIER_WAIVABLE: dict[Tier, bool] = {"T0": False, "T1": True, "T2": False}


class TierMap:
    """Immutable T0/T1/T2 classification, loaded once and cached.

    T0 is the curated socle (source: ``socle-securite.json``); T1 is the curated
    ``eval/tiers.yaml`` list; T2 is the implicit remainder. The constructor
    asserts the policy invariant that T0 and T1 are disjoint — a socle case can
    never be tagged "dérogeable".
    """

    def __init__(self, *, t0: frozenset[str], t1: frozenset[str], version: int) -> None:
        overlap = t0 & t1
        if overlap:
            msg = f"eval-gate tier conflict: socle (T0) cases also listed as T1: {sorted(overlap)}"
            raise ValueError(msg)
        self._t0 = t0
        self._t1 = t1
        self.version = version

    @property
    def t0_cases(self) -> frozenset[str]:
        """The non-dérogeable socle case ids (Tier 0)."""
        return self._t0

    @property
    def t1_cases(self) -> frozenset[str]:
        """The dérogeable critical case ids (Tier 1)."""
        return self._t1

    def tier_of(self, case_id: str) -> Tier:
        """Classify one case id into its tier (T2 is the default remainder)."""
        if case_id in self._t0:
            return "T0"
        if case_id in self._t1:
            return "T1"
        return "T2"

    def is_critical(self, case_id: str) -> bool:
        """Whether a case is critical (T0 or T1) — blocking by default."""
        return case_id in self._t0 or case_id in self._t1

    @staticmethod
    def label(tier: Tier) -> str:
        """French label for a tier code."""
        return _TIER_LABEL[tier]

    @staticmethod
    def waivable(tier: Tier) -> bool:
        """Whether the policy allows a governed waiver to lift this tier."""
        return _TIER_WAIVABLE[tier]


@lru_cache(maxsize=1)
def load_tier_map() -> TierMap:
    """Load and cache the three-tier classification (T0 socle + T1 YAML)."""
    t0 = frozenset(load_security_floor().case_ids)
    raw = yaml.safe_load(_TIERS_YAML.read_text(encoding="utf-8"))
    raw = raw if isinstance(raw, dict) else {}
    version = int(raw.get("version", 1) or 1)
    tier1 = raw.get("tier1") if isinstance(raw.get("tier1"), dict) else {}
    cases = tier1.get("cases") if isinstance(tier1, dict) else []
    t1 = frozenset(str(c) for c in cases) if isinstance(cases, list) else frozenset()
    return TierMap(t0=t0, t1=t1, version=version)


def tier_for(case_id: str) -> Tier:
    """Return the tier (``T0`` / ``T1`` / ``T2``) of one catalogue case id."""
    return load_tier_map().tier_of(case_id)


def is_waivable(case_id: str) -> bool:
    """Whether a governed waiver could ever be effective on this case (T1 only)."""
    return load_tier_map().waivable(load_tier_map().tier_of(case_id))
