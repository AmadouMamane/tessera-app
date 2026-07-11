"""Corpus freshness vs live regulations (ADR 0010, idea #50).

Regulatory text is not static — DORA, GDPR, CNIL guidance and BaFin circulars are
amended, and an answer grounded in a superseded article is wrong even when the
retrieval is perfect. This module surfaces *staleness*: how old each ingested
regulatory corpus is, and whether it has drifted past its review horizon.

The honest framing: in this build the ingestion timestamp is approximated by the
data file's modification time, and the *authoritative as-of* date is a small
curated reference per regulation. A production deployment records the real
ingestion timestamp and the upstream publication date at ingest; the staleness
maths here is identical and ready for those inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = [
    "FreshnessReport",
    "RegulationFreshness",
    "assess_freshness",
    "load_corpus_freshness",
]

# Review horizon: a corpus not refreshed within this many days is stale.
_MAX_AGE_DAYS = 180
# Authoritative reference date per regulation family (applicability / last major
# revision). Curated, verifiable; surfaced so reviewers can sanity-check currency.
_AS_OF: dict[str, str] = {
    "dora": "2025-01-17",  # DORA becomes applicable
    "gdpr": "2018-05-25",  # GDPR applicability
    "cnil": "2024-01-01",  # CNIL guidance reference
    "bafin": "2023-01-01",  # BaFin BAIT/MaRisk reference
}


@dataclass(frozen=True, slots=True)
class RegulationFreshness:
    """Freshness of one ingested regulatory corpus."""

    name: str  # source file stem, e.g. "regulations_dora"
    corpus: str  # regulation family, e.g. "dora"
    n_docs: int
    age_days: int  # days since the corpus was last (re-)ingested
    as_of: str | None  # authoritative reference date, if known
    stale: bool


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    """Staleness across the regulatory corpora."""

    n_corpora: int
    n_stale: int
    max_age_days: int
    oldest_age_days: int
    regulations: list[RegulationFreshness] = field(default_factory=list)


def assess_freshness(
    entries: Sequence[tuple[str, int, int]],
    *,
    max_age_days: int = _MAX_AGE_DAYS,
) -> FreshnessReport:
    """Assess staleness from ``(name, n_docs, age_days)`` triples.

    Args:
        entries: One triple per corpus file: stem name, document count, and age
            in days since last ingestion.
        max_age_days: Review horizon; a corpus older than this is stale.

    Returns:
        A :class:`FreshnessReport`, regulations sorted oldest first.
    """
    regulations: list[RegulationFreshness] = []
    for name, n_docs, age_days in entries:
        corpus = name.removeprefix("regulations_")
        regulations.append(
            RegulationFreshness(
                name=name,
                corpus=corpus,
                n_docs=n_docs,
                age_days=age_days,
                as_of=_AS_OF.get(corpus),
                stale=age_days > max_age_days,
            )
        )
    regulations.sort(key=lambda r: r.age_days, reverse=True)
    return FreshnessReport(
        n_corpora=len(regulations),
        n_stale=sum(1 for r in regulations if r.stale),
        max_age_days=max_age_days,
        oldest_age_days=max((r.age_days for r in regulations), default=0),
        regulations=regulations,
    )


def load_corpus_freshness(
    data_dir: Path,
    *,
    now: datetime | None = None,
    max_age_days: int = _MAX_AGE_DAYS,
) -> FreshnessReport:
    """Read ``regulations_*.json`` files from ``data_dir`` and assess freshness.

    Document counts come from the JSON arrays; ages come from each file's
    modification time (an ingestion proxy, see the module docstring).
    """
    import json

    reference = now or datetime.now(UTC)
    entries: list[tuple[str, int, int]] = []
    for path in sorted(data_dir.glob("regulations_*.json")):
        try:
            docs = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # best-effort: skip an unreadable/corrupt regulations JSON — non-gating (0015)
            continue
        n_docs = len(docs) if isinstance(docs, list) else 1
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        age_days = max(0, (reference - mtime).days)
        entries.append((path.stem, n_docs, age_days))
    return assess_freshness(entries, max_age_days=max_age_days)
