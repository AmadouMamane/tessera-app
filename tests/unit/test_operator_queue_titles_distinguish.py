"""CLASS H — two rows in an operator queue never read as the same row.

The backlog is derived from failed eval cases, and `item_id` is ``<agent>.<case>.<language>``.
One case failing in three languages is **three real failures** and all three belong in the
queue: collapsing them would hide two, and the operator would fix one locale and believe they
had fixed the case. So this is not a deduplication problem.

It is a legibility problem, and the worse kind. Every row's `title` is the eval case's own
title, and `agent_a_faire` goes further and localises it PER `case_id` — so three rows for
three languages resolved to three byte-identical sentences, with the facts that told them apart
(the language, the agent) living only in fields nothing rendered. Measured before the fix: 18
items, **8 distinct titles**. An operator reading that cannot tell "several problems" from "one
problem, several times", and the queue's own count of open items stops meaning anything.

The dimension appended is computed per colliding group, never assumed. A first attempt always
appended the language and left "Unauthorised promise of a refund · FR" twice on screen — the
same case under two AGENTS, told apart by a field it still never mentioned.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime

from tessera.observability.operator_items import OperatorItem, _count_variants, load_items


def _item(agent: str, case: str, language: str, title: str) -> OperatorItem:
    return OperatorItem(
        item_id=f"{agent}.{case}.{language}",
        agent_id=agent,
        case_id=case,
        category="overconfidence",
        type_label="Overconfidence",
        title=title,
        language=language,
        source="Assistant",
        priority="high",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        needs_escalation=False,
        status="todo",
        assignee="",
    )


def test_a_lone_row_keeps_its_bare_title() -> None:
    """No collision, no qualifier. Qualifying everything to fix a few rows is just noise."""
    (only,) = _count_variants([_item("support-client", "c1", "fr", "A refund was promised")])

    assert only.n_variants == 1
    assert only.display_title == "A refund was promised"


def test_language_is_appended_when_language_is_what_differs() -> None:
    items = _count_variants(
        [
            _item("support-client", "c1", lang, "A refund was promised")
            for lang in ("fr", "de", "en")
        ]
    )

    assert {i.display_title for i in items} == {
        "A refund was promised · FR",
        "A refund was promised · DE",
        "A refund was promised · EN",
    }


def test_agent_is_appended_when_the_agent_is_what_differs() -> None:
    """The defect the first version had: two agents, one language, and 'FR' twice on screen."""
    items = _count_variants(
        [
            _item(agent, "c1", "fr", "A refund was promised")
            for agent in ("support-client", "recouvrement")
        ]
    )

    assert {i.display_title for i in items} == {
        "A refund was promised · support-client",
        "A refund was promised · recouvrement",
    }
    assert all(i.variant_dims == ("agent",) for i in items), (
        "the language is CONSTANT across these two; appending it adds a word and "
        "disambiguates nothing"
    )


def test_both_are_appended_when_both_differ() -> None:
    items = _count_variants(
        [
            _item("support-client", "c1", "fr", "A refund was promised"),
            _item("recouvrement", "c1", "de", "A refund was promised"),
        ]
    )

    assert {i.display_title for i in items} == {
        "A refund was promised · support-client · FR",
        "A refund was promised · recouvrement · DE",
    }


def test_grouping_is_by_title_not_by_case_id() -> None:
    """Two DIFFERENT cases sharing a title collide on screen exactly as badly.

    The id that would tell them apart is not rendered either, so grouping by `case_id` would
    have left the collision the operator actually sees.
    """
    items = _count_variants(
        [
            _item("support-client", "c1", "fr", "A refund was promised"),
            _item("support-client", "c2", "de", "A refund was promised"),
        ]
    )

    assert len({i.display_title for i in items}) == 2


def test_disambiguate_applies_to_a_localised_title_too() -> None:
    """`agent_a_faire` localises per `case_id`, which is a STRONGER collision than the raw title.

    Three languages resolve to one localised sentence, where the untranslated fallback at least
    varied when the eval titles did. Disambiguating the raw title and rendering the localised
    one would have fixed the collision in the wrong string.
    """
    item = replace(
        _item("support-client", "c1", "de", "raw"), n_variants=3, variant_dims=("language",)
    )

    assert (
        item.disambiguate("Un remboursement a été promis") == "Un remboursement a été promis · DE"
    )


def test_the_real_backlog_has_no_two_rows_reading_the_same() -> None:
    """The tree itself. 18 items over 8 distinct titles before; one row per title after."""
    items = load_items()
    if not items:  # a checkout with no eval report — nothing to assert, and nothing hidden
        return

    collisions = {t: n for t, n in Counter(i.display_title for i in items).items() if n > 1}

    assert collisions == {}, (
        "these titles name more than one queue row, so the operator cannot tell them apart:\n  "
        + "\n  ".join(f"{n}x  {t}" for t, n in sorted(collisions.items()))
    )
