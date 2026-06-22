/**
 * Seeded operator accounts for the demo (ADR 0009).
 *
 * Phase 1 has no user store: a tiny set of fixed accounts whose passwords come
 * from the environment (Secret Manager in the cloud) with demo defaults so the
 * dashboard works out of the box. Passwords are compared in constant time.
 *
 * The demo intentionally *displays* these credentials in the UI (see
 * `demoCredentials`), which makes the gate theatrical — it showcases the
 * login/RBAC flow rather than restricting access. Turning it into a real
 * restriction = stop displaying them (env passwords become genuine secrets) or
 * move to the Phase 2 OIDC provider with an email allow-list.
 */
import "server-only";

import { timingSafeEqual } from "node:crypto";

export type Role = "admin" | "auditor" | "superadmin" | "collections";

interface Account {
  username: string;
  password: string;
  role: Role;
}

// The superadmin gates the paid frontier models (e.g. GPT-5.5 via the OpenAI
// API): only this account may actually run them, so they can't be abused on a
// public demo to burn API credits. It is registered ONLY when an explicit
// password is configured — there is deliberately no weak default that could
// unlock spend, and its credentials are never surfaced in the demo banner.
const SUPERADMIN_PASSWORD = process.env.TESSERA_AUTH_SUPERADMIN_PASSWORD;

const ACCOUNTS: Account[] = [
  {
    username: "admin",
    password: process.env.TESSERA_AUTH_ADMIN_PASSWORD ?? "tessera-admin",
    role: "admin",
  },
  {
    username: "auditor",
    password: process.env.TESSERA_AUTH_AUDITOR_PASSWORD ?? "tessera-auditor",
    role: "auditor",
  },
  {
    // Business-plane role (ADR 0010 Phase C / 0013): reaches recouvrement's
    // dedicated console directly, never the cockpit. Distinct from the platform
    // roles above.
    username: "collections",
    password: process.env.TESSERA_AUTH_COLLECTIONS_PASSWORD ?? "tessera-collections",
    role: "collections",
  },
  ...(SUPERADMIN_PASSWORD
    ? [{ username: "superadmin", password: SUPERADMIN_PASSWORD, role: "superadmin" as const }]
    : []),
];

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a, "utf-8");
  const bb = Buffer.from(b, "utf-8");
  // timingSafeEqual throws on length mismatch — guard first, but still run the
  // comparison against equal-length buffers to keep the timing roughly flat.
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

/** Validate a username/password pair; returns the granted role or null. */
export function verifyCredentials(username: string, password: string): { role: Role } | null {
  const account = ACCOUNTS.find((a) => a.username === username);
  if (!account) return null;
  return safeEqual(password, account.password) ? { role: account.role } : null;
}

/**
 * Credentials surfaced in the demo banner. Synthetic and intentionally public
 * (the gate is theatrical by design — see the module docstring and ADR 0009).
 * The superadmin is deliberately excluded: its credentials are a genuine secret
 * because it can spend real API budget on the paid frontier models.
 */
export function demoCredentials(): { username: string; password: string; role: Role }[] {
  return ACCOUNTS.filter((a) => a.role !== "superadmin").map(({ username, password, role }) => ({
    username,
    password,
    role,
  }));
}
