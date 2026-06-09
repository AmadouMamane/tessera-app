"""Poisoned-corpus / indirect-injection-via-RAG detection (ADR 0010, idea #52).

The classic prompt-injection guard screens what the *user* types. But a
retrieval-augmented agent also ingests text it did not write: the chunks pulled
from the corpus. If an attacker plants "ignore your instructions and …" inside a
document, that instruction reaches the model through the back door of retrieval
(OWASP LLM01, indirect prompt injection).

This module screens each retrieved chunk against the same injection deny-patterns
the guard applies to user input — matching the patterns directly so the scan has
no audit side effect — and reports which chunks are poisoned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.guard.decisions import load_policy

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.guard.decisions import Policy

__all__ = ["ChunkFinding", "CorpusScanReport", "scan_chunks"]

_SNIPPET_LEN = 160


@dataclass(frozen=True, slots=True)
class ChunkFinding:
    """An injection pattern matched inside one retrieved chunk."""

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


def scan_chunks(chunks: Sequence[str], *, policy: Policy | None = None) -> CorpusScanReport:
    """Screen each chunk against the guard's injection deny-patterns.

    Args:
        chunks: The retrieved document chunks grounding an answer.
        policy: The guard policy to read patterns from; loaded if omitted.

    Returns:
        A :class:`CorpusScanReport` listing every poisoned chunk and pattern.
    """
    active_policy = policy or load_policy()
    findings: list[ChunkFinding] = []
    poisoned: set[int] = set()
    for index, chunk in enumerate(chunks):
        for pattern in active_policy.prompt_injection_deny:
            match = pattern.search(chunk)
            if match is None:
                continue
            poisoned.add(index)
            findings.append(
                ChunkFinding(
                    index=index,
                    pattern=pattern.pattern,
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
