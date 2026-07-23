import { describe, expect, it } from "vitest";

import { safeLoginReturnTo } from "./return-to";

describe("safeLoginReturnTo", () => {
  it("keeps an internal cockpit destination", () => {
    expect(safeLoginReturnTo("/surveiller/vue-ensemble")).toBe("/surveiller/vue-ensemble");
  });

  it("keeps a safe query string on an internal destination", () => {
    expect(safeLoginReturnTo("/surveiller/vue-ensemble?period=d30")).toBe(
      "/surveiller/vue-ensemble?period=d30",
    );
  });

  it.each([
    undefined,
    "",
    "https://example.com",
    "//example.com",
    "/\\example.com",
    "/fr/surveiller/vue-ensemble",
    "/login",
    " /surveiller/vue-ensemble",
  ])("rejects an unsafe or looping destination: %s", (value) => {
    expect(safeLoginReturnTo(value)).toBeNull();
  });

  it("uses only the first query value", () => {
    expect(safeLoginReturnTo(["/surveiller/vue-ensemble", "https://example.com"])).toBe(
      "/surveiller/vue-ensemble",
    );
  });
});
