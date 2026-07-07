"""Phase 2 — Table A.3 wiring proof: graph / trace / tool structure (ADR 0010).

Eight signals from ``docs/design/signal-wiring-map.md`` Table A.3, each declared
``real-computed`` and a priori pure or bundle-injectable at the route seam (no
alias/freeze like the Table D negative controls, e.g. ``embedding_skew``). Every
probe's ``compute`` reproduces the *route's* source assembly in
``src/tessera/api/routes/observability.py`` — the exact list-comprehension or call
the endpoint makes — before calling the module's pure function, per the
load-bearing rule in the map (test the signal *as wired*, not the naked provider):

* #86  reproducibility-hash        — ``reproducibility.py:detect_nondeterminism``
* #87  graph-topology-versioning   — ``graph_topology.py:compare_topology``
* #41  golden-snapshot-ci          — ``trace_snapshot.py:diff_traces``
* #189 handoff-tracing             — ``handoffs.py:analyze_handoffs``
* #89  context-overflow            — ``context_overflow.py:analyze_overflow``
* #88  tool-loop-detection         — ``tool_loops.py:detect_loops``
* #47  schema-conformance          — ``conformance.py:compute_conformance``
* #1   trace-replay                — ``replay.py:replay``

#86/#41/#189 share one route transform (``routes/observability.py`` lines
514-518 / 2065-2069 / 2730-2734): ``[(b.question, list((b.latency_ms or {}).keys()))
for b in replay_mod.recent_bundles()]`` — the "executed nodes" of a turn are the
*keys* of its captured per-node latency map, in insertion (execution) order. #89
uses the sibling transform at lines 2493-2499 (paragraph-split ``context``). #88's
``detect_loops`` takes a plain ``{stream: [tools]}`` dict — the route (lines
2543-2559) assembles it from the audit trail, but the provider itself is a pure
fn-arg consumer, so the dict is the honest seam to perturb (the same treatment
Phase 1 gave ``aggregate_leaks``' turn tuples). #47 perturbs a real temporary
ledger file through ``compute_conformance(path=...)`` (``unit+temp``, seam=store)
— the route call at line 2490 is reproduced verbatim, including ``at=None,
agent_id=None``. #1 mirrors the *existing* ``test_observability_replay.py``
mechanism exactly (a directly constructed ``ReplayBundle`` plus an injectable stub
backend/judge) rather than opening a real Postgres/LLM connection — see the
probe's comment for the seam divergence this implies versus the map's
``store``/``integration`` label (flagged, not silently upgraded).
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from tessera.agent.graph import build_graph
from tessera.agent.sdk import graph_topology as graph_topology_mod
from tessera.llm.router import ChatResponse
from tessera.observability import (
    conformance as conformance_mod,
    context_overflow as context_overflow_mod,
    handoffs as handoffs_mod,
    reproducibility as reproducibility_mod,
    tool_loops as tool_loops_mod,
    trace_snapshot as trace_snapshot_mod,
)
from tessera.observability.eval.judge import JudgeVerdict
from tessera.observability.replay import ReplayBundle, ReplayResult, replay as replay_fn
from tests.support.wiring import Probe, assert_wired

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from pathlib import Path

    from tessera.agent.sdk.graph_topology import AgentStateGraph, TopologyDrift
    from tessera.llm.router import ChatMessage
    from tessera.observability.conformance import ConformanceReport
    from tessera.observability.context_overflow import OverflowReport
    from tessera.observability.handoffs import HandoffReport
    from tessera.observability.reproducibility import ReproReport
    from tessera.observability.tool_loops import LoopReport
    from tessera.observability.trace_snapshot import SnapshotDiffReport

# --------------------------------------------------------------------------- #
# Shared bundle/turn builders — the object and transform ``recent_bundles()``-
# backed routes actually use (routes/observability.py:514-518/2065-2069/2730-2734).
# --------------------------------------------------------------------------- #


def _bundle(
    question: str,
    *,
    latency_ms: dict[str, float] | None = None,
    context: str = "",
) -> ReplayBundle:
    """A minimal, route-shaped ``ReplayBundle`` — what ``recent_bundles()`` returns."""
    return ReplayBundle(
        bundle_id=uuid.uuid4().hex,
        captured_at="2026-01-01T00:00:00+00:00",
        conversation_id=None,
        language="fr",
        question=question,
        context=context,
        original_answer="",
        original_model="test-model",
        original_score=0.8,
        latency_ms=latency_ms,
    )


def _turns_from_bundles(bundles: list[ReplayBundle]) -> list[tuple[str, list[str]]]:
    """The #86/#41/#189 route transform: executed nodes = latency-map keys, in order."""
    return [(b.question, list((b.latency_ms or {}).keys())) for b in bundles]


def _overflow_turns(bundles: list[ReplayBundle]) -> list[tuple[str, list[str]]]:
    """The #89 route transform (routes/observability.py:2496-2498): paragraph chunks."""
    return [(b.question, [c for c in b.context.split("\n\n") if c.strip()]) for b in bundles]


# --------------------------------------------------------------------------- #
# Observers — payload -> scalar (named functions, mirroring Phase 1's convention
# so mypy --strict infers each without lambda-context guessing).
# --------------------------------------------------------------------------- #


def _obs_n_nondeterministic(payload: object) -> int:
    return cast("ReproReport", payload).n_nondeterministic


def _obs_drifted(payload: object) -> bool:
    return cast("TopologyDrift", payload).drifted


def _obs_n_drifted(payload: object) -> int:
    return cast("SnapshotDiffReport", payload).n_drifted


def _obs_total_broken(payload: object) -> int:
    return cast("HandoffReport", payload).total_broken


def _obs_overflow_rate(payload: object) -> float:
    return cast("OverflowReport", payload).overflow_rate


def _obs_n_loops(payload: object) -> int:
    return cast("LoopReport", payload).n_loops


def _obs_conformance_rate(payload: object) -> float:
    return cast("ConformanceReport", payload).conformance_rate


def _obs_score_delta(payload: object) -> float:
    return cast("ReplayResult", payload).score_delta


# --------------------------------------------------------------------------- #
# #86 reproducibility-hash. Route (routes/observability.py:514-518): turns from
# recent_bundles() -> detect_nondeterminism(turns). Perturbation: append the SAME
# (normalised) question with a genuinely different executed-node sequence -> that
# repeat group now has >1 shape -> n_nondeterministic changes 0 -> 1.
# --------------------------------------------------------------------------- #

_REPRO_BASE: list[ReplayBundle] = [
    _bundle(
        "Quel est mon solde ?",
        latency_ms={"router": 5.0, "planner": 8.0, "account_lookup": 12.0, "reviewer": 3.0},
    ),
]


def _repro_compute(bundles: list[ReplayBundle]) -> object:
    return reproducibility_mod.detect_nondeterminism(_turns_from_bundles(bundles))


def _repro_perturb(bundles: list[ReplayBundle]) -> list[ReplayBundle]:
    divergent = _bundle(
        "quel est mon solde ?",  # normalises equal to the base question (lower/whitespace)
        latency_ms={"router": 4.0, "planner": 7.0, "reviewer": 3.0},  # skips account_lookup
    )
    return [*bundles, divergent]


_repro_probe: Probe[list[ReplayBundle]] = Probe(
    key="reproducibility-hash#86",
    compute=_repro_compute,
    observe=_obs_n_nondeterministic,
    base_source=_REPRO_BASE,
    perturb=_repro_perturb,
    relation="changes",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# #87 graph-topology-versioning. Route (routes/observability.py:2516-2525):
# topology_snapshot(build_graph()) -> compare_topology(snapshot, golden=...).
# topology_snapshot only reads .nodes/.edges/.branches (graph_topology.py:63-97),
# so a duck-typed proxy of the REAL build_graph() output with one node pruned
# reproduces the pure fingerprinting exactly while embodying "the graph was
# reshaped" -> drift.drifted changes False -> True. No route caching (unlike
# #85's span-propagation probe), so build_graph() itself is the honest fn-arg
# source, verified empirically (dry run) rather than assumed from the map.
# --------------------------------------------------------------------------- #


def _prune_node(graph: AgentStateGraph, drop: str) -> AgentStateGraph:
    """Duck-typed copy of ``graph`` with node ``drop`` removed from nodes/edges/branches."""
    branches_raw = getattr(graph, "branches", {}) or {}
    pruned_branches: dict[str, dict[str, SimpleNamespace]] = {}
    for source, named in branches_raw.items():
        if source == drop:
            continue
        pruned_named: dict[str, SimpleNamespace] = {}
        for name, branch in named.items():
            ends = getattr(branch, "ends", None) or {}
            pruned_named[name] = SimpleNamespace(ends={k: v for k, v in ends.items() if v != drop})
        pruned_branches[source] = pruned_named
    proxy = SimpleNamespace(
        nodes=[n for n in graph.nodes if str(n) != drop],
        edges={(s, d) for s, d in getattr(graph, "edges", set()) if drop not in (s, d)},
        branches=pruned_branches,
    )
    return cast("AgentStateGraph", proxy)


def _topology_compute(graph: AgentStateGraph) -> object:
    snapshot = graph_topology_mod.topology_snapshot(graph)
    return graph_topology_mod.compare_topology(
        snapshot, golden=graph_topology_mod.GOLDEN_FINGERPRINT
    )


def _topology_perturb(graph: AgentStateGraph) -> AgentStateGraph:
    return _prune_node(graph, "simulator")


_topology_probe: Probe[AgentStateGraph] = Probe(
    key="graph-topology-versioning#87",
    compute=_topology_compute,
    observe=_obs_drifted,
    base_source=build_graph(),
    perturb=_topology_perturb,
    relation="changes",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# #41 golden-snapshot-ci. Route (routes/observability.py:2730-2734): same turns
# transform as #86 -> diff_traces(turns). Perturbation: append a turn whose
# latency-map keys include a node outside GOLDEN_KNOWN_NODES -> n_drifted 0 -> 1.
# --------------------------------------------------------------------------- #

_SNAPSHOT_BASE: list[ReplayBundle] = [
    _bundle(
        "balance?",
        latency_ms={"router": 1.0, "planner": 1.0, "account_lookup": 1.0, "reviewer": 1.0},
    ),
]


def _snapshot_compute(bundles: list[ReplayBundle]) -> object:
    return trace_snapshot_mod.diff_traces(_turns_from_bundles(bundles))


def _snapshot_perturb(bundles: list[ReplayBundle]) -> list[ReplayBundle]:
    unknown = _bundle(
        "q",
        latency_ms={"router": 1.0, "planner": 1.0, "reviewer": 1.0, "mystery_node": 1.0},
    )
    return [*bundles, unknown]


_snapshot_probe: Probe[list[ReplayBundle]] = Probe(
    key="golden-snapshot-ci#41",
    compute=_snapshot_compute,
    observe=_obs_n_drifted,
    base_source=_SNAPSHOT_BASE,
    perturb=_snapshot_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# #189 handoff-tracing. Route (routes/observability.py:2065-2069): same turns
# transform as #86 -> analyze_handoffs(turns). Perturbation: append a turn that
# ran a worker (product_lookup) but never reached the reviewer -> a broken
# worker→reviewer handoff -> total_broken 0 -> 1.
# --------------------------------------------------------------------------- #

_HANDOFF_BASE: list[ReplayBundle] = [
    _bundle(
        "balance?",
        latency_ms={"router": 1.0, "planner": 1.0, "account_lookup": 1.0, "reviewer": 1.0},
    ),
]


def _handoff_compute(bundles: list[ReplayBundle]) -> object:
    return handoffs_mod.analyze_handoffs(_turns_from_bundles(bundles))


def _handoff_perturb(bundles: list[ReplayBundle]) -> list[ReplayBundle]:
    broken = _bundle("q2", latency_ms={"router": 1.0, "planner": 1.0, "product_lookup": 1.0})
    return [*bundles, broken]


_handoff_probe: Probe[list[ReplayBundle]] = Probe(
    key="handoff-tracing#189",
    compute=_handoff_compute,
    observe=_obs_total_broken,
    base_source=_HANDOFF_BASE,
    perturb=_handoff_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# #89 context-overflow. Route (routes/observability.py:2493-2500): context split
# into paragraph chunks -> analyze_overflow(turns) at the DEFAULT 8,192-token
# window (usable = 8,192 - 1,024 reserved = 7,168 tokens, context_overflow.py:26-28).
# Perturbation: append a turn whose single ~30,000-char paragraph (~7,500
# estimated tokens, cost_anomaly.estimate_tokens = chars // 4) blows that budget
# -> overflow_rate 0.0 -> 0.5.
# --------------------------------------------------------------------------- #

_OVERFLOW_BASE: list[ReplayBundle] = [
    _bundle(
        "Quel est le taux ?",
        context="Le taux du pret est de 3 pourcent.\n\nContexte credit Aurore.",
    ),
]


def _overflow_compute(bundles: list[ReplayBundle]) -> object:
    return context_overflow_mod.analyze_overflow(_overflow_turns(bundles))


def _overflow_perturb(bundles: list[ReplayBundle]) -> list[ReplayBundle]:
    huge = _bundle("Question tres longue", context="x" * 30_000)
    return [*bundles, huge]


_overflow_probe: Probe[list[ReplayBundle]] = Probe(
    key="context-overflow#89",
    compute=_overflow_compute,
    observe=_obs_overflow_rate,
    base_source=_OVERFLOW_BASE,
    perturb=_overflow_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# #88 tool-loop-detection. Route (routes/observability.py:2543-2559) assembles
# ``{"global": [tools]}`` from the sorted audit trail, but detect_loops itself is
# a pure fn-arg consumer of that dict (like Phase 1's aggregate_leaks turns) — so
# the dict is the honest seam. Perturbation: 3 consecutive identical tool calls
# -> a "repeat" loop fires -> n_loops 0 -> 1.
# --------------------------------------------------------------------------- #

_LOOPS_BASE: dict[str, list[str]] = {"global": ["account_balance", "card_block", "loan_simulate"]}


def _loops_compute(streams: dict[str, list[str]]) -> object:
    return tool_loops_mod.detect_loops(streams)


def _loops_perturb(streams: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        **streams,
        "global": [*streams["global"], "account_balance", "account_balance", "account_balance"],
    }


_loops_probe: Probe[dict[str, list[str]]] = Probe(
    key="tool-loop-detection#88",
    compute=_loops_compute,
    observe=_obs_n_loops,
    base_source=_LOOPS_BASE,
    perturb=_loops_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# #47 schema-conformance. Route (routes/observability.py:2484-2490):
# compute_conformance(at=at, agent_id=_agent_or_none(agent)) — the function
# itself does the ledger file I/O (unlike #88's plain-dict detect_loops), so the
# honest perturbation writes a real temporary ledger and calls
# compute_conformance(path=...) (unit+temp, seam=store) — the same mechanism the
# existing test already uses (test_observability_conformance.py::
# test_compute_conformance_handles_missing_file). Perturbation: a card_block call
# whose card_last_four violates policy.yaml's ``^[0-9]{4}$`` -> conformance_rate
# 1.0 -> 0.875. Built inside its test (needs pytest's tmp_path fixture).
# --------------------------------------------------------------------------- #


def _card_block_entry(card_last_four: str, *, reason: str = "lost") -> dict[str, object]:
    """One ``tessera.guard.audit`` ledger row for a ``card_block`` call."""
    return {
        "type": "tessera.guard.audit",
        "target": "card_block",
        "arguments": {"card_last_four": card_last_four, "reason": reason},
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "agent_id": "collections",
    }


_CONFORMANCE_BASE_ROWS: list[dict[str, object]] = [
    _card_block_entry("1234"),
    _card_block_entry("5678"),
    _card_block_entry("9012"),
]


def _conformance_perturb(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [*rows, _card_block_entry("12")]  # violates ^[0-9]{4}$ (policy.yaml:58-59)


# --------------------------------------------------------------------------- #
# #1 trace-replay. Route (routes/observability.py:1816-1841): get_bundle(id) ->
# replay(bundle, model=...) with the DEFAULT judge (a real LLMJudge) — a store
# lookup feeding a bare fn-arg call. The existing unit test
# (test_observability_replay.py::test_replay_computes_delta_and_similarity)
# already avoids Postgres/LLM by constructing a ReplayBundle directly and
# injecting a stub backend/judge; we reproduce that exact lightweight mechanism
# rather than opening a real store/LLM connection, per the task's instruction to
# follow the existing test's mechanism. DIVERGENCE FLAGGED: the map labels #1
# seam=store/test=integration; empirically the *provider* (`replay()`) is a bare
# fn-arg call over an injectable bundle+backend+judge, and the only "store" step
# (`get_bundle`) is a route-side lookup already covered by #86/#41/#189's
# recent_bundles() seam. Reported as a seam/test-mode reconciliation, not forced.
#
# Perturbation: a judge that scores "grounded" only when a marked fact is still
# present in context; stripping that fact from the bundle's context (as if the
# retrieved grounding chunk were lost) drops the candidate's judged score, hence
# score_delta -> down.
# --------------------------------------------------------------------------- #


class _StubBackend:
    """Deterministic ``ChatBackend`` double — never opens a real model connection."""

    name = "stub"

    def __init__(self, content: str, model: str = "candidate-model") -> None:
        self._content = content
        self.model = model

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            content=self._content,
            model=self.model,
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            yield self._content

        return _gen()


class _GroundingJudge:
    """Scores ``grounded`` iff a marked fact is still present in ``context``.

    Proves ``replay()`` really threads ``bundle.context`` into the judge call
    (replay.py:329-335) rather than just the generation prompt.
    """

    def __init__(self, fact: str, *, grounded_score: float, ungrounded_score: float) -> None:
        self._fact = fact
        self._grounded_score = grounded_score
        self._ungrounded_score = ungrounded_score

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        value = self._grounded_score if self._fact in context else self._ungrounded_score
        return JudgeVerdict(
            metric=metric, score=value, rationale="stub", judge_model="stub-grounding"
        )


_GROUNDING_FACT = "Le taux du pret Aurore est fixe a 3 pourcent."

_REPLAY_BASE = ReplayBundle(
    bundle_id="replay-a3-1",
    captured_at="2026-01-01T00:00:00+00:00",
    conversation_id=None,
    language="fr",
    question="Quel est le taux du pret Aurore ?",
    context=f"{_GROUNDING_FACT} Contexte credit Aurore.",
    original_answer="Le taux est de 3 pourcent.",
    original_model="baseline-model",
    original_score=0.7,
)


async def _replay_compute(bundle: ReplayBundle) -> object:
    return await replay_fn(
        bundle,
        model="candidate-model",
        judge=_GroundingJudge(_GROUNDING_FACT, grounded_score=0.9, ungrounded_score=0.3),
        backend=_StubBackend("Le taux est de 3 pourcent, selon le contexte fourni."),
    )


def _replay_perturb(bundle: ReplayBundle) -> ReplayBundle:
    stripped = bundle.context.replace(_GROUNDING_FACT, "").strip()
    return dataclasses.replace(bundle, context=stripped)


_replay_probe: Probe[ReplayBundle] = Probe(
    key="trace-replay#1",
    compute=_replay_compute,
    observe=_obs_score_delta,
    base_source=_REPLAY_BASE,
    perturb=_replay_perturb,
    relation="down",
    seam="fn-arg",  # divergence vs map's "store" — see block comment above
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_reproducibility_hash_is_wired() -> None:
    """Same question, a genuinely different executed-node shape -> n_nondeterministic moves."""
    result = assert_wired(_repro_probe)
    assert result.d0 == 0.0
    assert result.d1 == 1.0
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_graph_topology_versioning_is_wired() -> None:
    """The live graph matches the golden; pruning a real node flips drift.drifted."""
    result = assert_wired(_topology_probe)
    assert result.d0 == 0.0  # live build_graph() matches GOLDEN_FINGERPRINT
    assert result.d1 == 1.0  # pruned graph's recomputed hash necessarily differs
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_golden_snapshot_ci_is_wired() -> None:
    """A turn running a node outside the golden universe drifts n_drifted up."""
    result = assert_wired(_snapshot_probe)
    assert result.d0 == 0.0
    assert result.d1 == 1.0
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_handoff_tracing_is_wired() -> None:
    """A worker turn that never reaches the reviewer counts as a broken handoff."""
    result = assert_wired(_handoff_probe)
    assert result.d0 == 0.0
    assert result.d1 == 1.0
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_context_overflow_is_wired() -> None:
    """A turn whose context blows the usable-token budget raises overflow_rate."""
    result = assert_wired(_overflow_probe)
    assert result.d0 == 0.0
    assert result.d1 == 0.5
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_tool_loop_detection_is_wired() -> None:
    """Three consecutive identical tool calls trip the repeat-loop detector."""
    result = assert_wired(_loops_probe)
    assert result.d0 == 0.0
    assert result.d1 == 1.0
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_schema_conformance_is_wired(tmp_path: Path) -> None:
    """A malformed tool argument in a temp ledger file drags conformance_rate down."""
    ledger_path = tmp_path / "ledger.jsonl"

    def _write(rows: list[dict[str, object]]) -> None:
        with ledger_path.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row) + "\n")

    def _compute(rows: list[dict[str, object]]) -> object:
        _write(rows)
        # Reproduces routes/observability.py:2490 verbatim, pointed at the temp file
        # instead of the default settings audit file.
        return conformance_mod.compute_conformance(path=ledger_path, at=None, agent_id=None)

    probe: Probe[list[dict[str, object]]] = Probe(
        key="schema-conformance#47",
        compute=_compute,
        observe=_obs_conformance_rate,
        base_source=_CONFORMANCE_BASE_ROWS,
        perturb=_conformance_perturb,
        relation="down",
        seam="store",
        declared_class="real-computed",
    )
    result = assert_wired(probe)
    assert result.d0 == 1.0
    assert result.d1 < result.d0
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")


def test_trace_replay_is_wired() -> None:
    """Stripping the grounding fact from context drags the judged score_delta down."""
    result = assert_wired(_replay_probe)
    assert result.d0 > 0.0
    assert result.d1 < result.d0
    print(f"A3  {result.key:32} {result.verdict.value:10} {result.detail}")
