import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const root = process.cwd();
const read = (path: string) => readFileSync(join(root, path), "utf8");

const appFooter = read("components/layout/app-footer.tsx");
const authControl = read("components/auth/auth-control.tsx");
const appHeader = read("components/layout/app-header.tsx");
const appShell = read("components/layout/app-shell.tsx");
const creditAuroreHost = read("components/product/credit-aurore-mes-comptes-host.tsx");
const espacesPage = read("app/[locale]/espaces/page.tsx");
const cockpitAuthGate = read("components/layout/cockpit-auth-gate.tsx");
const commandSearch = read("components/layout/command-search.tsx");
const demoBadge = read("components/layout/demo-badge.tsx");
const demoLauncherLink = read("components/layout/demo-launcher-link.tsx");
const landingLauncher = read("components/landing/landing-launcher.tsx");
const ledgerIntegrity = read("components/layout/ledger-integrity.tsx");
const recouvrementProductExperience = read(
  "components/recouvrement/recouvrement-product-experience.tsx",
);
const systemStatus = read("components/layout/system-status-pill.tsx");
const sidebar = read("components/layout/sidebar.tsx");
const userMenu = read("components/layout/user-menu.tsx");

function accountMenuIsRailBound(menuSource: string, sidebarSource: string): boolean {
  return (
    sidebarSource.includes("md:w-[252px]") &&
    menuSource.includes("w-full") &&
    menuSource.includes("w-[var(--radix-dropdown-menu-trigger-width)]") &&
    menuSource.includes('side={compact ? "bottom" : "top"}') &&
    menuSource.includes('align={compact ? "end" : "start"}') &&
    !menuSource.includes("min-w-[15rem]")
  );
}

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
    expect(authControl).toContain("compact={compact}");
    expect(authControl).not.toContain("session.user.name");
    expect(userMenu).toContain('href="/login"');
    expect(userMenu).toContain("changeAccount");
    expect(userMenu).toContain("signOut");
    expect(userMenu).toContain("DropdownMenuSubContent");
    expect(userMenu).toContain("DropdownMenuRadioGroup");
    expect(userMenu).toContain("setTheme");
    expect(userMenu).not.toContain("auditorMode");
    expect(userMenu).not.toContain("setRole");
  });

  it("uses an avatar-only trigger on selection surfaces and the full role card in the cockpit", () => {
    expect(authControl).toContain('const compact = context === "optional"');
    expect(landingLauncher).toContain('<AppHeader plan="launcher" auth="optional" />');
    expect(sidebar).toContain('<AuthControl context="gated" />');
    expect(sidebar).not.toContain('<AuthControl context="gated" compact');
    expect(userMenu).toContain("compact?: boolean");
    expect(userMenu).toContain('? "h-10 w-10 justify-center rounded-full p-1"');
    expect(userMenu).toContain('side={compact ? "bottom" : "top"}');
    expect(userMenu).toContain('align={compact ? "end" : "start"}');
    expect(userMenu).toContain("{compact ? null : (");
  });

  it("keeps the connection card and its main menu inside the expanded sidebar", () => {
    expect(accountMenuIsRailBound(userMenu, sidebar)).toBe(true);

    const overflowRegression = userMenu.replace(
      "w-[var(--radix-dropdown-menu-trigger-width)]",
      "min-w-[15rem]",
    );
    expect(accountMenuIsRailBound(overflowRegression, sidebar)).toBe(false);
  });

  it("does not repeat the signed-in identity inside the main account menu", () => {
    const accountEntry = userMenu.match(
      /<DropdownMenuSubTrigger className="gap-2 rounded-lg">[\s\S]*?<\/DropdownMenuSubTrigger>/,
    )?.[0];

    expect(accountEntry).toContain('t("accounts")');
    expect(accountEntry).not.toContain("{roleLabel}");
    expect(accountEntry).not.toContain("initials(roleLabel)");
    expect(userMenu).not.toContain("accountIdentifier");
    expect(userMenu).not.toContain("name?: string");

    const repeatedIdentity = accountEntry?.replace('{t("accounts")}', "{roleLabel}");
    expect(repeatedIdentity).toContain("{roleLabel}");
  });

  it("promotes the floating demo pill to the single DemoBadge component", () => {
    expect(demoBadge).toContain("fixed bottom-3 left-3");
    expect(demoBadge).toContain("demoBadge");
    expect(demoBadge).not.toContain("Tessera");
    expect(demoLauncherLink).toContain("DemoBadge");
  });
});

describe("H2 cockpit header contract", () => {
  // 88px, not 56: the same rule height as the launcher's row and the sidebar's brand block,
  // so the top rule is one continuous line across the rail's edge.
  it("renders the cockpit header as an 88px three-zone shell", () => {
    expect(appHeader).toContain("grid min-h-[5.5rem]");
    expect(appHeader).toContain("grid-cols-[minmax(0,1fr)_auto]");
    expect(appHeader).toContain(
      "md:grid-cols-[minmax(10rem,1fr)_minmax(15rem,28rem)_minmax(10rem,1fr)]",
    );
    expect(appHeader).toContain('<CommandSearch plan="cockpit"');
    expect(appHeader).toContain("<SystemStatusPill");
    // The bell is a component now, not an icon with a frozen label: its accessible name
    // carries the real notification count (see chrome-honesty.test.ts). Asserting
    // `label="Notifications"` here would pin the static label the chrome lot removed.
    expect(appHeader).toContain("<NotificationsBell />");
    // The "?" is a menu now, and its label is localized: `label="Aide"` was French hardcoded
    // into the header. Its first item is the door to /comprendre.
    expect(appHeader).toContain("<HelpMenu />");
    expect(appHeader).toContain('<Link href="/comprendre">');
  });

  it("keeps cockpit preferences and identity anchored in the sidebar, not the header", () => {
    expect(appShell).toContain("<CockpitAuthGate>");
    expect(appShell).toContain("description={description}");
    expect(appShell).not.toContain("pageSubtitle={description}");
    expect(cockpitAuthGate).toContain(
      "router.replace(`/login?next=${encodeURIComponent(pathname)}`)",
    );
    expect(cockpitAuthGate).toContain('role === "admin"');
    expect(cockpitAuthGate).toContain('role === "auditor"');
    expect(cockpitAuthGate).toContain('role === "superadmin"');
    expect(appHeader).toContain("OperatorProductMenu");
    expect(appHeader).toContain('href="/espaces"');
    expect(appHeader).toContain('href="/produit"');
    expect(appHeader).not.toContain("ModelBadge");
    expect(appHeader).not.toContain("StatusBadge");
  });

  it("makes the system status popover visibly clickable and keeps the page subtitle in header", () => {
    expect(appHeader).toContain("description={description}");
    expect(appHeader).toContain("{description}");
    expect(systemStatus).toContain("cursor-pointer");
    expect(systemStatus).toContain("ChevronDown");
  });
});

describe("H3 launcher and spaces inheritance", () => {
  it("uses the shared demo badge instead of local demo pills", () => {
    expect(authControl).not.toContain("FlaskConical");
    expect(landingLauncher).toContain("<DemoBadge");
    expect(landingLauncher).not.toContain('t("demoBadge")');
    expect(espacesPage).toContain("<DemoBadge");
    expect(espacesPage).not.toContain('t("demoBadge")');
  });

  it("keeps language and theme preferences inside the shared user menu", () => {
    expect(appHeader).not.toContain("LanguageSwitcher");
    expect(appHeader).not.toContain("ThemeToggle");
    expect(appHeader).toContain("<AuthControl context={authContext} />");
    expect(userMenu).toContain("setTheme");
    expect(userMenu).toContain("DropdownMenuRadioGroup");
  });
});

describe("H4 product-surface header contract", () => {
  it("keeps the customer product stacked bars while the floating demo link uses the long wording", () => {
    expect(creditAuroreHost).toContain("DemoStrip");
    expect(creditAuroreHost).toContain("demo-strip");
    expect(creditAuroreHost).toContain("UtilityBar");
    expect(creditAuroreHost).toContain("Espace clients professionnels");
    // Lexicon (docs/design/ui-contract.md §Annexe): "Tessera" is cockpit-reserved, never on a
    // product surface. The old assertion PINNED the forbidden "Démo Tessera" kicker — a
    // pre-lexicon leftover (audit P0.5). Replaced by the guard that keeps this host clean.
    expect(creditAuroreHost).not.toContain("Tessera");
    expect(demoLauncherLink).toContain('t("demoExplore")');
  });

  it("keeps collections search read-only and uses the long floating demo link", () => {
    expect(recouvrementProductExperience).toContain("DemoLauncherLink floating");
    expect(recouvrementProductExperience).toContain("readOnly");
    expect(recouvrementProductExperience).not.toContain("dossierSearchRef");
    expect(recouvrementProductExperience).not.toContain('aria-keyshortcuts="Meta+K Control+K"');
    expect(recouvrementProductExperience).not.toContain("⌘K");
    // Lot 9: the notification badge derives from the REAL open-case counter —
    // the contract pins the derived value and its locale-owned template, never a hardcoded count.
    expect(recouvrementProductExperience).toContain("copy.ui.notificationsAria.replace(");
    expect(recouvrementProductExperience).toContain("String(counters?.open ?? 0)");
    expect(recouvrementProductExperience).toContain("min-h-[69px]");
  });
});

describe("H1 header i18n", () => {
  const requiredPaths = [
    "auth.changeAccount",
    "auth.addAccount",
    "auth.accounts",
    "auth.currentAccount",
    "auth.operatorAccount",
    "auth.customize",
    "auth.profile",
    "auth.settings",
    "auth.help",
    "auth.understand",
    "auth.detailedGuide",
    "auth.preferences",
    "auth.menuLabel",
    "auth.sessionActive",
    "app.clientSpace",
    "app.businessMenu",
    "app.demoExplore",
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
