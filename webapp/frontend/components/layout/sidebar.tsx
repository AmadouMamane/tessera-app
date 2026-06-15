"use client";

import {
  Archive,
  Boxes,
  ClipboardList,
  Cpu,
  DatabaseZap,
  FileCheck2,
  FileText,
  Gauge,
  GitBranch,
  Home,
  Inbox,
  KeyRound,
  LayoutDashboard,
  ListTodo,
  LockKeyhole,
  type LucideIcon,
  MemoryStick,
  PlayCircle,
  Plug,
  ScrollText,
  Settings,
  ShieldCheck,
  ShieldHalf,
  SlidersHorizontal,
  Sparkles,
  Terminal,
  UserRound,
  Users,
  Workflow,
  Wrench,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type RouteHref =
  // AGENT (flat)
  | "/agent/synthese"
  | "/agent/configurations"
  | "/agent/connaissances"
  | "/agent/garde-fous"
  | "/agent/prompts"
  | "/agent/evaluations"
  | "/agent/console"
  | "/agent/historique"
  | "/agent/a-traiter"
  | "/agent/a-faire"
  // GOUVERNER
  | "/surveiller/vue-ensemble"
  | "/surveiller/qualite-ia"
  | "/surveiller/securite-privacy"
  | "/surveiller/conformite"
  | "/surveiller/fiabilite-cout"
  | "/surveiller/observabilite"
  | "/surveiller/amelioration"
  | "/agir/incidents-playbooks"
  | "/agir/replay-shadow"
  | "/agir/curation-eval-set"
  | "/agir/release-control"
  | "/agir/automations"
  | "/prouver/audit-logs"
  | "/prouver/evidence-store"
  // PLATEFORME
  | "/configurer/signal-catalog"
  | "/configurer/garde-fous"
  | "/configurer/modeles"
  | "/configurer/connecteurs"
  | "/configurer/politiques"
  | "/configurer/sources-memoire"
  | "/configurer/parametres"
  | "/configurer/integrations"
  | "/admin/utilisateurs"
  | "/admin/roles-acces"
  | "/admin/profil-systeme";

interface NavItem {
  href: RouteHref;
  icon: LucideIcon;
  labelKey: string;
  badge?: string;
  badgeTone?: "default" | "danger" | "warning";
  pulse?: boolean;
  /** Render a thin separator above this item (AGENT queue split). */
  separatorBefore?: boolean;
}

interface NavGroup {
  /** Group sub-label; omitted for the flat AGENT group. */
  labelKey?: string;
  items: NavItem[];
}

interface SuperGroup {
  labelKey: string;
  groups: NavGroup[];
}

const SUPER_GROUPS: ReadonlyArray<SuperGroup> = [
  {
    labelKey: "super.agent",
    groups: [
      {
        items: [
          { href: "/agent/synthese", icon: LayoutDashboard, labelKey: "item.synthese" },
          {
            href: "/agent/configurations",
            icon: SlidersHorizontal,
            labelKey: "item.configurations",
          },
          { href: "/agent/connaissances", icon: MemoryStick, labelKey: "item.connaissances" },
          { href: "/agent/garde-fous", icon: ShieldCheck, labelKey: "item.agentGuardrails" },
          { href: "/agent/prompts", icon: FileText, labelKey: "item.prompts" },
          { href: "/agent/evaluations", icon: ClipboardList, labelKey: "item.evaluations" },
          { href: "/agent/console", icon: Terminal, labelKey: "item.console" },
          { href: "/agent/historique", icon: ScrollText, labelKey: "item.historique" },
          {
            href: "/agent/a-traiter",
            icon: Inbox,
            labelKey: "item.aTraiter",
            badge: "24",
            badgeTone: "danger",
            separatorBefore: true,
          },
          { href: "/agent/a-faire", icon: ListTodo, labelKey: "item.aFaire", badge: "8" },
        ],
      },
    ],
  },
  {
    labelKey: "super.gouverner",
    groups: [
      {
        labelKey: "group.surveiller",
        items: [
          { href: "/surveiller/vue-ensemble", icon: Home, labelKey: "item.vueEnsemble" },
          {
            href: "/surveiller/qualite-ia",
            icon: ShieldHalf,
            labelKey: "item.qualiteIa",
            badge: "52",
          },
          {
            href: "/surveiller/securite-privacy",
            icon: LockKeyhole,
            labelKey: "item.securitePrivacy",
            pulse: true,
          },
          {
            href: "/surveiller/conformite",
            icon: FileCheck2,
            labelKey: "item.conformite",
            pulse: true,
          },
          {
            href: "/surveiller/fiabilite-cout",
            icon: Gauge,
            labelKey: "item.fiabiliteCout",
            pulse: true,
          },
          { href: "/surveiller/observabilite", icon: Boxes, labelKey: "item.observabilite" },
          { href: "/surveiller/amelioration", icon: Sparkles, labelKey: "item.amelioration" },
        ],
      },
      {
        labelKey: "group.agir",
        items: [
          {
            href: "/agir/incidents-playbooks",
            icon: Wrench,
            labelKey: "item.incidentsPlaybooks",
            badge: "11",
            badgeTone: "danger",
          },
          { href: "/agir/replay-shadow", icon: PlayCircle, labelKey: "item.replayShadow" },
          {
            href: "/agir/curation-eval-set",
            icon: DatabaseZap,
            labelKey: "item.curationEvalSet",
            badge: "6",
            badgeTone: "warning",
          },
          { href: "/agir/release-control", icon: GitBranch, labelKey: "item.releaseControl" },
          { href: "/agir/automations", icon: Workflow, labelKey: "item.automations" },
        ],
      },
      {
        labelKey: "group.prouver",
        items: [
          { href: "/prouver/audit-logs", icon: ScrollText, labelKey: "item.auditLogs" },
          { href: "/prouver/evidence-store", icon: Archive, labelKey: "item.evidenceStore" },
        ],
      },
    ],
  },
  {
    labelKey: "super.plateforme",
    groups: [
      {
        labelKey: "group.configurer",
        items: [
          {
            href: "/configurer/signal-catalog",
            icon: Boxes,
            labelKey: "item.signalCatalog",
            badge: "200",
          },
          {
            href: "/configurer/garde-fous",
            icon: ShieldCheck,
            labelKey: "item.platformGuardrails",
          },
          { href: "/configurer/modeles", icon: Cpu, labelKey: "item.modeles" },
          { href: "/configurer/connecteurs", icon: Plug, labelKey: "item.connecteurs" },
          { href: "/configurer/politiques", icon: ShieldCheck, labelKey: "item.politiques" },
          {
            href: "/configurer/sources-memoire",
            icon: MemoryStick,
            labelKey: "item.sourcesMemoire",
          },
          { href: "/configurer/parametres", icon: SlidersHorizontal, labelKey: "item.parametres" },
          { href: "/configurer/integrations", icon: Settings, labelKey: "item.integrations" },
        ],
      },
      {
        labelKey: "group.admin",
        items: [
          { href: "/admin/utilisateurs", icon: Users, labelKey: "item.utilisateurs" },
          { href: "/admin/roles-acces", icon: KeyRound, labelKey: "item.rolesAcces" },
          { href: "/admin/profil-systeme", icon: UserRound, labelKey: "item.profilSysteme" },
        ],
      },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  return (
    <aside className="flex h-full w-20 shrink-0 flex-col border-r border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] text-[var(--tessera-text)] md:w-[218px]">
      <BrandHeader />
      <AppToggle />
      <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-3 md:px-3">
        <div className="flex flex-col gap-4">
          {SUPER_GROUPS.map((sg) => (
            <section key={sg.labelKey}>
              <p className="mb-1.5 hidden px-2 text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-[var(--tessera-text)] md:block">
                {t(sg.labelKey)}
              </p>
              <div className="flex flex-col gap-2.5">
                {sg.groups.map((group, gi) => (
                  <div key={group.labelKey ?? `flat-${gi}`}>
                    {group.labelKey ? (
                      <p className="mb-1 hidden px-2 text-[0.6rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)] md:block">
                        {t(group.labelKey)}
                      </p>
                    ) : null}
                    <ul className="flex flex-col gap-1 md:gap-0.5">
                      {group.items.map((item) => (
                        <li key={item.href}>
                          {item.separatorBefore ? (
                            <div className="my-1.5 mx-2 border-t border-[var(--tessera-border)]" />
                          ) : null}
                          <NavEntry
                            item={item}
                            active={isActive(pathname, item.href)}
                            label={t(item.labelKey)}
                          />
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      </nav>
      <IdentityBlock />
    </aside>
  );
}

function AppToggle() {
  const t = useTranslations("nav.toggle");
  return (
    <div className="hidden px-3 py-2 md:block">
      <div className="flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-0.5">
        <span className="flex-1 rounded bg-[var(--tessera-surface-elevated)] px-2 py-1 text-center text-[0.7rem] font-semibold text-white">
          {t("cockpit")}
        </span>
        <Link
          href="/produit"
          className="flex-1 rounded px-2 py-1 text-center text-[0.7rem] font-medium text-[var(--tessera-text-muted)] transition-colors hover:text-[var(--tessera-text)]"
        >
          {t("produit")}
        </Link>
      </div>
    </div>
  );
}

function NavEntry({ item, active, label }: { item: NavItem; active: boolean; label: string }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      aria-label={label}
      className={cn(
        "group flex min-h-9 items-center justify-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors md:justify-start md:px-3",
        active
          ? "border-l-2 border-[var(--tessera-green)] bg-[var(--tessera-surface-elevated)] pl-[6px] text-white md:pl-[10px]"
          : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
      )}
    >
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
              : item.badgeTone === "warning"
                ? "bg-amber-500 text-white"
                : active
                  ? "bg-[var(--tessera-green-soft)] text-[#d6f0e3]"
                  : "bg-[var(--tessera-muted)] text-[var(--tessera-text-muted)]",
          )}
        >
          {item.badge}
        </span>
      ) : null}
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

function isActive(pathname: string, href: RouteHref): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
