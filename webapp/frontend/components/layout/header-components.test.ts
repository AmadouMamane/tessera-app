import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const root = process.cwd();
const read = (path: string) => readFileSync(join(root, path), "utf8");

const appFooter = read("components/layout/app-footer.tsx");
const authControl = read("components/auth/auth-control.tsx");
const commandSearch = read("components/layout/command-search.tsx");
const demoBadge = read("components/layout/demo-badge.tsx");
const demoLauncherLink = read("components/layout/demo-launcher-link.tsx");
const ledgerIntegrity = read("components/layout/ledger-integrity.tsx");
const systemStatus = read("components/layout/system-status-pill.tsx");
const userMenu = read("components/layout/user-menu.tsx");

describe("H1 shared header components", () => {
  it("uses one tree-aware ledger wording source for the footer and system popover", () => {
    expect(ledgerIntegrity).toContain("Content integrity is not the same signal");
    expect(ledgerIntegrity).toContain("integrityForkedAttested");
    expect(ledgerIntegrity).toContain("integrityForkedPending");
    expect(appFooter).toContain("LedgerIntegrityText");
    expect(systemStatus).toContain("LedgerIntegrityText");
    expect(systemStatus).toContain("fetchAuditIntegrity");
    expect(systemStatus).toContain('queryKey: ["audit-integrity-footer"]');
    expect(systemStatus).toContain("fetchHealth");
    expect(systemStatus).toContain("modelHostingShort");
  });

  it("exposes a plan-scoped command-search input button with the shared shortcut", () => {
    expect(commandSearch).toContain('export type CommandSearchPlan = "cockpit" | "business"');
    expect(commandSearch).toContain('t("placeholder")');
    expect(commandSearch).toContain('t("shortcut")');
    expect(commandSearch).toContain('meta && event.key.toLowerCase() === "k"');
    expect(commandSearch).toContain("shell?.setPaletteOpen(true)");
  });

  it("anchors account actions, language and theme under the user menu without a role toggle", () => {
    expect(authControl).toContain("UserMenu");
    expect(userMenu).toContain('href="/login"');
    expect(userMenu).toContain("changeAccount");
    expect(userMenu).toContain("signOut");
    expect(userMenu).toContain("DropdownMenuRadioGroup");
    expect(userMenu).toContain("setTheme");
    expect(userMenu).not.toContain("auditorMode");
    expect(userMenu).not.toContain("setRole");
  });

  it("promotes the floating demo pill to the single DemoBadge component", () => {
    expect(demoBadge).toContain("fixed bottom-3 left-3");
    expect(demoBadge).toContain("demoBadge");
    expect(demoBadge).not.toContain("Tessera");
    expect(demoLauncherLink).toContain("DemoBadge");
  });
});

describe("H1 header i18n", () => {
  const requiredPaths = [
    "auth.changeAccount",
    "auth.menuLabel",
    "systemStatus.triggerLabel",
    "systemStatus.title",
    "systemStatus.environment",
    "systemStatus.model",
    "systemStatus.residence",
    "systemStatus.ledger",
    "systemStatus.residenceValue",
    "systemStatus.environmentValue.local",
    "commandSearch.placeholder",
    "commandSearch.shortcut",
    "commandSearch.scope.cockpit",
    "commandSearch.scope.business",
    "demoBadge.label",
    "demoBadge.ariaLabel",
  ];

  for (const locale of ["fr", "en", "de"]) {
    it(`defines every new H1 label in ${locale}`, () => {
      const messages = JSON.parse(read(`messages/${locale}.json`)) as Record<string, unknown>;
      for (const path of requiredPaths) {
        const value = path.split(".").reduce<unknown>((cursor, key) => {
          if (cursor && typeof cursor === "object" && key in cursor) {
            return (cursor as Record<string, unknown>)[key];
          }
          return undefined;
        }, messages);
        expect(value, `${locale}.${path}`).toEqual(expect.any(String));
      }
    });
  }

  it("keeps the demo badge product-safe: no cockpit brand in the shared demo copy", () => {
    for (const locale of ["fr", "en", "de"]) {
      const messages = JSON.parse(read(`messages/${locale}.json`)) as {
        demoBadge: Record<string, string>;
      };
      expect(Object.values(messages.demoBadge).join(" ")).not.toMatch(/Tessera|AI Control Plane/);
    }
  });
});
