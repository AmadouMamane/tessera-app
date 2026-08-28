"use client";

import { cn } from "@/lib/cn";

/**
 * Secondary tab control for AGENT pages: a segmented pill group rendered
 * below the section band (AgentTabs). The pill style deliberately differs
 * from the band's underlined tabs so the two navigation levels never blur.
 */
export function AgentSubtabs({
  tabs,
  active,
  onSelect,
}: {
  tabs: readonly string[];
  active: string;
  onSelect: (tab: string) => void;
}) {
  if (tabs.length === 0) return null;
  return (
    <div
      data-agent-subtabs
      className="flex flex-wrap items-center gap-1 self-start rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-1"
    >
      {tabs.map((tb) => {
        const on = tb === active;
        return (
          <button
            key={tb}
            type="button"
            onClick={() => onSelect(tb)}
            aria-pressed={on}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs transition-colors",
              on
                ? "bg-[var(--tessera-surface-elevated)] font-medium text-[var(--tessera-text)]"
                : "text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {tb}
          </button>
        );
      })}
    </div>
  );
}
