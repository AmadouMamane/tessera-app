import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  CONTEXTUAL_HELP_VIEW_GROUPS,
  activeHelpView,
  sourceHrefForHelpView,
} from "@/lib/contextual-help-views";
import { DASHBOARD_TAB_PARAM, EVAL_TAB_PARAM, QUALITY_VIEW_PARAM } from "@/lib/quality-tabs";

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
      ["signals", ["overview", "signals"]],
      ["evaluations", ["cases", "runs", "compare", "archive", "failed", "models", "judge"]],
    ]);
  });

  /**
   * The atlas is the page's own map, and a map that names a parameter the page stopped reading
   * sends every one of its links to the default view without failing.
   *
   * That happened: the monitoring strip's parameter was renamed to `onglet` — the two strips
   * used to collide on `?tab=` — and this registry kept writing `tab`, so its dashboard links
   * silently landed on the overview for as long as the rename existed. Asserted against the
   * declared constants rather than the literals, so the next rename cannot leave the map behind.
   */
  it("addresses each strip by the parameter that strip actually reads", () => {
    const [surfaces, signals, evaluations] = CONTEXTUAL_HELP_VIEW_GROUPS.quality ?? [];
    expect(surfaces?.param).toBe(QUALITY_VIEW_PARAM);
    expect(signals?.param).toBe(DASHBOARD_TAB_PARAM);
    expect(evaluations?.param).toBe(EVAL_TAB_PARAM);
    // Switching view must drop BOTH strips' tabs: carrying `onglet` into the evaluations view
    // (or `tab` back out of it) is how a link starts meaning two different screens again.
    expect(surfaces?.clearedParams).toEqual(
      expect.arrayContaining([EVAL_TAB_PARAM, DASHBOARD_TAB_PARAM]),
    );
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
