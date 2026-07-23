import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server/backend", () => ({
  backendHeaders: () => ({}),
  backendUrl: () => "http://backend.test",
}));

import { loadFleet } from "@/lib/server/fleet";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the server-side fleet window", () => {
  it("forwards the selected period and instant to the backend aggregate", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => ({ ok: false }));
    vi.stubGlobal("fetch", fetchMock);

    await loadFleet("fr", {
      agent: "onboarding",
      period: "h24",
      asof: "2026-07-23T12:00:00+00:00",
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://backend.test/observability/fleet?lang=fr&period=h24&at=2026-07-23T12%3A00%3A00%2B00%3A00",
    );
  });

  it("uses the rail's seven-day default when the clean URL omits period", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => ({ ok: false }));
    vi.stubGlobal("fetch", fetchMock);

    await loadFleet("de", {});

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://backend.test/observability/fleet?lang=de&period=d7",
    );
  });
});
