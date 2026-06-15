"use client";

import {
  Activity,
  Archive,
  Bot,
  Boxes,
  ChevronRight,
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
import { useEffect, useMemo, useState } from "react";

import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type RouteHref =
  | "/produit"
  | "/produit/mes-demandes"
  | "/produit/documents"
  | "/produit/alertes"
  | "/produit/parametres"
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

interface Leaf {
  href: RouteHref;
  icon: LucideIcon;
  labelKey: string;
  badge?: string;
  badgeTone?: "default" | "danger" | "warning";
  pulse?: boolean;
  /** Render a thin divider above this leaf (purely visual grouping). */
  separatorBefore?: boolean;
}

/** Per-section accent colour, carried by the header bar and active items inside it. */
type Accent = "green" | "amber" | "sky";

const ACCENT: Record<Accent, { bar: string; border: string; icon: string }> = {
  green: {
    bar: "bg-[var(--tessera-green)]",
    border: "border-[var(--tessera-green)]",
    icon: "text-[var(--tessera-green)]",
  },
  amber: { bar: "bg-amber-400", border: "border-amber-400", icon: "text-amber-400" },
  sky: { bar: "bg-sky-400", border: "border-sky-400", icon: "text-sky-400" },
};

interface Branch {
  key: string;
  icon: LucideIcon;
  labelKey: string;
  children: NavNode[];
  /** Always-expanded section header: no toggle, no chevron. */
  pinned?: boolean;
  /** Top-level section accent; inherited by descendants. */
  accent?: Accent;
}

type NavNode = Leaf | Branch;

const isBranch = (n: NavNode): n is Branch => "children" in n;

const TREE: ReadonlyArray<NavNode> = [
  {
    key: "agent",
    icon: Bot,
    labelKey: "super.agent",
    accent: "green",
    children: [
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
  {
    key: "gouverner",
    icon: ShieldHalf,
    labelKey: "super.gouverner",
    pinned: true,
    accent: "amber",
    children: [
      {
        key: "surveiller",
        icon: Activity,
        labelKey: "group.surveiller",
        children: [
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
        key: "agir",
        icon: Workflow,
        labelKey: "group.agir",
        children: [
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
        key: "prouver",
        icon: Archive,
        labelKey: "group.prouver",
        children: [
          { href: "/prouver/audit-logs", icon: ScrollText, labelKey: "item.auditLogs" },
          { href: "/prouver/evidence-store", icon: Archive, labelKey: "item.evidenceStore" },
        ],
      },
    ],
  },
  {
    key: "plateforme",
    icon: Boxes,
    labelKey: "super.plateforme",
    pinned: true,
    accent: "sky",
    children: [
      {
        key: "configurer",
        icon: SlidersHorizontal,
        labelKey: "group.configurer",
        children: [
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
          {
            href: "/configurer/parametres",
            icon: SlidersHorizontal,
            labelKey: "item.parametres",
          },
          { href: "/configurer/integrations", icon: Settings, labelKey: "item.integrations" },
        ],
      },
      {
        key: "admin",
        icon: KeyRound,
        labelKey: "group.admin",
        children: [
          { href: "/admin/utilisateurs", icon: Users, labelKey: "item.utilisateurs" },
          { href: "/admin/roles-acces", icon: KeyRound, labelKey: "item.rolesAcces" },
          { href: "/admin/profil-systeme", icon: UserRound, labelKey: "item.profilSysteme" },
        ],
      },
    ],
  },
];

/** Map each leaf href to the chain of branch keys leading to it. */
const ANCESTORS: Record<string, string[]> = (() => {
  const out: Record<string, string[]> = {};
  const walk = (nodes: ReadonlyArray<NavNode>, trail: string[]) => {
    for (const n of nodes) {
      if (isBranch(n)) walk(n.children, [...trail, n.key]);
      else out[n.href] = trail;
    }
  };
  walk(TREE, []);
  return out;
})();

function activeBranchKeys(pathname: string): string[] {
  for (const [href, trail] of Object.entries(ANCESTORS)) {
    if (pathname === href || pathname.startsWith(`${href}/`)) return trail;
  }
  return [];
}

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  // Everything is collapsed by default; only the branches on the active path are
  // auto-expanded so the current page stays visible. The user expands the rest.
  const activeTrail = useMemo(() => activeBranchKeys(pathname), [pathname]);
  const [open, setOpen] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(activeTrail.map((k) => [k, true])),
  );
  useEffect(() => {
    if (activeTrail.length === 0) return;
    setOpen((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const k of activeTrail)
        if (!next[k]) {
          next[k] = true;
          changed = true;
        }
      return changed ? next : prev;
    });
  }, [activeTrail]);

  const toggle = (key: string) => setOpen((p) => ({ ...p, [key]: !p[key] }));

  return (
    <aside className="flex h-full w-20 shrink-0 flex-col border-r border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] text-[var(--tessera-text)] md:w-[218px]">
      <BrandHeader />
      <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-3 md:px-3">
        <ul className="flex flex-col gap-2">
          {TREE.map((node) => (
            <NavTreeNode
              key={isBranch(node) ? node.key : node.href}
              node={node}
              depth={0}
              pathname={pathname}
              open={open}
              toggle={toggle}
              t={t}
            />
          ))}
        </ul>
      </nav>
      <IdentityBlock />
    </aside>
  );
}

type T = ReturnType<typeof useTranslations<"nav">>;

function NavTreeNode({
  node,
  depth,
  pathname,
  open,
  toggle,
  t,
  accent = "green",
}: {
  node: NavNode;
  depth: number;
  pathname: string;
  open: Record<string, boolean>;
  toggle: (key: string) => void;
  t: T;
  /** Section accent inherited from the enclosing depth-0 branch. */
  accent?: Accent;
}) {
  const pad = { paddingLeft: `${0.5 + depth * 0.75}rem` };

  if (!isBranch(node)) {
    const active = pathname === node.href || pathname.startsWith(`${node.href}/`);
    return (
      <>
        {node.separatorBefore ? (
          <li
            aria-hidden
            className="mx-3 -my-px h-px bg-gradient-to-r from-white/[0.06] via-white/15 to-white/[0.06]"
          />
        ) : null}
        <li>
          <Link
            href={node.href}
            aria-current={active ? "page" : undefined}
            style={pad}
            className={cn(
              "group flex min-h-9 items-center gap-2 rounded-md py-2 pr-2 text-sm font-medium transition-colors",
              active
                ? cn(
                    ACCENT[accent].border,
                    "border-l-2 bg-[var(--tessera-surface-elevated)] text-white",
                  )
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            <node.icon
              className={cn(
                "h-4 w-4 shrink-0 transition-colors",
                active
                  ? ACCENT[accent].icon
                  : "text-[var(--tessera-text-muted)] group-hover:text-[var(--tessera-text)]",
              )}
            />
            <span className="hidden min-w-0 flex-1 truncate md:block">{t(node.labelKey)}</span>
            {node.pulse ? <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> : null}
            {node.badge ? <Badge tone={node.badgeTone} active={active} value={node.badge} /> : null}
          </Link>
        </li>
      </>
    );
  }

  const pinned = node.pinned ?? false;
  const isOpen = pinned ? true : (open[node.key] ?? false);
  const containsActive = activeBranchKeys(pathname).includes(node.key);
  const sectionAccent = node.accent ?? accent;
  const headerClass = cn(
    "group flex min-h-9 w-full items-center gap-2 rounded-md py-2 pr-2 font-medium transition-colors",
    depth === 0
      ? cn("border-l-2 text-[0.7rem] uppercase tracking-[0.1em]", ACCENT[sectionAccent].border)
      : "text-[0.66rem] uppercase tracking-wide",
    containsActive
      ? "text-[var(--tessera-text)]"
      : "text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
  );
  return (
    <li>
      {pinned ? (
        <div style={pad} className={cn(headerClass, "hover:text-[var(--tessera-text-muted)]")}>
          <node.icon className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
          <span className="hidden min-w-0 flex-1 truncate text-left md:block">
            {t(node.labelKey)}
          </span>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => toggle(node.key)}
          aria-expanded={isOpen}
          style={pad}
          className={headerClass}
        >
          <node.icon className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
          <span className="hidden min-w-0 flex-1 truncate text-left md:block">
            {t(node.labelKey)}
          </span>
          <ChevronRight
            className={cn(
              "hidden h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)] transition-transform md:block",
              isOpen ? "rotate-90" : "",
            )}
          />
        </button>
      )}
      {isOpen ? (
        <ul className="mt-0.5 flex flex-col gap-0.5">
          {node.children.map((child) => (
            <NavTreeNode
              key={isBranch(child) ? child.key : child.href}
              node={child}
              depth={depth + 1}
              pathname={pathname}
              open={open}
              toggle={toggle}
              t={t}
              accent={sectionAccent}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Badge({
  tone,
  active,
  value,
}: { tone?: "default" | "danger" | "warning"; active: boolean; value: string }) {
  return (
    <span
      className={cn(
        "hidden rounded-full px-2 py-0.5 text-[0.65rem] font-semibold md:inline-flex",
        tone === "danger"
          ? "bg-red-500 text-white"
          : tone === "warning"
            ? "bg-amber-500 text-white"
            : active
              ? "bg-[var(--tessera-green-soft)] text-[#d6f0e3]"
              : "bg-[var(--tessera-muted)] text-[var(--tessera-text-muted)]",
      )}
    >
      {value}
    </span>
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
    <div className="border-t border-[var(--tessera-border)] px-2 py-3 md:px-3">
      <div className="flex items-center justify-center gap-3 md:justify-start">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-green-muted)] text-sm font-semibold text-[#d6f0e3]">
          AD
        </div>
        <div className="hidden min-w-0 md:block">
          <p className="truncate text-sm font-semibold text-white">{t("person")}</p>
          <p className="truncate text-xs text-[var(--tessera-text-muted)]">
            {t("persona")} · {t("role")}
          </p>
        </div>
      </div>
      <div className="mt-2 hidden gap-0.5 text-xs text-[var(--tessera-text-muted)] md:grid">
        <p className="truncate">{t("scope")}</p>
        <p className="truncate">{t("localeRuntime")}</p>
      </div>
    </div>
  );
}
