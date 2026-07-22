"""Observability routes — fleet surface."""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter
from pydantic import ValidationError

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.api.routes.observability._common import (
    _SYNTHESE_PERIODS,
    _agent_or_none,
    _scores_for,
)
from tessera.api.routes.observability.schemas_fleet import (
    AccessPayload,
    AccessUnavailable,
    AgentEvaluationsPayload,
    AgentEvaluationsUnavailable,
    ChromePayload,
    ChromeUnavailable,
    FleetPayload,
    FleetUnavailable,
    RbacMatrixPayload,
    RbacMatrixUnavailable,
    SandboxConfigPayload,
    SandboxConfigUnavailable,
)
from tessera.observability import (
    access as access_mod,
    agent_a_faire as agent_a_faire_mod,
    agent_configurations as agent_configurations_mod,
    agent_evaluations as agent_evaluations_mod,
    agent_garde_fous as agent_garde_fous_mod,
    agent_prompts as agent_prompts_mod,
    agent_synthese as agent_synthese_mod,
    chrome as chrome_mod,
    corpus_freshness as corpus_freshness_mod,
    fleet as fleet_mod,
    guard_activity as guard_activity_mod,
    knowledge as knowledge_mod,
    replay as replay_mod,
    roadmap as roadmap_mod,
    routing_intent as routing_intent_mod,
    users as users_mod,
)
from tessera.observability.spine.runtime import get_runtime_provider

router = APIRouter()


@router.get("/observability/fleet", response_model=FleetPayload | FleetUnavailable)
async def observability_fleet(lang: str = "fr") -> FleetPayload | FleetUnavailable:
    """Fleet rollup: per-agent observable KPIs + deduplicated org totals.

    ``lang`` localizes the per-agent release verdict label.

    The payload is **constructed**, never splatted. ``{"available": True, **compute()}`` was a
    promise the code did not keep: `compute_fleet` returns `None` for an agent with no eval run
    and no manifest — the honest-empty it owes — while the sample-derived response model declared
    those fields non-null. Nothing raised, so the ``except`` below never saw it; FastAPI validated
    the response, matched neither arm of the union, and served **500** on a virgin install.

    Three states, three answers, and they are not the same answer:

    * data (even all-zero) → ``available: true`` with a COMPLETE payload. An agent that has done
      nothing is a fact worth rendering, not an outage: the operator still gets the fleet.
    * the read failed (Postgres unreachable, …) → ``available: false``, logged as a failure.
    * the payload does not honour its own contract → ``available: false`` too, but logged as a
      **contract break**, because that is a bug in us, not an absence of data. A 500 would take
      the page down at the exact moment it is most needed; drowning it in the ordinary empty
      state would hide it forever. So it degrades, and it SAYS which of the two happened.
    """
    try:
        data = await fleet_mod.compute_fleet(lang)
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.fleet: failed: {exc}\n")
        return FleetUnavailable(available=False)
    try:
        return FleetPayload.model_validate({"available": True, **data})
    except ValidationError as exc:  # a shape we promised and did not deliver
        sys.stderr.write(f"tessera.observability.fleet: CONTRACT BREAK, payload rejected: {exc}\n")
        return FleetUnavailable(available=False)


@router.get("/observability/rbac-matrix", response_model=RbacMatrixPayload | RbacMatrixUnavailable)
async def observability_rbac_matrix(agent: str = "all") -> dict[str, object]:
    """RBAC role x agent matrix (real roles x real agents). Global, filterable.

    The enforced roles are currently org-wide; the matrix states that truthfully
    rather than fabricating per-agent grants. Degrades to ``available: false``.
    """
    from tessera.observability import rbac as rbac_mod

    try:
        return {"available": True, **rbac_mod.rbac_matrix(agent)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.rbac: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/release-control")
async def observability_release_control(agent: str = "all", lang: str = "fr") -> dict[str, object]:
    """Release Control (AGIR): per-agent release pipeline + eval-gate verdict.

    Global, filterable by agent (``?agent=all|<id>``) — distinct from the AGENT
    switcher. Each agent is a governed package; the verdict is the policy-correct
    gate over the agent's OWN run. Degrades to ``available: false``.
    """
    from tessera.observability import release_control as rc_mod

    try:
        return {"available": True, **rc_mod.compute_release_control(agent, lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.release_control: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-lifecycle")
async def observability_agent_lifecycle(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Governed lifecycle of an agent: state, gated release decision, S1 history.

    Closes the propose -> review -> approve -> release loop: the release decision
    is the agent's own two-level eval-gate verdict. Degrades to ``available:false``.
    """
    from tessera.observability import agent_lifecycle as lifecycle_mod

    try:
        return {"available": True, **lifecycle_mod.compute_agent_lifecycle(agent_id, lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.agent_lifecycle: failed: {exc}\n")
        return {"available": False}


@router.get(
    "/observability/agent-evaluations",
    response_model=AgentEvaluationsPayload | AgentEvaluationsUnavailable,
)
async def observability_agent_evaluations(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Agent Evaluations ("Evaluations") dashboard (reference image 29).

    Inner tab strip, active-snapshot bar, KPI strip, filterable evaluations
    table, watchlist, quick actions, global-score trend and a per-evaluation
    detail panel. Scored from the agent's OWN run over its OWN set (real
    llama3.2:3b), with the two-level gate verdict, per-agent judged metrics and
    the ER-01 run-history rail; degrades to ``available: false``.

    The ``agent_id`` query param scopes the page to one agent; it defaults to the
    single agent.
    """
    try:
        return {
            "available": True,
            **agent_evaluations_mod.compute_agent_evaluations(agent_id, lang),
        }
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_evaluations: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-prompts")
async def observability_agent_prompts(
    lang: str = "fr", agent_id: str = DEFAULT_AGENT_ID
) -> dict[str, object]:
    """Agent Prompts ("Prompts") dashboard (reference image 28).

    Backed by the live YAML source of truth
    (``src/tessera/agent/prompts/{fr,de,en}.yaml``): the prompt inventory,
    categories, languages, template variables, lengths and the per-prompt text
    in the detail panel are all real. Read-only (prompts live in Git). Display
    labels are localized via ``lang`` (fr/de/en). ``agent_id`` scopes the
    in-page navigation links. Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **(await agent_prompts_mod.build_agent_prompts(lang, agent_id))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_prompts: failed: {exc}\n")
        return {"available": False}


@router.get(
    "/observability/sandbox-config", response_model=SandboxConfigPayload | SandboxConfigUnavailable
)
async def observability_sandbox_config(lang: str = "fr") -> dict[str, object]:
    """Defaults for the Console sandbox playground (model/prompt/guardrails).

    Returns the *live* system prompt for ``lang`` (the YAML bundle the agent
    actually runs) and the toggleable guard categories with their real pattern
    counts (the runtime guard policy). The console prefills its prompt editor and
    guard switches from these — never from fabricated values. Read-only;
    overrides are applied per-turn at chat time, never persisted here.
    """
    from tessera.guard.decisions import load_policy
    from tessera.settings import LanguageCode, get_settings

    langs = {"fr": LanguageCode.FR, "de": LanguageCode.DE, "en": LanguageCode.EN}
    try:
        language = langs.get(lang, LanguageCode.FR)
        # ADR 0017 §1: the live system prompt + policy-rule count are agent-runtime
        # facts, read through the spine port — never by importing the runtime here.
        defaults = get_runtime_provider().sandbox_defaults(language)
        policy = load_policy(get_settings().guard.policy_path)
        return {
            "available": True,
            "language": language.value,
            "system_prompt": defaults.system_prompt,
            "guard_categories": [
                {
                    "key": "prompt_injection",
                    "label": "Prompt Injection",
                    "count": len(policy.prompt_injection_deny),
                    "detail": "Bloque l'entrée utilisateur qui matche un motif d'injection.",
                },
                {
                    "key": "pii",
                    "label": "Masquage PII",
                    "count": len(policy.pii_patterns),
                    "detail": "Masque les données personnelles dans la trace d'audit des outils.",
                },
                {
                    "key": "policy",
                    "label": "Refus policy",
                    "count": defaults.policy_rule_count,
                    "detail": (
                        "Court-circuits déterministes : conseil hors-scope, procédures "
                        "confidentielles, évasion anti-fraude, promesses interdites."
                    ),
                },
                {
                    "key": "tools",
                    "label": "Privilèges outils",
                    "count": len(policy.tools),
                    "detail": "Allowlist + confirmations + validation d'arguments par outil.",
                },
            ],
        }
    except Exception as exc:  # never break the console
        sys.stderr.write(f"tessera.observability.sandbox_config: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-garde-fous")
async def observability_agent_garde_fous(lang: str = "fr") -> dict[str, object]:
    """Agent Guardrails ("Garde-fous") dashboard (reference image 27).

    Backed by the live guard layer: rules are derived from ``policy.yaml`` and
    the firing stats (decisions, blocks, last fired, 24h deltas) plus audit-chain
    integrity are read from the tamper-evident audit log. Per-rule enable/disable
    state is durable. Display labels are localized via ``lang`` (fr/de/en).
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **(await agent_garde_fous_mod.build_agent_garde_fous(lang))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_garde_fous: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/guard-activity")
async def observability_guard_activity() -> dict[str, object]:
    """Guard-activity aggregate for the public launcher band (ADR 0009).

    Two counters, each from its own witness: user turns recorded today in the
    durable transcript (ADR 0040 — every persisted user turn entered through the
    input guard; test turns included, the scope the band's popover states) and
    input-guard denials recorded today in the tamper-evident audit trail. Only
    aggregates a public visitor may see — never per-case detail. Degrades to
    ``available: false`` on failure.
    """
    try:
        return {"available": True, **(await guard_activity_mod.build_guard_activity())}
    except Exception as exc:  # never break the launcher
        sys.stderr.write(f"tessera.observability.guard_activity: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-a-faire")
async def observability_agent_a_faire(lang: str = "fr") -> dict[str, object]:
    """Agent "A faire" personal action queue (reference image 23).

    Backed by the real operator backlog (failed eval cases with durable
    status/assignee): temporal rail + event timeline, KPI strip, saved-views
    filter rail, task table, per-item detail band and the right column.
    ``lang`` localizes the chrome (fr / de / en). Degrades to
    ``available: false`` on failure.
    """
    try:
        return {"available": True, **agent_a_faire_mod.compute_agent_a_faire(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_a_faire: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-connaissances")
async def observability_agent_connaissances(lang: str = "fr") -> dict[str, object]:
    """Agent Knowledge ("Connaissances") dashboard (reference image 01).

    Backed by the live pgvector ``documents`` table: the source inventory,
    chunk counts, languages and freshness are real. Per-agent attach/active
    state is durable. Display labels are localized via ``lang`` (fr/de/en).
    Degrades to ``available: false`` if the store is down.
    """
    try:
        return {"available": True, **(await knowledge_mod.build_connaissances(lang))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_connaissances: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-configurations")
async def observability_agent_configurations(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Agent Configurations dashboard (reference image 26).

    Composes the active settings, guard policy, prompt bundles, tools and
    corpus-backed sources into the operator configuration form. Degrades to
    ``available: false`` so the dashboard keeps rendering if a local source is
    temporarily unreadable. ``agent_id`` scopes the in-page navigation links;
    ``lang`` localizes the chrome and the editable option values.
    """
    try:
        return {
            "available": True,
            **(await agent_configurations_mod.compute_agent_configurations(agent_id, lang)),
        }
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_configurations: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-synthese")
async def observability_agent_synthese(
    period: str = "d7", agent_id: str = DEFAULT_AGENT_ID, at: str | None = None
) -> dict[str, object]:
    """Agent overview ("Synthese de l'agent") dashboard (reference image 25).

    Operational (events only): KPI strip, agent context/profile and capabilities,
    routing-motive distribution, detailed operational performance, recent
    conversations, the AT-01 activity feed, active prompts, operational alerts and
    quick access. Sourced end to end from the transcript + S1 journal + registry +
    pgvector; degrades to ``available: false``.

    The ``period`` query param (``h24``/``d7``/``d30``) restricts the
    transcript-derived figures to that trailing window; unknown values mean the
    whole history. The ``agent_id`` query param scopes the slice to one agent
    (per-turn attribution); it defaults to the single agent. ``at`` (ISO instant)
    is the AT-01 "Voir à date" reading: transcript/CSAT/journal figures are read
    over the window ending at T (registry identity, knowledge counts and the
    chain badge stay live — the rail says so).
    """
    period_days = _SYNTHESE_PERIODS.get(period)
    try:
        payload = await agent_synthese_mod.compute_agent_synthese(agent_id, period_days, at)
        return {"available": True, **payload}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_synthese: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/chrome", response_model=ChromePayload | ChromeUnavailable)
async def observability_chrome(lang: str = "fr") -> dict[str, object]:
    """Sidebar badges and bell notifications — every number a count, every count a page.

    Composes the reads the destination pages already perform; it opens no store of its own.
    A source that cannot be read contributes nothing rather than a zero, so the chrome
    under-reports before it ever misreports. Degrades to ``available: false``.
    """
    try:
        return {"available": True, **chrome_mod.compute_chrome(lang)}
    except Exception as exc:  # the chrome must never break the page it decorates
        sys.stderr.write(f"tessera.observability.chrome: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/access", response_model=AccessPayload | AccessUnavailable)
async def observability_access(lang: str = "fr") -> dict[str, object]:
    """Roles & access overview (page #18).

    Composes the access posture, the role table, the selected-role detail and
    the governance panels. Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **access_mod.compute_access_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.access: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/roadmap")
async def observability_roadmap(at: str | None = None, agent: str = "all") -> dict[str, object]:
    """Mine telemetry signals into a ranked product backlog (#124), live or as of T.

    Score- and bundle-derived inputs honour T; corpus freshness is a property of
    the ingested data today, so it stays live. ``agent`` scopes the score/bundle
    inputs to one agent (``all`` = org view); corpus freshness stays org.
    """
    from importlib import resources
    from pathlib import Path

    ag = _agent_or_none(agent)
    low_threshold = 0.80
    n_turns = 0
    n_low = 0
    languages_low: dict[str, int] = {}
    for score in _scores_for(at, ag):
        if score.get("metric") != "faithfulness":
            continue
        n_turns += 1
        if float(score["score"]) < low_threshold:  # type: ignore[arg-type]
            n_low += 1
            lang = score.get("language")
            key = lang if isinstance(lang, str) else "unknown"
            languages_low[key] = languages_low.get(key, 0) + 1

    questions = [b.question for b in replay_mod.recent_bundles(at, ag)]
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


@router.get("/observability/release-status")
async def observability_release_status() -> dict[str, object]:
    """Current release + real open quality regressions (Vue d'ensemble rail).

    Releases are parsed from ``CHANGELOG.md``; regressions are derived from the
    eval report archive (pass-rate drops between a model's two most recent
    full-catalogue runs). The release's status is a fact — ``n_regressions``
    open — not an invented flag.
    """
    from tessera.observability.eval.releases import release_status

    return asdict(release_status())


@router.get("/observability/users")
async def observability_users(lang: str = "fr") -> dict[str, object]:
    """Users overview from the real seeded operator accounts (admin/utilisateurs)."""
    try:
        return {"available": True, **users_mod.compute_users(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.users: failed: {exc}\n")
        return {"available": False}
