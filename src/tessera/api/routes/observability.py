"""Observability read endpoints for the dashboard (ADR 0010).

Exposes the recent online-eval scores so the dashboard can surface
eval-as-telemetry live. Aggregate quality scores are a public surface
(ADR 0009), so this endpoint is unauthenticated like ``/healthz``.
"""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from tessera.observability import (
    ablation as ablation_mod,
    ai_act as ai_act_mod,
    anomalies as anomalies_mod,
    citation_validity as citation_validity_mod,
    conformance as conformance_mod,
    consistency as consistency_mod,
    contradiction as contradiction_mod,
    corpus_freshness as corpus_freshness_mod,
    corpus_injection as corpus_injection_mod,
    cost_anomaly as cost_anomaly_mod,
    coverage as coverage_mod,
    cross_tenant as cross_tenant_mod,
    crosslingual as crosslingual_mod,
    embedding_inversion as embedding_inversion_mod,
    embedding_skew as embedding_skew_mod,
    erasure as erasure_mod,
    failure_clustering as failure_clustering_mod,
    failure_predictor as failure_predictor_mod,
    firewall_efficacy as firewall_mod,
    funnel as funnel_mod,
    guard_explain as guard_explain_mod,
    journey as journey_mod,
    language_routing as language_routing_mod,
    least_privilege as least_privilege_mod,
    locale_format as locale_format_mod,
    localization as localization_mod,
    memory_inventory as memory_inventory_mod,
    memory_obs as memory_obs_mod,
    obs_cost as obs_cost_mod,
    pii_leak as pii_leak_mod,
    playbooks as playbooks_mod,
    provenance as provenance_mod,
    redteam as redteam_mod,
    refusal as refusal_mod,
    replay as replay_mod,
    reranking_contribution as reranking_contribution_mod,
    retrieval_quality as retrieval_quality_mod,
    roadmap as roadmap_mod,
    robustness as robustness_mod,
    routing_intent as routing_intent_mod,
    sessions as sessions_mod,
    sft_export as sft_export_mod,
    shadow as shadow_mod,
    siem as siem_mod,
    slo as slo_mod,
    steganography as steganography_mod,
    tail_sampling as tail_sampling_mod,
    tool_validity as tool_validity_mod,
    toxicity as toxicity_mod,
    trajectory as trajectory_mod,
    trends as trends_mod,
    whatchanged as whatchanged_mod,
)
from tessera.observability.eval.calibration import calibrate, load_gold_set
from tessera.observability.eval.ensemble import evaluate_ensemble
from tessera.observability.eval.judge import LLMJudge
from tessera.observability.eval.scores import recent_scores
from tessera.observability.eval.sycophancy import detect_sycophancy

router = APIRouter(tags=["observability"])


class ReplayRequest(BaseModel):
    """Replay a captured turn against a candidate model."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    model: str


class ConsistencyRequest(BaseModel):
    """Measure self-consistency of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    samples: int = Field(default=3, ge=2, le=8)


class RobustnessRequest(BaseModel):
    """Measure robustness-under-noise of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class EnsembleRequest(BaseModel):
    """Score a captured turn with a multi-judge ensemble."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class CoverageRequest(BaseModel):
    """Measure corpus coverage of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class SycophancyRequest(BaseModel):
    """Judge a captured turn for sycophancy."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class CrossLingualRequest(BaseModel):
    """Measure cross-lingual consistency of a captured turn."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str


class ShadowRequest(BaseModel):
    """Mirror a batch of captured turns to a candidate model (shadow)."""

    model_config = ConfigDict(extra="forbid")

    model: str
    limit: int = Field(default=10, ge=1, le=50)


# Calibration runs the judge over the gold set (slow), so cache it per process.
_calibration_cache: dict[str, object] | None = None
# The obs-cost micro-benchmark is stable per process, so compute it once.
_obs_cost_cache: dict[str, object] | None = None
# The embedding-inversion demo embeds a fixed corpus; cache it per process.
_inversion_cache: dict[str, object] | None = None
# Failure clustering embeds the whole failure corpus; cache it per process.
_clustering_cache: dict[str, object] | None = None


def _load_failure_items() -> list[failure_clustering_mod.FailureItem]:
    """Load the documented failures as clustering items (English prompt)."""
    import json
    from pathlib import Path

    items: list[failure_clustering_mod.FailureItem] = []
    failures_dir = Path(__file__).resolve().parents[4] / "eval" / "failures"
    for path in sorted(failures_dir.glob("[0-9]*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        prompts = obj.get("prompts", {})
        text = ""
        if isinstance(prompts, dict):
            for lang in ("en", "fr", "de"):
                entry = prompts.get(lang)
                if isinstance(entry, dict) and entry.get("user"):
                    text = str(entry["user"])
                    break
        text = text or str(obj.get("title", ""))
        items.append(
            failure_clustering_mod.FailureItem(
                case_id=str(obj.get("id", path.stem)),
                category=str(obj.get("category", "unknown")),
                text=text,
            )
        )
    return items


@router.get("/observability/scores")
async def observability_scores() -> dict[str, object]:
    """Return the most recent online-eval scores (newest last)."""
    return {"scores": recent_scores()}


@router.get("/observability/slo")
async def observability_slo() -> dict[str, object]:
    """Quality SLO + error-budget burn-rate over the recent faithfulness scores."""
    faithfulness = [
        float(s["score"])  # type: ignore[arg-type]
        for s in recent_scores()
        if s.get("metric") == "faithfulness"
    ]
    return asdict(slo_mod.compute_slo(faithfulness))


@router.post("/observability/shadow")
async def observability_shadow(payload: ShadowRequest) -> dict[str, object]:
    """Mirror recent captured turns to a candidate model and compare (shadow)."""
    report = await shadow_mod.run_shadow(
        replay_mod.recent_bundles(), model=payload.model, limit=payload.limit
    )
    return asdict(report)


@router.get("/observability/tail-sampling")
async def observability_tail_sampling() -> dict[str, object]:
    """Tail-sampling retention: 100% of slow/low-score traces, sampled head."""
    return asdict(tail_sampling_mod.analyze_sampling(replay_mod.recent_bundles()))


@router.get("/observability/trend")
async def observability_trend() -> dict[str, object]:
    """Long-horizon faithfulness trend over the recent score series (#150)."""
    points: list[tuple[str, float]] = []
    for s in recent_scores():
        if s.get("metric") != "faithfulness":
            continue
        scored_at = s.get("scored_at")
        points.append(
            (
                scored_at if isinstance(scored_at, str) else "",
                float(s["score"]),  # type: ignore[arg-type]
            )
        )
    return asdict(trends_mod.analyze_trend(points))


@router.get("/observability/obs-cost")
async def observability_obs_cost() -> dict[str, object]:
    """Measured instrumentation overhead vs the turn budget (#84), cached."""
    global _obs_cost_cache
    if _obs_cost_cache is None:
        _obs_cost_cache = asdict(obs_cost_mod.measure_overhead())
    return _obs_cost_cache


@router.get("/observability/calibration")
async def observability_calibration() -> dict[str, object]:
    """Return the judge's calibration against the human gold set (cached).

    The first call runs the judge over the gold set and may take a few seconds;
    subsequent calls return the cached report. Degrades to ``available: false``
    when the judge or gold set is unavailable, so the dashboard never errors.
    """
    global _calibration_cache
    if _calibration_cache is None:
        try:
            report = await calibrate(LLMJudge(), load_gold_set())
            _calibration_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # never break the dashboard on a judge/IO error
            sys.stderr.write(f"tessera.observability.calibration: failed: {exc}\n")
            return {"available": False}
    return _calibration_cache


@router.get("/observability/replays")
async def observability_replays() -> dict[str, object]:
    """List the captured turns available for regression replay (newest last)."""
    return {"bundles": [asdict(b) for b in replay_mod.recent_bundles()]}


@router.post("/observability/replay")
async def observability_replay(payload: ReplayRequest) -> dict[str, object]:
    """Replay a captured turn against a candidate model and diff the result."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    result = await replay_mod.replay(bundle, model=payload.model)
    return asdict(result)


@router.post("/observability/consistency")
async def observability_consistency(payload: ConsistencyRequest) -> dict[str, object]:
    """Measure the self-consistency / uncertainty of a captured turn."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await consistency_mod.measure_consistency(
        question=bundle.question,
        context=bundle.context,
        model=bundle.original_model,
        samples=payload.samples,
    )
    return asdict(report)


@router.post("/observability/robustness")
async def observability_robustness(payload: RobustnessRequest) -> dict[str, object]:
    """Measure how stable a captured turn is under input noise."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await robustness_mod.measure_robustness(
        question=bundle.question, context=bundle.context, model=bundle.original_model
    )
    return asdict(report)


@router.post("/observability/coverage")
async def observability_coverage(payload: CoverageRequest) -> dict[str, object]:
    """Measure how well a captured turn's retrieved chunks cover its question."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await coverage_mod.measure_coverage(question=bundle.question, chunks=chunks)
    return asdict(report)


@router.post("/observability/reranking")
async def observability_reranking(payload: CoverageRequest) -> dict[str, object]:
    """Decompose a captured turn's fused ordering into vector vs lexical shares."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await reranking_contribution_mod.measure_contribution(
        question=bundle.question, chunks=chunks
    )
    return asdict(report)


@router.post("/observability/ablation")
async def observability_ablation(payload: CoverageRequest) -> dict[str, object]:
    """Re-answer a captured turn under no-RAG / no-rerank ablations and re-judge."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await ablation_mod.measure_ablation(
        question=bundle.question,
        context=bundle.context,
        model=bundle.original_model,
        baseline=bundle.original_score,
    )
    return asdict(report)


@router.post("/observability/crosslingual")
async def observability_crosslingual(payload: CrossLingualRequest) -> dict[str, object]:
    """Re-answer a captured turn in fr/de/en and measure cross-lingual agreement."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await crosslingual_mod.measure_crosslingual(
        question=bundle.question, context=bundle.context, model=bundle.original_model
    )
    return asdict(report)


@router.post("/observability/sycophancy")
async def observability_sycophancy(payload: SycophancyRequest) -> dict[str, object]:
    """Judge whether a captured turn sycophantically validates a false premise."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await detect_sycophancy(
        question=bundle.question, answer=bundle.original_answer, context=bundle.context
    )
    return asdict(report)


@router.post("/observability/ensemble")
async def observability_ensemble(payload: EnsembleRequest) -> dict[str, object]:
    """Score a captured turn with a multi-judge ensemble; flag disagreement."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    report = await evaluate_ensemble(
        question=bundle.question, answer=bundle.original_answer, context=bundle.context
    )
    return asdict(report)


@router.get("/observability/corpus-freshness")
async def observability_corpus_freshness() -> dict[str, object]:
    """Staleness of the ingested regulatory corpora vs their review horizon (#50)."""
    from importlib import resources
    from pathlib import Path

    data_dir = Path(str(resources.files("tessera.corpus.data")))
    return asdict(corpus_freshness_mod.load_corpus_freshness(data_dir))


@router.get("/observability/roadmap")
async def observability_roadmap() -> dict[str, object]:
    """Mine telemetry signals into a ranked product backlog (#124)."""
    from importlib import resources
    from pathlib import Path

    low_threshold = 0.80
    n_turns = 0
    n_low = 0
    languages_low: dict[str, int] = {}
    for score in recent_scores():
        if score.get("metric") != "faithfulness":
            continue
        n_turns += 1
        if float(score["score"]) < low_threshold:  # type: ignore[arg-type]
            n_low += 1
            lang = score.get("language")
            key = lang if isinstance(lang, str) else "unknown"
            languages_low[key] = languages_low.get(key, 0) + 1

    questions = [b.question for b in replay_mod.recent_bundles()]
    intents = routing_intent_mod.aggregate_intents(questions)

    data_dir = Path(str(resources.files("tessera.corpus.data")))
    freshness = corpus_freshness_mod.load_corpus_freshness(data_dir)

    signals = roadmap_mod.RoadmapSignals(
        n_turns=n_turns,
        n_low_score=n_low,
        n_unknown_intent=intents.unknown,
        n_stale_corpora=freshness.n_stale,
        languages_low=languages_low,
    )
    return asdict(roadmap_mod.build_roadmap(signals))


def _read_audit_entries() -> list[dict[str, object]]:
    """Read the guard audit log into a list of parsed entry dicts (best effort)."""
    import json

    from tessera.settings import get_settings

    path = get_settings().guard.audit_file
    entries: list[dict[str, object]] = []
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "tessera.guard.audit":
                entries.append(obj)
    return entries


@router.get("/observability/memory")
async def observability_memory() -> dict[str, object]:
    """Memory-layer activity: writes, recall hit/miss, stored-injection caught (#23)."""
    return asdict(memory_obs_mod.aggregate_memory_audit(_read_audit_entries()))


@router.get("/observability/erasure-coverage")
async def observability_erasure_coverage() -> dict[str, object]:
    """The telemetry-erasure surface: conversations, bundles, scores in scope (#180)."""
    return asdict(erasure_mod.coverage(replay_mod.recent_bundles(), recent_scores()))


@router.get("/observability/erasure/{conversation_id}")
async def observability_erasure_preview(conversation_id: str) -> dict[str, object]:
    """Preview the telemetry that a GDPR erasure of this subject would purge (#180)."""
    return asdict(
        erasure_mod.footprint(
            conversation_id,
            bundles=replay_mod.recent_bundles(),
            scores=recent_scores(),
        )
    )


@router.get("/observability/memory-inventory")
async def observability_memory_inventory() -> dict[str, object]:
    """What the agent remembers: long-term store inventory (GDPR access, #135)."""
    from tessera.memory.persistent import list_inventory
    from tessera.observability.memory_inventory import InventoryItem

    try:
        rows = await list_inventory()
    except Exception as exc:  # store may be offline / empty — never break the dashboard
        sys.stderr.write(f"tessera.observability.memory_inventory: failed: {exc}\n")
        return asdict(memory_inventory_mod.summarize_inventory([]))
    items = [
        InventoryItem(
            memory_id=row.memory_id,
            subject_id=row.subject_id,
            kind=row.kind,
            text=row.text,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )
        for row in rows
    ]
    return asdict(memory_inventory_mod.summarize_inventory(items))


@router.get("/observability/journey")
async def observability_journey() -> dict[str, object]:
    """Cross-session customer journeys mined from the memory audit trail (#99)."""
    events: list[tuple[str, str, str]] = []
    for entry in _read_audit_entries():
        target = entry.get("target")
        if not (isinstance(target, str) and target.startswith("memory.")):
            continue
        args = entry.get("arguments")
        subject = args.get("subject_id") if isinstance(args, dict) else None
        occurred_at = entry.get("occurred_at")
        if isinstance(subject, str) and isinstance(occurred_at, str):
            events.append((subject, target, occurred_at))
    return asdict(journey_mod.build_journeys(events))


@router.get("/observability/embedding-inversion")
async def observability_embedding_inversion() -> dict[str, object]:
    """Embedding-inversion privacy risk over a demo corpus (#73), cached."""
    global _inversion_cache
    if _inversion_cache is None:
        from tessera.retrieval.embeddings import embed

        try:
            report = await embedding_inversion_mod.assess_inversion_risk(
                embedding_inversion_mod.DEMO_MEMORIES,
                embedding_inversion_mod.DEMO_PROBES,
                embedder=embed,
            )
            _inversion_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # embedder offline — never break the dashboard
            sys.stderr.write(f"tessera.observability.embedding_inversion: failed: {exc}\n")
            return {"available": False}
    return _inversion_cache


@router.get("/observability/failure-clusters")
async def observability_failure_clusters() -> dict[str, object]:
    """Auto-clustered themes across the documented failure corpus (#123), cached."""
    global _clustering_cache
    if _clustering_cache is None:
        from tessera.retrieval.embeddings import embed

        try:
            report = await failure_clustering_mod.cluster_failures(
                _load_failure_items(), k=6, embedder=embed
            )
            _clustering_cache = {"available": True, **asdict(report)}
        except Exception as exc:  # embedder offline — never break the dashboard
            sys.stderr.write(f"tessera.observability.failure_clustering: failed: {exc}\n")
            return {"available": False}
    return _clustering_cache


@router.get("/observability/sft-dataset")
async def observability_sft_dataset() -> dict[str, object]:
    """Distil high-scoring captured turns into an SFT dataset (#122)."""
    turns = [
        (b.question, b.context, b.original_answer, b.language, b.original_score)
        for b in replay_mod.recent_bundles()
    ]
    return asdict(sft_export_mod.build_sft_dataset(turns))


_GRANTED_TOOLS = frozenset(
    {"account_balance", "card_block", "transaction_search", "loan_simulate", "ticket_escalate"}
)


@router.get("/observability/least-privilege")
async def observability_least_privilege() -> dict[str, object]:
    """Tool least-privilege: granted vs actually-used tools from the audit (#101)."""
    # Exclude non-tool audit targets: the input guard ("user_input") and the
    # memory governance actions are audited too but are not tool invocations.
    non_tools = {"user_input"}
    usage: dict[str, int] = {}
    for entry in _read_audit_entries():
        target = entry.get("target")
        if isinstance(target, str) and target not in non_tools and not target.startswith("memory."):
            usage[target] = usage.get(target, 0) + 1
    return asdict(least_privilege_mod.analyze_privilege(_GRANTED_TOOLS, usage))


@router.get("/observability/siem")
async def observability_siem() -> dict[str, object]:
    """Security audit events normalised to ECS/SIEM shape for the SOC (#172)."""
    return asdict(siem_mod.to_siem_events(_read_audit_entries()))


@router.get("/observability/ai-act")
async def observability_ai_act() -> dict[str, object]:
    """EU AI Act compliance posture: transparency, oversight, traceability (#76)."""
    from tessera.guard.audit import verify_audit_chain
    from tessera.settings import get_settings

    entries = _read_audit_entries()
    oversight = sum(1 for e in entries if e.get("target") == "ticket_escalate")
    audit_path = get_settings().guard.audit_file
    chain = verify_audit_chain(audit_path)
    signals = ai_act_mod.AIActSignals(
        disclosure_enabled=True,  # disclosure shipped on the chat UI (#134)
        n_turns=len(replay_mod.recent_bundles()),
        oversight_events=oversight,
        escalation_available=True,
        audit_present=audit_path.exists(),
        audit_chain_verified=chain.verified,
        data_governance_enabled=True,
    )
    return asdict(ai_act_mod.assess_compliance(signals))


@router.get("/observability/localization")
async def observability_localization() -> dict[str, object]:
    """Per-locale message completeness vs the default locale (#77)."""
    import json
    from pathlib import Path

    messages_dir = Path(__file__).resolve().parents[4] / "webapp" / "frontend" / "messages"
    catalogues: dict[str, dict[str, object]] = {}
    for locale in ("en", "fr", "de"):
        path = messages_dir / f"{locale}.json"
        try:
            catalogues[locale] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            catalogues[locale] = {}
    return asdict(localization_mod.assess_localization(catalogues))


@router.get("/observability/playbooks")
async def observability_playbooks() -> dict[str, object]:
    """Incident playbooks triggered by the current live signals (#115)."""
    bundles = replay_mod.recent_bundles()
    faithfulness = [
        float(s["score"])  # type: ignore[arg-type]
        for s in recent_scores()
        if s.get("metric") == "faithfulness"
    ]
    bar = 0.80
    low_rate = (
        sum(1 for s in faithfulness if s < bar) / len(faithfulness) if faithfulness else 0.0
    )
    snapshots = redteam_mod.recent_snapshots()
    jailbreak_rate = snapshots[-1].attack_success_rate if snapshots else 0.0
    pii = pii_leak_mod.aggregate_leaks(
        [(b.original_answer, f"{b.question}\n{b.context}") for b in bundles]
    )
    cost = cost_anomaly_mod.analyze_costs(
        [(b.question, f"{b.question}\n{b.context}\n{b.original_answer}") for b in bundles]
    )
    signals = playbooks_mod.PlaybookSignals(
        low_score_rate=low_rate,
        n_scores=len(faithfulness),
        jailbreak_success_rate=jailbreak_rate,
        pii_leak_rate=pii.leak_rate,
        cost_anomalies=cost.n_anomalies,
    )
    return asdict(playbooks_mod.trigger_playbooks(signals))


@router.get("/observability/cross-tenant")
async def observability_cross_tenant() -> dict[str, object]:
    """Cross-tenant leakage: foreign subject ids in a turn's context (#74)."""
    turns = [
        (b.conversation_id or "", b.context) for b in replay_mod.recent_bundles()
    ]
    return asdict(cross_tenant_mod.detect_cross_tenant(turns))


@router.get("/observability/toxicity")
async def observability_toxicity() -> dict[str, object]:
    """Toxicity / harmful-output rate over captured answers (#60)."""
    turns = [(b.question, b.original_answer) for b in replay_mod.recent_bundles()]
    return asdict(toxicity_mod.scan_toxicity(turns))


@router.get("/observability/failure-predictor")
async def observability_failure_predictor() -> dict[str, object]:
    """Back-test the pre-judge failure predictor against captured turns (#121)."""
    turns = [
        (b.question, b.context, b.original_score) for b in replay_mod.recent_bundles()
    ]
    return asdict(failure_predictor_mod.evaluate_predictor(turns))


@router.get("/observability/embedding-skew")
async def observability_embedding_skew() -> dict[str, object]:
    """Embedding-version skew between the query-time and corpus embedders (#64)."""
    from tessera.observability.embedding_skew import EmbeddingFingerprint
    from tessera.retrieval.embeddings import embedding_dimension
    from tessera.settings import LLMProfile, get_settings

    settings = get_settings()
    if settings.resolved_llm_profile() is LLMProfile.FRONTIER:
        query_model = settings.vertex.embedding_model
    else:
        query_model = settings.ollama.embedding_model
    query = EmbeddingFingerprint(model=query_model, dimension=embedding_dimension())
    # Until the corpus records its own fingerprint at ingestion, we treat the
    # active embedder as the corpus reference: equal by construction, so the check
    # reports "no skew" while still surfacing the live embedding identity and
    # flagging a future query-side profile flip.
    corpus = query
    return asdict(embedding_skew_mod.detect_skew(query, corpus))


@router.get("/observability/firewall-efficacy")
async def observability_firewall_efficacy() -> dict[str, object]:
    """Detection efficacy of the guard over injection vs benign inputs."""
    return asdict(firewall_mod.compute_efficacy())


@router.get("/observability/redteam")
async def observability_redteam() -> dict[str, object]:
    """Return the recorded jailbreak-drift snapshots (newest last)."""
    return {"snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()]}


@router.post("/observability/redteam")
async def observability_redteam_run() -> dict[str, object]:
    """Run the adversarial corpus through the guard and record a snapshot."""
    snapshot = redteam_mod.run_redteam()
    return {
        "latest": asdict(snapshot),
        "snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()],
    }


@router.get("/observability/refusal")
async def observability_refusal() -> dict[str, object]:
    """Refusal-rate calibration: over-refusal (legit) vs under-refusal (forbidden)."""
    return asdict(refusal_mod.compute_refusal_calibration())


@router.get("/observability/conformance")
async def observability_conformance() -> dict[str, object]:
    """Schema/format conformance of tool-call arguments from the audit trail."""
    return asdict(conformance_mod.compute_conformance())


@router.get("/observability/cost")
async def observability_cost() -> dict[str, object]:
    """Token-cost distribution and token-burn anomalies over captured turns."""
    turns = [
        (b.question, f"{b.question}\n{b.context}\n{b.original_answer}")
        for b in replay_mod.recent_bundles()
    ]
    return asdict(cost_anomaly_mod.analyze_costs(turns))


@router.get("/observability/guard-explain")
async def observability_guard_explain() -> dict[str, object]:
    """Ranked breakdown of which guard rules fired across the audit trail."""
    return asdict(guard_explain_mod.compute_guard_explain())


@router.get("/observability/tool-validity")
async def observability_tool_validity() -> dict[str, object]:
    """Validity of tool calls (allowed vs denied, argument failures)."""
    return asdict(tool_validity_mod.compute_tool_validity())


@router.get("/observability/routing")
async def observability_routing() -> dict[str, object]:
    """Language-routing health: served vs detected language, code-switching."""
    turns = [(b.question, b.language) for b in replay_mod.recent_bundles()]
    return asdict(language_routing_mod.aggregate_routing(turns))


@router.get("/observability/intent")
async def observability_intent() -> dict[str, object]:
    """Business-intent mix and routing confidence over captured questions."""
    questions = [b.question for b in replay_mod.recent_bundles()]
    return asdict(routing_intent_mod.aggregate_intents(questions))


@router.get("/observability/citations")
async def observability_citations() -> dict[str, object]:
    """Regulatory citation validity: cited articles absent from the grounding."""
    turns = [(b.original_answer, b.context) for b in replay_mod.recent_bundles()]
    return asdict(citation_validity_mod.aggregate_citations(turns))


@router.get("/observability/locale-format")
async def observability_locale_format() -> dict[str, object]:
    """Locale-formatting correctness: amounts whose style mismatches the locale."""
    turns = [(b.original_answer, b.language) for b in replay_mod.recent_bundles()]
    return asdict(locale_format_mod.aggregate_formatting(turns))


@router.get("/observability/pii-leak")
async def observability_pii_leak() -> dict[str, object]:
    """Output PII-leak rate: PII in answers absent from their grounding."""
    turns = [(b.original_answer, f"{b.question}\n{b.context}") for b in replay_mod.recent_bundles()]
    return asdict(pii_leak_mod.aggregate_leaks(turns))


@router.get("/observability/anomalies")
async def observability_anomalies() -> dict[str, object]:
    """Detect long/looping/repetitive sessions among captured turns."""
    by_conversation: dict[str, list[str]] = {}
    for bundle in replay_mod.recent_bundles():
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append(bundle.question)
    return asdict(anomalies_mod.detect_anomalies(by_conversation))


@router.get("/observability/what-changed")
async def observability_what_changed() -> dict[str, object]:
    """Attribute a score change to the lineage diff of the last two turns."""
    with_lineage = [b for b in replay_mod.recent_bundles() if b.lineage is not None]
    if len(with_lineage) < 2:  # noqa: PLR2004 — need two turns to diff
        return {"available": False}
    prev, curr = with_lineage[-2], with_lineage[-1]
    assert prev.lineage is not None  # narrowed by the filter above
    assert curr.lineage is not None
    report = whatchanged_mod.what_changed(
        prev_lineage=prev.lineage,
        prev_score=prev.original_score,
        curr_lineage=curr.lineage,
        curr_score=curr.original_score,
    )
    return {"available": True, **asdict(report)}


@router.get("/observability/funnel")
async def observability_funnel() -> dict[str, object]:
    """Per-language conversation funnel from scored turns."""
    turns: list[tuple[str, str | None, float]] = []
    for score in recent_scores():
        lang = score.get("language")
        conv = score.get("conversation_id")
        raw = score.get("score", 0.0)
        turns.append(
            (
                lang if isinstance(lang, str) else "unknown",
                conv if isinstance(conv, str) else None,
                float(raw),  # type: ignore[arg-type]
            )
        )
    return asdict(funnel_mod.aggregate_funnel(turns))


@router.get("/observability/sessions")
async def observability_sessions() -> dict[str, object]:
    """Session-level goal-completion analytics from scored turns."""
    turns: list[tuple[str | None, float]] = []
    for score in recent_scores():
        conv = score.get("conversation_id")
        raw = score.get("score", 0.0)
        turns.append((conv if isinstance(conv, str) else None, float(raw)))  # type: ignore[arg-type]
    return asdict(sessions_mod.aggregate_sessions(turns))


@router.get("/observability/contradictions")
async def observability_contradictions() -> dict[str, object]:
    """Detect self-contradictions across the turns of each captured session."""
    by_conversation: dict[str, list[tuple[str, str]]] = {}
    for bundle in replay_mod.recent_bundles():
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append((bundle.question, bundle.original_answer))

    n_turns = 0
    pairs: list[dict[str, object]] = []
    for conversation_id, turns in by_conversation.items():
        n_turns += len(turns)
        report = await contradiction_mod.detect_contradictions(turns)
        for pair in report.contradictions:
            pairs.append({"conversation_id": conversation_id, **asdict(pair)})

    return {
        "n_sessions": len(by_conversation),
        "n_turns": n_turns,
        "n_contradictions": len(pairs),
        "pairs": pairs,
    }


@router.get("/observability/corpus-scan/{bundle_id}")
async def observability_corpus_scan(bundle_id: str) -> dict[str, object]:
    """Screen a captured turn's retrieved chunks for indirect injection."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    return asdict(corpus_injection_mod.scan_chunks(chunks))


@router.get("/observability/steganography/{bundle_id}")
async def observability_steganography(bundle_id: str) -> dict[str, object]:
    """Detect hidden unicode (zero-width/bidi/tag) in a captured turn."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    return asdict(steganography_mod.scan_text(f"{bundle.question}\n{bundle.context}"))


@router.get("/observability/trajectory/{bundle_id}")
async def observability_trajectory(bundle_id: str) -> dict[str, object]:
    """Step-by-step trajectory of a captured turn (session theater)."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    return asdict(trajectory_mod.build_trajectory(bundle))


@router.get("/observability/provenance/{bundle_id}")
async def observability_provenance(bundle_id: str) -> dict[str, object]:
    """Claim-level attribution of a captured turn to its retrieved chunks."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await provenance_mod.attribute(bundle.original_answer, chunks)
    util = retrieval_quality_mod.utilization(report, len(chunks))
    return {**asdict(report), "utilization": asdict(util)}
