"""Response models for the fleet read domain — DERIVED from the real output, never guessed.

Audit 2026-07-10, **P1.4 `untyped-api`**: 10 `response_model` on ~174 routes. The contract the
cockpit depends on is nowhere declared, so the front re-implements it in hand-written zod and the
two drift silently. This module is the pilot: the fleet sub-router's contract, made explicit.

**Every model here was derived from 123 live responses**, sampled across each route's real
parameter space (3 languages x 6 agents x periods) — never from reading the code and guessing.
A `response_model` that does not match the real output does not fail loudly; FastAPI **silently
strips** the fields the model omits. So the shape is observed, and a test replays all 123 samples
through the models and asserts the serialization is byte-identical.

## The discriminated union, and why it is the whole point

Sixteen of the eighteen fleet handlers are written like this:

    try:
        return {"available": True, **compute(lang)}
    except Exception:
        return {"available": False}          # honest-empty: never break the page

So **every route has two shapes**, and a naive `response_model` has to make every payload field
optional — otherwise the degraded response becomes a 500 and "never break the page" turns into
"always break the page". But all-optional guarantees nothing, which is precisely the state the
front is in today: 13 of its 14 hand-written schemas accept `{"available": false}` by having
made everything optional, so they cannot catch a backend that drops `agents` entirely.

The union says what is actually true:

    Payload{available: Literal[True], ...every field REQUIRED}
      | Unavailable{available: Literal[False]}

`available: True` now *guarantees* the payload. The degraded shape is still accepted, unchanged,
byte for byte. And the generated zod is a **discriminated union**, so the front gets the same
guarantee for free instead of re-deriving it by hand.

## `available` means two different things, under the same key

This is the finding that makes the pilot worth having, and it is invisible from the field name.

* **The exception degrade** — the object *collapses* to `{"available": false}` and nothing else.
  Observed at `agent-evaluations.judge` (9 sightings with its seven fields, 3 as `{available:
  false}` alone). This is a **union**.
* **A business fact** — `available: false` arrives **with its full payload**. At
  `fleet.agents[].release` the object has **20 keys whether available is true or false**: false
  means *"no eval has been run for this agent"* (`verdict_label: "Éval non exécutée"`), which is
  a statement about the world, not a failure. Same at `north_star.trend`
  (`direction: "insufficient_data"`, with its points). This is **`available: bool`**, not a union.

The first draft of these models made every `available` a union — the obvious reading of the
name — and FastAPI therefore **silently dropped 20 fields on every agent** of the flagship
route. Nothing raised. The round-trip test is what caught it, which is the entire argument for
deriving models from observed output rather than from a plausible reading of the code.

The rule the generator now applies: **a union only where the observed `false` shape collapses.**

## Honest-empty is preserved, not typed away

A field never observed with a value is `None`, not `str`. Six of them exist in this domain
(`fleet.agents[].north_star.trend.delta_pct`, the five `badge` fields in `agent-configurations`).
Making them required would fabricate a value the product deliberately does not have.

No model carries `extra="forbid"`. The shapes are *observed*, not proven exhaustive; forbidding
an unobserved field would turn a new backend field into a 500.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SandboxConfigGuardCategoriesItem(BaseModel):
    """sandbox-config.guard_categories.item."""

    key: str
    label: str
    count: int
    detail: str


class SandboxConfigUnavailable(BaseModel):
    """Honest-empty: the compute raised; the page must not break."""

    available: Literal[False]


class SandboxConfigPayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union."""

    available: Literal[True]
    language: str
    system_prompt: str
    guard_categories: list[SandboxConfigGuardCategoriesItem]


class ChromeBadgesATraiter(BaseModel):
    """chrome.badges.a_traiter."""

    count: int
    tone: str


class ChromeBadgesAFaire(BaseModel):
    """chrome.badges.a_faire."""

    count: int
    tone: str


class ChromeBadgesIncidents(BaseModel):
    """chrome.badges.incidents."""

    count: int
    tone: str


class ChromeBadgesCuration(BaseModel):
    """chrome.badges.curation."""

    count: int
    tone: str


class ChromeBadgesSignalCatalog(BaseModel):
    """chrome.badges.signal_catalog."""

    count: int
    tone: str


class ChromeBadges(BaseModel):
    """chrome.badges."""

    a_traiter: ChromeBadgesATraiter
    a_faire: ChromeBadgesAFaire
    incidents: ChromeBadgesIncidents
    curation: ChromeBadgesCuration
    signal_catalog: ChromeBadgesSignalCatalog


class ChromeNotificationsItemsItem(BaseModel):
    """chrome.notifications.items.item."""

    id: str
    label: str
    href: str
    tone: str


class ChromeNotifications(BaseModel):
    """chrome.notifications."""

    count: int
    items: list[ChromeNotificationsItemsItem]


class ChromeUnavailable(BaseModel):
    """Honest-empty: the compute raised; the page must not break."""

    available: Literal[False]


class ChromePayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union."""

    available: Literal[True]
    badges: ChromeBadges
    notifications: ChromeNotifications


class RbacMatrixRolesItemCellsItem(BaseModel):
    """rbac-matrix.roles.item.cells.item."""

    agent_id: str
    name: str
    granted: bool
    scope: str


class RbacMatrixRolesItem(BaseModel):
    """rbac-matrix.roles.item."""

    role: str
    label: str
    caps: list[str]
    scope: str
    agent_count: int
    cells: list[RbacMatrixRolesItemCellsItem]


class RbacMatrixAgentsItem(BaseModel):
    """rbac-matrix.agents.item."""

    id: str
    name: str


class RbacMatrixUnavailable(BaseModel):
    """Honest-empty: the compute raised; the page must not break."""

    available: Literal[False]


class RbacMatrixPayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union."""

    available: Literal[True]
    roles: list[RbacMatrixRolesItem]
    agents: list[RbacMatrixAgentsItem]
    scope_model: str


class FleetAgentsItemRelease(BaseModel):
    """fleet.agents.item.release."""

    agent_id: str
    available: bool
    passed: bool
    verdict_label: str
    verdict_tone: str
    candidate_version: str
    eval_set: str
    executions: int
    socle_ok: bool
    blocking_socle: int
    blocking_t1: int
    waived_active: int
    run_at: str
    catalogue_version: str
    current_catalogue_version: str
    verdict_stale: bool
    summary_passed: int
    summary_total: int
    socle_passed: int
    socle_total: int
    # ADR 0021 Rule 1 on this column too: whether the measured null floor cleared the run, and
    # the one line naming what it holds against it when it did not (null when it clears).
    floor_ok: bool
    floor_block: str | None


class FleetAgentsItemNorthStarTrendPointsItem(BaseModel):
    """fleet.agents.item.north_star.trend.points.item."""

    bucket: str
    value_pct: float | None
    status: str


class FleetAgentsItemNorthStarTrend(BaseModel):
    """fleet.agents.item.north_star.trend."""

    available: bool
    direction: str
    delta_pct: None = None
    points: list[FleetAgentsItemNorthStarTrendPointsItem]


class FleetAgentsItemNorthStarEvidence(BaseModel):
    """fleet.agents.item.north_star.evidence."""

    observed_runs: int
    checks: int
    # The same disease, one level deeper — and ONLY the live virgin install found it. The
    # producer says so in its own docstring: "A metric no run ever produced yields zeros and
    # ``None`` — the genuine zero-data case, which keeps its dash." The samples this model was
    # generated from all had a run; none of them could show that None was allowed.
    last_checked_at: str | None


class FleetAgentsItemNorthStar(BaseModel):
    """fleet.agents.item.north_star."""

    agent_id: str | None = None
    key: str | None = None
    source: str | None = None
    level: str | None = None
    unit: str | None = None
    aggregation: str | None = None
    dimensions: list[str] | None = None
    engagement: str | None = None
    north_star: bool | None = None
    scorer: str | None = None
    value: float | None = None
    value_pct: float | None = None
    status: str | None = None
    reason: str | None = None
    trend: FleetAgentsItemNorthStarTrend | None = None
    evidence: FleetAgentsItemNorthStarEvidence | None = None


class FleetAgentsItem(BaseModel):
    """fleet.agents.item."""

    id: str
    name: str
    owner: str
    audience: str
    description: str
    tags: list[str]
    conversations: int
    turns: int
    messages: int
    escalation_rate: float
    latency_ms: float | None
    handoffs_in: int
    handoffs_out: int
    health: str
    # These three are NULLABLE, and the code always knew it: `release` is None until an eval has
    # run, `level`/`level_declared` are None until the agent has an AgentSpec manifest — the
    # honest-empty the fleet module documents in so many words ("None … → honest-empty, not L0").
    #
    # They were generated as required and non-null from 31 live samples in which every agent
    # happened to have both. A sample shows what WAS there; it can never show what is ALLOWED to
    # be absent. The result: a virgin install — no eval, no manifest — produced a payload that
    # satisfied neither arm of the union, and the fleet route answered 500. No default is given
    # (`| None` alone, never `= None`): the key must still be PRESENT, because `available: True`
    # promising a complete payload is the entire point of this union.
    release: FleetAgentsItemRelease | None
    level: str | None
    level_declared: str | None
    level_evidence: str
    observable: bool
    testable: bool
    north_star: FleetAgentsItemNorthStar | None
    pending_business_items: int


class FleetOrg(BaseModel):
    """fleet.org."""

    conversations: int
    turns: int


class FleetUnavailable(BaseModel):
    """Honest-empty: the compute raised; the page must not break."""

    available: Literal[False]


class FleetPayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union."""

    available: Literal[True]
    agents: list[FleetAgentsItem]
    org: FleetOrg
    naive_sum_conversations: int
    shared_conversations: int
    dedup_saved: int
    # Completed handoffs only: a raw S1 label earns this business meaning when a prior source
    # turn and the exact persisted target turn corroborate it. The immutable raw entries remain
    # in the audit ledger; legacy initial routes are not promoted into fleet transfer counts.
    handoff_events: int
    handoff_conversations: int
    handoff_conversations_seen_shared: int


class AccessKpisItem(BaseModel):
    """access.kpis.item."""

    key: str
    value: str
    sub: str
    series: list[int]


class AccessRolesItemMembersItem(BaseModel):
    """access.roles.item.members.item."""

    name: str
    team: str
    status: str


class AccessRolesItemPermissionDistItem(BaseModel):
    """access.roles.item.permission_dist.item."""

    key: str
    count: int
    pct: int
    color: str


class AccessRolesItemAccessScopeItem(BaseModel):
    """access.roles.item.access_scope.item."""

    key: str
    count: int
    pct: int
    color: str


class AccessRolesItem(BaseModel):
    """access.roles.item."""

    id: str
    name: str
    type: str
    description: str
    users: int
    groups: int
    permissions: int
    scope: str
    environment: str
    modified: str
    status: str
    caps: list[str]
    members: list[AccessRolesItemMembersItem]
    permission_dist: list[AccessRolesItemPermissionDistItem]
    access_scope: list[AccessRolesItemAccessScopeItem]
    owner: str
    created: str


class AccessSelectedMembersItem(BaseModel):
    """access.selected.members.item."""

    name: str
    team: str
    status: str


class AccessSelectedPermissionDistItem(BaseModel):
    """access.selected.permission_dist.item."""

    key: str
    count: int
    pct: int
    color: str


class AccessSelectedAccessScopeItem(BaseModel):
    """access.selected.access_scope.item."""

    key: str
    count: int
    pct: int
    color: str


class AccessSelected(BaseModel):
    """access.selected."""

    id: str
    name: str
    type: str
    description: str
    users: int
    groups: int
    permissions: int
    scope: str
    environment: str
    modified: str
    status: str
    caps: list[str]
    members: list[AccessSelectedMembersItem]
    permission_dist: list[AccessSelectedPermissionDistItem]
    access_scope: list[AccessSelectedAccessScopeItem]
    owner: str
    created: str


class AccessTopRolesItem(BaseModel):
    """access.top_roles.item."""

    name: str
    value: int
    label: str


class AccessAccessByResourceItem(BaseModel):
    """access.access_by_resource.item."""

    key: str
    count: int
    pct: int
    color: str


class AccessFooter(BaseModel):
    """access.footer."""

    total: int
    source: str


class AccessUnavailable(BaseModel):
    """Honest-empty: the compute raised; the page must not break."""

    available: Literal[False]


class AccessPayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union."""

    available: Literal[True]
    generated_at: str
    total_roles: int
    page_size: int
    kpis: list[AccessKpisItem]
    roles: list[AccessRolesItem]
    selected: AccessSelected
    top_roles: list[AccessTopRolesItem]
    access_by_resource: list[AccessAccessByResourceItem]
    pending_requests: list[None]
    sod_violations: list[None]
    inactive_accounts: list[None]
    footer: AccessFooter


class AgentEvaluationsActions(BaseModel):
    """agent-evaluations.actions."""

    asof: str
    create: str


class AgentEvaluationsMetaRbacItem(BaseModel):
    """agent-evaluations.meta.rbac.item."""

    role: str
    access: str


class AgentEvaluationsMeta(BaseModel):
    """agent-evaluations.meta."""

    model: str
    catalogue_version: str
    languages: str
    score10: str
    escalations: int
    tool_invocations: int
    rbac: list[AgentEvaluationsMetaRbacItem]


class AgentEvaluationsDetailLabels(BaseModel):
    """agent-evaluations.detail_labels."""

    eyebrow: str
    tabs: list[str]
    results_title: str
    results_cta: str
    rbac_title: str
    config_title: str
    info_title: str
    activity_title: str


class AgentEvaluationsSnapshot(BaseModel):
    """agent-evaluations.snapshot."""

    tag: str
    label: str
    updated_label: str
    updated: str
    updated_rel: str
    version_label: str
    version: str
    version_status: str
    evalset_label: str
    evalset: str
    coverage_label: str
    coverage: int
    coverage_tone: str
    asof: str
    compare: str


class AgentEvaluationsKpisItem(BaseModel):
    """agent-evaluations.kpis.item."""

    key: str
    label: str
    value: str
    scale: str
    note: str
    note_tone: str
    delta: str
    delta_tone: str
    gauge: int | None


class AgentEvaluationsFiltersOptionsTypeItem(BaseModel):
    """agent-evaluations.filters.options.type.item."""

    key: str
    label: str


class AgentEvaluationsFiltersOptionsQualityItem(BaseModel):
    """agent-evaluations.filters.options.quality.item."""

    key: str
    label: str


class AgentEvaluationsFiltersOptionsHallucItem(BaseModel):
    """agent-evaluations.filters.options.halluc.item."""

    key: str
    label: str


class AgentEvaluationsFiltersOptions(BaseModel):
    """agent-evaluations.filters.options."""

    type: list[AgentEvaluationsFiltersOptionsTypeItem]
    quality: list[AgentEvaluationsFiltersOptionsQualityItem]
    halluc: list[AgentEvaluationsFiltersOptionsHallucItem]


class AgentEvaluationsFilters(BaseModel):
    """agent-evaluations.filters."""

    search: str
    options: AgentEvaluationsFiltersOptions


class AgentEvaluationsTableRowsItem(BaseModel):
    """agent-evaluations.table.rows.item."""

    name: str
    type: str
    type_tone: str
    status: str
    status_tone: str
    version: str
    score: str
    score_num: float
    success: str
    halluc: str
    last_run: str
    owner: str
    tests: str
    category_key: str
    quality_key: str
    quality_label: str
    is_fact: bool
    passed: int
    total: int
    failed: int
    pass_rate: float


class AgentEvaluationsTable(BaseModel):
    """agent-evaluations.table."""

    columns: list[str]
    rows: list[AgentEvaluationsTableRowsItem]
    total: int


class AgentEvaluationsWatchItemsItem(BaseModel):
    """agent-evaluations.watch.items.item."""

    title: str
    detail: str
    tone: str


class AgentEvaluationsWatch(BaseModel):
    """agent-evaluations.watch."""

    title: str
    cta: str
    cta_href: str
    items: list[AgentEvaluationsWatchItemsItem]


class AgentEvaluationsQuickItemsItem(BaseModel):
    """agent-evaluations.quick.items.item."""

    key: str
    label: str


class AgentEvaluationsQuick(BaseModel):
    """agent-evaluations.quick."""

    title: str
    items: list[AgentEvaluationsQuickItemsItem]


class AgentEvaluationsTrend(BaseModel):
    """agent-evaluations.trend."""

    title: str
    value: str
    scale: str
    legend: str
    series: list[int]


class AgentEvaluationsGateBreakdown(BaseModel):
    """agent-evaluations.gate.breakdown."""

    critical_blocking: int
    tier0_non_derogeable: int
    waived: int


class AgentEvaluationsGateGrains(BaseModel):
    """agent-evaluations.gate.grains."""

    executions: int
    distinct_cases: int
    socle_cases: int


class AgentEvaluationsGateCounts(BaseModel):
    """agent-evaluations.gate.counts."""

    passed: int
    failed: int


class AgentEvaluationsGateSocle(BaseModel):
    """agent-evaluations.gate.socle."""

    ok: bool
    passed: int
    total: int


class AgentEvaluationsGateDomain(BaseModel):
    """agent-evaluations.gate.domain — a MEASUREMENT, not a gate (ADR 0021).

    `ok` and `min` are gone with the domain bar they expressed. `gating` is `False` and
    says it on the wire: a consumer that reads this block cannot mistake the rate for a
    verdict, and cannot resurrect a threshold by inferring one from a missing key.
    """

    passed: int
    total: int
    rate: float
    gating: Literal[False]


class AgentEvaluationsGateBreakdownGrain(BaseModel):
    """agent-evaluations.gate.breakdown_grain."""

    blocking_socle: int
    blocking_t1: int
    waived_active: int
    non_executed_critical: int


class AgentEvaluationsGateTiersItem(BaseModel):
    """agent-evaluations.gate.tiers.item."""

    tier: str
    label: str
    count: int
    tone: str
    waivable: bool


class AgentEvaluationsGateVenn(BaseModel):
    """agent-evaluations.gate.venn."""

    universe: int
    critiques: int
    socle: int
    t1: int
    domaine: int
    deroges: int
    reconciles: bool
    reconcile_total: int


class AgentEvaluationsGateSocleByCategoryItem(BaseModel):
    """agent-evaluations.gate.socle_by_category.item."""

    category: str
    label: str
    ok: bool
    passed: int
    total: int


class AgentEvaluationsGateCriticalCasesRowsItem(BaseModel):
    """agent-evaluations.gate.critical_cases.rows.item."""

    case_id: str
    title: str
    tier: str
    tier_label: str
    tier_tone: str
    language: str
    status_key: str
    status_label: str
    status_tone: str
    socle: bool


class AgentEvaluationsGateCriticalCases(BaseModel):
    """agent-evaluations.gate.critical_cases."""

    title: str
    columns: list[str]
    rows: list[AgentEvaluationsGateCriticalCasesRowsItem]
    total: int


class AgentEvaluationsGateWaivers(BaseModel):
    """agent-evaluations.gate.waivers."""

    title: str
    subtitle: str
    active: int
    total: int
    chain_verified: bool
    items: list[None]


class AgentEvaluationsGateContributionUnavailable(BaseModel):
    """Honest-empty: no set bound, no committed floor, NO MODEL SPOKE, or a STALE floor.

    A run whose every backend was unreachable still writes its configured `model` and still
    passes 70% of the catalogue on the deterministic layer alone — reporting `contribution:
    0, regressions: 0` for it would render as a clean bill of health for a model that never
    answered. Generated tokens are the witness, and when they are absent the block degrades.
    That is why this union exists rather than a zeroed payload.

    The same applies to a floor that no longer covers the run's cases: the model was not
    graded, and "0/0" would read as a measured zero. `refusal` carries WHY — an honest-empty
    that cannot say why it is empty sends the reader hunting for a bug in the page instead
    of at the floor that expired.
    """

    available: Literal[False]
    #: Why nothing could be graded. Optional only because the field is new; the backend
    #: always sets it. It MUST be declared here or the response model strips it in silence —
    #: a wrong `response_model` does not 500, it quietly deletes the field.
    refusal: str | None = None


class AgentEvaluationsGateContributionPayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union.

    What replaces the removed domain bar (ADR 0021 §3a): the model's delta over the null
    control restricted to THIS set's cases. `gated` is `False` — rule 2 is measured here,
    never gated, because a per-set bar would be an invented number, which is exactly what
    the ADR deleted. `regression_candidates` are candidates, not confirmed regressions: a
    break counts only once replayed, and the cockpit cannot replay.
    """

    available: Literal[True]
    title: str
    model: str
    floor_passed: int
    floor_total: int
    regression_candidates: list[str]
    contribution: int
    contribution_population: int
    gated: Literal[False]
    note: str


class AgentEvaluationsGate(BaseModel):
    """agent-evaluations.gate."""

    passed: bool
    failed_critical: list[str]
    standard_passed: int
    standard_total: int
    label: str
    breakdown: AgentEvaluationsGateBreakdown
    tone: str
    reason: str
    candidate: str
    grains: AgentEvaluationsGateGrains
    counts: AgentEvaluationsGateCounts
    socle: AgentEvaluationsGateSocle
    domain: AgentEvaluationsGateDomain
    contribution: (
        AgentEvaluationsGateContributionPayload | AgentEvaluationsGateContributionUnavailable
    )
    breakdown_grain: AgentEvaluationsGateBreakdownGrain
    tiers: list[AgentEvaluationsGateTiersItem]
    venn: AgentEvaluationsGateVenn
    socle_by_category: list[AgentEvaluationsGateSocleByCategoryItem]
    critical_cases: AgentEvaluationsGateCriticalCases
    waivers: AgentEvaluationsGateWaivers


class AgentEvaluationsJudgeUnavailable(BaseModel):
    """Honest-empty: the compute raised; the page must not break."""

    available: Literal[False]


class AgentEvaluationsJudgePayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union."""

    available: Literal[True]
    judge_model: str
    context_basis: str
    faithfulness: float
    grounding: float
    hallucination: float
    n: int


class AgentEvaluationsRunsItemsItem(BaseModel):
    """agent-evaluations.runs.items.item — one eval run on the ER-01 rail.

    Provenance is per run (date + catalogue version + model, eval-gate-policy
    § provenance). ``gate_passed`` is the verdict recorded at run time — ``None``
    means "not recorded", which the rail says instead of inventing one.
    ``delta_pass_rate`` is ``None`` unless a previous same-catalogue run exists.
    """

    run_at: str
    label: str
    date_label: str
    pass_rate: float
    score: str
    passed: int
    total: int
    gate_passed: bool | None
    eval_set: str
    catalogue_version: str
    model: str
    delta_pass_rate: float | None


class AgentEvaluationsRuns(BaseModel):
    """agent-evaluations.runs."""

    title: str
    subtitle: str
    empty_label: str
    items: list[AgentEvaluationsRunsItemsItem]
    count: int


class AgentEvaluationsSetsRowsItem(BaseModel):
    """agent-evaluations.sets.rows.item — one curated evaluation set."""

    slug: str
    name: str
    description: str
    agent_id: str
    bound: bool
    active: bool
    case_count: int
    declared_count: int
    floor_count: int
    critical_count: int
    standard_count: int
    category_count: int
    languages: list[str]
    gate_rationale: str
    case_ids: list[str]


class AgentEvaluationsSetsCasesItem(BaseModel):
    """agent-evaluations.sets.cases.item — one failure-catalogue case."""

    id: str
    title: str
    category: str
    category_label: str
    category_tone: str
    severity: str
    severity_label: str
    severity_tone: str
    languages: list[str]
    tags: list[str]
    citation: str


class AgentEvaluationsSets(BaseModel):
    """agent-evaluations.sets — curated eval sets + the case catalogue."""

    title: str
    subtitle: str
    columns: list[str]
    case_columns: list[str]
    rows: list[AgentEvaluationsSetsRowsItem]
    cases: list[AgentEvaluationsSetsCasesItem]
    total: int
    active_slug: str
    empty_label: str
    cases_label: str
    bound_label: str
    shared_label: str
    active_label: str
    rationale_label: str
    floor_note: str


class AgentEvaluationsResultsRowsItem(BaseModel):
    """agent-evaluations.results.rows.item — one case x language run outcome."""

    case_id: str
    title: str
    language: str
    category: str
    category_label: str
    category_tone: str
    passed: bool
    status_label: str
    status_tone: str
    escalated: bool
    tools: list[str]
    tool_count: int
    duration_ms: float
    duration_label: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    question: str
    response: str
    reasons: list[str]
    started_at: str


class AgentEvaluationsResultsLabels(BaseModel):
    """agent-evaluations.results.labels — the result drawer's localized chrome."""

    question: str
    response: str
    diagnostic: str
    tools: str
    no_tools: str
    escalated: str
    tokens: str
    started: str
    no_question: str


class AgentEvaluationsResults(BaseModel):
    """agent-evaluations.results — the run's per-case outcomes (Results / Errors)."""

    title: str
    subtitle: str
    columns: list[str]
    rows: list[AgentEvaluationsResultsRowsItem]
    total: int
    passed: int
    failed: int
    escalated: int
    errors_title: str
    errors_subtitle: str
    empty_results: str
    empty_errors: str
    labels: AgentEvaluationsResultsLabels


class AgentEvaluationsUnavailable(BaseModel):
    """Honest-empty: the compute raised; the page must not break."""

    available: Literal[False]


class AgentEvaluationsPayload(BaseModel):
    """`available: True` GUARANTEES every field below. That is the point of the union."""

    available: Literal[True]
    title: str
    subtitle: str
    actions: AgentEvaluationsActions
    subtabs: list[str]
    meta: AgentEvaluationsMeta
    detail_labels: AgentEvaluationsDetailLabels
    snapshot: AgentEvaluationsSnapshot
    kpis: list[AgentEvaluationsKpisItem]
    filters: AgentEvaluationsFilters
    table: AgentEvaluationsTable
    watch: AgentEvaluationsWatch
    quick: AgentEvaluationsQuick
    trend: AgentEvaluationsTrend
    agent_id: str
    scoped: bool
    gate: AgentEvaluationsGate
    judge: AgentEvaluationsJudgePayload | AgentEvaluationsJudgeUnavailable
    runs: AgentEvaluationsRuns
    sets: AgentEvaluationsSets
    results: AgentEvaluationsResults
