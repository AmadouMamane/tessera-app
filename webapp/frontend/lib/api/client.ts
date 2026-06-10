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
  type AnomalyReport,
  AnomalyReportSchema,
  type AuditIntegrity,
  AuditIntegritySchema,
  type AuditOutcome,
  type AuditPage,
  AuditPageSchema,
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
  type DisclosureReport,
  DisclosureReportSchema,
  type EnsembleReport,
  EnsembleReportSchema,
  type ErasureCoverage,
  ErasureCoverageSchema,
  type EvalScoresResponse,
  EvalScoresResponseSchema,
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
  type HealthResponse,
  HealthResponseSchema,
  type IntentReport,
  IntentReportSchema,
  type InventoryReport,
  InventoryReportSchema,
  type InversionReport,
  InversionReportSchema,
  type JourneyReport,
  JourneyReportSchema,
  type LocaleFormatSummary,
  LocaleFormatSummarySchema,
  type LocalizationReport,
  LocalizationReportSchema,
  type MemoryObsReport,
  MemoryObsReportSchema,
  type ObsCostReport,
  ObsCostReportSchema,
  type OverflowReport,
  OverflowReportSchema,
  type PIILeakSummary,
  PIILeakSummarySchema,
  type PlaybookReport,
  PlaybookReportSchema,
  type PredictorEvaluation,
  PredictorEvaluationSchema,
  type PrivilegeReport,
  PrivilegeReportSchema,
  type PropagationReport,
  PropagationReportSchema,
  type ProvenanceReport,
  ProvenanceReportSchema,
  type RedTeamResponse,
  RedTeamResponseSchema,
  type RefusalReport,
  RefusalReportSchema,
  type ReplayResult,
  ReplayResultSchema,
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
  type SFTDataset,
  SFTDatasetSchema,
  type SLOReport,
  SLOReportSchema,
  type SessionReport,
  SessionReportSchema,
  type ShadowReport,
  ShadowReportSchema,
  type SiemExport,
  SiemExportSchema,
  type SkewReport,
  SkewReportSchema,
  type StegoReport,
  StegoReportSchema,
  type SycophancyReport,
  SycophancyReportSchema,
  type TailSamplingReport,
  TailSamplingReportSchema,
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
  signal?: AbortSignal;
}

export async function fetchAudit(options: FetchAuditOptions = {}): Promise<AuditPage> {
  const params = new URLSearchParams();
  if (options.cursor != null) params.set("cursor", String(options.cursor));
  if (options.limit != null) params.set("limit", String(options.limit));
  if (options.target) params.set("target", options.target);
  if (options.outcome) params.set("outcome", options.outcome);
  const query = params.toString();
  return request(`/audit${query ? `?${query}` : ""}`, { signal: options.signal }, AuditPageSchema);
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

/** Recent online-eval scores (eval-as-telemetry; public aggregate surface). */
export async function fetchEvalScores(signal?: AbortSignal): Promise<EvalScoresResponse> {
  return request("/observability/scores", { signal }, EvalScoresResponseSchema);
}

/** Quality SLO + error-budget burn-rate over the recent faithfulness scores (#15). */
export async function fetchSLO(signal?: AbortSignal): Promise<SLOReport> {
  return request("/observability/slo", { signal }, SLOReportSchema);
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

/** EU AI Act compliance posture: transparency, oversight, traceability (#76). */
export async function fetchAIAct(signal?: AbortSignal): Promise<AIActReport> {
  return request("/observability/ai-act", { signal }, AIActReportSchema);
}

/** Per-locale message completeness vs the default locale (#77). */
export async function fetchLocalization(signal?: AbortSignal): Promise<LocalizationReport> {
  return request("/observability/localization", { signal }, LocalizationReportSchema);
}

/** Incident playbooks triggered by the current live signals (#115). */
export async function fetchPlaybooks(signal?: AbortSignal): Promise<PlaybookReport> {
  return request("/observability/playbooks", { signal }, PlaybookReportSchema);
}

/** Tool least-privilege: granted vs actually-used tools from the audit (#101). */
export async function fetchLeastPrivilege(signal?: AbortSignal): Promise<PrivilegeReport> {
  return request("/observability/least-privilege", { signal }, PrivilegeReportSchema);
}

/** Cross-tenant leakage: foreign subject ids in a turn's context (#74). */
export async function fetchCrossTenant(signal?: AbortSignal): Promise<CrossTenantReport> {
  return request("/observability/cross-tenant", { signal }, CrossTenantReportSchema);
}

/** Toxicity / harmful-output rate over captured answers (#60). */
export async function fetchToxicity(signal?: AbortSignal): Promise<ToxicityReport> {
  return request("/observability/toxicity", { signal }, ToxicityReportSchema);
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

/** Cross-session customer journeys mined from the memory audit trail (#99). */
export async function fetchJourney(signal?: AbortSignal): Promise<JourneyReport> {
  return request("/observability/journey", { signal }, JourneyReportSchema);
}

/** Telemetry-mined product backlog: ranked roadmap items (#124). */
export async function fetchRoadmap(signal?: AbortSignal): Promise<RoadmapReport> {
  return request("/observability/roadmap", { signal }, RoadmapReportSchema);
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

/** Long-horizon faithfulness trend over the recent score series (#150). */
export async function fetchTrend(signal?: AbortSignal): Promise<TrendReport> {
  return request("/observability/trend", { signal }, TrendReportSchema);
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

/** Schema/format conformance of tool-call arguments from the audit trail (#47). */
export async function fetchConformance(signal?: AbortSignal): Promise<ConformanceReport> {
  return request("/observability/conformance", { signal }, ConformanceReportSchema);
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

/** Tool-call validity (allowed vs denied, argument failures) from the audit trail. */
export async function fetchToolValidity(signal?: AbortSignal): Promise<ToolValidity> {
  return request("/observability/tool-validity", { signal }, ToolValiditySchema);
}

/** Language-routing health: served vs detected language + code-switching. */
export async function fetchRouting(signal?: AbortSignal): Promise<RoutingReport> {
  return request("/observability/routing", { signal }, RoutingReportSchema);
}

/** Context truncation/overflow vs the input window across captured turns (#89). */
export async function fetchContextOverflow(signal?: AbortSignal): Promise<OverflowReport> {
  return request("/observability/context-overflow", { signal }, OverflowReportSchema);
}

/** Token-cost distribution and token-burn anomalies over captured turns (#33). */
export async function fetchCost(signal?: AbortSignal): Promise<CostReport> {
  return request("/observability/cost", { signal }, CostReportSchema);
}

/** Business-intent mix and routing confidence over captured questions (#63). */
export async function fetchIntent(signal?: AbortSignal): Promise<IntentReport> {
  return request("/observability/intent", { signal }, IntentReportSchema);
}

/** Refusal-rate calibration: over-refusal (legit) vs under-refusal (forbidden) (#58). */
export async function fetchRefusal(signal?: AbortSignal): Promise<RefusalReport> {
  return request("/observability/refusal", { signal }, RefusalReportSchema);
}

/** Anomalous-conversation detection: long/looping/repetitive sessions (#69). */
export async function fetchAnomalies(signal?: AbortSignal): Promise<AnomalyReport> {
  return request("/observability/anomalies", { signal }, AnomalyReportSchema);
}

/** Root-cause "what changed": lineage diff + attribution of a score delta (#17). */
export async function fetchWhatChanged(signal?: AbortSignal): Promise<WhatChanged> {
  return request("/observability/what-changed", { signal }, WhatChangedSchema);
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

/** Output PII-leak rate: PII in answers absent from their grounding (#38). */
export async function fetchPiiLeak(signal?: AbortSignal): Promise<PIILeakSummary> {
  return request("/observability/pii-leak", { signal }, PIILeakSummarySchema);
}

/** Per-language conversation funnel from scored turns (#66). */
export async function fetchFunnel(signal?: AbortSignal): Promise<FunnelReport> {
  return request("/observability/funnel", { signal }, FunnelReportSchema);
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
