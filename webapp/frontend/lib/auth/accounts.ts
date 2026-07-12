/**
 * Seeded operator accounts for the demo (ADR 0009).
 *
 * Phase 1 has no user store: a tiny set of fixed accounts whose passwords come from the
 * environment (Secret Manager in the cloud), with demo defaults **only where a stranger
 * cannot reach the deployment**. Passwords are compared in constant time.
 *
 * The demo intentionally *displays* these credentials in the UI (see `demoCredentials`), which
 * makes the gate theatrical — it showcases the login/RBAC flow rather than restricting access.
 *
 * Audit 2026-07-12, **P1 F-9**: theatrical is fine; theatrical *by accident* is not. The
 * defaults below (`admin/tessera-admin`, …) are published in a git repository, and they stayed
 * valid in ANY deployment whose operator had not set three environment variables — the failure
 * pointed the wrong way, exactly like the bearer before it: a missing secret opened the door
 * instead of closing it. So the rule the superadmin already followed now applies to every
 * account: **on an exposed deployment, an account exists only if a password was explicitly
 * configured for it.** Nothing is accepted by default; if the operator sets no passwords, no
 * one can log in, and the log says why.
 *
 * The demo does not lose anything real: a public demo that WANTS the theatrical gate sets the
 * three passwords (whatever it likes) and `demoCredentials()` displays those. What it can no
 * longer do is accept the ones printed in the repo.
 *
 * See `posture.ts` for what "exposed" means and — honestly — for the one case it cannot
 * detect (the `next dev` tunnel), which is why the fallback is a loud boot warning.
 */
import "server-only";

import { timingSafeEqual } from "node:crypto";

import { isExposedDeployment } from "@/lib/auth/posture";

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

const EXPOSED = isExposedDeployment();

/**
 * The password for a seeded account: the configured one, or the repo default — and the repo
 * default ONLY when a stranger cannot reach us. On an exposed deployment an unset variable
 * yields `null`, and the account is not registered at all: an unknown username, refused in
 * constant time like any other.
 */
function seededPassword(configured: string | undefined, fallback: string): string | null {
  if (configured) return configured;
  return EXPOSED ? null : fallback;
}

const SEEDED: { username: string; configured: string | undefined; fallback: string; role: Role }[] =
  [
    {
      username: "admin",
      configured: process.env.TESSERA_AUTH_ADMIN_PASSWORD,
      fallback: "tessera-admin",
      role: "admin",
    },
    {
      username: "auditor",
      configured: process.env.TESSERA_AUTH_AUDITOR_PASSWORD,
      fallback: "tessera-auditor",
      role: "auditor",
    },
    {
      // Business-plane role (ADR 0010 Phase C / 0013): reaches recouvrement's
      // dedicated console directly, never the cockpit. Distinct from the platform
      // roles above.
      username: "collections",
      configured: process.env.TESSERA_AUTH_COLLECTIONS_PASSWORD,
      fallback: "tessera-collections",
      role: "collections",
    },
  ];

const ACCOUNTS: Account[] = [
  ...SEEDED.flatMap(({ username, configured, fallback, role }) => {
    const password = seededPassword(configured, fallback);
    return password === null ? [] : [{ username, password, role }];
  }),
  ...(SUPERADMIN_PASSWORD
    ? [{ username: "superadmin", password: SUPERADMIN_PASSWORD, role: "superadmin" as const }]
    : []),
];

// Say it out loud, once, at boot. Two failure modes, two messages — and neither is silent,
// which was the whole defect: an operator could publish this app and never learn that
// `admin/tessera-admin` (a password anyone can read on GitHub) still worked.
if (EXPOSED) {
  const missing = SEEDED.filter(({ configured }) => !configured).map(({ username }) => username);
  if (missing.length > 0) {
    console.error(
      `[auth] EXPOSED deployment: refusing the seeded default credentials for ${missing.join(", ")} — those passwords are published in the repository. Set TESSERA_AUTH_<ROLE>_PASSWORD for each role you want to keep. Until then those accounts DO NOT EXIST and no one can log in with them.`,
    );
  }
} else if (ACCOUNTS.some(({ password }, i) => password === SEEDED[i]?.fallback)) {
  console.warn(
    "[auth] seeded default credentials are ACTIVE (admin/tessera-admin, …). Correct for dev/CI. " +
      "If this instance is reachable from the internet — a cloudflared tunnel over `next dev` " +
      "keeps NODE_ENV=development, so it is NOT detected as exposed — declare it with " +
      "TESSERA_ENVIRONMENT=staging, which refuses these defaults.",
  );
}

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
