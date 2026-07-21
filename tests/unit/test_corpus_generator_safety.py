"""Regression tests for non-destructive, atomic corpus generation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tessera.corpus import generator
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    from pathlib import Path


def _page(source: str, *, text: str = "Editorial content") -> dict[str, object]:
    return {
        "source": source,
        "language": "fr",
        "text": text,
        "metadata": {"product": "editorial", "locator": source},
    }


def test_generation_preserves_editorial_pages_and_upserts_managed_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generator, "_resolve_data_dir", lambda: tmp_path)
    target = tmp_path / "credit_aurore_fr.json"
    existing = [
        _page("credit-aurore-livret-aurore", text="stale managed copy"),
        *[_page(f"editorial-{index}") for index in range(12)],
    ]
    target.write_text(json.dumps(existing), encoding="utf-8")

    generator._write_corpus(LanguageCode.FR, generator._CATALOGUE[LanguageCode.FR])

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload) == 13  # no legacy bootstrap duplicate is appended
    assert {item["source"] for item in payload} >= {f"editorial-{index}" for index in range(12)}
    managed = next(item for item in payload if item["source"] == "credit-aurore-livret-aurore")
    assert managed["text"] != "stale managed copy"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_invalid_existing_corpus_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generator, "_resolve_data_dir", lambda: tmp_path)
    target = tmp_path / "credit_aurore_fr.json"
    original = "{broken json\n"
    target.write_text(original, encoding="utf-8")

    with pytest.raises(generator.CorpusGenerationError, match="refusing to replace"):
        generator._write_corpus(LanguageCode.FR, generator._CATALOGUE[LanguageCode.FR])

    assert target.read_text(encoding="utf-8") == original


def test_cross_language_page_is_refused_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generator, "_resolve_data_dir", lambda: tmp_path)
    target = tmp_path / "credit_aurore_fr.json"
    target.write_text(json.dumps([{**_page("wrong-language"), "language": "en"}]), encoding="utf-8")

    with pytest.raises(generator.CorpusGenerationError, match="expected 'fr'"):
        generator._write_corpus(LanguageCode.FR, generator._CATALOGUE[LanguageCode.FR])
