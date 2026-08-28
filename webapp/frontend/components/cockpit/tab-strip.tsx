"use client";

import type { LucideIcon } from "lucide-react";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

/**
 * Premium pill tab strip — the bandeau first crafted for Qualité IA, extracted
 * so every tabbed cockpit page shares the same shell while keeping its OWN
 * accent. Harmony is per page: green for quality, blue for the config/cockpit
 * planes, violet for the agent + conformité planes. Pass `accent` accordingly —
 * never a uniform colour across pages.
 *
 * Items render as a `<button>` (controlled, via `onChange`) or as a `<Link>`
 * when `href` is set (URL-driven strips like the AGENT command bar). The caller
 * computes which key is `active`.
 */
export type TabAccent = "green" | "blue" | "violet";

export type TabStripItem<K extends string> = {
  key: K;
  label: string;
  icon?: LucideIcon;
  /** When set, the item renders as an i18n `<Link>` instead of a button. */
  href?: string;
};

// Segmented control: each tab is its own bordered cell (clear separation between
// columns), the active one a soft tinted segment — no gradient/glow, so it blends
// into the page instead of grabbing the eye.
const ACCENTS: Record<TabAccent, { active: string; activeIcon: string }> = {
  green: {
    active: "border-[#0c9a6f]/40 bg-[#0c9a6f]/15 text-[var(--tessera-fg-success)]",
    activeIcon: "text-[var(--tessera-fg-success)]",
  },
  blue: {
    active: "border-[#2e72d2]/40 bg-[#2e72d2]/15 text-[var(--tessera-fg-info)]",
    activeIcon: "text-[var(--tessera-fg-info)]",
  },
  violet: {
    active: "border-[#7c5cf5]/40 bg-[#7c5cf5]/15 text-[var(--tessera-fg-accent)]",
    activeIcon: "text-[var(--tessera-fg-accent)]",
  },
};

const NAV_CLASS =
  "flex flex-wrap items-center gap-1 rounded-xl border border-white/[0.05] bg-[var(--tessera-surface)]/40 px-1.5 py-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]";

const BTN_BASE =
  "group relative flex items-center gap-1.5 whitespace-nowrap rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors duration-150";

const INACTIVE =
  "border-white/[0.06] bg-white/[0.02] text-[var(--tessera-text-muted)] hover:border-white/[0.12] hover:bg-white/[0.05] hover:text-[var(--tessera-text)]";

export function TabStrip<K extends string>({
  items,
  active,
  onChange,
  accent = "blue",
  className,
  "data-testid": testId,
}: {
  items: ReadonlyArray<TabStripItem<K>>;
  active: K;
  onChange?: (key: K) => void;
  accent?: TabAccent;
  className?: string;
  "data-testid"?: string;
}) {
  const a = ACCENTS[accent];
  return (
    <nav className={cn(NAV_CLASS, className)} data-testid={testId}>
      {items.map((item) => (
        <TabStripNode
          key={item.key}
          item={item}
          on={item.key === active}
          accent={a}
          onChange={onChange}
        />
      ))}
    </nav>
  );
}

function TabStripNode<K extends string>({
  item,
  on,
  accent,
  onChange,
}: {
  item: TabStripItem<K>;
  on: boolean;
  accent: { active: string; activeIcon: string };
  onChange?: (key: K) => void;
}) {
  const { key, label, icon: Icon, href } = item;
  const cls = cn(BTN_BASE, on ? accent.active : INACTIVE);
  const inner = (
    <>
      {Icon ? (
        <Icon
          className={cn(
            "h-3.5 w-3.5 transition-colors",
            on
              ? accent.activeIcon
              : "text-[var(--tessera-text-muted)] group-hover:text-[var(--tessera-text)]",
          )}
        />
      ) : null}
      {label}
    </>
  );
  return href ? (
    <Link href={href} aria-current={on ? "page" : undefined} className={cls}>
      {inner}
    </Link>
  ) : (
    <button
      type="button"
      aria-current={on ? "page" : undefined}
      onClick={() => onChange?.(key)}
      className={cls}
    >
      {inner}
    </button>
  );
}
