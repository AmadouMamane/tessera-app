/**
 * Pure role/audience predicates and entry routing (ADR 0009/0013).
 *
 * This module is deliberately free of `server-only` and of any `auth()` call: it
 * holds only the *decision* logic (given a role, what may it see / where does it
 * land). The server-bound part — reading the verified next-auth session — lives
 * in `session.ts` (`currentRole`), which re-exports these helpers. Keeping the
 * decisions pure makes them unit-testable without a Next/RSC runtime.
 *
 * Authority vs. landing (ADR 0013, binding): `spaceRedirectForRole` only chooses
 * the *landing* surface. It is NOT the access control — the operator-rbac guard in
 * the cockpit layouts (`hasCockpitAccess`) remains the authority. Routing never
 * substitutes for authorization.
 */
import { DEFAULT_AGENT_ID, agentPath } from "@/lib/agent-context";
import type { Role } from "@/lib/auth/accounts";

export function isOperator(role: Role | null): boolean {
  return role === "admin" || role === "auditor" || role === "superadmin";
}

export function isAdmin(role: Role | null): boolean {
  return role === "admin" || role === "superadmin";
}

/** Only the superadmin may run the paid frontier models (e.g. GPT-5.5). */
export function isSuperadmin(role: Role | null): boolean {
  return role === "superadmin";
}

/**
 * Who may view the customer product (`/produit`). It is the *public* surface, so
 * anonymous/customer sessions (role `null`) see it — and an operator, holding the
 * higher privilege, may switch to it too (ADR 0013 operator switcher). This is
 * additive and never gates the cockpit; the cockpit authority is `hasCockpitAccess`.
 */
export function hasProductAccess(role: Role | null): boolean {
  return role === null || isOperator(role);
}

/** The operator-rbac authority for the cockpit/operator area (ADR 0009). */
export function hasCockpitAccess(role: Role | null): boolean {
  return isOperator(role);
}

/**
 * Who may reach recouvrement's dedicated business console (`/recouvrement`, ADR
 * 0010 Phase C). The `collections` business-plane role enters it directly; the
 * platform operators may also enter to supervise. A customer/anonymous session
 * never can. This gates the console route; the agent independently re-checks the
 * signed operator assertion (the authority is server-side, not this predicate).
 */
export function hasCollectionsAccess(role: Role | null): boolean {
  return role === "collections" || isOperator(role);
}

/**
 * The landing surface for a resolved role (ADR 0013). Identity is the door: an
 * authenticated operator lands in the operator area (cockpit by default); everyone
 * else (anonymous/customer) lands on the customer product. The manual picker is no
 * longer an entry — it survives only as a labelled demo launcher reached by URL.
 */
export function spaceRedirectForRole(
  role: Role | null,
): "/produit" | "/recouvrement" | `/agents/${string}/synthese` {
  // Business-plane role lands directly in its own console (never the cockpit).
  if (role === "collections") return "/recouvrement";
  if (isOperator(role)) return agentPath(DEFAULT_AGENT_ID, "synthese");
  return "/produit";
}
