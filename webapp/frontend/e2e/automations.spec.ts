import { type Page, expect, test } from "@playwright/test";

// Automations: the 6-tab bar was dead and the payload a fixture. Now the rule/
// execution core is REAL (code-defined rules evaluated against the owned
// stores, durable toggles, a journalled evaluate action) and the tabs switch;
// the approval-queue/savings zones stay flagged demonstration.

const PAGE = "/fr/agir/automations";

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
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({
    timeout: 20_000,
  });
});

test("overview shows the real rule catalogue with honest dashes", async ({ page }) => {
  await expect(page.getByText("A · Catalogue d’automations")).toBeVisible();
  // A real code-defined rule is listed.
  await expect(page.getByText("Gel release sur gate FAIL").first()).toBeVisible();
  // Storeless KPIs render dashes, never invented numbers.
  const kpiZone = page.locator("section", { hasText: "État actuel" }).first();
  await expect(kpiZone.getByText("—").first()).toBeVisible();
});

test("evaluate-now journals a real evaluation into executions", async ({ page }) => {
  await page.getByRole("button", { name: "Évaluer les règles maintenant" }).click();
  // The mutation returns the fresh payload; switch to the executions tab.
  await page.getByRole("tab", { name: "Exécutions" }).click();
  await expect(page.getByText("E · Journal d’exécution récent")).toBeVisible();
  // The journal carries a real observed value (e.g. "N denies / 24h").
  await expect(page.getByText(/denies \/ 24h|pending|turns </).first()).toBeVisible({
    timeout: 15_000,
  });
});

test("a rule toggle mutates the durable state and flips the badge", async ({ page }) => {
  await page.getByRole("tab", { name: "Règles" }).click();
  const rows = page.locator("#automations-tabpanel tbody tr");
  await expect(rows.first()).toBeVisible();
  const toggle = rows.first().getByRole("switch");
  const before = await toggle.getAttribute("aria-checked");
  await toggle.click();
  await expect(rows.first().getByRole("switch")).toHaveAttribute(
    "aria-checked",
    before === "true" ? "false" : "true",
    { timeout: 15_000 },
  );
  // Restore the durable state.
  await rows.first().getByRole("switch").click();
  await expect(rows.first().getByRole("switch")).toHaveAttribute("aria-checked", before ?? "true", {
    timeout: 15_000,
  });
});

test("the approvals queue is real: empty state or actionable rows; savings stays flagged demo", async ({
  page,
}) => {
  // The old "File d’attente" tab duplicated the approvals content; lot 1b removed it.
  await expect(page.getByRole("tab", { name: "File d’attente" })).toHaveCount(0);
  await page.getByRole("tab", { name: "Approbations" }).click();
  // Savings keeps its demonstration notice; the queue itself is REAL now (lot 4):
  // durable requests opened by fired approb-mode rules, with governed decisions.
  await expect(page.getByText(/démonstration/i).first()).toBeVisible();
  const approve = page.locator("#automations-tabpanel").getByRole("button", { name: "Approuver" });
  if ((await approve.count()) === 0) {
    // Honest empty state — and it no longer claims the queue is a demo subsystem.
    await expect(page.getByText(/Aucune approbation en attente/).first()).toBeVisible();
    await expect(page.getByText(/mode approbation/).first()).toBeVisible();
  } else {
    // Real pending requests carry ENABLED decisions (the dead disabled button is gone).
    await expect(approve.first()).toBeEnabled();
    await expect(
      page.locator("#automations-tabpanel").getByRole("button", { name: "Rejeter" }).first(),
    ).toBeEnabled();
  }
});

test("bulk suspend/activate: one governed act flips every rule switch, then restores", async ({
  page,
}) => {
  // Suspend ALL rules from the overview rail quick actions.
  await page.getByRole("button", { name: "Suspendre toutes les règles" }).click();
  await page.getByRole("tab", { name: "Règles" }).click();
  const switches = page.locator("#automations-tabpanel").getByRole("switch");
  await expect(switches.first()).toBeVisible();
  const n = await switches.count();
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    await expect(switches.nth(i)).toHaveAttribute("aria-checked", "false", { timeout: 15_000 });
  }
  // Restore the canonical durable state: every rule enabled.
  await page.getByRole("tab", { name: "Vue d’ensemble" }).click();
  await page.getByRole("button", { name: "Activer toutes les règles" }).click();
  await page.getByRole("tab", { name: "Règles" }).click();
  for (let i = 0; i < n; i++) {
    await expect(page.locator("#automations-tabpanel").getByRole("switch").nth(i)).toHaveAttribute(
      "aria-checked",
      "true",
      { timeout: 15_000 },
    );
  }
});
