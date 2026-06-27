"use client";

/**
 * Deep-link for the SURVEILLER signal scrubber (SR-01, registre §1/§5).
 *
 * The temporal navigation state is the URL — not a private component state — so a
 * cockpit view is shareable and survives reload, and the active mode never drifts
 * from what the address bar says. Two params carry it:
 *
 * - ``asof`` — the focused instant T (ISO), set while scrubbing the history.
 * - ``win``  — the absolute window END (ISO) when anchored to a past day.
 *
 * Mode is *derived*, never stored: either present ⇒ Historique, else Live. The
 * window DURATION (Période) stays the shared global window (window-store), so it
 * is intentionally NOT duplicated here (registre §8 — one window owner).
 *
 * Writes use ``replaceState`` so dragging the scrubber doesn't flood history; the
 * link stays shareable all the same. Implemented on the History API (not
 * ``useSearchParams``) to stay SSR-safe and free of a Suspense boundary.
 */

import { useEffect } from "react";

export interface TemporalUrlState {
  /** Focused instant T (ISO) or null when live. */
  asof: string | null;
  /** Absolute anchored window END (ISO) or null when live. */
  win: string | null;
}

const LIVE: TemporalUrlState = { asof: null, win: null };

/** Read the temporal state from the current URL (SSR-safe → live as default). */
export function readTemporalUrl(): TemporalUrlState {
  if (typeof window === "undefined") return LIVE;
  const p = new URLSearchParams(window.location.search);
  return { asof: p.get("asof"), win: p.get("win") };
}

/** Mirror the temporal state into the URL (replaceState — shareable, no spam). */
export function writeTemporalUrl(state: TemporalUrlState): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  const apply = (key: string, value: string | null) => {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  };
  apply("asof", state.asof);
  apply("win", state.win);
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
