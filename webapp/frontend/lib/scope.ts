/**
 * The first-class `Scope` value object (ADR 0015) — the front's mirror of the backend
 * `tessera.observability.spine.scope.Scope`.
 *
 * A cockpit signal is read under a `Scope`: the set of dimension filters `{at, agent,
 * language, model, environment}`. This **generalises ADR 0011's as-of-T** — the temporal
 * `at` is one dimension of `Scope`, not a separate mechanism — and folds the scattered
 * `withAsOf` / `withScope` / `readAgentScope` helpers into one place. Adding a dimension
 * later (Phase F) is a field here, not a route sweep.
 *
 * Pure module (no React/Next imports) — safe from both server and client code. The agent
 * dimension rides the same `?agent=` key `lib/agent-scope` owns; `"all"`/empty is the org
 * view and is dropped so a URL stays clean.
 */

import { AGENT_SCOPE_ALL, parseAgentScope } from "./agent-scope";

/** A slicing dimension a signal may or may not support (mirrors the backend enum). */
export type Dimension = "agent" | "time" | "language" | "model" | "environment";

/** The set of dimension filters a signal is read under. Absent fields = unconstrained. */
export interface Scope {
  /** As-of-T instant (ISO) — a window end (ADR 0011). Absent = live. */
  at?: string;
  /** Concrete agent id, or absent for the deduplicated org view. */
  agent?: string;
  /** Served language filter (Phase F). */
  language?: string;
  /** Model filter (Phase F). */
  model?: string;
  /** Environment filter (ADR 0014). */
  environment?: string;
}

type ScopeParams = URLSearchParams | Record<string, string | string[] | undefined>;

function getParam(params: ScopeParams, key: string): string | undefined {
  const raw = params instanceof URLSearchParams ? params.get(key) : params[key];
  const value = Array.isArray(raw) ? raw[0] : raw;
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

/**
 * Parse a {@link Scope} from URL params (client `URLSearchParams`) or a server component's
 * awaited `searchParams` record. `agent=all`/empty becomes the org view (`agent` absent).
 */
export function parseScope(params: ScopeParams): Scope {
  const agent = parseAgentScope(getParam(params, "agent"));
  const scope: Scope = {};
  const at = getParam(params, "at");
  if (at) scope.at = at;
  if (agent !== AGENT_SCOPE_ALL) scope.agent = agent;
  const language = getParam(params, "language");
  if (language) scope.language = language;
  const model = getParam(params, "model");
  if (model) scope.model = model;
  const environment = getParam(params, "environment");
  if (environment) scope.environment = environment;
  return scope;
}

/**
 * Append a scope's dimensions to an API path as query params (absorbs `withAsOf` +
 * `withScope`). Only set dimensions are written, and the org view (`agent` absent) writes
 * no `agent=` — so the URL stays clean and cache keys collapse.
 */
export function withScope(path: string, scope: Scope): string {
  const params = new URLSearchParams();
  if (scope.at) params.set("at", scope.at);
  if (scope.agent && scope.agent !== AGENT_SCOPE_ALL) params.set("agent", scope.agent);
  if (scope.language) params.set("language", scope.language);
  if (scope.model) params.set("model", scope.model);
  if (scope.environment) params.set("environment", scope.environment);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/** A stable, order-independent React-Query key fragment for a scope. */
export function scopeKey(scope: Scope): string {
  return [
    scope.at ?? "",
    scope.agent ?? AGENT_SCOPE_ALL,
    scope.language ?? "",
    scope.model ?? "",
    scope.environment ?? "",
  ].join("|");
}

/** The `?agent=` wire value: the id, or `"all"` for the org view. */
export function scopeAgentParam(scope: Scope): string {
  return scope.agent ?? AGENT_SCOPE_ALL;
}

/** Whether the scope targets one agent (vs the deduplicated org view). */
export function isScopedToAgent(scope: Scope): boolean {
  return scope.agent !== undefined && scope.agent !== AGENT_SCOPE_ALL;
}
