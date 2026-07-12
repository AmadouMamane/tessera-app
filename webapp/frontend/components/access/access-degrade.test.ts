// The `access` degrade bug, closed (audit P1.4).
//
// `/observability/access` answers `{available: false}` — and nothing else — when the roles store
// is unreachable. That response exists so the page DEGRADES instead of breaking. But
// `AccessOverviewSchema` was a flat `z.object` with every payload field REQUIRED, so:
//
//   safeParse({available:false})  ->  12 missing fields  ->  request() throws ApiError
//
// The page therefore broke on the exact response that exists to keep it standing, and it broke
// precisely when the backend was already failing. It also threw in the SSR prefetch
// (`roles-acces/page.tsx` calls `AccessOverviewSchema.parse`), so the failure was a server error,
// not a client fallback.
//
// The schema is now a discriminated union. `available: true` GUARANTEES the payload;
// `available: false` is a valid, expected answer that carries nothing.
import { describe, expect, it } from "vitest";

import { AccessOverviewSchema } from "@/lib/api/schemas";

describe("the access schema accepts the backend's own honest-empty degrade", () => {
  it("parses {available:false} — the response the page must survive", () => {
    const parsed = AccessOverviewSchema.safeParse({ available: false });

    expect(parsed.success).toBe(true);
    expect(parsed.data).toEqual({ available: false });
  });

  it("does not invent a payload for the degraded answer", () => {
    // Honest-empty means EMPTY. A schema that filled in defaults here would be fabricating a
    // roles catalogue out of an outage — the exact dishonesty the doctrine forbids.
    const parsed = AccessOverviewSchema.parse({ available: false });

    expect(Object.keys(parsed)).toEqual(["available"]);
  });

  it("still REJECTS a payload that claims available:true and omits its fields", () => {
    // The other half, and what the flat schema could never say: the discriminator now carries a
    // guarantee. A backend that dropped `roles` while claiming success is caught here.
    const parsed = AccessOverviewSchema.safeParse({ available: true });

    expect(parsed.success).toBe(false);
  });

  it("still parses a real payload unchanged", () => {
    const real = {
      available: true,
      generated_at: "2026-07-12T10:00:00Z",
      total_roles: 3,
      page_size: 10,
      kpis: [],
      roles: [],
      selected: {
        id: "admin",
        name: "Administrateur",
        type: "systeme" as const,
        scope: "org",
        description: "",
        owner: "",
        created: "-",
        modified: "-",
        status: "active" as const,
        environment: "prod",
        members: [],
        permission_dist: [],
        access_scope: [],
        caps: [],
      },
      top_roles: [],
      access_by_resource: [],
      pending_requests: [],
      sod_violations: [],
      inactive_accounts: [],
      footer: { total: 3, source: "registry" },
    };

    const parsed = AccessOverviewSchema.safeParse(real);

    expect(parsed.success, JSON.stringify(parsed.error?.issues?.[0])).toBe(true);
    expect(parsed.data).toEqual(real);
  });
});
