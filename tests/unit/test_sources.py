"""Tests for packaged source document lookup."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tessera.corpus.sources import find_source_document
from tessera.settings import LanguageCode


class TestSourceLookup:
    def test_finds_packaged_product_source(self) -> None:
        document = find_source_document(
            "credit-aurore/produits/virement-sepa-international",
            language=LanguageCode.FR,
        )

        assert document is not None
        assert document.corpus == "credit_aurore"
        assert document.language is LanguageCode.FR
        assert "Virements et paiements" in document.locator

    def test_source_endpoint_returns_document(self) -> None:
        from tessera.api.main import build_app

        client = TestClient(build_app())
        response = client.get(
            "/sources/credit-aurore/produits/virement-sepa-international",
            params={"language": "fr"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "credit-aurore/produits/virement-sepa-international"
        assert payload["language"] == "fr"
        assert "SEPA" in payload["text"]
