"""No request path may load the whole ledger — the class, closed at the seam that measures it.

The cockpit's main page took 3 938 ms. Not because of one bad query, but because of a HABIT:
answer a per-entity question by reading the entire append-only ledger into memory and filtering
it in Python — once per entity. Six times per fleet request, six more in the header of all 32
pages. Every one of them was written by someone reasonable, because each read looked local and
cheap, and none of them could see the others.

It was parked three times as "not blocking". It was not blocking until the ledger reached 25 716
rows, and an append-only store guarantees it will reach 250 000. **A debt deferred as
"not blocking" is only not-blocking until the data grows.**

So this file does not patch six reads. It closes the class, on two levels:

* **The budget** — the request paths this lot fixed are driven against a fake ledger of 5 000
  entries, and every store read they perform is counted. If any single read materialises more
  than :data:`ROW_BUDGET` rows, this fails. It counts through the real instrumentation
  (:mod:`tessera.observability.store_spans`), so it measures what the trace measures.

* **The freeze** — the set of modules that *can* materialise an unbounded slice of the ledger is
  pinned by exact-set equality. A twenty-second one cannot appear. The nineteen that remain are
  named below with the reason each is still there, and the ``OWED`` count is asserted so the debt
  is a number in CI rather than a sentence in a document nobody re-reads.

**The row count judges; the function name never does.** That is not a stylistic preference, it is
the finding: ``load_ledger_payloads_of_type("tessera.guard.audit")`` *looks* like a targeted read
and returns **94 % of the chain** (24 250 of 25 716, measured on the real ledger). A ratchet that
trusted the name would have certified it. This one counts the rows.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from tessera.observability import store_spans
from tests.unit._ledger_cardinality_fake import (
    LEDGER_ROWS,
    CardinalityLedgerConn,
    cardinality,
)

_SRC = Path(__file__).resolve().parents[2] / "src"

#: The most rows any single read on a fixed request path may bring back. Generous on purpose: the
#: point is not to police a query plan, it is to make a FULL READ impossible. The fixed paths
#: measure 1-3 rows; the reads this closes measured 25 716.
ROW_BUDGET = 100


#: Every module holding its OWN binding of ``_connect_sync``. ``from x import y`` copies the name,
#: so patching it in ``ledger_store`` alone leaves ``ledger_checkpoint`` pointing at the real
#: connection — and on a developer's machine, where Postgres IS up, this ratchet then measured the
#: REAL ledger and passed for the wrong reason. It was the cold-checkpoint test that caught it.
#: A budget that silently reads production is not a budget.
_CONNECT_SITES = (
    "tessera.guard.ledger_store._connect_sync",
    "tessera.guard.ledger_checkpoint._connect_sync",
)


def _install(monkeypatch: pytest.MonkeyPatch, conn: CardinalityLedgerConn) -> None:
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    for site in _CONNECT_SITES:
        monkeypatch.setattr(site, lambda conn=conn: conn)


@pytest.fixture
def fake_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route every sync ledger read to the cardinality oracle, in postgres mode."""
    _install(monkeypatch, CardinalityLedgerConn())


def _worst(reads: list[store_spans.StoreRead]) -> store_spans.StoreRead | None:
    """The read that pulled back the most rows — the one that would break the budget."""
    counted = [r for r in reads if r.rows is not None]
    return max(counted, key=lambda r: r.rows or 0) if counted else None


def _assert_within_budget(reads: list[store_spans.StoreRead], path: str) -> None:
    assert reads, f"{path}: no store read was recorded — the instrumentation is not wired"
    worst = _worst(reads)
    assert worst is not None and (worst.rows or 0) <= ROW_BUDGET, (
        f"{path} materialised {worst.rows if worst else '?'} rows in a single read "
        f"({worst.operation if worst else '?'}) — a request path may not load the ledger. "
        f"Ask the database the question you actually have: an indexed row, an aggregate, a "
        f"bounded window. Budget is {ROW_BUDGET}."
    )


class TestTheRequestPathsThisLotFixed:
    """Driven against a 5 000-entry ledger. Each read all 5 000 before — some six times."""

    def test_the_fleets_canary_verdicts_are_one_indexed_row_per_agent(
        self, fake_ledger: None
    ) -> None:
        """Was: ``load_ledger_payloads_sync()`` per agent, to find one entry. Six full reads."""
        from tessera.observability.quality_nets import latest_canary_verdicts

        with store_spans.recording() as reads:
            latest_canary_verdicts()

        _assert_within_budget(reads, "quality_nets.latest_canary_verdicts")

    def test_one_agents_canary_verdict_is_one_indexed_row(self, fake_ledger: None) -> None:
        from tessera.observability.quality_nets import latest_canary_verdict

        with store_spans.recording() as reads:
            latest_canary_verdict("recouvrement")

        _assert_within_budget(reads, "quality_nets.latest_canary_verdict")

    def test_the_fleets_handoff_counts_are_an_aggregate(self, fake_ledger: None) -> None:
        """A count belongs in the database. Was: every entry read, to count a few dozen."""
        from tessera.guard.ledger_store import handoff_counts

        with store_spans.recording() as reads:
            handoff_counts()

        _assert_within_budget(reads, "ledger_store.handoff_counts")

    def test_the_fleets_handoff_reconciliation_is_an_aggregate(self, fake_ledger: None) -> None:
        """The journeys the journal attests come back grouped in SQL — never the chain in Python."""
        from tessera.guard.ledger_store import handoff_conversations

        with store_spans.recording() as reads:
            events, conv_ids = handoff_conversations()

        assert events >= 1 and conv_ids, "the fake ledger attests handoffs; none came back"
        _assert_within_budget(reads, "ledger_store.handoff_conversations")

    def test_the_fleets_integrity_dot_is_incremental(self, fake_ledger: None) -> None:
        """The health dot asks the weak question, and pays the weak price.

        ``active_ledger_verdict`` re-hashes only the rows above a checkpoint whose anchor it
        re-reads from the ledger every time. The STRONG verifier (a full walk, for the page that
        asserts opposability to a regulator) is deliberately left alone — see
        ``active_ledger_tree_status``.
        """
        from tessera.guard.ledger_checkpoint import active_ledger_verdict

        with store_spans.recording() as reads:
            active_ledger_verdict()

        _assert_within_budget(reads, "ledger_checkpoint.active_ledger_verdict")

    def test_the_headers_canary_bell_is_one_query_for_the_whole_fleet(
        self, fake_ledger: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The bell in the header of all 32 pages. It used to read the ledger PER AGENT."""
        from tessera.observability import chrome

        with store_spans.recording() as reads:
            chrome._canary_notifications("fr")

        _assert_within_budget(reads, "chrome._canary_notifications")


class TestTheRatchetCanActuallyFail:
    """A ratchet that cannot go red is decoration. This proves it goes red on the real offence."""

    def test_the_old_full_read_breaks_the_budget(self, fake_ledger: None) -> None:
        """The literal call the fleet used to make, per agent. It must be refused."""
        from tessera.guard.ledger_store import load_ledger_payloads_sync

        with store_spans.recording() as reads:
            payloads = load_ledger_payloads_sync()

        assert len(payloads) == LEDGER_ROWS  # the oracle really did hand back the whole chain
        worst = _worst(reads)
        assert worst is not None and worst.rows == LEDGER_ROWS
        with pytest.raises(AssertionError, match="may not load the ledger"):
            _assert_within_budget(reads, "the offence")

    def test_a_read_that_is_targeted_in_name_only_is_still_a_full_read(
        self, fake_ledger: None
    ) -> None:
        """The subtle one, and the reason this ratchet counts rows instead of trusting names.

        ``load_ledger_payloads_of_type`` READS like a fix — it names a filter, it pushes it into
        SQL. It is bounded only when the type is RARE, and the type the cockpit reads most,
        ``tessera.guard.audit``, is **94 % of the real chain** (24 250 of 25 716, measured). A
        ratchet keyed on the function name would have pronounced that call closed.

        The oracle judges the query's SHAPE, and a predicate is not a bound. Asserted here so the
        distinction cannot be lost: a WHERE clause the database cannot use to skip rows is a full
        read wearing the word "filter".
        """
        sql = "SELECT payload FROM audit_ledger WHERE payload->>'type' = %s ORDER BY seq"
        assert cardinality(sql) == LEDGER_ROWS, (
            "a type filter that matches almost every row must still count as a full read — "
            "otherwise this ratchet certifies the very shape it was built to refuse"
        )

    def test_a_cold_process_walks_the_whole_chain_once_and_that_is_deliberate(self) -> None:
        """The exception, asserted — so it stays an exception instead of quietly becoming the rule.

        With no checkpoint the verifier re-reads and re-hashes every row: that full walk is what
        the incremental claim RESTS on, and it must keep happening. What must never happen is a
        full walk on every request. The steady state is the one the budget polices; this pins the
        cold one so a regression that silently discards the checkpoint on each call shows up here
        as a 5 000-row read rather than as a slow afternoon.
        """
        from tessera.guard import ledger_checkpoint

        with pytest.MonkeyPatch.context() as mp, store_spans.recording() as reads:
            _install(mp, CardinalityLedgerConn(checkpoint=False))
            ledger_checkpoint.active_ledger_verdict()

        worst = _worst(reads)
        assert worst is not None and worst.rows == LEDGER_ROWS
        assert worst.operation == "audit_ledger.rows_above"

    def test_the_recorder_survives_the_thread_hop(self, fake_ledger: None) -> None:
        """This lot pushed the blocking reads into ``asyncio.to_thread``.

        A budget that stopped counting the moment a read moved off the event loop would have
        certified the very change it exists to police. ``contextvars`` are copied into the thread,
        so the read still lands in the recorder — asserted, not assumed.
        """
        from tessera.guard.ledger_store import load_ledger_payloads_sync

        async def drive() -> None:
            await asyncio.to_thread(load_ledger_payloads_sync)

        with store_spans.recording() as reads:
            asyncio.run(drive())

        assert [r.rows for r in reads] == [LEDGER_ROWS], (
            "a store read performed inside asyncio.to_thread was not recorded — the budget "
            "would silently stop policing every read this lot moved off the event loop"
        )


#: Every module that can materialise an unbounded slice of the ledger, and WHY it still can.
#:
#: ``file`` — reachable only under ``TESSERA_LEDGER_SOURCE=file``. A flat journal has no index;
#: the scan is irreducible there and the module takes the targeted path in postgres mode.
#: ``strong`` — deliberately full: the verdict this produces is asserted to a third party, and an
#: assertion of that weight re-reads what it asserts about.
#: ``off-chrono`` — not on a request path (the cut gate, the backfill, the periodic verifier).
#: ``OWED`` — a request path that still materialises the ledger. This is the debt. It has a
#: number, and the number may only go down.
_UNBOUNDED_CAPABLE: dict[str, str] = {
    # ── the seam and its deliberate full walks ──────────────────────────────────
    "tessera/guard/ledger_store.py": "strong — the read seam itself + the full-walk verifiers",
    "tessera/guard/seal.py": "strong — État à date asserts opposability; it re-reads the chain",
    # ── file-mode fallbacks (the postgres path is targeted) ─────────────────────
    "tessera/observability/fleet.py": "file — postgres counts handoffs in SQL",
    "tessera/observability/quality_nets.py": "file — postgres reads one indexed canary row",
    "tessera/api/routes/observability/_common.py": "OWED — audit 94 %, cached sync + filter",
    "tessera/observability/spine/adapters/current.py": "OWED — same 94 % read, via the spine",
    # ── OWED: request paths that still read the whole chain and filter in Python ─
    "tessera/observability/agent_garde_fous.py": "file — postgres unnests decisions in SQL",
    "tessera/observability/agent_lifecycle.py": "OWED",
    "tessera/observability/automation_store.py": "OWED",
    "tessera/observability/automations.py": "OWED",
    "tessera/observability/conformance.py": "OWED",
    "tessera/observability/etat_a_date.py": "OWED",
    "tessera/observability/governance_feed.py": "OWED",
    "tessera/observability/guard_explain.py": "file — postgres unnests decisions in SQL",
    "tessera/observability/integrations.py": "file — postgres unnests tool decisions in SQL",
    "tessera/observability/policies.py": "OWED",
    "tessera/observability/session_detail.py": "OWED",
    "tessera/observability/tool_validity.py": "OWED",
}

#: How many of them are a request path that still loads the ledger. **This may only go down.**
#: 2026-07-22: agent_synthese, then incidents, paid their debt — both journal scans are
#: bounded at the seam (``read_ledger_entries(since=, until=)``, SQL-side in postgres mode).
#: 2026-07-29: system_profile paid its debt — the runtime panel's ``audit_lines`` is a bounded
#: ``count_ledger_entries()`` (SQL ``count(*)``) instead of ``len(read_ledger_entries())``.
#: 2026-07-29: guard_explain paid its debt — the (rule, kind) rollup is a bounded SQL ``GROUP BY``
#: over unnested decisions (``guard_explain_scan``); it drops to a ``file``-only capability (the
#: flat-journal fallback still scans), so it stays frozen but leaves the OWED count.
#: 2026-07-29: integrations paid its debt — the per-tool stats (decisions/denials/24h/last) are a
#: bounded SQL ``GROUP BY`` over the unnested ``tool.<name>.allow`` decisions
#: (``integrations_tool_scan``); ``file``-only fallback, same as guard_explain.
#: 2026-07-30: agent_garde_fous paid its debt — the per-rule stats + four whole-log totals
#: (decisions/denials, 24h, prior-24h, last-fired) are a bounded SQL ``GROUP BY`` over the unnested
#: decisions (``audit_rule_scan``, cutoffs passed so the boundary is the caller's clock);
#: ``file``-only fallback, same as guard_explain.
OWED_COUNT = 11

#: The readers that cannot promise a bound. ``load_ledger_payloads_of_type`` is here ON PURPOSE:
#: it is bounded only when the type is rare, and the type the cockpit reads most is 94 % of the
#: chain. A reader is "bounded" when the DATABASE limits it — a LIMIT, an aggregate, an indexed
#: row, a time window — never when the caller merely names a filter.
_UNBOUNDED_READERS = {"load_ledger_payloads_sync", "load_ledger_payloads_of_type"}


def _modules_that_can_load_the_chain() -> dict[str, list[str]]:
    """Every module calling a reader that may hand back the whole ledger, by AST.

    ``read_ledger_entries(since=…, until=…)`` is bounded IN SQL on the ``occurred_at`` index and
    does not count; the same call without a window does. The AST is what distinguishes them — a
    grep sees one name and cannot.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        hits: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else (func.attr if isinstance(func, ast.Attribute) else None)
            )
            if name in _UNBOUNDED_READERS:
                hits.add(name)
            elif name == "read_ledger_entries" and not (
                {kw.arg for kw in node.keywords} & {"since", "until"}
            ):
                hits.add("read_ledger_entries")
        if hits:
            found[str(path.relative_to(_SRC))] = sorted(hits)
    return found


class TestTheFreeze:
    """The set may shrink. It may not grow. That is the whole point of a ratchet."""

    def test_no_new_module_may_load_the_whole_ledger(self) -> None:
        found = set(_modules_that_can_load_the_chain())
        frozen = set(_UNBOUNDED_CAPABLE)

        appeared = sorted(found - frozen)
        assert not appeared, (
            f"a NEW module reads the ledger without a bound: {appeared}. This is the class this "
            f"ratchet exists to close — it cost the cockpit's main page 3.5 of its 3.9 seconds, "
            f"and it was written six times by six reasonable people. Ask the database the "
            f"question you have: an indexed row (latest_entry_of_type_for_agent), an aggregate "
            f"(handoff_counts), or a window (read_ledger_entries(since=…, until=…))."
        )

        gone = sorted(frozen - found)
        assert not gone, (
            f"these modules no longer load the ledger — excellent. Delete them from "
            f"_UNBOUNDED_CAPABLE and lower OWED_COUNT so the debt shrinks on the record: {gone}"
        )

    def test_the_debt_is_a_number_and_it_only_goes_down(self) -> None:
        """11 request paths still materialise the chain. Naming them is what makes them payable.

        The honest claim of this lot is NOT "the class is closed everywhere". It is: no NEW
        full-ledger read can appear, the fleet and the header no longer perform one, and the
        eleven that remain are named, counted, and cannot multiply while nobody is looking.
        """
        owed = sum(1 for reason in _UNBOUNDED_CAPABLE.values() if reason.startswith("OWED"))
        assert owed == OWED_COUNT, (
            f"the owed count moved ({owed} vs {OWED_COUNT}). If a path was fixed, lower "
            f"OWED_COUNT — the number is the debt, and it is meant to be read."
        )
