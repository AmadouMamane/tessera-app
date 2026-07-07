import { describe, expect, it } from "vitest";

import { metierTemporalMode, resolveMetierAsOf } from "./metier-temporal";

describe("resolveMetierAsOf (BR-01 §5)", () => {
  it("is live (null instant) when no as-of is posed", () => {
    expect(resolveMetierAsOf({ asof: null, at: null })).toBeNull();
    expect(metierTemporalMode(null)).toBe("live");
  });

  it("honors an explicit as-of instant (voir à date)", () => {
    const instant = "2026-07-01T09:00:00Z";
    expect(resolveMetierAsOf({ asof: instant, at: null })).toBe(instant);
    expect(metierTemporalMode(instant)).toBe("asof");
  });

  it("falls back to the history cursor when no explicit as-of", () => {
    expect(resolveMetierAsOf({ asof: null, at: "2026-06-30T12:00:00Z" })).toBe(
      "2026-06-30T12:00:00Z",
    );
  });

  it("prefers the explicit as-of over the history cursor", () => {
    expect(resolveMetierAsOf({ asof: "2026-07-01T09:00:00Z", at: "2026-06-30T12:00:00Z" })).toBe(
      "2026-07-01T09:00:00Z",
    );
  });

  it("treats an empty string as no instant", () => {
    expect(resolveMetierAsOf({ asof: "", at: "" })).toBeNull();
  });
});
