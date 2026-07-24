import { safeLoginReturnTo } from "@/lib/auth/return-to";

export const GLOBAL_HELP_HREF = "/comprendre";
export const OVERVIEW_HREF = "/surveiller/vue-ensemble";
const CONTEXTUAL_HELP_COACHMARK_VERSION = "2026-07";

export type ContextualHelpSection =
  | "agents"
  | "agent"
  | "monitor"
  | "act"
  | "prove"
  | "configure"
  | "admin";

export interface ContextualHelpGuide {
  key: string;
  section: ContextualHelpSection;
  sourceHref: string;
  guideHref: string;
  defaultReturnHref: string;
}

interface StaticContextualHelpGuide {
  key: string;
  section: ContextualHelpSection;
  sourceHref: string;
  guideHref: string;
}

/**
 * One declared mapping per delivered cockpit guide.
 *
 * Redirects and business experiences outside the cockpit are deliberately absent.
 * Agent workspaces are resolved separately because their real route carries an agent id.
 */
export const STATIC_CONTEXTUAL_HELP_GUIDES = [
  {
    key: "fleet",
    section: "agents",
    sourceHref: "/agents",
    guideHref: "/comprendre/agents",
  },
  {
    key: "inbox",
    section: "agents",
    sourceHref: "/a-traiter",
    guideHref: "/comprendre/a-traiter",
  },
  {
    key: "todo",
    section: "agents",
    sourceHref: "/a-faire",
    guideHref: "/comprendre/a-faire",
  },
  {
    key: "overview",
    section: "monitor",
    sourceHref: OVERVIEW_HREF,
    guideHref: "/comprendre/surveiller/vue-ensemble",
  },
  {
    key: "quality",
    section: "monitor",
    sourceHref: "/surveiller/qualite-ia",
    guideHref: "/comprendre/surveiller/qualite-ia",
  },
  {
    key: "security",
    section: "monitor",
    sourceHref: "/surveiller/securite-privacy",
    guideHref: "/comprendre/surveiller/securite-privacy",
  },
  {
    key: "compliance",
    section: "monitor",
    sourceHref: "/surveiller/conformite",
    guideHref: "/comprendre/surveiller/conformite",
  },
  {
    key: "reliability",
    section: "monitor",
    sourceHref: "/surveiller/fiabilite-cout",
    guideHref: "/comprendre/surveiller/fiabilite-cout",
  },
  {
    key: "observability",
    section: "monitor",
    sourceHref: "/surveiller/observabilite",
    guideHref: "/comprendre/surveiller/observabilite",
  },
  {
    key: "improvement",
    section: "monitor",
    sourceHref: "/surveiller/amelioration",
    guideHref: "/comprendre/surveiller/amelioration",
  },
  {
    key: "incidents",
    section: "act",
    sourceHref: "/agir/incidents-playbooks",
    guideHref: "/comprendre/agir/incidents-playbooks",
  },
  {
    key: "replay",
    section: "act",
    sourceHref: "/agir/replay-shadow",
    guideHref: "/comprendre/agir/replay-shadow",
  },
  {
    key: "curation",
    section: "act",
    sourceHref: "/agir/curation-eval-set",
    guideHref: "/comprendre/agir/curation-eval-set",
  },
  {
    key: "release",
    section: "act",
    sourceHref: "/agir/release-control",
    guideHref: "/comprendre/agir/release-control",
  },
  {
    key: "automations",
    section: "act",
    sourceHref: "/agir/automations",
    guideHref: "/comprendre/agir/automations",
  },
  {
    key: "audit",
    section: "prove",
    sourceHref: "/prouver/audit-logs",
    guideHref: "/comprendre/prouver/audit-logs",
  },
  {
    key: "evidence",
    section: "prove",
    sourceHref: "/prouver/evidence-store",
    guideHref: "/comprendre/prouver/evidence-store",
  },
  {
    key: "asof",
    section: "prove",
    sourceHref: "/prouver/etat-a-date",
    guideHref: "/comprendre/prouver/etat-a-date",
  },
  {
    key: "signals",
    section: "configure",
    sourceHref: "/configurer/signal-catalog",
    guideHref: "/comprendre/configurer/signal-catalog",
  },
  {
    key: "platformGuardrails",
    section: "configure",
    sourceHref: "/configurer/garde-fous",
    guideHref: "/comprendre/configurer/garde-fous",
  },
  {
    key: "models",
    section: "configure",
    sourceHref: "/configurer/modeles",
    guideHref: "/comprendre/configurer/modeles",
  },
  {
    key: "connectors",
    section: "configure",
    sourceHref: "/configurer/connecteurs",
    guideHref: "/comprendre/configurer/connecteurs",
  },
  {
    key: "policies",
    section: "configure",
    sourceHref: "/configurer/politiques",
    guideHref: "/comprendre/configurer/politiques",
  },
  {
    key: "sources",
    section: "configure",
    sourceHref: "/configurer/sources-memoire",
    guideHref: "/comprendre/configurer/sources-memoire",
  },
  {
    key: "parameters",
    section: "configure",
    sourceHref: "/configurer/parametres",
    guideHref: "/comprendre/configurer/parametres",
  },
  {
    key: "integrations",
    section: "configure",
    sourceHref: "/configurer/integrations",
    guideHref: "/comprendre/configurer/integrations",
  },
  {
    key: "users",
    section: "admin",
    sourceHref: "/admin/utilisateurs",
    guideHref: "/comprendre/admin/utilisateurs",
  },
  {
    key: "roles",
    section: "admin",
    sourceHref: "/admin/roles-acces",
    guideHref: "/comprendre/admin/roles-acces",
  },
  {
    key: "systemProfile",
    section: "admin",
    sourceHref: "/admin/profil-systeme",
    guideHref: "/comprendre/admin/profil-systeme",
  },
  {
    key: "settings",
    section: "configure",
    sourceHref: "/settings",
    guideHref: "/comprendre/settings",
  },
] as const satisfies readonly StaticContextualHelpGuide[];

export const AGENT_CONTEXTUAL_HELP_GUIDES = [
  { key: "agentSummary", page: "synthese" },
  { key: "agentConfigurations", page: "configurations" },
  { key: "agentKnowledge", page: "connaissances" },
  { key: "agentGuardrails", page: "garde-fous" },
  { key: "agentPrompts", page: "prompts" },
  { key: "agentBusiness", page: "metier" },
  { key: "agentEvaluations", page: "evaluations" },
  { key: "agentConsole", page: "console" },
  { key: "agentHistory", page: "historique" },
] as const;

export const CONTEXTUAL_HELP_ROUTES: Readonly<Record<string, string>> = Object.fromEntries(
  STATIC_CONTEXTUAL_HELP_GUIDES.map((guide) => [guide.sourceHref, guide.guideHref]),
);

const STATIC_BY_SOURCE = new Map<string, StaticContextualHelpGuide>(
  STATIC_CONTEXTUAL_HELP_GUIDES.map((guide) => [guide.sourceHref, guide]),
);
const STATIC_BY_GUIDE = new Map<string, StaticContextualHelpGuide>(
  STATIC_CONTEXTUAL_HELP_GUIDES.map((guide) => [guide.guideHref, guide]),
);
const AGENT_BY_PAGE = new Map(AGENT_CONTEXTUAL_HELP_GUIDES.map((guide) => [guide.page, guide]));
const AGENT_BY_GUIDE = new Map(
  AGENT_CONTEXTUAL_HELP_GUIDES.map((guide) => [`/comprendre/agents/${guide.page}`, guide]),
);

function resolvedStaticGuide(guide: StaticContextualHelpGuide): ContextualHelpGuide {
  return { ...guide, defaultReturnHref: guide.sourceHref };
}

/** Resolve a real cockpit pathname to its declared guide. */
export function contextualHelpGuideForPath(pathname: string): ContextualHelpGuide | null {
  const exact = STATIC_BY_SOURCE.get(pathname);
  if (exact) return resolvedStaticGuide(exact);

  const match = pathname.match(/^\/agents\/([^/]+)\/([^/]+)(?:\/([^/]+))?$/);
  if (!match) return null;
  const [, agentId, page, detail] = match;
  const template = AGENT_BY_PAGE.get(page as (typeof AGENT_CONTEXTUAL_HELP_GUIDES)[number]["page"]);
  if (!template || (detail && page !== "historique")) return null;

  const sourceHref = `/agents/${agentId}/${page}`;
  return {
    key: template.key,
    section: "agent",
    sourceHref,
    guideHref: `/comprendre/agents/${page}`,
    defaultReturnHref: sourceHref,
  };
}

/** Resolve a guide route rendered by the generic catch-all page. */
export function contextualHelpGuideForHref(guideHref: string): ContextualHelpGuide | null {
  const exact = STATIC_BY_GUIDE.get(guideHref);
  if (exact) return resolvedStaticGuide(exact);

  const agent = AGENT_BY_GUIDE.get(guideHref);
  if (!agent) return null;
  return {
    key: agent.key,
    section: "agent",
    sourceHref: `/agents/:agentId/${agent.page}`,
    guideHref,
    defaultReturnHref: "/agents",
  };
}

export function hasContextualHelp(pathname: string): boolean {
  return contextualHelpGuideForPath(pathname) !== null;
}

/** Browser-local acknowledgement key for the one-time guide discovery cue. */
export function contextualHelpCoachmarkKey(pathname: string): string {
  const guide = contextualHelpGuideForPath(pathname);
  const stablePage =
    guide?.sourceHref.replace(/^\/agents\/[^/]+\//, "/agents/:agentId/") ?? pathname;
  return `tessera:contextual-help:${CONTEXTUAL_HELP_COACHMARK_VERSION}:${stablePage}`;
}

/** Resolve the header help destination and preserve the current page filters for the return. */
export function contextualHelpHref(pathname: string, search: string): string {
  const guide = contextualHelpGuideForPath(pathname);
  if (!guide) return GLOBAL_HELP_HREF;

  const current = search ? `${pathname}?${search}` : pathname;
  return `${guide.guideHref}?from=${encodeURIComponent(current)}`;
}

/** Accept only a return route explained by the requested guide. */
export function safeContextualHelpReturnTo(
  value: string | string[] | undefined,
  guideKey: string,
): string {
  const guide = [...STATIC_CONTEXTUAL_HELP_GUIDES, ...AGENT_CONTEXTUAL_HELP_GUIDES].find(
    (candidate) => candidate.key === guideKey,
  );
  const fallback =
    guide && "sourceHref" in guide
      ? guide.sourceHref
      : guide && "page" in guide
        ? "/agents"
        : OVERVIEW_HREF;
  const candidate = safeLoginReturnTo(value);
  if (!candidate) return fallback;

  const parsed = new URL(candidate, "https://tessera.invalid");
  return contextualHelpGuideForPath(parsed.pathname)?.key === guideKey ? candidate : fallback;
}

/** Backward-compatible wrapper for the bespoke Overview guide. */
export function safeOverviewHelpReturnTo(value: string | string[] | undefined): string {
  return safeContextualHelpReturnTo(value, "overview");
}
