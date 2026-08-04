"""pgvector-backed document store.

The store owns one process-wide async connection pool, the schema migration
required to host pgvector columns of the active embedding dimension, and the
two retrieval queries used by ingestion and search: :func:`knn_search` (dense,
HNSW over pgvector) and :func:`lexical_search` (sparse, GIN over a generated
``tsvector`` analysed per language). They are siblings on purpose — each one
*retrieves*, independently, and fusion happens above them.

The schema is created idempotently on the first call to :func:`ensure_schema`
and depends on ``pgvector`` being installed in the target database — see
``infra/terraform/postgres.tf``.
"""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from psycopg import sql
from psycopg.errors import UndefinedColumn, UndefinedTable
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from tessera.retrieval.embeddings import embedding_dimension, embedding_model_name
from tessera.settings import LanguageCode, get_settings
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from psycopg import AsyncConnection

__all__ = [
    "TEXT_SEARCH_CONFIG",
    "DocumentRecord",
    "LexicalHit",
    "LexicalIndexUnavailableError",
    "ReembeddedChunk",
    "UnfingerprintedChunk",
    "VectorHit",
    "corpus_fingerprints",
    "ensure_schema",
    "get_pool",
    "insert_documents",
    "knn_search",
    "lexical_search",
    "load_unfingerprinted_chunks",
    "replace_unfingerprinted_embeddings",
]


#: The PostgreSQL text-search configuration each stored language is analysed with.
#:
#: This mapping is the whole reason the lexical arm is not one shared ``simple`` config:
#: each language gets its own snowball stemmer and stop-word list. Measured on PostgreSQL 16
#: — ``german`` stems *Bedingungen* to ``beding``, so a query for *Bedingung* matches, while
#: ``english`` leaves it as ``bedingungen`` and matches nothing; ``french`` stems *immobiliers*
#: to ``immobili`` and *Crédit* to ``cred``; ``simple`` stems nothing at all. A trilingual
#: corpus analysed with one config is a lexical index that works for at most one language.
#:
#: What this is NOT: decompounding. PostgreSQL's ``german`` is a snowball stemmer, not an
#: ispell dictionary — *Immobilienkredite* becomes ``immobilienkredit`` under ``german`` and
#: under ``english`` alike, because both merely strip a trailing ``e``. Claiming German
#: compound splitting here would be claiming a capability this schema does not have.
#:
#: Frozen at three entries by construction: :class:`LanguageCode` is the frozen project
#: convention, and a language with no entry here would be silently analysed as English.
TEXT_SEARCH_CONFIG: dict[LanguageCode, str] = {
    LanguageCode.FR: "french",
    LanguageCode.DE: "german",
    LanguageCode.EN: "english",
}

#: Name of the generated ``tsvector`` column and of its GIN index suffix.
_TEXT_SEARCH_COLUMN = "text_search"

#: Alphanumeric runs, optionally joined by single hyphens — the tokens handed to
#: ``to_tsquery`` as a disjunction.
#:
#: **The hyphens are load-bearing, and they are about precision.** PostgreSQL indexes
#: ``AUR-2024-118`` as three lexemes ``aur``, ``-2024``, ``-118`` (its parser reads the
#: hyphenated parts as signed integers). Splitting the query on ``\w+`` alone asks for
#: ``'aur' | '2024' | '118'``, which — measured — also matches ``AUR-2024-999``: a different
#: reference, returned as if it were the one asked for. Keeping the token whole makes
#: ``to_tsquery`` build the phrase ``'aur' <-> '-2024' <-> '-118'``, which matches the right
#: reference and not its neighbour. Reference numbers are the exact token class this whole
#: arm exists for, so getting them approximately right would be missing the point.
#:
#: This pattern is also the whole of the tsquery-syntax defence: it admits no ``&``, ``|``,
#: ``!``, ``:``, ``*``, ``(``, ``)``, ``<``, ``>`` or quote, and cannot produce a bare or
#: leading ``-``, so a user query cannot express an operator — let alone an unbalanced one
#: that would raise. The *value* is bound like any other; this guards the language inside it.
_QUERY_TERM = re.compile(r"\w+(?:-\w+)*", re.UNICODE)

#: Ceiling on the number of OR-ed terms. A pathological query (a pasted document) would
#: otherwise build a tsquery with thousands of branches; 64 covers every real question.
_MAX_QUERY_TERMS = 64


def _or_tsquery(query: str) -> str:
    """Turn a natural-language query into a disjunction for ``to_tsquery``.

    **Not** ``websearch_to_tsquery``, and that choice is the difference between a lexical arm
    that fires and one that never does. ``websearch_to_tsquery`` joins terms with AND: for
    *"quel est le taux du prêt immobilier Crédit Aurore"* it builds
    ``'quel' & 'taux' & 'prêt' & 'immobili' & 'cred' & 'auror'``, which demands that one chunk
    contain all six. Measured 2026-08-04 over the 174 failure-catalogue prompts against the
    live corpus: **0 matches in 348 searches.** A retriever silent on every natural-language
    query is not a retriever.

    The disjunction is what a sparse retriever is supposed to do — match on any term and let
    ``ts_rank_cd`` rank by how many, and how close. Stemming still happens inside PostgreSQL,
    per language: ``to_tsquery`` analyses each term with the configuration it is given, and a
    hyphenated term (a reference number) becomes a phrase rather than three loose tokens that
    would also match the next reference along — see :data:`_QUERY_TERM`.

    Args:
        query: The raw user query.

    Returns:
        A ``to_tsquery`` expression, or ``""`` when the query holds no usable term — in which
        case there is nothing to ask and the caller must not ask it.
    """
    terms = _QUERY_TERM.findall(query)[:_MAX_QUERY_TERMS]
    return " | ".join(terms)


class LexicalIndexUnavailableError(RuntimeError):
    """The lexical column/index this store needs is not present in the database.

    Raised — never swallowed here — so the caller decides what a missing lexical arm means.
    :mod:`tessera.retrieval.hybrid_search` degrades to the historical vector-only path and
    says so on stderr rather than quietly serving half a search.
    """


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """A document chunk ready to insert."""

    corpus: str
    source: str
    chunk_id: str
    language: LanguageCode
    text: str
    embedding: list[float]
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class VectorHit:
    """A single nearest-neighbour result."""

    source: str
    chunk_id: str
    language: LanguageCode
    text: str
    score: float
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class LexicalHit:
    """One chunk the LEXICAL index matched, carrying both signals for it.

    ``score`` is the same cosine similarity a :class:`VectorHit` carries, computed by the
    same query against the same stored embedding. That matters: a chunk the dense arm never
    returned still arrives with a **real** dense score rather than an invented one, so the
    downstream surfaces that read a cosine (citation gate, grounding) never see a number this
    layer made up.

    ``lexical_rank`` is PostgreSQL's ``ts_rank_cd`` — a cover-density rank, not BM25. It is
    only comparable within one result set, which is exactly what reciprocal-rank fusion needs.
    """

    source: str
    chunk_id: str
    language: LanguageCode
    text: str
    score: float
    metadata: dict[str, str]
    lexical_rank: float


@dataclass(frozen=True, slots=True)
class UnfingerprintedChunk:
    """One stored chunk whose original embedding space was not recorded."""

    corpus: str
    source: str
    chunk_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ReembeddedChunk:
    """Replacement vector for one exact, still-unfingerprinted stored chunk."""

    corpus: str
    source: str
    chunk_id: str
    text: str
    embedding: list[float]


_pool: AsyncConnectionPool | None = None

# Fixed key serialising per-env schema creation across concurrently-opened
# pool connections (see :func:`_isolate_environment`). Arbitrary constant; only
# its stability matters, so all bootstrappers contend on the same lock.
_SCHEMA_BOOTSTRAP_LOCK = 0x7E55E2A04154  # "TESSERA ISA" leet, fits in a signed bigint


async def _isolate_environment(conn: AsyncConnection[Any]) -> None:
    """Pin every pooled connection to this environment's schema (ADR 0014).

    Creates ``<schema>`` if missing and sets ``search_path`` to ``<schema>,
    public`` so every durable write (transcript, eval, memory, lineage, …) lands
    in the environment's namespace while pgvector's ``vector`` type and other
    shared objects still resolve from ``public``. For production the schema is
    ``public`` itself, making this a no-op that leaves the deployed stack exactly
    as it was. Runs on each new connection; ``CREATE SCHEMA IF NOT EXISTS`` is
    idempotent and cheap.
    """
    schema = get_settings().pg_schema
    async with conn.cursor() as cur:
        # ``CREATE SCHEMA IF NOT EXISTS`` still races to a duplicate-key error when
        # the pool opens several connections at once; a transaction-scoped advisory
        # lock serialises the bootstrap so the IF NOT EXISTS guard actually holds.
        await cur.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_BOOTSTRAP_LOCK,))
        await cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        await cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
    await conn.commit()


def get_pool() -> AsyncConnectionPool:
    """Return the lazily-initialised process-wide async pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            conninfo=str(settings.postgres.dsn),
            min_size=settings.postgres.pool_min_size,
            max_size=settings.postgres.pool_max_size,
            configure=_isolate_environment,
            open=False,
        )
    return _pool


@asynccontextmanager
async def _connection() -> AsyncIterator[AsyncConnection[Any]]:
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn:
        yield conn


async def ensure_schema() -> None:
    """Create the documents table and HNSW index idempotently."""
    settings = get_settings()
    table = safe_identifier(settings.postgres.vector_table)
    dim = embedding_dimension()
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id           bigserial PRIMARY KEY,
                corpus       text       NOT NULL,
                source       text       NOT NULL,
                chunk_id     text       NOT NULL,
                language     varchar(2) NOT NULL,
                text         text       NOT NULL,
                embedding    vector({dim}) NOT NULL,
                metadata     jsonb      NOT NULL DEFAULT '{{}}'::jsonb,
                inserted_at  timestamptz NOT NULL DEFAULT now(),
                UNIQUE (corpus, source, chunk_id)
            );
            """
        )
        # The embedding SPACE each row was built in, recorded at ingestion.
        #
        # Without these two columns `/observability/embedding-skew` had no corpus fingerprint
        # to compare against, so it passed the ACTIVE embedder as both sides — a comparison of
        # a thing with itself, which cannot fail. It reported `corpus_known: false` rather than
        # a clean bill, which was honest, but it measured nothing. Now it can.
        #
        # Added with IF NOT EXISTS rather than in the CREATE above: the table already exists in
        # every deployment, and rows ingested before this stay NULL — which is the truthful
        # record of "we did not write it down at the time", and is what lets the probe say
        # which part of the corpus it can and cannot vouch for.
        await cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embedding_model text;")
        await cur.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embedding_dimension integer;"
        )
        await cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {table}_embedding_hnsw
                ON {table} USING hnsw (embedding vector_cosine_ops);
            """
        )
        await cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {table}_corpus_language
                ON {table} (corpus, language);
            """
        )
        # The LEXICAL half of "hybrid search" — added 2026-08-04, and until then it did not
        # exist. `hybrid_search` embedded the query, ran kNN, and reordered those candidates
        # with a Python token-overlap score. Reordering is not retrieval: a chunk the dense
        # arm did not return was unreachable, however literally it matched. The gap mattered
        # most for what embeddings smear — reference numbers, article ids, product codes, IBAN
        # fragments — which is a large part of what a banking corpus is addressed by.
        #
        # A GENERATED column rather than a trigger: the tsvector is a pure function of two
        # columns already in the row, so it cannot drift from the text it indexes, and every
        # existing row is filled by the ALTER itself. `to_tsvector(regconfig, text)` is
        # IMMUTABLE for a literal config, and a CASE over immutable branches is immutable —
        # which is what makes the per-language analysis (see TEXT_SEARCH_CONFIG) possible in a
        # generated column at all. Verified on the deployed engine, PostgreSQL 16.
        #
        # ADD COLUMN IF NOT EXISTS, like the two fingerprint columns above: the table already
        # exists in every deployment. Unlike them, nothing is left NULL — the expression is
        # evaluated for every row at ALTER time, so the index is complete the moment it exists.
        # Both halves are module constants, never caller input — and both go through the
        # identifier gate anyway, at the point of interpolation, per :mod:`tessera.sql`: the
        # boundary check is what makes a later refactor unable to silently un-validate them.
        case_branches = " ".join(
            f"WHEN '{safe_identifier(lang.value)}' THEN "
            f"to_tsvector('{safe_identifier(config)}', text)"
            for lang, config in TEXT_SEARCH_CONFIG.items()
        )
        await cur.execute(
            f"""
            ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {_TEXT_SEARCH_COLUMN} tsvector
                GENERATED ALWAYS AS (
                    CASE language {case_branches} ELSE to_tsvector('simple', text) END
                ) STORED;
            """
        )
        await cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {table}_{_TEXT_SEARCH_COLUMN}_gin
                ON {table} USING gin ({_TEXT_SEARCH_COLUMN});
            """
        )
        await conn.commit()


async def insert_documents(records: Sequence[DocumentRecord]) -> int:
    """Bulk-insert ``records``; returns the number of rows actually inserted."""
    if not records:
        return 0
    table = safe_identifier(get_settings().postgres.vector_table)
    model = embedding_model_name()
    async with _connection() as conn, conn.cursor() as cur:
        rows = [
            (
                r.corpus,
                r.source,
                r.chunk_id,
                r.language.value,
                r.text,
                r.embedding,
                json.dumps(r.metadata),
                model,
                # The dimension comes from the VECTOR, not from the config. It is a fact about
                # the row; the model name is a claim about how the row was made. Recording the
                # config's dimension would make the two columns agree by construction and the
                # skew check would go back to comparing a thing with itself.
                len(r.embedding),
            )
            for r in records
        ]
        await cur.executemany(
            f"""
            INSERT INTO {table}
                (corpus, source, chunk_id, language, text, embedding, metadata,
                 embedding_model, embedding_dimension)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (corpus, source, chunk_id) DO NOTHING;
            """,
            rows,
        )
        await conn.commit()
        return cur.rowcount or 0


async def knn_search(
    *,
    query_embedding: list[float],
    corpus: str,
    language: LanguageCode | None,
    top_k: int = 10,
) -> list[VectorHit]:
    """Return the ``top_k`` nearest chunks in ``corpus``.

    When ``language`` is ``None`` the search spans all languages — used by
    the regulation lookup where EU texts are stored in their source language
    regardless of the active conversation language.
    """
    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if language is not None:
            await cur.execute(
                f"""
                    SELECT source, chunk_id, language, text, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM {table}
                    WHERE corpus = %s AND language = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                (query_embedding, corpus, language.value, query_embedding, top_k),
            )
        else:
            await cur.execute(
                f"""
                    SELECT source, chunk_id, language, text, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM {table}
                    WHERE corpus = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                (query_embedding, corpus, query_embedding, top_k),
            )
        rows = await cur.fetchall()
    return [
        VectorHit(
            source=str(row["source"]),
            chunk_id=str(row["chunk_id"]),
            language=LanguageCode(row["language"]),
            text=str(row["text"]),
            metadata=dict(row.get("metadata") or {}),
            score=float(row["score"]),
        )
        for row in rows
    ]


async def lexical_search(
    *,
    query: str,
    query_embedding: list[float],
    corpus: str,
    language: LanguageCode | None,
    top_k: int = 10,
) -> list[LexicalHit]:
    """Return the ``top_k`` best full-text matches for ``query`` in ``corpus``.

    This is the arm that **retrieves**, as opposed to the arm that reorders. It queries the
    GIN index built by :func:`ensure_schema` with a disjunction of the query's own terms — see
    :func:`_or_tsquery` for why a disjunction and not ``websearch_to_tsquery``.

    When ``language`` is ``None`` the search spans all languages, and each language partition
    is queried with **its own** text-search configuration (see :data:`TEXT_SEARCH_CONFIG`) as
    a separate branch of one ``UNION ALL``. One config for three languages would silently
    stem two of them wrong; one round trip per language would pay three latencies on the hot
    path. Each branch is index-friendly on its own because its config is a literal.

    ``query_embedding`` is not used to *find* anything here — it is projected onto the matched
    rows so every hit carries its true cosine. That is what lets fusion return a
    lexically-recovered chunk without inventing a dense score for it.

    Args:
        query: The raw user query, handed to ``websearch_to_tsquery`` as typed.
        query_embedding: The query vector, used only to score the matched rows.
        corpus: The corpus to search.
        language: One language, or ``None`` to span all of them.
        top_k: Maximum rows returned across all branches.

    Returns:
        Hits ordered by lexical rank, best first; empty when nothing matches — which is an
        ordinary outcome for a query made entirely of stop words, and which the caller must
        not confuse with a missing index (that raises instead).

    Raises:
        LexicalIndexUnavailableError: The generated column or its index is missing, i.e.
            :func:`ensure_schema` has not run against this database since 2026-08-04.
    """
    tsquery = _or_tsquery(query)
    if not tsquery:
        return []
    table = safe_identifier(get_settings().postgres.vector_table)
    languages = [language] if language is not None else list(TEXT_SEARCH_CONFIG)

    branches: list[str] = []
    params: list[Any] = []
    for lang in languages:
        config = TEXT_SEARCH_CONFIG[lang]
        branches.append(
            f"""
            (SELECT source, chunk_id, language, text, metadata,
                    1 - (embedding <=> %s::vector) AS score,
                    ts_rank_cd({_TEXT_SEARCH_COLUMN}, q) AS lexical_rank
               FROM {table}, to_tsquery(%s::regconfig, %s) AS q
              WHERE corpus = %s AND language = %s AND {_TEXT_SEARCH_COLUMN} @@ q
              ORDER BY lexical_rank DESC, score DESC
              LIMIT %s)
            """  # fixed, validated identifiers; every value is bound
        )
        params.extend([query_embedding, config, tsquery, corpus, lang.value, top_k])
    params.append(top_k)

    statement = (
        f"SELECT * FROM ({' UNION ALL '.join(branches)}) AS merged "  # noqa: S608 — see above
        "ORDER BY lexical_rank DESC, score DESC LIMIT %s;"
    )

    async with _connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        try:
            await cur.execute(statement, params)
            rows = await cur.fetchall()
        except (UndefinedColumn, UndefinedTable) as exc:
            await conn.rollback()
            msg = (
                f"the lexical index is missing from {table!r}: {exc}. "
                "Run ensure_schema() against this database."
            )
            raise LexicalIndexUnavailableError(msg) from exc
    return [
        LexicalHit(
            source=str(row["source"]),
            chunk_id=str(row["chunk_id"]),
            language=LanguageCode(row["language"]),
            text=str(row["text"]),
            metadata=dict(row.get("metadata") or {}),
            score=float(row["score"]),
            lexical_rank=float(row["lexical_rank"]),
        )
        for row in rows
    ]


async def corpus_fingerprints() -> list[tuple[str | None, int | None, int]]:
    """The embedding spaces the corpus actually holds: ``[(model, dimension, rows)]``.

    This is what turns `/observability/embedding-skew` from a tautology into a measurement. It
    reads what the STORE recorded, not what the process is configured to use — the whole point
    being that those two can differ, silently, after a profile flip or a model swap.

    A ``(None, None, n)`` group is rows ingested before the fingerprint columns existed. That
    is neither a skew nor a clean bill: it is the part of the corpus the probe cannot vouch
    for, and it travels separately so the surface can say exactly that (ADR 0026 — a witness
    that cannot see reports where the blindness is).

    Returns:
        One tuple per distinct space, largest group first. Empty when the corpus is empty.
    """
    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT embedding_model, embedding_dimension, count(*)::int
              FROM {table}
             GROUP BY embedding_model, embedding_dimension
             ORDER BY count(*) DESC;
            """  # noqa: S608 — fixed, validated identifier; no caller string reaches the SQL
        )
        rows = await cur.fetchall()
    return [(r[0], r[1], int(r[2])) for r in rows]


async def load_unfingerprinted_chunks() -> list[UnfingerprintedChunk]:
    """Read the exact stored texts whose embedding provenance is incomplete.

    The repair re-embeds these texts as stored; it does not re-chunk source files or assume
    which model created the legacy vector. That keeps content and identity stable while the
    missing evidence is rebuilt.
    """
    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT corpus, source, chunk_id, text
              FROM {table}
             WHERE embedding_model IS NULL OR embedding_dimension IS NULL
             ORDER BY corpus, source, chunk_id;
            """  # noqa: S608 — fixed, validated identifier; no caller string reaches the SQL
        )
        rows = await cur.fetchall()
    return [
        UnfingerprintedChunk(
            corpus=str(row[0]),
            source=str(row[1]),
            chunk_id=str(row[2]),
            text=str(row[3]),
        )
        for row in rows
    ]


_EMBEDDING_REPAIR_LOCK = 0x7E55E2A0454D  # "TESSERA EM", serialises repair transactions


async def replace_unfingerprinted_embeddings(
    repairs: Sequence[ReembeddedChunk],
    *,
    model: str,
    dimension: int,
) -> int:
    """Atomically replace every legacy vector after staging and exact-text reconciliation.

    Retrieval keeps reading the old committed vectors while embeddings are computed. This
    function then stages all replacements in a temporary table and updates the live rows in
    one transaction. It refuses partial coverage, content drift, duplicate keys and dimension
    mismatches; no fingerprint is ever backfilled without a freshly produced vector.

    Args:
        repairs: Fresh vectors for the complete current set of unfingerprinted chunks.
        model: Active model that produced every replacement vector.
        dimension: Expected width of every replacement vector.

    Returns:
        Number of rows atomically replaced.

    Raises:
        ValueError: The replacement set is internally inconsistent.
        RuntimeError: The live target changed or cannot be reconciled exactly.
    """
    if not model.strip():
        msg = "embedding repair model must be non-empty"
        raise ValueError(msg)
    if dimension < 1:
        msg = "embedding repair dimension must be positive"
        raise ValueError(msg)
    keys = [(row.corpus, row.source, row.chunk_id) for row in repairs]
    if len(keys) != len(set(keys)):
        msg = "embedding repair contains duplicate chunk keys"
        raise ValueError(msg)
    if any(len(row.embedding) != dimension for row in repairs):
        msg = f"embedding repair contains a vector outside the declared {dimension}-d space"
        raise ValueError(msg)

    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn, conn.cursor() as cur:
        try:
            await cur.execute("SELECT pg_advisory_xact_lock(%s)", (_EMBEDDING_REPAIR_LOCK,))
            await cur.execute(
                f"""
                SELECT count(*)::int
                  FROM {table}
                 WHERE embedding_model IS NULL OR embedding_dimension IS NULL;
                """  # noqa: S608 — fixed, validated identifier
            )
            count_row = await cur.fetchone()
            current = int(count_row[0]) if count_row is not None else 0
            if current != len(repairs):
                msg = (
                    "embedding repair target changed after planning: "
                    f"planned {len(repairs)}, found {current}"
                )
                raise RuntimeError(msg)

            await cur.execute(
                f"""
                CREATE TEMP TABLE tessera_embedding_repair_stage (
                    corpus               text NOT NULL,
                    source               text NOT NULL,
                    chunk_id             text NOT NULL,
                    original_text        text NOT NULL,
                    embedding            vector({dimension}) NOT NULL,
                    embedding_model      text NOT NULL,
                    embedding_dimension  integer NOT NULL,
                    PRIMARY KEY (corpus, source, chunk_id)
                ) ON COMMIT DROP;
                """
            )
            await cur.executemany(
                """
                INSERT INTO tessera_embedding_repair_stage
                    (corpus, source, chunk_id, original_text, embedding,
                     embedding_model, embedding_dimension)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                [
                    (
                        row.corpus,
                        row.source,
                        row.chunk_id,
                        row.text,
                        row.embedding,
                        model,
                        dimension,
                    )
                    for row in repairs
                ],
            )
            await cur.execute(
                f"""
                SELECT count(*)::int
                  FROM {table} AS target
                  JOIN tessera_embedding_repair_stage AS stage
                    USING (corpus, source, chunk_id)
                 WHERE target.text = stage.original_text
                   AND (target.embedding_model IS NULL OR target.embedding_dimension IS NULL);
                """  # noqa: S608 — fixed, validated identifier
            )
            matched_row = await cur.fetchone()
            matched = int(matched_row[0]) if matched_row is not None else 0
            if matched != len(repairs):
                msg = (
                    "embedding repair staging did not reconcile with the live texts: "
                    f"planned {len(repairs)}, matched {matched}"
                )
                raise RuntimeError(msg)

            await cur.execute(
                f"""
                UPDATE {table} AS target
                   SET embedding = stage.embedding,
                       embedding_model = stage.embedding_model,
                       embedding_dimension = stage.embedding_dimension
                  FROM tessera_embedding_repair_stage AS stage
                 WHERE target.corpus = stage.corpus
                   AND target.source = stage.source
                   AND target.chunk_id = stage.chunk_id
                   AND target.text = stage.original_text
                   AND (target.embedding_model IS NULL OR target.embedding_dimension IS NULL);
                """  # noqa: S608 — fixed, validated identifier
            )
            updated = cur.rowcount or 0
            if updated != len(repairs):
                msg = f"embedding repair updated {updated} rows; expected {len(repairs)}"
                raise RuntimeError(msg)
            await conn.commit()
            return updated
        except Exception:
            await conn.rollback()
            raise
