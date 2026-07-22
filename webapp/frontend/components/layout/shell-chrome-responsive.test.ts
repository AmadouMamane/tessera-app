import { describe, expect, it } from "vitest";

import { resolveSidebarCollapsed } from "./shell-chrome";

describe("responsive shell chrome", () => {
  it("always starts compact on a narrow viewport", () => {
    expect(resolveSidebarCollapsed(null, true)).toBe(true);
    expect(resolveSidebarCollapsed("0", true)).toBe(true);
    expect(resolveSidebarCollapsed("1", true)).toBe(true);
  });

  it("honours the persisted preference on a wider viewport", () => {
    expect(resolveSidebarCollapsed(null, false)).toBe(false);
    expect(resolveSidebarCollapsed("0", false)).toBe(false);
    expect(resolveSidebarCollapsed("1", false)).toBe(true);
  });
});
