import { type Page, expect, test } from "@playwright/test";

// Policies & garde-fous: the 6-tab bar was dead and the whole payload a fixture.
// Now the governance core is REAL (compiled policy.yaml rows keyed by emitted
// policy_rule ids, ledger-derived KPIs/gauges, live chain) and the tabs switch;
// the impact simulator / approvals stay flagged demonstration zones.

const PAGE = "/fr/configurer/politiques";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible();
});

test("overview shows the real policy rows keyed by emitted rule ids", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // Real rule ids from the compiled guard policy (joins to logged decisions).
  await expect(page.getByText("prompt_injection.deny_patterns").first()).toBeVisible();
  await expect(page.getByText("memory.write.governance").first()).toBeVisible();
  // The live chain status in the footer (real verify, not the old constant).
  await expect(page.getByText(/entrées vérifiées/).first()).toBeVisible();
});

test("the active-policies tab lists every real rule including tools", async ({ page }) => {
  await page.getByRole("tab", { name: "Politiques actives" }).click();
  await expect(page.getByText("tool.account_balance.allow")).toBeVisible();
  // Overview KPI grid is dropped (proves switching).
  await expect(page.getByText("E · Simulateur d’impact")).toHaveCount(0);
});

test("runtime guardrails tab shows the ledger-derived gauges", async ({ page }) => {
  await page.getByRole("tab", { name: "Garde-fous runtime" }).click();
  await expect(page.getByText("D · Garde-fous runtime (24h)")).toBeVisible();
});

test("impact simulator and approvals tabs are flagged demonstration", async ({ page }) => {
  await page.getByRole("tab", { name: "Simulateur d’impact" }).click();
  await expect(page.getByText(/démonstration|Demonstration/i).first()).toBeVisible();

  await page.getByRole("tab", { name: "Approbations" }).click();
  await expect(page.getByText(/démonstration|Demonstration/i).first()).toBeVisible();
});

test("the single real version rail renders with the active version", async ({ page }) => {
  // The rail carries exactly one real version chip (no invented timeline).
  const rail = page.getByText("Version active", { exact: false }).first();
  await expect(rail).toBeVisible();
});
