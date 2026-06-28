/**
 * Single owner of the cockpit's temporal WINDOW (the period: h24 / d7 / d30).
 *
 * The window is SHARED STATE, not a property of any rail (ADR 0011). It is set in
 * ONE place — the page's top toolbar control — and READ by everything that needs
 * it (the KPIs and the time rail). The rail never owns the window: it reads this
 * store and renders only its own job (anchor / replay / compare / scrub), so the
 * window can never be duplicated nor lost.
 *
 * Ephemeral on purpose (no persistence): a fresh load is the default window.
 */
import { create } from "zustand";

interface WindowState {
  /** Active window key: "h24" | "d7" | "d30". */
  period: string;
  setPeriod: (period: string) => void;
  /**
   * Absolute window END as an ISO instant (end of the chosen day), or null = now
   * (live). The period spans backwards from here. Set from the SR-01 signal
   * scrubber's "Aller à une date" calendar so the window can travel over a long
   * production history; the rail reads it back to anchor its axis. null keeps the
   * page live.
   */
  anchorEnd: string | null;
  setAnchorEnd: (anchorEnd: string | null) => void;
  /**
   * Baseline lens for reading the past — "target" (the SLO objective), "now" (the
   * present value), or "none". It is a temporal-window dimension (registre §5), so
   * it lives here with the period, NOT as a private rail state: every SURVEILLER
   * page reads the SAME "Comparer à". Only baselines that are actually computable
   * are offered by the bar; an uncomputable one falls back to "none".
   */
  compare: string;
  setCompare: (compare: string) => void;
}

export const useWindowStore = create<WindowState>((set) => ({
  period: "d7",
  setPeriod: (period) => set({ period }),
  anchorEnd: null,
  setAnchorEnd: (anchorEnd) => set({ anchorEnd }),
  compare: "target",
  setCompare: (compare) => set({ compare }),
}));
