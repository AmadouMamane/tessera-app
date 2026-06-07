"use client";

import {
  Activity,
  AlertTriangle,
  FileSearch,
  type LucideIcon,
  MessageSquareText,
  Settings,
  ShieldCheck,
  LineChart,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

interface NavItem {
  href: "/chat" | "/audit" | "/eval" | "/health" | "/settings" | "/observability";
  icon: LucideIcon;
  labelKey: "chat" | "audit" | "eval" | "health" | "settings" | "observability";
}

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { href: "/chat", icon: MessageSquareText, labelKey: "chat" },
  { href: "/eval", icon: FileSearch, labelKey: "eval" },
  { href: "/audit", icon: ShieldCheck, labelKey: "audit" },
  { href: "/observability", icon: LineChart, labelKey: "observability" },
  { href: "/health", icon: Activity, labelKey: "health" },
  { href: "/settings", icon: Settings, labelKey: "settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--card)]/55 backdrop-blur-xl">
      <BrandHeader />
      <nav className="flex-1 px-3 py-4">
        <ul className="flex flex-col gap-0.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "border-l-2 border-blue-500 bg-blue-500/10 pl-[10px] text-[var(--foreground)] shadow-[inset_0_0_16px_-6px_oklch(0.62_0.18_262/0.4)] dark:border-blue-400 dark:bg-blue-400/10 dark:text-blue-300"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]",
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0 transition-colors",
                      active
                        ? "text-blue-500 dark:text-blue-400"
                        : "text-[var(--muted-foreground)] group-hover:text-[var(--foreground)]",
                    )}
                  />
                  <span>{t(item.labelKey)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <SidebarFooter />
    </aside>
  );
}

function BrandHeader() {
  const t = useTranslations("app");
  return (
    <div className="flex min-h-[5.5rem] items-center gap-3 border-b border-[var(--border)] px-5">
      <div
        aria-hidden
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-navy-900 font-serif text-base font-semibold text-gold-400 shadow-[inset_0_1px_1px_oklch(0.8_0.066_85/0.25),inset_0_-1px_1px_oklch(0.05_0.03_265/0.3)] ring-1 ring-gold-500/20 dark:bg-gold-500 dark:text-navy-950 dark:ring-gold-300/25"
      >
        T
      </div>
      <div className="flex flex-col leading-tight">
        <span className="font-serif text-base font-semibold tracking-tight text-[var(--foreground)]">
          {t("title")}
        </span>
        <span className="text-[0.65rem] text-[var(--muted-foreground)]/75">{t("subtitle")}</span>
        <span className="text-[0.7rem] font-medium text-[var(--muted-foreground)]">
          {t("bank")}
        </span>
      </div>
    </div>
  );
}

function SidebarFooter() {
  const t = useTranslations("app");
  return (
    <div className="border-t border-[var(--border)] px-4 py-3">
      <div className="flex items-start gap-1.5">
        <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-500/60" />
        <p className="text-[0.68rem] leading-relaxed text-[var(--muted-foreground)]/70">
          {t("disclaimer")}
        </p>
      </div>
    </div>
  );
}
