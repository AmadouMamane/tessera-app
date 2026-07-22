/**
 * Typed fetch client.
 *
 * Every public function wraps `fetch` with two invariants:
 *
 * 1. The path is prefixed with `/api` so that the Next.js rewrite layer
 *    forwards to the FastAPI backend (configured via the `TESSERA_BACKEND_URL`
 *    env var at build time).
 * 2. The response is validated through the matching Zod schema. Validation
 *    failures throw `ApiError` rather than returning malformed data.
 */
import type { z } from "zod";

import {
  type AIActReport,
  AIActReportSchema,
  type AblationReport,
  AblationReportSchema,
  type AccessOverview,
  AccessOverviewSchema,
  type AgentAFaire,
  AgentAFaireSchema,
  type AgentConfigurations,
  AgentConfigurationsSchema,
  type AgentConnaissances,
  AgentConnaissancesSchema,
  type AgentConsole,
  AgentConsoleSchema,
  type AgentEvaluations,
  AgentEvaluationsSchema,
  type AgentGardeFous,
  AgentGardeFousSchema,
  type AgentHistorique,
  AgentHistoriqueSchema,
  type AgentInvokeOutcome,
  AgentInvokeOutcomeSchema,
  type AgentPrompts,
  AgentPromptsSchema,
  type AgentSynthese,
  AgentSyntheseSchema,
  type AnomalyReport,
  AnomalyReportSchema,
  type AssistantOverview,
  AssistantOverviewSchema,
  type AuditActorRole,
  type AuditEventType,
  type AuditIntegrity,
  AuditIntegritySchema,
  type AuditOutcome,
  type AuditOverview,
  AuditOverviewSchema,
  type AuditPage,
  AuditPageSchema,
  type AutomationsOverview,
  AutomationsOverviewSchema,
  type BudgetSnapshot,
  BudgetSnapshotSchema,
  type BusinessCapabilitiesResponse,
  BusinessCapabilitiesResponseSchema,
  type Calibration,
  CalibrationSchema,
  type CatalogueConsumers,
  CatalogueConsumersSchema,
  type Chrome,
  ChromeSchema,
  type CitationResolution,
  CitationResolutionSchema,
  type CitationSummary,
  CitationSummarySchema,
  type ClientAlerts,
  ClientAlertsSchema,
  type ClientDocuments,
  ClientDocumentsSchema,
  type ClientRequests,
  ClientRequestsSchema,
  type ClientSettings,
  ClientSettingsSchema,
  type ClusterReport,
  ClusterReportSchema,
  type ComplianceReport,
  ComplianceReportSchema,
  type ConformanceReport,
  ConformanceReportSchema,
  type ConnectorsOverview,
  ConnectorsOverviewSchema,
  type ConsistencyReport,
  ConsistencyReportSchema,
  type ConsoleFeedback,
  ConsoleFeedbackSchema,
  type ContradictionReport,
  ContradictionReportSchema,
  type ControlSignals,
  ControlSignalsSchema,
  type ConversationList,
  ConversationListSchema,
  type ConversationMessages,
  ConversationMessagesSchema,
  type CorpusScanReport,
  CorpusScanReportSchema,
  type CostReport,
  CostReportSchema,
  type CoverageReport,
  CoverageReportSchema,
  type CrossLingualReport,
  CrossLingualReportSchema,
  type CrossTenantReport,
  CrossTenantReportSchema,
  type CurationOverview,
  CurationOverviewSchema,
  type CustomerFeedbackResponse,
  CustomerFeedbackResponseSchema,
  type DataRange,
  DataRangeSchema,
  type DisclosureReport,
  DisclosureReportSchema,
  type EnsembleReport,
  EnsembleReportSchema,
  type ErasureCoverage,
  ErasureCoverageSchema,
  type EtatADate,
  EtatADateSchema,
  type EvalScoresResponse,
  EvalScoresResponseSchema,
  type EvidencePackManifest,
  EvidencePackManifestSchema,
  type EvidencePackVerify,
  EvidencePackVerifySchema,
  type FailedCasesReport,
  FailedCasesReportSchema,
  type FailedRunsReport,
  FailedRunsReportSchema,
  type FirewallEfficacy,
  FirewallEfficacySchema,
  type Fleet,
  FleetSchema,
  type FreshnessReport,
  FreshnessReportSchema,
  type FunnelReport,
  FunnelReportSchema,
  type GovernanceFeed,
  GovernanceFeedSchema,
  type GraphTopology,
  GraphTopologySchema,
  type GuardExplainReport,
  GuardExplainReportSchema,
  type GuardrailCatalogue,
  GuardrailCatalogueSchema,
  type HandoffReport,
  HandoffReportSchema,
  type HealthResponse,
  HealthResponseSchema,
  type ImprovementReport,
  ImprovementReportSchema,
  type InboxOverview,
  InboxOverviewSchema,
  type IncidentsOverview,
  IncidentsOverviewSchema,
  type IntegrationsOverview,
  IntegrationsOverviewSchema,
  type IntentReport,
  IntentReportSchema,
  type InventoryReport,
  InventoryReportSchema,
  type InversionReport,
  InversionReportSchema,
  type JourneyReport,
  JourneyReportSchema,
  type JudgeConsensus,
  JudgeConsensusSchema,
  type JudgeDrift,
  JudgeDriftSchema,
  type LocaleFormatSummary,
  LocaleFormatSummarySchema,
  type LocalizationReport,
  LocalizationReportSchema,
  type MemoryObsReport,
  MemoryObsReportSchema,
  type MetricPairs,
  MetricPairsSchema,
  type ModelCatalogue,
  ModelCatalogueSchema,
  type ModelComparison,
  ModelComparisonSchema,
  type ObsCostReport,
  ObsCostReportSchema,
  type OverflowReport,
  OverflowReportSchema,
  type OverrideKnob,
  OverrideKnobSchema,
  type OverviewSnapshotEnvelope,
  OverviewSnapshotSchema,
  type OwnTranscript,
  OwnTranscriptSchema,
  type PIILeakSummary,
  PIILeakSummarySchema,
  type ParametersOverview,
  ParametersOverviewSchema,
  type PlaybookReport,
  PlaybookReportSchema,
  type PoliciesOverview,
  PoliciesOverviewSchema,
  type PredictorEvaluation,
  PredictorEvaluationSchema,
  type PrivilegeReport,
  PrivilegeReportSchema,
  type PromptOverlayState,
  PromptOverlayStateSchema,
  type ProofsOverview,
  ProofsOverviewSchema,
  type PropagationReport,
  PropagationReportSchema,
  ProposeAgentSchema,
  type ProvenanceReport,
  ProvenanceReportSchema,
  type QualityDatasetsReport,
  QualityDatasetsReportSchema,
  type RbacMatrix,
  RbacMatrixSchema,
  type RecouvrementQueue,
  RecouvrementQueueSchema,
  type RecouvrementRunsResponse,
  RecouvrementRunsResponseSchema,
  type RedTeamResponse,
  RedTeamResponseSchema,
  type RefusalReport,
  RefusalReportSchema,
  type RegressionRisk,
  RegressionRiskSchema,
  type ReleaseAgent,
  ReleaseAgentSchema,
  type ReleaseStatus,
  ReleaseStatusSchema,
  type ReliabilityReport,
  ReliabilityReportSchema,
  type ReplayResult,
  ReplayResultSchema,
  type ReplayShadowOverview,
  ReplayShadowOverviewSchema,
  type ReplaysResponse,
  ReplaysResponseSchema,
  type ReproReport,
  ReproReportSchema,
  type RerankContribution,
  RerankContributionSchema,
  type RetractionReport,
  RetractionReportSchema,
  type RoadmapReport,
  RoadmapReportSchema,
  type RobustnessReport,
  RobustnessReportSchema,
  type RoutingReport,
  RoutingReportSchema,
  type RunRegistry,
  RunRegistrySchema,
  type SFTDataset,
  SFTDatasetSchema,
  type SLOReport,
  SLOReportSchema,
  type SandboxConfig,
  SandboxConfigSchema,
  type ScoreSeries,
  ScoreSeriesSchema,
  type SessionDetail,
  SessionDetailSchema,
  type SessionReport,
  SessionReportSchema,
  type SettingsOverrides,
  SettingsOverridesSchema,
  type ShadowReport,
  ShadowReportSchema,
  type SiemExport,
  SiemExportSchema,
  type SignalCatalogue,
  SignalCatalogueSchema,
  type SkewReport,
  SkewReportSchema,
  type SnapshotDiffReport,
  SnapshotDiffReportSchema,
  type SourcesOverview,
  SourcesOverviewSchema,
  type StatusCountsTrend,
  StatusCountsTrendSchema,
  type StegoReport,
  StegoReportSchema,
  type SycophancyReport,
  SycophancyReportSchema,
  type SystemProfile,
  SystemProfileSchema,
  type TailSamplingReport,
  TailSamplingReportSchema,
  type TimelineReport,
  TimelineReportSchema,
  type ToolLoopReport,
  ToolLoopReportSchema,
  type ToolValidity,
  ToolValiditySchema,
  type ToxicityReport,
  ToxicityReportSchema,
  type TracesObs,
  TracesObsSchema,
  type Trajectory,
  TrajectorySchema,
  type TrendReport,
  TrendReportSchema,
  type UsersOverview,
  UsersOverviewSchema,
  type WhatChanged,
  WhatChangedSchema,
  type WhyExplanation,
  WhyExplanationSchema,
} from "./schemas";

const BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<TSchema extends z.ZodTypeAny>(
  path: string,
  init: RequestInit,
  schema: TSchema,
): Promise<z.infer<TSchema>> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
  });

  const text = await response.text();
  let body: unknown = null;
  if (text.length > 0) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const message =
      (body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : null) ?? `request to ${path} failed`;
    throw new ApiError(message, response.status, body);
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError(
      `response from ${path} did not match the expected schema`,
      response.status,
      parsed.error.format(),
    );
  }
  return parsed.data;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export interface FetchAuditOptions {
  cursor?: number;
  limit?: number;
  target?: string;
  outcome?: AuditOutcome;
  eventType?: AuditEventType;
  actorRole?: AuditActorRole;
  scope?: string;
  policyRule?: string;
  query?: string;
  since?: string;
  until?: string;
  agent?: string;
  signal?: AbortSignal;
}

function appendAuditParams(params: URLSearchParams, options: FetchAuditOptions): void {
  if (options.target) params.set("target", options.target);
  if (options.outcome) params.set("outcome", options.outcome);
  if (options.eventType) params.set("event_type", options.eventType);
  if (options.actorRole) params.set("actor_role", options.actorRole);
  if (options.scope) params.set("scope", options.scope);
  if (options.policyRule) params.set("policy_rule", options.policyRule);
  if (options.query) params.set("q", options.query);
  if (options.since) params.set("since", options.since);
  if (options.until) params.set("until", options.until);
  if (options.agent && options.agent !== "all") params.set("agent", options.agent);
}

export async function fetchAudit(options: FetchAuditOptions = {}): Promise<AuditPage> {
  const params = new URLSearchParams();
  if (options.cursor != null) params.set("cursor", String(options.cursor));
  if (options.limit != null) params.set("limit", String(options.limit));
  appendAuditParams(params, options);
  const query = params.toString();
  return request(`/audit${query ? `?${query}` : ""}`, { signal: options.signal }, AuditPageSchema);
}

export async function fetchAuditOverview(
  options: Omit<FetchAuditOptions, "cursor" | "limit"> = {},
): Promise<AuditOverview> {
  const params = new URLSearchParams();
  appendAuditParams(params, options);
  const query = params.toString();
  return request(
    `/audit/overview${query ? `?${query}` : ""}`,
    { signal: options.signal },
    AuditOverviewSchema,
  );
}

export async function fetchAuditIntegrity(
  signal?: AbortSignal,
  at?: string,
): Promise<AuditIntegrity> {
  // The chain length honours T (append-only count up to the instant); the chain
  // verification stays a structural live check (handled server-side).
  return request(withAsOf("/audit/integrity", at), { signal }, AuditIntegritySchema);
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request("/healthz", { signal }, HealthResponseSchema);
}

export async function fetchReadiness(signal?: AbortSignal): Promise<HealthResponse> {
  return request("/readyz", { signal }, HealthResponseSchema);
}

/** Append an optional `?at=<ISO>` as-of-T instant to an observability path (ADR 0011). */
function withAsOf(path: string, at?: string): string {
  return at ? `${path}?at=${encodeURIComponent(at)}` : path;
}

/**
 * Append the optional as-of-T instant (`?at=`) and the global agent scope
 * (`?agent=`) to an observability path. The agent scope rides the same `?agent=`
 * key the GOUVERNER/PLATEFORME surfaces use (lib/agent-scope); `"all"` (or empty)
 * is the org view and is omitted so the URL stays clean.
 */
function withScope(path: string, at?: string, agent?: string): string {
  const params = new URLSearchParams();
  if (at) params.set("at", at);
  if (agent && agent !== "all") params.set("agent", agent);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/**
 * Recent online-eval scores (eval-as-telemetry; public aggregate surface).
 *
 * With `at` set, the durable score log is read as of that instant (ADR 0011).
 */
export async function fetchEvalScores(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<EvalScoresResponse> {
  return request(
    withScope("/observability/scores", at, agent),
    { signal },
    EvalScoresResponseSchema,
  );
}

/** Generic business runs for ANY agent — dimension filters only (ADR 0017 Phase A). */
export async function fetchBusinessRuns(
  signal?: AbortSignal,
  options: {
    at?: string;
    agent?: string;
    workflowId?: string;
    capabilityId?: string;
    limit?: number;
  } = {},
): Promise<RecouvrementRunsResponse> {
  const params = new URLSearchParams();
  if (options.at) params.set("at", options.at);
  if (options.agent) params.set("agent", options.agent);
  if (options.workflowId) params.set("workflow_id", options.workflowId);
  if (options.capabilityId) params.set("capability_id", options.capabilityId);
  params.set("limit", String(options.limit ?? 20));
  return request(
    `/observability/business/runs?${params.toString()}`,
    { signal },
    RecouvrementRunsResponseSchema,
  );
}

/** Per-capability business aggregate for one agent (ADR 0017 §A1.4). */
export async function fetchBusinessCapabilities(
  signal?: AbortSignal,
  options: {
    at?: string;
    agent?: string;
    workflowId?: string;
    conversationId?: string;
    turnId?: string;
    caseId?: string;
  } = {},
): Promise<BusinessCapabilitiesResponse> {
  const params = new URLSearchParams();
  if (options.at) params.set("at", options.at);
  if (options.agent) params.set("agent", options.agent);
  if (options.workflowId) params.set("workflow_id", options.workflowId);
  if (options.conversationId) params.set("conversation_id", options.conversationId);
  if (options.turnId) params.set("turn_id", options.turnId);
  if (options.caseId) params.set("case_id", options.caseId);
  return request(
    `/observability/business/capabilities?${params.toString()}`,
    { signal },
    BusinessCapabilitiesResponseSchema,
  );
}

/** Temporal lineage timeline — dated events for the cockpit time rail (#201). */
export async function fetchTimeline(signal?: AbortSignal, at?: string): Promise<TimelineReport> {
  return request(withAsOf("/observability/timeline", at), { signal }, TimelineReportSchema);
}

/** Honest data-availability bounds for the time-rail "Aller à une date" calendar. */
export async function fetchDataRange(signal?: AbortSignal): Promise<DataRange> {
  return request("/observability/data-range", { signal }, DataRangeSchema);
}

/**
 * Quality SLO + error-budget burn-rate over the faithfulness scores (#15).
 *
 * With `at` set, the SLO is recomputed over the durable log as of T (ADR 0011).
 */
export async function fetchSLO(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<SLOReport> {
  return request(withScope("/observability/slo", at, agent), { signal }, SLOReportSchema);
}

/**
 * Every hot-path signal for one scope, in a single round-trip (ADR 0015 §Performance).
 *
 * The backend computes them over shared upstream reads, behind a read-through cache with
 * single-flight; `tests/unit/test_spine_signals_parity.py` pins each slice byte-identical to
 * the individual route it replaces. Cards select their slice with `selectSignal`, validating
 * it against the very schema their own route used — the collapse buys round-trips, not trust.
 *
 * The per-signal routes below are RETAINED: other pages still call them, and they remain the
 * contract this snapshot is checked against.
 */
export async function fetchOverviewSnapshot(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
  signals?: readonly string[],
): Promise<OverviewSnapshotEnvelope> {
  const path = withScope("/observability/snapshot", at, agent);
  const scoped =
    signals && signals.length > 0
      ? `${path}${path.includes("?") ? "&" : "?"}signals=${signals.join(",")}`
      : path;
  return request(scoped, { signal }, OverviewSnapshotSchema);
}

/** Mirror recent captured turns to a candidate model and compare (shadow, #16). */
export async function runShadow(model: string, limit = 10): Promise<ShadowReport> {
  return request(
    "/observability/shadow",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model, limit }),
    },
    ShadowReportSchema,
  );
}

/** Memory-layer activity: writes, recall hit/miss, stored-injection caught (#23). */
export async function fetchMemoryObs(signal?: AbortSignal): Promise<MemoryObsReport> {
  return request("/observability/memory", { signal }, MemoryObsReportSchema);
}

/** Security audit events normalised to ECS/SIEM shape for the SOC (#172). */
export async function fetchSiem(signal?: AbortSignal): Promise<SiemExport> {
  return request("/observability/siem", { signal }, SiemExportSchema);
}

/** Resolve answer citations to verifiable corpus sources (clickable, #132). */
export async function fetchCitationLinks(signal?: AbortSignal): Promise<CitationResolution> {
  return request("/observability/citation-links", { signal }, CitationResolutionSchema);
}

/** AI-interaction disclosure status and per-locale text (Art. 50, #134). */
export async function fetchDisclosure(signal?: AbortSignal): Promise<DisclosureReport> {
  return request("/observability/disclosure", { signal }, DisclosureReportSchema);
}

/** EU AI Act compliance posture: transparency, oversight, traceability (#76), live or as of T. */
export async function fetchAIAct(signal?: AbortSignal, at?: string): Promise<AIActReport> {
  return request(withAsOf("/observability/ai-act", at), { signal }, AIActReportSchema);
}

/** Per-locale message completeness vs the default locale (#77). */
export async function fetchLocalization(signal?: AbortSignal): Promise<LocalizationReport> {
  return request("/observability/localization", { signal }, LocalizationReportSchema);
}

/** Incident playbooks triggered by the live (or as-of-T) signals (#115). */
export async function fetchPlaybooks(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<PlaybookReport> {
  return request(
    withScope("/observability/playbooks", at, agent),
    { signal },
    PlaybookReportSchema,
  );
}

/** Tool least-privilege: granted vs actually-used tools from the audit (#101). */
export async function fetchLeastPrivilege(signal?: AbortSignal): Promise<PrivilegeReport> {
  return request("/observability/least-privilege", { signal }, PrivilegeReportSchema);
}

/** Cross-tenant leakage: foreign subject ids in a turn's context (#74). */
export async function fetchCrossTenant(signal?: AbortSignal): Promise<CrossTenantReport> {
  return request("/observability/cross-tenant", { signal }, CrossTenantReportSchema);
}

/** Toxicity / harmful-output rate over captured answers (#60), live or as of T. */
export async function fetchToxicity(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<ToxicityReport> {
  return request(withScope("/observability/toxicity", at, agent), { signal }, ToxicityReportSchema);
}

/** Distil high-scoring captured turns into an SFT dataset (#122). */
export async function fetchSftDataset(signal?: AbortSignal): Promise<SFTDataset> {
  return request("/observability/sft-dataset", { signal }, SFTDatasetSchema);
}

/** Back-test the pre-judge failure predictor against captured turns (#121). */
export async function fetchFailurePredictor(signal?: AbortSignal): Promise<PredictorEvaluation> {
  return request("/observability/failure-predictor", { signal }, PredictorEvaluationSchema);
}

/** Auto-clustered themes across the documented failure corpus (#123). */
export async function fetchFailureClusters(signal?: AbortSignal): Promise<ClusterReport> {
  return request("/observability/failure-clusters", { signal }, ClusterReportSchema);
}

/** Embedding-inversion privacy risk over a demo corpus (#73). */
export async function fetchEmbeddingInversion(signal?: AbortSignal): Promise<InversionReport> {
  return request("/observability/embedding-inversion", { signal }, InversionReportSchema);
}

/** The telemetry-erasure surface: conversations, bundles, scores in scope (#180). */
export async function fetchErasureCoverage(signal?: AbortSignal): Promise<ErasureCoverage> {
  return request("/observability/erasure-coverage", { signal }, ErasureCoverageSchema);
}

/** What the agent remembers: long-term store inventory (GDPR access, #135). */
export async function fetchMemoryInventory(signal?: AbortSignal): Promise<InventoryReport> {
  return request("/observability/memory-inventory", { signal }, InventoryReportSchema);
}

/** Delegation-chain handoff tracing and broken-handoff detection (#189). */
export async function fetchHandoffs(signal?: AbortSignal): Promise<HandoffReport> {
  return request("/observability/handoffs", { signal }, HandoffReportSchema);
}

/** Cross-session customer journeys mined from the memory audit trail (#99). */
export async function fetchJourney(signal?: AbortSignal): Promise<JourneyReport> {
  return request("/observability/journey", { signal }, JourneyReportSchema);
}

/** Telemetry-mined product backlog: ranked roadmap items (#124), live or as of T. */
export async function fetchRoadmap(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<RoadmapReport> {
  return request(withScope("/observability/roadmap", at, agent), { signal }, RoadmapReportSchema);
}

/** Staleness of the ingested regulatory corpora vs their review horizon (#50). */
export async function fetchCorpusFreshness(signal?: AbortSignal): Promise<FreshnessReport> {
  return request("/observability/corpus-freshness", { signal }, FreshnessReportSchema);
}

/** Embedding-version skew between the query-time and corpus embedders (#64). */
export async function fetchEmbeddingSkew(signal?: AbortSignal): Promise<SkewReport> {
  return request("/observability/embedding-skew", { signal }, SkewReportSchema);
}

/** Async/parallel span-propagation health from a live isolated probe (#85). */
export async function fetchSpanPropagation(signal?: AbortSignal): Promise<PropagationReport> {
  return request("/observability/span-propagation", { signal }, PropagationReportSchema);
}

/** Tail-sampling retention: 100% of slow/low-score traces, sampled head (#32). */
export async function fetchTailSampling(signal?: AbortSignal): Promise<TailSamplingReport> {
  return request("/observability/tail-sampling", { signal }, TailSamplingReportSchema);
}

/** Trace-shape reproducibility / non-determinism across repeated questions (#86). */
export async function fetchReproducibility(signal?: AbortSignal): Promise<ReproReport> {
  return request("/observability/reproducibility", { signal }, ReproReportSchema);
}

/**
 * Long-horizon faithfulness trend over the score series (#150).
 *
 * With `at` set, the trend is recomputed over the durable log as of T (ADR 0011).
 */
export async function fetchTrend(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<TrendReport> {
  return request(withScope("/observability/trend", at, agent), { signal }, TrendReportSchema);
}

/** Calendar-time score series for one metric (Vue d'ensemble chart + metric KPIs). */
export async function fetchScoreSeries(
  signal?: AbortSignal,
  at?: string,
  metric?: string,
  agent?: string,
): Promise<ScoreSeries> {
  const params = new URLSearchParams();
  if (at) params.set("at", at);
  if (metric) params.set("metric", metric);
  if (agent && agent !== "all") params.set("agent", agent);
  const query = params.toString();
  return request(
    `/observability/score-series${query ? `?${query}` : ""}`,
    { signal },
    ScoreSeriesSchema,
  );
}

/** Judge score-drift over the window (Calibration juge tab, image 05). */
export async function fetchJudgeDrift(
  signal?: AbortSignal,
  at?: string,
  metric?: string,
): Promise<JudgeDrift> {
  const params = new URLSearchParams();
  if (at) params.set("at", at);
  if (metric) params.set("metric", metric);
  const query = params.toString();
  return request(
    `/observability/judge-drift${query ? `?${query}` : ""}`,
    { signal },
    JudgeDriftSchema,
  );
}

/** Forward-looking regression risk (Vue d'ensemble — Signaux prédictifs, image 00). */
export async function fetchRegressionRisk(
  signal?: AbortSignal,
  at?: string,
  metric?: string,
): Promise<RegressionRisk> {
  const params = new URLSearchParams();
  if (at) params.set("at", at);
  if (metric) params.set("metric", metric);
  const query = params.toString();
  return request(
    `/observability/regression-risk${query ? `?${query}` : ""}`,
    { signal },
    RegressionRiskSchema,
  );
}

/** Per-severity-band score-count trend (Signaux KPI strip, image 01). */
export async function fetchSignalStatusTrend(
  signal?: AbortSignal,
  at?: string,
): Promise<StatusCountsTrend> {
  const params = new URLSearchParams();
  if (at) params.set("at", at);
  const query = params.toString();
  return request(
    `/observability/signal-status-trend${query ? `?${query}` : ""}`,
    { signal },
    StatusCountsTrendSchema,
  );
}

/** Multi-judge consensus over the gold set (Calibration juge tab, image 05). */
export async function fetchJudgeConsensus(signal?: AbortSignal): Promise<JudgeConsensus> {
  return request("/observability/judge-consensus", { signal }, JudgeConsensusSchema);
}

/** Eval run registry from the report archive (Runs & datasets tab, image 02). */
export async function fetchRuns(signal?: AbortSignal): Promise<RunRegistry> {
  return request("/observability/runs", { signal }, RunRegistrySchema);
}

/** Themed quality datasets (catalogue × runs) for the Runs & datasets tab (image 02). */
export async function fetchEvalDatasets(signal?: AbortSignal): Promise<QualityDatasetsReport> {
  return request("/observability/eval-datasets", { signal }, QualityDatasetsReportSchema);
}

/** Per-model comparison from the report archive (Comparaisons modèles tab, image 04). */
export async function fetchModelComparison(signal?: AbortSignal): Promise<ModelComparison> {
  return request("/observability/model-comparison", { signal }, ModelComparisonSchema);
}

/** Current release + real open regressions, for the Vue d'ensemble rail (image 00). */
export async function fetchReleaseStatus(signal?: AbortSignal): Promise<ReleaseStatus> {
  return request("/observability/release-status", { signal }, ReleaseStatusSchema);
}

/** Per-turn metric pairs for a scatter, e.g. faithfulness vs grounding (image 00). */
export async function fetchMetricPairs(
  signal?: AbortSignal,
  x = "faithfulness",
  y = "grounding",
  at?: string,
): Promise<MetricPairs> {
  const params = new URLSearchParams({ x, y });
  if (at) params.set("at", at);
  return request(`/observability/metric-pairs?${params.toString()}`, { signal }, MetricPairsSchema);
}

/** Documented failed-case catalogue + distributions (Cas échoués tab, image 03). */
export async function fetchFailedCases(
  signal?: AbortSignal,
  language?: string,
  limit?: number,
): Promise<FailedCasesReport> {
  const params = new URLSearchParams();
  if (language) params.set("language", language);
  if (limit != null) params.set("limit", String(limit));
  const query = params.toString();
  return request(
    `/observability/failed-cases${query ? `?${query}` : ""}`,
    { signal },
    FailedCasesReportSchema,
  );
}

/** Real failed cases from the run archive (Cas échoués tab, image 03). */
export async function fetchFailedRuns(signal?: AbortSignal): Promise<FailedRunsReport> {
  return request("/observability/failed-runs", { signal }, FailedRunsReportSchema);
}

/** Measured instrumentation overhead vs the turn budget (cost of obs, #84). */
export async function fetchObsCost(signal?: AbortSignal): Promise<ObsCostReport> {
  return request("/observability/obs-cost", { signal }, ObsCostReportSchema);
}

/** Judge calibration against the human gold set (computed server-side, cached). */
export async function fetchCalibration(signal?: AbortSignal): Promise<Calibration> {
  return request("/observability/calibration", { signal }, CalibrationSchema);
}

/** Guard/firewall detection efficacy over injection vs benign inputs. */
export async function fetchFirewallEfficacy(signal?: AbortSignal): Promise<FirewallEfficacy> {
  return request("/observability/firewall-efficacy", { signal }, FirewallEfficacySchema);
}

/** Regulatory compliance posture derived from the real runtime signals (#07). */
export async function fetchCompliance(
  lang: string,
  signal?: AbortSignal,
): Promise<ComplianceReport> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/compliance${q}`, { signal }, ComplianceReportSchema);
}

/** Operational reliability & cost posture derived from the real signals (#08). */
export async function fetchReliability(
  signal?: AbortSignal,
  days = 14,
  anchor?: string | null,
  lang?: string,
): Promise<ReliabilityReport> {
  const qs = new URLSearchParams({ days: String(days) });
  if (anchor) qs.set("anchor", anchor);
  if (lang) qs.set("lang", lang);
  return request(`/observability/reliability?${qs}`, { signal }, ReliabilityReportSchema);
}

/** Continuous-improvement posture mined from the telemetry roadmap (#09). */
export async function fetchImprovement(
  lang: string,
  at?: string | null,
  signal?: AbortSignal,
): Promise<ImprovementReport> {
  const params = new URLSearchParams({ lang });
  if (at) params.set("at", at);
  return request(`/observability/improvement?${params}`, { signal }, ImprovementReportSchema);
}

/** Open one durable incident (governed act; opener = verified assertion). */
export async function mutateIncidentCreate(body: {
  title: string;
  severity: string;
  domain?: string;
  lang?: string;
}): Promise<IncidentsOverview> {
  return request(
    "/observability/incidents",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    IncidentsOverviewSchema,
  );
}

/** Move one incident along its lifecycle (governed, journalled). */
export async function mutateIncidentTransition(body: {
  incident_id: string;
  status: string;
  lang?: string;
}): Promise<IncidentsOverview> {
  return request(
    "/observability/incidents/transition",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    IncidentsOverviewSchema,
  );
}

/** Attach one declared playbook to an incident (governed, journalled). */
export async function mutateIncidentPlaybook(body: {
  incident_id: string;
  playbook_id: string;
  lang?: string;
}): Promise<IncidentsOverview> {
  return request(
    "/observability/incidents/playbook",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    IncidentsOverviewSchema,
  );
}

export async function fetchIncidentsOverview(
  lang: string,
  at?: string | null,
  signal?: AbortSignal,
): Promise<IncidentsOverview> {
  const params = new URLSearchParams({ lang });
  if (at) params.set("at", at);
  return request(`/observability/incidents?${params}`, { signal }, IncidentsOverviewSchema);
}

export async function fetchReplayShadowOverview(
  lang: string,
  at?: string | null,
  signal?: AbortSignal,
): Promise<ReplayShadowOverview> {
  const params = new URLSearchParams();
  if (lang) params.set("lang", lang);
  if (at) params.set("at", at);
  const q = params.size ? `?${params}` : "";
  return request(`/observability/replay-shadow${q}`, { signal }, ReplayShadowOverviewSchema);
}

export async function fetchCurationOverview(
  lang: string,
  at?: string | null,
  signal?: AbortSignal,
): Promise<CurationOverview> {
  const params = new URLSearchParams();
  if (lang) params.set("lang", lang);
  if (at) params.set("at", at);
  const q = params.size ? `?${params}` : "";
  return request(`/observability/curation${q}`, { signal }, CurationOverviewSchema);
}

/** Persist a curation decision (promote/review/reject) for one candidate; returns fresh payload. */
export async function mutateCurationDecision(body: {
  candidate_id: string;
  decision: "pending" | "promote" | "review" | "reject";
  lang?: string;
}): Promise<CurationOverview> {
  return request(
    "/observability/curation/decision",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    CurationOverviewSchema,
  );
}

/** Evaluate every enabled automation rule against its real store; journalled. */
export async function mutateAutomationsEvaluate(lang: string): Promise<AutomationsOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(
    `/observability/automations/evaluate${q}`,
    { method: "POST" },
    AutomationsOverviewSchema,
  );
}

/** Persist an automation rule's enabled flag; returns the fresh payload. */
export async function mutateAutomationRuleState(body: {
  rule_id: string;
  enabled: boolean;
  lang?: string;
}): Promise<AutomationsOverview> {
  return request(
    "/observability/automations/rule-state",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    AutomationsOverviewSchema,
  );
}

/** Enable or suspend EVERY automation rule in one governed, journalled act. */
export async function mutateAutomationsRulesState(body: {
  enabled: boolean;
  lang?: string;
}): Promise<AutomationsOverview> {
  return request(
    "/observability/automations/rules-state",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    AutomationsOverviewSchema,
  );
}

/** Decide one pending approval request (approve/reject); author = verified assertion. */
export async function mutateAutomationApprove(body: {
  approval_id: string;
  approved: boolean;
  lang?: string;
}): Promise<AutomationsOverview> {
  return request(
    "/observability/automations/approve",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    AutomationsOverviewSchema,
  );
}

export async function fetchAutomationsOverview(
  lang: string,
  at?: string | null,
  signal?: AbortSignal,
): Promise<AutomationsOverview> {
  const params = new URLSearchParams();
  if (lang) params.set("lang", lang);
  if (at) params.set("at", at);
  const q = params.size ? `?${params}` : "";
  return request(`/observability/automations${q}`, { signal }, AutomationsOverviewSchema);
}

export async function fetchProofsOverview(
  lang: string,
  signal?: AbortSignal,
  asOf?: string | null,
): Promise<ProofsOverview> {
  const params = new URLSearchParams();
  if (lang) params.set("lang", lang);
  // As-of T: the backend bounds every real count at T (SR-01 reading is real).
  if (asOf) params.set("asof", asOf);
  const q = params.toString();
  return request(`/observability/proofs${q ? `?${q}` : ""}`, { signal }, ProofsOverviewSchema);
}

/** The real collection-case queue + counters (subject-scoped; BFF attaches the assertion). */
export async function fetchRecouvrementQueue(signal?: AbortSignal): Promise<RecouvrementQueue> {
  return request("/observability/recouvrement-queue", { signal }, RecouvrementQueueSchema);
}

/** Freeze one evidence-pack manifest (governed act; author = verified assertion). */
export async function mutateEvidencePackCreate(lang: string): Promise<ProofsOverview> {
  return request(
    "/observability/evidence-packs",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lang }),
    },
    ProofsOverviewSchema,
  );
}

/** One stored pack manifest, verbatim (the downloadable artifact). */
export async function fetchEvidencePackManifest(
  packId: string,
  signal?: AbortSignal,
): Promise<EvidencePackManifest> {
  return request(
    `/observability/evidence-packs/${encodeURIComponent(packId)}/manifest`,
    { signal },
    EvidencePackManifestSchema,
  );
}

/** Re-derive the pack digest + re-verify the live chain — a real verdict. */
export async function fetchEvidencePackVerify(
  packId: string,
  signal?: AbortSignal,
): Promise<EvidencePackVerify> {
  return request(
    `/observability/evidence-packs/${encodeURIComponent(packId)}/verify`,
    { signal },
    EvidencePackVerifySchema,
  );
}

export async function fetchSignalCatalogue(
  lang: string,
  signal?: AbortSignal,
): Promise<SignalCatalogue> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/signal-catalogue${q}`, { signal }, SignalCatalogueSchema);
}

export async function fetchPoliciesOverview(
  lang: string,
  signal?: AbortSignal,
): Promise<PoliciesOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/policies${q}`, { signal }, PoliciesOverviewSchema);
}

export async function fetchSourcesOverview(
  lang?: string,
  signal?: AbortSignal,
): Promise<SourcesOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/sources${q}`, { signal }, SourcesOverviewSchema);
}

export async function fetchAccessOverview(
  lang: string,
  signal?: AbortSignal,
): Promise<AccessOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/access${q}`, { signal }, AccessOverviewSchema);
}

export async function fetchAssistantOverview(
  lang: string,
  signal?: AbortSignal,
): Promise<AssistantOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/assistant${q}`, { signal }, AssistantOverviewSchema);
}

export async function fetchIntegrationsOverview(
  lang: string,
  signal?: AbortSignal,
): Promise<IntegrationsOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/integrations${q}`, { signal }, IntegrationsOverviewSchema);
}

export async function fetchSystemProfile(
  lang: string,
  signal?: AbortSignal,
): Promise<SystemProfile> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/system-profile${q}`, { signal }, SystemProfileSchema);
}

export async function fetchParametersOverview(
  lang: string,
  signal?: AbortSignal,
  asOf?: string | null,
): Promise<ParametersOverview> {
  const params = new URLSearchParams();
  if (lang) params.set("lang", lang);
  // As-of T: the governed overrides are refolded from the ledger at T (OT-01).
  if (asOf) params.set("asof", asOf);
  const q = params.toString();
  return request(
    `/observability/parameters${q ? `?${q}` : ""}`,
    { signal },
    ParametersOverviewSchema,
  );
}

/** The governed operable-knob panel (ADR 0030): org + per-agent chat model. */
export async function fetchSettingsOverrides(signal?: AbortSignal): Promise<SettingsOverrides> {
  return request("/settings/overrides", { signal }, SettingsOverridesSchema);
}

/** Set one governed override (superadmin; author = verified assertion, reason mandatory). */
export async function mutateSettingsOverride(
  key: string,
  body: { value: string; reason: string },
): Promise<OverrideKnob> {
  return request(
    "/settings/overrides",
    {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ key, ...body }),
    },
    OverrideKnobSchema,
  );
}

/** Revert one governed override to its frozen base (superadmin; reason mandatory). */
export async function mutateSettingsOverrideRevert(
  key: string,
  body: { reason: string },
): Promise<OverrideKnob> {
  return request(
    "/settings/overrides/revert",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ key, ...body }),
    },
    OverrideKnobSchema,
  );
}

/** The cockpit chrome's badges and bell. Cheap, composed of reads the pages already do. */
export async function fetchChrome(lang: string, signal?: AbortSignal): Promise<Chrome> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/chrome${q}`, { signal }, ChromeSchema);
}

export async function fetchInboxOverview(
  lang: string,
  signal?: AbortSignal,
  agent?: string,
): Promise<InboxOverview> {
  const params = new URLSearchParams();
  if (lang) params.set("lang", lang);
  if (agent && agent !== "all") params.set("agent", agent);
  const q = params.toString();
  return request(`/observability/inbox${q ? `?${q}` : ""}`, { signal }, InboxOverviewSchema);
}

/** The operator control-cases queue for the overview triage panel (live backlog). */
export async function fetchOverviewCases(signal?: AbortSignal): Promise<InboxOverview> {
  return request("/observability/inbox", { signal }, InboxOverviewSchema);
}

/** Map each overview control to its real catalogue signal + drill-down route. */
export async function fetchControlSignals(
  lang: string,
  signal?: AbortSignal,
): Promise<ControlSignals> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/control-signals${q}`, { signal }, ControlSignalsSchema);
}

/** Governed-activity feed: real S1 governance events + lineage deploys, live or as of T. */
export async function fetchGovernance(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<GovernanceFeed> {
  return request(
    withScope("/observability/governance", at, agent),
    { signal },
    GovernanceFeedSchema,
  );
}

/** Real trace observability read back from the Langfuse stack, live or as of T. */
export async function fetchTracesObs(signal?: AbortSignal, at?: string): Promise<TracesObs> {
  return request(withAsOf("/observability/traces-obs", at), { signal }, TracesObsSchema);
}

/** Persist a status/assignee change for one queue item; returns the fresh payload. */
export async function mutateInboxItem(body: {
  item_id: string;
  status?: string;
  assignee?: string;
}): Promise<InboxOverview> {
  return request(
    "/observability/inbox/item-state",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    InboxOverviewSchema,
  );
}

/** Schema/format conformance of tool-call arguments from the audit trail (#47), live or as of T. */
export async function fetchConformance(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<ConformanceReport> {
  return request(
    withScope("/observability/conformance", at, agent),
    { signal },
    ConformanceReportSchema,
  );
}

/** Topology fingerprint of the live agent graph vs the golden pin (#87). */
export async function fetchGraphTopology(signal?: AbortSignal): Promise<GraphTopology> {
  return request("/observability/graph-topology", { signal }, GraphTopologySchema);
}

/** Streamed-token exposure before an output-guard trigger fires (#90). */
export async function fetchGuardRetraction(signal?: AbortSignal): Promise<RetractionReport> {
  return request("/observability/guard-retraction", { signal }, RetractionReportSchema);
}

/** Ranked breakdown of which guard rules fired across the audit trail (#19). */
export async function fetchGuardExplain(signal?: AbortSignal): Promise<GuardExplainReport> {
  return request("/observability/guard-explain", { signal }, GuardExplainReportSchema);
}

/** Tool-call loop/oscillation detection over the audit invocation stream (#88). */
export async function fetchToolLoops(signal?: AbortSignal): Promise<ToolLoopReport> {
  return request("/observability/tool-loops", { signal }, ToolLoopReportSchema);
}

/** Tool-call validity (allowed vs denied, argument failures) from the audit trail, live or as of T. */
export async function fetchToolValidity(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<ToolValidity> {
  return request(
    withScope("/observability/tool-validity", at, agent),
    { signal },
    ToolValiditySchema,
  );
}

/** Language-routing health: served vs detected language + code-switching. */
export async function fetchRouting(signal?: AbortSignal): Promise<RoutingReport> {
  return request("/observability/routing", { signal }, RoutingReportSchema);
}

/** Context truncation/overflow vs the input window across captured turns (#89). */
export async function fetchContextOverflow(signal?: AbortSignal): Promise<OverflowReport> {
  return request("/observability/context-overflow", { signal }, OverflowReportSchema);
}

/** Token-cost distribution and token-burn anomalies over captured turns (#33), live or as of T. */
export async function fetchCost(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<CostReport> {
  return request(withScope("/observability/cost", at, agent), { signal }, CostReportSchema);
}

/** Business-intent mix and routing confidence over captured questions (#63). */
export async function fetchIntent(signal?: AbortSignal): Promise<IntentReport> {
  return request("/observability/intent", { signal }, IntentReportSchema);
}

/** Refusal-rate calibration: over-refusal (legit) vs under-refusal (forbidden) (#58). */
export async function fetchRefusal(signal?: AbortSignal): Promise<RefusalReport> {
  return request("/observability/refusal", { signal }, RefusalReportSchema);
}

/** Anomalous-conversation detection: long/looping/repetitive sessions (#69), live or as of T. */
export async function fetchAnomalies(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<AnomalyReport> {
  return request(withScope("/observability/anomalies", at, agent), { signal }, AnomalyReportSchema);
}

/** Root-cause "what changed": lineage diff + attribution of a score delta (#17), live or as of T. */
export async function fetchWhatChanged(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<WhatChanged> {
  return request(
    withScope("/observability/what-changed", at, agent),
    { signal },
    WhatChangedSchema,
  );
}

/** Multi-turn self-contradictions across captured sessions (#30). */
export async function fetchContradictions(signal?: AbortSignal): Promise<ContradictionReport> {
  return request("/observability/contradictions", { signal }, ContradictionReportSchema);
}

/** Recorded jailbreak-drift snapshots (continuous red-team, #24). */
export async function fetchRedteam(signal?: AbortSignal): Promise<RedTeamResponse> {
  return request("/observability/redteam", { signal }, RedTeamResponseSchema);
}

/** Run the adversarial corpus through the guard and record a snapshot (#24). */
export async function runRedteam(): Promise<RedTeamResponse> {
  return request("/observability/redteam", { method: "POST" }, RedTeamResponseSchema);
}

/** Regulatory citation validity: cited articles absent from the grounding (#49). */
export async function fetchCitations(signal?: AbortSignal): Promise<CitationSummary> {
  return request("/observability/citations", { signal }, CitationSummarySchema);
}

/** Locale-formatting correctness: amounts whose style mismatches the locale (#51). */
export async function fetchLocaleFormat(signal?: AbortSignal): Promise<LocaleFormatSummary> {
  return request("/observability/locale-format", { signal }, LocaleFormatSummarySchema);
}

/** Output PII-leak rate: PII in answers absent from their grounding (#38), live or as of T. */
export async function fetchPiiLeak(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<PIILeakSummary> {
  return request(withScope("/observability/pii-leak", at, agent), { signal }, PIILeakSummarySchema);
}

/** Per-language conversation funnel from scored turns (#66), live or as of T. */
export async function fetchFunnel(
  signal?: AbortSignal,
  at?: string,
  agent?: string,
): Promise<FunnelReport> {
  return request(withScope("/observability/funnel", at, agent), { signal }, FunnelReportSchema);
}

/** Session-level goal-completion analytics. */
export async function fetchSessions(signal?: AbortSignal, agent?: string): Promise<SessionReport> {
  return request(
    withScope("/observability/sessions", undefined, agent),
    { signal },
    SessionReportSchema,
  );
}

/** Step-by-step trajectory of a captured turn — session theater (#40/#113). */
export async function fetchTrajectory(bundleId: string, signal?: AbortSignal): Promise<Trajectory> {
  return request(
    `/observability/trajectory/${encodeURIComponent(bundleId)}`,
    { signal },
    TrajectorySchema,
  );
}

/** Golden-trace snapshot diff of executed-node shapes across turns (#41). */
export async function fetchTraceSnapshot(signal?: AbortSignal): Promise<SnapshotDiffReport> {
  return request("/observability/trace-snapshot", { signal }, SnapshotDiffReportSchema);
}

/** Captured production turns available for regression replay. */
export async function fetchReplays(signal?: AbortSignal): Promise<ReplaysResponse> {
  return request("/observability/replays", { signal }, ReplaysResponseSchema);
}

/** Screen a captured turn's retrieved chunks for indirect injection (#52). */
export async function fetchCorpusScan(
  bundleId: string,
  signal?: AbortSignal,
): Promise<CorpusScanReport> {
  return request(
    `/observability/corpus-scan/${encodeURIComponent(bundleId)}`,
    { signal },
    CorpusScanReportSchema,
  );
}

/** Detect hidden unicode (zero-width/bidi/tag) in a captured turn (#72). */
export async function fetchSteganography(
  bundleId: string,
  signal?: AbortSignal,
): Promise<StegoReport> {
  return request(
    `/observability/steganography/${encodeURIComponent(bundleId)}`,
    { signal },
    StegoReportSchema,
  );
}

/** Build a user-facing "why this answer" explanation from provenance (#133). */
export async function runWhy(bundleId: string): Promise<WhyExplanation> {
  return request(
    "/observability/why",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    WhyExplanationSchema,
  );
}

/** Claim-level provenance of a captured turn against its retrieved chunks. */
export async function fetchProvenance(
  bundleId: string,
  signal?: AbortSignal,
): Promise<ProvenanceReport> {
  return request(
    `/observability/provenance/${encodeURIComponent(bundleId)}`,
    { signal },
    ProvenanceReportSchema,
  );
}

/** Measure self-consistency / uncertainty of a captured turn (samples it N times). */
export async function runConsistency(bundleId: string, samples = 3): Promise<ConsistencyReport> {
  return request(
    "/observability/consistency",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId, samples }),
    },
    ConsistencyReportSchema,
  );
}

/** Measure robustness-under-noise of a captured turn (typos/homoglyphs/casing). */
export async function runRobustness(bundleId: string): Promise<RobustnessReport> {
  return request(
    "/observability/robustness",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    RobustnessReportSchema,
  );
}

/** Re-answer a captured turn in fr/de/en and measure cross-lingual agreement (#70). */
export async function runCrossLingual(bundleId: string): Promise<CrossLingualReport> {
  return request(
    "/observability/crosslingual",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    CrossLingualReportSchema,
  );
}

/** Measure how well a captured turn's chunks cover its question (#28). */
export async function runCoverage(bundleId: string): Promise<CoverageReport> {
  return request(
    "/observability/coverage",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    CoverageReportSchema,
  );
}

/** Decompose a captured turn's fused ordering into vector vs lexical shares (#27). */
export async function runReranking(bundleId: string): Promise<RerankContribution> {
  return request(
    "/observability/reranking",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    RerankContributionSchema,
  );
}

/** Re-answer a captured turn under no-RAG / no-rerank ablations, re-judge (#81). */
export async function runAblation(bundleId: string): Promise<AblationReport> {
  return request(
    "/observability/ablation",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    AblationReportSchema,
  );
}

/** Judge whether a captured turn sycophantically validates a false premise (#59). */
export async function runSycophancy(bundleId: string): Promise<SycophancyReport> {
  return request(
    "/observability/sycophancy",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    SycophancyReportSchema,
  );
}

/** Score a captured turn with a multi-judge ensemble; flags disagreement (#95). */
export async function runEnsemble(bundleId: string): Promise<EnsembleReport> {
  return request(
    "/observability/ensemble",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId }),
    },
    EnsembleReportSchema,
  );
}

/** Replay a captured turn against a candidate model and diff the result. */
export async function runReplay(bundleId: string, model: string): Promise<ReplayResult> {
  return request(
    "/observability/replay",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bundle_id: bundleId, model }),
    },
    ReplayResultSchema,
  );
}

/**
 * The /budget endpoint emits text/plain key/value lines. We parse it here so
 * callers see a typed snapshot.
 */
export async function fetchBudget(signal?: AbortSignal): Promise<BudgetSnapshot> {
  const response = await fetch(`${BASE}/budget`, {
    signal,
    headers: { Accept: "text/plain" },
  });
  if (!response.ok) {
    throw new ApiError("/budget failed", response.status, null);
  }
  const text = await response.text();
  const parsed = Object.fromEntries(
    text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, ...rest] = line.split(" ");
        return [key, rest.join(" ")];
      }),
  );
  return BudgetSnapshotSchema.parse({
    input_tokens: Number(parsed.input_tokens ?? 0),
    output_tokens: Number(parsed.output_tokens ?? 0),
    estimated_cost_eur: Number(parsed.estimated_cost_eur ?? 0),
  });
}

/** Point-in-time reconstruction ("Etat a date", prouver/etat-a-date). */
export async function fetchEtatADate(
  asOf: string | null,
  sources?: string | null,
  agent?: string | null,
  lang?: string,
  signal?: AbortSignal,
): Promise<EtatADate> {
  const params = new URLSearchParams();
  if (asOf) params.set("as_of", asOf);
  if (sources) params.set("sources", sources);
  if (agent) params.set("agent", agent);
  if (lang) params.set("lang", lang);
  const query = params.toString();
  return request(
    query ? `/observability/etat-a-date?${query}` : "/observability/etat-a-date",
    { signal },
    EtatADateSchema,
  );
}

/** Persist a reconstruction snapshot at T; returns the refreshed payload. */
export async function saveEtatSnapshot(
  asOf: string | null,
  sources?: string | null,
  agent?: string | null,
  lang?: string,
): Promise<EtatADate> {
  return request(
    "/observability/etat-a-date/snapshot",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        as_of: asOf,
        sources: sources ?? null,
        agent: agent ?? null,
        lang: lang ?? "fr",
      }),
    },
    EtatADateSchema,
  );
}

/** Agent overview ("Synthese de l'agent") dashboard (reference image 25). */
export async function fetchAgentSynthese(
  agentId: string,
  period: string,
  at?: string | null,
  signal?: AbortSignal,
): Promise<AgentSynthese> {
  const params = new URLSearchParams({ period, agent_id: agentId });
  if (at) params.set("at", at);
  return request(`/observability/agent-synthese?${params}`, { signal }, AgentSyntheseSchema);
}

export async function fetchAgentConsole(
  lang: string,
  agentId: string,
  signal?: AbortSignal,
): Promise<AgentConsole> {
  // ADR 0019 §I2 — the console is agent-scoped: the binding (and thus the payload shape)
  // is read from the agent named here, not the fleet default.
  const params = new URLSearchParams();
  if (lang) params.set("lang", lang);
  if (agentId) params.set("agent", agentId);
  const q = params.toString();
  return request(`/observability/agent-console${q ? `?${q}` : ""}`, { signal }, AgentConsoleSchema);
}

/**
 * ADR 0019 §I3 — send one operator test turn to an http-binding agent. Hits the Next BFF
 * proxy (which mints the operator assertion); the backend enforces operator + plane +
 * binding and audits the call. Returns the invocation outcome (a red verdict is data, not
 * a throw); auth/plane refusals throw ApiError.
 */
export type AgentInvokeBody =
  | { message: string }
  | { action: { capability_id: string; params: Record<string, unknown> } };

export async function invokeAgentTurn(
  agentId: string,
  body: AgentInvokeBody,
  signal?: AbortSignal,
): Promise<AgentInvokeOutcome> {
  return request(
    `/agents/${encodeURIComponent(agentId)}/invoke`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    },
    AgentInvokeOutcomeSchema,
  );
}

/** Sandbox console defaults: the live system prompt + toggleable guard categories. */
export async function fetchSandboxConfig(
  lang: string,
  signal?: AbortSignal,
): Promise<SandboxConfig> {
  return request(
    `/observability/sandbox-config?lang=${encodeURIComponent(lang)}`,
    { signal },
    SandboxConfigSchema,
  );
}

/** Read the persisted operator feedback (turn -> rating) for a conversation. */
export async function fetchConsoleFeedback(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ConsoleFeedback> {
  const query = new URLSearchParams({ conversation_id: conversationId }).toString();
  return request(
    `/observability/agent-console/feedback?${query}`,
    { signal },
    ConsoleFeedbackSchema,
  );
}

/** Persist (or toggle off) one chat turn's rating; returns the fresh map. */
export async function saveConsoleFeedback(
  conversationId: string,
  turn: number,
  rating: "up" | "down" | null,
): Promise<ConsoleFeedback> {
  return request(
    "/observability/agent-console/feedback",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, turn, rating }),
    },
    ConsoleFeedbackSchema,
  );
}

/**
 * A customer's 👍/👎 on an assistant reply (ADR 0041). Requires the conversation's signed
 * resume capability — the same token the widget holds from turn.start — forwarded as the
 * `X-Tessera-Resume-Token` header so the agent can bind the vote to this conversation.
 */
export async function submitCustomerFeedback(args: {
  conversationId: string;
  turnId: string;
  rating: "up" | "down";
  resumeToken: string;
}): Promise<CustomerFeedbackResponse> {
  return request(
    "/observability/customer-feedback",
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "X-Tessera-Resume-Token": args.resumeToken,
      },
      body: JSON.stringify({
        conversation_id: args.conversationId,
        turn_id: args.turnId,
        rating: args.rating,
      }),
    },
    CustomerFeedbackResponseSchema,
  );
}

export async function fetchAgentConfigurations(
  agentId: string,
  lang: string,
  signal?: AbortSignal,
): Promise<AgentConfigurations> {
  const q = `?agent_id=${encodeURIComponent(agentId)}${lang ? `&lang=${encodeURIComponent(lang)}` : ""}`;
  return request(`/observability/agent-configurations${q}`, { signal }, AgentConfigurationsSchema);
}

/** Persist editable agent-profile overrides; returns the refreshed payload. */
export async function saveAgentConfigurations(
  agentId: string,
  changes: Record<string, unknown>,
  lang: string,
): Promise<AgentConfigurations> {
  const q = `?agent_id=${encodeURIComponent(agentId)}`;
  return request(
    `/observability/agent-configurations/config${q}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ changes, lang }),
    },
    AgentConfigurationsSchema,
  );
}

export async function fetchAgentConnaissances(
  lang?: string,
  signal?: AbortSignal,
): Promise<AgentConnaissances> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/agent-connaissances${q}`, { signal }, AgentConnaissancesSchema);
}

/** Attach/detach/activate a knowledge source; returns the refreshed payload. */
export async function mutateConnaissancesSource(body: {
  key: string;
  attached?: boolean;
  active?: boolean;
  lang?: string;
}): Promise<AgentConnaissances> {
  const { lang, ...payload } = body;
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(
    `/observability/agent-connaissances/source-state${q}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
    AgentConnaissancesSchema,
  );
}

export async function fetchAgentAFaire(lang: string, signal?: AbortSignal): Promise<AgentAFaire> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/agent-a-faire${q}`, { signal }, AgentAFaireSchema);
}

/** Persist a status/assignee change for one A-faire item; returns the fresh payload. */
export async function mutateAFaireItem(body: {
  item_id: string;
  status?: string;
  assignee?: string;
  lang?: string;
}): Promise<AgentAFaire> {
  return request(
    "/observability/agent-a-faire/item-state",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    AgentAFaireSchema,
  );
}

export async function fetchAgentGardeFous(
  lang?: string,
  signal?: AbortSignal,
): Promise<AgentGardeFous> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/agent-garde-fous${q}`, { signal }, AgentGardeFousSchema);
}

/** Enable/disable a guard rule; returns the refreshed payload. */
export async function mutateGardeFousRule(body: {
  key: string;
  enabled: boolean;
  lang?: string;
}): Promise<AgentGardeFous> {
  const { lang, ...payload } = body;
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(
    `/observability/agent-garde-fous/rule-state${q}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
    AgentGardeFousSchema,
  );
}

export async function fetchAgentPrompts(
  agentId: string,
  lang?: string,
  signal?: AbortSignal,
): Promise<AgentPrompts> {
  const params = new URLSearchParams({ agent_id: agentId });
  if (lang) params.set("lang", lang);
  return request(`/observability/agent-prompts?${params}`, { signal }, AgentPromptsSchema);
}

// ADR 0037 — the governed overlay lifecycle (propose: operator; review: superadmin).
export async function proposePromptOverlay(
  agentId: string,
  text: string,
): Promise<PromptOverlayState> {
  return request(
    "/observability/agent-prompt-overlay/propose",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, text }),
    },
    PromptOverlayStateSchema,
  );
}

export async function reviewPromptOverlay(
  agentId: string,
  action: "approve" | "reject" | "revoke",
): Promise<PromptOverlayState> {
  return request(
    "/observability/agent-prompt-overlay/review",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, action }),
    },
    PromptOverlayStateSchema,
  );
}

export async function fetchAgentEvaluations(
  agentId: string,
  lang: string,
  signal?: AbortSignal,
): Promise<AgentEvaluations> {
  const q = `?agent_id=${encodeURIComponent(agentId)}${lang ? `&lang=${encodeURIComponent(lang)}` : ""}`;
  return request(`/observability/agent-evaluations${q}`, { signal }, AgentEvaluationsSchema);
}

export async function fetchAgentHistorique(
  agentId: string,
  lang: string,
  signal?: AbortSignal,
): Promise<AgentHistorique> {
  const q = `?agent_id=${encodeURIComponent(agentId)}${lang ? `&lang=${encodeURIComponent(lang)}` : ""}`;
  return request(`/observability/agent-historique${q}`, { signal }, AgentHistoriqueSchema);
}

/** An agent's recent conversations (business console "Récents"). */
export async function fetchConversations(
  agentId: string,
  limit = 30,
  signal?: AbortSignal,
): Promise<ConversationList> {
  const q = `?agent_id=${encodeURIComponent(agentId)}&limit=${limit}`;
  return request(`/observability/conversations${q}`, { signal }, ConversationListSchema);
}

/**
 * The persisted messages of one conversation (to RESUME it in the OPERATOR console).
 *
 * Subject-scoped: this is the operator's transcript read, and the agent requires a verified
 * operator assertion for it (audit 2026-07-12, F-4). A customer resuming their OWN chat must
 * use `fetchOwnTranscript` instead — it proves the grant with the signed capability the agent
 * minted for that browser, rather than merely knowing an id.
 */
export async function fetchConversationMessages(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ConversationMessages> {
  const q = `?conversation_id=${encodeURIComponent(conversationId)}`;
  return request(
    `/observability/conversation-messages${q}`,
    { signal },
    ConversationMessagesSchema,
  );
}

/**
 * The caller's OWN conversation, replayed against the signed resume capability (F-4).
 *
 * The widget holds `{conversationId, resumeToken}`; the agent verifies that the token is the
 * one it minted for that conversation and refuses (403) otherwise — so a leaked id, on its
 * own, no longer reads a transcript. No operator assertion is involved: this is the customer
 * plane, which has no per-person identity to assert.
 */
export async function fetchOwnTranscript(
  conversationId: string,
  resumeToken: string,
  signal?: AbortSignal,
): Promise<OwnTranscript> {
  const q = `?conversation_id=${encodeURIComponent(conversationId)}`;
  return request(
    `/session/transcript${q}`,
    { signal, headers: { "X-Tessera-Resume-Token": resumeToken } },
    OwnTranscriptSchema,
  );
}

/** Conversation session detail (turn-by-turn, per-turn agent attribution). */
export async function fetchSessionDetail(
  conversationId: string,
  signal?: AbortSignal,
): Promise<SessionDetail> {
  const q = `?conversation_id=${encodeURIComponent(conversationId)}`;
  return request(`/observability/session-detail${q}`, { signal }, SessionDetailSchema);
}

/** Fleet rollup (per-agent observable KPIs + deduplicated org totals). */
export async function fetchFleet(signal?: AbortSignal): Promise<Fleet> {
  return request("/observability/fleet", { signal }, FleetSchema);
}

/** RBAC role × agent matrix (real roles × real registry agents). */
export async function fetchRbacMatrix(agent: string, signal?: AbortSignal): Promise<RbacMatrix> {
  const params = new URLSearchParams({ agent });
  return request(`/observability/rbac-matrix?${params}`, { signal }, RbacMatrixSchema);
}

/** CONFIGURER "used-by": consumer agents of each catalogue item of `kind`. */
export async function fetchCatalogueConsumers(
  kind: string,
  agent: string,
  lang: string,
  signal?: AbortSignal,
): Promise<CatalogueConsumers> {
  const params = new URLSearchParams({ kind, agent });
  if (lang) params.set("lang", lang);
  return request(
    `/observability/catalogue-consumers?${params}`,
    { signal },
    CatalogueConsumersSchema,
  );
}

export async function fetchModelCatalogue(
  lang: string,
  agent: string,
  signal?: AbortSignal,
): Promise<ModelCatalogue> {
  const params = new URLSearchParams({ lang, agent });
  return request(`/observability/model-catalogue?${params}`, { signal }, ModelCatalogueSchema);
}

export async function fetchGuardrailCatalogue(
  lang: string,
  agent: string,
  signal?: AbortSignal,
): Promise<GuardrailCatalogue> {
  const params = new URLSearchParams({ lang, agent });
  return request(
    `/observability/guardrail-catalogue?${params}`,
    { signal },
    GuardrailCatalogueSchema,
  );
}

/** Governed, audited proposal to add a new agent (registry is approved as a unit). */
export async function proposeAgent(
  name: string,
): Promise<{ available: boolean; proposed?: string }> {
  return request(
    "/observability/agents/propose",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name }),
    },
    ProposeAgentSchema,
  );
}

/** Attempt to promote an agent to live — gated server-side by its eval-gate. */
export async function requestAgentRelease(agentId: string): Promise<ReleaseAgent> {
  return request(
    "/observability/agents/release",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ agent_id: agentId }),
    },
    ReleaseAgentSchema,
  );
}

// ── Client space (Produit) ───────────────────────────────────────────────────

/** Customer documents, sourced from the real Crédit Aurore corpus (locale-aware). */
export async function fetchClientDocuments(
  locale: string,
  signal?: AbortSignal,
): Promise<ClientDocuments> {
  return request(
    `/observability/client/documents?locale=${encodeURIComponent(locale)}`,
    { signal },
    ClientDocumentsSchema,
  );
}

/** Customer support requests (escalation tickets). */
export async function fetchClientRequests(
  lang: string,
  signal?: AbortSignal,
): Promise<ClientRequests> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/client/requests${q}`, { signal }, ClientRequestsSchema);
}

/** Account alerts with the durable read-state applied. */
export async function fetchClientAlerts(lang: string, signal?: AbortSignal): Promise<ClientAlerts> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/client/alerts${q}`, { signal }, ClientAlertsSchema);
}

/** Persist one alert's read/unread state; returns the fresh alerts payload. */
export async function mutateClientAlert(body: {
  alert_id: string;
  read: boolean;
  lang: string;
}): Promise<ClientAlerts> {
  return request(
    "/observability/client/alerts/read",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    ClientAlertsSchema,
  );
}

/** Customer preferences (notifications, privacy/consent, security). */
export async function fetchClientSettings(
  lang: string,
  signal?: AbortSignal,
): Promise<ClientSettings> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/client/settings${q}`, { signal }, ClientSettingsSchema);
}

/** Persist one preference; returns the full settings payload. */
export async function mutateClientSetting(body: {
  key: string;
  value: boolean | string;
  lang: string;
}): Promise<ClientSettings> {
  return request(
    "/observability/client/settings",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    ClientSettingsSchema,
  );
}

// ── Connectors & Users (cockpit) ─────────────────────────────────────────────

/** Connectors overview for the real Tessera stack (configurer/connecteurs). */
export async function fetchConnectors(
  lang: string,
  signal?: AbortSignal,
): Promise<ConnectorsOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/connectors${q}`, { signal }, ConnectorsOverviewSchema);
}

/** Users overview from the real seeded operator accounts (admin/utilisateurs). */
export async function fetchUsers(lang: string, signal?: AbortSignal): Promise<UsersOverview> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/users${q}`, { signal }, UsersOverviewSchema);
}
