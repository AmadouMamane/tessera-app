"""Observability routes — the stack's components, as the preflight witness sees them.

``/fr/surveiller/observabilite`` rendered four KPI cards whose only health inputs were
``/healthz`` and ``/readyz``: two probes about the agent process, collapsed into one green dot.
Its own contextual help promised something else — *"commencez par la composante indisponible ou
dégradée, puis lisez sa dernière vérification et les dépendances touchées"* — and the link that
leads there is labelled *"Voir les composants santé"*. There were no components on it.

The consequence was not cosmetic. On 2026-08-05 ``tessera.preflight`` reported ClickHouse
``FAIL`` (``403 AUTHENTICATION_FAILED``) while that page showed everything operational, because
nothing it rendered could go red for a dependency. A page that cannot express a dependency
failure is not a monitoring page.

This exposes the prober that already existed and was wired to nothing but a CLI.
:func:`tessera.preflight.run_preflight` interrogates each dependency **by its own adapter**
(ADR 0026 — the eval archive through the loader the dashboards call, Postgres through the
ledger's ``connect``, ClickHouse/Prometheus/Ollama through theirs), never a neighbour, and it
distinguishes three outcomes where a dashboard usually has two:

* ``ok``    — it looked, and the answer was good;
* ``fail``  — it looked, and the answer was bad;
* ``blind`` — it could not look at all, which is **not** ``ok`` and not ``fail``.

That third state is the reason this endpoint is worth having rather than a green/red boolean.

**Cost.** These are live probes — a socket to Postgres, an HTTP round-trip to ClickHouse and
Prometheus, a model-list call to Ollama with a 4 s ceiling. The dashboard polls, so the result
is cached for :data:`_TTL_S` and computed off the event loop. The cache stores the *observation
time* alongside the report and the payload publishes it: a component list that does not say
when it was last checked invites the reader to assume "now", which is the failure this whole
surface exists to stop.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Final

from fastapi import APIRouter, Depends, Query

from tessera.api.security import require_bearer
from tessera.observability import component_history, probe_scheduler, quality_nets
from tessera.observability.langfuse_obs import langfuse_read_health
from tessera.observability.stack_components import (
    STACK_COMPONENTS,
    StackObservation,
    is_loopback,
    probe_stack_observations,
    ui_url,
)
from tessera.observability.stack_topology import (
    AGENT_NODE,
    CHAIN_EDGES,
    CHAIN_NODES,
    CONSEQUENCES,
    consequence_because,
    consequence_states,
    reachable_signals,
)
from tessera.preflight import Check, PreflightReport, Verdict, run_preflight

router = APIRouter()

#: Seconds a probe result is reused. Short enough that an operator watching a component come
#: back sees it within one poll, long enough that a 10 s dashboard poll does not open a
#: Postgres connection and four sockets per viewer.
_TTL_S: Final = 15.0

#: Wall clock, not monotonic: the value is PUBLISHED to a browser that will render it as a
#: time, so it has to mean something outside this process.
_cache: tuple[float, PreflightReport] | None = None
_cache_lock = Lock()

_stack_cache: tuple[float, tuple[StackObservation, ...]] | None = None
_stack_cache_lock = Lock()

#: What each stack component is, in the operator's words — read from the declaration so the
#: page and the registry cannot drift into two answers.
_STACK_ROLES: Final[dict[str, str]] = {c.key: c.role for c in STACK_COMPONENTS}

#: What was PUT TO each stack component, DERIVED from how it is probed rather than written out.
#: A second hand-maintained sentence per component is a second thing to get wrong, and this one
#: has exactly one right answer already sitting in the declaration: the protocol, and the path
#: for HTTP. The surface translates it; this is the fallback and the machine-readable form.
_STACK_QUESTIONS: Final[dict[str, str]] = {
    c.key: (f"HTTP GET {c.path or '/'}" if c.kind == "http" else "TCP connect")
    for c in STACK_COMPONENTS
}

#: What each check actually interrogates — the evidence, so a reader can tell a dependency
#: being down from a probe that never ran. Keyed by ``Check.name``; an unknown name degrades to
#: no subtitle rather than to a guess.
_INTERROGATES: Final[dict[str, str]] = {
    "eval-package": "import eval, import eval.runner",
    "eval-reports": "the report loader the dashboards call",
    "app-factory": "build_app()",
    "operator-key": "the operator assertion signing key",
    "postgres": "ln.connect — the ledger store's own connection",
    "clickhouse": "the ClickHouse adapter's own HTTP read",
    "prometheus": "the Prometheus adapter's own query",
    "ollama": "the chat backend's model list",
}

_HEADLINE: Final[dict[int, str]] = {0: "clear", 1: "fail", 2: "blind"}

#: Stack components whose preflight twin performs an ADAPTER-LEVEL read (the ledger's own
#: ``connect``, the ClickHouse adapter's HTTP read, the Prometheus adapter's query). For these,
#: a capability's state merges the socket verdict with the read verdict — the port being open is
#: the neighbourhood, the read is the thing (ADR 0026). The morning of 2026-08-05 is the proof:
#: ClickHouse accepted connections while refusing its credentials.
_READ_WITNESSES: Final = frozenset({"postgres", "clickhouse", "prometheus"})


def _read_observations(report: PreflightReport) -> dict[str, tuple[Verdict, str]]:
    """Component key → its own READ path's verdict AND the sentence that earned it.

    Preflight supplies three (postgres / clickhouse / prometheus — each check IS the adapter's
    read); Langfuse gets its own, because its socket said OK on 2026-08-06 while this process
    could not complete one authenticated read and the overview page said so — two cockpit
    surfaces contradicting each other about one system.

    The sentence travels with the verdict because of what the operator asked next, on
    2026-08-07: *"why is langfuse-web the problem when I can see it is OK in the list below?"*
    A page that carries the read verdict only into the CONSEQUENCES makes the component table
    and the consequence block disagree in plain sight, and leaves the reader to guess that the
    two are answering different questions. So the read rides on the component's own row.
    """
    reads = {
        check.name: (check.verdict, check.detail)
        for check in report.checks
        if check.name in _READ_WITNESSES
    }
    health = langfuse_read_health()
    reads["langfuse-web"] = (health.verdict, health.detail)
    return reads


def _read_verdicts(report: PreflightReport) -> dict[str, Verdict]:
    """Just the verdicts — what the capability merge consumes."""
    return {key: verdict for key, (verdict, _) in _read_observations(report).items()}


def probe_for_scheduler() -> float:
    """One scheduler beat: ensure a fresh stack observation exists, then stamp liveness.

    Runs through the same cache as the page's own reads, so a beat landing just after a page
    poll reuses its observation instead of opening a second round of sockets — and the journal write
    stays where it belongs, on the actual probe. The stamp is written on every beat regardless:
    it vouches for the LOOP being alive, which is a different fact from an observation having
    happened, and the history endpoint reports it as such.
    """
    observed_at, _ = _stack()
    probe_scheduler.write_stamp()
    return observed_at


def _probe() -> tuple[float, PreflightReport]:
    """Run both witnesses, off the event loop, at most once per TTL."""
    global _cache
    with _cache_lock:
        cached = _cache
        if cached is not None and (time.time() - cached[0]) < _TTL_S:
            return cached
    # Deliberately outside the lock: a probe takes seconds, and holding the lock across it
    # would serialise every concurrent reader behind one round-trip. The worst case is two
    # concurrent probes on a cold cache, which is cheaper than a queue of blocked requests.
    observed_at = time.time()
    report = run_preflight()
    with _cache_lock:
        _cache = (observed_at, report)
    return _cache


def _stack() -> tuple[float, tuple[StackObservation, ...]]:
    """The declared stack components, cached on the same TTL as the preconditions."""
    global _stack_cache
    with _stack_cache_lock:
        cached = _stack_cache
        if cached is not None and (time.time() - cached[0]) < _TTL_S:
            return cached
    observed_at = time.time()
    checks = probe_stack_observations()
    with _stack_cache_lock:
        _stack_cache = (observed_at, checks)
    # Journalled HERE, on the cache MISS, because this is where an observation actually
    # happened. Recording on every request would count cache hits as looks, and the history's
    # whole value is that it distinguishes "watched and steady" from "nobody was looking".
    component_history.record_observation(
        {o.check.name: o.check.verdict.value for o in checks},
        at=datetime.fromtimestamp(observed_at, tz=UTC),
    )
    return _stack_cache


@router.get("/observability/components", dependencies=[Depends(require_bearer)])
async def observability_components() -> dict[str, object]:
    """Every declared component, what was interrogated, and what it answered.

    Returns:
        ``components`` — one entry per check, each carrying ``name``, ``verdict``
        (``ok``/``fail``/``blind``/``skip``), ``detail`` (the probe's own evidence) and
        ``interrogates``; ``verdict`` — the headline (``clear``/``fail``/``blind``), which is
        ``blind`` whenever any check could not look, never ``clear``; and ``observed_at``, the
        instant the probe actually ran, which is NOT the instant of this request.
    """
    observed_at, report = await asyncio.to_thread(_probe)
    _, observations = await asyncio.to_thread(_stack)
    stack = tuple(o.check for o in observations)
    #: Outcome code + the machine's own words, per component. The English sentence in
    #: ``Check.detail`` stays too (the CLI prints it); the surface prefers these, because a
    #: French page rendering "postgres:5432 accepts connections" is showing OUR prose untranslated.
    outcomes = {o.check.name: o for o in observations}
    # Adapter-level reads join the socket verdicts (they can only degrade, never improve): the
    # Langfuse leg is a live authenticated round-trip, so it runs off the event loop with the
    # other probes rather than blocking it for its 3 s timeout.
    read_obs = await asyncio.to_thread(_read_observations, report)

    def entry(check: Check, group: str, *, role: str, asked: str) -> dict[str, object]:
        """One row, with the three facts kept apart instead of two of them sharing a cell.

        They were not distinct before, and the table said so: one column headed *"ce qui est
        interrogé"* held the component's ROLE for a stack row and the QUESTION for a
        precondition row — two different meanings under one heading. Beside it, *"ce qu'il a
        répondu"* showed ``detail``, which for ``eval-package`` is literally the question again:
        ``import eval, import eval.runner`` in both cells.

        * ``role``  — what the thing IS. Empty for a precondition: a precondition is not a thing.
        * ``asked`` — what was PUT TO IT. Derived for a stack component (it is a property of the
          probe, not prose to maintain), declared for a precondition.
        * ``detail`` — what came BACK, in the probe's own words. Left verbatim, because it is the
          evidence; the surface hides it when it merely echoes the question.
        """
        seen = outcomes.get(check.name) if group == "stack" else None
        # The SECOND witness on this component, when one exists: not "does the port answer"
        # but "can the adapter that uses it actually read". Carried on the stack row only —
        # a precondition IS that read, and repeating it against itself would say nothing.
        read = read_obs.get(check.name) if group == "stack" else None
        return {
            "name": check.name,
            "group": group,
            "verdict": check.verdict.value,
            "detail": check.detail,
            "role": role,
            "asked": asked,
            # Absent (``None``) means NO read witness exists for this component — which is not
            # the same claim as a read that came back fine, and the surface must not render the
            # two the same way.
            "read": ({"verdict": read[0].value, "detail": read[1]} if read is not None else None),
            # What the probe found, as a CODE the surface can say in the reader's language, and
            # the machine's own words kept apart from it. Absent for a precondition: preflight
            # is a CLI witness whose line is read in a terminal, and paraphrasing it here would
            # make the page and the terminal disagree about the same check.
            "outcome": seen.outcome if seen else "",
            "address": seen.address if seen else "",
            "raw": seen.raw if seen else "",
            # Kept so an older client keeps rendering something rather than an empty column.
            "interrogates": asked,
        }

    components = [
        entry(
            check,
            "stack",
            role=_STACK_ROLES.get(check.name, ""),
            asked=_STACK_QUESTIONS.get(check.name, ""),
        )
        for check in stack
    ] + [
        entry(check, "precondition", role="", asked=_INTERROGATES.get(check.name, ""))
        for check in report.checks
    ]
    every = (*stack, *report.checks)
    fail = sum(1 for c in every if c.verdict is Verdict.FAIL)
    blind = sum(1 for c in every if c.verdict is Verdict.BLIND)
    verdicts = {check.name: check.verdict for check in stack}
    read_checks = {key: verdict for key, (verdict, _) in read_obs.items()}
    states = consequence_states(verdicts, read_checks)
    because = consequence_because(verdicts, read_checks)
    return {
        "observed_at": observed_at,
        # A FAIL anywhere outranks a blind spot: "something is down" is the actionable one.
        # Blind never yields "clear" — the reason this surface has three states.
        "verdict": "fail" if fail else ("blind" if blind else "clear"),
        "counts": {
            "total": len(every),
            "ok": sum(1 for c in every if c.verdict is Verdict.OK),
            "fail": fail,
            "blind": blind,
            # The operator's stack, counted on its own: the preconditions are a different
            # question and folding them together would hide which half moved.
            #
            # Every one of these is published per half, not just `ok`, because a headline that
            # opens "I observe {stack_ok}/{stack_total} STACK components" and then continues
            # "· {blind} unreadable" from the whole-of-everything tally is two scopes in one
            # sentence. It read correctly only while every precondition was green — the
            # infalsifiable shape: wrong, and unable to show it until something else moved.
            "stack_total": len(stack),
            "stack_ok": sum(1 for c in stack if c.verdict is Verdict.OK),
            "stack_fail": sum(1 for c in stack if c.verdict is Verdict.FAIL),
            "stack_blind": sum(1 for c in stack if c.verdict is Verdict.BLIND),
            "precondition_total": len(report.checks),
            "precondition_ok": sum(1 for c in report.checks if c.verdict is Verdict.OK),
        },
        "components": components,
        # The chain, so the page can show that one dead node explains three red rows. Nodes and
        # edges are declared (stack_topology); the verdicts joined onto them are the live probe's.
        "chain": {
            "nodes": [
                {
                    "key": node.key,
                    "stage": node.stage,
                    "carries": list(node.carries),
                    # The emitter is not probed from outside: this very response is its proof.
                    # Stated, not inferred, so a reader knows why one node cannot go red here.
                    "verdict": "ok"
                    if node.key == AGENT_NODE
                    else verdicts[node.key].value
                    if node.key in verdicts
                    else "blind",
                    "self_evident": node.key == AGENT_NODE,
                }
                for node in CHAIN_NODES
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "signal": edge.signal,
                    "declared_in": edge.declared_in,
                    "profile": edge.profile,
                }
                for edge in CHAIN_EDGES
            ],
            "signals": reachable_signals(verdicts),
        },
        # What each store underwrites, and whether it still does. The capability is declared
        # (it is a fact about this codebase, and `reads` cites the module); the STATE is
        # computed from the probe above and never asserted.
        "consequences": [
            {
                "key": consequence.key,
                "needs": list(consequence.needs),
                "reads": consequence.reads,
                "gates_agents": consequence.gates_agents,
                "state": states[consequence.key],
                # Which dependency is responsible — so the row names a component to restart
                # instead of leaving the operator to intersect two lists by eye. Same merge as
                # the state (socket ⊕ its own read), so the two can never disagree.
                "because": because[consequence.key],
                # The dependencies whose verdict includes an adapter-level READ this cycle —
                # named, so "assurée" over a socket-only check cannot be mistaken for the
                # stronger claim.
                "checked_by_read": [need for need in consequence.needs if need in read_checks],
            }
            for consequence in CONSEQUENCES
        ],
        # Where a browser opens each tool. `loopback` is a fact about the URL, not a
        # recommendation: the caller compares it with its own vantage point before offering a
        # live link, because a loopback address is only true on the deployment host.
        "links": [
            {"key": component.key, "url": url, "loopback": is_loopback(url)}
            for component in STACK_COMPONENTS
            if (url := ui_url(component))
        ],
    }


#: Windows the history card offers. Bounded to a declared set rather than accepting any integer:
#: an unbounded window over a file-backed journal is a way to ask one reader to parse everything.
_HISTORY_DAYS: Final = (1, 7, 30)


@router.get("/observability/component-history", dependencies=[Depends(require_bearer)])
async def observability_component_history(
    days: int = Query(1, ge=1, le=max(_HISTORY_DAYS)),
) -> dict[str, object]:
    """Availability and verdict CHANGES per component over the last ``days``.

    The dimension the live probe cannot have. Read the numbers with ``observed_ratio``: the probe
    runs when the cockpit asks, so a window is watched in patches, and every percentage below is
    a share of **observed** time, not of wall-clock time. ``observed_ratio`` is how much of the
    window was watched at all; where it is low, the availability figure is a true statement about
    a small sample and says nothing about the rest — which is why both travel together and the UI
    may not render one without the other.

    Returns:
        ``availability`` — per component, seconds in each verdict plus the observed share;
        ``transitions`` — every verdict change inside the window, newest first, each flagged
        ``after_gap`` when it was *discovered* after a hole rather than witnessed;
        ``window`` — the bounds actually used.
    """
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    phases = await asyncio.to_thread(component_history.load_phases)
    stats = component_history.availability(since=start, until=end, phases=phases)
    changes = component_history.transitions(since=start, until=end, phases=phases)
    visible = component_history.clipped_phases(since=start, until=end, phases=phases)
    return {
        "window": {"since": start.isoformat(), "until": end.isoformat(), "days": days},
        # The phases themselves, clipped to the window — what a timeline draws. The totals
        # above cannot say WHEN the fail was, and "when" is the question an operator opens
        # this window with.
        "phases": [
            {
                "component": phase.component,
                "verdict": phase.verdict,
                "since": phase.since,
                "until": phase.until,
                "n_observations": phase.n_observations,
            }
            for phase in visible
        ],
        # The scheduler's own heartbeat (ADR 0052 §Amendment 1) — derived from the stamp the
        # loop writes, never from configuration, so a dead leader reads as `stale` and not as
        # "scheduled". `never` + a configured interval means the first beat has not landed.
        "probe": probe_scheduler.scheduler_report(),
        "availability": [
            {
                "component": stat.component,
                "seconds_by_verdict": stat.seconds_by_verdict,
                "observed_seconds": round(stat.observed_seconds, 1),
                # Observed time in which the probe reached a verdict about the component. The
                # denominator of `ok_ratio`, published so a reader can see what the percentage
                # is a percentage OF — blind minutes are observed and are not decidable.
                "decidable_seconds": round(stat.decidable_seconds, 1),
                "window_seconds": round(stat.window_seconds, 1),
                "observed_ratio": round(stat.observed_ratio, 4),
                # None when nothing was DECIDABLE — never 0 or 1, both of which are claims the
                # record cannot support. A window watched entirely through a blind spot yields
                # None, not 0 %.
                "ok_ratio": None if stat.ok_ratio is None else round(stat.ok_ratio, 4),
            }
            for stat in sorted(stats.values(), key=lambda s: s.component)
        ],
        "transitions": [
            {
                "component": change.component,
                "from": change.from_verdict,
                "to": change.to_verdict,
                "at": change.at,
                "after_gap": change.after_gap,
            }
            for change in changes
        ],
        "continuity_window_s": component_history.CONTINUITY_WINDOW.total_seconds(),
    }


@router.get("/observability/instrumentation-coverage", dependencies=[Depends(require_bearer)])
async def observability_instrumentation_coverage() -> dict[str, object]:
    """Signal 92 for the whole fleet — how much of the L1 span contract each agent stamps.

    Existed per agent since step 6b (``/observability/quality-nets?agent=…``) and was therefore
    unaskable by any surface that shows a fleet. ``blind`` true means the store did not answer:
    every agent then reads ``unverifiable`` and no percentage may be rendered, because a store
    that is down produces exactly the same empty rows as an agent that emits nothing.
    """
    return await asyncio.to_thread(quality_nets.fleet_coverage)
