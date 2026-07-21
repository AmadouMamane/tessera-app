import type { LauncherSignal } from "@/lib/server/launcher-signal";

/**
 * The launcher's three product pillars — Supervise · Evaluate & secure · Prove —
 * each paired with the REAL system state carried by the public-safe signal.
 *
 * Pure and client-safe (it imports only the TYPE of the server-only signal, which
 * erases at compile time): it maps the signal to i18n keys + a display tone; the
 * component does the translation and rendering. No value is ever invented — a
 * missing or uncertain source yields an HONEST state key ("évaluations actives",
 * "vérification indisponible"), never a fabricated "prêt"/"vérifiée".
 */
export type PillarKey = "supervise" | "evaluate" | "prove";

/**
 * Display tone, NOT a raw status. `live`/`govern` are the neutral capability
 * accents (cyan / champagne); `verified`/`unverified`/`neutral` recolour the
 * PROOFS state by the real verification verdict (§5: status colours are reserved
 * for real states — a gate holding an agent back is not painted red here).
 */
export type PillarTone = "live" | "govern" | "verified" | "unverified" | "neutral";

export interface Pillar {
  key: PillarKey;
  /** i18n key of the capability NAME (the label, not a metric). */
  titleKey: string;
  /** i18n key of the real system STATE shown under the name. */
  stateKey: string;
  /** ICU variables for `stateKey` (agent count, ready/total) — real numbers only. */
  stateVars?: Record<string, number>;
  tone: PillarTone;
}

/**
 * Build the three pillars from the signal, or `null` when there is no signal at
 * all (the band then renders a single honest "indisponible").
 */
export function launcherPillars(signal: LauncherSignal | null): Pillar[] | null {
  if (!signal) return null;

  // 1 · Supervise — the real fleet size under observation. Singular/plural is
  // handled by the ICU `plural` in `agentsSupervised`; `agentsCount` is always
  // ≥ 1 here (a zero-agent fleet yields a null signal upstream).
  const supervise: Pillar = {
    key: "supervise",
    titleKey: "signal.pillarSupervise",
    stateKey: "signal.agentsSupervised",
    stateVars: { count: signal.agentsCount },
    tone: "live",
  };

  // 2 · Evaluate & secure — "release gates actifs · {ready}/{total} prêts" ONLY
  // when the gate really produces verdicts (≥ 1 agent has a real release verdict);
  // the ready count is the gate's OWN verdict, never inferred from a blended score.
  // With no verdict yet, the honest "évaluations actives" — the capability is on,
  // the gate simply has nothing to clear.
  const gatesActive = signal.agentsWithRelease > 0;
  const evaluate: Pillar = {
    key: "evaluate",
    titleKey: "signal.pillarEvaluate",
    stateKey: gatesActive ? "signal.releaseGatesReady" : "signal.evaluationsActive",
    stateVars: gatesActive
      ? { ready: signal.passedAgents, total: signal.agentsWithRelease }
      : undefined,
    tone: "govern",
  };

  // 3 · Prove — "chaîne d'intégrité vérifiée" ONLY when the audit chain actually
  // re-derives (content_integrity == true). A proven break → "non vérifiée"; an
  // unreachable check → "vérification indisponible". Never verified from the mere
  // existence of audit entries.
  const verified = signal.integrityVerified;
  const prove: Pillar = {
    key: "prove",
    titleKey: "signal.pillarProve",
    stateKey:
      verified === true
        ? "signal.integrityVerified"
        : verified === false
          ? "signal.integrityUnverified"
          : "signal.integrityUnavailable",
    tone: verified === true ? "verified" : verified === false ? "unverified" : "neutral",
  };

  return [supervise, evaluate, prove];
}
