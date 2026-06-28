"use client";

/**
 * Deep-link for the SURVEILLER signal scrubber (SR-01, registre §1/§5).
 *
 * The temporal navigation state is the URL — not a private component state — so a
 * cockpit view is shareable, survives reload, and the active reading never drifts
 * from what the address bar says. The URL is the reproducible source of truth:
 * same URL + same scope + same instant/period + same comparison = same view.
 *
 * Params carried (all optional; defaults reconstruct "live"):
 *
 * - ``lecture`` — live | asOf | history (omitted when live). The user-facing reading.
 * - ``period``  — h24 | d7 | d30 (omitted when d7). The shared window duration.
 * - ``asof``    — instant T (ISO) when lecture=asOf.
 * - ``at``      — scrub cursor (ISO) when lecture=history (optional).
 * - ``to``      — absolute window END (ISO) to freeze a history window (optional input;
 *                 normal rolling history never writes it — it ends "now").
 * - ``compare`` — target | previous_period | baseline | previous_release | now | none
 *                 (omitted when "target").
 * - ``expanded``— "1" when the scrubber panel is open.
 *
 * The agent scope rides the separate ``?agent=`` param (lib/agent-scope) — NOT
 * duplicated here. Writes use ``replaceState`` so dragging the scrubber doesn't
 * flood history; the link stays shareable all the same. Implemented on the History
 * API (not ``useSearchParams``) to stay SSR-safe and free of a Suspense boundary.
 */

import { useEffect } from "react";

/** Internal reading values (kept everywhere in code/state/tests). */
export type Reading = "live" | "asof" | "historique";

export interface TemporalUrlState {
  /** User-facing reading, reconstructed from the URL (defaults to "live"). */
  reading: Reading;
  /** Window duration key, or null when the default (d7). */
  period: string | null;
  /** As-of instant T (ISO) or null. */
  asof: string | null;
  /** History scrub cursor (ISO) or null. */
  at: string | null;
  /** Frozen history window END (ISO) or null (rolling = ends now). */
  to: string | null;
  /** Comparison baseline value, or null when the default ("target"). */
  compare: string | null;
  /** Whether the scrubber panel is open. */
  expanded: boolean;
}

const LIVE: TemporalUrlState = {
  reading: "live",
  period: null,
  asof: null,
  at: null,
  to: null,
  compare: null,
  expanded: false,
};

/** Map the internal reading to its URL token (camelCase / "history"). */
function lectureToken(reading: Reading): string {
  return reading === "asof" ? "asOf" : reading === "historique" ? "history" : "live";
}

/** Parse a ``lecture`` URL token back to the internal reading (robust to either spelling). */
function parseLecture(raw: string | null): Reading {
  if (raw === "asOf" || raw === "asof") return "asof";
  if (raw === "history" || raw === "historique" || raw === "historical") return "historique";
  return "live";
}

/** Read the temporal state from the current URL (SSR-safe → live as default). */
export function readTemporalUrl(): TemporalUrlState {
  if (typeof window === "undefined") return LIVE;
  const p = new URLSearchParams(window.location.search);
  return {
    reading: parseLecture(p.get("lecture")),
    period: p.get("period"),
    asof: p.get("asof"),
    at: p.get("at"),
    to: p.get("to"),
    compare: p.get("compare"),
    expanded: p.get("expanded") === "1",
  };
}

/** Mirror the temporal state into the URL (replaceState — shareable, no spam). */
export function writeTemporalUrl(state: {
  reading: Reading;
  period: string;
  asof: string | null;
  at: string | null;
  to?: string | null;
  compare: string;
  expanded: boolean;
}): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  const apply = (key: string, value: string | null) => {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  };
  // Omit defaults so a live, default view keeps a clean URL; reads reconstruct them.
  apply("lecture", state.reading === "live" ? null : lectureToken(state.reading));
  apply("period", state.period && state.period !== "d7" ? state.period : null);
  apply("asof", state.reading === "asof" ? state.asof : null);
  apply("at", state.reading === "historique" ? state.at : null);
  apply("to", state.reading === "historique" ? (state.to ?? null) : null);
  apply("compare", state.compare && state.compare !== "target" ? state.compare : null);
  apply("expanded", state.expanded ? "1" : null);
  if (url.toString() !== window.location.href) {
    window.history.replaceState(window.history.state, "", url.toString());
  }
}

/** Re-read the URL on back/forward so it stays the single source of truth. */
export function useTemporalUrlPopstate(onChange: (state: TemporalUrlState) => void): void {
  useEffect(() => {
    const handler = () => onChange(readTemporalUrl());
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, [onChange]);
}
