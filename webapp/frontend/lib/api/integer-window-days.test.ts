import { describe, expect, it } from "vitest";

import { integerWindowDays } from "./client";

describe("integerWindowDays", () => {
  it.each([
    ["h24", 1],
    ["d7", 7],
    ["d30", 30],
    ["14", 14],
  ])("maps %s to %i day(s)", (window, expected) => {
    expect(integerWindowDays(window)).toBe(expected);
  });

  it.each([undefined, "", "all", "d0", "-1"])("rejects unsupported window %s", (window) => {
    expect(integerWindowDays(window)).toBeUndefined();
  });
});
