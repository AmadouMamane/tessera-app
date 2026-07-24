export interface ContextualHelpView {
  key: string;
  labelKey: string;
}

export interface ContextualHelpViewGroup {
  key: string;
  titleKey: string;
  param: string;
  fallback: string;
  views: readonly ContextualHelpView[];
  requiredParams?: Readonly<Record<string, string>>;
  clearedParams?: readonly string[];
}

function pageViews(
  guideKey: string,
  namespace: string,
  keys: readonly string[],
): readonly ContextualHelpViewGroup[] {
  return [
    {
      key: "page",
      titleKey: `pageHelp.guides.${guideKey}.title`,
      param: "vue",
      fallback: "overview",
      views: keys.map((key) => ({ key, labelKey: `${namespace}.tabs.${key}` })),
    },
  ];
}

/**
 * Page-level lenses exposed by the cockpit.
 *
 * Labels deliberately point to the page's existing catalogue. Only the
 * explanations live under `pageHelp`, so the cockpit and its guide cannot drift
 * into two different names for the same view.
 */
export const CONTEXTUAL_HELP_VIEW_GROUPS: Readonly<
  Record<string, readonly ContextualHelpViewGroup[]>
> = {
  quality: [
    {
      key: "surfaces",
      titleKey: "pageHelp.viewAtlas.surfaceTitle",
      param: "vue",
      fallback: "signals",
      clearedParams: ["tab"],
      views: [
        { key: "signals", labelKey: "quality.views.signals" },
        { key: "evaluations", labelKey: "quality.views.evaluations" },
      ],
    },
    {
      key: "signals",
      titleKey: "quality.views.signals",
      param: "tab",
      fallback: "overview",
      requiredParams: { vue: "signals" },
      views: ["overview", "signals", "runs", "failed", "models", "judge"].map((key) => ({
        key,
        labelKey: `quality.tabs.${key}`,
      })),
    },
    {
      key: "evaluations",
      titleKey: "quality.views.evaluations",
      param: "tab",
      fallback: "runs",
      requiredParams: { vue: "evaluations" },
      views: ["cases", "runs", "compare"].map((key) => ({
        key,
        labelKey: `eval.tabs.${key}`,
      })),
    },
  ],
  security: pageViews("security", "security", [
    "overview",
    "promptInjection",
    "pii",
    "guard",
    "tools",
    "memory",
    "isolation",
    "redteam",
  ]),
  compliance: pageViews("compliance", "compliance", [
    "overview",
    "mapping",
    "obligations",
    "evaluations",
    "incidents",
    "retention",
    "evidence",
    "registry",
  ]),
  reliability: pageViews("reliability", "reliability", [
    "overview",
    "reliability",
    "cost",
    "performance",
    "quotas",
    "incidents",
    "capacity",
  ]),
  improvement: pageViews("improvement", "improvement", [
    "overview",
    "plan",
    "curation",
    "experiments",
    "release",
  ]),
  incidents: pageViews("incidents", "incidents", [
    "overview",
    "incidents",
    "playbooks",
    "orchestration",
    "actions",
    "postmortems",
    "problemes",
    "rapports",
  ]),
  replay: pageViews("replay", "replay", [
    "overview",
    "cassettes",
    "sessions",
    "shadow",
    "comparisons",
    "baselines",
    "diffs",
    "evals",
    "exports",
  ]),
  curation: pageViews("curation", "curation", [
    "overview",
    "curate",
    "coverage",
    "promotions",
    "rejections",
    "history",
  ]),
  automations: pageViews("automations", "automations", [
    "overview",
    "rules",
    "executions",
    "approvals",
    "audit",
  ]),
  evidence: pageViews("evidence", "proofs", [
    "overview",
    "evidencePacks",
    "exporters",
    "chain",
    "destinations",
  ]),
  policies: pageViews("policies", "policies", [
    "overview",
    "activePolicies",
    "history",
    "runtimeGuardrails",
    "impactSimulator",
    "approvals",
  ]),
  sources: pageViews("sources", "sources", [
    "overview",
    "sources",
    "memory",
    "indexation",
    "quality",
    "access",
    "retention",
    "lineage",
    "history",
  ]),
  parameters: pageViews("parameters", "parameters", [
    "overview",
    "general",
    "security",
    "data",
    "models",
    "access",
    "notifications",
    "integrations",
    "audit",
    "system",
  ]),
};

export function contextualHelpViewAnchor(guideKey: string, groupKey: string, viewKey: string) {
  return `vue-${guideKey}-${groupKey}-${viewKey}`;
}

export function sourceHrefForHelpView(
  backHref: string,
  group: ContextualHelpViewGroup,
  viewKey: string,
): string {
  const url = new URL(backHref, "https://tessera.invalid");
  for (const param of group.clearedParams ?? []) url.searchParams.delete(param);
  for (const [param, value] of Object.entries(group.requiredParams ?? {})) {
    if (param === "vue" && value === "signals") url.searchParams.delete(param);
    else url.searchParams.set(param, value);
  }
  if (viewKey === group.fallback) url.searchParams.delete(group.param);
  else url.searchParams.set(group.param, viewKey);
  return `${url.pathname}${url.search}${url.hash}`;
}

export function activeHelpView(backHref: string, group: ContextualHelpViewGroup): string {
  const url = new URL(backHref, "https://tessera.invalid");
  const required = Object.entries(group.requiredParams ?? {});
  const matchesContext = required.every(([param, value]) => {
    const actual = url.searchParams.get(param);
    return value === "signals" ? actual === null || actual === "signals" : actual === value;
  });
  if (!matchesContext) return "";
  const raw = url.searchParams.get(group.param);
  return group.views.some((view) => view.key === raw) ? (raw ?? group.fallback) : group.fallback;
}
