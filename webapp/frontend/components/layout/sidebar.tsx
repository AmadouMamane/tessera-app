"use client";

import {
  Archive,
  Bot,
  Boxes,
  ClipboardList,
  DatabaseZap,
  FileCheck2,
  FileSearch,
  Gauge,
  GitBranch,
  Home,
  KeyRound,
  LockKeyhole,
  MemoryStick,
  PlayCircle,
  ScrollText,
  Settings,
  ShieldCheck,
  ShieldHalf,
  Sparkles,
  UserRound,
  Workflow,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type RouteHref =
  | "/"
  | "/chat"
  | "/audit"
  | "/incidents"
  | "/replay"
  | "/eval"
  | "/observability"
  | "/security"
  | "/compliance"
  | "/reliability"
  | "/improvement"
  | "/health"
  | "/settings";

interface NavItem {
  href?: RouteHref;
  icon: LucideIcon;
  labelKey: string;
  badge?: string;
  badgeTone?: "default" | "danger";
  pulse?: boolean;
}

interface NavGroup {
  labelKey: string;
  items: NavItem[];
}

const NAV_GROUPS: ReadonlyArray<NavGroup> = [
  {
    labelKey: "groups.product",
    items: [
      { href: "/chat", icon: Bot, labelKey: "assistant" },
      { icon: ClipboardList, labelKey: "inbox", badge: "24", badgeTone: "danger" },
    ],
  },
  {
    labelKey: "groups.cockpit",
    items: [
      { href: "/", icon: Home, labelKey: "overview" },
      { href: "/observability", icon: ShieldHalf, labelKey: "quality", badge: "52" },
      { href: "/security", icon: LockKeyhole, labelKey: "security", pulse: true },
      { href: "/compliance", icon: FileCheck2, labelKey: "compliance", pulse: true },
      { href: "/reliability", icon: Gauge, labelKey: "reliability", pulse: true },
      { href: "/improvement", icon: Sparkles, labelKey: "improvement" },
    ],
  },
  {
    labelKey: "groups.act",
    items: [
      { href: "/incidents", icon: Wrench, labelKey: "incidents", badge: "11" },
      { href: "/replay", icon: PlayCircle, labelKey: "replay" },
      { icon: DatabaseZap, labelKey: "curation" },
      { icon: GitBranch, labelKey: "release" },
      { icon: Workflow, labelKey: "automations" },
    ],
  },
  {
    labelKey: "groups.prove",
    items: [
      { href: "/audit", icon: ScrollText, labelKey: "audit" },
      { icon: Archive, labelKey: "proofExporters" },
      { icon: FileSearch, labelKey: "evidencePack" },
    ],
  },
  {
    labelKey: "groups.configure",
    items: [
      { icon: Boxes, labelKey: "signalCatalog", badge: "200" },
      { icon: ShieldCheck, labelKey: "policies" },
      { icon: MemoryStick, labelKey: "sourcesMemory" },
      { icon: KeyRound, labelKey: "rolesAccess" },
      { icon: Settings, labelKey: "integrations" },
      { href: "/settings", icon: UserRound, labelKey: "systemProfile" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  return (
    <aside className="flex h-full w-20 shrink-0 flex-col border-r border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] text-[var(--tessera-text)] md:w-[218px]">
      <BrandHeader />
      <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-4 md:px-3">
        <div className="flex flex-col gap-4">
          {NAV_GROUPS.map((group) => (
            <section key={group.labelKey}>
              <p className="mb-1.5 hidden px-2 text-[0.65rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)] md:block">
                {t(group.labelKey)}
              </p>
              <ul className="flex flex-col gap-1 md:gap-0.5">
                {group.items.map((item) => (
                  <li key={item.labelKey}>
                    <NavEntry
                      item={item}
                      active={isActive(pathname, item.href)}
                      label={t(item.labelKey)}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </nav>
      <IdentityBlock />
    </aside>
  );
}

function NavEntry({ item, active, label }: { item: NavItem; active: boolean; label: string }) {
  const Icon = item.icon;
  const content = (
    <>
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 transition-colors",
          active
            ? "text-[var(--tessera-green)]"
            : "text-[var(--tessera-text-muted)] group-hover:text-[var(--tessera-text)]",
        )}
      />
      <span className="hidden min-w-0 flex-1 truncate md:block">{label}</span>
      {item.pulse ? <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> : null}
      {item.badge ? (
        <span
          className={cn(
            "hidden rounded-full px-2 py-0.5 text-[0.65rem] font-semibold md:inline-flex",
            item.badgeTone === "danger"
              ? "bg-red-500 text-white"
              : active
                ? "bg-[var(--tessera-green-soft)] text-[#d6f0e3]"
                : "bg-[var(--tessera-muted)] text-[var(--tessera-text-muted)]",
          )}
        >
          {item.badge}
        </span>
      ) : null}
    </>
  );

  const className = cn(
    "group flex min-h-9 items-center justify-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors md:justify-start md:px-3",
    active
      ? "border-l-2 border-[var(--tessera-green)] bg-[var(--tessera-surface-elevated)] pl-[6px] text-white md:pl-[10px]"
      : item.href
        ? "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
        : "cursor-not-allowed text-[var(--tessera-text-subtle)]",
  );

  if (!item.href) {
    return (
      <span className={className} aria-disabled="true" aria-label={label}>
        {content}
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      className={className}
      aria-current={active ? "page" : undefined}
      aria-label={label}
    >
      {content}
    </Link>
  );
}

function BrandHeader() {
  const t = useTranslations("app");
  return (
    <div className="flex min-h-[5.5rem] items-center justify-center gap-3 border-b border-[var(--tessera-border)] px-3 md:justify-start md:px-5">
      <TesseraMark />
      <div className="hidden min-w-0 flex-col leading-tight md:flex">
        <span className="font-sans text-xl font-semibold tracking-normal text-white">
          {t("title")}
        </span>
        <span className="truncate text-xs text-[var(--tessera-text-muted)]">{t("subtitle")}</span>
      </div>
    </div>
  );
}

function TesseraMark() {
  return (
    <svg
      aria-hidden="true"
      className="h-9 w-9 shrink-0 text-[var(--tessera-green)]"
      viewBox="0 0 36 36"
      fill="none"
    >
      <path
        d="M18 3.5 31 10.75v14.5L18 32.5 5 25.25v-14.5L18 3.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M18 3.5v14.7m0 14.3V18.2m0 0L5 10.75m13 7.45 13-7.45M5 25.25l13-7.05 13 7.05"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}

function IdentityBlock() {
  const t = useTranslations("nav.identity");
  return (
    <div className="border-t border-[var(--tessera-border)] p-2 md:p-3">
      <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2 md:p-3">
        <div className="flex items-center justify-center gap-3 md:justify-start">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--tessera-green-muted)] text-sm font-semibold text-[#d6f0e3]">
            AD
          </div>
          <div className="hidden min-w-0 md:block">
            <p className="truncate text-sm font-semibold text-white">{t("person")}</p>
            <p className="truncate text-xs text-[var(--tessera-text-muted)]">{t("persona")}</p>
          </div>
        </div>
        <div className="mt-3 hidden gap-1 text-xs text-[var(--tessera-text-muted)] md:grid">
          <p>{t("role")}</p>
          <p>{t("scope")}</p>
          <p>{t("localeRuntime")}</p>
        </div>
      </div>
    </div>
  );
}

function isActive(pathname: string, href?: RouteHref): boolean {
  if (!href) return false;
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
