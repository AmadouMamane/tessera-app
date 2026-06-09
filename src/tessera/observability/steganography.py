"""Unicode steganography detection (ADR 0010, idea #72).

Text can carry instructions a human reviewer never sees: zero-width characters
splicing hidden words, bidirectional-override controls reordering what is
rendered, and — most insidiously — Unicode *tag* characters (U+E0000..U+E007F)
that encode arbitrary ASCII invisibly. An attacker can smuggle "ignore your
rules" into an otherwise innocent-looking message or document.

This module is pure and dependency-free: it classifies every suspicious
codepoint, decodes any ASCII hidden in tag characters (revealing the smuggled
payload), and returns a cleaned copy with the hidden characters stripped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["StegoFinding", "StegoReport", "scan_text"]

# Zero-width and invisible formatting characters.
_ZERO_WIDTH = frozenset(
    {
        0x200B,  # zero-width space
        0x200C,  # zero-width non-joiner
        0x200D,  # zero-width joiner
        0x2060,  # word joiner
        0xFEFF,  # zero-width no-break space / BOM
    }
)
# Bidirectional override / isolate controls (text-reordering attacks).
_BIDI = frozenset({0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069})
# Unicode tag block — invisible ASCII smuggling (U+E0000..U+E007F).
_TAG_LO, _TAG_HI = 0xE0000, 0xE007F
# Printable-ASCII range a tag character can decode to.
_ASCII_LO, _ASCII_HI = 0x20, 0x7E


def _category(codepoint: int) -> str | None:
    """Return the steganography category of ``codepoint``, or ``None`` if benign."""
    if codepoint in _ZERO_WIDTH:
        return "zero_width"
    if codepoint in _BIDI:
        return "bidi"
    if _TAG_LO <= codepoint <= _TAG_HI:
        return "tag"
    return None


@dataclass(frozen=True, slots=True)
class StegoFinding:
    """One suspicious codepoint found in the text."""

    codepoint: str  # ``U+XXXX``
    category: str
    position: int


@dataclass(frozen=True, slots=True)
class StegoReport:
    """Hidden-character analysis of a single piece of text."""

    n_hidden: int
    clean: bool
    categories: dict[str, int]
    decoded_tags: str  # ASCII smuggled via tag characters, if any
    findings: list[StegoFinding] = field(default_factory=list)


def scan_text(text: str) -> StegoReport:
    """Scan ``text`` for hidden steganographic characters.

    Returns:
        A :class:`StegoReport` with per-category counts, the ASCII decoded from
        any tag characters, and the list of findings.
    """
    findings: list[StegoFinding] = []
    categories: dict[str, int] = {}
    decoded: list[str] = []
    for position, char in enumerate(text):
        codepoint = ord(char)
        category = _category(codepoint)
        if category is None:
            continue
        categories[category] = categories.get(category, 0) + 1
        findings.append(
            StegoFinding(codepoint=f"U+{codepoint:04X}", category=category, position=position)
        )
        if category == "tag":
            # Tag characters map to ASCII as codepoint - 0xE0000.
            ascii_code = codepoint - _TAG_LO
            if _ASCII_LO <= ascii_code <= _ASCII_HI:
                decoded.append(chr(ascii_code))

    return StegoReport(
        n_hidden=len(findings),
        clean=not findings,
        categories=categories,
        decoded_tags="".join(decoded),
        findings=findings,
    )
