"""Unit tests for unicode steganography detection (ADR 0010, #72)."""

from __future__ import annotations

from tessera.observability import steganography as stego

# Built with chr() so the source file carries no literal hidden characters.
_ZWSP = chr(0x200B)  # zero-width space
_ZWJ = chr(0x200D)  # zero-width joiner
_RLO = chr(0x202E)  # right-to-left override


def test_clean_text_has_no_findings() -> None:
    report = stego.scan_text("Quel est le solde de mon compte ?")
    assert report.clean is True
    assert report.n_hidden == 0
    assert report.categories == {}
    assert report.decoded_tags == ""


def test_zero_width_is_detected() -> None:
    report = stego.scan_text(f"hel{_ZWSP}lo{_ZWJ}world")
    assert report.clean is False
    assert report.categories.get("zero_width") == 2


def test_bidi_override_is_detected() -> None:
    report = stego.scan_text(f"balance{_RLO}tnuocca")
    assert report.categories.get("bidi") == 1


def test_tag_chars_decode_hidden_ascii() -> None:
    # Smuggle "hi" via the Unicode tag block (U+E0000 + ascii).
    smuggled = "ok" + chr(0xE0000 + ord("h")) + chr(0xE0000 + ord("i"))
    report = stego.scan_text(smuggled)
    assert report.categories.get("tag") == 2
    assert report.decoded_tags == "hi"
