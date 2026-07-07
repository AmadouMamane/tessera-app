/**
 * Agent scope for the AGENT cockpit section (multi-agent foundation, Phase 0).
 *
 * The AGENT section is scoped to a selected agent: its routes are
 * `/agents/<agentId>/...`. Every internal link in that section is built with
 * {@link agentPath} (never a literal `/agents/...` or hard-coded id). Until the
 * registry/switcher lands (Phase 1/3) there is a single agent,
 * {@link DEFAULT_AGENT_ID} — the same slug the backend stamps on events, metrics
 * and messages, so data and URLs agree.
 *
 * This module is pure (no React/Next imports) so it is safe from both server
 * (redirects, layouts) and client code. The active agent is read in client
 * components with `useAgentId` from `@/lib/use-agent-id`.
 *
 * The slug is intentionally the URL segment only (no locale prefix): pair it
 * with `Link`/`redirect` from `@/i18n/navigation`, which add the locale.
 */

/** Default agent slug used until the agent registry (Phase 1) lands. */
export const DEFAULT_AGENT_ID = "support-client";

/** AGENT section leaf pages (the slugs under `/agents/<agentId>/`). */
export type AgentPage =
  | "synthese"
  | "configurations"
  | "connaissances"
  | "garde-fous"
  | "prompts"
  | "metier"
  | "evaluations"
  | "console"
  | "historique";

/**
 * Build a locale-agnostic, agent-scoped cockpit path.
 *
 * The `"synthese"` overload returns the precise template type so callers that
 * declare a `/agents/${string}/synthese` slot (space switcher, role redirect)
 * type-check without a cast.
 *
 * @example agentPath("support-client", "synthese") // "/agents/support-client/synthese"
 */
export function agentPath(agentId: string, page: "synthese"): `/agents/${string}/synthese`;
export function agentPath(agentId: string, page?: AgentPage | string): string;
export function agentPath(agentId: string, page: AgentPage | string = ""): string {
  return page ? `/agents/${agentId}/${page}` : `/agents/${agentId}`;
}

/**
 * i18n namespace carrying each AGENT page's `title` + `subtitle`. Co-located with
 * the route registry so the section header (rendered once by the AGENT-area
 * layout) and the tab strip stay in sync — the title derives from the URL, never
 * from page-local state (see `ui-contract.md`).
 */
export const AGENT_PAGE_NAMESPACE: Record<AgentPage, string> = {
  synthese: "agentSynthese",
  configurations: "agentConfigurations",
  connaissances: "agentConnaissances",
  "garde-fous": "agentGardeFous",
  prompts: "agentPrompts",
  metier: "agentMetier",
  evaluations: "agentEvaluations",
  console: "agentConsole",
  historique: "agentHistorique",
};

/**
 * Resolve the topbar header namespace for an AGENT-area pathname (locale-stripped,
 * e.g. `/agents/support-client/evaluations`). The fleet list and each section map
 * to the namespace whose `title`/`subtitle` describe the active view. Drill-downs
 * (`/agents/<id>/historique/<sessionId>`) reuse their section's header and render
 * their own in-body header for the specific item.
 */
export function agentAreaHeaderNamespace(pathname: string): string {
  const seg = pathname.split("/").filter(Boolean);
  if (seg[0] !== "agents") return "fleet";
  if (seg.length === 1) return "fleet";
  if (seg.length === 2) return AGENT_PAGE_NAMESPACE.synthese; // /agents/<id> → redirects to synthese
  return AGENT_PAGE_NAMESPACE[seg[2] as AgentPage] ?? AGENT_PAGE_NAMESPACE.synthese;
}
