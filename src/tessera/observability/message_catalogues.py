"""Where the message catalogues are, and what to say when they are not there.

`/observability/localization` reported **100 % complete in production for its entire life**, and
not because the translations were complete. It resolved
``Path(__file__).parents[5] / "webapp" / "frontend" / "messages"`` and swallowed the failure::

    try:
        catalogues[locale] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        catalogues[locale] = {}

In the container that path is ``/app/webapp/frontend/messages``, and ``Dockerfile.agent`` copies
``src``, ``eval``, ``README.md`` and ``LICENSE`` — nothing else. Interrogated directly::

    $ docker exec tessera-local-agent ls /app
    eval
    src

So all three reads failed, all three catalogues became ``{}``, the default locale contributed
**zero** keys, and ``assess_localization`` divides by it::

    completeness = (n_default - len(missing)) / n_default if n_default else 1.0

`1.0`. A hundred percent, over nothing, on a compliance surface. It is ADR 0026's exact failure —
a witness that cannot see reporting "ok" — and it is the second time in this repo that a route
reading outside `src/` returned a confident answer about a directory it could not open.

This module answers two questions instead of one:

* **where** the catalogues are — trying the shipped location first, then the repo layout;
* **whether they were found at all** — as a value the caller must handle, never as a silent
  empty dict.

A missing catalogue is now `available: false` naming the paths tried. That is worth more than a
number: "I could not look" and "everything is fine" are the two answers a compliance surface
must never confuse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["CatalogueLoad", "LOCALES", "load_catalogues", "messages_dir"]

#: The locales the product claims on its front page.
LOCALES: tuple[str, ...] = ("en", "fr", "de")

#: Shipped inside the package (`Dockerfile.agent` copies `src`), then the repo layout for a
#: source checkout. Order matters: the container has only the first.
_CANDIDATES: tuple[Path, ...] = (
    Path(__file__).parent / "data" / "messages",
    Path(__file__).resolve().parents[3] / "webapp" / "frontend" / "messages",
)


@dataclass(frozen=True, slots=True)
class CatalogueLoad:
    """The catalogues, or an honest account of why there are none."""

    #: ``locale -> message dict``. Empty when nothing could be read.
    catalogues: dict[str, dict[str, object]]
    #: The directory actually used, as a string. ``None`` when none was found.
    source: str | None
    #: Every path tried, so a failure says where it looked.
    tried: list[str] = field(default_factory=list)
    #: Locales whose file was missing or unparseable in an otherwise-found directory.
    unreadable: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        """True when at least the default locale was read."""
        return bool(self.catalogues)


def messages_dir() -> Path | None:
    """The first candidate directory that exists, or ``None``."""
    return next((c for c in _CANDIDATES if c.is_dir()), None)


def load_catalogues() -> CatalogueLoad:
    """Read every locale catalogue, reporting what could not be read.

    Never raises and never substitutes an empty catalogue for a missing one — those are the two
    ways this measurement has already lied. A locale that could not be parsed is named in
    ``unreadable`` and left OUT of ``catalogues``, so it cannot be counted as complete.
    """
    tried = [str(c) for c in _CANDIDATES]
    directory = messages_dir()
    if directory is None:
        return CatalogueLoad(catalogues={}, source=None, tried=tried)

    catalogues: dict[str, dict[str, object]] = {}
    unreadable: list[str] = []
    for locale in LOCALES:
        path = directory / f"{locale}.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unreadable.append(locale)
            continue
        if isinstance(loaded, dict):
            catalogues[locale] = loaded
        else:
            unreadable.append(locale)

    return CatalogueLoad(
        catalogues=catalogues,
        source=str(directory),
        tried=tried,
        unreadable=unreadable,
    )
