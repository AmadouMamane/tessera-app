"""Observability routes — the cockpit's read surface plus its operator mutations.

Was a single 3 219-line, 152-route module (audit 2026-07-10, `god-router`): public reads,
PII reads and 26 privileged mutations interleaved in one flat router, with nowhere to attach
a single ``dependencies=``. That flatness was the root cause of the authorization drift.

Three planes now, each a router, each its own seam for a guard:

* ``mutations`` — the 26 operator POSTs, behind ``require_operator`` (closed 2026-07-11).
* ``pii`` — the SUBJECT-SCOPED reads, behind ``require_subject_reader`` (closed by this
  change, audit 2026-07-12 P1 F-4). Transcripts, session detail, replay bundles, memory
  inventory, erasure footprints: personal data, and until now served to anyone who asked.
* everything else — the public aggregate surface ADR 0009 declares: scores, rates, levels,
  badges, signals. It carries no subject and it stays open.

The split that mattered was never read-vs-write. It is *"can this response identify
someone?"* — and the 2026-07-10 split, which grouped reads by **page**, could not express it:
``console`` held the transcript next to the span-propagation probe. Route paths are unchanged.
"""

from __future__ import annotations

from fastapi import APIRouter

from tessera.api.routes.observability import (
    business,
    client,
    compliance,
    console,
    evals,
    feedback,
    fleet,
    memory,
    mutations,
    pii,
    safety,
    signals,
)

# Load-bearing re-exports: tests reach these private helpers through the package root, as
# they did when it was one module. Kept so the split stays behaviour-preserving all the way
# out to the test surface.
from tessera.api.routes.observability._common import (
    _agent_or_none,
    _data_availability_start,
    _load_failure_items,
)
from tessera.api.routes.observability.business import (
    observability_automations,
    observability_business_capabilities,
    observability_business_events,
    observability_business_runs,
    observability_curation,
    observability_etat_a_date,
    observability_funnel,
    observability_improvement,
    observability_inbox,
    observability_journey,
    observability_sessions,
)
from tessera.api.routes.observability.client import (
    observability_client_alerts,
    observability_client_documents,
    observability_client_requests,
    observability_client_settings,
)
from tessera.api.routes.observability.compliance import (
    observability_ai_act,
    observability_catalogue_consumers,
    observability_citation_links,
    observability_citations,
    observability_compliance,
    observability_connectors,
    observability_corpus_freshness,
    observability_corpus_scan,
    observability_disclosure,
    observability_governance,
    observability_integrations,
    observability_locale_format,
    observability_localization,
    observability_parameters,
    observability_proofs,
    observability_sources,
    observability_system_profile,
)
from tessera.api.routes.observability.console import (
    observability_agent_console,
    observability_assistant,
    observability_graph_topology,
    observability_replay_shadow,
    observability_span_propagation,
    observability_tail_sampling,
    observability_timeline,
    observability_traces_obs,
)
from tessera.api.routes.observability.evals import (
    observability_calibration,
    observability_contradictions,
    observability_eval_datasets,
    observability_failed_cases,
    observability_failed_runs,
    observability_failure_clusters,
    observability_failure_predictor,
    observability_judge_consensus,
    observability_judge_drift,
    observability_model_catalogue,
    observability_model_comparison,
    observability_regression_risk,
    observability_reproducibility,
    observability_runs,
    observability_sft_dataset,
)
from tessera.api.routes.observability.fleet import (
    observability_access,
    observability_agent_a_faire,
    observability_agent_configurations,
    observability_agent_connaissances,
    observability_agent_evaluations,
    observability_agent_garde_fous,
    observability_agent_lifecycle,
    observability_agent_prompts,
    observability_agent_synthese,
    observability_chrome,
    observability_fleet,
    observability_rbac_matrix,
    observability_release_control,
    observability_release_status,
    observability_roadmap,
    observability_sandbox_config,
    observability_users,
)
from tessera.api.routes.observability.memory import (
    observability_erasure_coverage,
    observability_memory,
)
from tessera.api.routes.observability.mutations import (
    observability_ablation,
    observability_agent_a_faire_mutate,
    observability_agent_configurations_save,
    observability_agent_connaissances_mutate,
    observability_agent_console_feedback_save,
    observability_agent_garde_fous_mutate,
    observability_agents_propose,
    observability_agents_release,
    observability_automations_evaluate,
    observability_automations_rule_state,
    observability_client_alerts_read,
    observability_client_settings_save,
    observability_consistency,
    observability_coverage,
    observability_crosslingual,
    observability_curation_decision,
    observability_ensemble,
    observability_etat_a_date_snapshot,
    observability_inbox_mutate,
    observability_redteam_run,
    observability_replay,
    observability_reranking,
    observability_robustness,
    observability_shadow,
    observability_sycophancy,
    observability_why,
)
from tessera.api.routes.observability.pii import (
    observability_agent_console_feedback,
    observability_agent_historique,
    observability_context_overflow,
    observability_conversation_messages,
    observability_conversations,
    observability_erasure_preview,
    observability_handoffs,
    observability_memory_inventory,
    observability_provenance,
    observability_replays,
    observability_session_detail,
    observability_trace_snapshot,
    observability_trajectory,
)
from tessera.api.routes.observability.safety import (
    observability_cross_tenant,
    observability_embedding_inversion,
    observability_embedding_skew,
    observability_firewall_efficacy,
    observability_guard_explain,
    observability_guard_retraction,
    observability_guardrail_catalogue,
    observability_incidents,
    observability_least_privilege,
    observability_pii_leak,
    observability_playbooks,
    observability_policies,
    observability_redteam,
    observability_refusal,
    observability_siem,
    observability_steganography,
    observability_tool_loops,
    observability_tool_validity,
    observability_toxicity,
)
from tessera.api.routes.observability.signals import (
    observability_anomalies,
    observability_availability,
    observability_conformance,
    observability_control_signals,
    observability_cost,
    observability_data_range,
    observability_intent,
    observability_metric_pairs,
    observability_obs_cost,
    observability_quality_nets,
    observability_reliability,
    observability_routing,
    observability_score_series,
    observability_scores,
    observability_signal_catalogue,
    observability_signal_status_trend,
    observability_slo,
    observability_snapshot,
    observability_trend,
    observability_what_changed,
)

router = APIRouter()

# Reads: public cockpit surface.
router.include_router(business.router)
router.include_router(client.router)
router.include_router(compliance.router)
router.include_router(console.router)
router.include_router(evals.router)
router.include_router(fleet.router)
router.include_router(memory.router)
router.include_router(safety.router)
router.include_router(signals.router)

# Subject-scoped reads: transcripts, session detail, replay bundles, memory inventory,
# erasure footprints. Personal data (GDPR), NOT the public aggregate surface — one router so
# the read guard, like the mutation guard, has a single seam (audit 2026-07-12, P1 F-4).
router.include_router(pii.router)

# Mutations: the 26 operator POSTs. Mounted as one router so a guard has a single seam.
router.include_router(mutations.router)

# Customer-plane write: the 👍/👎 on an assistant reply (ADR 0041). NOT an operator mutation —
# bearer-less, self-authenticating on the signed resume capability (like /chat), so it stays
# off the ``mutations`` router and its ``require_operator`` guard.
router.include_router(feedback.router)
