/**
 * Server-only minting of the signed OPERATOR assertion (ADR 0010 Phase B).
 *
 * The BFF mints this assertion *after* verifying a next-auth operator session
 * (`auth()`), then forwards it to the FastAPI agent, which verifies it to derive
 * `AuthState.OPERATOR`. The wire format is identical to the Python verifier
 * (`src/tessera/api/operator.py`):
 *
 *     base64url(json) "." base64url(HMAC-SHA256(key, base64url(json)))
 *     json = {"principal","role","surface","iat"}   // exact key order, no spaces
 *
 * The signing key is a server-only secret shared with the agent
 * (`TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY`, from env / Secret Manager) and
 * MUST NOT reach the browser — this module is import-guarded to server use only
 * (route handlers). Without the key, nothing is minted (the operator path is
 * inert), which is the safe direction: the agent can never be granted OPERATOR by
 * accident.
 */
import { createHmac } from "node:crypto";

/** The surface an operator assertion always carries (must match the agent). */
const OPERATOR_SURFACE = "cockpit-embedded";

/** Header the agent reads the forwarded assertion from. */
export const OPERATOR_ASSERTION_HEADER = "X-Tessera-Operator-Assertion";

function b64url(input: Buffer): string {
  return input.toString("base64url");
}

/**
 * Mint a signed operator assertion for `principal`/`role`, or `null` when no
 * signing key is configured (operator path inert). The JSON is built with the
 * exact key order and separators the Python verifier expects.
 */
export function mintOperatorAssertion(principal: string, role: string): string | null {
  const key = process.env.TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY;
  if (!key) return null;
  const payload = {
    principal,
    role,
    surface: OPERATOR_SURFACE,
    iat: Math.floor(Date.now() / 1000),
  };
  const body = b64url(Buffer.from(JSON.stringify(payload), "utf-8"));
  const signature = b64url(createHmac("sha256", key).update(body, "ascii").digest());
  return `${body}.${signature}`;
}
