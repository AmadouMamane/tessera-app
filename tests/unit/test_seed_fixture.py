"""The committed e2e seed must not silently fall behind the corpus it was built from.

CI restores ``fixtures/e2e/pgvector-seed.sql.gz`` instead of ingesting, which is what
keeps the workflow free of an embedding model and therefore of any secret. The price of
that trade is a committed artifact that no longer regenerates itself: edit a corpus JSON,
and the fixture goes on serving yesterday's chunks while every e2e spec stays green.

These tests are that guard. They re-derive each recorded fact rather than trust it — the
corpus hash from the sources, the row count and vector width from inside the dump — so a
hand-edited manifest fails exactly as loudly as a stale one.

No database, no network: a unit test that reads two files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.seed_fixture import build_manifest, corpus_sha256, read_dump_facts

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIR = _ROOT / "fixtures" / "e2e"
_DUMP = _FIXTURE_DIR / "pgvector-seed.sql.gz"
_MANIFEST = _FIXTURE_DIR / "manifest.json"

_REGENERATE = "run `make seed-fixture` to regenerate the e2e seed"


@pytest.fixture(scope="module")
def manifest() -> dict[str, object]:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_the_fixture_and_its_manifest_are_committed() -> None:
    """CI restores these two files. A missing one is a red e2e job nobody can debug."""
    assert _DUMP.is_file(), f"{_DUMP} is missing — {_REGENERATE}"
    assert _MANIFEST.is_file(), f"{_MANIFEST} is missing — {_REGENERATE}"


def test_the_corpus_has_not_moved_since_the_seed_was_built(manifest: dict[str, object]) -> None:
    """The staleness guard proper: corpus sources in, fixture out — hash them together.

    A corpus edit that skips the re-seed leaves CI asserting against chunks that no longer
    exist in the repository. The suite would stay green and mean nothing.
    """
    assert (
        manifest["corpus_sha256"] == corpus_sha256()
    ), f"the corpus sources changed after the fixture was built — {_REGENERATE}"


def test_the_corpus_file_set_has_not_moved(manifest: dict[str, object]) -> None:
    """A new corpus file is a corpus change even before a single byte of it is embedded."""
    on_disk = sorted(p.name for p in (_ROOT / "src" / "tessera" / "corpus" / "data").glob("*.json"))
    assert manifest["corpus_files"] == on_disk, f"corpus file set changed — {_REGENERATE}"


def test_the_manifest_describes_the_dump_that_is_actually_committed(
    manifest: dict[str, object],
) -> None:
    """Row count and vector width are read back out of the dump, never taken on trust.

    This is what makes a hand-edited manifest fail: the numbers have exactly one source,
    and it is the artifact CI will restore.
    """
    facts = read_dump_facts(_DUMP)
    assert manifest["rows"] == facts["rows"], "the manifest's row count is not the dump's"
    assert manifest["embedding_dimension"] == facts["embedding_dimension"]


def test_the_seed_carries_the_corpus_e2e_asserts_on(manifest: dict[str, object]) -> None:
    """`sources.spec.ts` counts 17 catalogue rows: 15 corpus categories + memory + transcript.

    An empty `documents` table is exactly the failure this whole fixture exists to remove
    (19 red specs on a bare runner, none of them spec debt). Pin the substance, not just
    the plumbing: a dump that restores cleanly but carries no rows would pass every other
    test in this module.
    """
    rows = manifest["rows"]
    assert isinstance(rows, dict)
    documents = rows.get("tessera_local.documents")
    assert documents, "the seed carries no corpus rows — the e2e catalogue would read empty"
    assert documents > 200, f"only {documents} corpus chunks: the seed looks truncated"


def test_the_manifest_is_exactly_what_the_generator_would_write(
    manifest: dict[str, object],
) -> None:
    """The generator is the single definition of the manifest — including its own comment."""
    assert (
        manifest == build_manifest()
    ), f"the manifest is not the generator's output — {_REGENERATE}"
