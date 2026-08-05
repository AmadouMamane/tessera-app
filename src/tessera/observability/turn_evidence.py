"""Turn-evidence read — the fact that folds *real emission* into the L1 level (ADR 0017 §F).

ADR 0017 §4 says "L1 Observable" and §Governing rule says *the cockpit reads the spine*. This
module closes the §7 remote-profile ingestion gap named by the ADR but never built: L1 must
mean the cockpit **observes** the agent emitting turns, not merely that its AgentSpec declares
it will. The first evidence is the Prometheus counter ``tessera_agent_turns_total`` — a spine
store the cockpit already owns (0015 keeps Prometheus for every aggregate number), so an
**out-of-process** agent's OTLP metrics reach the cockpit through the collector's Prometheus
exporter with **no cockpit import and no agent-specific code** (the two-profiles-one-wire seam).

**Two sources, not one** (ADR 0017 §4 Amendment 3, 2026-08-06). That counter is incremented on
the ``/chat`` turn path, and ``/chat`` is not the only way a turn is served. ``recouvrement``
serves its turns over ``/recouvrement-assistant/message``, never touched the counter, and was
therefore read as having emitted nothing — while its 1281 timestamped business events sat in
the ledger unread, because the level short-circuits to L0 before it looks at them. The one
agent in the fleet emitting real evidence was the one the door refused for want of evidence.
That is ADR 0026's shape exactly: the witness interrogated the *neighbourhood* (one route)
instead of the thing (the agent). So a turn is also proven by the **business-event ledger** —
a distinct ``turn_id`` carrying a timestamped event inside :data:`RECENCY_WINDOW`.

Both are emissions the agent *makes* and a store *records*; neither is a declaration, so the
"never asserted" rule of §4 holds unchanged. What widens is only what counts as looking.
Widening what counts as evidence **frees** agents rather than blocking them, and a change that
frees must be read harder than one that blocks — see the merge table on
:func:`turn_evidence_state`, where a source that saw nothing proves absence only if the other
one could be asked.

Honesty (0016 / the project rule):

* An unreachable metrics store cannot *disprove* emission — but it cannot *prove* it either.
  Evidence-unknown therefore yields **no proof**, and a computed level never rests on an
  assumption. It used to: unknown was silently trusted as observed, so a fleet with no
  metrics store displayed an L1 that looked computed while it was merely declared. That is
  the over-claim class this project forbids, and it is gone.
* Nothing is lost by refusing to guess. The unproven rung is not hidden — the caller also
  reads what the manifest *declares* and the badge renders the attenuated
  "L1 declared · no evidence" variant, which distinguishes ``unverifiable`` (store off or
  down) from ``dormant`` (store read, agent has emitted nothing).
* The read is a deployment capability, gated by ``TESSERA_LEVEL_TURN_EVIDENCE`` and shipped
  **off** (like every 0015/0017 store flip). Off ⇒ ``unverifiable`` ⇒ no computed L1
  anywhere, which is the honest reading of a cockpit that observes nothing. Turning it on is
  a config action, recorded, never faked.

Evidence horizon, per source — they differ, and pretending otherwise is what makes a window
necessary:

* The Prometheus query sums the **cumulative** counter as an instant vector, with no rolling
  window. "No turn observed over the metrics store's retention" is what it measures, and a
  process restart zeroes it — which is precisely why an agent serving turns can read as silent.
* The ledger keeps business events for **six months**. Read without a window it would answer a
  different question — "has this agent ever emitted?" — and an agent dead since July would read
  as observed until January. That trades one false negative for a false positive, so the ledger
  read is bounded by :data:`RECENCY_WINDOW` and only ever asks *is it emitting now*.

Consequence to state plainly rather than discover: an agent that stops emitting **will** fall
back to L0 once the window passes it. That is the feature — evidence expires — not a
regression, and any surface reading this must word it as "observed recently", never "observed".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal

from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.prometheus import PrometheusAdapter

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

__all__ = [
    "RECENCY_WINDOW",
    "TurnEvidence",
    "TurnWindow",
    "agents_with_turn_evidence",
    "agents_with_ledger_turns",
    "has_turn_evidence",
    "ledger_turn_evidence",
    "recent_turn_evidence",
    "turn_evidence_enabled",
    "turn_evidence_sources",
    "turn_evidence_state",
    "turns_in_window",
]

#: How far back a ledger emission still counts as *this agent is emitting*.
#:
#: 30 days, chosen against both neighbours rather than picked: it is the usual Prometheus
#: retention (so the two sources answer over comparable horizons instead of one reaching six
#: months further than the other), and it is short enough that "observed" keeps meaning
#: *in service* — the whole reason the window exists. It is a read-model parameter, never a
#: user-facing number, and never a promise a surface may restate as an SLA.
RECENCY_WINDOW: Final = timedelta(days=30)

#: Why the cockpit does or does not have turn evidence for an agent. ``unverifiable`` and
#: ``dormant`` both mean *no proof*; they differ in whose silence it is — the store's or the
#: agent's — and the badge tooltip must say which.
TurnEvidence = Literal["observed", "dormant", "unverifiable"]

#: The per-agent turn counter every profile emits (semconv / metrics.py). A positive value
#: for an agent_id is the honest evidence that the cockpit has observed it processing turns.
_TURNS_METRIC = "tessera_agent_turns_total"

_ENABLE_FLAG = "TESSERA_LEVEL_TURN_EVIDENCE"
_TRUTHY = {"1", "true", "yes", "on"}
#: A PromQL instant-vector sample is ``[timestamp, "value"]`` — a 2-tuple.
_SAMPLE_LEN = 2

#: The counter is scraped more frequently than this range. Asking Prometheus for the increase
#: over two minutes, once a minute, gives a bounded 24-hour read with enough overlap not to miss
#: an increment between two evaluation instants. These are read-model sampling parameters, never
#: user-facing numbers.
_RECENT_STEP = "60s"
_RECENT_INCREASE_RANGE = "2m"


def turn_evidence_enabled() -> bool:
    """Whether the L1 turn-evidence read is enabled for this deployment (config flip)."""
    return os.environ.get(_ENABLE_FLAG, "").strip().lower() in _TRUTHY


def agents_with_turn_evidence() -> set[str] | None:
    """The set of ``agent_id`` s Prometheus has observed emitting turns.

    ``None`` means *evidence unknown* — the read is disabled, or the metrics store is
    unreachable — in which case the level trusts the declared contract. A returned set is
    authoritative: an agent absent from it (with the store reachable) has no observed turns.
    """
    if not turn_evidence_enabled():
        return None
    try:
        rows = PrometheusAdapter().instant(f"sum by (agent_id) ({_TURNS_METRIC})")
    except SpineUnavailableError:
        return None
    observed: set[str] = set()
    for row in rows:
        metric = row.get("metric")
        value = row.get("value")
        if not isinstance(metric, dict) or not isinstance(value, list) or len(value) != _SAMPLE_LEN:
            continue
        agent_id = metric.get("agent_id")
        try:
            count = float(value[1])
        except (TypeError, ValueError):
            # best-effort: skip a Prometheus sample value that won't parse — non-gating (0015)
            continue
        if isinstance(agent_id, str) and agent_id and count > 0:
            observed.add(agent_id)
    return observed


def recent_turn_evidence(
    since: datetime,
    *,
    until: datetime | None = None,
    adapter: PrometheusAdapter | None = None,
) -> dict[str, datetime]:
    """Last observed turn-counter increment per agent inside a bounded window.

    This is the time-aware sibling of :func:`agents_with_turn_evidence`. The cumulative instant
    vector can prove that an agent emitted *at some point in retention* but cannot support the
    `/comprendre` contract "observed during the last 24 hours". A Prometheus range query over
    ``increase`` interrogates the same fleet evidence seam without pretending that a process
    counter's current value has a date.

    Args:
        since: Inclusive aware lower bound.
        until: Inclusive aware upper bound; defaults to now in UTC.
        adapter: Optional spine adapter override for tests.

    Returns:
        A mapping from agent id to the timestamp of its latest positive counter increase.

    Raises:
        ValueError: If either bound is timezone-naive or the window is inverted.
        SpineUnavailableError: Propagated when the Prometheus spine cannot be read.
    """
    end = until or datetime.now(UTC)
    if since.tzinfo is None or end.tzinfo is None:
        msg = "recent turn-evidence bounds must be timezone-aware"
        raise ValueError(msg)
    if end < since:
        msg = "recent turn-evidence window is inverted"
        raise ValueError(msg)
    reader = adapter or PrometheusAdapter()
    query = f"sum by (agent_id) (increase({_TURNS_METRIC}[{_RECENT_INCREASE_RANGE}])) > 0"
    rows = reader.range(
        query,
        start=since.isoformat(),
        end=end.isoformat(),
        step=_RECENT_STEP,
    )
    observed: dict[str, datetime] = {}
    for row in rows:
        metric = row.get("metric")
        values = row.get("values")
        if not isinstance(metric, dict) or not isinstance(values, list):
            continue
        agent_id = metric.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            continue
        for point in values:
            if not isinstance(point, list | tuple) or len(point) != _SAMPLE_LEN:
                continue
            try:
                stamp = datetime.fromtimestamp(float(point[0]), tz=UTC)
                increase = float(point[1])
            except (TypeError, ValueError, OSError):
                continue
            if increase <= 0 or stamp < since or stamp > end:
                continue
            previous = observed.get(agent_id)
            if previous is None or stamp > previous:
                observed[agent_id] = stamp
    return observed


@dataclass(frozen=True, slots=True)
class TurnWindow:
    """The turns a set of ledger rows proves, and whether the rows could be dated at all.

    ``turns`` empty is NOT automatically "this agent emitted nothing": rows carrying no parsable
    instant are counted separately, because a timestamp format this parser does not understand
    would otherwise empty the window silently and read as dormancy. The ledger writes UTC with
    an offset in-process and ``DateTime64`` without one through ClickHouse; both parse here, and
    a third form arriving one day must announce itself as illegible rather than as absence.
    """

    turns: frozenset[str]
    rows_seen: int
    rows_undated: int

    @property
    def legible(self) -> bool:
        """False when rows existed and none of them carried a usable instant — *cannot say*."""
        return self.rows_seen == 0 or self.rows_undated < self.rows_seen


def _instant(value: object) -> datetime | None:
    """Parse a ledger row's timestamp, naive read as UTC — the convention the writer uses.

    ``clickhouse_business_events._clickhouse_datetime`` stamps rows as UTC and drops the offset
    on the way in; reading a naive value back as anything else would shift every row by the
    local offset and silently move the window.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)


def turns_in_window(
    rows: Iterable[Mapping[str, object]],
    *,
    since: datetime,
    until: datetime | None = None,
) -> TurnWindow:
    """The distinct ``turn_id`` s these ledger rows prove inside the window (pure, no I/O).

    Counts **turns**, not events: the Prometheus counter it stands in for counts turns, and a
    single turn emitting thirty events must not read as thirty proofs of anything. Bounded above
    as well as below — an event dated in the future is a clock, not an emission.

    Args:
        rows: Serialised business-event rows (``business_event_read(...).rows``).
        since: Inclusive aware lower bound.
        until: Inclusive aware upper bound; defaults to now in UTC.

    Returns:
        The turns found, plus enough counts to tell "none in the window" from "none datable".
    """
    end = until or datetime.now(UTC)
    turns: set[str] = set()
    seen = 0
    undated = 0
    for row in rows:
        seen += 1
        stamp = _instant(row.get("timestamp") or row.get("occurred_at"))
        if stamp is None:
            undated += 1
            continue
        if stamp < since or stamp > end:
            continue
        turn_id = row.get("turn_id")
        if isinstance(turn_id, str) and turn_id:
            turns.add(turn_id)
    return TurnWindow(turns=frozenset(turns), rows_seen=seen, rows_undated=undated)


def ledger_turn_evidence(agent_id: str, *, now: datetime | None = None) -> TurnEvidence:
    """What the business-event ledger says about ``agent_id`` serving a turn inside the window.

    Returns the SAME three-valued vocabulary the Prometheus source speaks, deliberately: the two
    are merged, and a merge whose inputs use different alphabets is where the "did it look?" bit
    gets dropped. ``unverifiable`` is the store unreachable, or answering with rows none of which
    could be dated — both are blindness, and blindness is never dormancy.

    Synthetic (canary) events are excluded by the read seam's default (ADR 0019 §4), so a canary
    turn can never manufacture the evidence that unlocks a rung — the exclusion is inherited
    here rather than restated, which is why this calls the seam and not the store.
    """
    from tessera.observability import business_events

    end = now or datetime.now(UTC)
    read = business_events.business_event_read(agent_id=agent_id)
    if read.blind:
        return "unverifiable"
    window = turns_in_window(read.rows, since=end - RECENCY_WINDOW, until=end)
    if not window.legible:
        return "unverifiable"
    return "observed" if window.turns else "dormant"


def agents_with_ledger_turns(*, now: datetime | None = None) -> set[str] | None:
    """The ``agent_id`` s the ledger proves served a turn inside the window — one whole-fleet read.

    The grouped sibling of :func:`ledger_turn_evidence`, for the fleet loop: one read for every
    card instead of one per card. ``None`` when the store did not answer, or when it answered
    with rows that carry no usable instant.
    """
    from tessera.observability import business_events

    end = now or datetime.now(UTC)
    read = business_events.business_event_read()
    if read.blind:
        return None
    since = end - RECENCY_WINDOW
    by_agent: dict[str, list[Mapping[str, object]]] = {}
    for row in read.rows:
        agent_id = row.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            by_agent.setdefault(agent_id, []).append(row)
    if not by_agent:
        return set()
    emitting: set[str] = set()
    legible_anywhere = False
    for agent_id, rows in by_agent.items():
        window = turns_in_window(rows, since=since, until=end)
        legible_anywhere = legible_anywhere or window.legible
        if window.turns:
            emitting.add(agent_id)
    # Rows existed and not one of them could be dated: the store answered, but not with facts
    # this read understands. Reporting an empty set would publish that as fleet-wide dormancy.
    return emitting if legible_anywhere else None


class _Unread:
    """Sentinel — this source was not handed in, so read it.

    Distinct from ``None``, which a source uses to say *I looked and could not see*. The two were
    one value on ``observed`` and it worked only by luck (re-reading an unreachable store fails
    the same way twice). Merging a second source makes the confusion load-bearing, so it is named.
    """

    __slots__ = ()


_UNREAD: Final = _Unread()


def turn_evidence_state(
    agent_id: str | None,
    observed: set[str] | None = None,
    *,
    emitting: set[str] | None | _Unread = _UNREAD,
) -> TurnEvidence:
    """Why the cockpit does or does not have turn evidence for ``agent_id``.

    - ``observed`` — a store was read and proves this agent served turns. The only proof.
    - ``unverifiable`` — no store could answer, or the only one that answered saw nothing while
      the other stayed silent. Nothing is known.
    - ``dormant`` — **every** source answered and none of them has a turn for this agent.

    Two sources are merged (§4 Amendment 3), and the merge is deliberately asymmetric::

        counter        ledger          verdict
        ─────────────  ──────────────  ──────────────
        has turns      *               observed
        *              has turns       observed
        no turns       no turns        dormant
        no turns       blind           unverifiable   ← the widening's cost, paid honestly
        blind          no turns        unverifiable
        blind          blind           unverifiable

    The fourth row is the one that matters. Before the ledger counted, the counter's silence
    *was* the answer; now that a second source can contradict it, one source's silence proves
    absence only when the other could be asked. Anything else would let a ClickHouse outage
    quietly demote an agent — the ADR 0026 failure this project keeps re-finding.

    Pass pre-fetched sets to check a whole fleet against one read of each store
    (:func:`agents_with_turn_evidence`, :func:`agents_with_ledger_turns`); omit them for a
    single-agent resolve. ``None`` means *that store was read and could not see*; omitting the
    argument means *read it for me*.
    """
    if observed is None:
        observed = agents_with_turn_evidence()
    counter = _state_from_set(agent_id, observed)

    if isinstance(emitting, _Unread):
        ledger = ledger_turn_evidence(agent_id) if agent_id else "unverifiable"
    else:
        ledger = _state_from_set(agent_id, emitting)

    if "observed" in (counter, ledger):
        return "observed"
    # Neither store proves a turn. Only claim dormancy if BOTH of them actually looked: with two
    # sources, one source's silence is not absence unless the other could be asked.
    return "dormant" if counter == ledger == "dormant" else "unverifiable"


def _state_from_set(agent_id: str | None, membership: set[str] | None) -> TurnEvidence:
    """Turn one store's pre-fetched answer into the shared vocabulary.

    ``None`` is *that store could not see* — never *this agent emitted nothing*. Collapsing the
    two is the bug this whole module is shaped against.
    """
    if membership is None:
        return "unverifiable"
    return "observed" if agent_id and agent_id in membership else "dormant"


def turn_evidence_sources(agent_id: str | None) -> dict[str, TurnEvidence]:
    """What each source said on its own — for diagnosis, never for a verdict.

    A surface explaining *why* an agent sits at a rung reads this; a gate reads
    :func:`turn_evidence_state` and nothing else, because only the merge knows that one store's
    dormancy plus another's blindness is not dormancy.
    """
    return {
        "counter": _state_from_set(agent_id, agents_with_turn_evidence()),
        "ledger": ledger_turn_evidence(agent_id) if agent_id else "unverifiable",
    }


def has_turn_evidence(agent_id: str | None, observed: set[str] | None = None) -> bool:
    """Whether the cockpit has **observed** turns for ``agent_id`` — proof, never assumption.

    Evidence-unknown is not evidence. Callers that want to show what the manifest promises
    read the declared rung separately; they never obtain it by trusting a silent store.
    """
    return turn_evidence_state(agent_id, observed) == "observed"
