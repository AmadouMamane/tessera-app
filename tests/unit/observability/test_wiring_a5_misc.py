"""Metamorphic wiring proof — Phase 2, Table A.5 (misc real-computed / composite).

Extends the Phase 1 harness (``tests/support/wiring.py``, ``test_signal_wiring.py``
— both frozen) to the 8 rows of Table A.5 in ``docs/design/signal-wiring-map.md``.

Per the map's load-bearing rule, every ``compute`` below reproduces the *route's*
source-assembly from ``src/tessera/api/routes/observability.py`` rather than a
shortcut call to the bare provider.

Signals covered (route -> function):
  * #122 traces-to-sft          - /observability/sft-dataset      -> sft_export.build_sft_dataset
  * #124 telemetry-to-roadmap   - /observability/roadmap          -> roadmap.build_roadmap
  * #180 gdpr-erasure-telemetry - /observability/erasure-coverage
    -> erasure.coverage / purge_telemetry
  * #3   tamper-evident-audit   - /observability/audit-integrity
    -> ledger_store.verify_active_ledger
  * #16  shadow-traffic         - /observability/shadow           -> shadow.run_shadow
  * #172 siem-integration       - /observability/siem             -> siem.to_siem_events
  * #36  consent-governance-ops - /observability/memory
    -> memory_obs.aggregate_memory_audit
  * #99  cross-session-journey  - /observability/journey          -> journey.build_journeys

Two rows carry a documented finding rather than a plain WIRED:

* **#124** has a dead sub-path: the route never sets ``RoadmapSignals.n_coverage_gaps``,
  so the ``coverage_gap`` roadmap item can never fire — even though the pure
  ``build_roadmap`` reacts correctly when that field IS set directly. The main
  signal (``n_items`` via low-faithfulness turns) is WIRED; the sub-path proof
  below isolates the dead field and shows the pure function's causal reaction,
  attributing the deadness to the route, not the aggregator (rigor rule 2).
* **#16** and **#172** were named in the plan as negative-control fixtures (R0);
  Phase 0's cartography found both genuinely wired (``run_shadow`` replays real
  bundles, ``to_siem_events`` maps real ledger rows) — this file proves that,
  keeping them in Table A rather than the negative control.

Several signals read from real module-global stores (the captured-bundle buffer
in ``replay.py``, the score buffer in ``eval/scores.py``). Following the
established sibling pattern (``test_wiring_b_store_baseline.py``'s
``online-scores`` probe), ``compute`` resets the relevant buffer to empty, then
replays the exact production write path for each spec in the deterministic
``source`` before reading back through the production read path — this proves
the write leg and the read leg together and stays hermetic across repeated runs.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

from tessera.guard import ledger_store as ledger_store_mod
from tessera.guard.audit import _hash_core
from tessera.observability import (
    erasure as erasure_mod,
    journey as journey_mod,
    memory_obs as memory_obs_mod,
    replay as replay_mod,
    roadmap as roadmap_mod,
    sft_export as sft_export_mod,
    shadow as shadow_mod,
    siem as siem_mod,
)
from tessera.observability.eval import scores as scores_mod
from tessera.observability.eval.judge import JudgeVerdict
from tessera.observability.replay import ReplayBundle, ReplayResult
from tests.support.wiring import Probe, Verdict, assert_wired, evaluate

if TYPE_CHECKING:
    from tessera.guard.audit import ChainStatus
    from tessera.observability.erasure import ErasureCoverage
    from tessera.observability.journey import JourneyReport
    from tessera.observability.memory_obs import MemoryObsReport
    from tessera.observability.roadmap import RoadmapReport
    from tessera.observability.sft_export import SFTDataset
    from tessera.observability.shadow import ShadowReport
    from tessera.observability.siem import SiemExport

# --------------------------------------------------------------------------- #
# Observers — payload -> scalar
# --------------------------------------------------------------------------- #


def _obs_n_eligible(payload: object) -> int:
    return cast("SFTDataset", payload).n_eligible


def _obs_n_items(payload: object) -> int:
    return cast("RoadmapReport", payload).n_items


def _obs_has_coverage_gap_item(payload: object) -> bool:
    report = cast("RoadmapReport", payload)
    return any(item.signal == "coverage_gap" for item in report.items)


def _obs_n_conversations(payload: object) -> int:
    return cast("ErasureCoverage", payload).n_conversations


def _obs_verified(payload: object) -> bool:
    return cast("ChainStatus", payload).verified


def _obs_n_compared(payload: object) -> int:
    return cast("ShadowReport", payload).n_compared


def _obs_n_events(payload: object) -> int:
    return cast("SiemExport", payload).n_events


def _obs_writes_denied(payload: object) -> int:
    return cast("MemoryObsReport", payload).writes_denied


def _obs_n_forgets(payload: object) -> int:
    return cast("MemoryObsReport", payload).n_forgets


def _obs_n_returning(payload: object) -> int:
    return cast("JourneyReport", payload).n_returning


# --------------------------------------------------------------------------- #
# #122 traces-to-sft. Route (/observability/sft-dataset, ~L2252-2259) builds
# turns as (b.question, b.context, b.original_answer, b.language,
# b.original_score) for every bundle from replay_mod.recent_bundles(), then
# returns asdict of sft_export_mod.build_sft_dataset(turns). Following the
# online-scores sibling pattern, compute resets the live bundle buffer, replays
# the real capture_bundle() write path for each spec, then reads back through
# the real recent_bundles(). seam=store.
# --------------------------------------------------------------------------- #

_SFTSpec = tuple[str, float]  # (question, score)


def _sft_seed(specs: list[_SFTSpec]) -> list[tuple[str, str, str, str, float]]:
    replay_mod._BUNDLES.clear()
    replay_mod._WARMED = True
    for question, score in specs:
        replay_mod.capture_bundle(
            question=question,
            context="ctx",
            original_answer="une reponse detaillee et complete",
            language="fr",
            original_score=score,
            original_model="llama3.2:3b",
        )
    return [
        (b.question, b.context, b.original_answer, b.language, b.original_score)
        for b in replay_mod.recent_bundles()
    ]


def _sft_compute(specs: list[_SFTSpec]) -> object:
    turns = _sft_seed(specs)
    return sft_export_mod.build_sft_dataset(turns)


def _sft_perturb(specs: list[_SFTSpec]) -> list[_SFTSpec]:
    return [*specs, ("nouvelle question bien jugee", 0.95)]


_SFT_BASE: list[_SFTSpec] = [("premiere question", 0.9)]

_sft_probe: Probe[list[_SFTSpec]] = Probe(
    key="traces-to-sft#122",
    compute=_sft_compute,
    observe=_obs_n_eligible,
    base_source=_SFT_BASE,
    perturb=_sft_perturb,
    relation="up",
    seam="store",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #124 telemetry-to-roadmap (PARTIAL — documented dead sub-path). Route
# (/observability/roadmap, ~L1967-2006) assembles RoadmapSignals from n_turns
# and n_low_score (the score store), n_unknown_intent (routing_intent over
# recent_bundles questions), n_stale_corpora (corpus_freshness), and
# languages_low — but never sets n_coverage_gaps, so it keeps the dataclass
# default of 0 no matter what. compute mirrors that exact field list, omitting
# n_coverage_gaps exactly like the route.
# --------------------------------------------------------------------------- #


def _roadmap_compute(low_score_count: int) -> object:
    signals = roadmap_mod.RoadmapSignals(
        n_turns=10,
        n_low_score=low_score_count,
        n_unknown_intent=0,
        n_stale_corpora=0,
        languages_low={},
    )
    return roadmap_mod.build_roadmap(signals)


def _roadmap_perturb(low_score_count: int) -> int:
    return low_score_count + 4


_roadmap_probe: Probe[int] = Probe(
    key="telemetry-to-roadmap#124",
    compute=_roadmap_compute,
    observe=_obs_n_items,
    base_source=0,
    perturb=_roadmap_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

# The dead sub-path: no perturbation reachable through the route-faithful
# compute can ever move whether a "coverage_gap" item appears, because the
# route has no channel to n_coverage_gaps at all -- not an alias, an omission.
_roadmap_subpath_probe: Probe[int] = Probe(
    key="telemetry-to-roadmap#124/coverage-gap-subpath",
    compute=_roadmap_compute,
    observe=_obs_has_coverage_gap_item,
    base_source=0,
    perturb=_roadmap_perturb,  # more low-score turns -- irrelevant to n_coverage_gaps
    relation="changes",
    seam="route-fixed",
    declared_class="real-computed",
)


def _roadmap_pure_reacts_to_coverage_gaps() -> bool:
    """The pure build_roadmap DOES react when n_coverage_gaps is set directly."""
    without = roadmap_mod.build_roadmap(roadmap_mod.RoadmapSignals(n_turns=10))
    with_gaps = roadmap_mod.build_roadmap(roadmap_mod.RoadmapSignals(n_turns=10, n_coverage_gaps=3))
    has_item = any(item.signal == "coverage_gap" for item in with_gaps.items)
    had_none = not any(item.signal == "coverage_gap" for item in without.items)
    return has_item and had_none


# --------------------------------------------------------------------------- #
# #180 gdpr-erasure-telemetry. Route (/observability/erasure-coverage,
# ~L2022-2025) calls erasure_mod.coverage(replay_mod.recent_bundles(),
# read_scores()) with no extra transformation, so feeding coverage() directly-
# constructed bundle/score sequences is route-faithful for the aggregation
# leg (relation up: capture more -> n_conversations up). The purge leg
# (relation down) must go through the real global buffers, since
# purge_telemetry mutates them directly -- compute resets both buffers, seeds
# them via the real capture_bundle()/scores_mod write paths, then purges the
# conversations named in to_purge via the real purge_telemetry (spine deletion
# stubbed offline, matching test_observability_erasure.py's own fixture).
# --------------------------------------------------------------------------- #

_ErasureSpec = tuple[tuple[str, ...], tuple[str, ...]]  # (captured_conv_ids, purged_conv_ids)


def _erasure_compute(spec: _ErasureSpec) -> object:
    captured, to_purge = spec
    replay_mod._BUNDLES.clear()
    replay_mod._WARMED = True
    scores_mod._RECENT.clear()
    scores_mod._WARMED = True
    for conv in captured:
        replay_mod.capture_bundle(
            question="q",
            context="ctx",
            original_answer="a",
            language="fr",
            original_score=0.8,
            original_model="m",
            conversation_id=conv,
        )
        scores_mod.emit_score(
            JudgeVerdict(
                metric="faithfulness", score=0.8, rationale="probe", judge_model="probe-judge"
            ),
            language="fr",
            conversation_id=conv,
        )
    with patch.object(erasure_mod, "_spine_delete", lambda _cid: 0):
        for conv in to_purge:
            erasure_mod.purge_telemetry(conv)
    return erasure_mod.coverage(replay_mod.recent_bundles(), scores_mod.recent_scores())


def _erasure_perturb_capture(spec: _ErasureSpec) -> _ErasureSpec:
    captured, to_purge = spec
    return (*captured, "conv-nouveau"), to_purge


_ERASURE_BASE: _ErasureSpec = (("conv-un",), ())

_erasure_capture_probe: Probe[_ErasureSpec] = Probe(
    key="gdpr-erasure-telemetry#180/capture",
    compute=_erasure_compute,
    observe=_obs_n_conversations,
    base_source=_ERASURE_BASE,
    perturb=_erasure_perturb_capture,
    relation="up",
    seam="store",
    declared_class="real-computed",
)

_ERASURE_TWO_CONVS: _ErasureSpec = (("conv-un", "conv-deux"), ())


def _erasure_perturb_purge(spec: _ErasureSpec) -> _ErasureSpec:
    captured, _to_purge = spec
    return captured, ("conv-un",)


_erasure_purge_probe: Probe[_ErasureSpec] = Probe(
    key="gdpr-erasure-telemetry#180/purge",
    compute=_erasure_compute,
    observe=_obs_n_conversations,
    base_source=_ERASURE_TWO_CONVS,
    perturb=_erasure_perturb_purge,
    relation="down",
    seam="store",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #3 tamper-evident-audit. Route (/observability/audit-integrity, ~L2334-2342)
# calls ledger_store.verify_active_ledger(), which in the default postgres
# ledger_source() branch calls verify_ledger_rows(load_ledger_payloads_sync())
# (guard/ledger_store.py ~L502-512) -- the same pair shadow_verify_ledger uses.
# compute patches load_ledger_payloads_sync to return a controlled hash chain
# (built with the real _hash_core, so it verifies genuinely) and forces
# ledger_source to "postgres" for determinism regardless of the environment,
# leaving verify_active_ledger and verify_ledger_rows themselves real.
# --------------------------------------------------------------------------- #

_GENESIS = "0" * 64
_AUDIT_ACTIONS = ["memory.write", "memory.read", "guard.deny"]


def _build_chain(actions: list[str], *, tamper_first: bool) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    prev = _GENESIS
    for i, action in enumerate(actions):
        core: dict[str, object] = {"seq": i, "prev_hash": prev, "action": action}
        digest = _hash_core(core)
        entries.append({**core, "hash": digest})
        prev = digest
    if tamper_first:
        # Edit an already-hashed entry's payload without recomputing its hash --
        # exactly "edit a persisted row" (the map's declared perturbation).
        entries[0] = {**entries[0], "action": "edited-after-the-fact"}
    return entries


def _audit_compute(tamper: bool) -> object:
    payloads = _build_chain(_AUDIT_ACTIONS, tamper_first=tamper)
    with (
        patch.object(ledger_store_mod, "ledger_source", lambda: "postgres"),
        patch.object(ledger_store_mod, "load_ledger_payloads_sync", lambda **_kw: payloads),
    ):
        return ledger_store_mod.verify_active_ledger()


def _audit_perturb(tamper: bool) -> bool:
    return not tamper


_audit_probe: Probe[bool] = Probe(
    key="tamper-evident-audit#3",
    compute=_audit_compute,
    observe=_obs_verified,
    base_source=False,
    perturb=_audit_perturb,
    relation="changes",
    seam="store",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #16 shadow-traffic (R0 -- confirmed real, not a fixture). Route
# (/observability/shadow, ~L490-496) calls shadow_mod.run_shadow(
# replay_mod.recent_bundles(), model=payload.model, limit=payload.limit) --
# bundles pass straight through as an explicit argument, so a plain list of
# ReplayBundle is route-faithful. run_shadow calls replay_mod.replay(bundle,
# model=, judge=) internally with no injectable backend, so compute patches
# that one seam to a deterministic fake, matching test_observability_shadow.py.
# --------------------------------------------------------------------------- #


async def _fake_replay(bundle: ReplayBundle, *, model: str, **_kw: object) -> ReplayResult:
    """Deterministic stand-in for replay_mod.replay: candidate == original score."""
    return ReplayResult(
        bundle_id=bundle.bundle_id,
        original_model=bundle.original_model,
        original_score=bundle.original_score,
        candidate_model=model,
        candidate_answer="candidate",
        candidate_score=bundle.original_score,
        score_delta=0.0,
        similarity=0.7,
    )


def _shadow_bundle(question: str) -> ReplayBundle:
    return ReplayBundle(
        bundle_id=question,
        captured_at="2026-06-09T00:00:00+00:00",
        conversation_id="c1",
        language="fr",
        question=question,
        context="ctx",
        original_answer="answer",
        original_model="llama3.2:3b",
        original_score=0.8,
    )


def _shadow_compute(bundles: list[ReplayBundle]) -> object:
    with patch.object(replay_mod, "replay", _fake_replay):
        return asyncio.run(shadow_mod.run_shadow(bundles, model="mistral:7b"))


def _shadow_perturb(bundles: list[ReplayBundle]) -> list[ReplayBundle]:
    return [*bundles, _shadow_bundle("nouvelle question capturee")]


_SHADOW_BASE: list[ReplayBundle] = [_shadow_bundle("premiere question")]

_shadow_probe: Probe[list[ReplayBundle]] = Probe(
    key="shadow-traffic#16",
    compute=_shadow_compute,
    observe=_obs_n_compared,
    base_source=_SHADOW_BASE,
    perturb=_shadow_perturb,
    relation="up",
    seam="store",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #172 siem-integration (R0 -- confirmed real, not a fixture). Route
# (/observability/siem, ~L2280-2284) calls
# siem_mod.to_siem_events(_read_audit_entries()), where _read_audit_entries()
# filters read_ledger_entries() down to type == "tessera.guard.audit" -- a
# plain filter with no other transformation, so a list of audit-entry dicts
# already shaped that way is route-faithful. seam=fn-arg.
# --------------------------------------------------------------------------- #

_SIEM_BASE: list[dict[str, object]] = [
    {
        "type": "tessera.guard.audit",
        "target": "card.block",
        "outcome": "allowed",
        "decisions": [{"decision": "allow", "rationale": "ok"}],
        "occurred_at": "2026-06-09T00:00:00+00:00",
        "arguments": {"subject_id": "cust-1"},
    }
]


def _siem_compute(entries: list[dict[str, object]]) -> object:
    return siem_mod.to_siem_events(entries)


def _siem_perturb(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    denied: dict[str, object] = {
        "type": "tessera.guard.audit",
        "target": "prompt.injection",
        "outcome": "denied",
        "decisions": [{"decision": "deny", "rationale": "blocked"}],
        "occurred_at": "2026-06-09T00:05:00+00:00",
        "arguments": {"subject_id": "cust-2"},
    }
    return [*entries, denied]


_siem_probe: Probe[list[dict[str, object]]] = Probe(
    key="siem-integration#172",
    compute=_siem_compute,
    observe=_obs_n_events,
    base_source=_SIEM_BASE,
    perturb=_siem_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #36 consent-governance-ops. Route (/observability/memory, ~L2016-2019) calls
# memory_obs_mod.aggregate_memory_audit(_read_audit_entries()) -- the same
# function and seam as #23 memory-observability (test_wiring_a4_routing.py),
# but observed on writes_denied / n_forgets rather than recall_hit_rate.
# --------------------------------------------------------------------------- #

_CONSENT_BASE: list[dict[str, object]] = [
    {
        "type": "tessera.guard.audit",
        "target": "memory.write",
        "outcome": "allowed",
        "decisions": [{"decision": "allow", "rationale": "persisted 1/1 candidate fact(s)"}],
    }
]


def _consent_compute(entries: list[dict[str, object]]) -> object:
    return memory_obs_mod.aggregate_memory_audit(entries)


def _consent_perturb_denied_write(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    denied_write: dict[str, object] = {
        "type": "tessera.guard.audit",
        "target": "memory.write",
        "outcome": "denied",
        "decisions": [{"decision": "deny", "rationale": "consent not given"}],
    }
    return [*entries, denied_write]


_consent_writes_denied_probe: Probe[list[dict[str, object]]] = Probe(
    key="consent-governance-ops#36/writes-denied",
    compute=_consent_compute,
    observe=_obs_writes_denied,
    base_source=_CONSENT_BASE,
    perturb=_consent_perturb_denied_write,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


def _consent_perturb_forget(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    forget: dict[str, object] = {
        "type": "tessera.guard.audit",
        "target": "memory.forget",
        "outcome": "allowed",
        "decisions": [{"decision": "allow", "rationale": "erasure requested"}],
    }
    return [*entries, forget]


_consent_n_forgets_probe: Probe[list[dict[str, object]]] = Probe(
    key="consent-governance-ops#36/n-forgets",
    compute=_consent_compute,
    observe=_obs_n_forgets,
    base_source=_CONSENT_BASE,
    perturb=_consent_perturb_forget,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #99 cross-session-journey. Route (/observability/journey, ~L2072-2085) filters
# _read_audit_entries() to memory.* targets, extracts (subject_id, target,
# occurred_at) triples, then calls journey_mod.build_journeys(events). A list
# of pre-shaped audit entries is route-faithful. seam=fn-arg.
# --------------------------------------------------------------------------- #

_JOURNEY_BASE: list[dict[str, object]] = [
    {
        "target": "memory.read",
        "arguments": {"subject_id": "cust-1"},
        "occurred_at": "2026-06-09T09:00:00+00:00",
    }
]


def _journey_compute(entries: list[dict[str, object]]) -> object:
    events: list[tuple[str, str, str]] = []
    for entry in entries:
        target = entry.get("target")
        if not (isinstance(target, str) and target.startswith("memory.")):
            continue
        args = entry.get("arguments")
        subject = args.get("subject_id") if isinstance(args, dict) else None
        occurred_at = entry.get("occurred_at")
        if isinstance(subject, str) and isinstance(occurred_at, str):
            events.append((subject, target, occurred_at))
    return journey_mod.build_journeys(events)


def _journey_perturb(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    later_read: dict[str, object] = {
        "target": "memory.read",
        "arguments": {"subject_id": "cust-1"},
        "occurred_at": "2026-06-09T09:45:00+00:00",  # 45 min later -- new session
    }
    return [*entries, later_read]


_journey_probe: Probe[list[dict[str, object]]] = Probe(
    key="cross-session-journey#99",
    compute=_journey_compute,
    observe=_obs_n_returning,
    base_source=_JOURNEY_BASE,
    perturb=_journey_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_traces_to_sft_is_wired() -> None:
    """Capturing one more turn scored >= 0.80 moves n_eligible up."""
    result = assert_wired(_sft_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_telemetry_to_roadmap_is_wired() -> None:
    """More low-faithfulness turns move n_items up via the low_faithfulness item."""
    result = assert_wired(_roadmap_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_telemetry_to_roadmap_coverage_gap_subpath_is_dead_at_route() -> None:
    """No route-reachable perturbation ever surfaces a coverage_gap item (DEAD sub-path)."""
    result = evaluate(_roadmap_subpath_probe)
    assert result.verdict in {Verdict.DEAD, Verdict.INVARIANT_OK}, result.detail
    assert result.d0 == 0.0
    assert result.d1 == 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_telemetry_to_roadmap_pure_function_reacts_to_coverage_gaps() -> None:
    """The causal proof required by rigor rule 2: the PURE aggregator does react
    to n_coverage_gaps when it is set directly, bypassing the route's omission --
    attributing the dead sub-path to the route, not to build_roadmap."""
    assert _roadmap_pure_reacts_to_coverage_gaps() is True


def test_gdpr_erasure_telemetry_capture_is_wired() -> None:
    """Capturing a new conversation's turn+score moves n_conversations up."""
    result = assert_wired(_erasure_capture_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_gdpr_erasure_telemetry_purge_is_wired() -> None:
    """purge_telemetry on one of two conversations moves n_conversations down."""
    result = assert_wired(_erasure_purge_probe)
    assert result.delta < 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_tamper_evident_audit_verified_flips_on_edit() -> None:
    """Editing an already-hashed ledger row (without recomputing its hash) flips
    verify_active_ledger()'s ChainStatus.verified from True to False."""
    result = assert_wired(_audit_probe)
    assert result.d0 == 1.0  # verified True on the clean chain
    assert result.d1 == 0.0  # verified False once entry 0 is tampered
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_shadow_traffic_is_wired() -> None:
    """Capturing one more bundle moves n_compared up (R0: confirmed real)."""
    result = assert_wired(_shadow_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_siem_integration_is_wired() -> None:
    """A live guard deny moves n_events up (R0: confirmed real)."""
    result = assert_wired(_siem_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_consent_governance_ops_writes_denied_is_wired() -> None:
    """A consent-denied memory write moves writes_denied up."""
    result = assert_wired(_consent_writes_denied_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_consent_governance_ops_n_forgets_is_wired() -> None:
    """A memory.forget action moves n_forgets up."""
    result = assert_wired(_consent_n_forgets_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_cross_session_journey_is_wired() -> None:
    """A read 45 minutes after the prior action for the same subject starts a new
    session, moving n_returning up."""
    result = assert_wired(_journey_probe)
    assert result.delta > 0.0
    print(f"A5  {result.key:38} {result.verdict.value:10} {result.detail}")


def test_a5_probe_summary() -> None:
    """Diagnostic sweep over every up/down probe in this file, in Table A.5 order."""
    probes: list[Probe[Any]] = [
        _sft_probe,
        _roadmap_probe,
        _erasure_capture_probe,
        _erasure_purge_probe,
        _audit_probe,
        _shadow_probe,
        _siem_probe,
        _consent_writes_denied_probe,
        _consent_n_forgets_probe,
        _journey_probe,
    ]
    for probe in probes:
        result = evaluate(probe)
        assert (
            result.verdict is Verdict.WIRED
        ), f"{probe.key}: expected WIRED, got {result.verdict.value} — {result.detail}"
        print(
            f"A5  {probe.key:38} {result.verdict.value:10} "
            f"d0={result.d0:.6g} d1={result.d1:.6g} Δ={result.delta:+.6g} "
            f"seam={result.seam}"
        )
