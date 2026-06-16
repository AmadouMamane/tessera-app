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
  type Calibration,
  CalibrationSchema,
  type CitationResolution,
  CitationResolutionSchema,
  type CitationSummary,
  CitationSummarySchema,
  type ClusterReport,
  ClusterReportSchema,
  type ComplianceReport,
  ComplianceReportSchema,
  type ConformanceReport,
  ConformanceReportSchema,
  type ConsistencyReport,
  ConsistencyReportSchema,
  type ContradictionReport,
  ContradictionReportSchema,
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
  type DisclosureReport,
  DisclosureReportSchema,
  type EnsembleReport,
  EnsembleReportSchema,
  type ErasureCoverage,
  ErasureCoverageSchema,
  type EvalScoresResponse,
  EvalScoresResponseSchema,
  type FailedCasesReport,
  FailedCasesReportSchema,
  type FailedRunsReport,
  FailedRunsReportSchema,
  type FirewallEfficacy,
  FirewallEfficacySchema,
  type FreshnessReport,
  FreshnessReportSchema,
  type FunnelReport,
  FunnelReportSchema,
  type GraphTopology,
  GraphTopologySchema,
  type GuardExplainReport,
  GuardExplainReportSchema,
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
  type ModelComparison,
  ModelComparisonSchema,
  type ObsCostReport,
  ObsCostReportSchema,
  type OverflowReport,
  OverflowReportSchema,
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
  type ProofsOverview,
  ProofsOverviewSchema,
  type PropagationReport,
  PropagationReportSchema,
  type ProvenanceReport,
  ProvenanceReportSchema,
  type QualityDatasetsReport,
  QualityDatasetsReportSchema,
  type RedTeamResponse,
  RedTeamResponseSchema,
  type RefusalReport,
  RefusalReportSchema,
  type RegressionRisk,
  RegressionRiskSchema,
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
  type ScoreSeries,
  ScoreSeriesSchema,
  type SessionReport,
  SessionReportSchema,
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
  type Trajectory,
  TrajectorySchema,
  type TrendReport,
  TrendReportSchema,
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

export async function fetchAuditIntegrity(signal?: AbortSignal): Promise<AuditIntegrity> {
  return request("/audit/integrity", { signal }, AuditIntegritySchema);
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
 * Recent online-eval scores (eval-as-telemetry; public aggregate surface).
 *
 * With `at` set, the durable score log is read as of that instant (ADR 0011).
 */
export async function fetchEvalScores(
  signal?: AbortSignal,
  at?: string,
): Promise<EvalScoresResponse> {
  return request(withAsOf("/observability/scores", at), { signal }, EvalScoresResponseSchema);
}

/** Temporal lineage timeline — dated events for the cockpit time rail (#201). */
export async function fetchTimeline(signal?: AbortSignal, at?: string): Promise<TimelineReport> {
  return request(withAsOf("/observability/timeline", at), { signal }, TimelineReportSchema);
}

/**
 * Quality SLO + error-budget burn-rate over the faithfulness scores (#15).
 *
 * With `at` set, the SLO is recomputed over the durable log as of T (ADR 0011).
 */
export async function fetchSLO(signal?: AbortSignal, at?: string): Promise<SLOReport> {
  return request(withAsOf("/observability/slo", at), { signal }, SLOReportSchema);
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
export async function fetchPlaybooks(signal?: AbortSignal, at?: string): Promise<PlaybookReport> {
  return request(withAsOf("/observability/playbooks", at), { signal }, PlaybookReportSchema);
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
export async function fetchToxicity(signal?: AbortSignal, at?: string): Promise<ToxicityReport> {
  return request(withAsOf("/observability/toxicity", at), { signal }, ToxicityReportSchema);
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
export async function fetchRoadmap(signal?: AbortSignal, at?: string): Promise<RoadmapReport> {
  return request(withAsOf("/observability/roadmap", at), { signal }, RoadmapReportSchema);
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
export async function fetchTrend(signal?: AbortSignal, at?: string): Promise<TrendReport> {
  return request(withAsOf("/observability/trend", at), { signal }, TrendReportSchema);
}

/** Calendar-time score series for one metric (Vue d'ensemble chart + metric KPIs). */
export async function fetchScoreSeries(
  signal?: AbortSignal,
  at?: string,
  metric?: string,
): Promise<ScoreSeries> {
  const params = new URLSearchParams();
  if (at) params.set("at", at);
  if (metric) params.set("metric", metric);
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
export async function fetchCompliance(signal?: AbortSignal): Promise<ComplianceReport> {
  return request("/observability/compliance", { signal }, ComplianceReportSchema);
}

/** Operational reliability & cost posture derived from the real signals (#08). */
export async function fetchReliability(
  signal?: AbortSignal,
  days = 14,
  anchor?: string | null,
): Promise<ReliabilityReport> {
  const qs = new URLSearchParams({ days: String(days) });
  if (anchor) qs.set("anchor", anchor);
  return request(`/observability/reliability?${qs}`, { signal }, ReliabilityReportSchema);
}

/** Continuous-improvement posture mined from the telemetry roadmap (#09). */
export async function fetchImprovement(signal?: AbortSignal): Promise<ImprovementReport> {
  return request("/observability/improvement", { signal }, ImprovementReportSchema);
}

export async function fetchIncidentsOverview(signal?: AbortSignal): Promise<IncidentsOverview> {
  return request("/observability/incidents", { signal }, IncidentsOverviewSchema);
}

export async function fetchReplayShadowOverview(
  signal?: AbortSignal,
): Promise<ReplayShadowOverview> {
  return request("/observability/replay-shadow", { signal }, ReplayShadowOverviewSchema);
}

export async function fetchCurationOverview(signal?: AbortSignal): Promise<CurationOverview> {
  return request("/observability/curation", { signal }, CurationOverviewSchema);
}

export async function fetchAutomationsOverview(signal?: AbortSignal): Promise<AutomationsOverview> {
  return request("/observability/automations", { signal }, AutomationsOverviewSchema);
}

export async function fetchProofsOverview(signal?: AbortSignal): Promise<ProofsOverview> {
  return request("/observability/proofs", { signal }, ProofsOverviewSchema);
}

export async function fetchSignalCatalogue(signal?: AbortSignal): Promise<SignalCatalogue> {
  return request("/observability/signal-catalogue", { signal }, SignalCatalogueSchema);
}

export async function fetchPoliciesOverview(signal?: AbortSignal): Promise<PoliciesOverview> {
  return request("/observability/policies", { signal }, PoliciesOverviewSchema);
}

export async function fetchSourcesOverview(signal?: AbortSignal): Promise<SourcesOverview> {
  return request("/observability/sources", { signal }, SourcesOverviewSchema);
}

export async function fetchAccessOverview(signal?: AbortSignal): Promise<AccessOverview> {
  return request("/observability/access", { signal }, AccessOverviewSchema);
}

export async function fetchAssistantOverview(signal?: AbortSignal): Promise<AssistantOverview> {
  return request("/observability/assistant", { signal }, AssistantOverviewSchema);
}

export async function fetchIntegrationsOverview(
  signal?: AbortSignal,
): Promise<IntegrationsOverview> {
  return request("/observability/integrations", { signal }, IntegrationsOverviewSchema);
}

export async function fetchSystemProfile(signal?: AbortSignal): Promise<SystemProfile> {
  return request("/observability/system-profile", { signal }, SystemProfileSchema);
}

export async function fetchParametersOverview(signal?: AbortSignal): Promise<ParametersOverview> {
  return request("/observability/parameters", { signal }, ParametersOverviewSchema);
}

export async function fetchInboxOverview(signal?: AbortSignal): Promise<InboxOverview> {
  return request("/observability/inbox", { signal }, InboxOverviewSchema);
}

/** Schema/format conformance of tool-call arguments from the audit trail (#47), live or as of T. */
export async function fetchConformance(
  signal?: AbortSignal,
  at?: string,
): Promise<ConformanceReport> {
  return request(withAsOf("/observability/conformance", at), { signal }, ConformanceReportSchema);
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
export async function fetchToolValidity(signal?: AbortSignal, at?: string): Promise<ToolValidity> {
  return request(withAsOf("/observability/tool-validity", at), { signal }, ToolValiditySchema);
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
export async function fetchCost(signal?: AbortSignal, at?: string): Promise<CostReport> {
  return request(withAsOf("/observability/cost", at), { signal }, CostReportSchema);
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
export async function fetchAnomalies(signal?: AbortSignal, at?: string): Promise<AnomalyReport> {
  return request(withAsOf("/observability/anomalies", at), { signal }, AnomalyReportSchema);
}

/** Root-cause "what changed": lineage diff + attribution of a score delta (#17), live or as of T. */
export async function fetchWhatChanged(signal?: AbortSignal, at?: string): Promise<WhatChanged> {
  return request(withAsOf("/observability/what-changed", at), { signal }, WhatChangedSchema);
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
export async function fetchPiiLeak(signal?: AbortSignal, at?: string): Promise<PIILeakSummary> {
  return request(withAsOf("/observability/pii-leak", at), { signal }, PIILeakSummarySchema);
}

/** Per-language conversation funnel from scored turns (#66), live or as of T. */
export async function fetchFunnel(signal?: AbortSignal, at?: string): Promise<FunnelReport> {
  return request(withAsOf("/observability/funnel", at), { signal }, FunnelReportSchema);
}

/** Session-level goal-completion analytics. */
export async function fetchSessions(signal?: AbortSignal): Promise<SessionReport> {
  return request("/observability/sessions", { signal }, SessionReportSchema);
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

/** Agent overview ("Synthese de l'agent") dashboard (reference image 22). */
export async function fetchAgentSynthese(signal?: AbortSignal): Promise<AgentSynthese> {
  return request("/observability/agent-synthese", { signal }, AgentSyntheseSchema);
}

export async function fetchAgentConsole(signal?: AbortSignal): Promise<AgentConsole> {
  return request("/observability/agent-console", { signal }, AgentConsoleSchema);
}

export async function fetchAgentConfigurations(signal?: AbortSignal): Promise<AgentConfigurations> {
  return request("/observability/agent-configurations", { signal }, AgentConfigurationsSchema);
}

/** Persist editable agent-profile overrides; returns the refreshed payload. */
export async function saveAgentConfigurations(
  changes: Record<string, unknown>,
): Promise<AgentConfigurations> {
  return request(
    "/observability/agent-configurations/config",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ changes }),
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

export async function fetchAgentAFaire(signal?: AbortSignal): Promise<AgentAFaire> {
  return request("/observability/agent-a-faire", { signal }, AgentAFaireSchema);
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
  lang?: string,
  signal?: AbortSignal,
): Promise<AgentPrompts> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return request(`/observability/agent-prompts${q}`, { signal }, AgentPromptsSchema);
}

export async function fetchAgentEvaluations(signal?: AbortSignal): Promise<AgentEvaluations> {
  return request("/observability/agent-evaluations", { signal }, AgentEvaluationsSchema);
}

export async function fetchAgentHistorique(signal?: AbortSignal): Promise<AgentHistorique> {
  return request("/observability/agent-historique", { signal }, AgentHistoriqueSchema);
}
