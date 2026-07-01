import { type Page, expect, test } from "@playwright/test";

// The Amélioration dashboard shipped with a dead 5-tab bar (static <span>s, no
// activeTab state) over one always-rendered blob, plus a dead "Préparer le plan"
// button and static sensitive-action rows. This proves the real behaviour: the
// tabs switch, each shows its own real view, and the rail CTA jumps to the plan.

const PAGE = "/fr/surveiller/amelioration";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

const panel = (page: Page) => page.locator("#improvement-tabpanel");

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByRole("tab", { name: "Vue d'ensemble" })).toBeVisible();
});

test("overview tab is selected by default and shows the KPI strip + causes", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d'ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(panel(page).getByText("Gain qualité potentiel")).toBeVisible();
  await expect(panel(page).getByText("Répartition des causes")).toBeVisible();
});

test("Plan d'action tab reveals the real opportunities backlog", async ({ page }) => {
  await page.getByRole("tab", { name: "Plan d'action" }).click();
  await expect(page.getByRole("tab", { name: "Plan d'action" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(panel(page).getByText("Opportunités prioritaires")).toBeVisible();
  // The corpus-debt KPI/panel belong to overview/curation, not the plan tab.
  await expect(panel(page).getByText("Dette corpus")).toHaveCount(0);
});

test("Curation and Release tabs each expose a real CTA into the sibling page", async ({ page }) => {
  await page.getByRole("tab", { name: "Curation & eval set" }).click();
  await expect(panel(page).getByText("Ouvrir le jeu d'évaluation")).toBeVisible();

  await page.getByRole("tab", { name: "Release qualité" }).click();
  await expect(panel(page).getByText("Ouvrir le contrôle de release")).toBeVisible();
});

test("the rail 'Préparer le plan' button jumps to the Plan tab", async ({ page }) => {
  await page.getByRole("button", { name: "Préparer le plan d'action" }).click();
  await expect(page.getByRole("tab", { name: "Plan d'action" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(panel(page).getByText("Opportunités prioritaires")).toBeVisible();
});
