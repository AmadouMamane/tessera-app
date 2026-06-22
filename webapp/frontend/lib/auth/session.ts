/**
 * Server-side session/role resolution (ADR 0009/0013).
 *
 * The single server-bound piece: read the operator role from the verified Auth.js
 * JWT session. The pure decision logic (who may see what, where a role lands) lives
 * in `roles.ts` and is re-exported here so existing `@/lib/auth/session` imports
 * keep working — while the decisions stay unit-testable without a Next runtime.
 */
import "server-only";

import { auth } from "@/auth";
import type { Role } from "@/lib/auth/accounts";

export {
  hasCockpitAccess,
  hasProductAccess,
  isAdmin,
  isOperator,
  isSuperadmin,
  spaceRedirectForRole,
} from "@/lib/auth/roles";

/** Resolve the current role from the verified server-side next-auth session. */
export async function currentRole(): Promise<Role | null> {
  const session = await auth();
  return session?.user?.role ?? null;
}
