import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("localization signal honesty", () => {
  it("does not render a missing catalogue as an empty measured result", () => {
    const source = readFileSync(
      join(process.cwd(), "components/observability/overview-exec.tsx"),
      "utf8",
    );
    expect(source).toContain("!localization.available || localization.measured === false");
    expect(source).toContain('tq("pred.langsUnmeasured")');
  });
});
