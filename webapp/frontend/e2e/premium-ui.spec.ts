import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const ROUTES = [
  "/fr/surveiller/vue-ensemble",
  "/fr/surveiller/qualite-ia",
  "/fr/a-traiter",
  "/fr/agir/incidents-playbooks",
  "/fr/configurer/politiques",
] as const;

async function login(page: Page): Promise<void> {
  await page.goto("/fr/login");
  await page.fill("#login-username", process.env.E2E_USER ?? "admin");
  await page.fill("#login-password", process.env.E2E_PASSWORD ?? "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

async function settle(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  if (new URL(page.url()).pathname.endsWith("/configurer/politiques")) {
    await page.getByRole("tablist").waitFor({ state: "visible", timeout: 20_000 });
  }
  await page.waitForTimeout(800);
  const coachmark = page.getByTestId("contextual-help-coachmark");
  if (await coachmark.isVisible().catch(() => false)) {
    await coachmark.getByRole("button").click();
  }
}

async function waitForRenderedContent(page: Page): Promise<void> {
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, { timeout: 20_000 });
}

test.describe("premium UI gate", () => {
  test.beforeEach(async ({ page }) => login(page));

  test("critical cockpit routes have no serious automated WCAG violation", async ({ page }) => {
    for (const route of ROUTES) {
      await page.goto(route);
      await settle(page);
      const results = await new AxeBuilder({ page })
        .include("main")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze();
      const blocking = results.violations.filter(
        (violation) => violation.impact === "critical" || violation.impact === "serious",
      );
      expect(blocking, `${route}: ${blocking.map((item) => item.id).join(", ")}`).toEqual([]);
    }
  });

  test("mobile shell uses the full viewport and card tables do not overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const route of ROUTES) {
      await page.goto(route);
      await settle(page);
      const geometry = await page.evaluate(() => {
        const main = document.querySelector("main");
        const content = document.querySelector<HTMLElement>("[data-shell-content]");
        const tables = Array.from(
          document.querySelectorAll<HTMLElement>('table[data-mobile-table="cards"]'),
        );
        const contentRight = content?.getBoundingClientRect().right ?? 0;
        const overflowers = content
          ? Array.from(content.querySelectorAll<HTMLElement>("*"))
              .filter((element) => {
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.right > contentRight + 1;
              })
              .slice(0, 8)
              .map((element) => ({
                tag: element.tagName.toLowerCase(),
                over: Math.round(element.getBoundingClientRect().right - contentRight),
                className: element.className.toString().slice(0, 120),
              }))
          : [];
        const touchTargets = Array.from(
          document.querySelectorAll<HTMLElement>(
            '[data-shell-content] button, [data-shell-content] [role="button"], header button, nav button, nav a',
          ),
        ).filter((element) => {
          const rect = element.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0 && rect.height < 43.5;
        });
        return {
          mainWidth: main?.getBoundingClientRect().width ?? 0,
          contentOverflow: content ? content.scrollWidth - content.clientWidth : 0,
          overflowers,
          overflowingTables: tables.filter((table) => table.scrollWidth > table.clientWidth + 1)
            .length,
          undersizedTargets: touchTargets.length,
        };
      });
      expect(geometry.mainWidth, route).toBeGreaterThanOrEqual(389);
      expect(
        geometry.contentOverflow,
        `${route}: ${JSON.stringify(geometry.overflowers)}`,
      ).toBeLessThanOrEqual(1);
      expect(geometry.overflowingTables, route).toBe(0);
      expect(geometry.undersizedTargets, route).toBe(0);
    }
  });

  test("contextual help never switches Radix Tooltip control mode", async ({ page }) => {
    const warnings: string[] = [];
    page.on("console", (message) => {
      const text = message.text();
      if (/controlled.*uncontrolled|uncontrolled.*controlled/i.test(text)) warnings.push(text);
    });
    await page.goto("/fr/configurer/politiques");
    await settle(page);
    expect(warnings).toEqual([]);
  });

  test("desktop overview visual baseline", async ({ page }) => {
    await page.setViewportSize({ width: 1512, height: 982 });
    await page.goto("/fr/surveiller/vue-ensemble");
    await settle(page);
    await waitForRenderedContent(page);
    await expect(page).toHaveScreenshot("overview-desktop.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("mobile overview and policies visual baselines", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/fr/surveiller/vue-ensemble");
    await settle(page);
    await waitForRenderedContent(page);
    await expect(page).toHaveScreenshot("overview-mobile.png", {
      animations: "disabled",
      caret: "hide",
    });
    await page.goto("/fr/configurer/politiques");
    await settle(page);
    await expect(page).toHaveScreenshot("policies-mobile.png", {
      animations: "disabled",
      caret: "hide",
    });
  });
});
