"""A duplicate key in a message catalogue is silent — every JSON-based check is blind to it.

``JSON.parse`` and ``json.loads`` both accept a duplicate key and keep the last value. So a
catalogue with ``"h24"`` written twice in one object parses, type-checks, renders, and passes
the parity ratchet (which counts *parsed* leaves — the duplicate is already gone by then).
The only witness is one that reads the key/value PAIRS before the parser collapses them.

This is not hypothetical: inserting a new label on 2026-08-04 anchored on a line
(``"d7": "7 jours",``) that occurs in two namespaces. The insertion landed in the first one,
which already had that key — producing a duplicate — and the reliability namespace it was
meant for did not get the label at all. Both halves of that mistake are silent, and both are
caught here: this file for the duplicate, ``catalogue-parity.test.ts`` for the absence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MESSAGES = Path(__file__).resolve().parents[2] / "webapp" / "frontend" / "messages"
_LOCALES = ("fr", "de", "en")


def _duplicates(path: Path) -> list[str]:
    """Every key written more than once inside one object, as a dotted path."""
    found: list[str] = []

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        for key, _ in pairs:
            if key in seen:
                found.append(key)
            seen.add(key)
        return dict(pairs)

    json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=hook)
    return found


def test_the_catalogues_are_actually_read() -> None:
    """Positive control: a wrong path would make every assertion below vacuous."""
    assert _MESSAGES.is_dir(), f"{_MESSAGES} is not a directory"
    for locale in _LOCALES:
        path = _MESSAGES / f"{locale}.json"
        assert path.exists(), f"{path} is missing"
        size = len(path.read_text(encoding="utf-8"))
        assert size > 100_000, f"{locale}.json is suspiciously small ({size} chars)"


def test_no_message_key_is_written_twice_in_one_object() -> None:
    offenders = {loc: _duplicates(_MESSAGES / f"{loc}.json") for loc in _LOCALES}
    wrong = {loc: keys for loc, keys in offenders.items() if keys}
    assert not wrong, (
        "a key is written twice in one object — the second value silently wins:\n"
        + "\n".join(f"  {loc}: {sorted(set(keys))}" for loc, keys in wrong.items())
    )


def test_the_detector_would_actually_see_a_duplicate(tmp_path: Path) -> None:
    """Negative control: the check above is only worth its green if it can go red."""
    planted = tmp_path / "planted.json"
    planted.write_text('{"a": {"k": 1, "k": 2}, "b": {"k": 3}}', encoding="utf-8")
    assert _duplicates(planted) == ["k"]

    clean = tmp_path / "clean.json"
    clean.write_text('{"a": {"k": 1}, "b": {"k": 2}}', encoding="utf-8")
    assert _duplicates(clean) == [], "the same key in two DIFFERENT objects is not a duplicate"


def test_the_label_that_started_this_is_in_the_namespace_that_needed_it() -> None:
    """The other half of the 2026-08-04 mistake: it went in, but in the wrong place."""
    for locale in _LOCALES:
        doc = json.loads((_MESSAGES / f"{locale}.json").read_text(encoding="utf-8"))
        period = doc["reliability"]["period"]
        assert "h24" in period, f"{locale}: the 24 h preset has no label on Fiabilité & coût"
        assert period["h24"].strip(), f"{locale}: the 24 h label is empty"
