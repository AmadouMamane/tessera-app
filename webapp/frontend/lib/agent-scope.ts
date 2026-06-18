/**
 * Global agent-scope filter for GOUVERNER / PLATEFORME (multi-agent).
 *
 * GOUVERNER (Surveiller / Agir / Prouver) and PLATEFORME (Configurer / Admin) are
 * **global, filterable by agent**. They carry their OWN filter in the URL
 * (`?agent=all|<id>`, default `all`) — deliberately **distinct from `useAgentId`**,
 * which only scopes the AGENT section (`/agents/:id/*`). Confusing the two would
 * turn a global surface per-agent and lose the fleet view, so they never share a
 * key: the AGENT scope lives in the path, this filter lives in the query string.
 *
 * Pure module (no React/Next imports) — safe from both server and client code.
 */

/** Query-string key carrying the global agent scope. Never the path segment. */
export const AGENT_SCOPE_PARAM = "agent";

/** Sentinel meaning "all agents" (the default, deduplicated org view). */
export const AGENT_SCOPE_ALL = "all";

/**
 * Normalise a raw `?agent=` value to a scope: `"all"` or a concrete agent id.
 * Anything empty / missing falls back to `"all"`.
 */
export function parseAgentScope(raw: string | string[] | null | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value && value !== AGENT_SCOPE_ALL ? value : AGENT_SCOPE_ALL;
}

/** Whether the scope targets one agent (vs the deduplicated org view). */
export function isScopedToAgent(scope: string): boolean {
  return scope !== AGENT_SCOPE_ALL;
}

/**
 * Read the global agent scope from a server component's `searchParams`.
 * Mirror of {@link parseAgentScope} for the server (awaited searchParams).
 */
export function readAgentScope(
  searchParams: Record<string, string | string[] | undefined> | undefined,
): string {
  return parseAgentScope(searchParams?.[AGENT_SCOPE_PARAM]);
}
