"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, type LucideIcon, PanelLeft, Search, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { fetchFleet } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { useShellChrome } from "./shell-chrome";
import { navLeaves } from "./sidebar";

interface Command {
  id: string;
  label: string;
  group: string;
  icon: LucideIcon;
  run: () => void;
}

/**
 * ⌘K command palette — fuzzy search over REAL destinations/actions only:
 *  - Agents from the live fleet registry (switch the active agent).
 *  - Pages from the real sidebar route map (navLeaves).
 *  - Actions that are genuinely wired (focus mode, sidebar rail, open the fleet).
 * No fabricated entry: an action that is not wired simply does not appear.
 */
export function CommandPalette() {
  const { paletteOpen, setPaletteOpen, toggleFocus, toggleCollapsed } = useShellChrome();
  const t = useTranslations("nav");
  const tp = useTranslations("shell.palette");
  const router = useRouter();
  const pathname = usePathname();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);

  const { data: fleet } = useQuery({
    queryKey: ["fleet-palette"],
    queryFn: ({ signal }) => fetchFleet(signal),
    staleTime: 60_000,
    enabled: paletteOpen,
  });
  const agents = fleet?.agents ?? [];
  const subPage = pathname.match(/\/agents\/[^/]+\/(.+)$/)?.[1] ?? "synthese";

  const commands = useMemo<Command[]>(() => {
    const close = () => setPaletteOpen(false);
    const go = (href: string) => {
      close();
      router.push(href as Parameters<typeof router.push>[0]);
    };
    return [
      ...agents.map(
        (a): Command => ({
          id: `agent:${a.id}`,
          label: a.name,
          group: tp("agents"),
          icon: Bot,
          run: () => go(agentPath(a.id, subPage)),
        }),
      ),
      ...navLeaves().map(
        (leaf): Command => ({
          id: `page:${leaf.href}`,
          label: t(leaf.labelKey),
          group: tp("pages"),
          icon: leaf.icon,
          run: () => go(leaf.href),
        }),
      ),
      {
        id: "action:focus",
        label: tp("toggleFocus"),
        group: tp("actions"),
        icon: Sparkles,
        run: () => {
          close();
          toggleFocus();
        },
      },
      {
        id: "action:sidebar",
        label: tp("toggleSidebar"),
        group: tp("actions"),
        icon: PanelLeft,
        run: () => {
          close();
          toggleCollapsed();
        },
      },
      {
        id: "action:fleet",
        label: tp("fleet"),
        group: tp("actions"),
        icon: Bot,
        run: () => go("/agents"),
      },
    ];
  }, [agents, subPage, t, tp, router, setPaletteOpen, toggleFocus, toggleCollapsed]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.group.toLowerCase().includes(q),
    );
  }, [commands, query]);

  // Reset the highlight to the top whenever the query changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: query drives the reset, it is not read in the body
  useEffect(() => {
    setSelected(0);
  }, [query]);
  useEffect(() => {
    if (paletteOpen) {
      setQuery("");
      setSelected(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [paletteOpen]);
  // Keep the selected row in view.
  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-idx="${selected}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  if (!paletteOpen) return null;

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelected((s) => Math.min(s + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      filtered[selected]?.run();
    } else if (event.key === "Escape") {
      event.preventDefault();
      setPaletteOpen(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/50 px-4 pt-[12vh] backdrop-blur-sm"
      onMouseDown={() => setPaletteOpen(false)}
    >
      {/* biome-ignore lint/a11y/useSemanticElements: intentional focus-trapped overlay palette, not a native <dialog> */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={tp("title")}
        onMouseDown={(e) => e.stopPropagation()}
        className="flex w-full max-w-[640px] flex-col overflow-hidden rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[0_24px_70px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-center gap-2 border-b border-[var(--tessera-border)] px-3">
          <Search className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
          {/* Focus is driven by the open effect (requestAnimationFrame → focus). */}
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={tp("placeholder")}
            className="h-12 min-w-0 flex-1 bg-transparent text-sm text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)]"
          />
          <kbd className="shrink-0 rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
            Esc
          </kbd>
        </div>
        <ul ref={listRef} className="max-h-[50vh] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <li className="px-4 py-6 text-center text-sm text-[var(--tessera-text-muted)]">
              {tp("empty")}
            </li>
          ) : (
            filtered.map((c, i) => (
              <li key={c.id} data-idx={i}>
                <button
                  type="button"
                  onMouseEnter={() => setSelected(i)}
                  onClick={() => c.run()}
                  className={cn(
                    "flex w-full items-center gap-3 px-3 py-2 text-left text-sm transition-colors motion-reduce:transition-none",
                    i === selected
                      ? "bg-[var(--tessera-surface-elevated)] text-[var(--tessera-text)]"
                      : "text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]",
                  )}
                >
                  <c.icon className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  <span className="shrink-0 text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                    {c.group}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
