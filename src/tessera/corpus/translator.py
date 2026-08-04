"""Contributor tool: translate a corpus page to FR / DE / EN via the LLM.

The translator is *not* part of the runtime path — it is a helper invoked
manually when a new product page is added. Output must always be
human-reviewed before being committed to the catalogue.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from tessera.llm import ChatMessage, get_chat_backend
from tessera.llm.ceiling import resolve_spend_model

__all__ = ["translate_page"]


_INSTRUCTION: dict[Literal["fr", "de", "en"], str] = {
    "fr": (
        "Tu es un traducteur professionnel spécialisé dans les produits bancaires. "
        "Traduis le texte ci-dessous en français commercial-juridique précis et "
        "courtois. Conserve les chiffres, taux, devises et noms de produits."
    ),
    "de": (
        "Sie sind ein professioneller Übersetzer mit Spezialisierung auf "
        "Bankprodukte. Übersetzen Sie den nachstehenden Text in präzises, "
        "kundenfreundliches juristisches Deutsch. Bewahren Sie alle Zahlen, "
        "Zinssätze, Währungen und Produktnamen."
    ),
    "en": (
        "You are a professional translator specialised in banking products. "
        "Translate the text below into precise, customer-friendly legal "
        "English. Preserve all numbers, rates, currencies, and product names."
    ),
}


async def translate_page(
    *,
    text: str,
    target: Literal["fr", "de", "en"],
) -> str:
    """Translate ``text`` into ``target`` via the active chat backend.

    Raises:
        DailyCeilingReachedError: The org's daily ceiling is reached (ADR 0034). Raised rather
            than returning the source text: a corpus page that silently stayed in its original
            language would be a translation failure that looks like a translation.
    """
    model = await resolve_spend_model(caller="corpus.translator")
    backend = get_chat_backend()
    response = await backend.chat(
        [
            ChatMessage(role="system", content=_INSTRUCTION[target]),
            ChatMessage(role="user", content=text),
        ],
        temperature=0.1,
        model=model,
    )
    return response.content.strip()


def main() -> None:
    """CLI: ``uv run python -m tessera.corpus.translator --target de <text>``."""
    import argparse

    parser = argparse.ArgumentParser(description="Translate a corpus page.")
    parser.add_argument("--target", required=True, choices=["fr", "de", "en"])
    parser.add_argument("text")
    args = parser.parse_args()
    print(asyncio.run(translate_page(text=args.text, target=args.target)))


if __name__ == "__main__":  # pragma: no cover
    main()
