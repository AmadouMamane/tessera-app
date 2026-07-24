import { describe, expect, it } from "vitest";

import { COCKPIT_VIEW_PARAM } from "@/lib/use-url-backed-view";

describe("URL-backed cockpit views", () => {
  it("uses one declared parameter for page-level views", () => {
    expect(COCKPIT_VIEW_PARAM).toBe("vue");
  });
});
