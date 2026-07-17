"""Observability routes — the 26 operator mutations, behind one guard.

Audit 2026-07-10, **P0 `broken-access-control`**: these 26 endpoints were reachable
ANONYMOUSLY (route.ts:25/81 · observability.py 26x · main.py:310). They promote an agent to
production, rewrite runtime configuration, switch a guardrail off and mutate the governance
stores — and the public BFF proxied POSTs to them with no session check at all, attaching the
service bearer on the caller's behalf.

The guard is declared HERE, on the router, rather than at the mount site: a mutation added to
this module inherits it by construction, and there is no way to add one that forgets it. That
is the whole point of splitting the god-router — the flat 152-route module had nowhere to
attach a single ``dependencies=``, which is what let the drift happen in the first place.
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.api.security import actor_of, require_operator
from tessera.api.session import (  # noqa: TCH001  — FastAPI resolves Depends annotations at runtime
    SessionContext,
)
from tessera.guard.audit import emit_governance_mutation
from tessera.observability import (
    ablation as ablation_mod,
    agent_a_faire as agent_a_faire_mod,
    agent_configurations as agent_configurations_mod,
    agent_garde_fous as agent_garde_fous_mod,
    automations as automations_mod,
    client_space as client_space_mod,
    consistency as consistency_mod,
    console_feedback as console_feedback_mod,
    coverage as coverage_mod,
    crosslingual as crosslingual_mod,
    curation as curation_mod,
    etat_a_date as etat_a_date_mod,
    inbox as inbox_mod,
    knowledge as knowledge_mod,
    redteam as redteam_mod,
    replay as replay_mod,
    reranking_contribution as reranking_contribution_mod,
    robustness as robustness_mod,
    shadow as shadow_mod,
    why_answer as why_answer_mod,
)
from tessera.observability.eval.ensemble import evaluate_ensemble
from tessera.observability.eval.sycophancy import detect_sycophancy

#: Every route in this module mutates state, so every route requires a verified operator.
#: Declared on the router, not per-route: a new mutation cannot be added without the guard.
router = APIRouter(dependencies=[Depends(require_operator)])


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


class _AgentProposeBody(BaseModel):
    """A governed proposal to add a new agent to the fleet."""

    name: str


class _AgentReleaseBody(BaseModel):
    """A governed request to promote an agent (version) to live."""

    agent_id: str


class _RuleStateBody(BaseModel):
    """Enable/disable mutation for one guard rule."""

    key: str
    enabled: bool


class _SourceStateBody(BaseModel):
    """Attach/detach/activate mutation for one knowledge source."""

    key: str
    attached: bool | None = None
    active: bool | None = None


class _AgentConfigBody(BaseModel):
    """A set of agent-profile overrides to persist (only known keys are kept)."""

    changes: dict[str, object]
    lang: str = "fr"


class _ConsoleFeedbackBody(BaseModel):
    """A single thumbs up/down on a console chat turn, persisted durably."""

    conversation_id: str
    turn: int = Field(ge=0)
    rating: str | None = None


class _EtatSnapshotBody(BaseModel):
    """Body for saving an Etat-a-date reconstruction snapshot."""

    model_config = ConfigDict(extra="forbid")
    as_of: str | None = None
    sources: str | None = None
    lang: str = "fr"
    agent: str | None = None


class _ItemStateBody(BaseModel):
    """Status/assignee mutation for one operator-queue item."""

    item_id: str
    status: str | None = None
    assignee: str | None = None
    lang: str = "fr"


class _AutomationRuleStateBody(BaseModel):
    """Durable enable/disable for one code-defined automation rule."""

    rule_id: str
    enabled: bool
    lang: str = "fr"


class _AutomationRulesStateBody(BaseModel):
    """Bulk enable/suspend for EVERY code-defined automation rule.

    ``extra="forbid"``: a field this body tolerates is a field a caller can
    send — an author-naming one gets a loud 422, never a silent forgery.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    lang: str = "fr"


class _AutomationApproveBody(BaseModel):
    """A decision on one pending approval request (approve or reject).

    No ``decided_by`` field on purpose — the author is the verified assertion
    principal, and ``extra="forbid"`` turns any attempt to name one into a 422
    (ADR 0024).
    """

    model_config = ConfigDict(extra="forbid")

    approval_id: str
    approved: bool
    lang: str = "fr"


class _CurationDecisionBody(BaseModel):
    """A durable curation decision (promote/review/reject) for one candidate.

    ``decided_by`` is **gone**, and ``extra="forbid"`` is what makes its removal load-bearing:
    a caller who still sends one now gets a **422**, loudly, instead of having their chosen
    name silently dropped — and F-1's lesson is that a silently dropped identity field and an
    honoured one are indistinguishable from the outside. The name in the register comes from
    the session the server verified (:func:`~tessera.api.security.actor_of`); a caller who can
    choose it can sign someone else's decision.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    decision: str
    lang: str = "fr"


class _AlertReadBody(BaseModel):
    """Mark one account alert read/unread (durable)."""

    alert_id: str
    read: bool = True
    lang: str = "fr"


class _SettingBody(BaseModel):
    """Update one customer preference (durable)."""

    key: str
    value: object
    lang: str = "fr"


@router.post("/observability/shadow")
async def observability_shadow(payload: ShadowRequest) -> dict[str, object]:
    """Mirror recent captured turns to a candidate model and compare (shadow)."""
    report = await shadow_mod.run_shadow(
        replay_mod.recent_bundles(), model=payload.model, limit=payload.limit
    )
    return asdict(report)


@router.post("/observability/agents/propose")
async def observability_agents_propose(
    body: _AgentProposeBody,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> dict[str, object]:
    """Record a governed, audited proposal to add an agent.

    An agent is a package approved as a unit (ADR 0012), so the registry is not
    mutated at runtime: this emits an auditable S1 event (proposal) that feeds the
    propose -> review -> release flow. RBAC is enforced on the client; the event
    captures the intent durably either way.

    The proposal named ``"operator"`` as its author until 2026-07-13 — the default on
    ``emit_agent_proposed``, which this route never overrode. It names the verified principal now.
    """
    from tessera.guard.audit import emit_agent_proposed

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    emit_agent_proposed(name=name, actor=actor_of(session))
    return {"available": True, "proposed": name}


@router.post("/observability/agents/release")
async def observability_agents_release(
    body: _AgentReleaseBody,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> dict[str, object]:
    """Attempt to promote an agent to live — gated by its eval-gate.

    An agent only goes live once a run of ITS own set cleared the two-level gate.
    The attempt is recorded as a hash-chained S1 event (``released`` on success,
    ``release_blocked`` otherwise), so the promotion is opposable either way.

    **Opposable to whom, though?** The gate's verdict was in the chain and the promoter's name
    was not: ``request_release`` defaulted its ``actor`` to the literal ``"operator"``, so every
    promotion this fleet ever performed carried the same author. Two people promoting two agents
    produced two byte-identical attributions — a record that cannot distinguish them is not a
    record of who did it. ``actor_of(session)`` is the principal of the verified assertion.
    """
    from tessera.observability.agent_lifecycle import request_release

    agent_id = body.agent_id.strip()
    if not agent_id:
        raise HTTPException(status_code=422, detail="agent_id is required")
    decision = request_release(agent_id, actor=actor_of(session))
    return {"available": True, **decision.as_dict()}


@router.post("/observability/agent-garde-fous/rule-state")
async def observability_agent_garde_fous_mutate(
    body: _RuleStateBody,
    session: Annotated[SessionContext, Depends(require_operator)],
    lang: str = "fr",
) -> dict[str, object]:
    """Persist an enable/disable change and return the fresh payload.

    **Switching a guardrail off is the single most sensitive act this cockpit offers**, and it
    wrote nothing at all to the ledger (ADR 0024 §Owed). The store flipped a flag in a JSON file
    and returned a fresh page; the chain never learned that the injection screen had been
    disabled, still less by whom. Every incident review that ever asked *"was the guard on?"*
    would have been answered from the guard's **current** state, which is the one thing that
    cannot testify about the past.

    The entry is written **before** the mutation, and that ordering is deliberate: if the store
    write fails, the ledger holds an attempt that did not take effect — recoverable, and visibly
    odd. The reverse order loses the act entirely on exactly the runs where something went wrong.
    """
    if body.key not in agent_garde_fous_mod.available_rules():
        raise HTTPException(status_code=404, detail="unknown rule")
    emit_governance_mutation(
        target="guard.rule_state",
        detail={"rule": body.key, "enabled": body.enabled},
        actor=actor_of(session),
    )
    agent_garde_fous_mod.set_rule_state(body.key, enabled=body.enabled)
    return {"available": True, **(await agent_garde_fous_mod.build_agent_garde_fous(lang))}


@router.post("/observability/agent-connaissances/source-state")
async def observability_agent_connaissances_mutate(
    body: _SourceStateBody, lang: str = "fr"
) -> dict[str, object]:
    """Persist an attach/detach/activate change and return the fresh payload."""
    if body.key not in knowledge_mod.available_sources():
        raise HTTPException(status_code=404, detail="unknown source")
    knowledge_mod.set_source_state(body.key, attached=body.attached, active=body.active)
    return {"available": True, **(await knowledge_mod.build_connaissances(lang))}


@router.post("/observability/agent-configurations/config")
async def observability_agent_configurations_save(
    body: _AgentConfigBody, agent_id: str = DEFAULT_AGENT_ID
) -> dict[str, object]:
    """Persist editable agent-profile overrides and return the fresh payload.

    Incoming option values may be localized; ``set_agent_config`` re-canonicalizes
    them to French before persisting, so the durable store stays locale-stable.
    """
    unknown = set(body.changes) - agent_configurations_mod.available_config_keys()
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown keys: {sorted(unknown)}")
    agent_configurations_mod.set_agent_config(body.changes, agent_id)
    return {
        "available": True,
        **agent_configurations_mod.compute_agent_configurations(agent_id, body.lang),
    }


@router.post("/observability/agent-console/feedback")
async def observability_agent_console_feedback_save(
    body: _ConsoleFeedbackBody,
) -> dict[str, object]:
    """Persist (or toggle off) one turn's rating and return the fresh map."""
    if body.rating is not None and body.rating not in console_feedback_mod.available_ratings:
        raise HTTPException(status_code=422, detail="rating must be 'up', 'down' or null")
    ratings = console_feedback_mod.record_console_feedback(
        body.conversation_id, body.turn, body.rating
    )
    return {"ratings": ratings}


@router.post("/observability/etat-a-date/snapshot")
async def observability_etat_a_date_snapshot(body: _EtatSnapshotBody) -> dict[str, object]:
    """Persist a snapshot of the reconstruction at ``body.as_of``.

    Saves to the durable snapshot store and returns the refreshed payload with
    the new snapshot at the head of the list, shaped by the optional per-source
    ``body.sources`` scope and localized by ``body.lang``.
    """
    if body.agent is not None:
        from tessera.agent.registry import list_agents

        if body.agent not in {a.id for a in list_agents()}:
            raise HTTPException(status_code=422, detail=f"unknown fleet agent {body.agent!r}")
    return await etat_a_date_mod.save_etat_snapshot(
        body.as_of, body.sources, body.lang, agent=body.agent
    )


@router.post("/observability/inbox/item-state")
async def observability_inbox_mutate(body: _ItemStateBody) -> dict[str, object]:
    """Persist a status/assignee change for one queue item; return fresh payload."""
    from tessera.observability import operator_items as operator_items_mod

    if body.item_id not in operator_items_mod.available_item_ids():
        raise HTTPException(status_code=404, detail="unknown item")
    operator_items_mod.set_item_state(body.item_id, status=body.status, assignee=body.assignee)
    return {"available": True, **inbox_mod.compute_inbox_overview(lang=body.lang)}


@router.post("/observability/agent-a-faire/item-state")
async def observability_agent_a_faire_mutate(body: _ItemStateBody) -> dict[str, object]:
    """Persist a status/assignee change for one A-faire item; return fresh payload."""
    from tessera.observability import operator_items as operator_items_mod

    if body.item_id not in operator_items_mod.available_item_ids():
        raise HTTPException(status_code=404, detail="unknown item")
    operator_items_mod.set_item_state(body.item_id, status=body.status, assignee=body.assignee)
    return {"available": True, **agent_a_faire_mod.compute_agent_a_faire(body.lang)}


@router.post("/observability/automations/evaluate")
async def observability_automations_evaluate(lang: str = "fr") -> dict[str, object]:
    """Evaluate every enabled automation rule against its REAL store now.

    Each evaluation is journalled durably (automation_runs.json); the fresh
    overview payload is returned so the client swaps its cache in one trip.
    """
    from tessera.observability import automation_store

    automation_store.evaluate_rules()
    return {"available": True, **automations_mod.compute_automations_overview(lang)}


@router.post("/observability/automations/rule-state")
async def observability_automations_rule_state(
    body: _AutomationRuleStateBody,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> dict[str, object]:
    """Persist a rule's enabled flag; 404 on unknown rule; returns fresh payload.

    The exact twin of the guardrail toggle above, silent for the same reason, and found by
    asking the question *as a class* rather than route by route: ADR 0024 §Owed named the
    guardrail; the class ratchet named this one too. That is the difference between fixing a
    finding and closing a class — the second one catches the instance nobody wrote down.
    """
    from tessera.observability import automation_store

    if body.rule_id not in automation_store.available_rule_ids():
        raise HTTPException(status_code=404, detail="unknown automation rule")
    emit_governance_mutation(
        target="automation.rule_state",
        detail={"rule": body.rule_id, "enabled": body.enabled},
        actor=actor_of(session),
    )
    automation_store.set_rule_enabled(body.rule_id, enabled=body.enabled)
    return {"available": True, **automations_mod.compute_automations_overview(body.lang)}


@router.post("/observability/automations/rules-state")
async def observability_automations_rules_state(
    body: _AutomationRulesStateBody,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> dict[str, object]:
    """Enable or suspend EVERY automation rule in one governed act.

    The cockpit's "activate / suspend the automations" quick actions: an
    org-wide kill switch is a real operational act, so it is journalled once
    with the full rule list it touched — five per-rule entries would hide that
    ONE decision was taken. Returns the fresh payload.
    """
    from tessera.observability import automation_store

    rule_ids = sorted(automation_store.available_rule_ids())
    emit_governance_mutation(
        target="automation.rules_state",
        detail={"enabled": body.enabled, "rules": rule_ids},
        actor=actor_of(session),
    )
    for rule_id in rule_ids:
        automation_store.set_rule_enabled(rule_id, enabled=body.enabled)
    return {"available": True, **automations_mod.compute_automations_overview(body.lang)}


@router.post("/observability/automations/approve")
async def observability_automations_approve(
    body: _AutomationApproveBody,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> dict[str, object]:
    """Decide one pending approval request opened by a fired approb-mode rule.

    The decision is durable and attributed: the store records the verified
    principal, the journal carries the same author, and a request already
    decided (or unknown) is a 404 — a second decision must never silently
    overwrite the first author. Returns the fresh payload.
    """
    from tessera.observability import automation_store

    actor = actor_of(session)
    try:
        entry = automation_store.decide_approval(
            body.approval_id, approved=body.approved, decided_by=actor.principal
        )
    except automation_store.ApprovalNotPendingError as exc:
        raise HTTPException(
            status_code=404, detail="unknown or already-decided approval request"
        ) from exc
    emit_governance_mutation(
        target="automation.approval",
        detail={
            "approval": body.approval_id,
            "rule": str(entry.get("rule_id", "")),
            "approved": body.approved,
        },
        actor=actor,
    )
    return {"available": True, **automations_mod.compute_automations_overview(body.lang)}


@router.post("/observability/curation/decision")
async def observability_curation_decision(
    body: _CurationDecisionBody,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> dict[str, object]:
    """Persist a curation decision for one real candidate; return the fresh payload.

    **Authentication is not attribution**, and this route is where that distinction was costing
    us. It has carried ``require_operator`` on its router since the 26 anonymous mutations were
    closed — the door was locked — and it then wrote ``decided_by=body.decided_by`` into the
    register: a verified operator could sign a curation decision **in anyone's name**. That is
    F-1's body-chosen attribution, alive inside a router we had hardened, which is precisely why
    a guard alone never closes this class. The guard answers *may you come in*; only a
    server-derived :class:`~tessera.authz.Actor` answers *who signed*.
    """
    from tessera.observability import curation_store

    if body.candidate_id not in curation_store.available_candidate_ids():
        raise HTTPException(status_code=404, detail="unknown candidate")
    if body.decision not in curation_store.DECISIONS:
        raise HTTPException(status_code=422, detail="invalid decision")
    curation_store.set_decision(
        body.candidate_id, decision=body.decision, decided_by=actor_of(session)
    )
    return {"available": True, **curation_mod.compute_curation_overview(body.lang)}


@router.post("/observability/replay")
async def observability_replay(payload: ReplayRequest) -> dict[str, object]:
    """Replay a captured turn against a candidate model and diff the result.

    Every executed replay is journalled durably (replay_store) so the Replay &
    shadow page's "requêtes rejouées" / deviation figures reflect real runs.
    """
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    result = await replay_mod.replay(bundle, model=payload.model)
    try:
        from tessera.observability.replay_store import record_replay_run

        record_replay_run(
            result.bundle_id,
            # Pre-attribution bundles carry no agent; "none" is the shared
            # unattributed marker (same convention as the guard metrics).
            agent_id=bundle.agent_id or "none",
            model=result.candidate_model,
            score_delta=result.score_delta,
            similarity=result.similarity,
        )
    except Exception as exc:  # journalling must never break the replay itself
        sys.stderr.write(f"tessera.observability.replay_store: record failed: {exc}\n")
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


@router.post("/observability/why")
async def observability_why(payload: CoverageRequest) -> dict[str, object]:
    """Build a user-facing 'why this answer' explanation from provenance (#133)."""
    bundle = replay_mod.get_bundle(payload.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await why_answer_mod.build_explanation(answer=bundle.original_answer, chunks=chunks)
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


@router.post("/observability/redteam")
async def observability_redteam_run() -> dict[str, object]:
    """Run the adversarial corpus through the guard and record a snapshot."""
    snapshot = redteam_mod.run_redteam()
    return {
        "latest": asdict(snapshot),
        "snapshots": [asdict(s) for s in redteam_mod.recent_snapshots()],
    }


@router.post("/observability/client/alerts/read")
async def observability_client_alerts_read(body: _AlertReadBody) -> dict[str, object]:
    """Persist an alert's read state and return the fresh alerts payload."""
    return {
        "available": True,
        **client_space_mod.mark_alert_read(body.alert_id, read=body.read, lang=body.lang),
    }


@router.post("/observability/client/settings")
async def observability_client_settings_save(body: _SettingBody) -> dict[str, object]:
    """Persist one preference and return the full settings payload."""
    return {
        "available": True,
        **client_space_mod.update_setting(body.key, body.value, body.lang),
    }
