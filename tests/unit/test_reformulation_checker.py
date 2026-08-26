"""Unit behaviours of the layer-3 must-survive checker and its gate (ADR 0054).

The referent ratchet measures the checker over the whole labeled set; this file
pins the individual RULES — each on a minimal pair, so a broken rule names
itself instead of surfacing as an opaque count drop — plus the two seams other
code depends on: the closed instruction gate and the ONE forbidden-terms source
shared with the drafting policy.
"""

from __future__ import annotations

import pytest

from tessera.recouvrement.reformulation import (
    FORBIDDEN_CLIENT_MESSAGE_TERMS,
    TONE_INSTRUCTIONS,
    check_must_survive,
    gate_tone_instruction,
)

_TEMPLATE_FR = (
    "Bonjour Marie Lefèvre,\n\n"
    "Nous vous contactons au sujet du dossier RC-2048. Le montant restant dû est de "
    "1 260,50 €.\n\n"
    "Votre promesse de paiement du 12 août n'a pas pu être tenue. Le dossier présente un "
    "retard de 23 jours.\n\n"
    "Cordialement,\nCrédit Aurore"
)


def _faithful() -> str:
    return (
        "Bonjour Marie Lefèvre,\n\n"
        "Nous revenons vers vous, avec toute notre considération, au sujet du dossier "
        "RC-2048. Le montant restant dû est de 1 260,50 €.\n\n"
        "Votre promesse de paiement du 12 août n'a pas pu être tenue. Le dossier présente un "
        "retard de 23 jours.\n\n"
        "Cordialement,\nCrédit Aurore"
    )


def test_a_faithful_tone_rewrite_passes() -> None:
    verdict = check_must_survive(_TEMPLATE_FR, _faithful(), language="fr")
    assert verdict.ok and verdict.failures == ()


def test_a_changed_amount_is_named() -> None:
    verdict = check_must_survive(
        _TEMPLATE_FR, _faithful().replace("1 260,50 €", "1 270,50 €"), language="fr"
    )
    assert not verdict.ok
    assert any(f.startswith("number_missing:260") for f in verdict.failures)
    assert any(f.startswith("number_invented:270") for f in verdict.failures)
    assert any(f.startswith("amount_missing:") for f in verdict.failures)


def test_an_invented_figure_is_named() -> None:
    verdict = check_must_survive(
        _TEMPLATE_FR, _faithful() + " Merci de régler sous 48 heures.", language="fr"
    )
    assert not verdict.ok
    assert "number_invented:48" in verdict.failures


def test_a_worded_number_fails_verbatim_survival() -> None:
    # "23 jours" -> "vingt-trois jours": the fact is arguably intact, but the ADR requires
    # VERBATIM survival — strictness errs toward sending the exact template, always safe.
    verdict = check_must_survive(
        _TEMPLATE_FR, _faithful().replace("23 jours", "vingt-trois jours"), language="fr"
    )
    assert not verdict.ok
    assert "number_missing:23" in verdict.failures


def test_the_promise_clause_must_survive_verbatim() -> None:
    reworded = _faithful().replace(
        "Votre promesse de paiement du 12 août n'a pas pu être tenue.",
        "Votre promesse de paiement du 12 août reste ouverte.",
    )
    verdict = check_must_survive(_TEMPLATE_FR, reworded, language="fr")
    assert not verdict.ok
    assert any(f.startswith("clause_missing:") for f in verdict.failures)


def test_the_signature_must_survive() -> None:
    verdict = check_must_survive(
        _TEMPLATE_FR, _faithful().replace("Crédit Aurore", "Le service"), language="fr"
    )
    assert not verdict.ok
    assert "signature_missing:" in verdict.failures


def test_identity_context_fields_must_survive() -> None:
    candidate = _faithful().replace("Marie Lefèvre", "Madame")
    verdict = check_must_survive(
        _TEMPLATE_FR, candidate, language="fr", context={"client": "Marie Lefèvre"}
    )
    assert not verdict.ok
    assert "context_missing:client" in verdict.failures


def test_a_forbidden_term_is_caught_accents_or_not() -> None:
    verdict = check_must_survive(
        _TEMPLATE_FR, _faithful() + " À défaut, une mise en demeure suivra.", language="fr"
    )
    assert not verdict.ok
    assert "forbidden_term:mise en demeure" in verdict.failures


def test_thin_spaces_never_fail_a_survival_check() -> None:
    # A model that renders the grouped amount with a narrow no-break space is faithful.
    candidate = _faithful().replace("1 260,50 €", "1\u202f260,50\u00a0€")
    verdict = check_must_survive(_TEMPLATE_FR, candidate, language="fr")
    assert verdict.ok, verdict.failures


def test_an_empty_candidate_is_refused() -> None:
    verdict = check_must_survive(_TEMPLATE_FR, "   ", language="fr")
    assert verdict.failures == ("empty_candidate:",)


@pytest.mark.parametrize("instruction", TONE_INSTRUCTIONS)
def test_the_gate_accepts_exactly_the_closed_vocabulary(instruction: str) -> None:
    assert gate_tone_instruction(instruction) == instruction
    assert gate_tone_instruction(instruction.upper()) == instruction
    assert gate_tone_instruction(f"  {instruction}  ") == instruction


@pytest.mark.parametrize(
    "adversarial",
    ["sois drôle", "make it funny", "be casual", "duze den Kunden", "", "plus_agressif"],
)
def test_the_gate_refuses_everything_else(adversarial: str) -> None:
    assert gate_tone_instruction(adversarial) is None


def test_the_forbidden_terms_have_one_source() -> None:
    """The drafting policy review consumes THIS set — a fork would let the two checks drift."""
    import inspect

    from tessera.agent import recouvrement as graph

    source = inspect.getsource(graph.review_client_message_policy)
    assert "FORBIDDEN_CLIENT_MESSAGE_TERMS" in source
    assert "mise en demeure" in FORBIDDEN_CLIENT_MESSAGE_TERMS
