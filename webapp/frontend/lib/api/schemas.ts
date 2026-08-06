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
        z.object({
          label: z.string(),
          value: z.string(),
          scale: z.string(),
          tone: z.string(),
        }),
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
        z.object({
          name: z.string(),
          status: z.string(),
          tone: z.string(),
          latency: z.string(),
        }),
      ),
    })
    .optional(),
  guardrails: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({
          name: z.string(),
          status: z.string(),
          tone: z.string(),
          detail: z.string(),
        }),
      ),
    })
    .optional(),
  // XT-01 waterfall — real per-node spans (ADR 0010 #4), laid end-to-end in
  // execution order: cumulative start_ms, real duration_ms, total = sum, status
  // derived from the turn's guard decisions. No fabricated stage or ms.
  trace: z
    .object({
      title: z.string(),
      total_ms: z.number(),
      count: z.number().int().nonnegative(),
      spans: z.array(
        z.object({
          key: z.string(),
          label: z.string(),
          start_ms: z.number(),
          duration_ms: z.number(),
          status: z.string(),
        }),
      ),
    })
    .optional(),
  tokens: z.number().int().nonnegative().optional(),
  // ── Console Debug surfaces (real per-turn introspection) ────────────────
  // #1 — the exact assembled LLM message list (system + injected memory +
  // verbatim turns + final synthesis user content).
  prompt: z
    .object({
      title: z.string(),
      messages: z.array(z.object({ role: z.string(), content: z.string() })),
      message_count: z.number().int().nonnegative(),
      char_count: z.number().int().nonnegative(),
    })
    .optional(),
  // #2 — the injected memory context (summary, entity ledger, long-term facts).
  memory: z
    .object({
      title: z.string(),
      summary: z.string().nullable(),
      entities: z.array(z.string()),
      long_term: z.array(z.string()),
      recent_verbatim: z.number().int().nonnegative(),
      backend: z.string(),
    })
    .optional(),
  // #3 — the routing decision plus the planner's plan and rationale.
  routing: z
    .object({
      title: z.string(),
      agent_id: z.string(),
      reason: z.string(),
      handoff: z.boolean(),
      from_agent: z.string().nullable(),
      plan: z.array(z.string()),
      plan_rationale: z.string().nullable(),
    })
    .optional(),
  // #4 — real token counts, latency, and indicative cost.
  usage: z
    .object({
      title: z.string(),
      input_tokens: z.number().int().nonnegative(),
      output_tokens: z.number().int().nonnegative(),
      total_tokens: z.number().int().nonnegative(),
      latency_ms: z.number(),
      estimated_cost_eur: z.number(),
      model: z.string(),
      provider: z.string(),
      // ADR 0031 — the sampling that actually served this turn (seam-resolved;
      // only SET parameters appear). Optional → older payloads stay valid.
      sampling: z.record(z.string(), z.number()).optional(),
      // ADR 0032 — the behaviour style (directive slugs) and hard cap that
      // served this turn. Optional → older payloads stay valid.
      style: z.record(z.string(), z.string()).optional(),
      max_output_tokens: z.number().int().nullable().optional(),
    })
    .optional(),
  // #5 — the reviewer's grounding/coverage/guard split behind the composite.
  reviewer: z
    .object({
      title: z.string(),
      confidence: z.number().nullable(),
      grounding: z.number().nullable(),
      coverage: z.number().nullable(),
      guard: z.number().nullable(),
      needs_escalation: z.boolean(),
      reason: z.string().nullable(),
      // ADR 0033 — the escalation bar this turn was judged against.
      threshold: z.number().nullable().optional(),
    })
    .optional(),
  // #6 — detected language and its confidence.
  language: z
    .object({
      title: z.string(),
      detected: z.string(),
      confidence: z.number().nullable(),
      pinned: z.boolean(),
    })
    .optional(),
  // #7 — the worker draft versus the final user-facing response.
  draft: z
    .object({
      title: z.string(),
      draft: z.string().nullable(),
      draft_label: z.string(),
      final: z.string(),
      changed: z.boolean(),
      draft_chars: z.number().int().nonnegative(),
      final_chars: z.number().int().nonnegative(),
    })
    .optional(),
  // #8 — the effective sandbox config that actually ran this turn.
  config: z
    .object({
      title: z.string(),
      model: z.string(),
      model_source: z.string(),
      system_prompt_override: z.boolean(),
      guard_overrides: z.array(z.string()),
    })
    .optional(),
});
export type ChatDebug = z.infer<typeof ChatDebugSchema>;
export type ChatTrace = NonNullable<ChatDebug["trace"]>;

export const ChatStartEventSchema = z.object({
  conversation_id: z.string().uuid(),
  turn_id: z.string().uuid(),
  /**
   * Signed capability letting THIS browser re-read THIS conversation (audit 2026-07-12,
   * F-4). Optional so an older agent still streams; without it the widget simply cannot
   * resume and starts a fresh conversation, which is the safe direction.
   */
  resume_token: z.string().optional(),
});

/** The caller's OWN transcript, replayed against the resume capability (GET /session/transcript). */
export const OwnTranscriptSchema = z.object({
  conversation_id: z.string(),
  messages: z.array(z.object({ role: z.string(), content: z.string() })),
});
export type OwnTranscript = z.infer<typeof OwnTranscriptSchema>;

export const ChatEndEventSchema = z.object({
  conversation_id: z.string().uuid(),
  turn_id: z.string().uuid(),
  language: LocaleSchema,
  final_response: z.string(),
  needs_escalation: z.boolean(),
  confidence: z.number().min(0).max(1).nullable(),
  citations: z.array(ChatCitationSchema),
  finish_reason: z.enum(["complete", "escalated", "error"]),
  confirmation_required: z
    .object({
      tool: z.literal("card_block"),
      card_last_four: z.string().regex(/^\d{4}$/),
      // Signed proof the server offered THIS action for approval. Echoed back on the
      // confirming turn; without it the guard denies, exactly as it does for a first ask.
      confirmation_token: z.string(),
    })
    .nullable()
    .optional(),
  debug: ChatDebugSchema.optional(),
});
export type ChatEndEvent = z.infer<typeof ChatEndEventSchema>;

/**
 * A guard replaced a streamed answer after the fact. Two reasons, both post-hoc because the
 * check needs the whole answer, so on a streaming transport it can only correct — never
 * pre-empt: `ungrounded` (the grounding guard, claims the corpus could not back) and `egress`
 * (the outbound egress guard, ADR 0049 — limes masked PII the regex leg missed, or withheld an
 * answer carrying a secret). What the record keeps is always the replacement; `unsupported` is
 * populated only for `ungrounded`.
 */
export const ChatCorrectionEventSchema = z.object({
  final_response: z.string(),
  reason: z.enum(["ungrounded", "egress"]),
  unsupported: z.array(z.string()).default([]),
});
export type ChatCorrectionEvent = z.infer<typeof ChatCorrectionEventSchema>;

export const ChatTokenEventSchema = z.object({
  token: z.string(),
});
export type ChatTokenEvent = z.infer<typeof ChatTokenEventSchema>;

// Sandbox console playground defaults (live system prompt + toggleable guard
// categories). Used to prefill the console's prompt editor and guard switches.
export const SandboxGuardCategorySchema = z.object({
  key: z.string(),
  label: z.string(),
  count: z.number(),
  detail: z.string(),
});
export const SandboxConfigSchema = z.object({
  available: z.boolean(),
  language: z.string().optional(),
  system_prompt: z.string().default(""),
  guard_categories: z.array(SandboxGuardCategorySchema).default([]),
});
export type SandboxConfig = z.infer<typeof SandboxConfigSchema>;

export const ChatErrorEventSchema = z.object({
  error: z.string(),
});

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export const AuditOutcomeSchema = z.enum(["allowed", "denied", "error"]);
export type AuditOutcome = z.infer<typeof AuditOutcomeSchema>;
export const AuditEventTypeSchema = z.enum(["guard", "tool", "memory", "governance", "other"]);
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
  // No `.default()` on either — the same rule as the backend model, for the same reason, on the
  // plane where it is easiest to forget. `.default("audit-log")` meant that a ledger entry which
  // arrived WITHOUT an author was rendered in the Journal's author column as "audit-log": the
  // frontend manufacturing an attribution the backend never made. A missing author must reach
  // the eye as missing. The backend always sends one (`_UNRECORDED_ACTOR` when the entry has
  // none), so this now fails loudly at parse time if that ever stops being true — which is the
  // point: a schema that fills in a plausible name cannot tell you it stopped being true.
  actor: z.string(),
  actor_role: AuditActorRoleSchema,
  scope: z.string().default("global"),
  object_label: z.string().default("audit event"),
  policy_rule: z.string().nullable().optional(),
  proof_ref: z.string().nullable().optional(),
  agent_id: z.string().nullable().optional(),
});
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

export const AuditPageSchema = z.object({
  entries: z.array(AuditEntrySchema),
  cursor: z.number().int().nonnegative(),
  has_more: z.boolean(),
});
export type AuditPage = z.infer<typeof AuditPageSchema>;

export const AuditIntegritySchema = z.object({
  verified: z.boolean(), // back-compat alias of content_integrity (tamper-evidence)
  length: z.number().int(),
  broken_at: z.number().int().nullable().default(null),
  // TESS-LEDGER-001 — tree-aware: content integrity (no tampering) is distinct from total order.
  content_integrity: z.boolean().optional(),
  linear: z.boolean().default(true),
  fork_count: z.number().int().default(0),
  orphan_count: z.number().int().default(0),
  attested: z.boolean().default(false),
  // Verification provenance. Content integrity is checked INCREMENTALLY against a checkpoint (the
  // ledger is append-only, so a verified prefix stays verified). These three fields are what stop
  // that from being an assumption dressed as a proof: the badge says when the WHOLE chain was last
  // walked, and how many entries have been verified incrementally since. Null in file mode, where
  // every read walks the whole journal anyway.
  full_verified_at: z.string().nullable().default(null),
  entries_since_full: z.number().int().default(0),
  checkpoint_used: z.boolean().default(false),
  // Hica external seal facet (ADR 0015 §Amendment 3 / §Correction 3c). `badge` is the register §9
  // opposability verdict, computed live from tree + seal — never stored, never cosmetic.
  seal_state: z
    .enum(["absent", "verified", "stale", "unverifiable", "divergent"])
    .default("absent"),
  seal_provider: z.string().nullable().default(null),
  seal_qualified: z.boolean().default(false),
  sealed_at: z.string().nullable().default(null),
  sealed_head: z.string().nullable().default(null),
  badge: z
    .enum(["non_scelle", "scelle_opposable", "scelle_non_qualifie", "integrite_partielle"])
    .default("integrite_partielle"),
});
export type AuditIntegrity = z.infer<typeof AuditIntegritySchema>;

// Guard-activity aggregate for the public launcher band (ADR 0009): user turns
// checked and denials recorded since local midnight, each from its own witness
// (transcript / audit trail). `available: false` carries no counters — the band
// renders "compteurs indisponibles", never a fabricated zero.
export const GuardActivitySchema = z.object({
  available: z.boolean(),
  checked_today: z.number().int().nonnegative().optional(),
  blocked_today: z.number().int().nonnegative().optional(),
  since: z.string().optional(),
});
export type GuardActivity = z.infer<typeof GuardActivitySchema>;

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
  // Real deployment environment (mono-env). Optional → an older payload renders
  // an honest-empty env badge rather than a fabricated value.
  environment: z.string().optional(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

/**
 * The stack's components as `tessera.preflight` sees them.
 *
 * `verdict` has THREE states on purpose. `blind` — the probe could not look at all — is
 * neither `ok` nor `fail`, and collapsing it into either is the failure ADR 0026 is about.
 * `observed_at` is the instant the probe ran, not the instant of the request: the backend
 * caches it, and a component list that cannot say when it last looked invites "now".
 */
export const ComponentCheckSchema = z.object({
  name: z.string(),
  /**
   * `stack` — one of the twelve components the deployment runs (Redis, ClickHouse, Postgres,
   * MinIO, …). `precondition` — what the agent process itself needs to serve a turn. Two
   * different questions: Grafana being down is not the agent being broken, and a surface that
   * merges them tells the operator to look in the wrong place.
   */
  group: z.enum(["stack", "precondition"]),
  verdict: z.enum(["ok", "fail", "blind", "skip"]),
  /** What came BACK, in the probe's own words. The evidence — never rewritten. */
  detail: z.string(),
  /**
   * What the thing IS (stack rows only; a precondition is not a thing).
   *
   * Its own field because it used to share one with the question below, under a single heading:
   * a stack row showed its role there and a precondition row showed what was asked. Two
   * meanings, one column.
   */
  role: z.string().default(""),
  /** What was PUT TO it — derived for a stack component, declared for a precondition. */
  asked: z.string().default(""),
  /**
   * What the probe FOUND, as a code — so the answer can be said in the reader's language.
   *
   * `postgres:5432 accepts connections` is not the machine talking; it is our own sentence,
   * written in `stack_components.py`, and it was rendered verbatim under a French heading.
   * Prose we wrote can be translated. What the machine said travels in `raw` and never is.
   * Empty for a precondition: preflight is a CLI witness whose line is read in a terminal, and
   * paraphrasing it here would make the page and the terminal disagree about one check.
   */
  outcome: z.string().default(""),
  /** What was contacted — a host:port or a URL. An address, so never translated. */
  address: z.string().default(""),
  /** The machine's own words: an errno, an HTTP status. Never rewritten. */
  raw: z.string().default(""),
  /** Legacy alias of `asked`, kept so an older client renders something rather than nothing. */
  interrogates: z.string(),
});
/**
 * A capability's standing — the same three-valued alphabet the probe speaks, deliberately.
 * `cannot_say` is not `lost`: an operator restarts a component for one and questions their own
 * vantage point for the other.
 */
export const ConsequenceStateSchema = z.enum(["served", "lost", "cannot_say"]);
export type ConsequenceState = z.infer<typeof ConsequenceStateSchema>;

/** What travels an edge of the chain. Four kinds, because they fail independently. */
export const ChainSignalSchema = z.enum(["traces", "metrics", "events", "state"]);
export type ChainSignal = z.infer<typeof ChainSignalSchema>;

export const ChainNodeSchema = z.object({
  key: z.string(),
  stage: z.enum(["emitter", "pipeline", "store", "viewer"]),
  carries: z.array(ChainSignalSchema),
  verdict: z.enum(["ok", "fail", "blind", "skip"]),
  /**
   * True for the emitter alone: nothing probes it from outside, because this very response is
   * its proof. Carried rather than inferred so the UI can say why one node cannot go red.
   */
  self_evident: z.boolean(),
});
export type ChainNode = z.infer<typeof ChainNodeSchema>;

export const ChainEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  signal: ChainSignalSchema,
  /** The config file that wires this edge — the drawing's evidence, reachable by the reader. */
  declared_in: z.string(),
  /** Non-null when the edge exists only in one deployment profile (`remote`). */
  profile: z.string().nullable(),
});
export type ChainEdge = z.infer<typeof ChainEdgeSchema>;

/**
 * What the cockpit stops being able to answer when a store goes quiet.
 *
 * The capability is declared (`reads` cites the module that queries the store); `state` is
 * computed from the live probe. Keeping the two apart is the point: a page that states a
 * consequence it did not measure is exactly the over-claim this project forbids.
 */
export const ConsequenceSchema = z.object({
  key: z.string(),
  needs: z.array(z.string()),
  reads: z.string(),
  /** True when losing it can BLOCK an agent rather than merely blank a chart. */
  gates_agents: z.boolean(),
  state: ConsequenceStateSchema,
  /** Which dependency is responsible — so the row names a component instead of a puzzle. */
  because: z.array(z.string()),
  /**
   * The dependencies whose verdict included an ADAPTER-LEVEL read this cycle (ADR 0052 Am.1.3)
   * — the socket is the neighbourhood, the read is the thing. Named so « assurée » over a
   * socket-only check cannot be mistaken for the stronger claim.
   */
  checked_by_read: z.array(z.string()),
});
export type Consequence = z.infer<typeof ConsequenceSchema>;

/**
 * Where a browser opens a tool.
 *
 * `loopback` is a FACT about the URL, not a recommendation: `127.0.0.1:13000` is Grafana on the
 * deployment host, and a reader on `tessera.example.com` clicking it reaches whatever happens to
 * run on their own port 13000. The caller pairs it with its own vantage point before offering a
 * live link — otherwise the page promises closed doors.
 */
export const ComponentLinkSchema = z.object({
  key: z.string(),
  url: z.string(),
  loopback: z.boolean(),
});
export type ComponentLink = z.infer<typeof ComponentLinkSchema>;

export type ComponentCheck = z.infer<typeof ComponentCheckSchema>;

export const ComponentsResponseSchema = z.object({
  observed_at: z.number(),
  verdict: z.enum(["clear", "fail", "blind"]),
  counts: z.object({
    total: z.number().int().nonnegative(),
    ok: z.number().int().nonnegative(),
    fail: z.number().int().nonnegative(),
    blind: z.number().int().nonnegative(),
    stack_total: z.number().int().nonnegative(),
    stack_ok: z.number().int().nonnegative(),
    /**
     * Counted per half, not just `ok`. A sentence that opens with the STACK ratio and then
     * continues with the whole-of-twenty `fail`/`blind` tally is two scopes in one claim — and
     * it reads correctly only while every precondition happens to be green.
     */
    stack_fail: z.number().int().nonnegative(),
    stack_blind: z.number().int().nonnegative(),
    precondition_total: z.number().int().nonnegative(),
    precondition_ok: z.number().int().nonnegative(),
  }),
  components: z.array(ComponentCheckSchema),
  chain: z.object({
    nodes: z.array(ChainNodeSchema),
    edges: z.array(ChainEdgeSchema),
    /** Per signal, whether it still gets from the agent to somewhere it is kept. */
    signals: z.record(ChainSignalSchema, ConsequenceStateSchema),
  }),
  consequences: z.array(ConsequenceSchema),
  links: z.array(ComponentLinkSchema),
});
export type ComponentsResponse = z.infer<typeof ComponentsResponseSchema>;

/**
 * Component verdicts over time — availability and, above all, CHANGES.
 *
 * Read `ok_ratio` only beside `observed_ratio`. The probe runs when the cockpit asks, so a
 * window is watched in patches: "99.9 % available" over a window watched for four of its
 * twenty-four hours is a true statement about four hours and a false one about the day. Both
 * numbers travel together, and the UI may not render one without the other.
 */
export const ComponentAvailabilitySchema = z.object({
  component: z.string(),
  seconds_by_verdict: z.record(z.string(), z.number()),
  observed_seconds: z.number(),
  /**
   * Observed time in which the probe reached a verdict about the component — `ok` or `fail`.
   * The denominator of `ok_ratio`: blind minutes are observed and decide nothing, so they are
   * excluded, and a window watched entirely through a blind spot has no availability at all.
   */
  decidable_seconds: z.number(),
  window_seconds: z.number(),
  observed_ratio: z.number(),
  /** Null when nothing was DECIDABLE — never 0 or 1, both of which are unsupported claims. */
  ok_ratio: z.number().nullable(),
});
export type ComponentAvailability = z.infer<typeof ComponentAvailabilitySchema>;

export const ComponentTransitionSchema = z.object({
  component: z.string(),
  from: z.string(),
  to: z.string(),
  at: z.string(),
  /**
   * True when the change was found after a hole in the record: `at` is then a DISCOVERY time,
   * not an occurrence time, and the wording has to say so.
   */
  after_gap: z.boolean(),
});
export type ComponentTransition = z.infer<typeof ComponentTransitionSchema>;

/** One uninterrupted stretch of one verdict, clipped to the requested window — what a timeline draws. */
export const ComponentPhaseSchema = z.object({
  component: z.string(),
  verdict: z.string(),
  since: z.string(),
  until: z.string(),
  n_observations: z.number().int().nonnegative(),
});
export type ComponentPhase = z.infer<typeof ComponentPhaseSchema>;

/**
 * The probe scheduler's heartbeat (ADR 0052 Am.1.1) — derived from the stamp the leader loop
 * actually writes, never from configuration. `never` = no beat has landed (the interval, when
 * present, is the announced intent); `stale` = the beats stopped, which is a dead leader loop
 * and a different repair from "not configured".
 */
export const ProbeSchedulerReportSchema = z.object({
  state: z.enum(["never", "active", "stale"]),
  interval_s: z.number().nullable(),
  last_run_at: z.string().nullable(),
});
export type ProbeSchedulerReport = z.infer<typeof ProbeSchedulerReportSchema>;

export const ComponentHistorySchema = z.object({
  window: z.object({ since: z.string(), until: z.string(), days: z.number() }),
  availability: z.array(ComponentAvailabilitySchema),
  /** The phases themselves — the totals above cannot say WHEN the fail was. */
  phases: z.array(ComponentPhaseSchema),
  probe: ProbeSchedulerReportSchema,
  transitions: z.array(ComponentTransitionSchema),
  continuity_window_s: z.number(),
});
export type ComponentHistory = z.infer<typeof ComponentHistorySchema>;

/**
 * Signal 92 — how much of the L1 span contract each agent actually stamps.
 *
 * `status` distinguishes the two ways a percentage can be absent, and they are not the same
 * fact: `no_evidence` is a store that answered "none", `unverifiable` is a store that did not
 * answer. Rendering the second as 0 % turns a ClickHouse outage into a fleet that instruments
 * nothing.
 */
export const AgentCoverageSchema = z.object({
  agent_id: z.string(),
  covered_pct: z.number().nullable(),
  missing_attributes: z.array(z.string()),
  required_attributes: z.array(z.string()),
  evidence_at: z.string().nullable(),
  /**
   * Four states, because absence has four causes and they are not the same finding.
   * `not_applicable` — this agent's manifest declares no business signals, so the evidence this
   * measurement is taken on does not exist for it and never will. Rendering that as
   * `no_evidence` reads as an instrumentation failure, which is how five correctly-behaving
   * agents came to be listed as emitting nothing while Prometheus showed them serving turns.
   */
  status: z.enum(["measured", "no_evidence", "not_applicable", "unverifiable"]),
  evidence_source: z.string(),
  measures: z.string(),
});
export type AgentCoverage = z.infer<typeof AgentCoverageSchema>;

export const InstrumentationCoverageSchema = z.object({
  observed_at: z.string(),
  blind: z.boolean(),
  required_attributes: z.array(z.string()),
  evidence_source: z.string(),
  measures: z.string(),
  agents: z.array(AgentCoverageSchema),
});
export type InstrumentationCoverage = z.infer<typeof InstrumentationCoverageSchema>;

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
  // The runner records the execution context per (case, language) and the report HOLDS it —
  // but zod strips what it does not declare, so omitting these silently emptied block 4 of the
  // case detail (tools, duration, tokens) while the JSON on disk had it all along. Nullable
  // rather than zero-defaulted: a report written before the runner recorded a duration has no
  // duration, and 0 ms would be a fabricated measurement.
  duration_ms: z.number().nullable().default(null),
  input_tokens: z.number().nullable().default(null),
  output_tokens: z.number().nullable().default(null),
  started_at: z.string().nullable().default(null),
  ended_at: z.string().nullable().default(null),
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
// The sweep, the floor, and the catalogue (spec §A1.4)
//
// With three models scored on one dataset, "latest" stops meaning anything — a single
// `latest.json` cannot represent a sweep, and the screen that read one was showing a
// three-week-old, three-case, zero-token run as if it were the current result. A SWEEP is
// N runs on ONE catalogue version. The screen reads the sweep; it never reads "a run".

/**
 * The committed null control (`eval/baselines/null-control.json`): what the deterministic
 * guard/router layer passes with NO model at all — 122 of 174. This is the FLOOR, and the
 * dashboard READS it (criterion 12). It is never recomputed here: a floor computed by the
 * surface that displays it would be marking its own homework.
 */
export const NullControlBaselineSchema = z.object({
  kind: z.literal("null_control"),
  model: z.string().nullable().optional(),
  catalogue_version: z.string().nullable().optional(),
  note: z.string().optional(),
  totals: z.object({ total: z.number().int(), passed: z.number().int() }),
  /** `{"<case_id>|<language>": passed}` — the harness's own key (`eval/ratchet.py::_key`). */
  verdicts: z.record(z.string(), z.boolean()),
});
export type NullControlBaseline = z.infer<typeof NullControlBaselineSchema>;

/**
 * What the catalogue MEASURES — `eval/baselines/discrimination.json`, written by
 * `eval.discrimination`.
 *
 * A pass rate says how well the model did. It cannot say whether a case tests the *model* at
 * all: the null control (no model, zero tokens) already passes 122 of the 174 runs, so most of
 * the score is the deterministic guard/router layer. Each run is therefore classified by what
 * it separates, measured over repeated passes of a strong and a weak model — never declared by
 * the case itself.
 *
 * Declare every field that is rendered: zod **strips undeclared keys in silence**, so a count
 * left out here would not throw, it would simply vanish and the tile would render a hole.
 */
/**
 * What the design could have DETECTED — the licence to report an absence.
 *
 * Mirrors `tessera.verdict.Power`. It is present iff the experiment could have rejected the null
 * *at all*; when it could not, the artefact carries a `blind_spot` instead, and no run in it may
 * be called dead or non-discriminating. That is not a display convention, it is enforced in the
 * type on the Python side: `NoEffect` cannot be constructed without a `Power`.
 */
export const DetectionPowerSchema = z.union([
  z.object({
    samples: z.number().int(),
    threshold: z.number(),
    best_achievable_p: z.number(),
    /** The smallest effect this design could have certified. Anything under it is CANNOT SAY. */
    minimum_detectable_effect: z.number(),
    effect_unit: z.string(),
  }),
  z.object({ blind_spot: z.string() }),
]);

export const CataloguePowerSchema = z.object({
  kind: z.literal("catalogue_power"),
  /** The case set this classification describes. A different one makes it VOID, not stale. */
  catalogue_version: z.string(),
  strong_model: z.string(),
  weak_model: z.string(),
  /** Passes per arm — the honesty of every p-value behind the counts. */
  strong_n: z.number().int(),
  weak_n: z.number().int(),
  alpha: z.number(),
  /** `alpha / runs` — the tightest step, and the level the detection power is quoted against. */
  threshold: z.number(),
  detection_power: DetectionPowerSchema,
  power: z.object({
    discriminating_cases: z.number().int(),
    discriminating_runs: z.number().int(),
    total_cases: z.number().int(),
    total_runs: z.number().int(),
    unstable_cases: z.number().int(),
    unstable_runs: z.number().int(),
    /** Holm certifies the ratchet's number; BH feeds the diagnosis. Both are published. */
    holm_runs: z.number().int(),
    bh_runs: z.number().int(),
    /** Runs BH certifies and Holm does not — what the ratchet's conservatism costs. */
    correction_gap: z.array(z.string()),
  }),
  /**
   * The three buckets, and they do not share a bucket.
   *
   * `fact` is observed (no p-value, no power — the null control is deterministic). `certified` is
   * an inference that survived the multiplicity correction. `cannot_say` is the honest output of a
   * test that could not see: **not dead, unknown**, and it is the distinction that keeps a
   * modest-but-real discriminator off a removal list.
   */
  bucket_counts: z.object({
    fact: z.number().int(),
    certified: z.number().int(),
    cannot_say: z.number().int(),
  }),
  case_counts: z.object({
    // FACT — observed.
    dead: z.number().int(),
    inverted: z.number().int(),
    saturated: z.number().int(),
    unreached: z.number().int(),
    // CERTIFIED — inferred, and it survived Holm.
    discriminating: z.number().int(),
    reversed: z.number().int(),
    // CANNOT SAY — underpowered. Never "no effect".
    underpowered: z.number().int(),
  }),
});
export type CataloguePower = z.infer<typeof CataloguePowerSchema>;

/** Why a case exists. The citation IS the proof the bench was not invented. */
export const EvalSourceReferenceSchema = z.object({
  citation: z.string(),
  url: z.string().optional(),
  urls: z.array(z.string()).default([]),
  notes: z.string().optional(),
});
export type EvalSourceReference = z.infer<typeof EvalSourceReferenceSchema>;

/** Every criterion the harness knows how to check (`eval/failures/_schema.json`). */
export const EvalPassCriteriaSchema = z.object({
  must_not_contain: z.array(z.string()).optional(),
  /** Claims the response must not ASSERT. Unlike `must_not_contain`, an occurrence inside a
   *  negated clause passes — a case whose forbidden wording is the wording its own prompt used
   *  cannot otherwise be refuted, because denying a claim means repeating it. */
  must_not_assert: z.array(z.string()).optional(),
  must_contain_any: z.array(z.string()).optional(),
  /** Regex alternatives of the SAME requirement as `must_contain_any` (ORed with it, not
   *  ANDed). German is verb-second: "Ich kann Ihnen X nicht nennen" contains no literal the
   *  catalogue spelled. Undeclared here, zod would strip the field and the case sheet would
   *  show a criterion the harness applied and the screen never mentioned. */
  must_contain_any_pattern: z.array(z.string()).optional(),
  must_not_match: z.array(z.string()).optional(),
  must_escalate: z.boolean().optional(),
  min_confidence: z.number().optional(),
  max_confidence: z.number().optional(),
  must_cite_source: z.boolean().optional(),
  must_not_invoke_tools: z.array(z.string()).optional(),
  must_invoke_tools: z.array(z.string()).optional(),
});
export type EvalPassCriteria = z.infer<typeof EvalPassCriteriaSchema>;

export const EvalPromptSchema = z.object({
  user: z.string(),
  system_override: z.string().optional(),
});
export type EvalPrompt = z.infer<typeof EvalPromptSchema>;

/** One failure case as the CATALOGUE defines it — a versioned artefact, never a result. */
export const EvalCaseSchema = z.object({
  id: z.string(),
  title: z.string(),
  category: z.string(),
  severity: z.enum(["critical", "standard"]).default("standard"),
  source_reference: EvalSourceReferenceSchema,
  languages: z.array(LocaleSchema),
  prompts: z.record(z.string(), EvalPromptSchema),
  expected_behavior: z.string(),
  pass_criteria: EvalPassCriteriaSchema.default({}),
  tags: z.array(z.string()).default([]),
});
export type EvalCase = z.infer<typeof EvalCaseSchema>;

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

export const BusinessEventClassificationSchema = z.object({
  observable: z.boolean().optional(),
  auditable: z.boolean().optional(),
  scoring_input: z.boolean().optional(),
  metric_input: z.boolean().optional(),
  cockpit_signal: z.boolean().optional(),
});

export const BusinessEventSchema = z.object({
  event_name: z.string(),
  timestamp: z.string(),
  agent_id: z.string(),
  conversation_id: z.string(),
  turn_id: z.string(),
  schema_version: z.string().optional(),
  event_version: z.number().optional(),
  version: z.number().optional(),
  workflow_id: z.string().nullable().optional(),
  capability_id: z.string().nullable().optional(),
  surface: z.string().nullable().optional(),
  language: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  environment: z.string().nullable().optional(),
  case_id: z.string().nullable().optional(),
  node_name: z.string().nullable().optional(),
  artifact_id: z.string().nullable().optional(),
  artifact_type: z.string().nullable().optional(),
  artifact_status: z.string().nullable().optional(),
  decision: z.string().nullable().optional(),
  reason_codes: z.array(z.string()).default([]),
  payload: z.record(z.string(), z.unknown()).default({}),
  actor: z.string().optional(),
  classification: BusinessEventClassificationSchema.optional(),
});
export type BusinessEvent = z.infer<typeof BusinessEventSchema>;

export const BusinessScoreSchema = z.object({
  metric: z.string(),
  score: z.number().nullable(),
  status: z.string(),
  reason: z.string(),
});
export type BusinessScore = z.infer<typeof BusinessScoreSchema>;

export const RecouvrementRunArtifactSchema = z.object({
  artifact_id: z.string(),
  artifact_type: z.string().nullable().optional(),
  artifact_status: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  generation_mode: z.string().nullable().optional(),
  template_id: z.string().nullable().optional(),
  template_version: z.string().nullable().optional(),
  no_message_sent: z.boolean().nullable().optional(),
  no_payment_initiated: z.boolean().nullable().optional(),
  no_payment_link_created: z.boolean().nullable().optional(),
  no_payment_link_sent: z.boolean().nullable().optional(),
  no_schedule_created: z.boolean().nullable().optional(),
  no_external_effect: z.boolean().nullable().optional(),
});
export type RecouvrementRunArtifact = z.infer<typeof RecouvrementRunArtifactSchema>;

export const RecouvrementRunDecisionSchema = z.object({
  event_name: z.string().nullable().optional(),
  decision: z.string().nullable().optional(),
  reason_codes: z.array(z.string()).default([]),
  rule_id: z.string().nullable().optional(),
  action_name: z.string().nullable().optional(),
  no_external_effect: z.boolean().nullable().optional(),
});
export type RecouvrementRunDecision = z.infer<typeof RecouvrementRunDecisionSchema>;

export const RecouvrementSensitiveActionSchema = z.object({
  event_name: z.string().nullable().optional(),
  action_name: z.string(),
  artifact_id: z.string().nullable().optional(),
  artifact_type: z.string().nullable().optional(),
  current_status: z.string().nullable().optional(),
  target_status: z.string().nullable().optional(),
  no_external_effect: z.boolean().nullable().optional(),
  requires_validation: z.boolean().nullable().optional(),
  reason_codes: z.array(z.string()).default([]),
});
export type RecouvrementSensitiveAction = z.infer<typeof RecouvrementSensitiveActionSchema>;

export const RecouvrementRunSchema = z.object({
  agent_id: z.string().nullable().optional(),
  workflow_id: z.string().nullable().optional(),
  capability_id: z.string().nullable().optional(),
  surface: z.string().nullable().optional(),
  case_id: z.string().nullable().optional(),
  conversation_id: z.string(),
  turn_id: z.string(),
  started_at: z.string().nullable().optional(),
  event_count: z.number().int(),
  timeline: z.array(BusinessEventSchema),
  artifacts: z.array(RecouvrementRunArtifactSchema),
  decisions: z.array(RecouvrementRunDecisionSchema),
  sensitive_actions: z.array(RecouvrementSensitiveActionSchema),
  scores: z.array(BusinessScoreSchema),
});
export type RecouvrementRun = z.infer<typeof RecouvrementRunSchema>;

export const RecouvrementRunsResponseSchema = z.object({
  runs: z.array(RecouvrementRunSchema),
  // `events` and `scores` describe the SAME runs as `runs` — they used not to, carrying the
  // whole unsliced read while `runs` honoured `limit`. `*_total` says what the bound dropped,
  // because a truncation nobody can see reads as coverage.
  events: z.array(BusinessEventSchema),
  scores: z.array(BusinessScoreSchema),
  events_total: z.number().int().optional(),
  runs_total: z.number().int().optional(),
  as_of: z.string().nullable().optional(),
  agent: z.string(),
  workflow_id: z.string().nullable().optional(),
  capability_id: z.string().nullable().optional(),
  conversation_id: z.string().nullable().optional(),
  turn_id: z.string().nullable().optional(),
  case_id: z.string().nullable().optional(),
});
export type RecouvrementRunsResponse = z.infer<typeof RecouvrementRunsResponseSchema>;

export const BusinessTrendPointSchema = z
  .object({
    bucket: z.string(),
    volume: z.number().optional(),
    value_pct: z.number().nullable().optional(),
    status: z.string().optional(),
  })
  .passthrough();
export type BusinessTrendPoint = z.infer<typeof BusinessTrendPointSchema>;

export const BusinessTrendSchema = z.object({
  available: z.boolean(),
  direction: z.string(),
  delta_pct: z.number().nullable().optional(),
  points: z.array(BusinessTrendPointSchema).default([]),
});
export type BusinessTrend = z.infer<typeof BusinessTrendSchema>;

export const BusinessCapabilityRowSchema = z.object({
  capability_id: z.string(),
  label_key: z.string().nullable().optional(),
  label: z.string().nullable().optional(),
  external_effect_level: z.string().nullable().optional(),
  volume: z.number().int(),
  conformity_pct: z.number().nullable().optional(),
  validation_required_pct: z.number().nullable().optional(),
  blocked_pct: z.number().nullable().optional(),
  external_effects_prevented: z.number().int(),
  trend: BusinessTrendSchema,
  event_count: z.number().int(),
});
export type BusinessCapabilityRow = z.infer<typeof BusinessCapabilityRowSchema>;

/** What the scorer actually saw for a signal (P3 item 18) — never inferred, may be all zeros. */
export const BusinessSignalEvidenceSchema = z.object({
  observed_runs: z.number().int().default(0),
  checks: z.number().int().default(0),
  last_checked_at: z.string().nullable().default(null),
});
export type BusinessSignalEvidence = z.infer<typeof BusinessSignalEvidenceSchema>;

export const BusinessSignalValueSchema = z.object({
  agent_id: z.string(),
  key: z.string(),
  source: z.string(),
  level: z.string(),
  unit: z.string(),
  aggregation: z.string(),
  dimensions: z.array(z.string()).default([]),
  engagement: z.string(),
  north_star: z.boolean().default(false),
  scorer: z.string().nullable().optional(),
  value: z.number().nullable().optional(),
  value_pct: z.number().nullable().optional(),
  status: z.string(),
  reason: z.string(),
  trend: BusinessTrendSchema,
  // Absent on a payload from a backend that predates item 18: the card then falls back to
  // the dash + reason, which is the honest reading of "we do not know".
  evidence: BusinessSignalEvidenceSchema.optional(),
});
export type BusinessSignalValue = z.infer<typeof BusinessSignalValueSchema>;

export const BusinessCapabilitiesResponseSchema = z.object({
  capabilities: z.array(BusinessCapabilityRowSchema),
  business_signals: z.array(BusinessSignalValueSchema).default([]),
  event_count: z.number().int(),
  as_of: z.string().nullable().optional(),
  agent: z.string(),
  workflow_id: z.string().nullable().optional(),
  conversation_id: z.string().nullable().optional(),
  turn_id: z.string().nullable().optional(),
  case_id: z.string().nullable().optional(),
  source: z.string(),
  fact: z.string(),
  // The DECLARED rung — what the manifest reaches. Kept under its historical name because
  // this page's question is a contract one; `computed_level` is the PROVEN rung the release
  // gate reads. They differ routinely, and a screen that shows one without naming it lets an
  // operator read a declaration as a measurement (found on the Métier page, 2026-08-05).
  observability_level: z.string().nullable().optional(),
  computed_level: z.string().nullable().optional(),
  // False when the business-event store did not answer: neither rung exists, and the page
  // must say it cannot see rather than render "level not yet reached".
  level_readable: z.boolean().default(true),
  required_level: z.string(),
  missing_requirements: z.array(z.string()).default([]),
  unknown_capability_id: z.string().optional(),
  unknown_capability_label: z.string().optional(),
});
export type BusinessCapabilitiesResponse = z.infer<typeof BusinessCapabilitiesResponseSchema>;

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

/** Honest bounds for the time-rail calendar: earliest real data → now. */
export const DataRangeSchema = z.object({
  start: z.string().nullable(),
  end: z.string(),
  n: z.number().int(),
});
export type DataRange = z.infer<typeof DataRangeSchema>;

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

export const ReliabilityErrorSliceSchema = z.object({
  label: z.string(),
  count: z.number().int(),
});
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
  // The instant opening the bucket — the only unambiguous identity a bucket has once a
  // window can be read hourly: 24 hourly buckets of one day all share the same `date`.
  bucket_start: z.string(),
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
  // Grain of `daily`, and the window it actually covers. Published rather than inferred:
  // the number of points alone cannot tell 24 hours from 24 days, and a control that
  // re-derives its own window from the item count collapses when the count surprises it.
  resolution: z.enum(["hour", "day"]).optional(),
  bucket_seconds: z.number().int().optional(),
  window_start: z.string().optional(),
  window_end: z.string().optional(),
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
  /** conformant | partial | non_conformant | na — `na` means it could not be MEASURED. */
  status: z.string(),
  value: z.number(),
  risk: z.string(),
  owner: z.string(),
  evidence_id: z.string(),
  /**
   * Why an `na` control has no value: "no-sample" (the probe ran over an empty window),
   * "read-failed" (it raised) or "no-reader" (nothing produces this signal). Null when the
   * control was measured. A dash on a compliance screen has to say why it is a dash.
   */
  unavailable: z.string().nullable().default(null),
  /** Observations behind `value`. Zero means the number is not a measurement. */
  n_samples: z.number().int().default(0),
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

export const BusinessLegalSignalSchema = z.object({
  agent_id: z.string(),
  agent_name: z.string(),
  key: z.string(),
  value_pct: z.number().nullable(),
  status: z.string(),
  reason: z.string(),
  source: z.string(),
  href: z.string(),
});
export type BusinessLegalSignal = z.infer<typeof BusinessLegalSignalSchema>;

// --- Conformite command-bar tabs (generic catalogue shape) ---------------

// Plain-language "what does this number mean?" text rendered as the ⓘ popover
// next to a KPI / panel / table title; populated grounded + localized by the
// backend (compliance_tabs.py). Optional so untouched tabs keep working.
export const TabExplainSchema = z.object({
  what: z.string(),
  how: z.string().nullable().optional(),
  source: z.string().nullable().optional(),
});
export type TabExplain = z.infer<typeof TabExplainSchema>;

export const TabKpiSchema = z.object({
  label: z.string(),
  value: z.string(),
  unit: z.string().nullable().optional(),
  sub: z.string().nullable().optional(),
  delta: z.string().nullable().optional(),
  delta_good: z.boolean().nullable().optional(),
  tone: z.string().nullable().optional(),
  explain: TabExplainSchema.nullable().optional(),
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
  explain: TabExplainSchema.nullable().optional(),
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
  explain: TabExplainSchema.nullable().optional(),
});
export type TabSection = z.infer<typeof TabSectionSchema>;

export const CatalogTabSchema = z.object({
  table_title: z.string(),
  table_explain: TabExplainSchema.nullable().optional(),
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
  business_legal_signals: z.array(BusinessLegalSignalSchema).optional(),
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
  agent_id: z.string().nullable().optional(),
  turn_id: z.string().nullable().optional(),
  // XT-01 — the S2 execution record. Every field is optional: a bundle
  // captured before the capture existed reads as "non capturé". Zod strips
  // undeclared keys, so each S2 field the lens reads MUST be declared here.
  prompt_messages: z
    .array(z.object({ role: z.string(), content: z.string() }))
    .nullable()
    .optional(),
  sampling: z.record(z.string(), z.number()).nullable().optional(),
  max_output_tokens: z.number().nullable().optional(),
  tool_calls: z
    .array(
      z.object({
        name: z.string(),
        node: z.string(),
        succeeded: z.boolean(),
        duration_ms: z.number(),
      }),
    )
    .nullable()
    .optional(),
  node_starts: z.record(z.string(), z.number()).nullable().optional(),
  reporter_ms: z.number().nullable().optional(),
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
  // A multilingual agent run has no single language. It used to arrive as the STRING "None"
  // (Python `str(None)`), which the table then had to special-case; it is now null.
  language: z.string().nullable(),
  total: z.number().int(),
  passed: z.number().int(),
  failed: z.number().int(),
  pass_rate: z.number(),
  est_cost_eur: z.number().nullable(),
  mean_latency_ms: z.number().nullable(),
  catalogue_version: z.string().nullable(),
  eval_set: z.string().nullable(),
  // When the verdicts in this row were decided, and by which ruler. A re-grade re-judges
  // recorded responses under moved criteria: it changes the pass rate without changing
  // run_at, so a screen that shows only run_at cannot say the numbers moved today.
  regraded_at: z.string().nullable(),
  grader_criteria_sha: z.string().nullable(),
  // The `case|language` runs whose verdict was CARRIED, not re-derived — a criterion the
  // recording cannot answer (max_confidence, must_cite_source). Non-empty means the sha above
  // is the rule that was applied, not a claim that it judged everything.
  grader_blind_runs: z.array(z.string()).default([]),
  superseded_copies: z.number().int(),
});
export type RunSummary = z.infer<typeof RunSummarySchema>;

export const RunRegistrySchema = z.object({
  n: z.number().int(),
  runs: z.array(RunSummarySchema),
  catalogue_cases: z.number().int(),
  catalogue_version: z.string().nullable(),
  models: z.array(z.string()),
  languages: z.array(z.string()),
  superseded: z.number().int(),
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

export const SkewReportSchema = z
  .object({
    query_model: z.string(),
    query_dimension: z.number().int().positive(),
    corpus_model: z.string(),
    corpus_dimension: z.number().int().positive(),
    dimension_mismatch: z.boolean(),
    model_mismatch: z.boolean(),
    skew: z.boolean(),
    severity: z.enum(["none", "soft", "hard", "unknown"]),
    reason: z.string(),
    corpus_known: z.boolean(),
    corpus_rows: z.number().int().nonnegative(),
    unfingerprinted_rows: z.number().int().nonnegative(),
    spaces: z.array(
      z.object({
        model: z.string(),
        dimension: z.number().int().positive(),
        rows: z.number().int().positive(),
      }),
    ),
  })
  .superRefine((report, context) => {
    const measuredRows = report.spaces.reduce((total, space) => total + space.rows, 0);
    if (measuredRows + report.unfingerprinted_rows !== report.corpus_rows) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "embedding evidence does not cover corpus rows exactly",
        path: ["corpus_rows"],
      });
    }
    if (report.corpus_known && report.unfingerprinted_rows !== 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "known corpus cannot contain unfingerprinted rows",
        path: ["corpus_known"],
      });
    }
    if (report.severity === "none" && !report.corpus_known) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "incomplete evidence cannot receive a clean verdict",
        path: ["severity"],
      });
    }
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
  /**
   * Signal families with an EMPTY sample. They cannot trigger, and their silence is not news.
   *
   * `n_triggered: 0` with `n_unmeasured: 0` is a quiet fleet. `n_triggered: 0` with
   * `n_unmeasured: 4` is a fleet nobody looked at. The digit is identical; only this tells
   * them apart, and until 2026-08-01 the cockpit rendered both as "aucun incident".
   */
  unmeasured: z.array(z.string()).default([]),
  n_unmeasured: z.number().int().default(0),
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
  // `false` when NO catalogue could be read. Not cosmetic: the route reported 100 % complete
  // in production for its whole life because it resolved the catalogues under `webapp/`, which
  // the agent image does not ship, swallowed the failures into `{}`, and divided by an empty
  // reference. A caller that renders a percentage without checking this is rendering that lie.
  available: z.boolean().default(true),
  reason: z.string().optional(),
  /** Locales whose file was present but unparseable — EXCLUDED from the comparison. */
  unreadable: z.array(z.string()).default([]),
  default_locale: z.string().default("en"),
  n_default_keys: z.number().int().default(0),
  /** `false` when there was no reference set. The numbers below it mean nothing. */
  measured: z.boolean().default(true),
  n_locales: z.number().int().default(0),
  locales: z.array(LocaleCompletenessSchema).default([]),
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
  // Lot 10 — the DURABLE incidents an operator opened (attributed journal).
  durable_incidents: z
    .array(
      z.object({
        incident_id: z.string(),
        title: z.string(),
        severity: z.string(),
        domain: z.string(),
        status: z.string(),
        source: z.string(),
        opened_at: z.string(),
        opened_by: z.string(),
        closed_at: z.string().nullable(),
        closed_by: z.string().nullable(),
        playbook_id: z.string().nullable(),
        journal: z.array(z.object({ at: z.string(), actor: z.string(), action: z.string() })),
      }),
    )
    .default([]),
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
  // The As-of instant every projection was folded to (registre §6); null in Live.
  as_of: z.string().nullable().default(null),
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
  candidate_id: z.string(),
  source: z.enum(["live", "replay", "shadow"]),
  category: z.string(),
  score: z.number().int(),
  risk: z.enum(["eleve", "moyen", "bas"]),
  owner: z.string(),
  decision: z.enum(["pending", "promote", "review", "reject"]),
});
const CurCandidateSchema = z.object({
  id: z.string(),
  candidate_id: z.string(),
  agent_id: z.string(),
  title: z.string(),
  source: z.enum(["live", "replay", "shadow"]),
  category: z.string(),
  language: z.string(),
  priority: z.enum(["crit", "high", "mod", "low"]),
  score: z.number().int(),
  risk: z.enum(["eleve", "moyen", "bas"]),
  owner: z.string(),
  decision: z.enum(["pending", "promote", "review", "reject"]),
  decided_at: z.string(),
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
  // The As-of instant every projection was folded to (registre §6); null in Live.
  as_of: z.string().nullable().default(null),
  period_days: z.number().int(),
  updated_at: z.string(),
  kpis: z.array(CurKpiSchema),
  priority_lots: z.array(CurLotSchema),
  candidate_lots: z.array(CurCandidateSchema),
  why_tours: z.array(CurWhySchema),
  workflow: z.array(CurWorkflowSchema),
  release: z.object({
    id: z.string(),
    status: z.string(),
    readiness: z.number().int(),
  }),
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
  footer: z.object({
    release: z.string(),
    source: z.string(),
    sync: z.string(),
  }),
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
  id: z.string(),
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
const AuPipelineSchema = z.object({
  key: z.string(),
  count: z.string(),
  pct: z.number(),
});
const AuSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});
const AuEnvSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  color: z.string(),
});
const AuJournalSchema = z.object({
  time: z.string(),
  automation: z.string(),
  trigger: z.string(),
  actor: z.string(),
  evidence: z.string(),
  duration: z.string(),
  result: z.enum(["success", "fail", "blocked", "approb"]),
});
// Real pending approval requests (lot 4): opened by fired approb-mode rules,
// decided by the governed approve endpoint. id/rule_id drive the mutation;
// observed is the real store value that made the rule fire.
const AuApprovalSchema = z.object({
  id: z.string(),
  rule_id: z.string(),
  name: z.string(),
  since: z.string(),
  observed: z.string(),
  role: z.string(),
});
const AuGuardrailSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
});
const AuSavingSchema = z.object({
  key: z.string(),
  value: z.string(),
  delta: z.string(),
});

export const AutomationsOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  // The As-of instant every projection was folded to (registre §6); null in Live.
  as_of: z.string().nullable().default(null),
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
  chain_verified: z.boolean(),
  kpis: z.array(PfKpiSchema),
  alerts: z.array(z.object({ level: z.enum(["ok", "warn", "bad"]), label: z.string() })),
  alert_count: z.number().int(),
  pipeline: z.array(z.object({ key: z.string(), count: z.string(), status: z.string() })),
  // null until an operator freezes the first pack (lot 7) — honest empty state.
  current_pack: z
    .object({
      id: z.string(),
      period: z.string(),
      scope: z.string(),
      hash: z.string(),
      signer: z.string(),
      contents: z.array(z.object({ key: z.string(), n: z.number().int() })),
    })
    .nullable(),
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
    chain_length: z.string(),
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
    z.object({
      time: z.string(),
      label: z.string(),
      status: z.enum(["ok", "degraded", "down"]),
    }),
  ),
  queue: z.object({
    pending_signature: z.number().int(),
    pending_export: z.number().int(),
    verifications: z.number().int(),
  }),
  footer: z.object({ chain: z.string(), source: z.string() }),
});
export type ProofsOverview = z.infer<typeof ProofsOverviewSchema>;

// One stored evidence-pack manifest (lot 7): passthrough keeps every manifest
// field for the verbatim download; pack_id is the only shape we rely on.
export const EvidencePackManifestSchema = z.object({ pack_id: z.string() }).passthrough();
export type EvidencePackManifest = z.infer<typeof EvidencePackManifestSchema>;

export const EvidencePackVerifySchema = z.object({
  pack_id: z.string(),
  manifest_ok: z.boolean(),
  chain_verified_now: z.boolean(),
  chain_length_now: z.number().int(),
  verified_at: z.string(),
});
export type EvidencePackVerify = z.infer<typeof EvidencePackVerifySchema>;

// The REAL collection-case queue (lot 9, pii router — this hand-written zod is
// the only wire contract; undeclared fields are stripped). Every seeded demo
// case carries seed: true, so the UI can say what is demo book vs live work.
export const RecouvrementCaseRowSchema = z.object({
  case_id: z.string(),
  client: z.string(),
  amount_due: z.number(),
  days_late: z.number().int(),
  missed_promise_date: z.string().nullable(),
  contact_window_start: z.string(),
  contact_window_end: z.string(),
  recommended_channel: z.string(),
  alternative_channel: z.string(),
  status: z.string(),
  seed: z.boolean().optional(),
  updated_at: z.string().optional(),
  updated_by: z.string().optional(),
});
export type RecouvrementCaseRow = z.infer<typeof RecouvrementCaseRowSchema>;

export const RecouvrementQueueSchema = z.object({
  available: z.boolean(),
  counters: z.object({
    relance_a_valider: z.number().int(),
    echeancier_a_confirmer: z.number().int(),
    situation_a_verifier: z.number().int(),
    traite: z.number().int(),
    total: z.number().int(),
    open: z.number().int(),
  }),
  cases: z.array(RecouvrementCaseRowSchema),
});
export type RecouvrementQueue = z.infer<typeof RecouvrementQueueSchema>;

// ---------------------------------------------------------------------------
// Signal catalogue (page #16)
// ---------------------------------------------------------------------------

const ScKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
  series: z.array(z.number()),
});
const ScRowSchema = z.object({ label: z.string(), value: z.string() });
const ScBarSchema = z.object({
  label: z.string(),
  count: z.number().int(),
  passed: z.number().int().optional(),
  color: z.string(),
});
const ScDetailSchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.string(),
  status: z.enum(["active", "evaluation", "deprecated", "disabled"]),
  severity: z.enum(["critical", "high", "medium", "low"]),
  description: z.string(),
  definition: z.array(ScRowSchema),
  performance: z.array(ScRowSchema),
  guard: z.array(ScRowSchema),
  distribution: z.array(ScBarSchema),
  outcome: z.array(ScBarSchema),
  tags: z.array(z.string()),
  usage: z.object({ logged_by: z.string(), monitors: z.string() }),
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
  detail: ScDetailSchema,
});

export const SignalCatalogueSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  total_signals: z.number().int(),
  page_size: z.number().int(),
  kpis: z.array(ScKpiSchema),
  signals: z.array(ScSignalSchema),
  categories: z.array(z.string()),
  sources: z.array(z.string()),
  run_at: z.string(),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type SignalCatalogue = z.infer<typeof SignalCatalogueSchema>;
export type ScSignal = z.infer<typeof ScSignalSchema>;

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
    lines: z.array(
      z.object({
        type: z.enum(["context", "added", "removed"]),
        text: z.string(),
      }),
    ),
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

const SmSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});

const SmKvSchema = z.object({ label: z.string(), value: z.string() });
const SmConsumersSchema = z.object({
  title: z.string(),
  label: z.string(),
  count: z.number().int(),
  regate_count: z.number().int(),
  regate_label: z.string(),
  model_changed: z.boolean(),
  revalidate_label: z.string(),
  infra: z.boolean(),
  note: z.string(),
  items: z.array(
    z.object({
      agent_id: z.string(),
      name: z.string(),
      tone: z.string(),
      label: z.string(),
      passed: z.boolean(),
    }),
  ),
});
const SmVersionRunSchema = z.object({
  run_id: z.string(),
  when: z.string(),
  model: z.string(),
  chunking: z.string(),
  chunks: z.string(),
  language: z.string(),
  trigger: z.string(),
});
const SmVersionsSchema = z.object({
  title: z.string(),
  current_title: z.string(),
  current: z.array(SmKvSchema),
  runs_title: z.string(),
  runs: z.array(SmVersionRunSchema),
  empty: z.string(),
  note: z.string(),
  // Re-gate signal raised when the active embedding model drifts from the index
  // (added by Commit 3); optional so the schema is forward-compatible.
  drift: z
    .object({
      changed: z.boolean(),
      from: z.string(),
      to: z.string(),
      label: z.string(),
    })
    .optional(),
});
const SmDetailSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(["active", "disabled"]),
  type: z.string(),
  classification: z.enum(["public", "internal", "confidential"]),
  description: z.string(),
  sections: z.array(z.object({ key: z.string(), title: z.string(), rows: z.array(SmKvSchema) })),
  consumers: SmConsumersSchema.optional(),
  versions: SmVersionsSchema.optional(),
});

export const SourcesOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string(),
  total_sources: z.number().int(),
  page_size: z.number().int(),
  subtitle: z.string(),
  readonly_note: z.string(),
  kpis: z.array(
    z.object({
      key: z.string(),
      label: z.string(),
      value: z.string(),
      series: z.array(z.number()),
    }),
  ),
  sources: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      type: z.string(),
      classification: z.enum(["public", "internal", "confidential"]),
      volume: z.string(),
      volume_num: z.number(),
      units: z.string(),
      languages: z.string(),
      freshness: z.string(),
      freshness_days: z.number().int().nullable(),
      status: z.enum(["active", "disabled"]),
      citation: z.string(),
      citation_pct: z.number().nullable(),
      hits: z.number().int(),
      version: z.string(),
      quality_tone: z.string(),
      quality_label: z.string(),
      retention: z.string(),
      used_by: z.string(),
      used_by_count: z.number().int(),
      consumer_ids: z.array(z.string()),
      infra: z.boolean(),
      growth: z.array(z.object({ day: z.string(), count: z.number().int() })),
      detail: SmDetailSchema,
    }),
  ),
  selected: SmDetailSchema.nullable(),
  by_type: z.array(SmSliceSchema),
  by_type_total: z.number().int(),
  by_env: z.array(
    z.object({
      key: z.string(),
      label: z.string(),
      value: z.string(),
      pct: z.number(),
      color: z.string(),
    }),
  ),
  cost_by_source: z.array(
    z.object({
      name: z.string(),
      value: z.number(),
      label: z.string(),
      color: z.string().optional(),
    }),
  ),
  zones: z.object({
    by_type: z.string(),
    by_env: z.string(),
    cost: z.string(),
  }),
  cost: z.object({
    active: z.string(),
    frontier: z.string(),
    note: z.string(),
  }),
  lineage: z.object({
    title: z.string(),
    steps: z.array(
      z.object({
        key: z.string(),
        label: z.string(),
        value: z.string(),
        href: z.string().optional(),
      }),
    ),
  }),
  audit: z.object({
    verified: z.boolean(),
    tone: z.string(),
    label: z.string(),
    length: z.string(),
    checked_label: z.string(),
    checked: z.string(),
  }),
  activity: z.object({
    title: z.string(),
    empty: z.string(),
    items: z.array(
      z.object({
        time: z.string(),
        text: z.string(),
        actor: z.string(),
        tone: z.string(),
      }),
    ),
  }),
  embedding: z.object({
    model: z.string(),
    dim: z.string(),
    distance: z.string(),
    topk: z.string(),
    chunks: z.string(),
    documents: z.string(),
    languages: z.string(),
  }),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type SourcesOverview = z.infer<typeof SourcesOverviewSchema>;

// --- CONFIGURER model catalogue (configurer/modeles) ----------------------
const McConsumersSchema = z.object({
  title: z.string(),
  count: z.number().int(),
  regate_count: z.number().int(),
  regate_label: z.string(),
  revalidate_label: z.string(),
  empty: z.string(),
  note: z.string(),
  items: z.array(
    z.object({
      agent_id: z.string(),
      name: z.string(),
      tone: z.string(),
      label: z.string(),
      passed: z.boolean(),
    }),
  ),
});
const McDetailSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(["active", "available"]),
  sections: z.array(z.object({ key: z.string(), title: z.string(), rows: z.array(SmKvSchema) })),
  consumers: McConsumersSchema,
});
export const ModelCatalogueSchema = z.object({
  available: z.boolean(),
  subtitle: z.string().optional(),
  kpis: z.array(z.object({ key: z.string(), label: z.string(), value: z.string() })).optional(),
  columns: z.array(z.string()).optional(),
  models: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        provider: z.string(),
        provider_label: z.string(),
        role: z.enum(["chat", "embedding"]),
        role_label: z.string(),
        status: z.enum(["active", "available"]),
        status_label: z.string(),
        price: z.string(),
        used_by: z.string(),
        used_by_count: z.number().int(),
        consumer_ids: z.array(z.string()),
        detail: McDetailSchema,
      }),
    )
    .optional(),
  note: z.string().optional(),
});
export type ModelCatalogue = z.infer<typeof ModelCatalogueSchema>;

// --- CONFIGURER platform guardrail catalogue (configurer/garde-fous) -------
export const GuardrailCatalogueSchema = z.object({
  available: z.boolean(),
  subtitle: z.string().optional(),
  kpis: z.array(z.object({ key: z.string(), label: z.string(), value: z.string() })).optional(),
  columns: z.array(z.string()).optional(),
  blocks: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        scope: z.string(),
        composition: z.string(),
        status: z.enum(["active", "available"]),
        status_label: z.string(),
        used_by: z.string(),
        used_by_count: z.number().int(),
        consumer_ids: z.array(z.string()),
        detail: McDetailSchema,
      }),
    )
    .optional(),
  note: z.string().optional(),
});
export type GuardrailCatalogue = z.infer<typeof GuardrailCatalogueSchema>;

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

// Honest-empty, made explicit (audit P1.4 / the `access` degrade bug).
//
// The backend answers `{available: false}` — and NOTHING else — when the roles store is
// unreachable: the page must degrade, not break. This schema used to be a flat `z.object` with
// `available: z.boolean()` and every payload field REQUIRED, so `safeParse` REJECTED that
// response and `request()` threw. The page therefore broke on the exact response that exists so
// it would not break, and it broke precisely when the backend was already failing.
//
// A discriminated union says what is true: `available: true` GUARANTEES the payload; `available:
// false` carries nothing and is a valid, expected answer. This mirrors the generated
// `AccessResponseSchema` (lib/api/generated/fleet.ts), which the domain will migrate to wholesale
// — this is the same fix, landed now, because the bug is live.
export const AccessOverviewUnavailableSchema = z.object({
  available: z.literal(false),
});

const AccessOverviewPayloadSchema = z.object({
  available: z.literal(true),
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
      caps: z.array(z.string()).default([]),
      owner: z.string().default(""),
      created: z.string().default("-"),
      members: z
        .array(z.object({ name: z.string(), team: z.string(), status: z.string() }))
        .default([]),
      permission_dist: z.array(RaSliceSchema).default([]),
      access_scope: z.array(RaSliceSchema).default([]),
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
    caps: z.array(z.string()).default([]),
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

export const AccessOverviewSchema = z.discriminatedUnion("available", [
  AccessOverviewPayloadSchema,
  AccessOverviewUnavailableSchema,
]);
export type AccessOverviewPayload = z.infer<typeof AccessOverviewPayloadSchema>;
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

const IgRowSchema = z.object({ label: z.string(), value: z.string() });
const IgDetailSchema = z.object({
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
  usage: z.object({
    read: IgMetricSchema,
    write: IgMetricSchema,
    cost: IgMetricSchema,
  }),
  config_rows: z.array(IgRowSchema).default([]),
  security_rows: z.array(IgRowSchema).default([]),
});
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
      detail: IgDetailSchema,
    }),
  ),
  selected: IgDetailSchema,
  by_type: z.array(IgSliceSchema),
  by_type_total: z.number().int(),
  by_env: z.array(
    z.object({
      key: z.string(),
      label: z.string().default(""),
      value: z.string(),
      pct: z.number(),
      color: z.string(),
    }),
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
  runtime: z.object({
    uptime: z.string(),
    audit_lines: z.string(),
    audit_chain: z.string(),
    started: z.string(),
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
  // As-of only: true = the policy socle was reconstructed from git at T; false
  // (or absent, older payloads) = the fold covers the governed overrides only.
  socle_policy_asof: z.boolean().optional(),
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
      status: z.enum(["active", "draft", "deprecated", "override"]),
    }),
  ),
  config_state: z.object({
    total: z.number().int(),
    slices: z.array(
      z.object({
        key: z.string(),
        count: z.number().int(),
        pct: z.number(),
        color: z.string(),
      }),
    ),
  }),
  compliance: z.array(z.object({ key: z.string(), status: z.enum(["ok", "warn", "bad"]) })),
  usage_policies: z.array(z.object({ name: z.string(), value: z.string(), status: z.string() })),
  models_configured: z
    .array(
      z.object({
        name: z.string(),
        provider: z.string(),
        role: z.string(),
        status: z.enum(["active", "available"]),
      }),
    )
    .default([]),
  backup: z.object({
    last_backup: z.string(),
    frequency: z.string(),
    retention: z.string(),
    size: z.string(),
  }),
  footer: z.object({ version: z.string(), source: z.string() }),
});
export type ParametersOverview = z.infer<typeof ParametersOverviewSchema>;

// Governed operable-knob overrides (ADR 0030): the closed registry the agent
// enumerates — org-wide + per-agent chat model — with base, override and
// attribution. Served by /settings/overrides through the dedicated BFF.
export const OverrideKnobSchema = z.object({
  key: z.string(),
  agent_id: z.string().nullable(),
  base: z.string(),
  // ADR 0034 — the knob family binds the control (model select / EUR input /
  // closed behaviour select); `options` is the closed list for enum knobs.
  kind: z.enum(["model", "budget_eur", "overrun"]).optional(),
  options: z.array(z.string()).nullable().optional(),
  override: z
    .object({
      value: z.string(),
      author: z.string(),
      reason: z.string(),
      updated_at: z.string(),
    })
    .nullable(),
});
export type OverrideKnob = z.infer<typeof OverrideKnobSchema>;

export const SettingsOverridesSchema = z.object({
  allowed_chat_models: z.array(z.string()),
  knobs: z.array(OverrideKnobSchema),
});
export type SettingsOverrides = z.infer<typeof SettingsOverridesSchema>;

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
  rail: z.object({
    period: z.string(),
    sla: z.string(),
    updated: z.string(),
    compare: z.string(),
  }),
  kpis: z.array(IbKpiSchema),
  agent: z.string().optional(),
  items: z.array(
    z.object({
      id: z.string(),
      /** The agent whose own eval run produced this case (real per-agent attribution). */
      agent_id: z.string().default(""),
      agent: z.string().default(""),
      priority: z.enum(["urgent", "high", "medium", "low"]),
      type: z.string(),
      title: z.string(),
      source: z.string(),
      assignee: z.string(),
      sla: z.string(),
      sla_tone: z.enum(["crit", "warn", "ok"]),
      due: z.string(),
      status: z.enum(["todo", "in_progress", "waiting", "resolved"]),
      href: z.string().optional().default(""),
      source_kind: z.string().optional().default("eval_failure"),
      // WF-01 — journaled case transitions, each naming its verified author.
      transitions: z
        .array(z.object({ at: z.string(), label: z.string(), by: z.string() }))
        .optional()
        .default([]),
    }),
  ),
  total_items: z.number().int(),
  by_type: z.array(
    z.object({
      key: z.string(),
      count: z.number().int(),
      pct: z.number(),
      color: z.string(),
    }),
  ),
  by_type_total: z.number().int(),
  sla_buckets: z.array(z.object({ key: z.string(), count: z.number().int(), color: z.string() })),
  recent_activity: z.array(z.object({ time: z.string(), actor: z.string(), action: z.string() })),
  footer: z.object({ total: z.number().int(), source: z.string() }),
});
export type InboxOverview = z.infer<typeof InboxOverviewSchema>;

// ---------------------------------------------------------------------------
// Overview — control → catalogue-signal resolver (actionable Contrôles critiques)
// ---------------------------------------------------------------------------

export const ControlSignalSchema = z.object({
  id: z.string(),
  /** Real catalogue signal id (SIG-xxx) — null for a non-catalogued live probe. */
  signal_id: z.string().nullable(),
  signal_name: z.string().nullable(),
  category: z.string().nullable(),
  /** Real SURVEILLER drill-down route (always present). */
  route: z.string(),
  catalogued: z.boolean(),
  /** Why it is not catalogued (live policy/calibration probe), else null. */
  reason: z.string().nullable(),
});
export const ControlSignalsSchema = z.object({
  available: z.boolean(),
  controls: z.array(ControlSignalSchema),
});
export type ControlSignal = z.infer<typeof ControlSignalSchema>;
export type ControlSignals = z.infer<typeof ControlSignalsSchema>;

// ---------------------------------------------------------------------------
// Overview — governed-activity feed (real S1 governance events + lineage deploys)
// ---------------------------------------------------------------------------

export const GovernanceEventSchema = z.object({
  occurred_at: z.string(),
  kind: z.enum([
    "routing",
    "handoff",
    "proposed",
    "released",
    "blocked",
    "deploy_model",
    "deploy_prompt",
    "deploy_policy",
  ]),
  actor: z.string(),
  agent_id: z.string().nullable(),
  from_agent: z.string().nullable(),
  to_agent: z.string().nullable(),
  detail: z.string(),
  count: z.number().int(),
  evidence: z.string().nullable(),
});
export const GovernanceFeedSchema = z.object({
  available: z.boolean(),
  events: z.array(GovernanceEventSchema),
  total: z.number().int(),
  by_kind: z.record(z.string(), z.number().int()),
  as_of: z.string().nullable(),
});
export type GovernanceEvent = z.infer<typeof GovernanceEventSchema>;
export type GovernanceFeed = z.infer<typeof GovernanceFeedSchema>;

// ---------------------------------------------------------------------------
// Overview — trace observability read back from the Langfuse stack (real)
// ---------------------------------------------------------------------------

export const TracesObsSchema = z.object({
  available: z.boolean(),
  total: z.number().int(),
  latency_p50_s: z.number().nullable(),
  latency_p95_s: z.number().nullable(),
  top_ops: z.array(z.object({ name: z.string(), count: z.number().int() })),
  recent: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      timestamp: z.string(),
      latency_s: z.number().nullable(),
      url: z.string(),
    }),
  ),
  langfuse_url: z.string(),
  grafana_url: z.string(),
  phoenix_url: z.string(),
  as_of: z.string().nullable(),
});
export type TracesObs = z.infer<typeof TracesObsSchema>;

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
    z.object({
      name: z.string(),
      detail: z.string(),
      level: z.enum(["warn", "crit", "ok"]),
    }),
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
  // Verbose descriptive form for the `title=` hover tooltip. `label` is kept terse so the
  // narrow tile never ellipsises; `full` restores it (e.g. "Conversations traitées") on hover.
  full: z.string().optional(),
  value: z.string(),
  delta: z.string(),
  good: z.boolean(),
  series: z.array(z.number()),
  // Optional MetricInfo tooltip (what/how/source) — attached to cells whose honest
  // small number would otherwise read as a bug (Utilisateurs servis, Satisfaction).
  explain: TabExplainSchema.nullable().optional(),
});
const SynLabelValueSchema = z.object({ label: z.string(), value: z.string() });
const SynBarSchema = z.object({
  label: z.string(),
  pct: z.number(),
  tone: z.string(),
});

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
  context: z
    .object({
      name: z.string(),
      status: z.string(),
      agentId: z.string(),
      description: z.string(),
      fields: z.array(SynLabelValueSchema),
      cta: z.string(),
      ctaHref: z.string().optional(),
    })
    .optional(),
  opAlerts: z
    .object({
      title: z.string(),
      cta: z.string(),
      ctaHref: z.string().optional(),
      items: z.array(
        z.object({
          label: z.string(),
          detail: z.string(),
          tone: z.string(),
          badge: z.string(),
        }),
      ),
    })
    .optional(),
  quickAccess: z
    .object({
      title: z.string(),
      items: z.array(z.object({ label: z.string(), sublabel: z.string(), href: z.string() })),
    })
    .optional(),
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
  repartition: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      items: z.array(SynBarSchema),
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
      cta: z.string(),
      ctaHref: z.string().optional(),
      rows: z.array(
        z.object({
          time: z.string(),
          label: z.string(),
          detail: z.string(),
          kind: z.string(),
          badge: z.string(),
        }),
      ),
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
      // TE-01 owed param, closed: the folded agent id (null = historical default)
      // and the real fleet ids the selector may fold to.
      agent_id: z.string().nullable().default(null),
      agents: z.array(z.string()).default([]),
      context_source: z.string(),
      timezone: z.string(),
      scope: z
        .object({
          keys: z.array(z.string()),
          labels: z.array(z.string()),
          count: z.number(),
        })
        .nullable()
        .optional(),
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
  // Register §9 opposability badge (TE-01) — the Hica seal facet, computed live from tree + seal.
  opposability: z
    .object({
      badge: z.enum([
        "non_scelle",
        "scelle_opposable",
        "scelle_non_qualifie",
        "integrite_partielle",
        "verification_en_cours",
      ]),
      badge_label: z.string(),
      seal_state: z.string(),
      seal_provider: z.string().nullable(),
      seal_qualified: z.boolean(),
      sealed_at: z.string().nullable(),
      content_integrity: z.boolean(),
      linear: z.boolean(),
      attested: z.boolean(),
      provider_label: z.string(),
      mention: z.string(),
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
  handoffs: z
    .object({
      title: z.string(),
      subtitle: z.string().optional(),
      rows: z.array(
        z.object({
          from: z.string(),
          to: z.string(),
          reason: z.string(),
          at: z.string(),
        }),
      ),
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
  sla_tone: z.string(),
  sla_rows: z.array(z.object({ label: z.string(), value: z.string() })),
  // WF-01 — journaled case transitions, each naming its verified author.
  transitions_title: z.string().optional(),
  transitions_empty: z.string().optional(),
  transition_rows: z
    .array(
      z.object({
        at: z.string(),
        label: z.string(),
        by: z.string(),
        kind: z.string(),
      }),
    )
    .optional(),
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
        z.object({
          time: z.string(),
          label: z.string(),
          ref: z.string(),
          tone: z.string(),
        }),
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
  // Explicit on-state for toggle fields (locale-independent; the displayed
  // `value` is localized so it can't be string-compared in the client).
  on: z.boolean().optional(),
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
  // ADR 0031 — provenance and effectiveness: `unset` means the parameter is
  // not sent (the backend default serves), `overridden` means a durable
  // override produced the value, `applied` says the serving backend forwards it.
  unset: z.boolean().optional(),
  overridden: z.boolean().optional(),
  applied: z.boolean().optional(),
  // ADR 0033 — what "unset" means for THIS knob when it is not the backend
  // default (e.g. "Défaut org (0,60)" for the escalation threshold).
  unset_label: z.string().optional(),
});

// ADR 0031 — which backend serves this agent (from its effective model) and
// which sampling sliders that backend actually applies.
const AgentConfigRuntimeSchema = z.object({
  label: z.string(),
  model: z.string(),
  backend: z.string(),
  applied: z.array(z.string()),
  not_applied: z.array(z.string()),
  note: z.string(),
});

export const AgentConfigurationsSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  governance_banner: z.string().optional(),
  definition: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      link: z.object({ label: z.string(), href: z.string() }),
      rows: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
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
      runtime: AgentConfigRuntimeSchema.optional(),
      // ADR 0033 — the operable, governed escalation threshold.
      escalation: z
        .object({
          title: z.string(),
          slider: AgentConfigSliderSchema,
          note: z.string(),
        })
        .optional(),
      // ADR 0035 — per-agent retrieval depth + reranking.
      retrieval: z
        .object({
          title: z.string(),
          slider: AgentConfigSliderSchema,
          toggle: AgentConfigFieldSchema,
          note: z.string(),
        })
        .optional(),
      // ADR 0036 — per-agent memory tier + window.
      memory: z
        .object({
          title: z.string(),
          select: AgentConfigFieldSchema,
          slider: AgentConfigSliderSchema,
          note: z.string(),
        })
        .optional(),
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
  // ADR 0019 §I2 — the declared cockpit→agent binding this console drives. The console
  // generates its shape from this: `invocable` gates the interactive surface vs the
  // honest-empty state. `in_process_chat` is the only invocable binding until the I3
  // http invoker; a publish-only agent declares `none`.
  invocation: z
    .object({
      binding: z.enum(["none", "in_process_chat", "http"]),
      invocable: z.boolean(),
      // http only (ADR 0019 §I3): the request/response mode + the endpoint the cockpit consumes.
      mode: z.enum(["request_response"]).optional(),
      endpoint: z.string().nullable().optional(),
    })
    .optional(),
  // Honest-empty descriptor for a non-invocable agent (binding: none) — "this agent
  // exposes no test invocation — observe it through its runs and evals". Present in place
  // of the config panels, never alongside them.
  empty: z.object({ title: z.string(), detail: z.string() }).optional(),
  // http console descriptor (ADR 0019 §I3): the request/response test bench chrome. Present
  // only for an http-binding agent, in place of the in-process sandbox/debug panels.
  http_console: z
    .object({
      placeholder: z.string(),
      send_label: z.string(),
      reply_label: z.string(),
      result_label: z.string(),
      verdict_ok: z.string(),
      verdict_failed: z.string(),
    })
    .optional(),
  // ADR 0019 §A1.2 (c) — the agent's declared capability forms, each a JSON Schema the console
  // renders generically. `label_key` travels unresolved so the frontend owns the locale
  // catalogue (keeps the projection agent-agnostic). Absent ⇒ undefined; `[]` is meaningful —
  // an http agent that declares no capability with an input_schema — never a fabricated fill.
  capabilities: z
    .array(
      z.object({
        id: z.string(),
        label_key: z.string(),
        schema: z.record(z.string(), z.unknown()),
      }),
    )
    .optional(),
  // Generic chrome for those forms (never agent-specific).
  capability_console: z
    .object({
      free_text_label: z.string(),
      section_label: z.string(),
      hint: z.string(),
      submit_label: z.string(),
      required_label: z.string(),
    })
    .optional(),
  // Context strip atop the central "Résumé de la réponse" column (relocated from
  // the old full-width status bar). Real: env Sandbox + model + version stamps.
  context: z
    .object({
      session_id: z.string(),
      fields: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
  tabs: z.array(z.string()).optional(),
  // Loaded tools / guardrails from the policy — real configuration, honest
  // pre-turn (titled "disponibles" / "chargés"; the live debug swaps to the
  // "appelés" / "déclenchés" turn data).
  tools: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({
          name: z.string(),
          status: z.string(),
          tone: z.string(),
          latency: z.string(),
        }),
      ),
    })
    .optional(),
  guardrails: z
    .object({
      title: z.string(),
      rows: z.array(
        z.object({
          name: z.string(),
          status: z.string(),
          tone: z.string(),
          detail: z.string(),
        }),
      ),
    })
    .optional(),
  // Latest automated-eval run (real, not per-turn): metrics with an honest empty
  // value when a metric has no recorded score.
  evaluation: z
    .object({
      title: z.string(),
      note: z.string(),
      cta: z.string(),
      rows: z.array(z.object({ label: z.string(), value: z.string().nullable() })),
    })
    .optional(),
  footer: z
    .object({
      started: z.string(),
      context: z.string(),
      language: z.string(),
    })
    .optional(),
  // Operator feedback is NOT here: the thumbs come from `/console/feedback`
  // (ConsoleFeedbackSchema), a durable per-turn read. `actions.feedback` used to
  // ship two labels alongside it that nothing rendered.
  actions: z
    .object({
      input_placeholder: z.string(),
      footer_actions: z.array(z.object({ key: z.string(), label: z.string() })),
      new_session: z.string(),
    })
    .optional(),
});
export type AgentConsole = z.infer<typeof AgentConsoleSchema>;

export const ConsoleFeedbackSchema = z.object({
  ratings: z.record(z.string(), z.string()),
});
export type ConsoleFeedback = z.infer<typeof ConsoleFeedbackSchema>;

// ADR 0041 — the customer's 👍/👎 on an assistant reply. The backend echoes the recorded
// rating; the real signal lives in the durable `customer_feedback` store, read per-agent
// by the Synthèse CSAT KPI.
export const CustomerFeedbackResponseSchema = z.object({
  ok: z.boolean(),
  rating: z.string(),
});
export type CustomerFeedbackResponse = z.infer<typeof CustomerFeedbackResponseSchema>;

// ADR 0019 §I3 — the outcome of one http invocation (POST /agents/{id}/invoke). A red
// verdict is a successful invocation with a failure result (returned as data, HTTP 200);
// only auth/plane/binding refusals are HTTP errors.
export const AgentInvokeOutcomeSchema = z.object({
  ok: z.boolean(),
  verdict: z.enum(["green", "red"]),
  status_code: z.number().nullable(),
  duration_ms: z.number(),
  error: z.string().nullable(),
  conformance: z.array(z.string()),
  result: z.record(z.string(), z.unknown()).nullable(),
  conversation_id: z.string(),
  turn_id: z.string(),
});
export type AgentInvokeOutcome = z.infer<typeof AgentInvokeOutcomeSchema>;

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
          z.object({
            text: z.string(),
            answer: z.string().optional(),
            time: z.string(),
          }),
        ),
        params_title: z.string().optional(),
        params: z.array(z.object({ label: z.string(), value: z.string() })).optional(),
        attachment: z
          .object({
            title: z.string(),
            rows: z.array(z.object({ label: z.string(), value: z.string() })),
            journal_title: z.string().optional(),
            // S1 fold of the governed attach/detach acts: a list (possibly empty),
            // or null when the ledger could not be read — rendered as such.
            journal: z
              .array(
                z.object({
                  at: z.string(),
                  by: z.string(),
                  action: z.string(),
                }),
              )
              .nullable()
              .optional(),
            journal_empty: z.string().optional(),
            journal_unavailable: z.string().optional(),
          })
          .optional(),
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
  reasons: z
    .object({
      title: z.string(),
      items: z.array(
        z.object({
          label: z.string(),
          pct: z.number(),
          count: z.string(),
          tone: z.string(),
        }),
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
  mode_distribution: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      total: z.number(),
      items: z.array(
        z.object({
          label: z.string(),
          mode: z.string(),
          count: z.number(),
          active: z.number(),
          decisions: z.number(),
          pct: z.number(),
        }),
      ),
    })
    .optional(),
  overrides: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      count: z.number(),
      empty: z.string(),
      items: z.array(
        z.object({
          key: z.string(),
          name: z.string(),
          category: z.string(),
          mode: z.string(),
          status: z.string(),
        }),
      ),
    })
    .optional(),
});
export type AgentGardeFous = z.infer<typeof AgentGardeFousSchema>;

// ADR 0037 — the governed prompt-overlay lifecycle state.
export const PromptOverlaySchema = z.object({
  title: z.string(),
  note: z.string(),
  approved: z
    .object({
      text: z.string(),
      author: z.string(),
      approved_by: z.string(),
      at: z.string(),
    })
    .nullable(),
  draft: z.object({ text: z.string(), author: z.string(), at: z.string() }).nullable(),
  history: z.array(
    z.object({
      at: z.string(),
      event: z.string(),
      author: z.string(),
      chars: z.number(),
    }),
  ),
  max_chars: z.number().int(),
  agent_id: z.string(),
  labels: z.record(z.string(), z.string()),
});
export type PromptOverlay = z.infer<typeof PromptOverlaySchema>;

// The mutation routes return the bare lifecycle state.
export const PromptOverlayStateSchema = z.object({
  available: z.boolean(),
  draft: z.object({ text: z.string(), author: z.string(), at: z.string() }).nullable(),
  approved: z
    .object({
      text: z.string(),
      author: z.string(),
      approved_by: z.string(),
      at: z.string(),
    })
    .nullable(),
  history: z.array(
    z.object({
      at: z.string(),
      event: z.string(),
      author: z.string(),
      chars: z.number(),
    }),
  ),
});
export type PromptOverlayState = z.infer<typeof PromptOverlayStateSchema>;

export const AgentPromptsSchema = z.object({
  available: z.boolean(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  definition: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      link: z.object({ label: z.string(), href: z.string() }),
      rows: z.array(z.object({ label: z.string(), value: z.string() })),
    })
    .optional(),
  governance_banner: z.string().optional(),
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
        z.object({
          label: z.string(),
          value: z.string(),
          pct: z.number(),
          tone: z.string(),
        }),
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
          z.object({
            label: z.string(),
            value: z.string(),
            tone: z.string().optional(),
          }),
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
  // ADR 0037 — the one governed exception to this page's read-only rule:
  // the per-agent overlay lifecycle (propose → approve/reject/revoke).
  overlay: PromptOverlaySchema.optional(),
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
  agent_id: z.string().optional(),
  scoped: z.boolean().optional(),
  gate: z
    .object({
      passed: z.boolean().nullable(),
      failed_critical: z.array(z.string()),
      standard_passed: z.number(),
      standard_total: z.number(),
      label: z.string(),
      breakdown: z
        .object({
          critical_blocking: z.number(),
          tier0_non_derogeable: z.number(),
          waived: z.number(),
        })
        .optional(),
      // Policy-correct enrichments (eval-gate-policy.md, case × langue grain).
      tone: z.string().optional(),
      reason: z.string().optional(),
      candidate: z.string().optional(),
      grains: z
        .object({
          executions: z.number(),
          distinct_cases: z.number(),
          socle_cases: z.number(),
        })
        .optional(),
      counts: z.object({ passed: z.number(), failed: z.number() }).optional(),
      socle: z.object({ ok: z.boolean(), passed: z.number(), total: z.number() }).optional(),
      // T2 is measured, never gated (ADR 0021): no `ok`, no `min`. `gating: false` says it
      // on the wire, so the rate cannot be mistaken for a verdict.
      domain: z
        .object({
          passed: z.number(),
          total: z.number(),
          rate: z.number(),
          gating: z.literal(false),
        })
        .optional(),
      // What replaced the domain bar: the model's delta over THIS set's own null floor.
      // Honest-empty when no set is bound, no floor is committed, no model spoke, or the
      // floor no longer covers this run's cases. `refusal` says WHICH — declare it or zod
      // strips it in silence, and the empty state can never explain itself.
      contribution: z
        .union([
          z.object({
            available: z.literal(true),
            title: z.string(),
            model: z.string(),
            floor_passed: z.number(),
            floor_total: z.number(),
            regression_candidates: z.array(z.string()),
            contribution: z.number(),
            contribution_population: z.number(),
            gated: z.literal(false),
            note: z.string(),
          }),
          z.object({
            available: z.literal(false),
            refusal: z.string().nullish(),
          }),
        ])
        .optional(),
      breakdown_grain: z
        .object({
          blocking_socle: z.number(),
          blocking_t1: z.number(),
          waived_active: z.number(),
          non_executed_critical: z.number(),
        })
        .optional(),
      tiers: z
        .array(
          z.object({
            tier: z.string(),
            label: z.string(),
            count: z.number(),
            tone: z.string(),
            waivable: z.boolean(),
          }),
        )
        .optional(),
      venn: z
        .object({
          universe: z.number(),
          critiques: z.number(),
          socle: z.number(),
          t1: z.number(),
          domaine: z.number(),
          deroges: z.number(),
          reconciles: z.boolean(),
          reconcile_total: z.number(),
        })
        .optional(),
      socle_by_category: z
        .array(
          z.object({
            category: z.string(),
            label: z.string(),
            ok: z.boolean(),
            passed: z.number(),
            total: z.number(),
          }),
        )
        .optional(),
      critical_cases: z
        .object({
          title: z.string(),
          columns: z.array(z.string()),
          total: z.number(),
          rows: z.array(
            z.object({
              case_id: z.string(),
              title: z.string(),
              tier: z.string(),
              tier_label: z.string(),
              tier_tone: z.string(),
              language: z.string(),
              status_key: z.string(),
              status_label: z.string(),
              status_tone: z.string(),
              socle: z.boolean(),
            }),
          ),
        })
        .optional(),
      waivers: z
        .object({
          title: z.string(),
          subtitle: z.string(),
          active: z.number(),
          total: z.number(),
          chain_verified: z.boolean(),
          items: z.array(
            z.object({
              id: z.string(),
              case_id: z.string(),
              language: z.string(),
              tier: z.string(),
              tier_label: z.string(),
              status: z.string(),
              status_label: z.string(),
              active: z.boolean(),
              justification: z.string(),
              requester: z.string(),
              requester_role: z.string(),
              approver: z.string(),
              approver_role: z.string(),
              scope: z.string(),
              controls: z.array(z.string()),
              incident_ref: z.string(),
              expires_at: z.string(),
            }),
          ),
        })
        .optional(),
    })
    .optional(),
  judge: z
    .object({
      available: z.boolean(),
      judge_model: z.string().nullable().optional(),
      context_basis: z.string().nullable().optional(),
      faithfulness: z.number().nullable().optional(),
      grounding: z.number().nullable().optional(),
      hallucination: z.number().nullable().optional(),
      n: z.number().optional(),
    })
    .optional(),
  // ER-01 run journal: per-run provenance (date + catalogue version + model) and the
  // gate verdict recorded at run time (null = not recorded — said, never invented).
  runs: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      empty_label: z.string(),
      count: z.number(),
      items: z.array(
        z.object({
          run_at: z.string(),
          label: z.string(),
          date_label: z.string(),
          pass_rate: z.number(),
          score: z.string(),
          passed: z.number().int(),
          total: z.number().int(),
          gate_passed: z.boolean().nullable(),
          eval_set: z.string(),
          catalogue_version: z.string(),
          model: z.string(),
          delta_pass_rate: z.number().nullable(),
        }),
      ),
    })
    .optional(),
  // Jeux d'évaluations: the curated eval sets (eval/sets/*.json) + the failure
  // catalogue (eval/failures/*.json). Set names/descriptions are verbatim data.
  sets: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      columns: z.array(z.string()),
      case_columns: z.array(z.string()),
      rows: z.array(
        z.object({
          slug: z.string(),
          name: z.string(),
          description: z.string(),
          agent_id: z.string(),
          bound: z.boolean(),
          active: z.boolean(),
          case_count: z.number().int(),
          declared_count: z.number().int(),
          floor_count: z.number().int(),
          critical_count: z.number().int(),
          standard_count: z.number().int(),
          category_count: z.number().int(),
          languages: z.array(z.string()),
          gate_rationale: z.string(),
          case_ids: z.array(z.string()),
        }),
      ),
      cases: z.array(
        z.object({
          id: z.string(),
          title: z.string(),
          category: z.string(),
          category_label: z.string(),
          category_tone: z.string(),
          severity: z.string(),
          severity_label: z.string(),
          severity_tone: z.string(),
          languages: z.array(z.string()),
          tags: z.array(z.string()),
          citation: z.string(),
        }),
      ),
      total: z.number().int(),
      active_slug: z.string(),
      empty_label: z.string(),
      cases_label: z.string(),
      bound_label: z.string(),
      shared_label: z.string(),
      active_label: z.string(),
      rationale_label: z.string(),
      floor_note: z.string(),
    })
    .optional(),
  // Résultats / Erreurs: the run's per-case outcomes (snap.sessions). Each row is
  // one case×language execution with the joined question, answer and the judge's
  // verbatim diagnostic (reasons).
  results: z
    .object({
      title: z.string(),
      subtitle: z.string(),
      columns: z.array(z.string()),
      rows: z.array(
        z.object({
          case_id: z.string(),
          title: z.string(),
          language: z.string(),
          category: z.string(),
          category_label: z.string(),
          category_tone: z.string(),
          passed: z.boolean(),
          status_label: z.string(),
          status_tone: z.string(),
          escalated: z.boolean(),
          tools: z.array(z.string()),
          tool_count: z.number().int(),
          duration_ms: z.number(),
          duration_label: z.string(),
          input_tokens: z.number().int(),
          output_tokens: z.number().int(),
          total_tokens: z.number().int(),
          question: z.string(),
          response: z.string(),
          reasons: z.array(z.string()),
          started_at: z.string(),
        }),
      ),
      total: z.number().int(),
      passed: z.number().int(),
      failed: z.number().int(),
      escalated: z.number().int(),
      errors_title: z.string(),
      errors_subtitle: z.string(),
      empty_results: z.string(),
      empty_errors: z.string(),
      labels: z.object({
        question: z.string(),
        response: z.string(),
        diagnostic: z.string(),
        tools: z.string(),
        no_tools: z.string(),
        escalated: z.string(),
        tokens: z.string(),
        started: z.string(),
        no_question: z.string(),
      }),
    })
    .optional(),
});
export type AgentEvaluations = z.infer<typeof AgentEvaluationsSchema>;

// One conversation in an agent's list (console "Récents" + cockpit Historique).
export const ConversationSummarySchema = z.object({
  conversation_id: z.string(),
  title: z.string(),
  started_at: z.string(),
  last_at: z.string(),
  message_count: z.number(),
  turn_count: z.number(),
});
export type ConversationSummary = z.infer<typeof ConversationSummarySchema>;

export const ConversationListSchema = z.object({
  available: z.boolean(),
  conversations: z.array(ConversationSummarySchema),
});
export type ConversationList = z.infer<typeof ConversationListSchema>;

export const ConversationMessagesSchema = z.object({
  available: z.boolean(),
  conversation_id: z.string().optional(),
  messages: z.array(z.object({ role: z.string(), content: z.string() })),
});
export type ConversationMessages = z.infer<typeof ConversationMessagesSchema>;

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
        z.object({
          label: z.string(),
          value: z.string(),
          pct: z.number(),
          share: z.string(),
        }),
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
  // Real live conversations from the transcript, surfaced alongside the eval
  // sessions (additive). Absent on older payloads → optional.
  live_conversations: z.array(ConversationSummarySchema).optional(),
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

// Cockpit chrome — the sidebar badges and the bell, every number a real count.
//
// `badges` is a sparse map: a key is present only when its page has something to count.
// An absent key means "no badge", never a zero — a decorative `0` reads as "checked,
// nothing there" when the truth is "never looked". Tones arrive decided (the queue's own
// SLA rule, the incident core's own severity); the frontend colours, it does not judge.
export const ChromeBadgeSchema = z.object({
  count: z.number().int(),
  tone: z.enum(["danger", "warning", "neutral"]),
});
export const ChromeSchema = z.object({
  available: z.boolean(),
  badges: z.record(z.string(), ChromeBadgeSchema).optional().default({}),
  notifications: z
    .object({
      count: z.number().int(),
      // Each notification deep-links to the page where the act is performed. A bell that
      // announces a fact you cannot navigate to is a decoration with a number on it.
      items: z.array(
        z.object({
          id: z.string(),
          label: z.string(),
          // Queue facts carry their measured population so the header can compose
          // "all" / "x of y" without parsing a translated sentence.
          count: z.number().int().positive(),
          href: z.string(),
          tone: z.enum(["danger", "warning", "neutral"]),
        }),
      ),
    })
    .optional()
    .default({ count: 0, items: [] }),
});
export type Chrome = z.infer<typeof ChromeSchema>;
export type ChromeBadgeId = string;

// Fleet rollup — per-agent observable KPIs + deduplicated org totals.
/**
 * The interval a fleet payload answered.
 *
 * `period_days: null` means all history — a real answer, not a missing one. It exists because
 * two callers asked for two different windows and got payloads of identical shape: the Flotte
 * directory reads all history, every SURVEILLER domain page reads a trailing 7 days, and an
 * operator moving between them was comparing numbers that were never the same measurement.
 */
/**
 * How many signals the catalogue DECLARES, split by whether they were ever built.
 *
 * The Qualité IA header read "42 of the 200-signal catalogue" from two constants. Both were
 * wrong, and so was the framing: 202 are declared, 78 are `active` and 124 are `planned` —
 * designed and never implemented. A page cannot cover what does not exist, so a coverage ratio
 * against the whole catalogue measures nothing; what the operator needs is the FUNNEL, and its
 * first two stages are these.
 */
export const SignalCoverageSchema = z.object({
  available: z.boolean(),
  catalogue: z
    .object({
      total: z.number().int(),
      active: z.number().int(),
      planned: z.number().int(),
      on_quality_page: z.number().int(),
    })
    .optional(),
});
export type SignalCoverage = z.infer<typeof SignalCoverageSchema>;

export const FleetWindowSchema = z.object({
  period_days: z.number().int().nullable(),
  since: z.string().nullable(),
  until: z.string().nullable(),
});
export type FleetWindow = z.infer<typeof FleetWindowSchema>;

export const FleetSchema = z.object({
  available: z.boolean(),
  // Optional in the SCHEMA, not in the contract: a cached payload minted before this field
  // existed must still parse rather than blanking the page. The renderer says "unknown window"
  // when it is absent, which is the honest reading and a visibly temporary one.
  window: FleetWindowSchema.optional(),
  agents: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        owner: z.string(),
        audience: z.string().optional(),
        // Manifest-declared, projected verbatim: the card must say what an agent is FOR, and a
        // `demo` tag must mark the platform witnesses — else "5 agents" reads as 5 banking agents.
        description: z.string().optional(),
        tags: z.array(z.string()).optional(),
        conversations: z.number(),
        turns: z.number(),
        messages: z.number(),
        escalation_rate: z.number(),
        latency_ms: z.number().nullable(),
        handoffs_in: z.number(),
        handoffs_out: z.number(),
        health: z.string(),
        release: z
          .object({
            agent_id: z.string(),
            available: z.boolean(),
            passed: z.boolean(),
            verdict_label: z.string(),
            verdict_tone: z.string(),
            candidate_version: z.string(),
            eval_set: z.string(),
            executions: z.number(),
            socle_ok: z.boolean(),
            blocking_socle: z.number(),
            blocking_t1: z.number(),
            waived_active: z.number(),
            run_at: z.string().optional(),
            catalogue_version: z.string().optional(),
            current_catalogue_version: z.string().optional(),
            verdict_stale: z.boolean().optional(),
            summary_passed: z.number().optional(),
            summary_total: z.number().optional(),
            socle_passed: z.number().optional(),
            socle_total: z.number().optional(),
            // ADR 0021 Rule 1 on the release column: the measured floor's verdict and the one
            // line naming its refusal — declared here or zod strips them before any reader.
            floor_ok: z.boolean().optional(),
            floor_block: z.string().nullable().optional(),
          })
          .nullable()
          .optional(),
        // ADR 0017 §4 — observability level (L0–L2 in Phase B); null when the agent has
        // no AgentSpec manifest yet (honest-empty badge, never rendered as "L0").
        // `level` is COMPUTED from observed turns; `level_declared` is what the manifest
        // would reach if that evidence existed. They differ exactly when `level_evidence`
        // is not "observed", and the badge must render the gap rather than hide it.
        level: z.string().nullable().optional(),
        level_declared: z.string().nullable().optional(),
        level_evidence: z.enum(["observed", "dormant", "unverifiable"]).optional(),
        // The two structural contracts, derived server-side from the manifest: `observable` =
        // it declares telemetry capabilities, `testable` = it declares an invocation binding.
        // Default false — an agent with no manifest promises neither, so no chip renders.
        observable: z.boolean().optional().default(false),
        testable: z.boolean().optional().default(false),
        north_star: BusinessSignalValueSchema.nullable().optional(),
        pending_business_items: z.number().int().optional().default(0),
      }),
    )
    .optional(),
  org: z.object({ conversations: z.number(), turns: z.number() }).optional(),
  naive_sum_conversations: z.number().optional(),
  shared_conversations: z.number().optional(),
  dedup_saved: z.number().optional(),
  // Completed handoffs corroborated by the source and target transcript turns. The backend does
  // not promote legacy initial-route ledger labels into these fleet business counts. Keep all
  // three fields on the wire so a degraded or older producer can still expose a reconciliation
  // gap instead of letting zod silently strip it.
  handoff_events: z.number().optional(),
  handoff_conversations: z.number().optional(),
  handoff_conversations_seen_shared: z.number().optional(),
});
export type Fleet = z.infer<typeof FleetSchema>;

export const ReleaseControlAgentSchema = z.object({
  agent_id: z.string(),
  name: z.string(),
  owner: z.string(),
  state: z.string(),
  state_tone: z.string(),
  last_phase: z.string(),
  flow: z.array(z.string()),
  history: z.array(
    z.object({
      phase: z.string(),
      type: z.string(),
      occurred_at: z.string(),
      actor: z.string(),
      reason: z.string(),
    }),
  ),
  release: z.object({
    agent_id: z.string(),
    available: z.boolean(),
    passed: z.boolean(),
    verdict_label: z.string(),
    verdict_tone: z.string(),
    candidate_version: z.string(),
    eval_set: z.string(),
    executions: z.number(),
    socle_ok: z.boolean(),
    blocking_socle: z.number(),
    blocking_t1: z.number(),
    waived_active: z.number(),
    // The verdict's own evidence — provenance, pass counts, staleness and the ADR 0021
    // Rule 1 floor reason. The backend has always sent them (`ReleaseFacts`); without
    // these declarations zod strips them and the page can say BLOQUÉ but never WHY.
    run_at: z.string().optional(),
    catalogue_version: z.string().optional(),
    current_catalogue_version: z.string().optional(),
    verdict_stale: z.boolean().optional(),
    summary_passed: z.number().optional(),
    summary_total: z.number().optional(),
    socle_passed: z.number().optional(),
    socle_total: z.number().optional(),
    floor_ok: z.boolean().optional(),
    floor_block: z.string().nullable().optional(),
  }),
});
export const ReleaseControlSchema = z.object({
  available: z.boolean(),
  agents: z.array(ReleaseControlAgentSchema).optional(),
  summary: z
    .object({
      total: z.number(),
      passing: z.number(),
      blocked: z.number(),
      not_run: z.number(),
    })
    .optional(),
});
export type ReleaseControl = z.infer<typeof ReleaseControlSchema>;
export type ReleaseControlAgent = z.infer<typeof ReleaseControlAgentSchema>;

export const CatalogueConsumerSchema = z.object({
  agent_id: z.string(),
  name: z.string(),
  release: z.object({
    available: z.boolean(),
    passed: z.boolean(),
    verdict_label: z.string(),
    verdict_tone: z.string(),
  }),
});
export const CatalogueConsumersSchema = z.object({
  available: z.boolean(),
  kind: z.string().optional(),
  route: z.string().optional(),
  items: z
    .array(
      z.object({
        item: z.string(),
        consumer_count: z.number(),
        regate_count: z.number(),
        consumers: z.array(CatalogueConsumerSchema),
      }),
    )
    .optional(),
});
export type CatalogueConsumers = z.infer<typeof CatalogueConsumersSchema>;

export const RbacMatrixSchema = z.object({
  available: z.boolean(),
  scope_model: z.string().optional(),
  agents: z.array(z.object({ id: z.string(), name: z.string() })).optional(),
  roles: z
    .array(
      z.object({
        role: z.string(),
        label: z.string(),
        caps: z.array(z.string()),
        scope: z.string(),
        agent_count: z.number(),
        cells: z.array(
          z.object({
            agent_id: z.string(),
            name: z.string(),
            granted: z.boolean(),
            scope: z.string(),
          }),
        ),
      }),
    )
    .optional(),
});
export type RbacMatrix = z.infer<typeof RbacMatrixSchema>;

export const ProposeAgentSchema = z.object({
  available: z.boolean(),
  proposed: z.string().optional(),
});
export type ProposeAgent = z.infer<typeof ProposeAgentSchema>;

export const ReleaseAgentSchema = z.object({
  available: z.boolean(),
  agent_id: z.string(),
  allowed: z.boolean(),
  reason: z.string(),
  has_run: z.boolean(),
  gate_passed: z.boolean().nullable(),
  failed_critical: z.array(z.string()),
  run_at: z.string(),
});
export type ReleaseAgent = z.infer<typeof ReleaseAgentSchema>;

// ---------------------------------------------------------------------------
// Client space (Produit) — documents / requests / alerts / settings
// ---------------------------------------------------------------------------

const ClientKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
});
const ClientSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});
const ClientFooterSchema = z.object({
  total: z.number().int().optional(),
  source: z.string(),
});

export const ClientDocumentsSchema = z.object({
  available: z.boolean(),
  kpis: z.array(ClientKpiSchema).optional(),
  distribution: z.array(ClientSliceSchema).optional(),
  documents: z
    .array(
      z.object({
        id: z.string(),
        title: z.string(),
        category: z.string(),
        language: z.string(),
        source: z.string(),
        excerpt: z.string(),
        body: z.string(),
        size_kb: z.number().int(),
        pages: z.number().int(),
        updated: z.string(),
      }),
    )
    .optional(),
  footer: ClientFooterSchema.optional(),
});
export type ClientDocuments = z.infer<typeof ClientDocumentsSchema>;

export const ClientRequestsSchema = z.object({
  available: z.boolean(),
  kpis: z.array(ClientKpiSchema).optional(),
  requests: z
    .array(
      z.object({
        reference: z.string(),
        subject: z.string(),
        category: z.string(),
        channel: z.enum(["phone", "email", "branch"]),
        status: z.enum(["open", "in_progress", "resolved"]),
        opened: z.string(),
        updated: z.string(),
        summary: z.string(),
      }),
    )
    .optional(),
  footer: ClientFooterSchema.optional(),
});
export type ClientRequests = z.infer<typeof ClientRequestsSchema>;

export const ClientAlertsSchema = z.object({
  available: z.boolean(),
  kpis: z.array(ClientKpiSchema).optional(),
  alerts: z
    .array(
      z.object({
        id: z.string(),
        title: z.string(),
        category: z.string(),
        severity: z.enum(["info", "warning", "success"]),
        date: z.string(),
        body: z.string(),
        read: z.boolean(),
      }),
    )
    .optional(),
  footer: ClientFooterSchema.optional(),
});
export type ClientAlerts = z.infer<typeof ClientAlertsSchema>;

export const ClientSettingsSchema = z.object({
  available: z.boolean(),
  values: z.record(z.string(), z.union([z.boolean(), z.string()])).optional(),
  groups: z.array(z.object({ key: z.string(), items: z.array(z.string()) })).optional(),
  languages: z.array(z.string()).optional(),
  updated_at: z.string().optional(),
  footer: ClientFooterSchema.optional(),
});
export type ClientSettings = z.infer<typeof ClientSettingsSchema>;

// ---------------------------------------------------------------------------
// Connectors (configurer/connecteurs) — the real Tessera stack
// ---------------------------------------------------------------------------

const CxKpiSchema = z.object({
  key: z.string(),
  value: z.string(),
  sub: z.string(),
  series: z.array(z.number()),
});
const CxSliceSchema = z.object({
  key: z.string(),
  count: z.number().int(),
  pct: z.number(),
  color: z.string(),
});

export const ConnectorsOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string().optional(),
  kpis: z.array(CxKpiSchema).optional(),
  connectors: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        category: z.string(),
        status: z.enum(["active", "standby", "degraded", "error"]),
        environment: z.string(),
        latency: z.string(),
        last_check: z.string(),
        description: z.string(),
        endpoint: z.string(),
        auth: z.string(),
        version: z.string(),
        role: z.string(),
      }),
    )
    .optional(),
  distribution: z.array(CxSliceSchema).optional(),
  footer: z.object({ total: z.number().int().optional(), source: z.string() }).optional(),
});
export type ConnectorsOverview = z.infer<typeof ConnectorsOverviewSchema>;

// ---------------------------------------------------------------------------
// Users (admin/utilisateurs) — real seeded operator accounts + RBAC caps
// ---------------------------------------------------------------------------

export const UsersOverviewSchema = z.object({
  available: z.boolean(),
  generated_at: z.string().optional(),
  kpis: z.array(CxKpiSchema).optional(),
  users: z
    .array(
      z.object({
        username: z.string(),
        display: z.string(),
        role: z.string(),
        role_label: z.string(),
        team: z.string(),
        email: z.string(),
        status: z.string(),
        last_login: z.string(),
        mfa: z.boolean(),
        caps: z.array(z.string()),
        scope: z.string(),
        badge: z.string(),
      }),
    )
    .optional(),
  distribution: z.array(CxSliceSchema).optional(),
  footer: z.object({ total: z.number().int().optional(), source: z.string() }).optional(),
});
export type UsersOverview = z.infer<typeof UsersOverviewSchema>;

/**
 * The batched snapshot envelope (ADR 0015 §Performance).
 *
 * Deliberately permissive: each signal's payload is validated later by the SAME schema its
 * own route used (`selectSignal` in `lib/overview-snapshot.ts`), so this schema must not be
 * the place a slice is silently coerced. `data` absent ⇒ the backend had nothing to say, and
 * that must survive to the card as honest-empty.
 */
export const OverviewSnapshotSchema = z.object({
  scope: z.unknown().optional(),
  signals: z
    .record(
      z.string(),
      z.object({
        data: z.unknown().optional(),
        report: z.unknown().optional(),
      }),
    )
    .optional(),
  meta: z.unknown().optional(),
});
export type OverviewSnapshotEnvelope = z.infer<typeof OverviewSnapshotSchema>;

/**
 * A control's curve, as buckets of the payload the point value is computed from
 * (`/observability/control-series`).
 *
 * `payload` is deliberately `z.unknown()` and not a restatement of `ControlPayload`. The
 * bucket is fed straight to `readControls` — the same function, and the same per-source
 * schemas, the live number goes through — so declaring the shape a second time here would
 * create exactly the second contract this endpoint exists to avoid. Zod strips undeclared
 * keys, so a narrower schema would also silently delete whichever source it had not heard
 * of yet, and the curve for that control would go quietly flat.
 *
 * `unwindowed` maps a payload key to the reason it appears in no bucket. It is what lets a
 * row say "no curve, and here is why" instead of leaving an empty chart slot that reads as
 * a metric which never moves.
 */
export const ControlSeriesSchema = z.object({
  days: z.number().nullable(),
  n_buckets: z.number(),
  since: z.string().nullable(),
  until: z.string().nullable(),
  buckets: z.array(
    z.object({
      index: z.number(),
      since: z.string(),
      until: z.string(),
      payload: z.record(z.string(), z.unknown()),
    }),
  ),
  unwindowed: z.record(z.string(), z.string()),
});
export type ControlSeries = z.infer<typeof ControlSeriesSchema>;

/**
 * Every fleet agent's snapshot in one response (`/observability/fleet-snapshot`).
 *
 * Collapses the GOUVERNER breakdown's per-agent snapshot fan-out into a single round-trip.
 * Each element's `snapshot` is the SAME `OverviewSnapshotSchema` a single-agent read returns —
 * the backend reuses the same builder per agent, so a slice here is byte-identical to
 * `/observability/snapshot?agent=<id>` (pinned by `tests/unit/test_fleet_snapshot_parity.py`).
 * An agent whose compute failed is simply absent — the loader resolves it to `undefined` and
 * the row renders its honest refusal, exactly as a failed individual fetch did.
 */
export const FleetSnapshotSchema = z.object({
  agents: z.array(z.object({ agent_id: z.string(), snapshot: OverviewSnapshotSchema })),
});
export type FleetSnapshot = z.infer<typeof FleetSnapshotSchema>;

/**
 * The coalesced fleet read (`/observability/fleet-batch`): the fleet rollup AND the per-agent
 * snapshot fan-out in ONE round-trip — the two independent reads a GOUVERNER breakdown used to
 * await in series, each one a full tunnel round-trip.
 *
 * Each half is `unknown` here on purpose and re-validated by the loader with the very schema its
 * own route used (`FleetSchema`, `FleetSnapshotSchema`), so a half is byte-identical to the
 * standalone fetch (`tests/unit/test_fleet_batch_parity.py` pins that at the wire) and one half's
 * refusal cannot empty the other: a rollup that came back unavailable still leaves every agent's
 * snapshot readable, and vice versa — the same two independent degradations as before.
 */
export const FleetBatchSchema = z.object({
  fleet: z.unknown(),
  /** Present only when the caller asked for the per-agent fan-out (`?signals=`). */
  fleet_snapshot: z.unknown(),
  /** The org-wide snapshot, present only when asked for (`?org_signals=`) — the quality plan. */
  snapshot: z.unknown(),
});
export type FleetBatch = z.infer<typeof FleetBatchSchema>;

/**
 * The multiplex read (`/observability/batch`): several card reads in one response.
 *
 * `panels` maps each requested key to the SAME payload that key's individual endpoint returns —
 * left as `unknown` here and re-validated by each card with the very schema its own route used, so
 * a panel is byte-identical to the standalone fetch (`tests/unit/test_obs_batch_parity.py`). A key
 * whose compute failed is simply absent; the card then renders its honest-empty, exactly as a
 * failed individual fetch did. Collapses a page's fan-out of tunnel round-trips into one.
 */
export const BatchSchema = z.object({
  panels: z.record(z.string(), z.unknown()),
});
export type BatchEnvelope = z.infer<typeof BatchSchema>;

// ---------------------------------------------------------------------------
// Public `/comprendre` proof facts — one backend aggregate, tile-level empties
// ---------------------------------------------------------------------------

export const ComprendrePayloadSchema = z
  .object({
    available: z.literal(true),
    generated_at: z.string().min(1),
    fleet: z
      .object({
        observed_agents: z.number().int().nonnegative().nullable(),
        last_signal_at: z.string().min(1).nullable(),
        is_silent: z.boolean().nullable(),
        window_hours: z.number().int().positive(),
      })
      .strict(),
    guard: z
      .object({
        controlled_today: z.number().int().nonnegative().nullable(),
        blocked_today: z.number().int().nonnegative().nullable(),
        since: z.string().min(1),
      })
      .strict(),
    evaluations: z
      .object({
        ready_agents: z.number().int().nonnegative().nullable(),
        review_agents: z.number().int().nonnegative().nullable(),
      })
      .strict(),
    audit: z
      .object({
        last_verified_at: z.string().min(1).nullable(),
      })
      .strict(),
  })
  .strict();

export const ComprendreResponseSchema = z.discriminatedUnion("available", [
  ComprendrePayloadSchema,
  z.object({ available: z.literal(false) }).strict(),
]);
export type ComprendreResponse = z.infer<typeof ComprendreResponseSchema>;
