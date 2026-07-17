import { type Page, expect, test } from "@playwright/test";

// Lot 5 — registre des rails temporels §6/§8: an AGIR page composes As-of
// (read the folded state at T) + Live (act now); the SURVEILLER signal
// scrubber (SR-01) does not belong there. Automations carries the first real
// As-of fold (rule states from the S1 governance journal, runs/approvals by
// timestamp); the three other AGIR pages simply lose the misplaced scrubber
// until their own folds land (lot 5b).

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
});

test("automations As-of: deep-linked ?asof folds the past, shows the mode, freezes actions", async ({
  page,
}) => {
  await page.goto("/fr/agir/automations?asof=2000-01-01T00:00:00.000Z");
  const rail = page.getByTestId("agir-rail");
  await expect(rail.getByText("Lecture à date")).toBeVisible({ timeout: 20_000 });
  await expect(rail.getByRole("button", { name: "Revenir au direct" })).toBeVisible();
  // One does not act in the past: the evaluate action is frozen…
  await expect(page.getByRole("button", { name: "Évaluer les règles maintenant" })).toBeDisabled();
  // …and so are the rule toggles, over a state folded to T (all default-enabled
  // in 2000 — no governance journal entry existed yet).
  await page.getByRole("tab", { name: "Règles" }).click();
  const switches = page.locator("#automations-tabpanel").getByRole("switch");
  await expect(switches.first()).toBeVisible();
  await expect(switches.first()).toBeDisabled();
  await expect(switches.first()).toHaveAttribute("aria-checked", "true");

  // Back to live re-enables the acting surface (URL-derived, so one click).
  await rail.getByRole("button", { name: "Revenir au direct" }).click();
  await expect(rail.getByText("Live", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Évaluer les règles maintenant" })).toBeEnabled({
    timeout: 15_000,
  });
});

test("the SURVEILLER signal scrubber is gone from every AGIR page", async ({ page }) => {
  // The scrubber's own affordance ("Voir l’historique") must not render on AGIR.
  const pages = [
    "/fr/agir/automations",
    "/fr/agir/curation-eval-set",
    "/fr/agir/incidents-playbooks",
    "/fr/agir/replay-shadow",
  ];
  for (const target of pages) {
    await page.goto(target);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("button", { name: "Voir l’historique" })).toHaveCount(0);
  }
  // Automations carries the AGIR rail (Live badge visible); the three others
  // honestly carry none until their as-of folds land (lot 5b).
  await page.goto("/fr/agir/automations");
  await expect(page.getByTestId("agir-rail")).toBeVisible({ timeout: 20_000 });
  await page.goto("/fr/agir/curation-eval-set");
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("agir-rail")).toHaveCount(0);
});
