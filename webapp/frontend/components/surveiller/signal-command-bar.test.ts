import { describe, expect, it } from "vitest";

import { periodNavigationUrl } from "@/components/surveiller/signal-command-bar";

describe("the fleet period navigation", () => {
  it("makes a non-default period visible to the server while preserving the agent scope", () => {
    expect(periodNavigationUrl("/fr/surveiller/vue-ensemble", "agent=onboarding", "h24")).toBe(
      "/fr/surveiller/vue-ensemble?agent=onboarding&period=h24",
    );
  });

  it("removes the default period without dropping the rest of the shared reading", () => {
    expect(
      periodNavigationUrl(
        "/fr/surveiller/vue-ensemble",
        "agent=onboarding&period=d30&compare=none",
        "d7",
      ),
    ).toBe("/fr/surveiller/vue-ensemble?agent=onboarding&compare=none");
  });
});
