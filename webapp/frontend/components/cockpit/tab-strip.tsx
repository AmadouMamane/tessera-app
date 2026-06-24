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

const ACCENTS: Record<TabAccent, { active: string; activeIcon: string }> = {
  green: {
    active:
      "bg-gradient-to-b from-[#076a4d] to-[#04412f] text-[#d6f0e3] shadow-[0_1px_4px_-1px_rgba(13,148,94,0.28),0_1px_2px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.16)] ring-1 ring-inset ring-[#0c9a6f]/45",
    activeIcon: "text-[#7ff0b6]",
  },
  blue: {
    active:
      "bg-gradient-to-b from-[#0e5599] to-[#0a2f56] text-[#d8eaff] shadow-[0_1px_4px_-1px_rgba(46,114,210,0.30),0_1px_2px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.16)] ring-1 ring-inset ring-[#2e72d2]/45",
    activeIcon: "text-[#87bfff]",
  },
  violet: {
    active:
      "bg-gradient-to-b from-[#5b4bbd] to-[#33277e] text-[#e7e0ff] shadow-[0_1px_4px_-1px_rgba(124,92,245,0.30),0_1px_2px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.16)] ring-1 ring-inset ring-[#7c5cf5]/45",
    activeIcon: "text-[#b9a6ff]",
  },
};

const NAV_CLASS =
  "flex flex-wrap items-center gap-1 rounded-xl border border-white/[0.06] bg-[var(--tessera-surface)]/50 px-1.5 py-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_8px_24px_-12px_rgba(0,0,0,0.6)] backdrop-blur-md";

const BTN_BASE =
  "group relative flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[0.7rem] font-medium transition-all duration-200";

const INACTIVE =
  "text-[var(--tessera-text-muted)] hover:bg-white/[0.05] hover:text-[var(--tessera-text)]";

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
