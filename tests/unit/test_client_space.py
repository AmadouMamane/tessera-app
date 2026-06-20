"""Unit tests for the client-space (Produit) datasets.

Documents are asserted against the real Crédit Aurore corpus (so the page's
"real data" claim is verified, not just its shape). The durable mutations
(``mark_alert_read`` / ``update_setting``) are exercised against a temp store
redirected via ``_state_path``, so no real audit dir is touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability import client_space as cs

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_documents_sourced_from_real_corpus() -> None:
    payload = cs.compute_documents("fr")
    docs = payload["documents"]
    assert isinstance(docs, list)
    # The FR product corpus has 13 unique sources → 13 documents.
    assert len(docs) == 13
    # Every row traces to a real corpus source and carries real body text.
    for d in docs:
        assert d["source"].startswith("credit-aurore/")
        assert len(str(d["body"])) > 0
        assert d["category"] in {"products", "terms", "procedures", "services", "other"}
    # KPIs and distribution are derived from the rows, not invented.
    kpis = {k["key"]: int(k["value"]) for k in payload["kpis"]}
    assert kpis["total"] == 13
    assert sum(s["count"] for s in payload["distribution"]) == 13


def test_documents_locale_fallback() -> None:
    # An unknown locale falls back to FR rather than raising.
    assert cs.compute_documents("xx")["documents"] == cs.compute_documents("fr")["documents"]


def test_requests_shape() -> None:
    payload = cs.compute_requests()
    reqs = payload["requests"]
    assert len(reqs) == 5
    assert {r["status"] for r in reqs} <= {"open", "in_progress", "resolved"}


def test_alert_read_mutation_is_durable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "client_space.json"
    monkeypatch.setattr(cs, "_state_path", lambda: store)

    before = cs.compute_alerts()
    unread_before = int(next(k for k in before["kpis"] if k["key"] == "unread")["value"])

    cs.mark_alert_read("AL-1001", read=True)
    after = cs.compute_alerts()
    unread_after = int(next(k for k in after["kpis"] if k["key"] == "unread")["value"])
    assert unread_after == unread_before - 1
    assert store.exists()  # persisted

    # Toggling back restores the count.
    cs.mark_alert_read("AL-1001", read=False)
    restored = int(next(k for k in cs.compute_alerts()["kpis"] if k["key"] == "unread")["value"])
    assert restored == unread_before


def test_setting_update_is_durable_and_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "client_space.json"
    monkeypatch.setattr(cs, "_state_path", lambda: store)

    assert cs.compute_settings()["values"]["notify_push"] is False
    cs.update_setting("notify_push", True)
    assert cs.compute_settings()["values"]["notify_push"] is True

    # Unknown keys are ignored (no arbitrary writes).
    cs.update_setting("evil_key", "x")
    assert "evil_key" not in cs.compute_settings()["values"]

    # Language is validated.
    cs.update_setting("language", "de")
    assert cs.compute_settings()["values"]["language"] == "de"
    cs.update_setting("language", "zz")
    assert cs.compute_settings()["values"]["language"] == "de"
