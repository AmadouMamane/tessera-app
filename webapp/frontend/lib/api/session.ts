/**
 * Customer-session client (ADR 0008/0009).
 *
 * Thin wrapper over the `/api/session*` proxy. The signed session cookie is
 * httpOnly, so JS never reads it — these calls only observe/flip the state. On
 * success the agent's auth_state (server-derived from the cookie) becomes
 * `customer`, which makes recouvrement and the account tools reachable.
 */

export interface SessionState {
  authenticated: boolean;
  auth_state: string;
  subject_id: string | null;
  label: string | null;
  demo: boolean;
}

const ANONYMOUS: SessionState = {
  authenticated: false,
  auth_state: "anonymous",
  subject_id: null,
  label: null,
  demo: false,
};

async function asState(response: Response): Promise<SessionState> {
  if (!response.ok) return ANONYMOUS;
  return (await response.json()) as SessionState;
}

export async function fetchSessionState(signal?: AbortSignal): Promise<SessionState> {
  try {
    return await asState(await fetch("/api/session", { signal, cache: "no-store" }));
  } catch {
    return ANONYMOUS;
  }
}

export async function loginDemo(): Promise<SessionState> {
  return asState(await fetch("/api/session/login", { method: "POST" }));
}

export async function logoutSession(): Promise<SessionState> {
  return asState(await fetch("/api/session/logout", { method: "POST" }));
}
