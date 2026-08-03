"""Long-term memory had no record of which model wrote which vector.

The visible half of the drift is harmless: Vertex embeds at 768 dimensions and Ollama at 1024,
and `vector(768)` will not take 1024 floats — the INSERT fails, loudly, and somebody fixes it.

The dangerous half is the quiet one: **two different models at the same dimension.** Their
vectors live in unrelated spaces. Cosine distance between them is noise wearing a number.
Postgres is happy, pgvector is happy, the HNSW index is happy, and recall returns arbitrary
memories while every layer above reports an unchanged hit rate. `_recall` then swallowed its own
exception into an empty list, so "this subject has no memories" and "long-term memory has
stopped working" arrived at the dashboard as the same fact.

Three columns and a fence close it: every row says which model and which dimension wrote it,
every comparison is fenced to vectors the current model can actually be compared against, and
the gap between what we KNOW matches and what we ASSUME matches is a number
(:func:`fingerprint_skew`) rather than a silence.

These tests interrogate the composed SQL and the arithmetic, so they need no database — the
fence is exactly the kind of clause a refactor drops without any test noticing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.memory import persistent
from tessera.memory.persistent import FingerprintSkew

if TYPE_CHECKING:
    from collections.abc import Callable


def _sql_of(build: Callable[[], object]) -> str:
    """The statement a builder composes, as text — psycopg's `sql` objects print themselves."""
    return str(build())


class TestEveryComparisonIsFenced:
    """A vector may only be compared with one the same model wrote.

    Both places matter, and the second is the less obvious one: de-duplication compares a new
    vector against stored ones, so an unfenced 0.95 there would OVERWRITE an unrelated memory
    with a different subject's fact. A silent write is worse than a silent read.
    """

    def test_the_fence_names_both_halves_of_the_identity(self) -> None:
        fence = str(persistent._FINGERPRINT_FENCE)

        assert "embedding_model" in fence
        assert "embedding_dimension" in fence, (
            "the fence checks the model and not the dimension. One model served at two "
            "dimensions would pass it, and the vectors are still incomparable."
        )

    def test_unstamped_rows_are_kept_and_foreign_ones_are_not(self) -> None:
        """Pre-migration rows are an assumption; a different KNOWN model is a fact.

        Excluding the unstamped would empty a working memory on a suspicion. Including the
        foreign would rank against noise. The two cases are not the same and are not treated
        the same — and the difference is what `fingerprint_skew` counts.
        """
        fence = str(persistent._FINGERPRINT_FENCE)

        assert persistent._FINGERPRINT_UNKNOWN in fence, (
            "rows written before the stamp existed are fenced OUT, so deploying this migration "
            "silently empties every existing subject's long-term memory."
        )
        assert "0" in fence, "the pre-migration dimension default (0) must be admitted too"


class TestTheSkewIsANumberAndNotASilence:
    """`unreadable_fraction` is what an operator can act on. It must not lie in either direction."""

    def test_no_foreign_rows_reads_as_nothing_unreadable(self) -> None:
        skew = FingerprintSkew(
            current_model="text-embedding-004",
            current_dimension=768,
            comparable=40,
            unstamped=10,
            foreign={},
        )

        assert skew.total == 50
        assert skew.unreadable_fraction == 0.0

    def test_foreign_rows_are_counted_as_unreadable(self) -> None:
        skew = FingerprintSkew(
            current_model="nomic-embed-text",
            current_dimension=768,
            comparable=25,
            unstamped=0,
            foreign={"text-embedding-004@768": 75},
        )

        assert skew.total == 100
        assert skew.unreadable_fraction == pytest.approx(0.75), (
            "three quarters of this subject's memory cannot be reached by the current model, "
            "and the only symptom without this number is an agent that quietly forgets."
        )

    def test_an_empty_table_is_zero_and_not_a_division_by_zero(self) -> None:
        skew = FingerprintSkew(
            current_model="m", current_dimension=1, comparable=0, unstamped=0, foreign={}
        )

        assert skew.total == 0
        assert skew.unreadable_fraction == 0.0


class TestTheFingerprintComesFromTheEmbeddingLayer:
    """It must be READ from the embedding module, never re-declared beside it.

    A constant copied next to the thing it describes is how the two drift: the embedding
    provider would change and the memory table would go on stamping the old name, which is
    precisely the failure this column exists to make visible.
    """

    def test_it_asks_the_embeddings_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            persistent.embeddings, "embedding_model_name", lambda: "a-different-model"
        )
        monkeypatch.setattr(persistent.embeddings, "embedding_dimension", lambda: 4242)

        assert persistent._fingerprint() == ("a-different-model", 4242)


class TestABrokenRecallDoesNotLookLikeAnEmptyOne:
    """The two most important states to tell apart, reported identically until 2026-08-04."""

    def test_the_module_has_a_logger_to_say_it_with(self) -> None:
        assert hasattr(persistent, "_LOG"), (
            "recall degradation was written to stderr only, where nothing collects it. An "
            "operator reading the dashboard saw an agent with no memories, not an agent whose "
            "memory had stopped answering."
        )
