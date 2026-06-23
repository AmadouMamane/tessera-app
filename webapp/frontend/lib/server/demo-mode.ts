import "server-only";

/**
 * Demo-mode flag (server-only) — gates the 1-click seeded-account login on the
 * launcher (ADR 0009 demo posture).
 *
 * SAFETY (non-negotiable): a real production must NEVER expose a 1-click operator
 * login. So this is **off in production by default**; it is only on when explicitly
 * opted in via `TESSERA_DEMO_MODE=true` (or the legacy `TESSERA_DASHBOARD_PUBLIC`),
 * which the public *demo* deployment sets. In dev/CI it defaults on for
 * convenience. When off, the guarded cards fall back to the "sign-in required" note
 * — no demo login button is rendered and no seeded credentials are sent to the
 * client.
 */
export function isDemoMode(): boolean {
  const explicit = process.env.TESSERA_DEMO_MODE ?? process.env.TESSERA_DASHBOARD_PUBLIC;
  if (explicit != null && explicit !== "") return explicit.toLowerCase() === "true";
  return process.env.NODE_ENV !== "production";
}
