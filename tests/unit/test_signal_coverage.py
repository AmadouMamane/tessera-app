"""The catalogue counts are READ, and readable from where the code actually runs.

Two failures are being held off here, and they are different failures.

**The number.** "42 of the 200-signal catalogue" was two constants. The catalogue holds 202,
78 of them `active`, and 44 declare the quality page — so the header was wrong on all three of
its numbers and had been since it was written. A count nobody reads cannot go stale loudly; it
just drifts, and the screen keeps asserting it.

**The path.** The catalogue was authored at `docs/signal-catalog.yaml`, and
`infra/docker/Dockerfile.agent` copies `src`, `eval`, `README.md` and `LICENSE` — nothing else.
A route reading `docs/` passes every local test and returns nothing in production. That trap has
already been paid for once in this repo, which is why the assertion below interrogates the
SHIPPED path rather than the authored one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessera.observability.signal_coverage import (
    _CATALOGUE,
    catalogue_counts,
    compute_signal_coverage,
)

_REPO = Path(__file__).resolve().parents[2]


def test_the_catalogue_ships_inside_the_package() -> None:
    """The image copies `src` and `eval`. A catalogue outside them is absent in production."""
    relative = _CATALOGUE.resolve().relative_to(_REPO)
    assert relative.parts[0] == "src", (
        f"the catalogue lives at {relative}, which `Dockerfile.agent` does not copy. "
        "The route would answer locally and return nothing in the container."
    )
    assert _CATALOGUE.is_file()


def test_the_authored_path_still_resolves_to_the_shipped_one() -> None:
    """`docs/signal-catalog.yaml` is where it is authored, and must stay one file.

    A copy under `docs/` would be a second catalogue: the one people edit and the one the code
    reads, diverging silently — the exact shape this whole chantier is removing everywhere else.
    """
    authored = _REPO / "docs" / "signal-catalog.yaml"
    assert authored.is_symlink(), "docs/signal-catalog.yaml must be a symlink, never a copy"
    assert authored.resolve() == _CATALOGUE.resolve()


def test_counts_are_read_rather_than_asserted() -> None:
    """The four counts must be internally consistent — nothing here is a typed-in number."""
    counts = catalogue_counts()

    assert counts["total"] == counts["active"] + counts["planned"]
    assert counts["total"] > 0
    assert 0 < counts["on_quality_page"] <= counts["total"]


def test_the_shape_the_page_reads() -> None:
    payload = compute_signal_coverage()

    assert payload["available"] is True
    assert payload["catalogue"] == catalogue_counts()


def test_a_missing_catalogue_raises_instead_of_reading_as_a_clean_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zeros would render as "0 of 0 signals" — a fully-covered, entirely empty cockpit.

    Every other observability route degrades to `available: false`, because a dead panel beats
    a dead page. This one may not: its degraded value is indistinguishable from a good result,
    which is the one case where failing loudly is the honest option.
    """
    import tessera.observability.signal_coverage as mod

    catalogue_counts.cache_clear()
    monkeypatch.setattr(mod, "_CATALOGUE", _REPO / "src" / "nowhere.yaml")
    try:
        with pytest.raises(FileNotFoundError):
            catalogue_counts()
    finally:
        catalogue_counts.cache_clear()
