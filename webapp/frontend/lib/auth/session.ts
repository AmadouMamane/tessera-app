/**
 * Server-side session/role helpers (ADR 0009).
 *
 * Read the operator role from the Auth.js JWT session and decide who may see
 * the operator surfaces (audit, budget, per-case eval detail). Both `admin` and
 * `auditor` are operators; only `admin` may reach the settings surface.
 */
import "server-only";

import { auth } from "@/auth";
import type { Role } from "@/lib/auth/accounts";

export async function currentRole(): Promise<Role | null> {
  const session = await auth();
  return session?.user?.role ?? null;
}

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

export function hasProductAccess(role: Role | null): boolean {
  return role === null || role === "admin" || role === "superadmin";
}

export function hasCockpitAccess(role: Role | null): boolean {
  return isOperator(role);
}

export function hasDualSpaceAccess(role: Role | null): boolean {
  return hasProductAccess(role) && hasCockpitAccess(role);
}

export function spaceRedirectForRole(
  role: Role | null,
): "/select-space" | "/produit" | "/agent/synthese" {
  if (hasDualSpaceAccess(role)) return "/select-space";
  if (hasCockpitAccess(role)) return "/agent/synthese";
  return "/produit";
}
