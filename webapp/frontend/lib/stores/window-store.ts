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
}

export const useWindowStore = create<WindowState>((set) => ({
  period: "d7",
  setPeriod: (period) => set({ period }),
  anchorEnd: null,
  setAnchorEnd: (anchorEnd) => set({ anchorEnd }),
}));
