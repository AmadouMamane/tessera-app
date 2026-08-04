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
    // The claim is "the expanded sidebar is 252px wide", not "it expands at md".
    // The breakpoint moved md→lg on 2026-08-01 (a 252px panel on a 768px tablet
    // was a third of the screen); pinning the prefix made this assertion fail for
    // a change it has no opinion about.
    /\b(?:sm|md|lg|xl|2xl):w-\[252px\]/.test(sidebarSource) &&
    menuSource.includes("w-full") &&
    menuSource.includes("w-[var(--radix-dropdown-menu-trigger-width)]") &&
    menuSource.includes('side={compact ? "bottom" : "top"}') &&
    menuSource.includes('align={compact ? "end" : "start"}') &&
    !menuSource.includes("min-w-[15rem]")
  );
}

describe("H1 shared header components", () => {
  it("uses one tree-aware ledger wording source for the footer and system tray", () => {
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
    expect(commandSearch).toContain("compact?: boolean");
    expect(commandSearch).toContain('t("placeholder")');
    expect(commandSearch).toContain('t("shortcut")');
    expect(commandSearch).toContain('meta && event.key.toLowerCase() === "k"');
    expect(commandSearch).toContain("shell?.setPaletteOpen(true)");
    expect(commandSearch).toContain('compact ? "h-[18px] w-[18px]"');
    expect(commandSearch).toContain('"inline-flex h-9 w-9 items-center justify-center');
    expect(commandSearch).toContain("strokeWidth={1.75}");
    expect(commandSearch).toContain("<TooltipContent");
    expect(commandSearch).toContain('t("tooltip", { shortcut: t("shortcut") })');
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

  it("keeps account avatars visually neutral instead of reusing the operational green", () => {
    const avatarClass = userMenu.match(/const IDENTITY_AVATAR_CLASS =\s*\n?\s*"([^"]+)"/)?.[1];

    expect(avatarClass).toContain("bg-[var(--tessera-surface-elevated)]");
    expect(avatarClass).toContain("border-cyan-300/30");
    expect(userMenu).not.toContain("tessera-green");
    expect(userMenu.match(/IDENTITY_AVATAR_CLASS/g)).toHaveLength(3);

    const signalMutation = avatarClass?.replace(
      "bg-[var(--tessera-surface-elevated)]",
      "bg-[var(--tessera-green)]",
    );
    expect(signalMutation).toContain("tessera-green");
  });

  it("uses the cockpit brand as a localized route back to the home page", () => {
    const brandHeader = sidebar.match(/function BrandHeader[\s\S]*?function IdentityBlock/)?.[0];

    expect(brandHeader).toContain('const t = useTranslations("nav")');
    expect(brandHeader).toContain('href="/"');
    expect(brandHeader).toContain('aria-label={t("rail.home")}');
    expect(brandHeader).toContain('title={t("rail.home")}');

    const inertBrand = brandHeader?.replace('href="/"', 'href="/surveiller/vue-ensemble"');
    expect(inertBrand).not.toContain('href="/"');
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
  it("renders the cockpit header as an 88px two-zone shell with one control dock", () => {
    expect(appHeader).toContain("grid min-h-[5.5rem]");
    expect(appHeader).toContain("grid-cols-[minmax(0,1fr)_auto]");
    expect(appHeader).not.toContain(
      "md:grid-cols-[minmax(10rem,1fr)_minmax(15rem,28rem)_minmax(10rem,1fr)]",
    );
    expect(appHeader).toContain('data-testid="cockpit-control-dock"');
    expect(appHeader).toContain('<CommandSearch plan="cockpit" compact />');
    expect(appHeader).toContain("<SystemStatusTrigger");
    expect(appHeader).toContain("<SystemStatusPanel");
    expect(appHeader).toContain('const HEADER_TOOL_ICON_CLASS = "h-[18px] w-[18px]"');
    expect(appHeader).toContain('className="flex h-11 items-center gap-1"');
    expect(appHeader).not.toContain('className="flex h-11 items-center gap-1 rounded-xl border');
    expect(appHeader).not.toContain("bg-[var(--tessera-surface)]/60");
    expect(appHeader).not.toContain("border-cyan-400/20");
    expect(appHeader).not.toContain("bg-emerald-400/10");
    expect(appHeader).not.toContain("data-[state=open]:bg-[var(--tessera-muted)]");
    expect(appHeader).toContain("data-[state=open]:after:bg-[var(--tessera-green)]");
    expect(appHeader).not.toContain('className="mx-0.5 h-5 w-px');
    // The bell is a component now, not an icon with a frozen label: its accessible name
    // carries the real notification count (see chrome-honesty.test.ts). Asserting
    // `label="Notifications"` here would pin the static label the chrome lot removed.
    expect(appHeader).toContain("<NotificationsTrigger");
    expect(appHeader).toContain("<HelpLink");
    expect(appHeader).toContain("<TooltipContent");
    expect(appHeader).toContain("contextualHelpHref(pathname, searchParams.toString())");
    expect(appHeader).toContain("hasContextualHelp(pathname)");
    expect(appHeader).toContain("href={href}");
    expect(appHeader).toContain("contextualHelpCoachmarkKey(pathname)");
    expect(appHeader).toContain('window.localStorage.getItem(storageKey) !== "seen"');
    expect(appHeader).toContain('window.localStorage.setItem(storageKey, "seen")');
    expect(appHeader).toContain('data-testid="contextual-help-coachmark"');
    expect(appHeader).toContain("contextual && coachmarkVisible && !suppressCoachmark");

    const coachmark = appHeader.match(
      /<aside[\s\S]*?data-testid="contextual-help-coachmark"[\s\S]*?<\/aside>/,
    )?.[0];
    expect(coachmark).toContain("border-cyan-300/45 border-l");
    expect(coachmark).not.toContain("shadow");
    expect(coachmark).not.toContain("rounded-");
    expect(coachmark).not.toContain("border-r");
    expect(coachmark).not.toContain("border-b");
  });

  it("groups actionable facts by their real destination and uses a dot, not a fake unread count", () => {
    expect(appHeader).toContain("groupNotifications(items)");
    expect(appHeader).toContain('href === "/a-traiter"');
    expect(appHeader).toContain('href === "/a-faire"');
    expect(appHeader).toContain('href === "/surveiller/observabilite"');
    expect(appHeader).toContain('href === "/prouver/etat-a-date"');
    expect(appHeader).toContain('item.id.startsWith("queue:pending:")');
    expect(appHeader).toContain('item.id.startsWith("queue:overdue:")');
    expect(appHeader).toContain("count: pending?.count ?? undefined");
    expect(appHeader).toContain("overdueCount: overdue?.count ?? 0");
    expect(appHeader).not.toMatch(/item\.label\.(match|includes|startsWith)/);
    expect(appHeader).toContain('className="absolute right-1 top-1 h-2 w-2');
    expect(appHeader).not.toContain("{items.length}\n            </span>");

    const wrongCountLeg = appHeader.replace(
      "count: pending?.count ?? undefined",
      "count: overdue?.count ?? undefined",
    );
    expect(wrongCountLeg).not.toContain("count: pending?.count ?? undefined");
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
    expect(appHeader).toContain("OperatorProductTrigger");
    expect(appHeader).toContain("OperatorProductPanel");
    expect(appHeader).toContain('href="/espaces"');
    expect(appHeader).toContain('href="/produit"');
    expect(appHeader).not.toContain("ModelBadge");
    expect(appHeader).not.toContain("StatusBadge");
  });

  it("uses one attached shadowless tray for spaces, status and notifications", () => {
    expect(appHeader).toContain("description={description}");
    expect(appHeader).toContain("{description}");
    expect(appHeader).toContain('type CockpitPanel = "spaces" | "status" | "notifications"');
    expect(appHeader).toContain("activePanel ===");
    expect(appHeader).toContain("id={COCKPIT_TRAY_ID}");
    expect(appHeader).toContain('data-testid="cockpit-control-tray"');
    expect(appHeader).toContain("top-[calc(100%+1.375rem)]");
    expect(appHeader).toContain("border-[var(--tessera-border)] border-l");
    expect(appHeader).not.toContain("rounded-b-xl");
    expect(appHeader).not.toContain("border-x border-b");
    expect(appHeader).toContain("bg-[var(--tessera-bg)]");
    expect(appHeader).not.toContain("HEADER_PANEL_CLASS");
    const tray = appHeader.match(
      /<section[\s\S]*?data-testid="cockpit-control-tray"[\s\S]*?<\/section>/,
    )?.[0];
    expect(tray).not.toContain("shadow");
    expect(tray).not.toContain("rounded-2xl");
    expect(tray).not.toContain("border-t");
    expect(systemStatus).not.toContain("@radix-ui/react-popover");
    expect(systemStatus).not.toContain("Popover.Root");
    expect(systemStatus).toContain("useSystemStatusState");
    expect(systemStatus).toContain("SystemStatusTrigger");
    expect(systemStatus).toContain("SystemStatusPanel");
    expect(systemStatus).toContain("cursor-pointer");
    expect(systemStatus).toContain("Activity");
    expect(systemStatus).toContain('className="h-[18px] w-[18px]"');
    expect(systemStatus).not.toContain("ChevronDown");
    expect(systemStatus).toContain('t("description")');
    expect(systemStatus).not.toContain("bg-green-500/10");
    expect(systemStatus).not.toContain("data-[state=open]:bg-[var(--tessera-muted)]");
    expect(systemStatus).toContain("data-[state=open]:after:bg-[var(--tessera-green)]");
    expect(systemStatus).toContain("strokeWidth={1.75}");
    expect(systemStatus).not.toContain("ServerCog");
    expect(systemStatus).not.toContain("icon={");
    expect(systemStatus).not.toContain("min-[1280px]:w-auto");
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
    // Lot 9: the notification badge derives from the REAL open-case counter. While the
    // counter is unavailable, assistive text stays generic rather than inventing zero cases.
    //
    // The condition used to be pinned as the literal `"counters\n                    ?"` —
    // an indentation, asserted as a contract. It broke on the 2026-08-04 fix that made the
    // accessible name use the BADGE's own condition (`counters.open > 0`) instead of merely
    // `counters`: with a real counter reading zero, the badge showed nothing while the
    // aria-label announced "0 notification". Pin the two conditions being IDENTICAL, which is
    // the actual contract, and let the formatter own the whitespace.
    expect(recouvrementProductExperience).toContain("copy.ui.notificationsAria.replace(");
    expect(recouvrementProductExperience).toContain("String(counters.open)");
    expect(recouvrementProductExperience).not.toContain("String(counters?.open ?? 0)");
    const ariaGuards = recouvrementProductExperience.match(/counters && counters\.open > 0/g) ?? [];
    expect(
      ariaGuards.length,
      "the aria-label and the visual badge must share one condition, so a zero count cannot be " +
        "announced to a screen reader while nothing is drawn for everyone else",
    ).toBeGreaterThanOrEqual(2);
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
    "app.spacesMenu.title",
    "app.spacesMenu.description",
    "app.spacesMenu.businessDescription",
    "app.spacesMenu.clientDescription",
    "app.actionCenter.title",
    "app.actionCenter.description",
    "app.actionCenter.deadline.all",
    "app.actionCenter.deadline.some",
    "app.actionCenter.deadline.none",
    "app.actionCenter.groups.validations",
    "app.actionCenter.groups.evaluations",
    "app.actionCenter.groups.agents",
    "app.actionCenter.groups.proofs",
    "app.actionCenter.groups.other",
    "systemStatus.triggerLabel",
    "systemStatus.triggerWithStatus",
    "systemStatus.title",
    "systemStatus.description",
    "comprendre.helpThisPage",
    "comprendre.coachmark.title",
    "comprendre.coachmark.body",
    "comprendre.coachmark.open",
    "comprendre.coachmark.dismiss",
    "systemStatus.environment",
    "systemStatus.model",
    "systemStatus.residence",
    "systemStatus.ledger",
    "systemStatus.residenceValue",
    "systemStatus.environmentValue.local",
    "commandSearch.placeholder",
    "commandSearch.shortcut",
    "commandSearch.tooltip",
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
