import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("premium cockpit contracts", () => {
  it("never renders a raw next-intl key when a dynamic catalogue entry is absent", () => {
    const source = readFileSync(join(root, "components/providers/intl-provider.tsx"), "utf8");
    expect(source).toContain("getMessageFallback");
    expect(source).toContain('=> "—"');
  });

  it("offers the shared 14-day window everywhere that owns a period control", () => {
    for (const file of [
      "components/surveiller/signal-command-bar.tsx",
      "components/overview/temporal-rail.tsx",
      "components/agent/agent-synthese.tsx",
    ]) {
      expect(readFileSync(join(root, file), "utf8")).toContain("d14");
    }
    const reliability = readFileSync(
      join(root, "components/reliability/reliability-dashboard.tsx"),
      "utf8",
    );
    expect(reliability).toContain("useWindowStore");
    expect(reliability).toContain("mirrorPeriodInUrl");
  });

  it("provides a localized route-transition skeleton that honors reduced motion", () => {
    const source = readFileSync(join(root, "app/[locale]/loading.tsx"), "utf8");
    expect(source).toContain('aria-busy="true"');
    expect(source).toContain("motion-reduce:animate-none");
  });

  it("keeps every large cockpit entity table on the premium table contract", () => {
    const screens = [
      "components/access/access-overview.tsx",
      "components/agent/agent-a-faire.tsx",
      "components/agent/agent-connaissances.tsx",
      "components/agent/agent-evaluations.tsx",
      "components/agent/agent-garde-fous.tsx",
      "components/agent/agent-historique.tsx",
      "components/agent/agent-prompts.tsx",
      "components/agent/agent-subtab-shared.tsx",
      "components/agent/evaluation-tabs.tsx",
      "components/cockpit/catalog-tab-view.tsx",
      "components/compliance/compliance-dashboard.tsx",
      "components/configurer/guardrail-catalogue.tsx",
      "components/configurer/model-catalogue.tsx",
      "components/connectors/connectors-overview.tsx",
      "components/inbox/inbox-overview.tsx",
      "components/integrations/integrations-overview.tsx",
      "components/observability/failed-board.tsx",
      "components/observability/runs-datasets.tsx",
      "components/observability/signals-table.tsx",
      "components/proofs/etat-a-date.tsx",
      "components/signals/signal-catalogue.tsx",
      "components/sources/sources-overview.tsx",
      "components/users/users-overview.tsx",
    ];

    for (const file of screens) {
      const source = readFileSync(join(root, file), "utf8");
      expect(source, file).toMatch(/data-premium-table="true"|PremiumDataTable/);
    }
  });

  it("keeps entity detail surfaces on the accessible shared drawer", () => {
    const screens = [
      "components/access/access-overview.tsx",
      "components/agent/agent-a-faire.tsx",
      "components/agent/agent-connaissances.tsx",
      "components/agent/agent-evaluations.tsx",
      "components/agent/agent-garde-fous.tsx",
      "components/agent/agent-historique.tsx",
      "components/agent/agent-prompts.tsx",
      "components/agent/agent-subtab-shared.tsx",
      "components/cockpit/catalog-tab-view.tsx",
      "components/configurer/guardrail-catalogue.tsx",
      "components/configurer/model-catalogue.tsx",
      "components/connectors/connectors-overview.tsx",
      "components/inbox/inbox-overview.tsx",
      "components/integrations/integrations-overview.tsx",
      "components/observability/observability-dashboard.tsx",
      "components/proofs/etat-a-date.tsx",
      "components/signals/signal-catalogue.tsx",
      "components/sources/sources-overview.tsx",
      "components/users/users-overview.tsx",
    ];

    for (const file of screens) {
      const source = readFileSync(join(root, file), "utf8");
      expect(source, file).toContain("@/components/cockpit/detail-drawer");
      expect(source, file).toContain("<DetailDrawer");
    }

    const drawer = readFileSync(join(root, "components/cockpit/detail-drawer.tsx"), "utf8");
    expect(drawer).toContain('aria-modal="true"');
    expect(drawer).toContain("trapFocus");
    expect(drawer).toContain('event.key === "Escape"');
    expect(drawer).toContain("z-[70]");
  });

  it("keeps the premium table typography and sticky identity column centralized", () => {
    const css = readFileSync(join(root, "app/globals.css"), "utf8");
    expect(css).toContain('[data-premium-table="true"]');
    expect(css).toContain(":is(th, td):first-child");
    expect(css).toContain("th:first-child");
    expect(css).toContain("0.65rem");
    expect(css).toContain("prefers-reduced-motion: reduce");
  });
});
