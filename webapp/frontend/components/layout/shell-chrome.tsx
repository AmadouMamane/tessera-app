"use client";

import { useTranslations } from "next-intl";
import { type ReactNode, createContext, useCallback, useContext, useEffect, useState } from "react";

import { CommandPalette } from "./command-palette";

/**
 * Shell-wide chrome state + power-user keyboard gestures, mounted once in the
 * AppShell so every cockpit page inherits them:
 *
 *  - ⌘B  toggle the sidebar between full and an icon rail (persisted).
 *  - ⌘.  toggle a distraction-free focus mode (session only — never persisted,
 *        so a reload never strands the operator with no chrome).
 *  - Esc  exit focus mode (and the command palette, wired in shell-chrome too).
 *
 * The command-palette open state lives here as well so ⌘K (added alongside the
 * palette) can drive it from one place.
 */
const COLLAPSE_KEY = "tessera.sidebarCollapsed";

interface ShellChromeValue {
  collapsed: boolean;
  toggleCollapsed: () => void;
  focus: boolean;
  toggleFocus: () => void;
  exitFocus: () => void;
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
}

const ShellChromeContext = createContext<ShellChromeValue | null>(null);

export function useShellChrome(): ShellChromeValue {
  const ctx = useContext(ShellChromeContext);
  if (!ctx) throw new Error("useShellChrome must be used within <ShellChrome>");
  return ctx;
}

export function ShellChrome({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [focus, setFocus] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Hydrate the persisted collapsed preference after mount (avoids SSR mismatch).
  useEffect(() => {
    setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((c) => {
      const next = !c;
      window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }, []);

  const toggleFocus = useCallback(() => setFocus((f) => !f), []);
  const exitFocus = useCallback(() => setFocus(false), []);

  // Global keyboard gestures. ⌘K is registered with the palette (separate
  // concern); here we own ⌘B, ⌘. and the Esc fall-through for focus mode.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();
      if (meta && key === "b") {
        event.preventDefault();
        toggleCollapsed();
      } else if (meta && event.key === ".") {
        event.preventDefault();
        setFocus((f) => !f);
      } else if (meta && key === "k") {
        event.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (event.key === "Escape" && focus && !paletteOpen) {
        setFocus(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleCollapsed, focus, paletteOpen]);

  return (
    <ShellChromeContext.Provider
      value={{
        collapsed,
        toggleCollapsed,
        focus,
        toggleFocus,
        exitFocus,
        paletteOpen,
        setPaletteOpen,
      }}
    >
      {children}
      {focus ? <FocusHint onExit={exitFocus} /> : null}
      <CommandPalette />
    </ShellChromeContext.Provider>
  );
}

/** Discreet, always-present way out of focus mode (the gesture is non-persisted,
 *  but the operator must never wonder how to get the chrome back). */
function FocusHint({ onExit }: { onExit: () => void }) {
  const t = useTranslations("shell");
  return (
    <button
      type="button"
      onClick={onExit}
      className="fade-in-0 fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 animate-in items-center gap-2 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-surface)]/90 px-3 py-1.5 text-[0.7rem] text-[var(--tessera-text-muted)] shadow-[0_8px_30px_rgba(0,0,0,0.35)] backdrop-blur transition-colors hover:text-[var(--tessera-text)] motion-reduce:animate-none"
    >
      <kbd className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 font-mono text-[0.62rem]">
        Esc
      </kbd>
      {t("focus.exitHint")}
    </button>
  );
}
