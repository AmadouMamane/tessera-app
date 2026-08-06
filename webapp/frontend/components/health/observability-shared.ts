"use client";

import { useEffect, useState } from "react";

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
 * Whether THIS page is being served from the loopback interface.
 *
 * The one fact that decides whether a `127.0.0.1` tool link is a door or a lie. Read in an
 * effect rather than during render: the server has no `window`, and reading it during render
 * would make the first client paint disagree with the server's HTML.
 *
 * Starts `false` — so before the effect runs, a loopback link renders as "on the deployment
 * host" rather than as a live link. Erring towards the honest caption costs a reader one frame;
 * erring the other way offers a door that is not there.
 */
export function useServedFromLoopback(): boolean {
  const [loopback, setLoopback] = useState(false);
  useEffect(() => {
    const host = window.location.hostname;
    setLoopback(host === "localhost" || host === "127.0.0.1" || host === "[::1]" || host === "::1");
  }, []);
  return loopback;
}

/**
 * The link for one component, and whether it may be offered as a live one.
 *
 * A loopback URL is only true on the deployment host. Offering it to a reader on another host
 * sends them to whatever runs on *their* port 13000 — nothing, usually, and something else
 * entirely at worst. So the URL is still shown (it is useful: an operator who can reach the host
 * wants to know the port) but it stops being clickable, under a caption that says why.
 */
export interface ResolvedLink {
  url: string;
  clickable: boolean;
}

export function resolveLink(
  links: ComponentLink[] | undefined,
  key: string,
  servedFromLoopback: boolean,
): ResolvedLink | null {
  const link = links?.find((candidate) => candidate.key === key);
  if (!link) return null;
  return { url: link.url, clickable: !link.loopback || servedFromLoopback };
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
 */
export function observedAt(epochSeconds: number): Date {
  return new Date(Math.min(epochSeconds * 1000, Date.now()));
}

/** Seconds → a compact duration an operator reads at a glance ("3 h 12", "4 min"). */
export function humanSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return minutes > 0 ? `${hours} h ${String(minutes).padStart(2, "0")}` : `${hours} h`;
}
