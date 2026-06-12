/**
 * Overview cockpit — shared types, tone helpers and signal derivation.
 *
 * The cockpit at `/[locale]` is an executive summary of the *live* backend:
 * every number is read from the `/observability/*`, `/audit` and `/healthz`
 * surfaces (see `lib/api/client.ts`) and the offline eval scorecards. This
 * module holds only the presentation-time glue — tone → CSS class maps and the
 * pure functions that turn a measured value into a coloured state — plus the
 * static UI affordances (action buttons, which are interactions, not metrics).
 *
 * There is deliberately NO mock data here: the previous hardcoded KPIs, cases
 * and incidents were removed so the dashboard cannot display fabricated
 * figures (CLAUDE.md honesty discipline).
 */
import type { LucideIcon } from "lucide-react";
import { Flame, History, PlayCircle, ShieldAlert, Ticket } from "lucide-react";

export type OverviewTone = "success" | "warning" | "danger" | "info" | "neutral" | "gold";

export const toneText: Record<OverviewTone, string> = {
  success: "text-emerald-400",
  warning: "text-orange-400",
  danger: "text-red-400",
  info: "text-blue-400",
  neutral: "text-[var(--muted-foreground)]",
  gold: "text-gold-400",
};

export const toneBg: Record<OverviewTone, string> = {
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  warning: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  danger: "border-red-500/30 bg-red-500/10 text-red-300",
  info: "border-blue-500/30 bg-blue-500/10 text-blue-300",
  neutral: "border-[var(--border)] bg-[var(--muted)]/50 text-[var(--foreground)]",
  gold: "border-gold-500/30 bg-gold-500/10 text-gold-300",
};

export const dotBg: Record<OverviewTone, string> = {
  success: "bg-emerald-400",
  warning: "bg-orange-400",
  danger: "bg-red-400",
  info: "bg-blue-400",
  neutral: "bg-slate-400",
  gold: "bg-gold-400",
};

/** Which direction is "good" for a measured rate. */
export type Direction = "higher" | "lower";

/** A control's qualitative state, derived from a value against its target. */
export type StateKey = "ok" | "warn" | "fail";

export interface ControlState {
  key: StateKey;
  tone: OverviewTone;
}

/**
 * Classify a measured value against a target threshold.
 *
 * `higher` direction means larger is better (e.g. faithfulness ≥ 0.8);
 * `lower` means smaller is better (e.g. toxicity ≤ 0.1%). A value within
 * `warnBand` (relative) of the target on the wrong side is a warning rather
 * than an outright failure.
 */
export function controlState(
  value: number,
  target: number,
  direction: Direction,
  warnBand = 0.15,
): ControlState {
  const meets = direction === "higher" ? value >= target : value <= target;
  if (meets) return { key: "ok", tone: "success" };
  const margin =
    direction === "higher" ? (target - value) / (target || 1) : (value - target) / (target || 1);
  if (margin <= warnBand) return { key: "warn", tone: "warning" };
  return { key: "fail", tone: "danger" };
}

/** Tone for a 0..1 rate where higher is better (e.g. an SLO good-rate). */
export function rateTone(rate: number): OverviewTone {
  if (rate >= 0.8) return "success";
  if (rate >= 0.5) return "warning";
  return "danger";
}

/** Format a 0..1 fraction as a percentage string. */
export function pct(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Format a 0..1 score on the conventional /100 cockpit scale. */
export function score100(value: number): string {
  return `${Math.round(value * 100)}/100`;
}

// ---------------------------------------------------------------------------
// Static UI affordances — buttons/interactions, not data. Each maps to a real
// capability the cockpit can trigger (red-team run, replay, ticket…).
// ---------------------------------------------------------------------------

export interface QuickAction {
  /** i18n key under `overview.quick`. */
  key: string;
  icon: LucideIcon;
  tone: OverviewTone;
}

export const quickActions: QuickAction[] = [
  { key: "redteam", icon: Flame, tone: "danger" },
  { key: "freezeReleases", icon: ShieldAlert, tone: "warning" },
  { key: "replay", icon: History, tone: "info" },
  { key: "ticket", icon: Ticket, tone: "neutral" },
  { key: "replayAt", icon: PlayCircle, tone: "success" },
];
