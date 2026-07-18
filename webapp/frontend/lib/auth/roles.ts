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
 * Who may MUTATE from the cockpit control plane — promote an agent to production,
 * rewrite runtime configuration, switch a guardrail off, decide curation, mutate
 * the governance stores (the 26 observability POSTs).
 *
 * Deliberately narrower than `hasCockpitAccess`, and the gap is the decision
 * (operator call, 2026-07-12): **the auditor reads and does not write.** ADR 0009
 * always said as much — *"auditor (audit + budget + eval detail, not settings)"* —
 * but that was only ever enforced by which pages the front chose to render. Seeing
 * a surface and being able to change it are different rights; an audit role that can
 * change what it audits is not an audit role.
 *
 * `collections` is the business plane (ADR 0010 Phase C) and never held cockpit
 * authority at all, so it is excluded here too — by `isAdmin` rather than by an
 * extra clause.
 *
 * This is the EDGE's copy of the rule; the authority is the agent's `MUTATION_ROLES`
 * (`src/tessera/api/operator.py`), which re-checks it on the signed assertion. A
 * predicate in the browser's own BFF can only ever be the friendly refusal.
 */
export function canMutateCockpit(role: Role | null): boolean {
  return isAdmin(role);
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
 * Who may ACT on the recouvrement business plane — run the assistant workflow, execute
 * governed artifact transitions, emit business events into the ledger (the two
 * `/recouvrement-assistant` POSTs). The business-plane counterpart of `canMutateCockpit`,
 * and it differs from `hasCollectionsAccess` by exactly one role, deliberately:
 *
 * - `collections` acts — these routes are its console's whole purpose;
 * - the `auditor` may still *enter* the console (`hasCollectionsAccess`) and still may
 *   not write from it. Seeing a surface and changing it are different rights, on every
 *   plane (ADR 0009; audit 2026-07-12, P0 F-1).
 *
 * This is the EDGE's copy of the rule; the authority is the agent's
 * `COLLECTIONS_MUTATION_ROLES` (`src/tessera/api/operator.py`), which re-checks it on the
 * signed assertion. A predicate in the browser's own BFF is only the friendly refusal.
 */
export function canActOnCollections(role: Role | null): boolean {
  return role === "collections" || isAdmin(role);
}

/**
 * Whether the 1-click DEMO login may run for a session of `role` entering
 * `target`. The demo shortcut exists for the ANONYMOUS visitor; a session that
 * can already enter the target must be NAVIGATED, never re-authenticated —
 * silently replacing a real session (e.g. the superadmin's) with the seeded
 * demo account is a privilege downgrade the operator never asked for (bug
 * reported 2026-07-18: superadmin → « Entrer dans le cockpit » → admin).
 * A session the target rejects still takes the demo login: that is the demo
 * launcher's whole point (one click into either plane, no account juggling).
 */
export function demoLoginNeeded(
  role: Role | null,
  target: "/produit" | "/recouvrement" | "/surveiller/vue-ensemble",
): boolean {
  if (role === null) return true;
  if (target === "/surveiller/vue-ensemble") return !hasCockpitAccess(role);
  if (target === "/recouvrement") return !hasCollectionsAccess(role);
  return !hasProductAccess(role);
}

/** The operator surfaces an assertion may carry (mirrors tessera.api.operator). */
export type OperatorSurface = "cockpit-embedded" | "dedicated-ui";

/**
 * The operator surface a session of `role` may mint for a given client-surface
 * hint — or `null` (no operator assertion). The surface is DERIVED FROM THE
 * ROLE's authority, never trusted from the hint (ADR 0010 Phase B/C hardening):
 *
 * - `cockpit-embedded` is reserved to platform operators (admin/auditor/
 *   superadmin) — the cockpit console;
 * - `dedicated-ui` is recouvrement's business console: the `collections` role, or
 *   a platform operator supervising.
 *
 * Consequence (the point of this function): a `collections` session can ONLY ever
 * mint `dedicated-ui`. Even if it spoofs the `console` hint, `isOperator` is false
 * so cockpit-embedded is unreachable — the hint cannot widen the surface. The hint
 * only selects *which* surface among those the role already authorizes.
 */
export function operatorSurfaceForHint(
  role: Role | null,
  hint: string | null,
): OperatorSurface | null {
  if (hint === "console" && isOperator(role)) return "cockpit-embedded";
  if (hint === "recouvrement" && hasCollectionsAccess(role)) return "dedicated-ui";
  return null;
}

/**
 * The operator surface a role may mint on when there is no client hint to consult — the case
 * of a plain GET through the BFF proxy (audit 2026-07-12, F-4: the subject-scoped reads now
 * require a verified assertion, so the proxy has to mint one for the human it just
 * authenticated).
 *
 * Derived from the role's own authority, exactly like `operatorSurfaceForHint`, and with the
 * same consequence: a `collections` session can only ever mint `dedicated-ui`. A role with no
 * operator authority mints nothing (`null`) — which is the safe direction, since the agent
 * grants OPERATOR only on a verified assertion.
 */
export function operatorSurfaceForRole(role: Role | null): OperatorSurface | null {
  if (isOperator(role)) return "cockpit-embedded";
  if (role === "collections") return "dedicated-ui";
  return null;
}

/**
 * Who may READ subject-scoped data — a transcript, a session detail, the memory inventory
 * (audit 2026-07-12, F-4). Every operator role, and that breadth is deliberate: the `auditor`
 * because reading is its trade (ADR 0009 — it reads and does not write), and `collections`
 * because the recouvrement console's own Récents list and conversation resume ARE two of
 * these endpoints.
 *
 * The read plane does not narrow; only the write plane does (`canMutateCockpit`). The
 * authority is the agent's `SUBJECT_READ_ROLES`.
 */
export function canReadSubjectData(role: Role | null): boolean {
  return role !== null && (isOperator(role) || role === "collections");
}

/**
 * The landing surface for a resolved role (ADR 0013). Identity is the door: an
 * authenticated operator lands on the **situational-awareness overview**
 * (`/surveiller/vue-ensemble`) — the cockpit is the *control plane*, and the
 * operator's first need is "state of everything?", a cross-fleet overview that
 * leads with governance, not an agent list. The fleet (list → detail) stays the
 * agents hub reached inside the cockpit. The collections role lands directly in
 * its own console; everyone else on the customer product. The manual picker is no
 * longer an entry — it survives only as a labelled demo launcher reached by URL.
 */
export function spaceRedirectForRole(
  role: Role | null,
): "/produit" | "/recouvrement" | "/surveiller/vue-ensemble" {
  // Business-plane role lands directly in its own console (never the cockpit).
  if (role === "collections") return "/recouvrement";
  if (isOperator(role)) return "/surveiller/vue-ensemble";
  return "/produit";
}
