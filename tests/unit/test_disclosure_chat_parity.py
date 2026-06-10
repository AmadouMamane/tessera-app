"""Guard: the Art. 50 disclosure shown in the chat must match the canonical text.

The chat composer renders the disclosure from bundled i18n (so it always shows,
even offline), while the observability dashboard monitors the backend's
canonical ``DISCLOSURE_TEXT``. If the two drift, the dashboard would attest a
wording the user never actually sees — a compliance gap. This test fails the
build on any divergence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessera.observability.disclosure import DISCLOSURE_TEXT

_MESSAGES_DIR = Path(__file__).resolve().parents[2] / "webapp" / "frontend" / "messages"


@pytest.mark.parametrize("locale", sorted(DISCLOSURE_TEXT))
def test_chat_disclosure_matches_canonical_text(locale: str) -> None:
    messages = json.loads((_MESSAGES_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    rendered = messages["chat"]["disclosure"]
    assert rendered == DISCLOSURE_TEXT[locale], (
        f"chat disclosure for {locale!r} diverged from tessera.observability.disclosure"
    )
