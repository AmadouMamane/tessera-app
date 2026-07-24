import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AGENT_CONTEXTUAL_HELP_GUIDES,
  GLOBAL_HELP_HREF,
  STATIC_CONTEXTUAL_HELP_GUIDES,
  contextualHelpCoachmarkKey,
  contextualHelpGuideForHref,
  contextualHelpHref,
  hasContextualHelp,
  safeContextualHelpReturnTo,
  safeOverviewHelpReturnTo,
} from "./contextual-help";

const root = process.cwd();
const cockpitPageGuide = readFileSync(
  join(root, "components/comprendre/cockpit-page-guide.tsx"),
  "utf8",
);
const overviewPageGuide = readFileSync(
  join(root, "components/comprendre/overview-page-guide.tsx"),
  "utf8",
);

describe("contextual cockpit help", () => {
  it("opens a static guide and preserves the current reading", () => {
    expect(
      contextualHelpHref(
        "/surveiller/vue-ensemble",
        "period=d30&lecture=history&agent=support-client",
      ),
    ).toBe(
      "/comprendre/surveiller/vue-ensemble?from=%2Fsurveiller%2Fvue-ensemble%3Fperiod%3Dd30%26lecture%3Dhistory%26agent%3Dsupport-client",
    );
    expect(contextualHelpHref("/surveiller/qualite-ia", "period=d30")).toBe(
      "/comprendre/surveiller/qualite-ia?from=%2Fsurveiller%2Fqualite-ia%3Fperiod%3Dd30",
    );
  });

  it("opens one shared guide per agent tab while preserving the selected agent and session", () => {
    expect(
      contextualHelpHref("/agents/support-client/historique/conversation-42", "tab=messages"),
    ).toBe(
      "/comprendre/agents/historique?from=%2Fagents%2Fsupport-client%2Fhistorique%2Fconversation-42%3Ftab%3Dmessages",
    );
    expect(hasContextualHelp("/agents/support-client/prompts")).toBe(true);
    expect(hasContextualHelp("/agents/support-client/unknown")).toBe(false);
  });

  it("keeps the global explanation as the honest fallback outside the cockpit programme", () => {
    expect(contextualHelpHref("/recouvrement", "")).toBe(GLOBAL_HELP_HREF);
    expect(hasContextualHelp("/recouvrement")).toBe(false);
  });

  it("keeps one versioned acknowledgement per page, not per selected agent", () => {
    expect(contextualHelpCoachmarkKey("/surveiller/vue-ensemble")).toBe(
      "tessera:contextual-help:2026-07:/surveiller/vue-ensemble",
    );
    expect(contextualHelpCoachmarkKey("/agents/support-client/prompts")).toBe(
      contextualHelpCoachmarkKey("/agents/onboarding/prompts"),
    );
    expect(contextualHelpCoachmarkKey("/agents/support-client/prompts")).not.toBe(
      contextualHelpCoachmarkKey("/agents/support-client/evaluations"),
    );
  });

  it("accepts only a safe return to the page explained by the guide", () => {
    expect(safeOverviewHelpReturnTo("/surveiller/vue-ensemble?period=d30")).toBe(
      "/surveiller/vue-ensemble?period=d30",
    );
    expect(safeOverviewHelpReturnTo("https://example.com")).toBe("/surveiller/vue-ensemble");
    expect(safeOverviewHelpReturnTo("/agir/release-control")).toBe("/surveiller/vue-ensemble");

    expect(
      safeContextualHelpReturnTo(
        "/agents/support-client/evaluations?run=latest",
        "agentEvaluations",
      ),
    ).toBe("/agents/support-client/evaluations?run=latest");
    expect(safeContextualHelpReturnTo("/agents/support-client/prompts", "agentEvaluations")).toBe(
      "/agents",
    );
    expect(safeContextualHelpReturnTo("/surveiller/qualite-ia", "security")).toBe(
      "/surveiller/securite-privacy",
    );
  });

  it("covers every real sidebar destination and no undeclared sidebar destination", () => {
    const sidebar = readFileSync(join(root, "components/layout/sidebar.tsx"), "utf8");
    const sidebarHrefs = [...sidebar.matchAll(/\{\s*href:\s*"(\/[^"]+)"/g)].map(
      (match) => match[1],
    );
    const uniqueSidebarHrefs = [...new Set(sidebarHrefs)].sort();
    const declared = STATIC_CONTEXTUAL_HELP_GUIDES.filter(
      (guide) => guide.sourceHref !== "/settings",
    )
      .map((guide) => guide.sourceHref)
      .sort();

    expect(uniqueSidebarHrefs.length).toBeGreaterThanOrEqual(29);
    expect(declared).toEqual(uniqueSidebarHrefs);
  });

  it("covers every real agent tab and no undeclared agent tab", () => {
    const tabs = readFileSync(join(root, "components/agent/agent-tabs.tsx"), "utf8");
    const tabPages = [...tabs.matchAll(/\{\s*page:\s*"([^"]+)"/g)].map((match) => match[1]).sort();
    const declared = AGENT_CONTEXTUAL_HELP_GUIDES.map((guide) => guide.page).sort();

    expect(tabPages.length).toBeGreaterThanOrEqual(9);
    expect(declared).toEqual(tabPages);
  });

  it("backs every declared destination with a real guide route", () => {
    const catchAll = join(root, "app/[locale]/comprendre/[...segments]/page.tsx");
    expect(existsSync(catchAll)).toBe(true);
    expect(existsSync(join(root, "app/[locale]/comprendre/surveiller/vue-ensemble/page.tsx"))).toBe(
      true,
    );

    for (const guide of STATIC_CONTEXTUAL_HELP_GUIDES) {
      expect(contextualHelpGuideForHref(guide.guideHref)?.key).toBe(guide.key);
    }
    for (const guide of AGENT_CONTEXTUAL_HELP_GUIDES) {
      expect(contextualHelpGuideForHref(`/comprendre/agents/${guide.page}`)?.key).toBe(guide.key);
    }
  });

  it("keeps the complete guide catalogue structurally identical in all languages", () => {
    const messages = ["fr", "en", "de"].map((locale) =>
      JSON.parse(readFileSync(join(root, `messages/${locale}.json`), "utf8")),
    );
    const paths = (node: object, prefix = ""): string[] =>
      Object.entries(node).flatMap(([key, value]) => {
        const path = prefix ? `${prefix}.${key}` : key;
        return value && typeof value === "object" ? paths(value, path) : [path];
      });

    const [fr, en, de] = messages.map((message) => paths(message.pageHelp));
    expect(en).toEqual(fr);
    expect(de).toEqual(fr);

    const declaredKeys = [
      ...STATIC_CONTEXTUAL_HELP_GUIDES.filter((guide) => guide.key !== "overview").map(
        (guide) => guide.key,
      ),
      ...AGENT_CONTEXTUAL_HELP_GUIDES.map((guide) => guide.key),
    ].sort();
    expect(Object.keys(messages[0].pageHelp.guides).sort()).toEqual(declaredKeys);
  });

  it("keeps the guide opening inset and every reading connector continuous", () => {
    expect(cockpitPageGuide).toContain("border-[var(--tessera-border)] border-y px-5 py-10");
    expect(cockpitPageGuide).toContain("absolute inset-x-0 top-5 hidden h-px bg-gradient-to-r");
    expect(overviewPageGuide).toContain("absolute inset-x-0 top-5 hidden h-px bg-gradient-to-r");

    const flushOpening = cockpitPageGuide.replace("border-y px-5 py-10", "border-y py-10");
    const shortenedConnector = cockpitPageGuide.replace(
      "absolute inset-x-0 top-5",
      "absolute left-[8%] right-[8%] top-5",
    );
    const shortenedOverviewConnector = overviewPageGuide.replace(
      "absolute inset-x-0 top-5",
      "absolute left-[8%] right-[8%] top-5",
    );
    expect(flushOpening).not.toContain("border-y px-5 py-10");
    expect(shortenedConnector).not.toContain("absolute inset-x-0 top-5");
    expect(shortenedOverviewConnector).not.toContain("absolute inset-x-0 top-5");
  });
});
