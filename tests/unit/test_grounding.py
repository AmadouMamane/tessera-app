"""Unit tests for the grounding-refusal gate (guard.grounding + reviewer leg).

The false-positive suite is the contract: a legitimate, grounded answer —
tool result, well-retrieved fact, policy refusal — must never be hedged.
"""

from __future__ import annotations

import uuid

import pytest

from tessera.agent import reviewer
from tessera.agent.state import RetrievedDocument, ToolCallRecord, new_state
from tessera.guard.grounding import (
    POLICY_RULE,
    REPLACED_CONFIDENCE,
    apply_grounding_guard,
    declares_unanswerable,
    hedge_response,
    unsupported_specifics,
)
from tessera.settings import LanguageCode


def _doc(
    text: str, source: str = "credit-aurore/produits/livret-aurore", **meta: str
) -> RetrievedDocument:
    return RetrievedDocument(
        source=source,
        chunk_id=f"{source}#0",
        language=LanguageCode.FR,
        text=text,
        score=0.02,
        metadata=dict(meta),
    )


_DOCS = [
    _doc("Le Livret Aurore est rémunéré à 3 % dans la limite d'un plafond de 22 950 €."),
    _doc(
        "DORA Artikel 19: Meldung schwerwiegender IKT-Vorfälle innerhalb von 4 Stunden.",
        source="DORA/art-19",
        locator="DORA Article 19",
    ),
]


class TestUnsupportedSpecifics:
    def test_supported_claims_never_flag(self) -> None:
        # Same numbers/units as the corpus, cross-language (heures <- Stunden)
        assert unsupported_specifics("Le taux est de 3 % et le délai de 4 heures.", _DOCS) == ()
        # Article backed by the chunk locator
        assert unsupported_specifics("Voir l'article 19 de DORA.", _DOCS) == ()
        # Grouping style differences (100 000 vs 100.000) are normalised
        de_doc = [_doc("Die Einlagensicherung beträgt 100.000 € je Einleger.")]
        assert unsupported_specifics("La garantie est de 100 000 €.", de_doc) == ()

    def test_bare_numbers_and_years_are_not_claims(self) -> None:
        assert unsupported_specifics("Depuis 2025, la directive 2014/49 s'applique.", _DOCS) == ()

    def test_fabricated_article_flags(self) -> None:
        flagged = unsupported_specifics("Oui, l'article 87 de DORA impose ce délai.", _DOCS)
        assert flagged and "article 87" in flagged[0]

    def test_invented_quantified_promise_flags(self) -> None:
        assert unsupported_specifics("Un cashback de 2 % vous est offert.", _DOCS) == ("2 %",)

    def test_fabricated_case_and_deliberation_flag(self) -> None:
        flagged = unsupported_specifics(
            "L'affaire C-123/45 et la délibération n° 2019-001 l'imposent.", _DOCS
        )
        assert set(flagged) == {"C-123/45", "n° 2019-001"}

    def test_brand_echo_flags_only_from_user_input(self) -> None:
        text = "L'application AuroreSecure Pay est disponible."
        ask = "Parlez-moi de AuroreSecure Pay"
        assert unsupported_specifics(text, _DOCS, user_input=ask) == ("AuroreSecure",)
        assert unsupported_specifics(text, _DOCS) == ()

    def test_no_documents_never_flags(self) -> None:
        assert unsupported_specifics("Un cashback de 9 % est garanti.", []) == ()

    def test_conversational_durations_never_flag(self) -> None:
        # "two years behind" arithmetic is not a commitment — never a claim
        assert unsupported_specifics("Vous êtes en retard de 24 mois environ.", _DOCS) == ()
        assert unsupported_specifics("Sie sind seit 24 Monaten im Verzug.", _DOCS) == ()

    def test_commitment_durations_flag_when_unsupported(self) -> None:
        flagged = unsupported_specifics(
            "Notre politique de remboursement rétroactif couvre 12 mois.", _DOCS
        )
        assert flagged == ("12 mois",)
        flagged = unsupported_specifics("There is an automatic 12-month retroactive refund.", _DOCS)
        assert flagged == ("12-month",)

    def test_refusal_repeating_the_users_figure_never_flags(self) -> None:
        # A refusal that politely repeats the user's own amount is not a claim
        assert (
            unsupported_specifics(
                "Un prêt de 1 000 000 000 € dépasse nos limites : je ne peux pas le simuler.",
                _DOCS,
                user_input="Simule-moi un prêt personnel de 1 000 000 000 € sur 6 mois.",
            )
            == ()
        )
        assert (
            unsupported_specifics(
                "Je ne peux pas donner de conseil d'investissement pour vos 20 000 €.",
                _DOCS,
                user_input="J'ai 20 000 € à placer, dis-moi quelles actions acheter.",
            )
            == ()
        )

    def test_affirmation_of_the_users_figure_still_flags(self) -> None:
        # Same echoed figure, but the agent AFFIRMS instead of refusing
        flagged = unsupported_specifics(
            "Bien sûr, un rendement garanti de 15 % est prévu pour vos placements.",
            _DOCS,
            user_input="On m'a promis 15 % garantis, c'est bien ça ?",
        )
        assert flagged == ("15 %",)


class TestApplyGroundingGuard:
    @pytest.mark.parametrize("language", list(LanguageCode))
    def test_unsupported_claim_is_replaced_with_hedge(self, language: LanguageCode) -> None:
        check = apply_grounding_guard(
            "Oui, l'article 87 de DORA impose un délai de notification de 4 heures.",
            language=language,
            documents=_DOCS,
        )
        assert check.replaced is True
        assert check.text == hedge_response(language)
        assert check.record is not None
        assert check.record.policy_rule == POLICY_RULE
        assert "article 87" in check.record.rationale

    def test_supported_answer_untouched(self) -> None:
        text = "Le Livret Aurore est rémunéré à 3 %, plafonné à 22 950 €."
        check = apply_grounding_guard(text, language=LanguageCode.FR, documents=_DOCS)
        assert check.replaced is False
        assert check.text == text
        assert check.record is None

    # ------------------------------------------------------------------
    # False-positive contract: legitimate grounded turns are never hedged.
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "text",
        [
            "Votre mensualité serait de 927,45 € sur 20 ans au taux de 3,5 %.",  # fr
            "Ihre monatliche Rate beträgt 927,45 € über 20 Jahre bei 3,5 %.",  # de
            "Your monthly payment would be EUR 927.45 over 20 years at 3.5%.",  # en
        ],
    )
    def test_tool_grounded_turn_never_hedged(self, text: str) -> None:
        check = apply_grounding_guard(
            text, language=LanguageCode.FR, documents=_DOCS, tool_grounded=True
        )
        assert check.replaced is False
        assert check.text == text

    def test_policy_refusal_turn_never_hedged(self) -> None:
        text = "Je ne peux pas communiquer le solde d'un tiers (durée légale : 5 ans)."
        check = apply_grounding_guard(
            text, language=LanguageCode.FR, documents=_DOCS, policy_refusal=True
        )
        assert check.replaced is False

    def test_sandbox_override_disables_the_gate(self) -> None:
        check = apply_grounding_guard(
            "Un cashback de 9 % est garanti.",
            language=LanguageCode.FR,
            documents=_DOCS,
            disabled=True,
        )
        assert check.replaced is False

    def test_answer_without_specific_claims_untouched(self) -> None:
        text = "Bonjour ! Je peux vous renseigner sur nos livrets et cartes."
        check = apply_grounding_guard(text, language=LanguageCode.FR, documents=_DOCS)
        assert check.replaced is False


class TestHedgeWording:
    """The hedge must read as a natural honest refusal in every language."""

    def test_fr_tokens(self) -> None:
        hedge = hedge_response(LanguageCode.FR)
        for token in ("ne trouve pas", "ne peux", "vérifier", "source officielle"):
            assert token in hedge

    def test_de_tokens(self) -> None:
        hedge = hedge_response(LanguageCode.DE)
        for token in ("kann ich nicht", "finde ich nicht", "nicht finden", "offiziellen Quelle"):
            assert token in hedge

    def test_en_tokens(self) -> None:
        hedge = hedge_response(LanguageCode.EN)
        for token in ("could not find", "cannot find", "verify", "official source"):
            assert token in hedge

    def test_hedges_carry_no_specific_claims(self) -> None:
        for language in LanguageCode:
            assert unsupported_specifics(hedge_response(language), _DOCS) == ()
            assert declares_unanswerable(hedge_response(language))


class TestDeclaresUnanswerable:
    @pytest.mark.parametrize(
        "text",
        [
            "Je ne trouve pas cette référence dans nos documents.",
            "Ich kann das nicht bestätigen.",
            "Ich kann solche Angaben nicht finden.",
            "I could not find any ruling matching this description.",
        ],
    )
    def test_non_answers_detected(self, text: str) -> None:
        assert declares_unanswerable(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Le taux du Livret Aurore est de 3 %.",
            "Votre carte sera bloquée immédiatement.",
            "Je ne peux pas traiter votre demande.",  # policy refusal, not a non-answer
        ],
    )
    def test_confident_or_policy_texts_not_detected(self, text: str) -> None:
        assert not declares_unanswerable(text)


class TestReviewerDraftLeg:
    def _state(self, **kwargs: object) -> dict[str, object]:
        state = new_state(
            conversation_id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            user_input="Parlez-moi du produit X",
            language=LanguageCode.FR,
            language_confidence=1.0,
        )
        state.update(kwargs)  # type: ignore[typeddict-item]
        return dict(state)

    def test_ungrounded_draft_is_replaced(self) -> None:
        update = reviewer.run(self._state(draft_response="Le produit X offre 9 % garantis."))  # type: ignore[arg-type]
        assert update["draft_response"] == hedge_response(LanguageCode.FR)
        assert update["needs_escalation"] is False
        assert update["confidence"] == REPLACED_CONFIDENCE
        records = update["guard_decisions"]
        assert isinstance(records, list) and records[0].policy_rule == POLICY_RULE

    def test_tool_grounded_draft_untouched(self) -> None:
        call = ToolCallRecord(
            tool_name="loan_simulate",
            arguments={"amount": 100000},
            result={"monthly": 927.45},
            succeeded=True,
        )
        update = reviewer.run(  # type: ignore[arg-type]
            self._state(draft_response="Votre mensualité serait de 927,45 €.", tool_calls=[call])
        )
        assert "draft_response" not in update
        assert "guard_decisions" not in update

    def test_draft_with_documents_untouched_here(self) -> None:
        update = reviewer.run(  # type: ignore[arg-type]
            self._state(
                draft_response="Le Livret Aurore est rémunéré à 3 %.",
                retrieved_documents=_DOCS,
            )
        )
        assert "draft_response" not in update
