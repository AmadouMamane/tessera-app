"""The judge's plane is DECLARED (ADR 0017 §A4, ADR 0053 §4) — and the spine keeps it so.

Two seams, one rule. Write side: :func:`online.evaluate_turn` refuses to judge an agent
whose declared quality regime is not ``llm_judged`` (witnessed next door in
``test_observability_eval.py``). Read side, here: ``SnapshotContext.scores`` — the one
seam every score-backed signal reads through, whatever adapter serves the rows — drops
rows attributed to a non-judged agent, so a leaked historical row cannot resurrect a
judged population. Measured leak, 2026-08-22: one operator-side /chat turn routed to
recouvrement was judged, and that single row became the whole per-agent SLO population
("100,0 %" rendered on n=1). Nothing is destroyed — the durable log keeps every row; the
plane the surfaces read simply excludes them.
"""

from __future__ import annotations

from tessera.observability.spine.adapters.fake import FakeSpineReader
from tessera.observability.spine.context import SnapshotContext
from tessera.observability.spine.scope import Scope


def _row(agent_id: str | None, score: float = 0.9) -> dict[str, object]:
    return {
        "metric": "faithfulness",
        "score": score,
        "agent_id": agent_id,
        "scored_at": "2026-08-22T13:51:31+00:00",
        "language": "fr",
    }


def test_a_business_scored_agents_rows_never_reach_a_signal() -> None:
    """The 2026-08-22 leak, replayed: recouvrement's judged row vanishes at the seam."""
    context = SnapshotContext(
        FakeSpineReader(scores=[_row("support-client"), _row("recouvrement", score=0.8)])
    )
    rows = context.scores(Scope())
    assert [r["agent_id"] for r in rows] == ["support-client"]


def test_the_filter_narrows_by_declaration_only() -> None:
    """Unattributed history and ids the registry does not know stay in the plane."""
    context = SnapshotContext(
        FakeSpineReader(scores=[_row(None), _row("not-a-registry-agent"), _row("recouvrement")])
    )
    rows = context.scores(Scope())
    assert [r["agent_id"] for r in rows] == [None, "not-a-registry-agent"]


def test_the_agent_scoped_read_of_a_non_judged_agent_is_honestly_empty() -> None:
    """Scoped to recouvrement itself, the judged plane answers empty — not its leak."""
    context = SnapshotContext(FakeSpineReader(scores=[_row("recouvrement")]))
    assert context.scores(Scope(agent_id="recouvrement")) == []


def test_the_shared_read_stays_single() -> None:
    """The filter rides the memoised read: two signals still cost ONE upstream load."""
    context = SnapshotContext(FakeSpineReader(scores=[_row("support-client")]))
    scope = Scope()
    context.scores(scope)
    context.scores(scope)
    assert context.upstream_reads == 1


def test_both_read_doors_apply_the_same_filter() -> None:
    """`read_scores` — the routes' direct seam — filters exactly like the snapshot's door.

    The parity ratchet caught the first version of this filter covering only the
    snapshot context: routes read through `read_scores` and served the leak while the
    snapshot did not. Both doors now call the one shared filter; this witness holds the
    second door on its own, so a future refactor cannot quietly reopen it.
    """
    from tessera.observability.spine.adapters import read_scores, set_reader

    set_reader(FakeSpineReader(scores=[_row("support-client"), _row("recouvrement")]))
    try:
        assert [r["agent_id"] for r in read_scores()] == ["support-client"]
    finally:
        set_reader(None)
