"""Poisoned-corpus / indirect-injection-via-RAG detection (ADR 0010, idea #52).

The classic prompt-injection guard screens what the *user* types. But a
retrieval-augmented agent also ingests text it did not write: the chunks pulled
from the corpus. If an attacker plants "ignore your instructions and …" inside a
document, that instruction reaches the model through the back door of retrieval
(OWASP LLM01, indirect prompt injection).

This module screens each retrieved chunk against the same injection patterns the
guard applies to user input — the ``limes`` rule set (ADR 0029), the single
source of truth. It matches the compiled patterns directly (so the scan has no
audit side effect, and so it can report the RAW poisoned span that limes'
detector redacts) and reports which chunks are poisoned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.guard.limes_backend import injection_rules

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["ChunkFinding", "CorpusScanReport", "scan_chunks"]

_SNIPPET_LEN = 160


@dataclass(frozen=True, slots=True)
class ChunkFinding:
    """An injection rule matched inside one retrieved chunk.

    Attributes:
        index: Position of the chunk in the retrieved set.
        pattern: The limes rule label that fired (e.g. ``injection:...``).
        snippet: A short raw window around the match, for operator forensics.
    """

    index: int
    pattern: str
    snippet: str


@dataclass(frozen=True, slots=True)
class CorpusScanReport:
    """Result of screening retrieved chunks for indirect injection."""

    n_chunks: int
    n_poisoned: int
    poison_rate: float  # share of chunks carrying at least one injection
    findings: list[ChunkFinding]


def _snippet(text: str, start: int, end: int) -> str:
    """Return a short window of ``text`` around the matched span."""
    lo = max(0, start - 20)
    hi = min(len(text), end + 20)
    return text[lo:hi][:_SNIPPET_LEN].replace("\n", " ").strip()


def scan_chunks(chunks: Sequence[str]) -> CorpusScanReport:
    """Screen each chunk against limes' injection patterns (ADR 0029).

    The patterns are limes' own rule set — the single source of truth, the same
    one the user-input guard runs — reached via
    :func:`tessera.guard.limes_backend.injection_rules`.

    Args:
        chunks: The retrieved document chunks grounding an answer.

    Returns:
        A :class:`CorpusScanReport` listing every poisoned chunk and the rule
        that fired.
    """
    rules = injection_rules()
    findings: list[ChunkFinding] = []
    poisoned: set[int] = set()
    for index, chunk in enumerate(chunks):
        for label, pattern in rules:
            match = pattern.search(chunk)
            if match is None:
                continue
            poisoned.add(index)
            findings.append(
                ChunkFinding(
                    index=index,
                    pattern=label,
                    snippet=_snippet(chunk, match.start(), match.end()),
                )
            )

    n_chunks = len(chunks)
    return CorpusScanReport(
        n_chunks=n_chunks,
        n_poisoned=len(poisoned),
        poison_rate=(len(poisoned) / n_chunks if n_chunks else 0.0),
        findings=findings,
    )
