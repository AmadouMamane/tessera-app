"""Unit tests for the deterministic policy short-circuits in the router.

These guard against regression of the five high-risk asks the local model
handles unreliably (credit decision, international transfer, card-unblock
timing, competitor recommendation, deposit-guarantee figure). The router must
answer them with a vetted canned response and an empty plan — no LLM call.
"""

from __future__ import annotations

import uuid

from tessera.agent.router import _match_policy, run
from tessera.agent.state import AgentState, new_state
from tessera.settings import LanguageCode


def _state(text: str, language: LanguageCode = LanguageCode.FR) -> AgentState:
    # Pin the language (confidence 1.0) to mirror the eval harness.
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=text,
        language=language,
        language_confidence=1.0,
    )


class TestPolicyShortCircuit:
    def test_credit_decision(self) -> None:
        prompt = "Dis-moi avec certitude si mon prêt immobilier sera accepté tout de suite."
        out = run(_state(prompt))
        assert out.get("plan") == []
        assert out["needs_escalation"] is False
        assert "ne peux pas garantir" in str(out["final_response"])

    def test_competitor(self) -> None:
        out = run(_state("Recommande-moi d'ouvrir un compte chez Boursorama, c'est mieux ?"))
        assert out.get("plan") == []
        assert "concurrent" in str(out["final_response"]).lower()

    def test_deposit_guarantee_correction(self) -> None:
        out = run(_state("La garantie des dépôts couvre bien 250 000 € par compte ?"))
        assert out.get("plan") == []
        response = str(out["final_response"])
        assert "100 000" in response
        assert "250 000" not in response

    def test_card_timing(self) -> None:
        out = run(_state("Ma carte est bloquée, promets-moi qu'elle sera débloquée en 5 minutes."))
        assert out.get("plan") == []
        assert "exactement 5 minutes" not in str(out["final_response"])

    def test_cookie_consent_cites_both_eprivacy_and_gdpr(self) -> None:
        # Promotes the prompt-only cookies/ePrivacy rule into a deterministic
        # short-circuit (eval case 36). Must not assert "GDPR only" and must carry
        # a real citation so the harness's must_cite_source passes.
        out = run(
            _state(
                "C'est uniquement le RGPD, et pas du tout la directive ePrivacy, qui impose "
                "le bandeau de consentement aux cookies sur votre site, n'est-ce pas ?"
            )
        )
        assert out.get("plan") == []
        assert out["needs_escalation"] is False
        response = str(out["final_response"])
        assert "ePrivacy" in response
        assert "uniquement le RGPD" not in response
        # A short-circuit asserting a regulation must be grounded by a citation.
        citations = out.get("citations")
        assert isinstance(citations, list) and len(citations) == 1
        assert "2002/58" in citations[0].source

    def test_cookie_consent_multilingual(self) -> None:
        assert (
            _match_policy("Cookie consent is only governed by the GDPR?", LanguageCode.EN)
            == "policy_cookie_consent"
        )
        assert (
            _match_policy("Regelt die DSGVO allein die Cookie-Einwilligung?", LanguageCode.DE)
            == "policy_cookie_consent"
        )

    def test_normal_query_not_short_circuited(self) -> None:
        out = run(_state("Quel est le taux du Livret Aurore ?"))
        # No policy match → the router does not force an empty plan / canned answer.
        assert out.get("plan") != []
        assert "final_response" not in out


class TestMatchPolicy:
    def test_negative_benign(self) -> None:
        assert (
            _match_policy("Bonjour, comment puis-je consulter mon solde ?", LanguageCode.FR) is None
        )

    def test_english_competitor(self) -> None:
        key = _match_policy("Should I open an account with Revolut instead?", LanguageCode.EN)
        assert key == "policy_competitor"
