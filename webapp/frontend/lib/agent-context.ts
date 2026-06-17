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
