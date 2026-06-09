"""Unit tests for corpus freshness (ADR 0010, #50)."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.observability.corpus_freshness import assess_freshness, load_corpus_freshness

if TYPE_CHECKING:
    from pathlib import Path


def test_empty() -> None:
    report = assess_freshness([])
    assert report.n_corpora == 0
    assert report.n_stale == 0
    assert report.oldest_age_days == 0


def test_staleness_threshold() -> None:
    report = assess_freshness(
        [("regulations_dora", 12, 30), ("regulations_gdpr", 10, 400)],
        max_age_days=180,
    )
    assert report.n_corpora == 2
    assert report.n_stale == 1
    by = {r.corpus: r for r in report.regulations}
    assert by["dora"].stale is False
    assert by["gdpr"].stale is True
    # Authoritative as-of is attached for known families.
    assert by["dora"].as_of == "2025-01-17"


def test_sorted_oldest_first() -> None:
    report = assess_freshness(
        [("regulations_a", 1, 10), ("regulations_b", 1, 200), ("regulations_c", 1, 90)]
    )
    ages = [r.age_days for r in report.regulations]
    assert ages == sorted(ages, reverse=True)
    assert report.oldest_age_days == 200


def test_unknown_family_has_no_as_of() -> None:
    report = assess_freshness([("regulations_mifid", 5, 10)])
    assert report.regulations[0].as_of is None


def test_load_from_dir_uses_mtime(tmp_path: Path) -> None:
    dora = tmp_path / "regulations_dora.json"
    dora.write_text(json.dumps([{"source": "DORA/art-5", "text": "x"}]), encoding="utf-8")
    # Backdate the file 400 days.
    old = time.time() - 400 * 86400
    os.utime(dora, (old, old))
    # A non-regulation file must be ignored.
    (tmp_path / "credit_aurore_fr.json").write_text("[]", encoding="utf-8")

    report = load_corpus_freshness(tmp_path, now=datetime.now(UTC), max_age_days=180)
    assert report.n_corpora == 1
    assert report.regulations[0].corpus == "dora"
    assert report.regulations[0].n_docs == 1
    assert report.regulations[0].stale is True


def test_load_recent_file_not_stale(tmp_path: Path) -> None:
    f = tmp_path / "regulations_gdpr.json"
    f.write_text(json.dumps([{"source": "a"}, {"source": "b"}]), encoding="utf-8")
    now = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) + timedelta(days=5)
    report = load_corpus_freshness(tmp_path, now=now, max_age_days=180)
    assert report.regulations[0].n_docs == 2
    assert report.regulations[0].stale is False
