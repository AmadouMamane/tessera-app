"use client";

import type { ComponentLink, ConsequenceState } from "@/lib/api/schemas";

/**
 * Shared vocabulary for the observability page, in one file so the six blocks cannot drift into
 * two colour languages for the same three states.
 */

/** A probe verdict → the tone it wears. `blind` is amber, and never green. */
export function verdictTone(verdict: string): "success" | "danger" | "warning" | "neutral" {
  if (verdict === "ok") return "success";
  if (verdict === "fail") return "danger";
  if (verdict === "skip") return "neutral";
  return "warning"; // blind, and anything unknown — a state we cannot read is not a pass
}

/** A capability's standing → its tone. Same rule: `cannot_say` is amber, never green. */
export function stateTone(state: ConsequenceState): "success" | "danger" | "warning" {
  if (state === "served") return "success";
  return state === "lost" ? "danger" : "warning";
}

/**
 * The link for one component, and whether its address is only true on the deployment host.
 *
 * This started stricter — a loopback link was rendered as inert text unless the page was itself
 * served over loopback — and that was wrong in the case that actually matters. The operator
 * reading `https://tessera.<domain>` is very often sitting **at** the deployment host, where
 * `127.0.0.1:13000` opens Grafana perfectly; refusing to link it hands them five chips that do
 * nothing, which is the complaint that produced this note. A page cannot detect that vantage
 * point either: probing the address is blocked, and the page's own origin only tells you how the
 * reader reached *this* app, not where they are.
 *
 * So the link is always a link, and what is *known* is said instead of guessed: `hostLocal` marks
 * an address that resolves only on the deployment host, and the UI labels it — visibly, not in a
 * tooltip. That is the honest trade. A reader elsewhere is told before they click; a reader on
 * the host gets the door. Withholding a working door is its own kind of dishonesty.
 */
export interface ResolvedLink {
  url: string;
  /** True when the address names loopback — meaningful only from the deployment host. */
  hostLocal: boolean;
}

export function resolveLink(links: ComponentLink[] | undefined, key: string): ResolvedLink | null {
  const link = links?.find((candidate) => candidate.key === key);
  if (!link) return null;
  return { url: link.url, hostLocal: link.loopback };
}

/**
 * The observation instant, as a Date that cannot be in the future.
 *
 * `observed_at` is the SERVER's wall clock and it is rendered against the BROWSER's. A skew of a
 * few hundred milliseconds — routine, and guaranteed the moment the agent runs in a container —
 * makes `relativeTime` say "in 2 seconds" about something that already happened. That reads as a
 * bug in the page, and worse, it undermines the one thing this stamp is here to establish: that
 * the reader is being told when the probe actually looked. Clamping keeps a skewed clock from
 * turning an honest disclosure into an obvious falsehood.
 *
 * Clamping alone did NOT fix it, which is why {@link relativeNow} exists beside it: next-intl
 * compares against the `now` its provider captured at SERVER RENDER, so a probe that ran after
 * the page was rendered is in that comparison's future however carefully this value is bounded.
 * The page kept saying "vérifié dans 2 secondes" with the clamp already in place — a fix that
 * addressed a real cause, and not the one on screen.
 */
export function observedAt(epochSeconds: number): Date {
  return new Date(Math.min(epochSeconds * 1000, Date.now()));
}

/**
 * The instant to compare a freshness stamp against — the BROWSER's now, passed explicitly.
 *
 * `useFormatter().relativeTime(date)` defaults to the `now` held by `NextIntlClientProvider`,
 * which is fixed at server render and does not advance. Every stamp on this page is read after
 * that instant, so the default reference makes recent events read as future ones. Only call it
 * where the data has already arrived (i.e. not during the first server pass), which is the case
 * for every caller here: the branches that render a stamp all sit behind a resolved query.
 */
export function relativeNow(): Date {
  return new Date();
}

/** Seconds → a compact duration an operator reads at a glance ("3 h 12", "4 min"). */
export function humanSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return minutes > 0 ? `${hours} h ${String(minutes).padStart(2, "0")}` : `${hours} h`;
}
