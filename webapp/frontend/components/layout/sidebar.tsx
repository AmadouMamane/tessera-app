"use client";

import {
  Activity,
  Archive,
  Bot,
  Boxes,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Cpu,
  DatabaseZap,
  FileCheck2,
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
  UserRound,
  Users,
  Workflow,
  Wrench,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo, TesseraMark } from "@/components/brand/tessera-logo";
import { Link, usePathname } from "@/i18n/navigation";
import { type ChromeBadgeKey, type ChromeTone, useChromeBadge } from "@/lib/chrome";
import { cn } from "@/lib/cn";
import { useShellChrome } from "./shell-chrome";

type RouteHref =
  | "/produit"
  // AGENTS super-section lists SECTIONS, not per-agent pages: the fleet hub plus
  // the global operator queue. Per-agent pages (Synthèse…Historique) live ONLY in
  // the command-bar (AgentTabs), scoped to /agents/:id — never duplicated here.
  | "/agents"
  | "/a-traiter"
  | "/a-faire"
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
  | "/prouver/etat-a-date"
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
  /**
   * Which chrome fact this leaf badges, if any. NOT a number: the count and its tone come
   * from `/observability/chrome`, computed by the same read the destination page performs.
   * There is no way to type a literal here, which is the point — see
   * `sidebar.test.ts::no numeric literal may reach a badge`.
   */
  badgeKey?: ChromeBadgeKey;
  pulse?: boolean;
  /** Render a thin divider above this leaf (purely visual grouping). */
  separatorBefore?: boolean;
}

/** Per-section accent colour for the super-section header bar. */
type Accent = "green" | "amber" | "sky";

const ACCENT: Record<Accent, string> = {
  green: "border-[var(--tessera-green)]/70",
  amber: "border-amber-400/70",
  sky: "border-sky-400/70",
};

interface Branch {
  key: string;
  icon: LucideIcon;
  labelKey: string;
  children: NavNode[];
  /** Always-expanded super-section header: no toggle, no chevron. */
  pinned?: boolean;
  /** Super-section accent colour (depth-0 header bar). */
  accent?: Accent;
}

type NavNode = Leaf | Branch;

const isBranch = (n: NavNode): n is Branch => "children" in n;

// The AGENTS super-section lists SECTIONS, not per-agent pages: the fleet hub
// (Flotte → /agents) and the GLOBAL cross-agent operator queue (À traiter /
// À faire). Per-agent pages live only in the command-bar (AgentTabs), so this
// section is fully static — independent of the selected agent.
const AGENTS_SECTION: Branch = {
  key: "agents",
  icon: Bot,
  labelKey: "super.agents",
  pinned: true,
  accent: "green",
  children: [
    { href: "/agents", icon: LayoutDashboard, labelKey: "item.flotte" },
    {
      href: "/a-traiter",
      icon: Inbox,
      labelKey: "item.aTraiter",
      badgeKey: "a_traiter",
      separatorBefore: true,
    },
    { href: "/a-faire", icon: ListTodo, labelKey: "item.aFaire", badgeKey: "a_faire" },
  ],
};

const TREE: ReadonlyArray<NavNode> = [
  AGENTS_SECTION,
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
            // No badge: the Qualité IA page counts no outstanding things. The 52 that used
            // to sit here was not stale or rounded — it was a decoration.
            labelKey: "item.qualiteIa",
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
            badgeKey: "incidents",
          },
          { href: "/agir/replay-shadow", icon: PlayCircle, labelKey: "item.replayShadow" },
          {
            href: "/agir/curation-eval-set",
            icon: DatabaseZap,
            labelKey: "item.curationEvalSet",
            badgeKey: "curation",
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
          { href: "/prouver/etat-a-date", icon: CalendarClock, labelKey: "item.etatADate" },
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
            badgeKey: "signal_catalog",
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

/** Whether a leaf is the active page. "Flotte" (/agents) matches EXACTLY so it
 *  never lights up inside an agent workspace (/agents/:id/...) — there the active
 *  tab lives in the command-bar (AgentTabs), and no sidebar item is active. */
function leafActive(href: string, pathname: string): boolean {
  if (href === "/agents") return pathname === "/agents";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** A flat, navigable view of the real route map — reused by the command palette
 *  so it navigates to the SAME pages the sidebar exposes (no parallel list). */
export interface NavLeafRef {
  href: string;
  labelKey: string;
  icon: LucideIcon;
}

export function navLeaves(): NavLeafRef[] {
  const out: NavLeafRef[] = [];
  const walk = (nodes: ReadonlyArray<NavNode>) => {
    for (const node of nodes) {
      if (isBranch(node)) walk(node.children);
      else out.push({ href: node.href, labelKey: node.labelKey, icon: node.icon });
    }
  };
  walk(TREE);
  return out;
}

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  // The nav tree is fully static now: the sidebar lists SECTIONS, the command-bar
  // (AgentTabs) handles per-agent pages.
  const tree = TREE;

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
  const { collapsed, toggleCollapsed } = useShellChrome();

  if (collapsed) {
    // Reduced to an icon rail — the brand mark + nav logos stay visible (never a
    // blank gutter); the edge handle expands it back. ⌘B is the keyboard twin.
    return (
      <aside className="group/sidebar relative flex h-full w-16 shrink-0 flex-col border-r border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] text-[var(--tessera-text)]">
        <BrandHeader collapsed />
        <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
          <ul className="flex flex-col gap-1">
            {tree.map((node) => (
              <RailNode
                key={isBranch(node) ? node.key : node.href}
                node={node}
                pathname={pathname}
                t={t}
              />
            ))}
          </ul>
        </nav>
        <EdgeCollapseHandle collapsed onToggle={toggleCollapsed} label={t("rail.expand")} />
      </aside>
    );
  }

  return (
    <aside className="group/sidebar relative flex h-full w-20 shrink-0 flex-col border-r border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] text-[var(--tessera-text)] md:w-[252px]">
      <BrandHeader />
      <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-3 md:px-3">
        <ul className="flex flex-col gap-2">
          {tree.map((node) => (
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
      <EdgeCollapseHandle onToggle={toggleCollapsed} label={t("rail.collapse")} />
    </aside>
  );
}

/** Discreet handle straddling the sidebar's right border, collapsing the panel to
 *  the icon rail and back. ⌘B (shell-chrome) is the keyboard equivalent. On the
 *  full sidebar it stays hidden until hover; on the narrow rail it rests faintly
 *  visible so the way back out is never lost. */
function EdgeCollapseHandle({
  collapsed = false,
  onToggle,
  label,
}: {
  collapsed?: boolean;
  onToggle: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={`${label} (⌘B)`}
      className={cn(
        "absolute top-1/2 -right-3 z-20 flex h-12 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-surface)] text-[var(--tessera-text-muted)] shadow-sm transition-all hover:text-[var(--tessera-text)] focus-visible:opacity-100 group-hover/sidebar:opacity-100 motion-reduce:transition-none",
        collapsed ? "opacity-60" : "opacity-0",
      )}
    >
      {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
    </button>
  );
}

/** A flattened, icon-only rail entry (collapsed sidebar). Branches render their
 *  own icon as a non-interactive section marker; leaves are reachable icon links
 *  with a native tooltip — nav is never lost in the rail. */
function RailNode({
  node,
  pathname,
  t,
}: {
  node: NavNode;
  pathname: string;
  t: T;
}) {
  // Hooks precede the branch early-return: a leaf and a branch must run the same ones.
  const badge = useChromeBadge(isBranch(node) ? undefined : node.badgeKey);
  if (isBranch(node)) {
    return (
      <>
        <li
          aria-hidden
          className="mx-2 mt-2 mb-1 flex items-center justify-center border-[var(--tessera-border)] border-t pt-2"
          title={t(node.labelKey)}
        >
          <node.icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]/70" />
        </li>
        {node.children.map((child) => (
          <RailNode
            key={isBranch(child) ? child.key : child.href}
            node={child}
            pathname={pathname}
            t={t}
          />
        ))}
      </>
    );
  }
  const active = leafActive(node.href, pathname);
  const label = t(node.labelKey);
  return (
    <li>
      <Link
        href={node.href}
        aria-current={active ? "page" : undefined}
        aria-label={label}
        title={label}
        className={cn(
          "group relative flex h-10 items-center justify-center rounded-md transition-colors motion-reduce:transition-none",
          active
            ? "bg-[var(--tessera-surface-elevated)] text-[var(--tessera-text)]"
            : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
        )}
      >
        <node.icon className="h-4.5 w-4.5 shrink-0" />
        {node.pulse ? (
          <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-emerald-400" />
        ) : null}
        {badge ? (
          <span className="absolute top-1 right-1 inline-flex min-w-3.5 items-center justify-center rounded-full bg-[var(--tessera-danger,#b4453a)] px-1 text-[0.55rem] font-semibold text-white">
            {badge.count}
          </span>
        ) : null}
      </Link>
    </li>
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
}: {
  node: NavNode;
  depth: number;
  pathname: string;
  open: Record<string, boolean>;
  toggle: (key: string) => void;
  t: T;
}) {
  const pad = { paddingLeft: `${0.5 + depth * 0.75}rem` };
  const badge = useChromeBadge(isBranch(node) ? undefined : node.badgeKey);

  if (!isBranch(node)) {
    const active = leafActive(node.href, pathname);
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
                ? "bg-[var(--tessera-surface-elevated)] text-[var(--tessera-text)]"
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            <node.icon
              className={cn(
                "h-4 w-4 shrink-0 transition-colors",
                active
                  ? "text-white"
                  : "text-[var(--tessera-text-muted)] group-hover:text-[var(--tessera-text)]",
              )}
            />
            <span className="hidden min-w-0 flex-1 truncate md:block">{t(node.labelKey)}</span>
            {node.pulse ? <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> : null}
            {badge ? <Badge tone={badge.tone} active={active} value={badge.count} /> : null}
          </Link>
        </li>
      </>
    );
  }

  const pinned = node.pinned ?? false;
  const isOpen = pinned ? true : (open[node.key] ?? false);
  const containsActive = activeBranchKeys(pathname).includes(node.key);
  const isSuper = depth === 0;
  const headerClass = cn(
    "group flex min-h-9 w-full items-center gap-2 rounded-md py-2 pr-2 font-medium transition-colors",
    isSuper
      ? cn(
          "border-l-2 text-[0.7rem] uppercase tracking-[0.1em] text-white",
          ACCENT[node.accent ?? "green"],
        )
      : cn(
          "text-[0.66rem] uppercase tracking-wide",
          containsActive
            ? "text-[var(--tessera-text)]"
            : "text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
        ),
  );
  return (
    <li>
      {pinned ? (
        <div style={pad} className={headerClass}>
          <span className="ml-1.5 hidden min-w-0 flex-1 truncate text-left md:block">
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
          {isSuper ? null : (
            <node.icon className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
          )}
          <span
            className={cn("hidden min-w-0 flex-1 truncate text-left md:block", isSuper && "ml-1.5")}
          >
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
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Badge({ tone, active, value }: { tone: ChromeTone; active: boolean; value: number }) {
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

// The brand block is the left half of the cockpit's top rule: its height and its bottom
// border must match row 1 of `AppHeader` exactly, or the line breaks at the rail's edge.
// 5.5rem = 88px, and `h-11` is the logo size the launcher (`BrandLead`) uses — the two
// surfaces show the same mark at the same size. `2735f9ad` cut this block to 56px and the
// logo to `h-8` when it shrank the header; both are restored here.
function BrandHeader({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div
      className={cn(
        "flex min-h-[5.5rem] items-center gap-3 border-b border-[var(--tessera-border)]",
        collapsed ? "justify-center px-2" : "justify-center px-3 md:justify-start md:px-5",
      )}
    >
      {collapsed ? <TesseraMark /> : <TesseraLogo className="h-11" />}
    </div>
  );
}

// The single identity home (Linear/Notion pattern): the cockpit account lives ONCE
// here, at the bottom of the sidebar — the header no longer repeats it. Real
// session control (role label + sign-out), not a static persona.
function IdentityBlock() {
  return (
    <div className="border-t border-[var(--tessera-border)] px-2 py-2.5 md:px-3">
      <AuthControl context="gated" />
    </div>
  );
}
