/**
 * Zod schemas that mirror the FastAPI response shapes.
 *
 * The schemas are the single source of truth for runtime validation *and*
 * type inference: every fetcher in this module pipes the response through
 * the matching schema's `.parse()` so that downstream UI never has to
 * defensively check shape.
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

export const LocaleSchema = z.enum(["fr", "de", "en"]);
export type Locale = z.infer<typeof LocaleSchema>;

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export const ChatCitationSchema = z.object({
  source: z.string(),
  locator: z.string(),
  language: LocaleSchema,
  excerpt: z.string().default(""),
});
export type ChatCitation = z.infer<typeof ChatCitationSchema>;

export const ChatDebugSchema = z.object({
  quality: z
    .object({
      title: z.string(),
      badge: z.string(),
      badge_tone: z.string(),
      rows: z.array(
        z.object({ label: z.string(), value: z.string(), scale: z.string(), tone: z.string() }),
      ),
    })
    .optional(),
  sources: z
    .object({
      title: z.string(),
      cta: z.string(),
      rows: z.array(z.object({ label: z.string(), scope: z.string() })),
    })
    .optional(),
  tools: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({ name: z.string(), status: z.string(), tone: z.string(), latency: z.string() }),
      ),
    })
    .optional(),
  guardrails: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({ name: z.string(), status: z.string(), tone: z.string(), detail: z.string() }),
      ),
    })
    .optional(),
  trace: z
    .object({
      title: z.string(),
      cta: z.string(),
      rows: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
  tokens: z.number().int().nonnegative().optional(),
});
export type ChatDebug = z.infer<typeof ChatDebugSchema>;

export const ChatStartEventSchema = z.object({
  conversation_id: z.string().uuid(),
  turn_id: z.string().uuid(),
});

export const ChatEndEventSchema = z.object({
  conversation_id: z.string().uuid(),
  turn_id: z.string().uuid(),
  language: LocaleSchema,
  final_response: z.string(),
  needs_escalation: z.boolean(),
  confidence: z.number().min(0).max(1).nullable(),
  citations: z.array(ChatCitationSchema),
  finish_reason: z.enum(["complete", "escalated", "error"]),
  debug: ChatDebugSchema.optional(),
});
export type ChatEndEvent = z.infer<typeof ChatEndEventSchema>;

export const ChatTokenEventSchema = z.object({
  token: z.string(),
});
export type ChatTokenEvent = z.infer<typeof ChatTokenEventSchema>;

export const ChatErrorEventSchema = z.object({
  error: z.string(),
});

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export const AuditOutcomeSchema = z.enum(["allowed", "denied", "error"]);
export type AuditOutcome = z.infer<typeof AuditOutcomeSchema>;
export const AuditEventTypeSchema = z.enum(["guard", "tool", "memory", "other"]);
export type AuditEventType = z.infer<typeof AuditEventTypeSchema>;
export const AuditActorRoleSchema = z.enum(["human", "service", "system", "model"]);
export type AuditActorRole = z.infer<typeof AuditActorRoleSchema>;

export const AuditDecisionSchema = z.object({
  target: z.string(),
  decision: z.enum(["allow", "deny", "transform"]),
  policy_rule: z.string(),
  rationale: z.string(),
  redactions: z.array(z.string()).default([]),
  occurred_at: z.string(),
});
export type AuditDecision = z.infer<typeof AuditDecisionSchema>;

export const AuditEntrySchema = z.object({
  occurred_at: z.string(),
  target: z.string(),
  outcome: AuditOutcomeSchema,
  model: z.string().nullable().optional(),
  arguments: z.record(z.string(), z.unknown()).default({}),
  decisions: z.array(AuditDecisionSchema).default([]),
  error: z.string().nullable().default(null),
  version: z.number().int().nullable().optional(),
  data_residency: z.string().nullable().optional(),
  prev_hash: z.string().nullable().optional(),
  hash: z.string().nullable().optional(),
  event_type: AuditEventTypeSchema.default("other"),
  actor: z.string().default("audit-log"),
  actor_role: AuditActorRoleSchema.default("system"),
  scope: z.string().default("global"),
  object_label: z.string().default("audit event"),
  policy_rule: z.string().nullable().optional(),
  proof_ref: z.string().nullable().optional(),
});
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

export const AuditPageSchema = z.object({
  entries: z.array(AuditEntrySchema),
  cursor: z.number().int().nonnegative(),
  has_more: z.boolean(),
});
export type AuditPage = z.infer<typeof AuditPageSchema>;

export const AuditIntegritySchema = z.object({
  verified: z.boolean(),
  length: z.number().int(),
  broken_at: z.number().int().nullable().default(null),
});
export type AuditIntegrity = z.infer<typeof AuditIntegritySchema>;

export const AuditCountSchema = z.object({
  key: z.string(),
  count: z.number().int(),
});
export type AuditCount = z.infer<typeof AuditCountSchema>;

export const AuditMetricSchema = z.object({
  key: z.enum([
    "signed_events",
    "sensitive_actions",
    "guard_refusals",
    "proof_events",
    "chain_integrity",
    "unique_actors",
  ]),
  value: z.number().int(),
  previous_value: z.number().int(),
  delta_pct: z.number().nullable().default(null),
});
export type AuditMetric = z.infer<typeof AuditMetricSchema>;

export const AuditTimelineBucketSchema = z.object({
  label: z.string(),
  start: z.string(),
  end: z.string(),
  total: z.number().int(),
  allowed: z.number().int(),
  denied: z.number().int(),
  error: z.number().int(),
});
export type AuditTimelineBucket = z.infer<typeof AuditTimelineBucketSchema>;

export const AuditProofSchema = z.object({
  occurred_at: z.string(),
  target: z.string(),
  outcome: AuditOutcomeSchema,
  actor: z.string(),
  hash: z.string(),
  prev_hash: z.string().nullable().optional(),
});
export type AuditProof = z.infer<typeof AuditProofSchema>;

export const AuditOverviewSchema = z.object({
  generated_at: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  total_events: z.number().int(),
  chain_verified: z.boolean(),
  chain_length: z.number().int(),
  chain_broken_at: z.number().int().nullable().default(null),
  metrics: z.array(AuditMetricSchema),
  timeline: z.array(AuditTimelineBucketSchema),
  targets: z.array(AuditCountSchema),
  outcomes: z.array(AuditCountSchema),
  policies: z.array(AuditCountSchema),
  actors: z.array(AuditCountSchema),
  roles: z.array(AuditCountSchema),
  scopes: z.array(AuditCountSchema),
  event_types: z.array(AuditCountSchema),
  recent_proofs: z.array(AuditProofSchema),
  suggested_filters: z.array(AuditCountSchema),
});
export type AuditOverview = z.infer<typeof AuditOverviewSchema>;

// ---------------------------------------------------------------------------
// Health + budget
// ---------------------------------------------------------------------------

export const HealthResponseSchema = z.object({
  status: z.string(),
  version: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const BudgetSnapshotSchema = z.object({
  input_tokens: z.number().int().nonnegative(),
  output_tokens: z.number().int().nonnegative(),
  estimated_cost_eur: z.number().nonnegative(),
});
export type BudgetSnapshot = z.infer<typeof BudgetSnapshotSchema>;

// ---------------------------------------------------------------------------
// Eval scorecard (read from a local JSON artefact, not from the backend)
// ---------------------------------------------------------------------------

export const ScorecardResultSchema = z.object({
  case_id: z.string(),
  language: LocaleSchema,
  passed: z.boolean(),
  reasons: z.array(z.string()).default([]),
  final_response: z.string(),
  needs_escalation: z.boolean(),
  invoked_tools: z.array(z.string()).default([]),
  category: z.string().default(""),
  title: z.string().default(""),
  expected_behavior: z.string().default(""),
});
export type ScorecardResult = z.infer<typeof ScorecardResultSchema>;

export const ScorecardSummarySchema = z.object({
  total: z.number().int(),
  passed: z.number().int(),
  failed: z.number().int(),
  pass_rate: z.number().min(0).max(1),
});
export type ScorecardSummary = z.infer<typeof ScorecardSummarySchema>;

// Qualitative failure synthesis (a "weakness map"): failures grouped into
// interpretive families with a one-line root-cause `note` and an optional
// remediation `fix`. Authored by hand or, at run time, generated by a capable
// model (--synthesis-model). When `fix` is absent the UI falls back to a static
// per-category remediation baseline. Superadmin-only.
export const SynthesisFamilySchema = z.object({
  label: z.string(),
  case_ids: z.array(z.string()).default([]),
  note: z.string().default(""),
  fix: z.string().default(""),
});
export type SynthesisFamily = z.infer<typeof SynthesisFamilySchema>;

export const SynthesisSchema = z.object({
  model: z.string().nullable().optional(),
  families: z.array(SynthesisFamilySchema).default([]),
});
export type Synthesis = z.infer<typeof SynthesisSchema>;

// Eval-run LLM cost (tokens + indicative EUR), recorded by the runner from an
// isolated budget tracker. Distinct from the live agent's *prod* /budget — this
// is the *eval* budget, persisted in the report. Admin-only in the UI.
export const RunCostSchema = z.object({
  input_tokens: z.number().default(0),
  output_tokens: z.number().default(0),
  estimated_cost_eur: z.number().default(0),
});
export type RunCost = z.infer<typeof RunCostSchema>;

export const ScorecardDocumentSchema = z.object({
  run_at: z.string().optional(),
  lang: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  catalogue_version: z.string().nullable().optional(),
  summary: ScorecardSummarySchema,
  results: z.array(ScorecardResultSchema),
  synthesis: SynthesisSchema.nullable().optional(),
  cost: RunCostSchema.nullable().optional(),
});
export type ScorecardDocument = z.infer<typeof ScorecardDocumentSchema>;

export const RunMetaSchema = z.object({
  filename: z.string(),
  run_at: z.string(),
  lang: z.string().nullable(),
  model: z.string().nullable().optional(),
  catalogue_version: z.string().nullable().optional(),
  summary: ScorecardSummarySchema,
  cost: RunCostSchema.nullable().optional(),
});
export type RunMeta = z.infer<typeof RunMetaSchema>;

// ---------------------------------------------------------------------------
// Observability — live online-eval scores (eval-as-telemetry, ADR 0010)
// ---------------------------------------------------------------------------

export const EvalScoreSchema = z.object({
  scored_at: z.string(),
  metric: z.string(),
  score: z.number(),
  language: z.string(),
  judge_model: z.string(),
  conversation_id: z.string().nullable().optional(),
  trace_id: z.string().nullable().optional(),
  sampled: z.boolean().default(false),
});
export type EvalScore = z.infer<typeof EvalScoreSchema>;

export const EvalScoresResponseSchema = z.object({
  scores: z.array(EvalScoreSchema),
});
export type EvalScoresResponse = z.infer<typeof EvalScoresResponseSchema>;

// Temporal control backbone (#201) — dated lineage events for the time rail.
export const TimelineEventSchema = z.object({
  at: z.string(),
  kind: z.enum(["score", "judge_change", "model_change", "guard_denial"]),
  label: z.string(),
  detail: z.string().default(""),
  tone: z.enum(["success", "warning", "danger", "info", "gold", "neutral"]).default("neutral"),
});
export type TimelineEvent = z.infer<typeof TimelineEventSchema>;

export const TimelineReportSchema = z.object({
  window_start: z.string(),
  window_end: z.string(),
  baseline_at: z.string(),
  n_events: z.number().int(),
  events: z.array(TimelineEventSchema),
});
export type TimelineReport = z.infer<typeof TimelineReportSchema>;

export const CalibrationPointSchema = z.object({
  question: z.string(),
  human_label: z.string(),
  judge_label: z.string(),
  judge_score: z.number(),
  length: z.number().int(),
  match: z.boolean(),
  case_id: z.string().optional(),
  language: z.string().optional(),
  category: z.string().optional(),
  segment: z.string().optional(),
  human_override: z.boolean().optional(),
});
export type CalibrationPoint = z.infer<typeof CalibrationPointSchema>;

export const GroupAgreementSchema = z.object({
  label: z.string(),
  n: z.number().int(),
  agreement: z.number(),
  kappa: z.number(),
  n_disagree: z.number().int(),
});
export type GroupAgreement = z.infer<typeof GroupAgreementSchema>;

export const CalibrationSchema = z.object({
  available: z.boolean(),
  n: z.number().int().optional(),
  kappa: z.number().optional(),
  agreement: z.number().optional(),
  mean_score_good: z.number().optional(),
  mean_score_bad: z.number().optional(),
  verbosity_corr: z.number().optional(),
  lenient: z.boolean().optional(),
  judge_model: z.string().optional(),
  points: z.array(CalibrationPointSchema).optional(),
  fp: z.number().int().optional(),
  fn: z.number().int().optional(),
  n_disagree: z.number().int().optional(),
  n_overrides: z.number().int().optional(),
  by_language: z.array(GroupAgreementSchema).optional(),
  by_category: z.array(GroupAgreementSchema).optional(),
  by_segment: z.array(GroupAgreementSchema).optional(),
  disagreement_by_category: z.record(z.string(), z.number()).optional(),
});
export type Calibration = z.infer<typeof CalibrationSchema>;

export const ReliabilityErrorSliceSchema = z.object({ label: z.string(), count: z.number().int() });
export const ReliabilityCostRowSchema = z.object({
  model: z.string(),
  provider: z.string(),
  n_requests: z.number().int(),
  cost_eur: z.number(),
  cost_per_1k: z.number(),
  pass_rate: z.number().nullable(),
  latency_ms: z.number().nullable(),
});
export const ReliabilityServiceRowSchema = z.object({
  name: z.string(),
  success: z.number(),
  latency_p50_ms: z.number(),
  n_requests: z.number().int(),
  mean_score: z.number(),
});
export const ReliabilityProviderRowSchema = z.object({
  provider: z.string(),
  n_requests: z.number().int(),
});
export const ReliabilityIncidentSchema = z.object({
  label: z.string(),
  type: z.string(),
  severity: z.string(),
  detail: z.string(),
  date: z.string().optional(),
  service: z.string().optional(),
});
export const ReliabilityDayPointSchema = z.object({
  date: z.string(),
  volume: z.number().int(),
  quality: z.number().nullable(),
  availability: z.number(),
  error_rate: z.number(),
  cost_eur: z.number(),
});
export const ReliabilityServiceCostRowSchema = z.object({
  name: z.string(),
  n_requests: z.number().int(),
  cost_eur: z.number(),
  cost_per_1k: z.number(),
  share: z.number(),
});
export const ReliabilityActionRowSchema = z.object({
  priority: z.number().int(),
  action: z.string(),
  impact: z.string(),
  complexity: z.string(),
});
export const ReliabilityReportSchema = z.object({
  available: z.boolean(),
  availability: z.number().optional(),
  error_rate: z.number().optional(),
  latency_p50_ms: z.number().optional(),
  latency_p95_ms: z.number().optional(),
  latency_p99_ms: z.number().optional(),
  tool_success: z.number().optional(),
  total_cost_eur: z.number().optional(),
  cost_per_request_eur: z.number().optional(),
  n_requests: z.number().int().optional(),
  total_tokens: z.number().int().optional(),
  cache_overhead_pct: z.number().optional(),
  within_budget: z.boolean().optional(),
  budget_monthly_eur: z.number().optional(),
  budget_spent_eur: z.number().optional(),
  budget_projected_eur: z.number().optional(),
  error_breakdown: z.array(ReliabilityErrorSliceSchema).optional(),
  models: z.array(ReliabilityCostRowSchema).optional(),
  services: z.array(ReliabilityServiceRowSchema).optional(),
  providers: z.array(ReliabilityProviderRowSchema).optional(),
  incidents: z.array(ReliabilityIncidentSchema).optional(),
  volume_series: z.array(z.number()).optional(),
  volume_delta: z.number().nullable().optional(),
  quality_series: z.array(z.number()).optional(),
  quality_delta: z.number().nullable().optional(),
  daily: z.array(ReliabilityDayPointSchema).optional(),
  services_cost: z.array(ReliabilityServiceCostRowSchema).optional(),
  actions: z.array(ReliabilityActionRowSchema).optional(),
  availability_delta: z.number().nullable().optional(),
  error_rate_delta: z.number().nullable().optional(),
  tool_success_delta: z.number().nullable().optional(),
  latency_p50_delta: z.number().nullable().optional(),
  cost_per_request_delta: z.number().nullable().optional(),
});
export type ReliabilityReport = z.infer<typeof ReliabilityReportSchema>;
export type ReliabilityDayPoint = z.infer<typeof ReliabilityDayPointSchema>;
export type ReliabilityServiceCostRow = z.infer<typeof ReliabilityServiceCostRowSchema>;
export type ReliabilityActionRow = z.infer<typeof ReliabilityActionRowSchema>;
export type ReliabilityCostRow = z.infer<typeof ReliabilityCostRowSchema>;
export type ReliabilityServiceRow = z.infer<typeof ReliabilityServiceRowSchema>;
export type ReliabilityIncident = z.infer<typeof ReliabilityIncidentSchema>;

export const OpportunitySchema = z.object({
  rank: z.number().int(),
  action: z.string(),
  cause: z.string(),
  gain_pts: z.number(),
  effort: z.string(),
  risk: z.string(),
  owner: z.string(),
  role: z.string(),
  status: z.string(),
  evidence: z.number().int(),
});
export type Opportunity = z.infer<typeof OpportunitySchema>;

export const ImprovementGateSchema = z.object({
  name: z.string(),
  value: z.string(),
  passed: z.boolean(),
});
export const ImprovementCandidateSchema = z.object({
  version: z.string(),
  label: z.string(),
  gates: z.array(ImprovementGateSchema),
});
export const ImprovementReportSchema = z.object({
  available: z.boolean(),
  potential_gain_pts: z.number().optional(),
  n_active_actions: z.number().int().optional(),
  n_to_curate: z.number().int().optional(),
  n_frozen_releases: z.number().int().optional(),
  n_shadow_candidates: z.number().int().optional(),
  eval_coverage: z.number().optional(),
  corpus_debt_days: z.number().int().optional(),
  roi_pct: z.number().optional(),
  opportunities: z.array(OpportunitySchema).optional(),
  causes: z.record(z.string(), z.number()).optional(),
  candidate: ImprovementCandidateSchema.nullable().optional(),
  current_version: z.string().optional(),
});
export type ImprovementReport = z.infer<typeof ImprovementReportSchema>;

export const ComplianceControlSchema = z.object({
  id: z.string(),
  name: z.string(),
  framework: z.string(),
  signal: z.string(),
  status: z.string(),
  value: z.number(),
  risk: z.string(),
  owner: z.string(),
  evidence_id: z.string(),
});
export type ComplianceControl = z.infer<typeof ComplianceControlSchema>;

export const ComplianceFrameworkSchema = z.object({
  code: z.string(),
  label: z.string(),
  score: z.number(),
  n_conformant: z.number().int(),
  n_partial: z.number().int(),
  n_non_conformant: z.number().int(),
  n_na: z.number().int(),
});
export type ComplianceFramework = z.infer<typeof ComplianceFrameworkSchema>;

export const ComplianceObligationSchema = z.object({
  name: z.string(),
  framework: z.string(),
  article: z.string(),
  status: z.string(),
  due: z.string(),
  owner: z.string(),
});
export type ComplianceObligation = z.infer<typeof ComplianceObligationSchema>;

export const NonConformitySchema = z.object({
  id: z.string(),
  title: z.string(),
  framework: z.string(),
  severity: z.string(),
  status: z.string(),
});
export type NonConformity = z.infer<typeof NonConformitySchema>;

// --- Conformite command-bar tabs (generic catalogue shape) ---------------

export const TabKpiSchema = z.object({
  label: z.string(),
  value: z.string(),
  unit: z.string().nullable().optional(),
  sub: z.string().nullable().optional(),
  delta: z.string().nullable().optional(),
  delta_good: z.boolean().nullable().optional(),
  tone: z.string().nullable().optional(),
});
export type TabKpi = z.infer<typeof TabKpiSchema>;

export const TabColumnSchema = z.object({
  key: z.string(),
  label: z.string(),
  kind: z.string(),
  align: z.string(),
});
export type TabColumn = z.infer<typeof TabColumnSchema>;

export const TabRowSchema = z.object({
  id: z.string(),
  cells: z.record(z.string(), z.unknown()),
});
export type TabRow = z.infer<typeof TabRowSchema>;

export const DetailFieldSchema = z.object({
  label: z.string(),
  value: z.string(),
  tone: z.string().nullable().optional(),
});

export const DetailListSchema = z.object({
  title: z.string(),
  items: z.array(z.record(z.string(), z.unknown())),
});

export const TabDetailSchema = z.object({
  eyebrow: z.string(),
  title: z.string(),
  status_label: z.string().nullable().optional(),
  status_tone: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  fields: z.array(DetailFieldSchema),
  lists: z.array(DetailListSchema),
  actions: z.array(z.string()),
});
export type TabDetail = z.infer<typeof TabDetailSchema>;

export const SectionItemSchema = z.object({
  label: z.string(),
  sub: z.string().nullable().optional(),
  value: z.string().nullable().optional(),
  badge: z.string().nullable().optional(),
  badge_tone: z.string().nullable().optional(),
});
export type SectionItem = z.infer<typeof SectionItemSchema>;

export const TabSectionSchema = z.object({
  title: z.string(),
  kind: z.string(),
  items: z.array(SectionItemSchema),
  cta: z.string().nullable().optional(),
  donut_value: z.number().nullable().optional(),
  donut_label: z.string().nullable().optional(),
  bars: z.array(z.record(z.string(), z.unknown())),
  series: z.array(z.record(z.string(), z.unknown())),
  actions: z.array(z.string()),
});
export type TabSection = z.infer<typeof TabSectionSchema>;

export const CatalogTabSchema = z.object({
  table_title: z.string(),
  kpis: z.array(TabKpiSchema),
  columns: z.array(TabColumnSchema),
  rows: z.array(TabRowSchema),
  detail: TabDetailSchema.nullable().optional(),
  sections: z.array(TabSectionSchema),
});
export type CatalogTab = z.infer<typeof CatalogTabSchema>;

export const ComplianceReportSchema = z.object({
  available: z.boolean(),
  score: z.number().int().optional(),
  n_obligations: z.number().int().optional(),
  n_applied: z.number().int().optional(),
  n_controls: z.number().int().optional(),
  n_conformant: z.number().int().optional(),
  n_partial: z.number().int().optional(),
  n_non_conformant: z.number().int().optional(),
  n_residual_risk: z.number().int().optional(),
  n_critical_deadlines: z.number().int().optional(),
  evidence_valid: z.number().int().optional(),
  evidence_missing: z.number().int().optional(),
  evidence_blocking: z.number().int().optional(),
  evidence_completeness: z.number().optional(),
  frameworks: z.array(ComplianceFrameworkSchema).optional(),
  controls: z.array(ComplianceControlSchema).optional(),
  obligations: z.array(ComplianceObligationSchema).optional(),
  non_conformities: z.array(NonConformitySchema).optional(),
  score_series: z.array(z.number()).optional(),
  score_delta: z.number().nullable().optional(),
  tabs: z.record(z.string(), CatalogTabSchema).optional(),
});
export type ComplianceReport = z.infer<typeof ComplianceReportSchema>;

export const LineageSchema = z.object({
  model: z.string(),
  prompt_version: z.string(),
  guard_policy_version: z.string(),
  doc_sources: z.array(z.string()),
});
export type Lineage = z.infer<typeof LineageSchema>;

export const ReplayBundleSchema = z.object({
  bundle_id: z.string(),
  captured_at: z.string(),
  conversation_id: z.string().nullable().optional(),
  language: z.string(),
  question: z.string(),
  context: z.string(),
  original_answer: z.string(),
  original_model: z.string(),
  original_score: z.number(),
  lineage: LineageSchema.nullable().optional(),
  latency_ms: z.record(z.string(), z.number()).nullable().optional(),
});
export type ReplayBundle = z.infer<typeof ReplayBundleSchema>;

export const ReplaysResponseSchema = z.object({
  bundles: z.array(ReplayBundleSchema),
});
export type ReplaysResponse = z.infer<typeof ReplaysResponseSchema>;

export const ReplayResultSchema = z.object({
  bundle_id: z.string(),
  original_model: z.string(),
  original_score: z.number(),
  candidate_model: z.string(),
  candidate_answer: z.string(),
  candidate_score: z.number(),
  score_delta: z.number(),
  similarity: z.number(),
});
export type ReplayResult = z.infer<typeof ReplayResultSchema>;

export const ProvenanceClaimSchema = z.object({
  text: z.string(),
  support: z.number(),
  supported: z.boolean(),
  best_chunk: z.number().int(),
});
export type ProvenanceClaim = z.infer<typeof ProvenanceClaimSchema>;

export const UtilizationSchema = z.object({
  n_chunks: z.number().int(),
  used_chunks: z.number().int(),
  dead_chunks: z.number().int(),
  utilization: z.number(),
  used_indices: z.array(z.number().int()),
});
export type Utilization = z.infer<typeof UtilizationSchema>;

export const ProvenanceReportSchema = z.object({
  n_claims: z.number().int(),
  grounded_fraction: z.number(),
  claims: z.array(ProvenanceClaimSchema),
  utilization: UtilizationSchema.optional(),
});
export type ProvenanceReport = z.infer<typeof ProvenanceReportSchema>;

export const ConsistencyReportSchema = z.object({
  samples: z.number().int(),
  consistency: z.number(),
  uncertainty: z.number(),
  answers: z.array(z.string()),
});
export type ConsistencyReport = z.infer<typeof ConsistencyReportSchema>;

export const JudgeScoreSchema = z.object({
  model: z.string(),
  score: z.number(),
  rationale: z.string(),
});

export const EnsembleReportSchema = z.object({
  metric: z.string(),
  mean_score: z.number(),
  max_spread: z.number(),
  agreement: z.number(),
  disagreement: z.boolean(),
  scores: z.array(JudgeScoreSchema),
});
export type EnsembleReport = z.infer<typeof EnsembleReportSchema>;

export const CoverageReportSchema = z.object({
  n_chunks: z.number().int(),
  max_similarity: z.number(),
  mean_similarity: z.number(),
  covered: z.boolean(),
  similarities: z.array(z.number()),
});
export type CoverageReport = z.infer<typeof CoverageReportSchema>;

export const RerankContributionSchema = z.object({
  n_chunks: z.number().int(),
  top_k: z.number().int(),
  reranker_lift: z.number().int(),
  top1_changed: z.boolean(),
  mean_vector_share: z.number(),
  mean_lexical_share: z.number(),
  vector_order: z.array(z.number().int()),
  fused_order: z.array(z.number().int()),
});
export type RerankContribution = z.infer<typeof RerankContributionSchema>;

export const AblationLayerSchema = z.object({
  layer: z.string(),
  score: z.number(),
  worth: z.number(),
});

export const AblationReportSchema = z.object({
  baseline: z.number(),
  model: z.string(),
  n_chunks: z.number().int(),
  layers: z.array(AblationLayerSchema),
});
export type AblationReport = z.infer<typeof AblationReportSchema>;

export const ClaimExplanationSchema = z.object({
  claim: z.string(),
  supported: z.boolean(),
  support: z.number(),
  source: z.string(),
});

export const WhyExplanationSchema = z.object({
  n_claims: z.number().int(),
  grounded_fraction: z.number(),
  confidence: z.number(),
  fully_grounded: z.boolean(),
  claims: z.array(ClaimExplanationSchema),
});
export type WhyExplanation = z.infer<typeof WhyExplanationSchema>;

export const SycophancyReportSchema = z.object({
  score: z.number(),
  sycophantic: z.boolean(),
  rationale: z.string(),
  judge_model: z.string(),
});
export type SycophancyReport = z.infer<typeof SycophancyReportSchema>;

export const CrossLingualReportSchema = z.object({
  languages: z.array(z.string()),
  consistency: z.number(),
  min_similarity: z.number(),
  consistent: z.boolean(),
  answers: z.record(z.string(), z.string()),
});
export type CrossLingualReport = z.infer<typeof CrossLingualReportSchema>;

export const PerturbationResultSchema = z.object({
  kind: z.string(),
  perturbed_question: z.string(),
  similarity: z.number(),
  faithfulness: z.number(),
});

export const RobustnessReportSchema = z.object({
  baseline_faithfulness: z.number(),
  mean_similarity: z.number(),
  min_faithfulness: z.number(),
  results: z.array(PerturbationResultSchema),
});
export type RobustnessReport = z.infer<typeof RobustnessReportSchema>;

export const SessionReportSchema = z.object({
  n_sessions: z.number().int(),
  total_turns: z.number().int(),
  mean_turns_per_session: z.number(),
  single_turn_rate: z.number(),
  mean_score: z.number(),
});
export type SessionReport = z.infer<typeof SessionReportSchema>;

export const RoutingReportSchema = z.object({
  n: z.number().int(),
  mismatches: z.number().int(),
  code_switches: z.number().int(),
  mismatch_rate: z.number(),
  code_switch_rate: z.number(),
});
export type RoutingReport = z.infer<typeof RoutingReportSchema>;

export const ToolValiditySchema = z.object({
  total: z.number().int(),
  allowed: z.number().int(),
  denied: z.number().int(),
  errored: z.number().int(),
  arg_failures: z.number().int(),
  validity_rate: z.number(),
});
export type ToolValidity = z.infer<typeof ToolValiditySchema>;

export const ChunkFindingSchema = z.object({
  index: z.number().int(),
  pattern: z.string(),
  snippet: z.string(),
});

export const CorpusScanReportSchema = z.object({
  n_chunks: z.number().int(),
  n_poisoned: z.number().int(),
  poison_rate: z.number(),
  findings: z.array(ChunkFindingSchema),
});
export type CorpusScanReport = z.infer<typeof CorpusScanReportSchema>;

export const StegoFindingSchema = z.object({
  codepoint: z.string(),
  category: z.string(),
  position: z.number().int(),
});

export const StegoReportSchema = z.object({
  n_hidden: z.number().int(),
  clean: z.boolean(),
  categories: z.record(z.string(), z.number().int()),
  decoded_tags: z.string(),
  findings: z.array(StegoFindingSchema),
});
export type StegoReport = z.infer<typeof StegoReportSchema>;

export const RedTeamSnapshotSchema = z.object({
  ran_at: z.string(),
  n_attacks: z.number().int(),
  n_blocked: z.number().int(),
  n_bypassed: z.number().int(),
  attack_success_rate: z.number(),
  bypassed_samples: z.array(z.string()),
});
export type RedTeamSnapshot = z.infer<typeof RedTeamSnapshotSchema>;

export const RedTeamResponseSchema = z.object({
  snapshots: z.array(RedTeamSnapshotSchema),
});
export type RedTeamResponse = z.infer<typeof RedTeamResponseSchema>;

export const ContradictionPairSchema = z.object({
  conversation_id: z.string(),
  i: z.number().int(),
  j: z.number().int(),
  topic_similarity: z.number(),
  answer_similarity: z.number(),
  question_i: z.string(),
  question_j: z.string(),
});

export const ContradictionReportSchema = z.object({
  n_sessions: z.number().int(),
  n_turns: z.number().int(),
  n_contradictions: z.number().int(),
  pairs: z.array(ContradictionPairSchema),
});
export type ContradictionReport = z.infer<typeof ContradictionReportSchema>;

export const FieldChangeSchema = z.object({
  field: z.string(),
  before: z.string(),
  after: z.string(),
});

export const WhatChangedSchema = z.object({
  available: z.boolean(),
  score_before: z.number().optional(),
  score_after: z.number().optional(),
  score_delta: z.number().optional(),
  regressed: z.boolean().optional(),
  changes: z.array(FieldChangeSchema).optional(),
  docs_added: z.array(z.string()).optional(),
  docs_removed: z.array(z.string()).optional(),
  attributed: z.boolean().optional(),
});
export type WhatChanged = z.infer<typeof WhatChangedSchema>;

export const SessionAnomalySchema = z.object({
  conversation_id: z.string(),
  n_turns: z.number().int(),
  repeated_pairs: z.number().int(),
  distinct_ratio: z.number(),
  anomalous: z.boolean(),
  reasons: z.array(z.string()),
});

export const AnomalyReportSchema = z.object({
  n_sessions: z.number().int(),
  n_anomalous: z.number().int(),
  sessions: z.array(SessionAnomalySchema),
});
export type AnomalyReport = z.infer<typeof AnomalyReportSchema>;

export const RefusalReportSchema = z.object({
  n_legit: z.number().int(),
  n_forbidden: z.number().int(),
  legit_refused: z.number().int(),
  forbidden_allowed: z.number().int(),
  over_refusal_rate: z.number(),
  under_refusal_rate: z.number(),
});
export type RefusalReport = z.infer<typeof RefusalReportSchema>;

export const TrajectoryStepSchema = z.object({
  index: z.number().int(),
  kind: z.string(),
  title: z.string(),
  detail: z.string(),
  duration_ms: z.number(),
  status: z.string(),
});

export const TrajectorySchema = z.object({
  bundle_id: z.string(),
  language: z.string(),
  model: z.string(),
  score: z.number(),
  total_ms: z.number(),
  n_steps: z.number().int(),
  steps: z.array(TrajectoryStepSchema),
});
export type Trajectory = z.infer<typeof TrajectorySchema>;
export type TrajectoryStep = z.infer<typeof TrajectoryStepSchema>;

export const CitationSummarySchema = z.object({
  n_turns: z.number().int(),
  n_citations: z.number().int(),
  n_unsupported: z.number().int(),
  validity_rate: z.number(),
  unsupported_examples: z.array(z.string()),
});
export type CitationSummary = z.infer<typeof CitationSummarySchema>;

export const LocaleFormatSummarySchema = z.object({
  n_turns: z.number().int(),
  n_amounts: z.number().int(),
  n_violations: z.number().int(),
  correctness_rate: z.number(),
  examples: z.array(z.string()),
});
export type LocaleFormatSummary = z.infer<typeof LocaleFormatSummarySchema>;

export const ConformanceReportSchema = z.object({
  n_calls: z.number().int(),
  n_fields_checked: z.number().int(),
  n_conformant: z.number().int(),
  n_violations: z.number().int(),
  conformance_rate: z.number(),
  violations: z.array(z.string()),
});
export type ConformanceReport = z.infer<typeof ConformanceReportSchema>;

export const IntentReportSchema = z.object({
  n: z.number().int(),
  distribution: z.record(z.string(), z.number().int()),
  unknown: z.number().int(),
  low_confidence: z.number().int(),
  low_confidence_rate: z.number(),
});
export type IntentReport = z.infer<typeof IntentReportSchema>;

export const TurnCostSchema = z.object({
  question: z.string(),
  tokens: z.number().int(),
  anomaly: z.boolean(),
});

export const CostReportSchema = z.object({
  n_turns: z.number().int(),
  total_tokens: z.number().int(),
  mean_tokens: z.number(),
  max_tokens: z.number().int(),
  threshold_tokens: z.number(),
  estimated_cost_eur: z.number(),
  n_anomalies: z.number().int(),
  anomalies: z.array(TurnCostSchema),
});
export type CostReport = z.infer<typeof CostReportSchema>;

export const RuleCountSchema = z.object({
  rule: z.string(),
  decision: z.string(),
  count: z.number().int(),
});

export const GuardExplainReportSchema = z.object({
  n_entries: z.number().int(),
  n_decisions: z.number().int(),
  n_denials: z.number().int(),
  rules: z.array(RuleCountSchema),
});
export type GuardExplainReport = z.infer<typeof GuardExplainReportSchema>;

export const LanguageFunnelSchema = z.object({
  language: z.string(),
  n_turns: z.number().int(),
  n_sessions: z.number().int(),
  mean_score: z.number(),
  single_turn_rate: z.number(),
  low_score_rate: z.number(),
});

export const FunnelReportSchema = z.object({
  n_turns: z.number().int(),
  languages: z.array(LanguageFunnelSchema),
});
export type FunnelReport = z.infer<typeof FunnelReportSchema>;

export const PIILeakSummarySchema = z.object({
  n_turns: z.number().int(),
  n_with_leak: z.number().int(),
  leak_rate: z.number(),
  total_leaked: z.number().int(),
  examples: z.array(z.string()),
});
export type PIILeakSummary = z.infer<typeof PIILeakSummarySchema>;

export const SLOReportSchema = z.object({
  metric: z.string(),
  threshold: z.number(),
  target: z.number(),
  n: z.number().int(),
  n_good: z.number().int(),
  n_bad: z.number().int(),
  good_rate: z.number(),
  error_budget: z.number(),
  budget_consumed: z.number(),
  budget_remaining: z.number(),
  burn_rate: z.number(),
  burn_rate_fast: z.number(),
  breaching: z.boolean(),
});
export type SLOReport = z.infer<typeof SLOReportSchema>;

export const SeriesBucketSchema = z.object({
  start: z.string(),
  n: z.number().int(),
  mean: z.number().nullable(),
});
export type SeriesBucket = z.infer<typeof SeriesBucketSchema>;

export const ScoreSeriesSchema = z.object({
  metric: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  n: z.number().int(),
  mean: z.number().nullable(),
  prev_mean: z.number().nullable(),
  delta: z.number().nullable(),
  buckets: z.array(SeriesBucketSchema),
});
export type ScoreSeries = z.infer<typeof ScoreSeriesSchema>;

export const JudgeDriftSchema = z.object({
  metric: z.string(),
  judge_model: z.string().nullable(),
  window_start: z.string(),
  window_end: z.string(),
  n: z.number().int(),
  mean: z.number().nullable(),
  divergence: z.number().nullable(),
  delta: z.number().nullable(),
  level: z.string(),
  buckets: z.array(SeriesBucketSchema),
  as_of: z.string().nullable().optional(),
});
export type JudgeDrift = z.infer<typeof JudgeDriftSchema>;

export const StatusBandSchema = z.object({
  counts: z.array(z.number().int()),
  current: z.number().int(),
  total: z.number().int(),
  delta: z.number().int().nullable(),
});
export const StatusCountsTrendSchema = z.object({
  metric: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  n_buckets: z.number().int(),
  active: StatusBandSchema,
  crit: StatusBandSchema,
  warn: StatusBandSchema,
  ok: StatusBandSchema,
  as_of: z.string().nullable().optional(),
});
export type StatusBand = z.infer<typeof StatusBandSchema>;
export type StatusCountsTrend = z.infer<typeof StatusCountsTrendSchema>;

export const RegressionRiskSchema = z.object({
  metric: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  n: z.number().int(),
  score_delta: z.number().nullable(),
  divergence: z.number().nullable(),
  regression_rate: z.number().nullable(),
  models_compared: z.number().int(),
  n_regressions: z.number().int(),
  score_component: z.number(),
  drift_component: z.number(),
  regression_component: z.number(),
  risk_score: z.number().nullable(),
  probability_7d: z.number().nullable(),
  level: z.string(),
  buckets_used: z.number().int(),
  as_of: z.string().nullable().optional(),
});
export type RegressionRisk = z.infer<typeof RegressionRiskSchema>;

export const JudgeAgreementSchema = z.object({
  judge_model: z.string(),
  agreement: z.number(),
});
export const JudgeConsensusSchema = z.object({
  available: z.boolean(),
  n_judges: z.number().int().optional(),
  n_cases: z.number().int().optional(),
  judge_models: z.array(z.string()).optional(),
  consensus_rate: z.number().optional(),
  mean_pairwise_agreement: z.number().optional(),
  fleiss_kappa: z.number().optional(),
  per_judge: z.array(JudgeAgreementSchema).optional(),
});
export type JudgeConsensus = z.infer<typeof JudgeConsensusSchema>;

export const MetricPointSchema = z.object({
  x: z.number(),
  y: z.number(),
  language: z.string(),
});
export const MetricPairsSchema = z.object({
  x_metric: z.string(),
  y_metric: z.string(),
  n: z.number().int(),
  points: z.array(MetricPointSchema),
});
export type MetricPairs = z.infer<typeof MetricPairsSchema>;

export const FailedCaseSchema = z.object({
  case_id: z.string(),
  title: z.string(),
  category: z.string(),
  severity: z.string(),
  language: z.string(),
  example: z.string(),
  expected: z.string(),
  tags: z.array(z.string()),
});
export type FailedCase = z.infer<typeof FailedCaseSchema>;

export const FailedCasesReportSchema = z.object({
  n: z.number().int(),
  cases: z.array(FailedCaseSchema),
  by_category: z.record(z.string(), z.number().int()),
  by_severity: z.record(z.string(), z.number().int()),
});
export type FailedCasesReport = z.infer<typeof FailedCasesReportSchema>;

export const RunSummarySchema = z.object({
  run_id: z.string(),
  run_at: z.string(),
  model: z.string(),
  language: z.string(),
  total: z.number().int(),
  passed: z.number().int(),
  failed: z.number().int(),
  pass_rate: z.number(),
  est_cost_eur: z.number().nullable(),
  mean_latency_ms: z.number().nullable(),
  catalogue_version: z.string().nullable(),
});
export type RunSummary = z.infer<typeof RunSummarySchema>;

export const RunRegistrySchema = z.object({
  n: z.number().int(),
  runs: z.array(RunSummarySchema),
  catalogue_cases: z.number().int(),
  catalogue_version: z.string().nullable(),
  models: z.array(z.string()),
  languages: z.array(z.string()),
});
export type RunRegistry = z.infer<typeof RunRegistrySchema>;

export const ModelStatSchema = z.object({
  model: z.string(),
  n_runs: z.number().int(),
  total_cases: z.number().int(),
  pass_rate: z.number(),
  est_cost_eur: z.number().nullable(),
  mean_latency_ms: z.number().nullable(),
  last_run_at: z.string(),
  verdict: z.string(),
  // Enrichments (image 04): judge metrics replayed per model (null until the
  // backfill runs), a pass-rate sparkline, and run-over-run non-regression.
  faithfulness: z.number().nullable().optional(),
  grounding: z.number().nullable().optional(),
  hallucination: z.number().nullable().optional(),
  evolution: z.array(z.number()).optional(),
  non_regression: z.number().nullable().optional(),
  categories: z.record(z.string(), z.number()).optional(),
});
export type ModelStat = z.infer<typeof ModelStatSchema>;

export const ModelComparisonSchema = z.object({
  models: z.array(ModelStatSchema),
  n_runs: z.number().int(),
  judge_model: z.string().nullable().optional(),
});
export type ModelComparison = z.infer<typeof ModelComparisonSchema>;

export const ReleaseSchema = z.object({
  version: z.string(),
  date: z.string().nullable(),
  added: z.number().int(),
  changed: z.number().int(),
  fixed: z.number().int(),
});
export type Release = z.infer<typeof ReleaseSchema>;

export const RegressionSchema = z.object({
  model: z.string(),
  prev_run_at: z.string(),
  last_run_at: z.string(),
  prev_rate: z.number(),
  last_rate: z.number(),
  delta: z.number(),
  total: z.number().int(),
});
export type Regression = z.infer<typeof RegressionSchema>;

export const ReleaseStatusSchema = z.object({
  current: ReleaseSchema.nullable(),
  releases: z.array(ReleaseSchema),
  regressions: z.array(RegressionSchema),
  n_regressions: z.number().int(),
  models_compared: z.number().int(),
  non_regression_rate: z.number(),
});
export type ReleaseStatus = z.infer<typeof ReleaseStatusSchema>;

export const ShadowComparisonSchema = z.object({
  question: z.string(),
  language: z.string(),
  original_score: z.number(),
  candidate_score: z.number(),
  score_delta: z.number(),
  similarity: z.number(),
  outcome: z.enum(["win", "loss", "tie"]),
});

export const ShadowReportSchema = z.object({
  candidate_model: z.string(),
  n_compared: z.number().int(),
  wins: z.number().int(),
  losses: z.number().int(),
  ties: z.number().int(),
  mean_delta: z.number(),
  mean_similarity: z.number(),
  mean_original_score: z.number(),
  mean_candidate_score: z.number(),
  comparisons: z.array(ShadowComparisonSchema),
});
export type ShadowReport = z.infer<typeof ShadowReportSchema>;

export const TailSamplingReportSchema = z.object({
  n_traces: z.number().int(),
  n_tail: z.number().int(),
  n_head: z.number().int(),
  n_kept: z.number().int(),
  n_dropped: z.number().int(),
  retention_rate: z.number(),
  tail_retention_rate: z.number(),
  base_rate: z.number(),
  n_slow: z.number().int(),
  n_low_score: z.number().int(),
  slow_threshold_ms: z.number(),
  score_threshold: z.number(),
});
export type TailSamplingReport = z.infer<typeof TailSamplingReportSchema>;

export const TrendBucketSchema = z.object({
  index: z.number().int(),
  n: z.number().int(),
  mean: z.number(),
});

export const TrendReportSchema = z.object({
  metric: z.string(),
  n: z.number().int(),
  slope: z.number(),
  direction: z.enum(["improving", "stable", "degrading"]),
  first_half_mean: z.number(),
  second_half_mean: z.number(),
  delta: z.number(),
  degrading: z.boolean(),
  buckets: z.array(TrendBucketSchema),
});
export type TrendReport = z.infer<typeof TrendReportSchema>;

export const ObsCostReportSchema = z.object({
  iterations: z.number().int(),
  span_overhead_us: z.number(),
  spans_per_turn: z.number().int(),
  overhead_per_turn_ms: z.number(),
  turn_budget_ms: z.number(),
  overhead_pct_of_budget: z.number(),
  est_bytes_per_span: z.number().int(),
  est_bytes_per_turn: z.number().int(),
  within_budget: z.boolean(),
});
export type ObsCostReport = z.infer<typeof ObsCostReportSchema>;

export const SkewReportSchema = z.object({
  query_model: z.string(),
  query_dimension: z.number().int(),
  corpus_model: z.string(),
  corpus_dimension: z.number().int(),
  dimension_mismatch: z.boolean(),
  model_mismatch: z.boolean(),
  skew: z.boolean(),
  severity: z.enum(["none", "soft", "hard"]),
  reason: z.string(),
});
export type SkewReport = z.infer<typeof SkewReportSchema>;

export const RegulationFreshnessSchema = z.object({
  name: z.string(),
  corpus: z.string(),
  n_docs: z.number().int(),
  age_days: z.number().int(),
  as_of: z.string().nullable(),
  stale: z.boolean(),
});

export const FreshnessReportSchema = z.object({
  n_corpora: z.number().int(),
  n_stale: z.number().int(),
  max_age_days: z.number().int(),
  oldest_age_days: z.number().int(),
  regulations: z.array(RegulationFreshnessSchema),
});
export type FreshnessReport = z.infer<typeof FreshnessReportSchema>;

export const QualityDatasetSchema = z.object({
  key: z.string(),
  cases: z.number().int(),
  languages: z.array(z.string()),
  version: z.string().nullable(),
  pass_rate: z.number().nullable(),
  drift: z.number().nullable(),
  coverage: z.number().nullable(),
  updated_at: z.string().nullable(),
  owner: z.string(),
});
export type QualityDataset = z.infer<typeof QualityDatasetSchema>;

export const PipelineStatusSchema = z.object({
  jobs_window: z.number().int(),
  runs_total: z.number().int(),
  data_freshness_seconds: z.number().nullable(),
  catalogue_coverage: z.number().nullable(),
  evidence_retention_days: z.number().int().nullable(),
  workers: z.number().int().nullable(),
  queue_depth: z.number().int().nullable(),
});
export type PipelineStatus = z.infer<typeof PipelineStatusSchema>;

export const QualityDatasetsReportSchema = z.object({
  n: z.number().int(),
  datasets: z.array(QualityDatasetSchema),
  catalogue_version: z.string().nullable(),
  total_cases: z.number().int(),
  languages: z.array(z.string()),
  monitored: z.number().int(),
  coverage_pct: z.number().nullable(),
  pipeline: PipelineStatusSchema,
});
export type QualityDatasetsReport = z.infer<typeof QualityDatasetsReportSchema>;

export const FailedRunCaseSchema = z.object({
  id: z.string(),
  category: z.string(),
  severity: z.string(),
  language: z.string(),
  title: z.string(),
  prompt: z.string(),
  expected: z.string(),
  response: z.string(),
  reasons: z.array(z.string()),
  model: z.string(),
  run_id: z.string(),
  run_at: z.string(),
  catalogue_version: z.string().nullable(),
  latency_ms: z.number().nullable(),
  owner: z.string(),
  status: z.string(),
});
export type FailedRunCase = z.infer<typeof FailedRunCaseSchema>;

export const FailedTrendPointSchema = z.object({
  date: z.string(),
  n: z.number().int(),
  by_severity: z.record(z.string(), z.number().int()),
});
export type FailedTrendPoint = z.infer<typeof FailedTrendPointSchema>;

export const FailedRunsReportSchema = z.object({
  n: z.number().int(),
  cases: z.array(FailedRunCaseSchema),
  by_category: z.record(z.string(), z.number().int()),
  by_severity: z.record(z.string(), z.number().int()),
  by_model: z.record(z.string(), z.number().int()),
  by_language: z.record(z.string(), z.number().int()),
  n_critical: z.number().int(),
  n_new: z.number().int(),
  n_recurrent: z.number().int(),
  trend: z.array(FailedTrendPointSchema),
  models: z.array(z.string()),
  languages: z.array(z.string()),
  catalogue_version: z.string().nullable(),
  mean_latency_ms: z.number().nullable(),
});
export type FailedRunsReport = z.infer<typeof FailedRunsReportSchema>;

export const RoadmapItemSchema = z.object({
  theme: z.string(),
  signal: z.string(),
  evidence: z.number().int(),
  severity: z.enum(["high", "medium", "low"]),
  suggestion: z.string(),
});

export const RoadmapReportSchema = z.object({
  n_turns: z.number().int(),
  n_items: z.number().int(),
  items: z.array(RoadmapItemSchema),
});
export type RoadmapReport = z.infer<typeof RoadmapReportSchema>;

export const MemoryObsReportSchema = z.object({
  n_actions: z.number().int(),
  n_writes: z.number().int(),
  writes_allowed: z.number().int(),
  writes_denied: z.number().int(),
  n_reads: z.number().int(),
  recall_hits: z.number().int(),
  recall_misses: z.number().int(),
  recall_hit_rate: z.number(),
  items_recalled: z.number().int(),
  items_screened_out: z.number().int(),
  n_forgets: z.number().int(),
});
export type MemoryObsReport = z.infer<typeof MemoryObsReportSchema>;

export const JourneySchema = z.object({
  subject: z.string(),
  n_sessions: z.number().int(),
  n_actions: z.number().int(),
  n_writes: z.number().int(),
  n_reads: z.number().int(),
  first_seen: z.string(),
  last_seen: z.string(),
  span_days: z.number(),
  returning: z.boolean(),
});

export const JourneyReportSchema = z.object({
  n_subjects: z.number().int(),
  n_returning: z.number().int(),
  n_events: z.number().int(),
  subjects: z.array(JourneySchema),
});
export type JourneyReport = z.infer<typeof JourneyReportSchema>;

export const InventorySampleSchema = z.object({
  memory_id: z.number().int(),
  subject: z.string(),
  kind: z.string(),
  preview: z.string(),
  expires_in_days: z.number().int(),
});

export const InventoryReportSchema = z.object({
  n_memories: z.number().int(),
  n_subjects: z.number().int(),
  by_kind: z.record(z.string(), z.number().int()),
  n_expiring_soon: z.number().int(),
  samples: z.array(InventorySampleSchema),
});
export type InventoryReport = z.infer<typeof InventoryReportSchema>;

export const ErasureCoverageSchema = z.object({
  n_conversations: z.number().int(),
  n_bundles: z.number().int(),
  n_scores: z.number().int(),
});
export type ErasureCoverage = z.infer<typeof ErasureCoverageSchema>;

export const InversionMatchSchema = z.object({
  memory: z.string(),
  probe: z.string(),
  cosine: z.number(),
  recoverable: z.boolean(),
});

export const InversionReportSchema = z.object({
  available: z.boolean().default(true),
  n_memories: z.number().int().optional(),
  n_recoverable: z.number().int().optional(),
  recovery_rate: z.number().optional(),
  threshold: z.number().optional(),
  matches: z.array(InversionMatchSchema).optional(),
});
export type InversionReport = z.infer<typeof InversionReportSchema>;

export const FailureClusterSchema = z.object({
  cluster_id: z.number().int(),
  size: z.number().int(),
  dominant_category: z.string(),
  purity: z.number(),
  categories: z.record(z.string(), z.number().int()),
  members: z.array(z.string()),
});

export const ClusterReportSchema = z.object({
  available: z.boolean().default(true),
  n_failures: z.number().int().optional(),
  k: z.number().int().optional(),
  mean_purity: z.number().optional(),
  clusters: z.array(FailureClusterSchema).optional(),
});
export type ClusterReport = z.infer<typeof ClusterReportSchema>;

export const PredictorEvaluationSchema = z.object({
  n: z.number().int(),
  n_predicted_fail: z.number().int(),
  n_actual_fail: z.number().int(),
  true_positive: z.number().int(),
  false_positive: z.number().int(),
  false_negative: z.number().int(),
  true_negative: z.number().int(),
  precision: z.number(),
  recall: z.number(),
});
export type PredictorEvaluation = z.infer<typeof PredictorEvaluationSchema>;

export const SFTRecordSchema = z.object({
  instruction: z.string(),
  input: z.string(),
  output: z.string(),
  language: z.string(),
  score: z.number(),
});

export const SFTDatasetSchema = z.object({
  n_total: z.number().int(),
  n_eligible: z.number().int(),
  min_score: z.number(),
  by_language: z.record(z.string(), z.number().int()),
  samples: z.array(SFTRecordSchema),
});
export type SFTDataset = z.infer<typeof SFTDatasetSchema>;

export const ToxicTurnSchema = z.object({
  question: z.string(),
  terms: z.array(z.string()),
});

export const ToxicityReportSchema = z.object({
  n_turns: z.number().int(),
  n_toxic: z.number().int(),
  toxicity_rate: z.number(),
  flagged: z.array(ToxicTurnSchema),
});
export type ToxicityReport = z.infer<typeof ToxicityReportSchema>;

export const CrossTenantLeakSchema = z.object({
  conversation_id: z.string(),
  foreign_ids: z.array(z.string()),
});

export const CrossTenantReportSchema = z.object({
  n_turns: z.number().int(),
  n_leaks: z.number().int(),
  leak_rate: z.number(),
  leaks: z.array(CrossTenantLeakSchema),
});
export type CrossTenantReport = z.infer<typeof CrossTenantReportSchema>;

export const ToolUsageSchema = z.object({
  tool: z.string(),
  used: z.number().int(),
});

export const PrivilegeReportSchema = z.object({
  n_granted: z.number().int(),
  n_used: z.number().int(),
  n_over_provisioned: z.number().int(),
  n_violations: z.number().int(),
  utilization_rate: z.number(),
  over_provisioned: z.array(z.string()),
  violations: z.array(z.string()),
  usage: z.array(ToolUsageSchema),
});
export type PrivilegeReport = z.infer<typeof PrivilegeReportSchema>;

export const PlaybookSchema = z.object({
  incident: z.string(),
  severity: z.enum(["critical", "high", "medium"]),
  trigger: z.string(),
  steps: z.array(z.string()),
});

export const PlaybookReportSchema = z.object({
  n_triggered: z.number().int(),
  playbooks: z.array(PlaybookSchema),
});
export type PlaybookReport = z.infer<typeof PlaybookReportSchema>;

export const SiemEventSchema = z.object({
  timestamp: z.string(),
  category: z.string(),
  action: z.string(),
  outcome: z.string(),
  severity: z.number().int(),
  actor: z.string(),
  message: z.string(),
});

export const SiemExportSchema = z.object({
  n_events: z.number().int(),
  n_high_severity: z.number().int(),
  by_category: z.record(z.string(), z.number().int()),
  events: z.array(SiemEventSchema),
});
export type SiemExport = z.infer<typeof SiemExportSchema>;

export const LocaleCompletenessSchema = z.object({
  locale: z.string(),
  n_keys: z.number().int(),
  n_missing: z.number().int(),
  completeness: z.number(),
  fallback_rate: z.number(),
  missing_sample: z.array(z.string()),
});

export const LocalizationReportSchema = z.object({
  default_locale: z.string(),
  n_default_keys: z.number().int(),
  locales: z.array(LocaleCompletenessSchema),
});
export type LocalizationReport = z.infer<typeof LocalizationReportSchema>;

export const ObligationSchema = z.object({
  name: z.string(),
  article: z.string(),
  satisfied: z.boolean(),
  evidence: z.string(),
});

export const AIActReportSchema = z.object({
  risk_class: z.string(),
  n_obligations: z.number().int(),
  n_satisfied: z.number().int(),
  compliance_rate: z.number(),
  obligations: z.array(ObligationSchema),
});
export type AIActReport = z.infer<typeof AIActReportSchema>;

export const CitationLinkSchema = z.object({
  citation: z.string(),
  resolved: z.boolean(),
  source: z.string().nullable(),
});

export const CitationResolutionSchema = z.object({
  n_citations: z.number().int(),
  n_resolved: z.number().int(),
  resolvable_rate: z.number(),
  links: z.array(CitationLinkSchema),
});
export type CitationResolution = z.infer<typeof CitationResolutionSchema>;

export const DisclosureReportSchema = z.object({
  enabled: z.boolean(),
  article: z.string(),
  n_locales: z.number().int(),
  all_covered: z.boolean(),
  missing_locales: z.array(z.string()),
  texts: z.record(z.string(), z.string()),
});
export type DisclosureReport = z.infer<typeof DisclosureReportSchema>;

export const TopologyDriftSchema = z.object({
  drifted: z.boolean(),
  fingerprint: z.string(),
  golden_fingerprint: z.string(),
  added_nodes: z.array(z.string()),
  removed_nodes: z.array(z.string()),
  added_edges: z.array(z.string()),
  removed_edges: z.array(z.string()),
  n_nodes: z.number().int(),
  n_edges: z.number().int(),
});

export const GraphTopologySchema = z.object({
  nodes: z.array(z.string()),
  edges: z.array(z.string()),
  n_nodes: z.number().int(),
  n_edges: z.number().int(),
  fingerprint: z.string(),
  drift: TopologyDriftSchema,
});
export type GraphTopology = z.infer<typeof GraphTopologySchema>;

export const ToolLoopSchema = z.object({
  stream: z.string(),
  kind: z.enum(["repeat", "oscillation"]),
  tools: z.array(z.string()),
  length: z.number().int(),
});

export const ToolLoopReportSchema = z.object({
  n_streams: z.number().int(),
  n_calls: z.number().int(),
  n_loops: z.number().int(),
  repeat_threshold: z.number().int(),
  loops: z.array(ToolLoopSchema),
});
export type ToolLoopReport = z.infer<typeof ToolLoopReportSchema>;

export const TurnOverflowSchema = z.object({
  question: z.string(),
  n_chunks: z.number().int(),
  context_tokens: z.number().int(),
  n_dropped: z.number().int(),
  overflowed: z.boolean(),
});

export const OverflowReportSchema = z.object({
  n_turns: z.number().int(),
  n_overflowed: z.number().int(),
  overflow_rate: z.number(),
  window_tokens: z.number().int(),
  usable_tokens: z.number().int(),
  max_context_tokens: z.number().int(),
  turns: z.array(TurnOverflowSchema),
});
export type OverflowReport = z.infer<typeof OverflowReportSchema>;

export const RetractionEventSchema = z.object({
  kind: z.enum(["injection_echo", "pii"]),
  tokens_before: z.number().int(),
  total_tokens: z.number().int(),
  exposure_rate: z.number(),
});

export const RetractionReportSchema = z.object({
  n_answers: z.number().int(),
  n_retractions: z.number().int(),
  retraction_rate: z.number(),
  max_tokens_exposed: z.number().int(),
  mean_tokens_exposed: z.number(),
  events: z.array(RetractionEventSchema),
});
export type RetractionReport = z.infer<typeof RetractionReportSchema>;

export const PropagationReportSchema = z.object({
  n_spans: z.number().int(),
  n_roots: z.number().int(),
  n_orphans: z.number().int(),
  max_fanout: z.number().int(),
  propagated_ok: z.boolean(),
  orphan_names: z.array(z.string()),
});
export type PropagationReport = z.infer<typeof PropagationReportSchema>;

export const DivergenceSchema = z.object({
  question: z.string(),
  n_runs: z.number().int(),
  n_variants: z.number().int(),
  shapes: z.array(z.string()),
});

export const ReproReportSchema = z.object({
  n_turns: z.number().int(),
  n_groups: z.number().int(),
  n_repeated_inputs: z.number().int(),
  n_nondeterministic: z.number().int(),
  divergences: z.array(DivergenceSchema),
});
export type ReproReport = z.infer<typeof ReproReportSchema>;

export const TurnSnapshotSchema = z.object({
  question: z.string(),
  executed: z.array(z.string()),
  unknown_nodes: z.array(z.string()),
  missing_required: z.array(z.string()),
  matches_golden: z.boolean(),
});

export const SnapshotDiffReportSchema = z.object({
  n_turns: z.number().int(),
  n_matching: z.number().int(),
  n_drifted: z.number().int(),
  known_nodes: z.array(z.string()),
  required_backbone: z.array(z.string()),
  drifts: z.array(TurnSnapshotSchema),
});
export type SnapshotDiffReport = z.infer<typeof SnapshotDiffReportSchema>;

export const HandoffTurnSchema = z.object({
  question: z.string(),
  n_handoffs: z.number().int(),
  n_broken: z.number().int(),
  broken: z.array(z.string()),
});

export const HandoffReportSchema = z.object({
  n_turns: z.number().int(),
  n_broken_turns: z.number().int(),
  total_handoffs: z.number().int(),
  total_broken: z.number().int(),
  broken_by_type: z.record(z.string(), z.number().int()),
  turns: z.array(HandoffTurnSchema),
});
export type HandoffReport = z.infer<typeof HandoffReportSchema>;

export const FirewallEfficacySchema = z.object({
  n_positive: z.number().int(),
  n_negative: z.number().int(),
  true_positive: z.number().int(),
  false_negative: z.number().int(),
  false_positive: z.number().int(),
  true_negative: z.number().int(),
  precision: z.number(),
  recall: z.number(),
  f1: z.number(),
});
export type FirewallEfficacy = z.infer<typeof FirewallEfficacySchema>;

// ---------------------------------------------------------------------------
// Incidents & playbooks (page #10)
// ---------------------------------------------------------------------------

const IncidentKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta_label: z.string(),
  good_is_up: z.boolean(),
  series: z.array(z.number()),
});

const PriorityIncidentSchema = z.object({
  id: z.string(),
  severity: z.enum(["critique", "eleve", "moyen"]),
  trigger: z.string(),
  domain: z.string(),
  status: z.enum(["ouvert", "encours", "resolu"]),
  owner: z.string(),
  sla: z.string(),
  sla_tone: z.enum(["crit", "warn", "ok"]),
  playbook: z.string(),
  role: z.string(),
});

const PlaybookCatalogItemSchema = z.object({
  name: z.string(),
  desc: z.string(),
  runs: z.number().int(),
});

const RecentIncidentSchema = z.object({
  id: z.string(),
  label: z.string(),
  severity: z.enum(["critique", "eleve", "moyen"]),
  time: z.string(),
});

const SlaEscalationSchema = z.object({
  id: z.string(),
  remaining: z.string(),
  tone: z.enum(["crit", "warn", "ok"]),
});

const DomainSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});

const ControlCaseSchema = z.object({
  id: z.string(),
  label: z.string(),
  assoc: z.number().int(),
});

const PlaybookStepSchema = z.object({
  key: z.string(),
  label: z.string(),
  time: z.string(),
  state: z.enum(["done", "current", "todo"]),
});

const RunningPlaybookSchema = z.object({
  name: z.string(),
  incident: z.string(),
  owner: z.string(),
  role: z.string(),
  proofs: z.number().int(),
  elapsed: z.string(),
  steps: z.array(PlaybookStepSchema),
});

const ResponseJournalRowSchema = z.object({
  time: z.string(),
  incident: z.string(),
  action: z.string(),
  actor: z.string(),
});

const AutomationRowSchema = z.object({
  rule: z.string(),
  status: z.enum(["actif", "dryrun", "inactif"]),
  last: z.string(),
  role: z.string(),
});

const ResolutionBarSchema = z.object({
  name: z.string(),
  pct: z.number(),
  ratio: z.string(),
  color: z.string(),
});

const PostmortemSchema = z.object({
  id: z.string(),
  label: z.string(),
  rca: z.string(),
  resolved: z.string(),
});

export const IncidentsOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  period_days: z.number().int(),
  updated_at: z.string(),
  kpis: z.array(IncidentKpiSchema),
  priority_incidents: z.array(PriorityIncidentSchema),
  playbook_catalog: z.array(PlaybookCatalogItemSchema),
  recent_incidents: z.array(RecentIncidentSchema),
  recent_more: z.number().int(),
  sla_escalations: z.array(SlaEscalationSchema),
  domain_distribution: z.array(DomainSliceSchema),
  donut_total: z.number().int(),
  control_cases: z.array(ControlCaseSchema),
  running_playbook: RunningPlaybookSchema,
  response_journal: z.array(ResponseJournalRowSchema),
  automations: z.array(AutomationRowSchema),
  mttr_series: z.object({
    labels: z.array(z.string()),
    mtta: z.array(z.number()),
    mttr: z.array(z.number()),
  }),
  resolution_by_playbook: z.array(ResolutionBarSchema),
  incidents_by_domain: z.array(DomainSliceSchema),
  postmortems: z.array(PostmortemSchema),
  footer: z.object({
    critical: z.number().int(),
    at_risk: z.number().int(),
    playbooks: z.number().int(),
    proofs: z.number().int(),
    source: z.string(),
    sync: z.string(),
  }),
  tabs: z.record(z.string(), CatalogTabSchema).optional(),
});
export type IncidentsOverview = z.infer<typeof IncidentsOverviewSchema>;
export type PriorityIncident = z.infer<typeof PriorityIncidentSchema>;

// ---------------------------------------------------------------------------
// Replay & shadow (page #11)
// ---------------------------------------------------------------------------

const RsKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta_label: z.string(),
  good_is_up: z.boolean(),
  series: z.array(z.number()),
});
const RsSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});
const RsSessionSchema = z.object({
  id: z.string(),
  service: z.string(),
  model: z.string(),
  status: z.enum(["rejouee", "termine", "encours", "error"]),
  origin: z.string(),
});
const RsDeviationSchema = z.object({
  id: z.string(),
  service: z.string(),
  type: z.string(),
  baseline: z.string(),
  severity: z.enum(["critique", "eleve", "moyen", "faible"]),
  delta: z.string(),
});
const RsComparisonSchema = z.object({
  label: z.string(),
  baseline: z.string(),
  sessions: z.string(),
  deviations: z.number().int(),
});
const RsRegressionSchema = z.object({
  service: z.string(),
  delta: z.string(),
  critical: z.number().int(),
  spark: z.array(z.number()),
});
const RsActivitySchema = z.object({
  id: z.string(),
  time: z.string(),
  status: z.enum(["rejouee", "termine", "encours", "error"]),
});

export const ReplayShadowOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  period_days: z.number().int(),
  updated_at: z.string(),
  kpis: z.array(RsKpiSchema),
  replay_traffic: z.object({
    labels: z.array(z.string()),
    requests: z.array(z.number()),
    tokens: z.array(z.number()),
  }),
  deviation_by_type: z.array(RsSliceSchema),
  deviation_total: z.number().int(),
  deviation_severity: z.array(RsSliceSchema),
  recent_sessions: z.array(RsSessionSchema),
  top_deviations: z.array(RsDeviationSchema),
  recent_comparisons: z.array(RsComparisonSchema),
  top_regressions: z.array(RsRegressionSchema),
  by_service: z.array(RsSliceSchema),
  by_model: z.array(RsSliceSchema),
  requests_total: z.string(),
  evals_by_category: z.array(RsSliceSchema),
  proofs_exports: z.object({
    generated: z.string(),
    available: z.string(),
    downloaded: z.string(),
    total_size: z.string(),
    last_export: z.string(),
  }),
  baselines: z.array(z.object({ value: z.string(), label: z.string() })),
  services: z.array(z.string()),
  activity_feed: z.array(RsActivitySchema),
  footer: z.object({
    environment: z.string(),
    services: z.number().int(),
    active_users: z.string(),
    confidence: z.string(),
    source: z.string(),
  }),
});
export type ReplayShadowOverview = z.infer<typeof ReplayShadowOverviewSchema>;

// ---------------------------------------------------------------------------
// Curation eval set (page #12)
// ---------------------------------------------------------------------------

const CurKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta_label: z.string(),
  good_is_up: z.boolean(),
  series: z.array(z.number()),
});
const CurLotSchema = z.object({
  id: z.string(),
  source: z.enum(["live", "replay", "shadow"]),
  category: z.string(),
  score: z.number().int(),
  risk: z.enum(["eleve", "moyen", "bas"]),
  owner: z.string(),
});
const CurWhySchema = z.object({
  reason: z.string(),
  value: z.number().int(),
  cost: z.string(),
});
const CurWorkflowSchema = z.object({
  step: z.string(),
  qty: z.number().int(),
  status: z.enum(["termine", "encours", "attente"]),
});
const CurSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});
const CurSignalSchema = z.object({
  key: z.string(),
  pct: z.number(),
  level: z.enum(["bon", "moyen", "faible"]),
});
const CurDatasetSchema = z.object({
  name: z.string(),
  size: z.string(),
  status: z.string(),
  updated: z.string(),
});
const CurOwnerSchema = z.object({
  role: z.string(),
  required: z.number().int(),
  assigned: z.number().int(),
  status: z.enum(["ok", "pending"]),
});
const CurActionSchema = z.object({
  key: z.string(),
  role: z.string(),
  requirement: z.enum(["", "dual", "signature"]),
});
const CurActivitySchema = z.object({
  time: z.string(),
  action: z.string(),
  actor: z.string(),
});

export const CurationOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  period_days: z.number().int(),
  updated_at: z.string(),
  kpis: z.array(CurKpiSchema),
  priority_lots: z.array(CurLotSchema),
  why_tours: z.array(CurWhySchema),
  workflow: z.array(CurWorkflowSchema),
  release: z.object({ id: z.string(), status: z.string(), readiness: z.number().int() }),
  cohort: z.string(),
  coverage: z.object({
    rows: z.array(z.string()),
    cols: z.array(z.string()),
    cells: z.array(z.array(z.enum(["ok", "warn", "bad", "none"]))),
  }),
  candidates_distribution: z.array(CurSliceSchema),
  distribution_total: z.number().int(),
  quality_signals: z.array(CurSignalSchema),
  linked_datasets: z.array(CurDatasetSchema),
  owners: z.array(CurOwnerSchema),
  actions: z.array(CurActionSchema),
  recent_activity: z.array(CurActivitySchema),
  backlog_trend: z.object({
    labels: z.array(z.string()),
    total: z.array(z.number()),
    to_curate: z.array(z.number()),
    promotable: z.array(z.number()),
    rejected: z.array(z.number()),
  }),
  balance: z.object({
    labels: z.array(z.string()),
    promote: z.array(z.number()),
    review: z.array(z.number()),
    reject: z.array(z.number()),
  }),
  impact: z.object({
    current: z.string(),
    projected: z.string(),
    delta: z.string(),
    current_val: z.number(),
    projected_val: z.number(),
  }),
  footer: z.object({ release: z.string(), source: z.string(), sync: z.string() }),
});
export type CurationOverview = z.infer<typeof CurationOverviewSchema>;

// ---------------------------------------------------------------------------
// Automations (page #13)
// ---------------------------------------------------------------------------

const AuKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta_label: z.string(),
  good_is_up: z.boolean(),
  series: z.array(z.number()),
});
const AuCatalogueSchema = z.object({
  name: z.string(),
  trigger: z.string(),
  action: z.string(),
  scope: z.string(),
  mode: z.enum(["auto", "approb"]),
  last_run: z.string(),
  success: z.string(),
  role: z.string(),
  status: z.enum(["active", "paused"]),
});
const AuIncidentSchema = z.object({
  severity: z.enum(["critique", "eleve", "moyen", "faible"]),
  id: z.string(),
  label: z.string(),
  time: z.string(),
});
const AuPipelineSchema = z.object({ key: z.string(), count: z.string(), pct: z.number() });
const AuSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});
const AuEnvSchema = z.object({ key: z.string(), count: z.number().int(), color: z.string() });
const AuJournalSchema = z.object({
  time: z.string(),
  automation: z.string(),
  trigger: z.string(),
  actor: z.string(),
  evidence: z.string(),
  duration: z.string(),
  result: z.enum(["success", "fail", "blocked", "approb"]),
});
const AuApprovalSchema = z.object({ name: z.string(), since: z.string(), role: z.string() });
const AuGuardrailSchema = z.object({ key: z.string(), count: z.number().int(), pct: z.number() });
const AuSavingSchema = z.object({ key: z.string(), value: z.string(), delta: z.string() });

export const AutomationsOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  period_days: z.number().int(),
  updated_at: z.string(),
  kpis: z.array(AuKpiSchema),
  catalogue: z.array(AuCatalogueSchema),
  recent_incidents: z.array(AuIncidentSchema),
  pipeline: z.array(AuPipelineSchema),
  completion: z.string(),
  by_type: z.array(AuSliceSchema),
  by_type_total: z.number().int(),
  by_env: z.array(AuEnvSchema),
  journal: z.array(AuJournalSchema),
  approvals: z.array(AuApprovalSchema),
  guardrails: z.array(AuGuardrailSchema),
  performance: z.object({
    labels: z.array(z.string()),
    success: z.array(z.number()),
    average: z.array(z.number()),
  }),
  savings: z.array(AuSavingSchema),
  context: z.object({
    version: z.string(),
    last_modified: z.string(),
    author: z.string(),
    branch: z.string(),
    scope: z.string(),
  }),
  governance: z.object({
    dual_control: z.boolean(),
    roles: z.array(z.object({ mode: z.string(), scope: z.string() })),
    default_scope: z.string(),
  }),
  footer: z.object({ source: z.string(), certified: z.string() }),
});
export type AutomationsOverview = z.infer<typeof AutomationsOverviewSchema>;

// ---------------------------------------------------------------------------
// Proofs & exporter (page #15)
// ---------------------------------------------------------------------------

const PfKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta_label: z.string(),
  good_is_up: z.boolean(),
  series: z.array(z.number()),
});
const PfSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});

export const ProofsOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  period_days: z.number().int(),
  updated_at: z.string(),
  kpis: z.array(PfKpiSchema),
  alerts: z.array(z.object({ level: z.enum(["ok", "warn", "bad"]), label: z.string() })),
  alert_count: z.number().int(),
  pipeline: z.array(z.object({ key: z.string(), count: z.string(), status: z.string() })),
  current_pack: z.object({
    id: z.string(),
    period: z.string(),
    scope: z.string(),
    hash: z.string(),
    signer: z.string(),
    contents: z.array(z.object({ key: z.string(), n: z.number().int() })),
  }),
  recent_packs: z.array(
    z.object({
      id: z.string(),
      scope: z.string(),
      artifacts: z.string(),
      signature: z.string(),
      destinations: z.string(),
      by: z.string(),
      time: z.string(),
      status: z.enum(["signe", "exporte", "attente", "echec"]),
    }),
  ),
  artifacts_distribution: z.array(PfSliceSchema),
  artifacts_total: z.number().int(),
  exporters: z.array(
    z.object({
      destination: z.string(),
      format: z.string(),
      status: z.enum(["ok", "degraded", "down"]),
      last_push: z.string(),
      queue: z.string(),
      retention: z.string(),
    }),
  ),
  crypto: z.object({
    valid_signatures: z.string(),
    algorithm: z.string(),
    key_rotation: z.string(),
    anomalies: z.number().int(),
  }),
  control_case_proofs: z.array(
    z.object({
      case_id: z.string(),
      subject: z.string(),
      linked: z.number().int(),
      owner: z.string(),
      status: z.enum(["ok", "pending"]),
    }),
  ),
  retention: z.array(
    z.object({
      destination: z.string(),
      proof_type: z.string(),
      retention: z.string(),
      obligation: z.string(),
      coverage: z.number().int(),
      expiry: z.string(),
    }),
  ),
  export_journal: z.array(
    z.object({ time: z.string(), label: z.string(), status: z.enum(["ok", "degraded", "down"]) }),
  ),
  queue: z.object({
    pending_signature: z.number().int(),
    pending_export: z.number().int(),
    verifications: z.number().int(),
  }),
  footer: z.object({ chain: z.string(), source: z.string() }),
});
export type ProofsOverview = z.infer<typeof ProofsOverviewSchema>;

// ---------------------------------------------------------------------------
// Signal catalogue (page #16)
// ---------------------------------------------------------------------------

const ScKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
  series: z.array(z.number()),
});
const ScSignalSchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.string(),
  description: z.string(),
  source: z.string(),
  severity: z.enum(["critical", "high", "medium", "low"]),
  status: z.enum(["active", "evaluation", "deprecated", "disabled"]),
  quality: z.number().int(),
  last_activity: z.string(),
  owner: z.string(),
  modified: z.string(),
});

export const SignalCatalogueSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  total_signals: z.number().int(),
  page_size: z.number().int(),
  kpis: z.array(ScKpiSchema),
  signals: z.array(ScSignalSchema),
  selected: z.object({
    id: z.string(),
    name: z.string(),
    category: z.string(),
    status: z.enum(["active", "evaluation", "deprecated", "disabled"]),
    description: z.string(),
    source: z.string(),
    type: z.string(),
    unit: z.string(),
    direction: z.string(),
    frequency: z.string(),
    environment: z.string(),
    tags: z.array(z.string()),
    created: z.string(),
    modified: z.string(),
    severity: z.enum(["critical", "high", "medium", "low"]),
    threshold_critical: z.string(),
    threshold_alert: z.string(),
    model: z.string(),
    last_activity: z.string(),
    quality: z.number().int(),
    distribution: z.array(
      z.object({ label: z.string(), count: z.number().int(), color: z.string() }),
    ),
    trend: z.array(z.number()),
    usage: z.object({ logged_by: z.string(), monitors: z.string() }),
  }),
  categories: z.array(z.string()),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type SignalCatalogue = z.infer<typeof SignalCatalogueSchema>;

// ---------------------------------------------------------------------------
// Policies & guardrails (page #16-policies)
// ---------------------------------------------------------------------------

const PolKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta_label: z.string(),
  good_is_up: z.boolean(),
  series: z.array(z.number()),
});

export const PoliciesOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  active_version: z.string(),
  compare_to: z.string(),
  version_timeline: z.array(
    z.object({
      version: z.string(),
      status: z.enum(["draft", "approved", "active", "canary", "archived"]),
      date: z.string(),
    }),
  ),
  version_detail: z.object({
    version: z.string(),
    effective_from: z.string(),
    commit: z.string(),
    author: z.string(),
    approver: z.string(),
    scope: z.string(),
  }),
  kpis: z.array(PolKpiSchema),
  active_policies: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      type: z.string(),
      action: z.enum(["deny", "allow", "warn"]),
      scope: z.string(),
      version: z.string(),
      changed_by: z.string(),
      approved_by: z.string(),
      status: z.enum(["active", "draft", "archived"]),
    }),
  ),
  version_history: z.array(
    z.object({
      version: z.string(),
      datetime: z.string(),
      author: z.string(),
      approver: z.string(),
      status: z.enum(["draft", "approved", "active", "canary", "archived"]),
    }),
  ),
  diff: z.object({
    title: z.string(),
    lines: z.array(z.object({ type: z.enum(["context", "added", "removed"]), text: z.string() })),
  }),
  guardrails: z.array(z.object({ key: z.string(), value: z.string(), pct: z.number() })),
  impact: z.array(
    z.object({
      metric: z.string(),
      baseline: z.string(),
      candidate: z.string(),
      delta: z.string(),
      tone: z.enum(["ok", "warn", "bad", "neutral"]),
    }),
  ),
  sensitive_actions: z.array(z.object({ key: z.string(), role: z.string() })),
  quick_links: z.array(z.string()),
  footer: z.object({ source: z.string(), chain: z.string() }),
});
export type PoliciesOverview = z.infer<typeof PoliciesOverviewSchema>;

// ---------------------------------------------------------------------------
// Sources & memory (page #17)
// ---------------------------------------------------------------------------

const SmKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
  series: z.array(z.number()),
});
const SmSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});

export const SourcesOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  total_sources: z.number().int(),
  page_size: z.number().int(),
  kpis: z.array(SmKpiSchema),
  sources: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      type: z.string(),
      classification: z.enum(["public", "internal", "confidential"]),
      environment: z.string(),
      status: z.enum(["active", "deprecated", "disabled"]),
      data_total: z.string(),
      indexed: z.string(),
      last_sync: z.string(),
      quality: z.number().int(),
      freshness: z.string(),
      owner: z.string(),
      cost: z.string(),
    }),
  ),
  selected: z.object({
    id: z.string(),
    name: z.string(),
    type: z.string(),
    status: z.enum(["active", "deprecated", "disabled"]),
    description: z.string(),
    connector: z.string(),
    environment: z.string(),
    region: z.string(),
    classification: z.enum(["public", "internal", "confidential"]),
    owner: z.string(),
    created: z.string(),
    modified: z.string(),
    retention: z.string(),
    source: z.string(),
    tags: z.array(z.string()),
    usage: z.string(),
    documents: z.object({ value: z.string(), delta: z.string() }),
    queries: z.object({ value: z.string(), delta: z.string() }),
    cost: z.object({ value: z.string(), delta: z.string() }),
    quality_global: z.number().int(),
    quality_breakdown: z.array(
      z.object({ key: z.string(), pct: z.number().int(), color: z.string() }),
    ),
  }),
  by_type: z.array(SmSliceSchema),
  by_type_total: z.number().int(),
  by_env: z.array(
    z.object({ key: z.string(), value: z.string(), pct: z.number(), color: z.string() }),
  ),
  cost_by_source: z.array(z.object({ name: z.string(), value: z.number(), label: z.string() })),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type SourcesOverview = z.infer<typeof SourcesOverviewSchema>;

// ---------------------------------------------------------------------------
// Roles & access (page #18)
// ---------------------------------------------------------------------------

const RaKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
  series: z.array(z.number()),
});
const RaSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});

export const AccessOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  total_roles: z.number().int(),
  page_size: z.number().int(),
  kpis: z.array(RaKpiSchema),
  roles: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      type: z.enum(["systeme", "metier"]),
      description: z.string(),
      users: z.number().int(),
      groups: z.number().int(),
      permissions: z.number().int(),
      scope: z.string(),
      environment: z.string(),
      modified: z.string(),
      status: z.enum(["active", "deprecated", "disabled"]),
    }),
  ),
  selected: z.object({
    id: z.string(),
    name: z.string(),
    type: z.enum(["systeme", "metier"]),
    scope: z.string(),
    description: z.string(),
    owner: z.string(),
    created: z.string(),
    modified: z.string(),
    status: z.enum(["active", "deprecated", "disabled"]),
    environment: z.string(),
    members: z.array(z.object({ name: z.string(), team: z.string(), status: z.string() })),
    permission_dist: z.array(RaSliceSchema),
    access_scope: z.array(RaSliceSchema),
  }),
  top_roles: z.array(z.object({ name: z.string(), value: z.number(), label: z.string() })),
  access_by_resource: z.array(RaSliceSchema),
  pending_requests: z.array(
    z.object({
      user: z.string(),
      role: z.string(),
      since: z.string(),
      risk: z.enum(["low", "medium", "high"]),
    }),
  ),
  sod_violations: z.array(
    z.object({
      user: z.string(),
      conflict: z.string(),
      severity: z.enum(["high", "medium", "low"]),
    }),
  ),
  inactive_accounts: z.array(
    z.object({ user: z.string(), last_seen: z.string(), role: z.string() }),
  ),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type AccessOverview = z.infer<typeof AccessOverviewSchema>;

// ---------------------------------------------------------------------------
// Integrations (page #19)
// ---------------------------------------------------------------------------

const IgKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
  series: z.array(z.number()),
});
const IgSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});
const IgMetricSchema = z.object({ value: z.string(), delta: z.string() });

export const IntegrationsOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  total_integrations: z.number().int(),
  page_size: z.number().int(),
  kpis: z.array(IgKpiSchema),
  integrations: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      type: z.string(),
      status: z.enum(["active", "warning", "error", "disabled"]),
      environment: z.string(),
      owner: z.string(),
      calls: z.string(),
      success_rate: z.string(),
      response_time: z.string(),
      last_sync: z.string(),
    }),
  ),
  selected: z.object({
    id: z.string(),
    name: z.string(),
    status: z.enum(["active", "warning", "error", "disabled"]),
    last_sync: z.string(),
    response_time: z.string(),
    success_rate: z.string(),
    description: z.string(),
    owner: z.string(),
    environment: z.string(),
    region: z.string(),
    criticality: z.enum(["low", "medium", "high"]),
    usage: z.object({ read: IgMetricSchema, write: IgMetricSchema, cost: IgMetricSchema }),
    config: z.object({
      url: z.string(),
      version: z.string(),
      auth: z.string(),
      timeout: z.string(),
      retry: z.string(),
      rate_limit: z.string(),
      pagination: z.string(),
    }),
    security: z.object({
      method: z.string(),
      client_id: z.string(),
      cert: z.string(),
      key_rotation: z.string(),
      last_rotation: z.string(),
    }),
  }),
  by_type: z.array(IgSliceSchema),
  by_type_total: z.number().int(),
  by_env: z.array(
    z.object({ key: z.string(), value: z.string(), pct: z.number(), color: z.string() }),
  ),
  top_integrations: z.array(z.object({ name: z.string(), value: z.number(), label: z.string() })),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type IntegrationsOverview = z.infer<typeof IntegrationsOverviewSchema>;

// ---------------------------------------------------------------------------
// System profile (page #20)
// ---------------------------------------------------------------------------

const SpSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});

export const SystemProfileSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  kpis: z.array(
    z.object({
      key: z.string(),
      kind: z.enum(["status", "metric", "chart", "time"]),
      value: z.string(),
      sub: z.string(),
      delta: z.string().optional(),
      link: z.string().optional(),
      extra: z.string().optional(),
      series: z.array(z.number()),
    }),
  ),
  architecture: z.object({
    edition: z.string(),
    version: z.string(),
    deployment: z.string(),
    region: z.string(),
    cluster: z.string(),
    deployed_at: z.string(),
    uptime: z.string(),
    next_maintenance: z.string(),
  }),
  topology: z.object({
    tiers: z.array(z.object({ key: z.string(), label: z.string(), nodes: z.number().int() })),
    planes: z.array(z.object({ key: z.string(), label: z.string(), nodes: z.number().int() })),
    stores: z.array(z.object({ key: z.string(), label: z.string(), detail: z.string() })),
  }),
  resources: z.object({ total: z.string(), slices: z.array(SpSliceSchema) }),
  os_info: z.object({
    os: z.string(),
    kernel: z.string(),
    arch: z.string(),
    virtualization: z.string(),
    cpu: z.string(),
    memory: z.string(),
    system_time: z.string(),
    timezone: z.string(),
    fqdn: z.string(),
    infra_id: z.string(),
    support: z.string(),
  }),
  health_checks: z.array(z.object({ key: z.string(), status: z.enum(["ok", "warn", "bad"]) })),
  resource_series: z.object({
    labels: z.array(z.string()),
    cpu: z.array(z.number()),
    memory: z.array(z.number()),
    disk: z.array(z.number()),
    network: z.array(z.number()),
  }),
  services: z.array(
    z.object({
      name: z.string(),
      status: z.enum(["ok", "warn", "bad"]),
      version: z.string(),
      instances: z.string(),
    }),
  ),
  versions: z.array(z.object({ name: z.string(), version: z.string() })),
  licenses: z.object({
    edition: z.string(),
    seats: z.string(),
    expiry: z.string(),
    quota_calls: z.string(),
    quota_storage: z.string(),
  }),
  footer: z.object({ version: z.string(), source: z.string() }),
});
export type SystemProfile = z.infer<typeof SystemProfileSchema>;

// ---------------------------------------------------------------------------
// Parameters / settings (page #21)
// ---------------------------------------------------------------------------

const PaKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
  series: z.array(z.number()),
});

export const ParametersOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  config_version: z.object({
    version: z.string(),
    env: z.string(),
    status: z.string(),
    active_since: z.string(),
    modified_by: z.string(),
    validation: z.string(),
    next_review: z.string(),
  }),
  kpis: z.array(PaKpiSchema),
  categories: z.array(z.object({ key: z.string(), desc: z.string() })),
  recent_params: z.array(
    z.object({
      name: z.string(),
      category: z.string(),
      value: z.string(),
      modified_by: z.string(),
      date: z.string(),
      status: z.enum(["active", "draft", "deprecated"]),
    }),
  ),
  config_state: z.object({
    total: z.number().int(),
    slices: z.array(
      z.object({ key: z.string(), count: z.number().int(), pct: z.number(), color: z.string() }),
    ),
  }),
  compliance: z.array(z.object({ key: z.string(), status: z.enum(["ok", "warn", "bad"]) })),
  usage_policies: z.array(z.object({ name: z.string(), value: z.string(), status: z.string() })),
  backup: z.object({
    last_backup: z.string(),
    frequency: z.string(),
    retention: z.string(),
    size: z.string(),
  }),
  footer: z.object({ version: z.string(), source: z.string() }),
});
export type ParametersOverview = z.infer<typeof ParametersOverviewSchema>;

// ---------------------------------------------------------------------------
// Inbox / À traiter (page #24)
// ---------------------------------------------------------------------------

const IbKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta_label: z.string(),
  good_is_up: z.boolean(),
  series: z.array(z.number()),
});

export const InboxOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  rail: z.object({ period: z.string(), sla: z.string(), updated: z.string(), compare: z.string() }),
  kpis: z.array(IbKpiSchema),
  items: z.array(
    z.object({
      id: z.string(),
      priority: z.enum(["urgent", "high", "medium", "low"]),
      type: z.string(),
      title: z.string(),
      source: z.string(),
      assignee: z.string(),
      sla: z.string(),
      sla_tone: z.enum(["crit", "warn", "ok"]),
      due: z.string(),
      status: z.enum(["todo", "in_progress", "waiting", "resolved"]),
    }),
  ),
  total_items: z.number().int(),
  by_type: z.array(
    z.object({ key: z.string(), count: z.number().int(), pct: z.number(), color: z.string() }),
  ),
  by_type_total: z.number().int(),
  sla_buckets: z.array(z.object({ key: z.string(), count: z.number().int(), color: z.string() })),
  recent_activity: z.array(z.object({ time: z.string(), actor: z.string(), action: z.string() })),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type InboxOverview = z.infer<typeof InboxOverviewSchema>;

const AsMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  time: z.string(),
  text: z.string().optional(),
  latency: z.string().optional(),
  tokens: z.string().optional(),
  intro: z.string().optional(),
  points: z.array(z.object({ label: z.string(), body: z.string() })).optional(),
  outro: z.string().optional(),
});

export const AssistantOverviewSchema = z.object({
  available: z.boolean(),
  session: z.object({
    id: z.string(),
    status: z.string(),
    model: z.string(),
    prompt_version: z.string(),
    sources_snapshot: z.string(),
    guardrails_version: z.string(),
    language: z.string(),
    trace: z.string(),
    started_at: z.string(),
    replay_at: z.string(),
  }),
  context: z.object({
    user: z.string(),
    environment: z.string(),
    objective: z.string(),
    tags: z.array(z.string()),
  }),
  messages: z.array(AsMessageSchema),
  sources: z.array(z.object({ title: z.string() })),
  tools: z.array(z.object({ name: z.string() })),
  guardrails: z.array(
    z.object({ name: z.string(), detail: z.string(), level: z.enum(["warn", "crit", "ok"]) }),
  ),
  quality: z.array(z.object({ key: z.string(), value: z.number() })),
  trace: z.array(z.object({ key: z.string(), done: z.boolean() })),
  suggestions: z.array(z.string()),
  rail_kpis: z.array(z.object({ key: z.string(), value: z.string() })),
  tenant: z.string(),
});
export type AssistantOverview = z.infer<typeof AssistantOverviewSchema>;

// --- Agent overview ("Synthese de l'agent") dashboard (reference image 22) ---

const SynKpiSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.string(),
  delta: z.string(),
  good: z.boolean(),
  series: z.array(z.number()),
});
const SynLabelValueSchema = z.object({ label: z.string(), value: z.string() });
const SynBarSchema = z.object({ label: z.string(), pct: z.number(), tone: z.string() });

export const AgentSyntheseSchema = z.object({
  available: z.boolean(),
  meta: z
    .object({
      mode: z.string(),
      period: z.string(),
      updated: z.string(),
      replayAt: z.string(),
      comparison: z.string(),
    })
    .optional(),
  kpis: z.array(SynKpiSchema).optional(),
  profile: z
    .object({
      name: z.string(),
      status: z.string(),
      fields: z.array(SynLabelValueSchema),
      cta: z.string(),
      ctaHref: z.string().optional(),
    })
    .optional(),
  capabilities: z
    .object({
      title: z.string(),
      items: z.array(z.string()),
      cta: z.string(),
      ctaHref: z.string().optional(),
    })
    .optional(),
  topics: z
    .object({
      title: z.string(),
      items: z.array(SynBarSchema),
      cta: z.string(),
      ctaHref: z.string().optional(),
    })
    .optional(),
  performance: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({
          label: z.string(),
          value: z.string(),
          delta: z.string(),
          good: z.boolean(),
        }),
      ),
      cta: z.string(),
      ctaHref: z.string().optional(),
    })
    .optional(),
  config: z
    .object({
      title: z.string(),
      rows: z.array(SynLabelValueSchema),
      cta: z.string(),
      ctaHref: z.string().optional(),
    })
    .optional(),
  conversations: z
    .object({
      title: z.string(),
      cta: z.string(),
      ctaHref: z.string().optional(),
      rows: z.array(
        z.object({
          title: z.string(),
          user: z.string(),
          time: z.string(),
          status: z.string(),
        }),
      ),
    })
    .optional(),
  activity: z
    .object({
      title: z.string(),
      rows: z.array(z.object({ time: z.string(), label: z.string(), kind: z.string() })),
    })
    .optional(),
  prompts: z
    .object({
      title: z.string(),
      cta: z.string(),
      ctaHref: z.string().optional(),
      rows: z.array(
        z.object({
          name: z.string(),
          version: z.string(),
          status: z.string(),
          updated: z.string(),
        }),
      ),
    })
    .optional(),
  channels: z.object({ title: z.string(), items: z.array(SynBarSchema) }).optional(),
  timeline: z
    .object({
      title: z.string(),
      cta: z.string(),
      ctaHref: z.string().optional(),
      rows: z.array(
        z.object({
          time: z.string(),
          label: z.string(),
          detail: z.string(),
          kind: z.string(),
        }),
      ),
    })
    .optional(),
  alerts: z
    .object({
      title: z.string(),
      cta: z.string(),
      ctaHref: z.string().optional(),
      items: z.array(z.object({ label: z.string(), value: z.string(), tone: z.string() })),
    })
    .optional(),
  quick_config: z
    .object({
      title: z.string(),
      cta: z.string(),
      ctaHref: z.string().optional(),
      items: z.array(z.object({ label: z.string(), href: z.string() })),
    })
    .optional(),
});
export type AgentSynthese = z.infer<typeof AgentSyntheseSchema>;

const EtatGovCardSchema = z.object({
  title: z.string(),
  rows: z.array(z.object({ label: z.string(), value: z.string() })),
  diff: z.array(z.object({ kind: z.string(), text: z.string() })),
  cta: z.string(),
  cta_href: z.string(),
});

export const EtatADateSchema = z.object({
  available: z.boolean(),
  meta: z
    .object({
      as_of: z.string().nullable(),
      as_of_label: z.string(),
      ref_code: z.string(),
      tenant: z.string(),
      agent: z.string(),
      context_source: z.string(),
      timezone: z.string(),
      banner: z.string(),
    })
    .optional(),
  reconstructed: z
    .object({
      title: z.string(),
      snapshot_id: z.string(),
      verified: z.boolean(),
      verified_label: z.string(),
      built_label: z.string(),
    })
    .optional(),
  original: z
    .object({
      title: z.string(),
      cta: z.string(),
      cta_href: z.string(),
      available: z.boolean(),
      ref_code: z.string(),
      question: z.string().optional(),
      answer: z.string().optional(),
      timestamp: z.string().optional(),
      session: z.string().optional(),
    })
    .optional(),
  guardrails: EtatGovCardSchema.optional(),
  prompt_model: EtatGovCardSchema.optional(),
  release: EtatGovCardSchema.optional(),
  table: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({
          key: z.string(),
          source: z.string(),
          type: z.string(),
          type_key: z.string(),
          type_tone: z.string(),
          langs: z.string(),
          chunks: z.number(),
          total_chunks: z.number(),
          version: z.string(),
          accessible_until: z.string(),
          updated: z.string(),
          first_seen: z.string(),
          status: z.string(),
          status_label: z.string(),
        }),
      ),
    })
    .optional(),
  integrity: z
    .object({
      title: z.string(),
      snapshot_id: z.string(),
      coverage: z.string(),
      test_query: z.string(),
      last_sync: z.string(),
      verified: z.boolean(),
      verified_label: z.string(),
      chain_label: z.string(),
    })
    .optional(),
  timeline: z
    .object({
      title: z.string(),
      rows: z.array(z.object({ time: z.string(), label: z.string(), kind: z.string() })),
      cta: z.string().optional(),
      cta_href: z.string().optional(),
    })
    .optional(),
  audit_pieces: z
    .object({
      title: z.string(),
      rows: z.array(z.object({ label: z.string(), href: z.string() })),
    })
    .optional(),
  snapshots: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({
          id: z.string(),
          as_of: z.string().nullable(),
          as_of_label: z.string(),
          ref_code: z.string(),
          saved_label: z.string(),
          summary: z.string(),
        }),
      ),
    })
    .optional(),
});
export type EtatADate = z.infer<typeof EtatADateSchema>;

const AgentAFaireDetailSchema = z.object({
  key: z.string().optional(),
  title: z.string().optional(),
  selected: z.object({
    key: z.string().optional(),
    id: z.string(),
    priority: z.string(),
    prio_tone: z.string(),
    title: z.string(),
    subtitle: z.string(),
    cta: z.string(),
  }),
  tabs: z.array(z.string()),
  context: z.array(z.object({ label: z.string(), value: z.string() })),
  summary_label: z.string(),
  summary: z.string(),
  sla_title: z.string(),
  sla_value: z.string(),
  sla_note: z.string(),
  sla_rows: z.array(z.object({ label: z.string(), value: z.string() })),
  assign_title: z.string(),
  assign_label: z.string(),
  assignee: z.string(),
  team_label: z.string(),
  team: z.string(),
  reassign: z.string(),
  current_status: z.string().optional(),
  current_status_tone: z.string().optional(),
  sla_cell: z.string().optional(),
});

export const AgentAFaireSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  rail: z
    .object({
      live: z.string(),
      segments: z.array(z.string()),
      period: z.string(),
      updated: z.string(),
      now: z.string(),
      scope: z.string(),
      bulk: z.string(),
    })
    .optional(),
  timeline: z
    .object({
      title: z.string(),
      cta: z.string(),
      events: z.array(
        z.object({ time: z.string(), label: z.string(), ref: z.string(), tone: z.string() }),
      ),
    })
    .optional(),
  kpis: z
    .array(
      z.object({
        key: z.string(),
        label: z.string(),
        value: z.string(),
        delta: z.string(),
        good: z.boolean(),
        tone: z.string(),
        series: z.array(z.number()),
      }),
    )
    .optional(),
  filters: z
    .object({
      title: z.string(),
      search: z.string(),
      selects: z.array(z.object({ label: z.string(), value: z.string() })),
      more: z.string(),
      views_title: z.string(),
      views: z.array(z.string()),
      views_cta: z.string(),
    })
    .optional(),
  table: z
    .object({
      columns: z.array(z.string()),
      count: z.string(),
      showing: z.string(),
      pages: z.array(z.number()),
      per_page_label: z.string(),
      per_page: z.string(),
      tasks: z.array(
        z.object({
          key: z.string().optional(),
          priority: z.string(),
          prio_tone: z.string(),
          type: z.string(),
          title: z.string(),
          source: z.string(),
          ref: z.string(),
          assignee: z.string(),
          sla: z.string(),
          sla_tone: z.string(),
          due: z.string(),
          status: z.string(),
          status_tone: z.string(),
        }),
      ),
    })
    .optional(),
  detail: AgentAFaireDetailSchema.optional(),
  details: z.array(AgentAFaireDetailSchema).optional(),
  donut: z
    .object({
      title: z.string(),
      cta: z.string(),
      center: z.string(),
      center_label: z.string(),
      segments: z.array(
        z.object({
          label: z.string(),
          count: z.number(),
          share: z.string(),
          color: z.string(),
        }),
      ),
    })
    .optional(),
  sla: z
    .object({
      title: z.string(),
      cta: z.string(),
      buckets: z.array(z.object({ label: z.string(), count: z.number(), color: z.string() })),
    })
    .optional(),
  quick: z.object({ title: z.string(), items: z.array(z.string()) }).optional(),
  activity: z
    .object({
      title: z.string(),
      cta: z.string(),
      items: z.array(z.object({ actor: z.string(), action: z.string(), time: z.string() })),
    })
    .optional(),
  status: z
    .object({
      title: z.string(),
      label: z.string(),
      value: z.string(),
      primary: z.string(),
      secondary: z.string(),
    })
    .optional(),
  footer: z.object({ check: z.string(), status: z.string() }).optional(),
});
export type AgentAFaire = z.infer<typeof AgentAFaireSchema>;

const AgentConfigFieldSchema = z.object({
  key: z.string().optional(),
  label: z.string(),
  value: z.string(),
  kind: z.string(),
  badge: z.string().nullable(),
  editable: z.boolean().optional(),
  options: z.array(z.string()).optional(),
});

const AgentConfigSliderSchema = z.object({
  key: z.string().optional(),
  label: z.string(),
  value: z.string(),
  pct: z.number(),
  num: z.number().optional(),
  min: z.number().optional(),
  max: z.number().optional(),
  step: z.number().optional(),
  editable: z.boolean().optional(),
});

export const AgentConfigurationsSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  actions: z
    .object({
      save: z.string(),
      saved: z.string().optional(),
      reset: z.string().optional(),
      more: z.string(),
      propose: z.string().optional(),
    })
    .optional(),
  identity: z
    .object({
      title: z.string(),
      left: z.array(AgentConfigFieldSchema),
      right: z.array(AgentConfigFieldSchema),
      link: z.object({ label: z.string(), href: z.string() }).optional(),
    })
    .optional(),
  model: z
    .object({
      title: z.string(),
      left: z.array(AgentConfigFieldSchema),
      right: z.array(AgentConfigFieldSchema),
      link: z.object({ label: z.string(), href: z.string() }).optional(),
    })
    .optional(),
  behavior: z
    .object({
      title: z.string(),
      selects: z.array(AgentConfigFieldSchema),
      sliders: z.array(AgentConfigSliderSchema),
      tools: z.object({
        label: z.string(),
        value: z.string(),
        items: z.array(z.string()).optional(),
        href: z.string().optional(),
      }),
      note: z.string(),
    })
    .optional(),
  routing: z
    .object({
      title: z.string(),
      left: z.array(AgentConfigFieldSchema),
      right: z.array(AgentConfigFieldSchema),
      link: z.object({ label: z.string(), href: z.string() }).optional(),
    })
    .optional(),
  governed: z.boolean().optional(),
  tags: z
    .object({
      title: z.string(),
      tags: z.array(z.string()),
      add_tag: z.string(),
      metadata_label: z.string(),
      metadata: z.string(),
      add_metadata: z.string(),
      created: z.string(),
      modified: z.string(),
      archive: z.string(),
      archived: z.boolean().optional(),
    })
    .optional(),
  status: z
    .object({
      title: z.string(),
      badge: z.string(),
      badge_tone: z.string().optional(),
      rows: z.array(
        z.object({
          label: z.string(),
          value: z.string(),
          badge: z.boolean().optional(),
          online: z.boolean().optional(),
          info: z.boolean().optional(),
          live: z.boolean().optional(),
        }),
      ),
    })
    .optional(),
  active_model: z
    .object({
      title: z.string(),
      name: z.string(),
      provider: z.string(),
      rows: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
  summary: z
    .object({
      title: z.string(),
      rows: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
  history: z
    .object({
      title: z.string(),
      cta: z.string(),
      items: z.array(z.object({ time: z.string(), actor: z.string(), label: z.string() })),
    })
    .optional(),
  links: z
    .object({
      title: z.string(),
      items: z.array(z.object({ title: z.string(), desc: z.string(), href: z.string() })),
    })
    .optional(),
});
export type AgentConfigurations = z.infer<typeof AgentConfigurationsSchema>;

export const AgentConsoleSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  status: z
    .object({
      session_id: z.string(),
      live: z.boolean(),
      fields: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
  transcript: z
    .array(
      z.object({
        role: z.string(),
        time: z.string(),
        text: z.string().optional(),
        latency: z.string().optional(),
        intro: z.string().optional(),
        points: z
          .array(z.object({ ref: z.string(), title: z.string(), body: z.string() }))
          .optional(),
        closing: z.string().optional(),
        chips: z.array(z.object({ label: z.string(), kind: z.string() })).optional(),
      }),
    )
    .optional(),
  kpis: z
    .array(z.object({ key: z.string(), label: z.string(), value: z.string(), good: z.boolean() }))
    .optional(),
  tabs: z.array(z.string()).optional(),
  quality: z
    .object({
      title: z.string(),
      badge: z.string(),
      badge_tone: z.string(),
      rows: z.array(
        z.object({ label: z.string(), value: z.string(), scale: z.string(), tone: z.string() }),
      ),
    })
    .optional(),
  sources: z
    .object({
      title: z.string(),
      cta: z.string(),
      rows: z.array(z.object({ label: z.string(), scope: z.string() })),
    })
    .optional(),
  tools: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({ name: z.string(), status: z.string(), tone: z.string(), latency: z.string() }),
      ),
    })
    .optional(),
  guardrails: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({ name: z.string(), status: z.string(), tone: z.string(), detail: z.string() }),
      ),
    })
    .optional(),
  trace: z
    .object({
      title: z.string(),
      cta: z.string(),
      rows: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
  footer: z
    .object({
      started: z.string(),
      live: z.boolean(),
      context: z.string(),
      language: z.string(),
      session_id: z.string(),
    })
    .optional(),
  actions: z
    .object({
      input_placeholder: z.string(),
      feedback: z.array(z.string()),
      footer_actions: z.array(z.object({ key: z.string(), label: z.string() })),
      timeline_incidents: z.string(),
      new_session: z.string(),
      replay: z.string(),
    })
    .optional(),
});
export type AgentConsole = z.infer<typeof AgentConsoleSchema>;

export const ConsoleFeedbackSchema = z.object({
  ratings: z.record(z.string(), z.string()),
});
export type ConsoleFeedback = z.infer<typeof ConsoleFeedbackSchema>;

export const AgentConnaissancesSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  actions: z.object({ manage: z.string(), memory: z.string(), attach: z.string() }).optional(),
  attachable: z.array(z.object({ key: z.string(), name: z.string(), type: z.string() })).optional(),
  kpis: z
    .array(
      z.object({
        key: z.string(),
        label: z.string(),
        value: z.string(),
        series: z.array(z.number()),
      }),
    )
    .optional(),
  filters: z
    .object({
      search: z.string(),
      selects: z.array(z.object({ label: z.string(), value: z.string() })),
      more: z.string(),
    })
    .optional(),
  table: z
    .object({
      columns: z.array(z.string()),
      count: z.string(),
      rows: z.array(
        z.object({
          key: z.string().optional(),
          name: z.string(),
          path: z.string(),
          type: z.string(),
          type_tone: z.string().optional(),
          status: z.string(),
          status_tone: z.string(),
          coverage: z.number().nullable(),
          freshness: z.string(),
          fresh_days: z.number().optional(),
          citation: z.string(),
          langs: z.array(z.string()).optional(),
          grounded: z.number().optional(),
        }),
      ),
    })
    .optional(),
  details: z
    .array(
      z.object({
        name: z.string(),
        status: z.string(),
        status_tone: z.string(),
        tabs: z.array(z.string()),
        summary_title: z.string(),
        summary: z.string(),
        usage_title: z.string(),
        usage: z.array(z.object({ label: z.string(), value: z.string() })),
        answers_title: z.string(),
        answers: z.array(
          z.object({ text: z.string(), answer: z.string().optional(), time: z.string() }),
        ),
        params_title: z.string().optional(),
        params: z.array(z.object({ label: z.string(), value: z.string() })).optional(),
        actions_title: z.string(),
        toggle_label: z.string(),
        toggle_on: z.boolean(),
        detach: z.string(),
        full_sheet: z.string(),
        key: z.string().optional(),
      }),
    )
    .optional(),
});
export type AgentConnaissances = z.infer<typeof AgentConnaissancesSchema>;

export const AgentGardeFousSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  actions: z.object({ asof: z.string(), create: z.string() }).optional(),
  snapshot: z
    .object({
      tag: z.string(),
      label: z.string(),
      updated_label: z.string(),
      updated: z.string(),
      updated_rel: z.string(),
      version_label: z.string(),
      version: z.string(),
      version_status: z.string(),
      evalset_label: z.string(),
      evalset: z.string(),
      coverage_label: z.string(),
      coverage: z.number(),
      coverage_tone: z.string(),
      asof: z.string(),
      compare: z.string(),
    })
    .optional(),
  kpis: z
    .array(
      z.object({
        key: z.string(),
        label: z.string(),
        value: z.string(),
        delta: z.string(),
        good: z.boolean(),
      }),
    )
    .optional(),
  filters: z
    .object({
      search: z.string(),
      selects: z.array(z.object({ label: z.string(), value: z.string() })),
      more: z.string(),
    })
    .optional(),
  table: z
    .object({
      columns: z.array(z.string()),
      count: z.string(),
      pages: z.number(),
      rows: z.array(
        z.object({
          key: z.string(),
          name: z.string(),
          category: z.string(),
          category_key: z.string(),
          severity: z.string(),
          sev_tone: z.string(),
          status: z.string(),
          status_tone: z.string(),
          mode: z.string(),
          mode_tone: z.string(),
          coverage: z.number(),
          decisions: z.number(),
          updated: z.string(),
          author: z.string(),
          test_status: z.string(),
          test_tone: z.string(),
        }),
      ),
    })
    .optional(),
  watch: z
    .object({
      title: z.string(),
      cta: z.string(),
      items: z.array(z.object({ title: z.string(), detail: z.string(), tone: z.string() })),
    })
    .optional(),
  quick: z
    .object({
      title: z.string(),
      items: z.array(z.object({ label: z.string(), href: z.string() })),
    })
    .optional(),
  coverage: z
    .object({
      title: z.string(),
      items: z.array(z.object({ label: z.string(), pct: z.number(), tone: z.string() })),
    })
    .optional(),
  details: z
    .array(
      z.object({
        key: z.string(),
        name: z.string(),
        id: z.string(),
        status: z.string(),
        status_tone: z.string(),
        enabled: z.boolean(),
        tabs: z.array(z.string()),
        description: z.string(),
        fields: z.array(
          z.object({
            label: z.string(),
            value: z.string(),
            tone: z.string().nullable().optional(),
          }),
        ),
        config_title: z.string(),
        config_cta: z.string(),
        config: z.array(z.object({ label: z.string(), value: z.string() })),
        rbac_title: z.string(),
        rbac_cta: z.string(),
        rbac: z.array(z.object({ role: z.string(), access: z.string() })),
        rbac_more: z.string(),
        toggle_label: z.string(),
        policy_updated: z.string(),
      }),
    )
    .optional(),
});
export type AgentGardeFous = z.infer<typeof AgentGardeFousSchema>;

export const AgentPromptsSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  actions: z.object({ asof: z.string(), create: z.string() }).optional(),
  subtabs: z.array(z.string()).optional(),
  snapshot: z
    .object({
      tag: z.string(),
      label: z.string(),
      updated_label: z.string(),
      updated: z.string(),
      updated_rel: z.string(),
      version_label: z.string(),
      version: z.string(),
      version_status: z.string(),
      evalset_label: z.string(),
      evalset: z.string(),
      coverage_label: z.string(),
      coverage: z.number(),
      coverage_tone: z.string(),
      asof: z.string(),
      compare: z.string(),
    })
    .optional(),
  kpis: z
    .array(
      z.object({
        key: z.string(),
        label: z.string(),
        value: z.string(),
        delta: z.string(),
        good: z.boolean(),
        gauge: z.number().nullable(),
      }),
    )
    .optional(),
  filters: z
    .object({
      search: z.string(),
      selects: z.array(z.object({ label: z.string(), value: z.string() })),
      var_options: z.array(z.object({ value: z.string(), label: z.string() })).optional(),
      more: z.string(),
    })
    .optional(),
  table: z
    .object({
      columns: z.array(z.string()),
      count: z.string(),
      pages: z.number(),
      rows: z.array(
        z.object({
          key: z.string(),
          name: z.string(),
          type: z.string(),
          type_tone: z.string(),
          status: z.string(),
          status_tone: z.string(),
          version: z.string(),
          langs_present: z.array(z.string()),
          quality: z.string(),
          quality_tone: z.string(),
          vars_count: z.number(),
          updated: z.string(),
          owner: z.string(),
          tests: z.string(),
          fr_len: z.number(),
        }),
      ),
    })
    .optional(),
  watch: z
    .object({
      title: z.string(),
      cta: z.string(),
      items: z.array(z.object({ title: z.string(), detail: z.string(), tone: z.string() })),
    })
    .optional(),
  quick: z
    .object({
      title: z.string(),
      items: z.array(z.object({ label: z.string(), href: z.string() })),
    })
    .optional(),
  by_type: z
    .object({
      title: z.string(),
      cta: z.string(),
      items: z.array(
        z.object({ label: z.string(), value: z.string(), pct: z.number(), tone: z.string() }),
      ),
    })
    .optional(),
  details: z
    .array(
      z.object({
        key: z.string(),
        name: z.string(),
        id: z.string(),
        status: z.string(),
        status_tone: z.string(),
        tabs: z.array(z.string()),
        description: z.string(),
        fields: z.array(
          z.object({ label: z.string(), value: z.string(), tone: z.string().optional() }),
        ),
        content: z.array(z.object({ lang: z.string(), text: z.string() })),
        tags_label: z.string(),
        tags: z.array(z.string()),
        config_title: z.string(),
        config_cta: z.string(),
        config: z.array(z.object({ label: z.string(), value: z.string() })),
        rbac_title: z.string(),
        rbac_cta: z.string(),
        rbac: z.array(z.object({ role: z.string(), access: z.string() })),
        rbac_more: z.string(),
        info_title: z.string(),
        info: z.array(z.object({ label: z.string(), value: z.string() })),
      }),
    )
    .optional(),
  footer: z.array(z.object({ label: z.string(), value: z.string() })).optional(),
});
export type AgentPrompts = z.infer<typeof AgentPromptsSchema>;

export const AgentEvaluationsSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  actions: z.object({ asof: z.string(), create: z.string() }).optional(),
  subtabs: z.array(z.string()).optional(),
  snapshot: z
    .object({
      tag: z.string(),
      label: z.string(),
      updated_label: z.string(),
      updated: z.string(),
      updated_rel: z.string(),
      version_label: z.string(),
      version: z.string(),
      version_status: z.string(),
      evalset_label: z.string(),
      evalset: z.string(),
      coverage_label: z.string(),
      coverage: z.number(),
      coverage_tone: z.string(),
      asof: z.string(),
      compare: z.string(),
    })
    .optional(),
  kpis: z
    .array(
      z.object({
        key: z.string(),
        label: z.string(),
        value: z.string(),
        scale: z.string(),
        note: z.string(),
        note_tone: z.string(),
        delta: z.string(),
        delta_tone: z.string(),
        gauge: z.number().nullable(),
      }),
    )
    .optional(),
  meta: z
    .object({
      model: z.string(),
      catalogue_version: z.string(),
      languages: z.string(),
      score10: z.string(),
      escalations: z.number(),
      tool_invocations: z.number(),
      rbac: z.array(z.object({ role: z.string(), access: z.string() })),
    })
    .optional(),
  detail_labels: z
    .object({
      eyebrow: z.string(),
      tabs: z.array(z.string()),
      results_title: z.string(),
      results_cta: z.string(),
      rbac_title: z.string(),
      config_title: z.string(),
      info_title: z.string(),
      activity_title: z.string(),
    })
    .optional(),
  filters: z
    .object({
      search: z.string(),
      options: z.object({
        type: z.array(z.object({ key: z.string(), label: z.string() })),
        quality: z.array(z.object({ key: z.string(), label: z.string() })),
        halluc: z.array(z.object({ key: z.string(), label: z.string() })),
      }),
    })
    .optional(),
  table: z
    .object({
      columns: z.array(z.string()),
      total: z.number(),
      rows: z.array(
        z.object({
          name: z.string(),
          type: z.string(),
          type_tone: z.string(),
          status: z.string(),
          status_tone: z.string(),
          version: z.string(),
          score: z.string(),
          score_num: z.number(),
          success: z.string(),
          halluc: z.string(),
          last_run: z.string(),
          owner: z.string(),
          tests: z.string(),
          category_key: z.string(),
          quality_key: z.string(),
          quality_label: z.string(),
          is_fact: z.boolean(),
          passed: z.number(),
          total: z.number(),
          failed: z.number(),
          pass_rate: z.number(),
        }),
      ),
    })
    .optional(),
  watch: z
    .object({
      title: z.string(),
      cta: z.string(),
      cta_href: z.string().optional(),
      items: z.array(z.object({ title: z.string(), detail: z.string(), tone: z.string() })),
    })
    .optional(),
  quick: z
    .object({
      title: z.string(),
      items: z.array(z.object({ key: z.string(), label: z.string() })),
    })
    .optional(),
  trend: z
    .object({
      title: z.string(),
      value: z.string(),
      scale: z.string(),
      legend: z.string(),
      series: z.array(z.number()),
    })
    .optional(),
});
export type AgentEvaluations = z.infer<typeof AgentEvaluationsSchema>;

export const AgentHistoriqueSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  actions: z.object({ export: z.string(), compare: z.string(), create: z.string() }).optional(),
  subtabs: z.array(z.string()).optional(),
  kpis: z
    .array(
      z.object({
        key: z.string(),
        label: z.string(),
        value: z.string(),
        delta: z.string(),
        delta_tone: z.string(),
        tone: z.string(),
        series: z.array(z.number()),
      }),
    )
    .optional(),
  meta: z.object({ model: z.string(), catalogue_version: z.string() }).optional(),
  detail_labels: z
    .object({
      eyebrow: z.string(),
      tabs: z.array(z.string()),
      config_title: z.string(),
      eval_title: z.string(),
      eval_cta: z.string(),
      info_title: z.string(),
      messages_title: z.string(),
      question_label: z.string(),
      response_label: z.string(),
      activity_title: z.string(),
    })
    .optional(),
  filters: z
    .object({
      search: z.string(),
      options: z.object({
        category: z.array(z.object({ key: z.string(), label: z.string() })),
        lang: z.array(z.object({ key: z.string(), label: z.string() })),
        status: z.array(z.object({ key: z.string(), label: z.string() })),
        score: z.array(z.object({ key: z.string(), label: z.string() })),
      }),
    })
    .optional(),
  table: z
    .object({
      columns: z.array(z.string()),
      total: z.number(),
      rows: z.array(
        z.object({
          sid: z.string(),
          user: z.string(),
          agent: z.string(),
          start: z.string(),
          start_ts: z.string(),
          messages: z.string(),
          score: z.string(),
          score_num: z.number(),
          score_tone: z.string(),
          status: z.string(),
          status_tone: z.string(),
          latency: z.string(),
          latency_ms: z.number(),
          tokens: z.string(),
          tokens_num: z.number(),
          case_id: z.string(),
          category_key: z.string(),
          category_label: z.string(),
          lang: z.string(),
          passed: z.boolean(),
          escalation: z.boolean(),
          tools_count: z.number(),
          input_tokens: z.number(),
          output_tokens: z.number(),
          question: z.string(),
          response: z.string(),
        }),
      ),
    })
    .optional(),
  trend: z
    .object({
      title: z.string(),
      control: z.string(),
      series: z.array(z.number()),
      prev: z.array(z.number()),
      legend: z.string(),
      legend_prev: z.string(),
    })
    .optional(),
  by_agent: z
    .object({
      title: z.string(),
      cta: z.string(),
      cta_href: z.string().optional(),
      items: z.array(
        z.object({ label: z.string(), value: z.string(), pct: z.number(), share: z.string() }),
      ),
    })
    .optional(),
  scores: z
    .object({
      title: z.string(),
      center: z.string(),
      center_label: z.string(),
      segments: z.array(
        z.object({
          label: z.string(),
          value: z.string(),
          share: z.string(),
          pct: z.number(),
          tone: z.string(),
        }),
      ),
    })
    .optional(),
  success: z
    .object({
      title: z.string(),
      gauge: z.number(),
      value: z.string(),
      note: z.string(),
      cta: z.string(),
      cta_href: z.string().optional(),
    })
    .optional(),
  watch: z
    .object({
      title: z.string(),
      cta: z.string(),
      cta_href: z.string().optional(),
      items: z.array(z.object({ title: z.string(), detail: z.string(), tone: z.string() })),
    })
    .optional(),
  quick: z
    .object({
      title: z.string(),
      items: z.array(z.object({ key: z.string(), label: z.string() })),
    })
    .optional(),
});
export type AgentHistorique = z.infer<typeof AgentHistoriqueSchema>;

// Conversation session detail — turn-by-turn with per-turn agent attribution.
export const SessionDetailSchema = z.object({
  available: z.boolean(),
  conversation_id: z.string().optional(),
  title: z.string().optional(),
  spans_agents: z.boolean().optional(),
  agents: z.array(z.object({ id: z.string(), name: z.string() })).optional(),
  handoffs: z
    .array(
      z.object({
        from: z.string(),
        from_name: z.string(),
        to: z.string(),
        to_name: z.string(),
        reason: z.string(),
      }),
    )
    .optional(),
  turns: z
    .array(
      z.object({
        turn: z.number(),
        agent_id: z.string(),
        agent_name: z.string(),
        question: z.string(),
        answer: z.string(),
        time: z.string(),
        routing_reason: z.string().optional(),
      }),
    )
    .optional(),
  stats: z.object({ turns: z.number(), agents: z.number() }).optional(),
});
export type SessionDetail = z.infer<typeof SessionDetailSchema>;
