"""Observability routes — safety surface."""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from tessera.api.routes.observability._common import (
    _GRANTED_TOOLS,
    _agent_or_none,
    _bundles_for,
    _read_audit_entries,
    _scores_for,
)
from tessera.observability import (
    cost_anomaly as cost_anomaly_mod,
    cross_tenant as cross_tenant_mod,
    embedding_inversion as embedding_inversion_mod,
    embedding_skew as embedding_skew_mod,
    firewall_efficacy as firewall_mod,
    guard_explain as guard_explain_mod,
    guard_retraction as guard_retraction_mod,
    incidents as incidents_mod,
    least_privilege as least_privilege_mod,
    pii_leak as pii_leak_mod,
    playbooks as playbooks_mod,
    policies as policies_mod,
    redteam as redteam_mod,
    refusal as refusal_mod,
    replay as replay_mod,
    siem as siem_mod,
    steganography as steganography_mod,
    tool_loops as tool_loops_mod,
    tool_validity as tool_validity_mod,
    toxicity as toxicity_mod,
)
from tessera.observability.read_snapshot import (
    SNAPSHOT_TTL_S,
    incidents_snapshot_key,
    read_snapshot,
)
from tessera.observability.spine.scope import parse_period_days

router = APIRouter()

_inversion_cache: dict[str, object] | None = None


@router.get("/observability/guardrail-catalogue")
def observability_guardrail_catalogue(lang: str = "fr", agent: str = "all") -> dict[str, object]:
    """CONFIGURER platform guardrail catalogue (configurer/garde-fous).

    The guardrail profiles agents bind, with the real shared-policy composition,
    audit posture and consuming agents (re-gate blast radius). Filterable by
    agent. Degrades to ``available: false`` on failure.
    """
    from tessera.observability import guardrail_catalogue as gc_mod

    try:
        return {"available": True, **gc_mod.build_guardrail_catalogue(lang, agent_scope=agent)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.guardrail_catalogue: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/incidents")
def observability_incidents(lang: str = "fr", at: str | None = None) -> dict[str, object]:
    """Incidents & playbooks overview (page #10).

    Composes the current incident posture, the triage queue with recommended
    playbooks, the running playbook timeline, the automation rules and the
    7-day impact charts into one payload. ``lang`` localizes the chrome and the
    per-tab operational catalogues. ``at`` (ISO instant) reads the posture as
    of T: deny window ending at T, bundles ≤ T, durable incidents replayed from
    their journals (registre §6 — AGIR As-of). Degrades to ``available: false``.

    The DEFAULT live view (``at=None``) is served from the leader-computed shared
    snapshot (ADR 0046): clustering the deny ledger is seconds cold and its
    per-worker memo expires between page visits, so a fresh visit recurrently hit
    a cold worker and waited. An as-of-T read, or a snapshot miss, computes fresh.
    """
    if at is None:
        snap = read_snapshot(incidents_snapshot_key(lang), SNAPSHOT_TTL_S)
        if snap is not None:
            return snap
    try:
        return {"available": True, **incidents_mod.compute_incidents_overview(lang, at)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.incidents: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/policies")
def observability_policies(lang: str = "fr") -> dict[str, object]:
    """Policies & guardrails overview (page #16-policies).

    Composes the version timeline, posture KPIs, critical active policies,
    version history, YAML diff, runtime guardrails, impact simulator and
    sensitive actions. Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **policies_mod.compute_policies_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.policies: failed: {exc}\n")
        return {"available": False}


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


@router.get("/observability/least-privilege")
def observability_least_privilege() -> dict[str, object]:
    """Tool least-privilege: granted vs actually-used tools from the audit (#101)."""
    # Exclude non-tool audit targets: the input guard ("user_input") and the
    # memory governance actions are audited too but are not tool invocations.
    non_tools = {"user_input"}
    from tessera.guard.ledger_store import audit_target_call_counts, ledger_source

    if ledger_source() == "postgres":
        # The DB counts per target (a handful of rows) instead of materialising 64 k payloads to
        # do usage[target] += 1. The exclusions apply to the small result — byte-identical usage.
        usage = {
            target: count
            for target, count in audit_target_call_counts("tessera.guard.audit").items()
            if target not in non_tools and not target.startswith("memory.")
        }
    else:
        usage = {}
        for entry in _read_audit_entries():
            target = entry.get("target")
            if (
                isinstance(target, str)
                and target not in non_tools
                and not target.startswith("memory.")
            ):
                usage[target] = usage.get(target, 0) + 1
    return asdict(least_privilege_mod.analyze_privilege(_GRANTED_TOOLS, usage))


@router.get("/observability/siem")
def observability_siem() -> dict[str, object]:
    """Security audit events normalised to ECS/SIEM shape for the SOC (#172)."""
    return asdict(siem_mod.to_siem_events(_read_audit_entries()))


@router.get("/observability/playbooks")
def observability_playbooks(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Incident playbooks triggered by the live (or as-of-T) signals (#115).

    Bundle- and score-derived inputs honour T and the selected period; the jailbreak
    rate is the latest red-team snapshot (a periodic probe, not a per-turn event), so
    it stays live. ``agent`` scopes the bundle/score inputs to one agent (``all`` = org
    view); the shared red-team probe stays org.
    """
    ag = _agent_or_none(agent)
    window = parse_period_days(days)
    bundles = _bundles_for(at, ag, window)
    faithfulness = [
        float(s["score"])  # type: ignore[arg-type]
        for s in _scores_for(at, ag, window)
        if s.get("metric") == "faithfulness"
    ]
    bar = 0.80
    low_rate = sum(1 for s in faithfulness if s < bar) / len(faithfulness) if faithfulness else 0.0
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
        # Zero snapshots is not a zero attack-success rate: `snapshots[-1]` does not exist, so
        # `jailbreak_rate` falls back to 0.0 above and would otherwise read as "no bypasses".
        n_snapshots=len(snapshots),
        pii_leak_rate=pii.leak_rate,
        cost_anomalies=cost.n_anomalies,
        # Both PII and cost derive from the same captured bundles. On 2026-08-01 this was ZERO
        # (last conversation 2026-07-24, seven-day window) and the panel reported no incidents.
        n_turns=len(bundles),
    )
    return asdict(playbooks_mod.trigger_playbooks(signals))


@router.get("/observability/cross-tenant")
def observability_cross_tenant() -> dict[str, object]:
    """Cross-tenant leakage: foreign subject ids in a turn's context (#74)."""
    turns = [(b.conversation_id or "", b.context) for b in replay_mod.recent_bundles()]
    return asdict(cross_tenant_mod.detect_cross_tenant(turns))


@router.get("/observability/toxicity")
def observability_toxicity(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Toxicity / harmful-output rate over captured answers (#60), live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view); ``days`` to the period.
    """
    turns = [
        (b.question, b.original_answer)
        for b in _bundles_for(at, _agent_or_none(agent), parse_period_days(days))
    ]
    return asdict(toxicity_mod.scan_toxicity(turns))


@router.get("/observability/embedding-skew")
async def observability_embedding_skew() -> dict[str, object]:
    """Embedding-version skew between the query-time and corpus embedders (#64).

    The corpus side is now READ BACK from the store: every row ingested since 2026-08-01
    records the model it was embedded with and the width of the vector it produced. Before
    that the active embedder stood in as the corpus reference — equal by construction, a
    comparison of a thing with itself that could not fail — and the report said so with
    ``corpus_known: false`` rather than pretending to a clean bill.

    Rows ingested before the columns existed carry no fingerprint. They are neither a skew nor
    a clearance: they are counted as ``unfingerprinted`` and reported separately, because the
    part of the corpus a witness cannot see is the part it must name.
    """
    from tessera.observability.embedding_skew import EmbeddingFingerprint
    from tessera.retrieval.embeddings import embedding_dimension
    from tessera.retrieval.store import corpus_fingerprints
    from tessera.settings import LLMProfile, get_settings

    settings = get_settings()
    if settings.resolved_llm_profile() is LLMProfile.FRONTIER:
        query_model = settings.vertex.embedding_model
    else:
        query_model = settings.ollama.embedding_model
    query = EmbeddingFingerprint(model=query_model, dimension=embedding_dimension())

    groups: list[tuple[str | None, int | None, int]] = []
    try:
        groups = await corpus_fingerprints()
    except Exception as exc:  # an unreachable store is a blind spot, never a clean bill
        sys.stderr.write(f"tessera.observability.embedding_skew: corpus unreadable: {exc}\n")
        report = asdict(embedding_skew_mod.detect_skew(query, query, corpus_known=False))
        return {**report, "corpus_rows": 0, "unfingerprinted_rows": 0, "spaces": []}

    known = [(m, d, n) for m, d, n in groups if m is not None and d is not None]
    unfingerprinted = sum(n for m, d, n in groups if m is None or d is None)
    if not known:
        # An empty corpus and a wholly unfingerprinted one are both "cannot compare", and both
        # must stay distinguishable from "compared, and fine".
        report = asdict(embedding_skew_mod.detect_skew(query, query, corpus_known=False))
        return {
            **report,
            "corpus_rows": unfingerprinted,
            "unfingerprinted_rows": unfingerprinted,
            "spaces": [],
        }

    # The LARGEST recorded space is the corpus reference — a partial re-ingestion under a new
    # model leaves two spaces, and the majority one is what queries mostly land against. Every
    # space travels in `spaces` so a split corpus is visible rather than averaged away.
    model, dimension, _ = known[0]
    corpus = EmbeddingFingerprint(model=str(model), dimension=int(dimension))
    report = asdict(embedding_skew_mod.detect_skew(query, corpus, corpus_known=True))
    return {
        **report,
        "corpus_rows": sum(n for _, _, n in groups),
        "unfingerprinted_rows": unfingerprinted,
        "spaces": [{"model": m, "dimension": d, "rows": n} for m, d, n in known],
    }


@router.get("/observability/firewall-efficacy")
def observability_firewall_efficacy() -> dict[str, object]:
    """Detection efficacy of the guard over injection vs benign inputs.

    The report is a deterministic fixed-corpus probe; the ``observed_at`` stamp is
    the live recompute time (ADR 0029) — the measurement is dated by *when it was
    read*, not by a wall clock baked into the reproducible measurement content.
    """
    from datetime import UTC, datetime

    return {**asdict(firewall_mod.compute_efficacy()), "observed_at": datetime.now(UTC).isoformat()}


@router.get("/observability/redteam")
def observability_redteam() -> dict[str, object]:
    """Return the recorded jailbreak-drift snapshots (newest last)."""
    return {"snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()]}


@router.get("/observability/refusal")
def observability_refusal() -> dict[str, object]:
    """Refusal-rate calibration: over-refusal (legit) vs under-refusal (forbidden)."""
    return asdict(refusal_mod.compute_refusal_calibration())


@router.get("/observability/guard-retraction")
def observability_guard_retraction() -> dict[str, object]:
    """Streamed-token exposure before an output-guard trigger fires (#90)."""
    from tessera.guard.decisions import load_policy

    answers = [b.original_answer for b in replay_mod.recent_bundles()]
    return asdict(guard_retraction_mod.analyze_retractions(answers, policy=load_policy()))


@router.get("/observability/guard-explain")
def observability_guard_explain() -> dict[str, object]:
    """Ranked breakdown of which guard rules fired across the audit trail."""
    return asdict(guard_explain_mod.compute_guard_explain())


@router.get("/observability/tool-loops")
def observability_tool_loops() -> dict[str, object]:
    """Tool-call loop/oscillation detection over the audit invocation stream (#88)."""
    non_tools = {"user_input"}
    ordered: list[tuple[str, str]] = []  # (occurred_at, tool)
    for entry in _read_audit_entries():
        target = entry.get("target")
        if not (isinstance(target, str) and target not in non_tools):
            continue
        if target.startswith("memory."):
            continue
        occurred = entry.get("occurred_at")
        ordered.append((occurred if isinstance(occurred, str) else "", target))
    ordered.sort(key=lambda pair: pair[0])
    # The audit trail is not conversation-scoped, so analyse one global stream.
    streams = {"global": [tool for _at, tool in ordered]}
    return asdict(tool_loops_mod.detect_loops(streams))


@router.get("/observability/tool-validity")
def observability_tool_validity(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Validity of tool calls (allowed vs denied, argument failures), live or as of T.

    ``agent`` scopes to one agent's tool calls (``all`` = org view); ``days`` to the period.
    """
    return asdict(
        tool_validity_mod.compute_tool_validity(
            at=at, agent_id=_agent_or_none(agent), days=parse_period_days(days)
        )
    )


@router.get("/observability/pii-leak")
def observability_pii_leak(
    at: str | None = None, agent: str = "all", days: str | None = None
) -> dict[str, object]:
    """Output PII-leak rate: PII in answers absent from their grounding, live or as of T.

    ``agent`` scopes to one agent's captured turns (``all`` = org view); ``days`` to the period.
    """
    turns = [
        (b.original_answer, f"{b.question}\n{b.context}")
        for b in _bundles_for(at, _agent_or_none(agent), parse_period_days(days))
    ]
    return asdict(pii_leak_mod.aggregate_leaks(turns))


@router.get("/observability/steganography/{bundle_id}")
def observability_steganography(bundle_id: str) -> dict[str, object]:
    """Detect hidden unicode (zero-width/bidi/tag) in a captured turn."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    return asdict(steganography_mod.scan_text(f"{bundle.question}\n{bundle.context}"))
