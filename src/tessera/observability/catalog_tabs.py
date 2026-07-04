"""Generic, render-friendly payload for command-bar catalogue tabs.

Several Tessera cockpits (Conformite, Incidents & playbooks, ...) share the same
command-bar shape for their non-overview tabs: a KPI strip, a main table with a
sticky detail panel, and a band of bottom sections (lists, activity feeds,
donuts, bar charts, multi-line trends, quick actions). This module factors that
shape into one set of typed dataclasses (``CatalogTab`` and friends) plus a few
cell builders, so each page only supplies deterministic fixture data.

The frontend renders any ``CatalogTab`` generically, so adding or tuning a tab is
a pure-data change in the page-specific ``*_tabs.py`` module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CatalogTab",
    "DetailField",
    "DetailList",
    "SectionItem",
    "TabColumn",
    "TabDetail",
    "TabExplain",
    "TabKpi",
    "TabRow",
    "TabSection",
    "bar",
    "badge",
    "delta",
    "owner",
]


@dataclass(frozen=True, slots=True)
class TabExplain:
    """Plain-language "what does this number mean?" text for a KPI / panel.

    Rendered as the info popover next to a metric or section title: ``what`` it
    is, ``how`` it is computed, and the ``source`` it comes from. Authored in
    French (ASCII) like the rest of the catalogue and localized through the
    module ``_TR`` map, so DE / EN come for free.
    """

    what: str
    how: str | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class TabKpi:
    """One KPI tile in a tab strip."""

    label: str
    value: str
    unit: str | None = None
    sub: str | None = None
    delta: str | None = None  # pre-formatted, ASCII signs, e.g. "+8.2%"
    delta_good: bool | None = None  # True -> green, False -> red
    tone: str | None = None  # good | warn | bad | neutral
    explain: TabExplain | None = None


@dataclass(frozen=True, slots=True)
class TabColumn:
    """A column descriptor for the main table."""

    key: str
    label: str
    kind: str = "text"  # text | num | delta | badge | owner | mono | bar | pct
    align: str = "left"


@dataclass(frozen=True, slots=True)
class TabRow:
    """One table row. ``cells`` maps column key -> render value."""

    id: str
    cells: dict[str, object]


@dataclass(frozen=True, slots=True)
class DetailField:
    """A label/value pair in the detail panel."""

    label: str
    value: str
    tone: str | None = None


@dataclass(frozen=True, slots=True)
class DetailList:
    """A small titled list inside the detail panel."""

    title: str
    items: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TabDetail:
    """The sticky right-hand detail panel for the selected row."""

    eyebrow: str
    title: str
    status_label: str | None
    status_tone: str | None
    summary: str | None
    fields: list[DetailField] = field(default_factory=list)
    lists: list[DetailList] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    explain: TabExplain | None = None


@dataclass(frozen=True, slots=True)
class SectionItem:
    """One row inside a bottom section."""

    label: str
    sub: str | None = None
    value: str | None = None
    badge: str | None = None
    badge_tone: str | None = None


@dataclass(frozen=True, slots=True)
class TabSection:
    """A bottom-band panel: list / activity / donut / bars / chart / actions."""

    title: str
    kind: str  # list | activity | donut | bars | chart | actions
    items: list[SectionItem] = field(default_factory=list)
    cta: str | None = None
    donut_value: float | None = None  # 0..1
    donut_label: str | None = None
    bars: list[dict[str, object]] = field(default_factory=list)  # {label,value,tone?}
    series: list[dict[str, object]] = field(default_factory=list)  # {label,color,points}
    actions: list[str] = field(default_factory=list)
    explain: TabExplain | None = None


@dataclass(frozen=True, slots=True)
class CatalogTab:
    """The full payload for one command-bar tab."""

    table_title: str
    kpis: list[TabKpi] = field(default_factory=list)
    columns: list[TabColumn] = field(default_factory=list)
    rows: list[TabRow] = field(default_factory=list)
    detail: TabDetail | None = None
    sections: list[TabSection] = field(default_factory=list)
    table_explain: TabExplain | None = None


# --- cell builders --------------------------------------------------------


def owner(name: str, role: str) -> dict[str, object]:
    """An owner cell: avatar initials + name + role."""
    return {"name": name, "role": role}


def badge(label: str, tone: str) -> dict[str, object]:
    """A badge cell: coloured pill."""
    return {"label": label, "tone": tone}


def delta(value: str, change: str, good: bool) -> dict[str, object]:
    """A numeric cell with a coloured period-over-period change."""
    return {"value": value, "delta": change, "good": good}


def bar(have: int, total: int) -> dict[str, object]:
    """A progress cell: ``have / total`` plus a percentage bar."""
    return {"have": have, "total": total, "pct": round(have / total * 100) if total else 0}
