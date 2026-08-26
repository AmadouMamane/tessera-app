import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server/backend", () => ({
  backendHeaders: () => ({}),
  backendUrl: () => "http://backend.test",
}));

import { loadDeclaredLens } from "@/lib/server/agent-lens";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** One fleet agent, complete enough to survive `FleetSchema` (which strips nothing silently). */
const agent = (id: string, name: string) => ({
  id,
  name,
  owner: "ops",
  conversations: 0,
  turns: 0,
  messages: 0,
  escalation_rate: 0,
  latency_ms: null,
  handoffs_in: 0,
  handoffs_out: 0,
  health: "ok",
});

/** A fleet rollup with two agents — enough for the lens to have rows to build. */
const FLEET = {
  available: true,
  agents: [agent("support-client", "SAV"), agent("recouvrement", "Recouvrement")],
};

/** An org snapshot whose SLO is met — the quality plan, which still wants the per-agent fan-out. */
const ORG_QUIET = {
  scope: { agent: "all", at: null },
  signals: {
    slo: {
      data: {
        metric: "faithfulness",
        threshold: 0.7,
        target: 0.9,
        n: 10,
        n_good: 10,
        n_bad: 0,
        good_rate: 1,
        error_budget: 0.1,
        budget_consumed: 0,
        budget_remaining: 0.1,
        burn_rate: 0,
        burn_rate_fast: 0,
        breaching: false,
      },
    },
  },
};

/** Same org read, but the page is focused on a signal with no per-agent substrate. */
const ORG_MASKED = ORG_QUIET;

const jsonResponse = (body: unknown) => ({ ok: true, json: async () => body });

describe("the declared lens loader", () => {
  it("asks the coalesced endpoint ONCE for a domain page — fleet + fan-out in one round-trip", async () => {
    // The regression this guards: the rollup and the per-agent fan-out are independent, and
    // awaiting them in series cost a second tunnel round-trip on every GOUVERNER domain page.
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      jsonResponse({ fleet: FLEET, fleet_snapshot: { agents: [] } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { fleet, lens } = await loadDeclaredLens("/surveiller/securite-privacy", "fr", {
      fleetSearchParams: { period: "h24", asof: "2026-07-23T12:00:00+00:00" },
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://backend.test/observability/fleet-batch?lang=fr&period=h24" +
        "&at=2026-07-23T12%3A00%3A00%2B00%3A00&signals=pii_leak%2Ctoxicity%2Ctool_validity",
    );
    // The fleet the caller renders is the one that read came back with — not a second fetch.
    expect(fleet?.agents?.map((a) => a.id)).toEqual(["support-client", "recouvrement"]);
    expect(lens.kind).toBe("security");
  });

  it("keeps the all-history fleet contract when the page passes no window", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      jsonResponse({ fleet: FLEET, fleet_snapshot: { agents: [] } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await loadDeclaredLens("/prouver/audit-logs", "de");

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://backend.test/observability/fleet-batch?lang=de&signals=governance%2Caudit_count",
    );
  });

  it("refuses honestly when the coalesced read fails — no fabricated fleet, no fabricated rows", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => ({ ok: false }));
    vi.stubGlobal("fetch", fetchMock);

    const { fleet, lens } = await loadDeclaredLens("/surveiller/conformite", "fr");

    expect(fleet).toBeNull();
    expect(lens.kind).toBe("monitoring");
  });

  it("passes an unavailable rollup through as unavailable — never stitched from the other half", async () => {
    // The fleet half degrades on its own terms (`available: false`, the backend's honest arm)
    // while the snapshot half is intact. The caller must see exactly that — the same object
    // `loadFleet` handed back before the two reads were coalesced — and the monitoring state,
    // never a rollup invented from the per-agent snapshots.
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      jsonResponse({ fleet: { available: false }, fleet_snapshot: { agents: [] } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { fleet, lens } = await loadDeclaredLens("/surveiller/fiabilite-cout", "fr");

    expect(fleet).toEqual({ available: false });
    expect(lens.kind).toBe("monitoring");
  });

  it("coalesces the QUALITY page's rollup with its org plan read, and only then fans out", async () => {
    // The org SLO read chooses the signal set (and can settle the page with no fan-out at all),
    // so the fan-out cannot ride along — but the rollup can, and does. 3 reads become 2.
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/observability/fleet-batch")) {
        return jsonResponse({ fleet: FLEET, snapshot: ORG_QUIET });
      }
      return jsonResponse({ agents: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    const { fleet, lens } = await loadDeclaredLens("/surveiller/qualite-ia", "fr", {
      fleetSearchParams: {},
    });

    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls).toEqual([
      "http://backend.test/observability/fleet-batch?lang=fr&period=d7&org_signals=slo",
      "http://backend.test/observability/fleet-snapshot?signals=slo%2Cscores&days=d7",
    ]);
    expect(fleet?.agents?.map((a) => a.id)).toEqual(["support-client", "recouvrement"]);
    expect(lens.kind).toBe("quality");
  });

  it("fans out under the SAME window and anchor as the rollup — one card, one clock", async () => {
    // The regression this guards (operator, 2026-08-26): the per-agent rows read all history
    // while the fleet total beside them obeyed the rail — the period selector changed the
    // total under the table and nothing in it. The fan-out's `days`/`at` must be the very
    // values `fleetQuery` resolved for the batch read, never re-derived.
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/observability/fleet-batch")) {
        return jsonResponse({ fleet: FLEET, snapshot: ORG_QUIET });
      }
      return jsonResponse({ agents: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    await loadDeclaredLens("/surveiller/qualite-ia", "fr", {
      fleetSearchParams: { period: "h24", asof: "2026-07-23T12:00:00+00:00" },
    });

    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls).toEqual([
      "http://backend.test/observability/fleet-batch?lang=fr&period=h24" +
        "&at=2026-07-23T12%3A00%3A00%2B00%3A00&org_signals=slo",
      "http://backend.test/observability/fleet-snapshot?signals=slo%2Cscores&days=h24" +
        "&at=2026-07-23T12%3A00%3A00%2B00%3A00",
    ]);
  });

  it("spends ONE read on the quality page when the org plan settles it org-wide", async () => {
    // The masked plan needs no per-agent fan-out at all — and now not a separate rollup read
    // either, since the rollup travelled with the org read that decided it.
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      jsonResponse({ fleet: FLEET, snapshot: ORG_MASKED }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { lens } = await loadDeclaredLens("/surveiller/qualite-ia", "fr", {
      fleetSearchParams: {},
      signalId: "audit_integrity",
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(lens.kind).toBe("masked");
  });
});
