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
});
export type ChatCitation = z.infer<typeof ChatCitationSchema>;

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
});
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

export const AuditPageSchema = z.object({
  entries: z.array(AuditEntrySchema),
  cursor: z.number().int().nonnegative(),
  has_more: z.boolean(),
});
export type AuditPage = z.infer<typeof AuditPageSchema>;

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
// Observability assurance
// ---------------------------------------------------------------------------

export const ExporterStatusSchema = z.object({
  collector_required: z.boolean(),
  collector_configured: z.boolean(),
  langfuse_enabled: z.boolean(),
  langfuse_configured: z.boolean(),
  primary_backend: z.string(),
  evidence_enabled: z.boolean(),
  evidence_signing_enabled: z.boolean(),
  raw_prompts_export: z.boolean(),
  pii_export: z.boolean(),
});
export type ExporterStatus = z.infer<typeof ExporterStatusSchema>;

export const LLMOpsStatusSchema = z.object({
  enabled: z.boolean(),
  configured: z.boolean(),
  credentials_configured: z.boolean(),
  status: z.string(),
  host: z.string().nullable(),
  project: z.string(),
  ingestion_mode: z.string(),
  role: z.string(),
});
export type LLMOpsStatus = z.infer<typeof LLMOpsStatusSchema>;

export const AssuranceStatusSchema = z.object({
  target_level: z.string(),
  current_level: z.string(),
  completeness: z.number().min(0).max(1),
  proof_consensus: z.number().min(0).max(1),
  proof_slo_status: z.string(),
  missing_controls: z.array(z.string()),
});
export type AssuranceStatus = z.infer<typeof AssuranceStatusSchema>;

export const EvidenceSummarySchema = z.object({
  evidence_id: z.string().nullable(),
  created_at: z.string().nullable(),
  turn_id: z.string().nullable(),
  profile: z.string().nullable(),
  assurance_level: z.string().nullable(),
  trace_id: z.string().nullable().default(null),
  trace_url: z.string().nullable().default(null),
  model: z.string().nullable().default(null),
  language: z.string().nullable().default(null),
  citation_count: z.number().int().nonnegative().default(0),
  retrieval_hit_count: z.number().int().nonnegative().default(0),
  proof_quality: z.string().nullable(),
  proof_consensus: z.string().nullable(),
  privacy_status: z.string().nullable(),
  evidence_gaps: z.array(z.string()).default([]),
});
export type EvidenceSummary = z.infer<typeof EvidenceSummarySchema>;

export const OperatorLinkSchema = z.object({
  key: z.string(),
  label: z.string(),
  url: z.string().nullable(),
  status: z.string(),
  role: z.string(),
});
export type OperatorLink = z.infer<typeof OperatorLinkSchema>;

export const TraceSummarySchema = z.object({
  recent_count: z.number().int().nonnegative(),
  traceable_count: z.number().int().nonnegative(),
  complete_count: z.number().int().nonnegative(),
  degraded_count: z.number().int().nonnegative(),
  latest_trace_id: z.string().nullable(),
  latest_trace_url: z.string().nullable(),
  latest_evidence_id: z.string().nullable(),
  latest_created_at: z.string().nullable(),
  gap_codes: z.array(z.string()),
});
export type TraceSummary = z.infer<typeof TraceSummarySchema>;

export const ObservabilityStatusSchema = z.object({
  profile: z.string(),
  assurance_level: z.string(),
  status: z.string(),
  exporters: ExporterStatusSchema,
  llmops: LLMOpsStatusSchema,
  operator_links: z.array(OperatorLinkSchema).default([]),
  trace_summary: TraceSummarySchema,
  assurance: AssuranceStatusSchema,
  recent_evidence: z.array(EvidenceSummarySchema),
  allowed_attribute_count: z.number().int().nonnegative(),
  forbidden_attribute_count: z.number().int().nonnegative(),
  low_cardinality_metric_labels: z.array(z.string()),
  prompt_family: z.string(),
  prompt_version: z.string(),
  dataset_id: z.string().nullable(),
  experiment_id: z.string().nullable(),
  experiment_variant: z.string().nullable(),
  warnings: z.array(z.string()),
});
export type ObservabilityStatus = z.infer<typeof ObservabilityStatusSchema>;

export const EvidenceBundleResponseSchema = z.object({
  evidence_id: z.string(),
  created_at: z.string(),
  turn_id: z.string(),
  profile: z.string(),
  assurance_level: z.string(),
  proof_quality: z.string(),
  proof_consensus: z.string(),
  privacy_status: z.string(),
  signature: z.string().nullable(),
  evidence_gaps: z.array(z.string()).default([]),
  persisted: z.boolean().optional(),
});
export type EvidenceBundleResponse = z.infer<typeof EvidenceBundleResponseSchema>;

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
