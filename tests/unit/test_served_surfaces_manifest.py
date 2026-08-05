"""The served-surfaces manifest is checked against the Dockerfiles and compose files (ADR 0051).

A manifest nobody verifies is a declaration, and this repository does not take declarations for
facts. ``served-surfaces.yaml`` claims which paths are baked into an image and which are mounted
from the working tree; if that claim drifts from what the Dockerfiles copy and the compose files
mount, ``make served-check`` keeps answering confidently with the wrong classification — a
witness asking the neighbourhood instead of the thing (ADR 0026).

So these tests read the build files themselves:

* every ``COPY`` in a Dockerfile lands under a path the manifest calls ``baked``;
* every repo-relative bind mount in a compose file is a path the manifest calls ``mounted``;
* nothing claimed ``mounted`` is unmounted, and nothing claimed ``absent`` is either copied or
  mounted.

Plus the pure verdict logic, driven without a network or a git repo.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

import pytest

_REPO: Final = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from served_check import (  # noqa: E402 — after the sys.path insert, by construction
    EXIT_BLIND,
    EXIT_OK,
    EXIT_STALE,
    Surface,
    classify,
    load_surfaces,
    verdict,
)

_DOCKERFILES: Final = (
    _REPO / "infra" / "docker" / "Dockerfile.agent",
    _REPO / "infra" / "docker" / "Dockerfile.frontend",
)
_COMPOSE_FILES: Final = tuple(sorted(_REPO.glob("docker-compose*.yml")))

#: `COPY --from=... /opt/venv /opt/venv` copies between STAGES, not from the repo — the source is
#: a path inside a previous image, so it is not a repo surface at all.
_STAGE_COPY = re.compile(r"^COPY\s+--from=")

#: A compose bind mount whose source is inside the repo: `./x/y:/container/path[:ro]`.
_REPO_BIND = re.compile(r"^\s*-\s+\./(?P<source>[^:]+):")


def _surfaces() -> list[Surface]:
    return load_surfaces()


def _medium_of(path: str, surfaces: list[Surface]) -> str:
    """The one medium this path classifies as — the same call served-check makes."""
    return next(medium for medium, paths in classify([path], surfaces).items() if paths)


def _copy_sources() -> set[str]:
    """Every repo path the Dockerfiles bake, as written in their ``COPY`` lines."""
    sources: set[str] = set()
    for dockerfile in _DOCKERFILES:
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith("COPY ") or _STAGE_COPY.match(stripped):
                continue
            # `COPY a b ./dest` — every token but the command and the destination is a source.
            tokens = stripped.split()[1:-1]
            sources.update(token for token in tokens if not token.startswith("--"))
    return sources


def _bind_sources() -> set[str]:
    """Every repo-relative bind-mount source across the compose files."""
    sources: set[str] = set()
    for compose in _COMPOSE_FILES:
        for line in compose.read_text(encoding="utf-8").splitlines():
            match = _REPO_BIND.match(line)
            if match:
                sources.add(match.group("source"))
    return sources


# ── the detectors, tested before they are trusted ────────────────────────────────────────────


def test_the_dockerfile_reader_finds_the_copies_we_know_exist() -> None:
    """If this regresses to an empty set, every "baked" assertion below passes over a hole."""
    sources = _copy_sources()
    assert {"src", "eval"} <= sources, sources


def test_the_compose_reader_finds_the_mounts_we_know_exist() -> None:
    sources = _bind_sources()
    assert "eval/reports" in sources, sources


# ── the manifest against the build files ─────────────────────────────────────────────────────


def test_every_baked_copy_is_declared_baked() -> None:
    """A path an image copies must not be described as mounted or absent.

    This is the assertion that would have caught the class: add `COPY config ./config` to the
    Dockerfile without touching the manifest, and served-check would classify every change under
    `config/` as harmless — reporting "no rebuild needed" about baked code.
    """
    surfaces = _surfaces()
    misdeclared = {}
    for source in _copy_sources():
        # Sources are written repo-relative without a trailing slash; the manifest uses `src/`.
        medium = _medium_of(source.rstrip("/") + "/", surfaces)
        if medium != "baked":
            misdeclared[source] = medium
    assert misdeclared == {}, (
        f"these paths are COPYed into an image but the manifest calls them {misdeclared} — "
        "served-check would then tell an operator a rebuild is unnecessary for baked code."
    )


def test_every_repo_bind_mount_is_declared_mounted() -> None:
    """A path compose mounts moves without a rebuild; calling it baked inverts the advice."""
    surfaces = _surfaces()
    misdeclared = {}
    for source in _bind_sources():
        medium = _medium_of(source.rstrip("/") + "/", surfaces)
        if medium != "mounted":
            misdeclared[source] = medium
    assert misdeclared == {}, (
        f"these paths are bind-mounted from the working tree but the manifest calls them "
        f"{misdeclared}. A mounted path is live WITHOUT a rebuild — and cannot be fixed BY one."
    )


def test_nothing_declared_mounted_is_actually_unmounted() -> None:
    """A `mounted` entry for a path no compose file mounts is a rule policing nothing."""
    binds = _bind_sources()
    orphans = [
        surface.path
        for surface in _surfaces()
        if surface.medium == "mounted"
        and not any(bind.rstrip("/").startswith(surface.path.rstrip("/")) for bind in binds)
    ]
    assert orphans == [], orphans


def test_every_surface_states_why() -> None:
    """The reason is the point: a path classified with no argument cannot be reviewed."""
    silent = [surface.path for surface in _surfaces() if not surface.why]
    assert silent == [], silent


# ── classification ───────────────────────────────────────────────────────────────────────────


def test_the_longest_prefix_wins_so_reports_beat_eval() -> None:
    """`eval/reports/` is mounted INSIDE `eval/`, which is baked. The specific one must win.

    This exact pair is the chimera that put the deployed cockpit into `CannotSay`: fresh reports
    mounted live, the grader that scores them frozen in the image.
    """
    grouped = classify(
        ["eval/reports/latest.json", "eval/baselines/null-control.json"], _surfaces()
    )
    assert grouped["mounted"] == ["eval/reports/latest.json"]
    assert grouped["baked"] == ["eval/baselines/null-control.json"]


def test_an_unknown_path_is_assumed_baked() -> None:
    """The safe default. "I do not recognise this" must never resolve to "it does not matter"."""
    grouped = classify(["some/brand/new/thing.py"], _surfaces())
    assert grouped["baked"] == ["some/brand/new/thing.py"]


# ── the verdict, pure ────────────────────────────────────────────────────────────────────────

_SURFACES: Final = [
    Surface(path="src/", medium="baked", why="code"),
    Surface(path="eval/reports/", medium="mounted", why="reports"),
    Surface(path="docs/", medium="absent", why="docs"),
]


def test_a_stack_that_cannot_be_reached_is_blind_never_ok() -> None:
    result = verdict(served_sha=None, head_sha="aaaaaaaa", changed=[], surfaces=_SURFACES)
    assert result.exit_code == EXIT_BLIND


@pytest.mark.parametrize("sha", ["dev", "", "unknown", "unverified:abc12345"])
def test_a_stack_that_cannot_name_its_commit_is_blind(sha: str) -> None:
    result = verdict(served_sha=sha, head_sha="aaaaaaaa", changed=[], surfaces=_SURFACES)
    assert result.exit_code == EXIT_BLIND


def test_a_dirty_build_stamp_cannot_be_diffed() -> None:
    """`-dirty` means the image holds a working tree, not a commit — there is nothing to compare."""
    result = verdict(
        served_sha="abc12345-dirty", head_sha="abc12345", changed=[], surfaces=_SURFACES
    )
    assert result.exit_code == EXIT_BLIND


def test_a_pair_that_disagrees_with_itself_refuses() -> None:
    result = verdict(
        served_sha="mixed:aaaaaaaa/bbbbbbbb", head_sha="aaaaaaaa", changed=[], surfaces=_SURFACES
    )
    assert result.exit_code == EXIT_STALE


def test_the_same_commit_matches() -> None:
    result = verdict(served_sha="abc12345", head_sha="abc12345", changed=[], surfaces=_SURFACES)
    assert result.exit_code == EXIT_OK
    assert "MATCH" in result.headline


def test_changed_baked_code_refuses() -> None:
    result = verdict(
        served_sha="abc12345",
        head_sha="def67890",
        changed=["src/tessera/observability/turn_evidence.py"],
        surfaces=_SURFACES,
    )
    assert result.exit_code == EXIT_STALE
    assert "STALE" in result.headline


def test_changed_mounted_data_under_older_code_refuses_as_a_chimera() -> None:
    """The failure this whole file exists for: new data, old code, no error anywhere."""
    result = verdict(
        served_sha="abc12345",
        head_sha="def67890",
        changed=["eval/reports/latest.json", "src/tessera/eval_grader.py"],
        surfaces=_SURFACES,
    )
    assert result.exit_code == EXIT_STALE
    assert "CHIMERA" in result.headline


def test_documentation_only_drift_is_not_a_refusal() -> None:
    """Refusing on an ADR edit would train the operator to ignore this check."""
    result = verdict(
        served_sha="abc12345",
        head_sha="def67890",
        changed=["docs/decisions/0051-served-surfaces.md"],
        surfaces=_SURFACES,
    )
    assert result.exit_code == EXIT_OK


def test_a_commit_the_repo_does_not_contain_is_blind() -> None:
    result = verdict(served_sha="abc12345", head_sha="def67890", changed=None, surfaces=_SURFACES)
    assert result.exit_code == EXIT_BLIND


def test_uncommitted_changes_to_served_paths_are_flagged_not_swallowed() -> None:
    """A green verdict computed over a tree with uncommitted served code is only half a verdict."""
    result = verdict(
        served_sha="abc12345",
        head_sha="abc12345",
        changed=[],
        surfaces=_SURFACES,
        dirty_paths=["src/tessera/api/routes/chat.py"],
    )
    assert result.exit_code == EXIT_OK
    assert any("uncommitted" in note for note in result.notes)
