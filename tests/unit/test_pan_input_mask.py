"""Unit tests for the input-side PAN mask (docs/design/pii-input-redaction.md).

``mask_pan`` rewrites what the *user* said, so its false-positive behaviour is
the contract under test: Luhn-valid card numbers are masked to the output leg's
``XXXX XXXX XXXX 6467`` form; everything else — Luhn-invalid runs (declared
residual), IBAN bodies, order/ticket references, phone numbers, account
numbers, amounts — must pass through byte-identical. Idempotence is asserted
explicitly (design note §4.3).

The corpus-derived fixtures frozen from the real-transcript replay live in
``test_pan_corpus_fixtures.py``; this file covers the primitive's mechanics.
"""

from __future__ import annotations

import pytest

from tessera.guard.redaction import mask_pan

# Luhn-valid test PANs (verified with an independent checksum before freezing).
_VISA_16 = "4242424242424242"
_VISA_16_REPO = "4539148803436467"  # the output-leg suite's own test PAN
_AMEX_15 = "378282246310005"
_VISA_13 = "4222222222222"
_PAN_19 = "4970101234567890127"
# Luhn-invalid — the declared residual (design note §4.4). The first is the
# design note's original example number.
_INVALID_16 = "4970101234567890"
_INVALID_16_B = "4242424242424241"


# ---------------------------------------------------------------------------
# Luhn-valid PANs are masked, keeping the last four
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ma carte 4242 4242 4242 4242 est refusée", "ma carte XXXX XXXX XXXX 4242 est refusée"),
        ("carte 4242-4242-4242-4242 bloquée", "carte XXXX XXXX XXXX 4242 bloquée"),
        ("carte 4242.4242.4242.4242 bloquée", "carte XXXX XXXX XXXX 4242 bloquée"),
        (f"compact {_VISA_16} fin", "compact XXXX XXXX XXXX 4242 fin"),
        (f"Kartennummer {_VISA_16_REPO}.", "Kartennummer XXXX XXXX XXXX 6467."),
        ("Amex 3782 822463 10005 déclinée", "Amex XXXX XXXX XXXX 0005 déclinée"),
        (f"legacy Visa {_VISA_13} ok", "legacy Visa XXXX XXXX XXXX 2222 ok"),
        (f"UnionPay {_PAN_19} refusée", "UnionPay XXXX XXXX XXXX 0127 refusée"),
        ("4242\u00a04242\u00a04242\u00a04242 (NBSP)", "XXXX XXXX XXXX 4242 (NBSP)"),
    ],
)
def test_luhn_valid_pan_masked(text: str, expected: str) -> None:
    result = mask_pan(text)
    assert result.text == expected
    assert result.changed
    # Labels carry only the masked form, never the original digits.
    assert all("XXXX" in label for label in result.redactions)


def test_multiple_pans_all_masked() -> None:
    text = f"ancienne {_VISA_16} et nouvelle {_AMEX_15}"
    result = mask_pan(text)
    assert result.text == "ancienne XXXX XXXX XXXX 4242 et nouvelle XXXX XXXX XXXX 0005"
    assert len(result.redactions) == 2


def test_pan_behind_list_number_still_masked() -> None:
    # "1. " merges into the digit run; the declined candidate must not shadow
    # the real PAN behind it (group-boundary retry).
    result = mask_pan("1. 4242 4242 4242 4242")
    assert result.text == "1. XXXX XXXX XXXX 4242"


def test_pan_behind_year_still_masked() -> None:
    result = mask_pan("depuis 2024 4242 4242 4242 4242 refusée")
    assert result.text == "depuis 2024 XXXX XXXX XXXX 4242 refusée"


def test_pan_after_iban_in_same_text_masked() -> None:
    text = f"IBAN FR76 3000 6000 0112 3456 7890 189, carte {_VISA_16}"
    result = mask_pan(text)
    assert result.text == "IBAN FR76 3000 6000 0112 3456 7890 189, carte XXXX XXXX XXXX 4242"
    assert len(result.redactions) == 1


# ---------------------------------------------------------------------------
# Everything else passes through byte-identical
# ---------------------------------------------------------------------------

_MUST_NOT_MASK = [
    # Luhn-invalid card-shaped runs — the declared residual (note §4.4).
    f"ma carte {_INVALID_16} est refusée",
    f"carte {_INVALID_16_B}",
    "carte 4970 1012 3456 7890 refusée",
    # IBAN bodies, grouped / compact / lowercase / letter bank code (GB).
    "mon IBAN est FR76 3000 6000 0112 3456 7890 189 merci",
    "IBAN : DE89 3704 0044 0532 0130 00",
    "GB29 NWBK 6016 1331 9268 19",
    "virement vers FR7630006000011234567890189",
    "iban fr76 3000 6000 0112 3456 7890 189",
    "FR76-3000-6000-0112-3456-7890-189",
    # Phone numbers (grouped, international, trunk zero).
    "rappelez-moi au 06 12 34 56 78",
    "tel +33 6 12 34 56 78",
    "Festnetz +49 30 123456789",
    "au 0033 6 12 34 56 78 svp",
    # Account / order / ticket references.
    "mon compte n° 00098123",
    "compte 0009812300123456",
    "commande 2024031299887767 non livrée",
    "réf. 2024031299887766",
    "ticket TSR-483920155",
    "dossier n° 4839201",
    # Amounts (decimal tail, grouped thousands).
    "solde de 1234567890123,45 €",
    "montant : 12 345 678 901 234,56 EUR",
    "4 567,89 € le 12.03.2024",
    # Dates and short digit runs.
    "rendez-vous le 12.03.2024 à 14h30",
    "code postal 75012, tél 01 42 00 00 00",
]


@pytest.mark.parametrize("text", _MUST_NOT_MASK)
def test_never_masked(text: str) -> None:
    result = mask_pan(text)
    assert result.text == text
    assert not result.changed
    assert result.redactions == ()


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_idempotence_on_masked_pans() -> None:
    # Design note §4.3: mask(mask(x)) == mask(x), asserted.
    samples = [
        f"ma carte {_VISA_16} et l'Amex 3782 822463 10005",
        f"IBAN FR76 3000 6000 0112 3456 7890 189 puis carte {_VISA_16_REPO}",
        "1. 4242 4242 4242 4242",
        *_MUST_NOT_MASK,
    ]
    for text in samples:
        once = mask_pan(text)
        twice = mask_pan(once.text)
        assert twice.text == once.text
        assert not twice.changed


def test_masked_form_matches_output_leg() -> None:
    # Input and output legs must be indistinguishable downstream.
    assert mask_pan(f"carte {_VISA_16_REPO}").text == "carte XXXX XXXX XXXX 6467"


def test_empty_and_digitless_fast_path() -> None:
    assert mask_pan("").text == ""
    assert mask_pan("aucun chiffre ici").text == "aucun chiffre ici"
