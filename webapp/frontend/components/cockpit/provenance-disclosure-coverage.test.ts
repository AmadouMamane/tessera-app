import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("contextual provenance disclosure", () => {
  it("labels the assistant fallback only when it is used", () => {
    const source = readFileSync(
      join(root, "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );
    expect(source).toContain("assistantFallback");
    expect(source).toContain('<ProvenanceNotice signalId="assistant" compact />');
  });

  it("labels the declared AI Act control at its exact scope", () => {
    const source = readFileSync(join(root, "components/overview/overview-dashboard.tsx"), "utf8");
    expect(source).toContain('<ProvenanceNotice signalId="disclosure" compact />');
  });

  it("removes the one-size-fits-all demo copy from every locale", () => {
    for (const locale of ["fr", "en", "de"]) {
      const messages = readFileSync(join(root, "messages", `${locale}.json`), "utf8");
      expect(messages).not.toContain('"synthetic"');
      expect(messages).not.toContain("Données de démonstration");
      expect(messages).not.toContain("Demonstration data");
      expect(messages).not.toContain("Demonstrationsdaten");
    }
  });
});
