import "server-only";

/**
 * Is this deployment reachable by a stranger? (audit 2026-07-12, **P1 F-9**)
 *
 * The agent already answers this question, and its reasoning is the one to copy
 * (`api/security.py`, `_BEARER_REQUIRED_ENVIRONMENTS`):
 *
 *   > `is_production()` was the wrong question. It asks *"is this the prod project?"* when
 *   > what the bearer guards against is *"can a stranger reach this?"* — and for staging the
 *   > honest answer is yes.
 *
 * The front had no answer at all, which is why `accounts.ts` kept `admin/tessera-admin` alive
 * wherever the env vars were missing — credentials published in a public git repository,
 * accepted by any deployment whose operator forgot three variables.
 *
 * Two signals, OR'd, because either one alone misses a real case:
 *
 * * `TESSERA_ENVIRONMENT` — the agent's own variable, staging/production. Set by Terraform on
 *   the deployed agent. The front has no Cloud Run service of its own yet, so it cannot rely
 *   on this alone.
 * * `NODE_ENV === "production"` — every containerised front (`Dockerfile.frontend` sets it on
 *   the runtime stage). This is the clause that actually covers today's only real deployment.
 *
 * **The gap, named rather than papered over.** The tunnel demo runs `next dev` behind
 * cloudflared, so `NODE_ENV` stays `"development"` (`providers.tsx` says exactly this) and
 * `TESSERA_ENVIRONMENT` is unset — yet it IS exposed. No signal available in-process
 * distinguishes it from a laptop. So it must be *declared*: run the tunnel with
 * `TESSERA_ENVIRONMENT=staging`. Until it is, `accounts.ts` shouts the seeded defaults at
 * boot, so an operator who tunnels an undeclared instance is told, in the log, what they just
 * published. Loud where it cannot be closed; closed everywhere it can be.
 *
 * Dev and CI keep the defaults deliberately — the local loop, the e2e suite and the demo
 * banner all depend on them, and that pressure is exactly what re-loosens such checks later.
 * The exemption is therefore drawn as narrowly as the agent's: not-exposed, not not-production.
 */
export function isExposedDeployment(): boolean {
  const environment = (process.env.TESSERA_ENVIRONMENT ?? "").toLowerCase();
  if (environment === "staging" || environment === "production") return true;
  return process.env.NODE_ENV === "production";
}
