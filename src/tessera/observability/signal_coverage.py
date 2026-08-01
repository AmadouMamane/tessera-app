"""How many signals the cockpit declares, how many it can actually read, and why not the rest.

The Qualité IA page headed itself "42 of the 200-signal catalogue" from two constants. Neither
was read from anything, and on 2026-08-01 all three of its numbers were wrong: the page rendered
**19** rows, the catalogue held **202**, and the operator's real question — *why are only three
signals critical and twelve unavailable?* — had no answer anywhere on the screen.

It has one, and it is a funnel, not a coverage ratio:

    202 declared in the catalogue
     78 of them `active` (124 are `planned` — designed, never built)
     N  declared by this page
     M  with a reader in code
     K  with a sample in the window
     B  breaching

Nothing on screen distinguished the stages, so "12 unavailable" silently pooled four different
situations that demand four different actions:

* **no-sample** — the reader works, the window is empty. Wait, or widen the window.
* **read-failed** — the source answered "I could not measure". Investigate the source.
* **no-reader** — the catalogue declares it; no code reads it. Build the reader.
* **planned** — declared as a design intention, never implemented. Nothing to fix today.

Pooling them under one word is ADR 0026's failure with an extra step: the screen reports a blind
spot without saying where the blindness is.

**The catalogue lives under `src/`.** It was authored at `docs/signal-catalog.yaml`, which the
agent image does not ship (`Dockerfile.agent` copies `src` and `eval`, nothing else) — a route
reading it would have worked in every local test and returned nothing in production. `docs/`
keeps a symlink so the authored path still resolves.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import yaml

__all__ = ["CatalogueCounts", "catalogue_counts", "compute_signal_coverage"]

#: The catalogue as shipped. Resolved from THIS file so it travels with the package.
_CATALOGUE = Path(__file__).parent / "data" / "signal_catalog.yaml"


class CatalogueCounts(TypedDict):
    """The declared population, split by whether it was ever built."""

    total: int
    active: int
    planned: int
    #: Signals whose declared home page is the quality surface.
    on_quality_page: int


@lru_cache(maxsize=1)
def catalogue_counts() -> CatalogueCounts:
    """Count the declared signals by status.

    Cached because the file is shipped, immutable at runtime, and read by a page that polls.

    Raises:
        FileNotFoundError: if the catalogue is absent. Deliberately NOT caught — a coverage
            number computed over a missing catalogue is the exact shape of lie this module
            exists to remove, and returning zeros would render as "0 of 0 signals", which
            reads like a clean, empty system.
    """
    signals = yaml.safe_load(_CATALOGUE.read_text(encoding="utf-8"))["signals"]
    active = sum(1 for s in signals if s.get("status") == "active")
    return {
        "total": len(signals),
        "active": active,
        "planned": len(signals) - active,
        "on_quality_page": sum(1 for s in signals if s.get("page") == "qualite"),
    }


def compute_signal_coverage() -> dict[str, object]:
    """The catalogue half of the funnel — the two stages the backend can answer.

    The remaining stages (declared by the page, wired, sampled, breaching) are facts about what
    the FRONTEND rendered, and are counted there from the rows it actually produced. Asking the
    backend to guess them would be the same mistake as the constants: a number about a screen,
    computed somewhere that cannot see the screen.
    """
    counts = catalogue_counts()
    return {"available": True, "catalogue": counts}
