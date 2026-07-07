"""Unit tests for the documented signal-catalog page vocabulary."""

from __future__ import annotations

from pathlib import Path

import yaml

ALLOWED_PAGES = {
    "qualite",
    "securite",
    "conformite",
    "fiabilite",
    "cout",
    "agir",
    "metier",
    "plateforme",
    "produit",
    "repo",
}


def _signals() -> list[dict[str, object]]:
    data = yaml.safe_load(Path("docs/signal-catalog.yaml").read_text(encoding="utf-8"))
    signals = data["signals"]
    assert isinstance(signals, list)
    return signals


def test_signal_catalog_page_vocabulary_includes_metier() -> None:
    pages = {str(signal["page"]) for signal in _signals()}

    assert pages <= ALLOWED_PAGES
    assert "metier" in pages


def test_business_metric_candidates_are_homed_on_metier() -> None:
    by_id = {int(signal["id"]): signal for signal in _signals()}

    assert by_id[65]["page"] == "metier"
    assert by_id[139]["page"] == "metier"
    assert by_id[190]["page"] == "metier"
