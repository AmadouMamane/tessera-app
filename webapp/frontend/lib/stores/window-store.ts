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
}

export const useWindowStore = create<WindowState>((set) => ({
  period: "d7",
  setPeriod: (period) => set({ period }),
}));
