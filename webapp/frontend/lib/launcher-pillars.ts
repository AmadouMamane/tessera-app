/**
 * The launcher's four product pillars — Supervise · Secure · Evaluate · Prove —
 * each paired with the REAL system state carried by the public-safe signal.
 *
 * Four columns because the two gates are different things and fusing them made
 * one dishonest line: the ONLINE gate (the input chokepoint every message
 * crosses, counted per message) and the RELEASE gate (exercised before
 * production, judged per agent). One column, one fact, one witness.
 *
 * Pure and client-safe: it consumes the structural `PillarSignal` subset (the
 * server's `LauncherSignal` is assignable to it, and so is the polled wire
 * payload), maps it to i18n keys + a display tone, and never invents a value —
 * a missing or uncertain source yields an HONEST state key ("évaluations
 * actives", "compteurs indisponibles", "vérification indisponible"), never a
 * fabricated "prêt"/"vérifiée".
 */

/** The structural subset of the launcher signal the pillars actually read. */
export interface PillarSignal {
  agentsCount: number;
  passedAgents: number;
  agentsWithRelease: number;
  evaluationBuckets: { ready: number; review: number } | null;
  agents: readonly { verdictStale: boolean }[];
  integrityVerified: boolean | null;
  opposabilityBadge:
    | "non_scelle"
    | "scelle_opposable"
    | "scelle_non_qualifie"
    | "integrite_partielle"
    | null;
  guardActivity: { checkedToday: number; blockedToday: number } | null;
}

export type PillarKey = "supervise" | "secure" | "evaluate" | "prove";

/**
 * Display tone, NOT a raw status. `live`/`guard`/`govern` are the neutral
 * capability accents; `stale` marks a release verdict put back in play;
 * `verified`/`unverified`/`neutral` recolour the PROOFS state by the real
 * verification verdict (§5: status colours are reserved for real states — a
 * gate holding an agent back is not painted red here).
 */
export type PillarTone =
  | "live"
  | "guard"
  | "govern"
  | "stale"
  | "verified"
  | "unverified"
  | "neutral";

export interface Pillar {
  key: PillarKey;
  /** i18n key of the capability NAME (the label, not a metric). */
  titleKey: string;
  /** i18n key of the real system STATE shown under the name. */
  stateKey: string;
  /** ICU variables for `stateKey` — real numbers only. */
  stateVars?: Record<string, number>;
  tone: PillarTone;
}

/**
 * Build the four pillars from the signal, or `null` when there is no signal at
 * all (the band then renders a single honest "indisponible").
 */
export function launcherPillars(signal: PillarSignal | null): Pillar[] | null {
  if (!signal) return null;

  // 1 · Supervise — the real fleet size under observation (passive: watching,
  // never touching). Singular/plural via ICU; `agentsCount` is always ≥ 1 here
  // (a zero-agent fleet yields a null signal upstream).
  const supervise: Pillar = {
    key: "supervise",
    titleKey: "signal.pillarSupervise",
    stateKey: "signal.agentsSupervised",
    stateVars: { count: signal.agentsCount },
    tone: "live",
  };

  // 2 · Secure — the ONLINE gate, counted per message from its two witnesses
  // (transcript turns + audited denials, today). `null` activity → an honest
  // "compteurs indisponibles"; a quiet day → a real "aucun message", never a
  // fabricated count.
  const activity = signal.guardActivity;
  const secure: Pillar =
    activity === null
      ? {
          key: "secure",
          titleKey: "signal.pillarSecure",
          stateKey: "signal.activityUnavailable",
          tone: "neutral",
        }
      : activity.checkedToday === 0
        ? {
            key: "secure",
            titleKey: "signal.pillarSecure",
            stateKey: "signal.noMessagesToday",
            tone: "guard",
          }
        : {
            key: "secure",
            titleKey: "signal.pillarSecure",
            stateKey: "signal.messagesChecked",
            stateVars: { checked: activity.checkedToday, blocked: activity.blockedToday },
            tone: "guard",
          };

  // 3 · Evaluate — the exact ready/review buckets composed by the shared
  // backend release seam. Missing, refused and stale verdicts all remain in
  // `review`; the launcher never rebuilds those semantics from agent rows.
  const buckets = signal.evaluationBuckets;
  const evaluate: Pillar = {
    key: "evaluate",
    titleKey: "signal.pillarEvaluate",
    stateKey: buckets ? "signal.evaluateBuckets" : "signal.evaluationsActive",
    stateVars: buckets ? { ready: buckets.ready, review: buckets.review } : undefined,
    tone: buckets && buckets.review > 0 ? "stale" : "govern",
  };

  // 4 · Prove — ADR 0042 reserves “registre infalsifiable” for the composed live verdict:
  // chain integrity + resolved order + fresh, verified qualified RFC 3161 seal. A chain that
  // re-hashes but lacks that external witness says so plainly; it never borrows the stronger word.
  const verified = signal.integrityVerified;
  const infalsifiable = signal.opposabilityBadge === "scelle_opposable";
  const prove: Pillar = {
    key: "prove",
    titleKey: "signal.pillarProve",
    stateKey: infalsifiable
      ? "signal.ledgerInfalsifiable"
      : verified === true
        ? "signal.integrityVerifiedSealPending"
        : verified === false
          ? "signal.integrityUnverified"
          : "signal.integrityUnavailable",
    tone: infalsifiable
      ? "verified"
      : verified === false
        ? "unverified"
        : verified === true
          ? "stale"
          : "neutral",
  };

  return [supervise, secure, evaluate, prove];
}
