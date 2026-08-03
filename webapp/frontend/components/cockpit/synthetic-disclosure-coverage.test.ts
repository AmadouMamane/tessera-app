import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("deterministic disclosure", () => {
  it("labels the assistant fallback only when it is used", () => {
    const source = readFileSync(
      join(root, "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );
    expect(source).toContain("assistantSynthetic");
    expect(source).toContain('<SyntheticNotice signalId="assistant" compact />');
  });

  it("labels the deterministic AI Act disclosure fixture", () => {
    const source = readFileSync(join(root, "components/overview/overview-dashboard.tsx"), "utf8");
    expect(source).toContain('<SyntheticNotice signalId="disclosure" compact />');
  });
});
