import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  CONTEXTUAL_HELP_VIEW_GROUPS,
  activeHelpView,
  sourceHrefForHelpView,
} from "@/lib/contextual-help-views";

const root = process.cwd();

function atPath(value: unknown, path: string): unknown {
  return path
    .split(".")
    .reduce<unknown>(
      (node, key) =>
        node && typeof node === "object" ? (node as Record<string, unknown>)[key] : undefined,
      value,
    );
}

function requiredGroup(guideKey: string, index = 0) {
  const group = CONTEXTUAL_HELP_VIEW_GROUPS[guideKey]?.[index];
  if (!group) throw new Error(`Missing contextual help group: ${guideKey}[${index}]`);
  return group;
}

describe("contextual help view contract", () => {
  it("declares every first-level Quality IA view", () => {
    const groups = CONTEXTUAL_HELP_VIEW_GROUPS.quality ?? [];
    expect(groups.map((group) => [group.key, group.views.map((view) => view.key)])).toEqual([
      ["surfaces", ["signals", "evaluations"]],
      ["signals", ["overview", "signals", "runs", "failed", "models", "judge"]],
      ["evaluations", ["cases", "runs", "compare"]],
    ]);
  });

  it("recognises the nested evaluation tab from the return URL", () => {
    const group = requiredGroup("quality", 2);
    expect(activeHelpView("/surveiller/qualite-ia?vue=evaluations&tab=compare", group)).toBe(
      "compare",
    );
  });

  it("keeps unrelated filters when opening a documented view", () => {
    const group = requiredGroup("security");
    expect(
      sourceHrefForHelpView(
        "/surveiller/securite-privacy?period=d30&agent=recouvrement",
        group,
        "pii",
      ),
    ).toBe("/surveiller/securite-privacy?period=d30&agent=recouvrement&vue=pii");
  });

  it("has a real label and a dedicated explanation in every language", () => {
    for (const locale of ["fr", "en", "de"]) {
      const messages = JSON.parse(readFileSync(join(root, `messages/${locale}.json`), "utf8"));
      for (const [guideKey, groups] of Object.entries(CONTEXTUAL_HELP_VIEW_GROUPS)) {
        for (const group of groups) {
          expect(atPath(messages, group.titleKey), `${locale}:${group.titleKey}`).toBeTruthy();
          for (const view of group.views) {
            expect(atPath(messages, view.labelKey), `${locale}:${view.labelKey}`).toBeTruthy();
            const description = `pageHelp.viewDescriptions.${guideKey}.${group.key}.${view.key}`;
            expect(atPath(messages, description), `${locale}:${description}`).toBeTruthy();
          }
        }
      }
    }
  });

  it("covers every page-level tab declared by the cockpit components", () => {
    const sources = {
      automations: ["components/automations/automations-overview.tsx", "TABS"],
      compliance: ["components/compliance/compliance-dashboard.tsx", "TABS"],
      curation: ["components/curation/curation-overview.tsx", "TABS"],
      improvement: ["components/improvement/improvement-dashboard.tsx", "TABS"],
      incidents: ["components/incidents/incidents-overview.tsx", "TABS"],
      reliability: ["components/reliability/reliability-dashboard.tsx", "TABS"],
      replay: ["components/replay/replay-overview.tsx", "TABS"],
      security: ["components/security/security-dashboard.tsx", "SEC_TABS"],
      evidence: ["components/proofs/proofs-overview.tsx", "TABS"],
      policies: ["components/policies/policies-overview.tsx", "TABS"],
      sources: ["components/sources/sources-overview.tsx", "VIEWS"],
      parameters: ["components/parameters/parameters-overview.tsx", "TABS"],
    } as const;

    for (const [guideKey, [file, constant]] of Object.entries(sources)) {
      const source = readFileSync(join(root, file), "utf8");
      const literal = source.match(new RegExp(`const ${constant} = \\[([\\s\\S]*?)\\] as const`));
      expect(literal, `${guideKey}:${constant}`).not.toBeNull();
      const actual = [...(literal?.[1] ?? "").matchAll(/"([^"]+)"/g)].map((match) => match[1]);
      const documented = requiredGroup(guideKey).views.map((view) => view.key);
      expect(documented, guideKey).toEqual(actual);
    }
  });
});
