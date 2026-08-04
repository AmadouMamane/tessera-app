"""ADR 0050 — hybrid search retrieves twice, and each witness interrogates the thing.

Until 2026-08-04 this repository's "hybrid retrieval store (BM25 + vector)" had exactly one
retriever. The lexical signal was a Python token-overlap score applied to the vector
candidates *after* the fact, so it could reorder them and nothing else: a chunk pgvector did
not return was unreachable, however literally it matched the query.

The witnesses here refuse to be satisfied by the shape of the code:

* the fusion is asked whether a **lexical-only** document actually comes back — the property
  the previous implementation could not have had;
* the search is asked which **queries it issues**, not whether a helper exists;
* the DDL is asked what it **emits** — a GIN index, and one text-search configuration per
  language — because a generated column that analysed three languages as one would be an
  index that works properly for at most one of them;
* the missing-index path is asked whether it **says so**, since a hybrid search that silently
  becomes a dense search is the exact failure this repository keeps finding.

What none of them can see, stated: no Postgres runs here, so nothing below proves the SQL is
valid or that the index is used. ``tests/integration/test_lexical_arm_recovers.py`` is what
asks the database.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest

from tessera.retrieval import hybrid_search, store
from tessera.retrieval.reranking import fuse
from tessera.retrieval.store import LexicalHit, VectorHit
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence


def _vec(source: str, score: float, text: str = "texte") -> VectorHit:
    return VectorHit(
        source=source,
        chunk_id=f"{source}-c1",
        language=LanguageCode.FR,
        text=text,
        score=score,
        metadata={},
    )


def _lex(source: str, rank: float, cosine: float = 0.4, text: str = "texte") -> LexicalHit:
    return LexicalHit(
        source=source,
        chunk_id=f"{source}-c1",
        language=LanguageCode.FR,
        text=text,
        score=cosine,
        metadata={},
        lexical_rank=rank,
    )


# --------------------------------------------------------------------------- #
# The fusion — a document the dense arm never returned can win
# --------------------------------------------------------------------------- #


class TestFusionRecoversWhatTheDenseArmMissed:
    def test_a_lexical_only_document_is_returned(self) -> None:
        dense = [_vec("a", 0.90), _vec("b", 0.85)]
        lexical = [_lex("z", 0.42)]  # never in the dense list
        fused = fuse(dense, lexical, top_k=3)
        sources = [item.source for item in fused]
        assert "z" in sources, (
            "the lexical arm returned a document and fusion dropped it — this is the whole "
            f"property the change exists for: {sources}"
        )
        recovered = next(item for item in fused if item.source == "z")
        assert recovered.found_by == "lexical"

    def test_found_by_names_which_arm_saw_each_document(self) -> None:
        fused = {
            item.source: item.found_by
            for item in fuse([_vec("a", 0.9), _vec("b", 0.8)], [_lex("b", 0.5), _lex("z", 0.4)])
        }
        assert fused == {"a": "vector", "b": "both", "z": "lexical"}

    def test_first_in_both_lists_scores_one(self) -> None:
        [top] = fuse([_vec("a", 0.9)], [_lex("a", 0.5)])
        assert top.fused_score == pytest.approx(1.0)

    def test_first_in_one_list_only_scores_half(self) -> None:
        fused = fuse([_vec("a", 0.9)], [_lex("z", 0.5)])
        by_source = {item.source: item.fused_score for item in fused}
        assert by_source["a"] == pytest.approx(0.5)
        assert by_source["z"] == pytest.approx(0.5)

    def test_a_vector_only_document_has_a_measured_zero_lexical_rank(self) -> None:
        """0.0 is what ``ts_rank_cd`` returns for a document that matches no lexeme."""
        [only] = fuse([_vec("a", 0.9)], [])
        assert only.lexical_rank == 0.0
        assert only.vector_score == 0.9

    def test_a_lexical_only_document_carries_its_real_cosine(self) -> None:
        """Not an invented dense score: the lexical query computed it on the same row."""
        [only] = fuse([], [_lex("z", 0.5, cosine=0.31)])
        assert only.vector_score == pytest.approx(0.31)

    def test_both_lists_empty_is_empty(self) -> None:
        assert fuse([], []) == []

    def test_the_order_is_deterministic_under_ties(self) -> None:
        dense = [_vec("b", 0.7), _vec("a", 0.7)]
        first = [item.source for item in fuse(dense, [])]
        second = [item.source for item in fuse(list(reversed(dense)), [])]
        assert first == second, "equal RRF sums must not resolve to a coin flip between runs"


# --------------------------------------------------------------------------- #
# The search — which queries does it actually issue?
# --------------------------------------------------------------------------- #


class _ArmRecorder:
    """Captures what each arm was asked, and answers with fixtures."""

    def __init__(
        self,
        *,
        dense: Sequence[VectorHit] = (),
        lexical: Sequence[LexicalHit] = (),
        lexical_raises: bool = False,
    ) -> None:
        self.dense_calls: list[dict[str, Any]] = []
        self.lexical_calls: list[dict[str, Any]] = []
        self._dense = list(dense)
        self._lexical = list(lexical)
        self._raises = lexical_raises

    async def knn_search(self, **kwargs: Any) -> list[VectorHit]:
        self.dense_calls.append(kwargs)
        return self._dense

    async def lexical_search(self, **kwargs: Any) -> list[LexicalHit]:
        self.lexical_calls.append(kwargs)
        if self._raises:
            raise store.LexicalIndexUnavailableError("no such column: text_search")
        return self._lexical


def _wire(monkeypatch: pytest.MonkeyPatch, recorder: _ArmRecorder) -> None:
    async def _embed(_texts: list[str]) -> list[list[float]]:
        return [[0.5, 0.5]]

    async def _record(_categories: list[str]) -> None:
        return None

    monkeypatch.setattr(hybrid_search.embeddings, "embed", _embed)
    monkeypatch.setattr(hybrid_search.store, "knn_search", recorder.knn_search)
    monkeypatch.setattr(hybrid_search.store, "lexical_search", recorder.lexical_search)
    monkeypatch.setattr(hybrid_search.citations, "record_retrieval_query", _record)
    monkeypatch.setattr(hybrid_search, "_lexical_arm_warned", False)


class TestTheSearchAsksBothArms:
    async def test_it_issues_a_lexical_query_at_the_same_depth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _ArmRecorder(dense=[_vec("a", 0.9)], lexical=[_lex("z", 0.5)])
        _wire(monkeypatch, recorder)
        await hybrid_search.search(
            query="référence AUR-2024-118", language=LanguageCode.FR, corpus="credit_aurore"
        )
        assert len(recorder.lexical_calls) == 1, (
            "no lexical query was issued — the search is dense-only, which is exactly the "
            "state ADR 0050 exists to end"
        )
        [dense_call] = recorder.dense_calls
        [lexical_call] = recorder.lexical_calls
        assert lexical_call["top_k"] == dense_call["top_k"]
        assert lexical_call["query"] == "référence AUR-2024-118"  # the raw text, not the vector
        assert lexical_call["corpus"] == "credit_aurore"
        assert lexical_call["language"] is LanguageCode.FR

    async def test_a_lexically_recovered_document_reaches_the_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _ArmRecorder(dense=[_vec("a", 0.9)], lexical=[_lex("z", 0.5)])
        _wire(monkeypatch, recorder)
        docs = await hybrid_search.search(
            query="AUR-2024-118", language=LanguageCode.FR, corpus="credit_aurore", top_k=4
        )
        assert "z" in [doc.source for doc in docs]

    async def test_an_empty_dense_arm_still_answers_from_the_lexical_arm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The old code returned [] the moment kNN was empty, whatever else existed."""
        recorder = _ArmRecorder(dense=[], lexical=[_lex("z", 0.5)])
        _wire(monkeypatch, recorder)
        docs = await hybrid_search.search(
            query="AUR-2024-118", language=LanguageCode.FR, corpus="credit_aurore"
        )
        assert [doc.source for doc in docs] == ["z"]

    async def test_rerank_false_asks_no_lexical_query_at_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ADR 0035's knob means 'the dense retriever, plain' — ADR 0050 widens, not changes."""
        recorder = _ArmRecorder(dense=[_vec("a", 0.9), _vec("b", 0.8)], lexical=[_lex("z", 0.5)])
        _wire(monkeypatch, recorder)
        docs = await hybrid_search.search(
            query="taux livret",
            language=LanguageCode.FR,
            corpus="credit_aurore",
            top_k=2,
            rerank=False,
        )
        assert recorder.lexical_calls == []
        assert [doc.source for doc in docs] == ["a", "b"]
        assert recorder.dense_calls[0]["top_k"] == 2  # no over-fetch either


class TestAMissingLexicalIndexDegradesOutLoud:
    async def test_it_falls_back_and_names_the_reason_on_stderr(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        recorder = _ArmRecorder(
            dense=[_vec("a", 0.9, text="taux immobilier"), _vec("b", 0.95, text="autre sujet")],
            lexical_raises=True,
        )
        _wire(monkeypatch, recorder)
        docs = await hybrid_search.search(
            query="taux immobilier", language=LanguageCode.FR, corpus="credit_aurore", top_k=2
        )
        assert [doc.source for doc in docs] == ["a", "b"], (
            "the fallback must be the historical in-candidate reranker — 'a' wins on lexical "
            "overlap despite 'b' having the better cosine"
        )
        assert "no lexical index" in capsys.readouterr().err

    async def test_it_never_raises_the_missing_index_at_the_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _ArmRecorder(dense=[_vec("a", 0.9)], lexical_raises=True)
        _wire(monkeypatch, recorder)
        assert await hybrid_search.search(
            query="taux", language=LanguageCode.FR, corpus="credit_aurore"
        )


# --------------------------------------------------------------------------- #
# The DDL and the queries — what does this code actually send to PostgreSQL?
# --------------------------------------------------------------------------- #


class _SQLRecorder:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self.statements: list[str] = []
        self.params: list[Any] = []
        self._rows = rows or []

    def cursor(self, **_kwargs: Any) -> _SQLRecorder:
        return self

    async def execute(self, statement: Any, params: Any = None) -> None:
        self.statements.append(str(statement))
        self.params.append(params)

    async def fetchall(self) -> list[Any]:
        return self._rows

    async def fetchone(self) -> Any:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> _SQLRecorder:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


def _capture_sql(monkeypatch: pytest.MonkeyPatch, recorder: _SQLRecorder) -> None:
    @asynccontextmanager
    async def _fake_connection() -> AsyncIterator[_SQLRecorder]:
        yield recorder

    monkeypatch.setattr(store, "_connection", _fake_connection)


class TestTheSchemaBuildsALexicalIndex:
    async def test_it_creates_a_gin_index_on_the_generated_column(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _SQLRecorder()
        _capture_sql(monkeypatch, recorder)
        await store.ensure_schema()
        emitted = " ".join(recorder.statements).lower()
        assert "using gin (text_search)" in emitted, (
            "no GIN index on the tsvector column: the lexical query would sequentially scan, "
            f"and 'hybrid' would be a promise the schema does not keep. Emitted: {emitted}"
        )
        assert "generated always as" in emitted

    async def test_every_language_gets_its_own_text_search_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _SQLRecorder()
        _capture_sql(monkeypatch, recorder)
        await store.ensure_schema()
        emitted = " ".join(recorder.statements)
        for language, config in store.TEXT_SEARCH_CONFIG.items():
            assert f"WHEN '{language.value}' THEN to_tsvector('{config}'" in emitted, (
                f"{language.value} is not analysed with '{config}': one shared configuration "
                "stems at most one of three languages correctly"
            )

    def test_the_configuration_map_covers_every_supported_language(self) -> None:
        assert set(store.TEXT_SEARCH_CONFIG) == set(LanguageCode)


class TestTheQueryIsADisjunction:
    """Measured 2026-08-04: with AND semantics the lexical arm matched 0 of 348 searches."""

    def test_a_sentence_becomes_an_or_of_its_terms(self) -> None:
        built = store._or_tsquery("quel est le taux du prêt immobilier")
        assert built == "quel | est | le | taux | du | prêt | immobilier"
        assert "&" not in built, (
            "AND semantics demands that one chunk contain every term of the question — which "
            "is why the arm was silent on every natural-language query it was ever given"
        )

    def test_tsquery_operators_cannot_survive_a_user_query(self) -> None:
        """The value is bound; this guards the little language *inside* the bound value."""
        built = store._or_tsquery("solde & !compte | (courant):* 'x'")
        assert built == "solde | compte | courant | x"

    def test_a_reference_number_stays_one_term(self) -> None:
        """Split into 'aur | 2024 | 118' it also matches AUR-2024-999 — measured, see ADR 0050."""
        assert store._or_tsquery("la référence AUR-2024-118") == "la | référence | AUR-2024-118"

    def test_a_stray_hyphen_never_becomes_a_term(self) -> None:
        """A bare '-' would reach to_tsquery as an operand it cannot parse."""
        assert store._or_tsquery("solde - frais -- total") == "solde | frais | total"

    def test_a_query_with_no_usable_term_builds_nothing(self) -> None:
        assert store._or_tsquery("   ") == ""
        assert store._or_tsquery("... !!! ???") == ""

    def test_a_pathological_query_is_capped(self) -> None:
        built = store._or_tsquery(" ".join(f"mot{i}" for i in range(500)))
        assert built.count("|") == store._MAX_QUERY_TERMS - 1


class TestTheLexicalQuery:
    async def test_one_language_asks_one_branch_with_that_language_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorder = _SQLRecorder()
        _capture_sql(monkeypatch, recorder)
        await store.lexical_search(
            query="AUR-2024-118",
            query_embedding=[0.1, 0.2],
            corpus="credit_aurore",
            language=LanguageCode.DE,
            top_k=5,
        )
        [statement] = recorder.statements
        assert statement.count("to_tsquery") == 1
        assert "UNION ALL" not in statement
        assert "german" in (recorder.params[0] or [])

    async def test_all_languages_ask_one_branch_each(self, monkeypatch: pytest.MonkeyPatch) -> None:
        recorder = _SQLRecorder()
        _capture_sql(monkeypatch, recorder)
        await store.lexical_search(
            query="DORA",
            query_embedding=[0.1, 0.2],
            corpus="regulations",
            language=None,
            top_k=5,
        )
        [statement] = recorder.statements
        assert statement.count("to_tsquery") == len(store.TEXT_SEARCH_CONFIG)
        params = recorder.params[0] or []
        for config in store.TEXT_SEARCH_CONFIG.values():
            assert config in params, f"the {config} partition is never queried"

    async def test_the_query_text_is_bound_never_interpolated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A user query reaching the SQL text would be an injection site, not a search."""
        recorder = _SQLRecorder()
        _capture_sql(monkeypatch, recorder)
        await store.lexical_search(
            query="'; DROP TABLE documents; --",
            query_embedding=[0.1],
            corpus="credit_aurore",
            language=LanguageCode.FR,
            top_k=5,
        )
        statement = recorder.statements[0]
        assert "DROP TABLE" not in statement
        assert "DROP | TABLE | documents" in (recorder.params[0] or [])

    async def test_a_blank_query_asks_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        recorder = _SQLRecorder()
        _capture_sql(monkeypatch, recorder)
        assert (
            await store.lexical_search(
                query="   ",
                query_embedding=[0.1],
                corpus="credit_aurore",
                language=LanguageCode.FR,
            )
            == []
        )
        assert recorder.statements == []
