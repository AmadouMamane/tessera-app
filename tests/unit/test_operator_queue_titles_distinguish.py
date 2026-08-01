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


def test_only_as_many_dimensions_as_it_takes_to_separate() -> None:
    """Two rows differing in agent AND language get the AGENT only — it already separates.

    Adding every differing dimension would put two qualifiers on a line that needed one. The
    chooser stops as soon as the rendered titles are distinct, which keeps the queue readable
    exactly where it is already crowded.
    """
    items = _count_variants(
        [
            _item("support-client", "c1", "fr", "A refund was promised"),
            _item("recouvrement", "c1", "de", "A refund was promised"),
        ]
    )

    assert {i.display_title for i in items} == {
        "A refund was promised · support-client",
        "A refund was promised · recouvrement",
    }
    assert all(i.variant_dims == ("agent",) for i in items)


def test_it_keeps_going_when_a_dimension_does_not_actually_separate() -> None:
    """A dimension can differ in the DATA and collide on SCREEN — the chooser must notice.

    The conversation reference is truncated for readability, so two conversations sharing a
    prefix render identically. On the live fleet that left "…· ckpt2-metier" twice after a
    version that computed the right dimension and never checked the result.
    """
    a = replace(
        _item("recouvrement", "RC-2048", "fr", "Validation requise"),
        item_id="a",
        context_ref="ckpt2-metier-live-aaaa",
        created_at=datetime(2026, 7, 7, 6, 6, tzinfo=UTC),
    )
    b = replace(
        _item("recouvrement", "RC-2048", "fr", "Validation requise"),
        item_id="b",
        context_ref="ckpt2-metier-live-bbbb",
        created_at=datetime(2026, 7, 7, 7, 3, tzinfo=UTC),
    )

    items = _count_variants([a, b])

    assert len({i.display_title for i in items}) == 2, (
        "the two rows still read the same: the truncated conversation prefix is shared, so the "
        "chooser had to fall through to the arrival instant"
    )
    assert all("time" in i.variant_dims for i in items)


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


def test_it_always_terminates_on_a_set_that_separates() -> None:
    """Two items identical in EVERY declared dimension still get distinct titles.

    Same agent, language, conversation and minute — the state the live fleet reached with two
    validation requests raised seconds apart in one conversation. The last candidate is a
    digest of `item_id`, the dedupe key, so it separates by construction.

    A tail of the id was tried first and did NOT work: these ids end with the artifact key
    (`…RC-2048-schedule-36-months-v2`), identical across the group, and only their middle
    varies. An id being unique says nothing about any fixed window of it.
    """
    when = datetime(2026, 7, 9, 23, 15, tzinfo=UTC)
    twins = [
        replace(
            _item("recouvrement", "RC-2048", "fr", "Validation requise"),
            item_id=f"recouvrement.validation.requested.conv-1.{n}.RC-2048-schedule-36-months-v2",
            context_ref="conv-1",
            created_at=when,
        )
        for n in ("aaa", "bbb")
    ]

    items = _count_variants(twins)

    assert len({i.display_title for i in items}) == 2
    assert all("ref" in i.variant_dims for i in items)


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
