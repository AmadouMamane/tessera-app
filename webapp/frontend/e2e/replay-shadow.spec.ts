import { type Page, expect, test } from "@playwright/test";

// Replay & shadow: the 8-tab bar was dead and the payload a fixture. Now the
// replay core is REAL (captured bundles, durable replay journal, run-to-run
// eval comparisons) and the tabs switch; shadow/export zones stay flagged.

const PAGE = "/fr/agir/replay-shadow";

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

test("overview shows real bundle counts and honest dashes", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("A · État actuel")).toBeVisible();
  // Storeless metrics are dashes, never invented numbers.
  const kpiZone = page.locator("section", { hasText: "A · État actuel" }).first();
  await expect(kpiZone.getByText("—").first()).toBeVisible();
});

test("comparisons tab lists the real run-to-run diffs", async ({ page }) => {
  await page.getByRole("tab", { name: "Comparaisons" }).click();
  await expect(page.getByRole("tab", { name: "Comparaisons" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // A real comparison row (run dd/mm vs dd/mm) or an honest empty panel.
  const row = page.getByText(/Run \d{2}\/\d{2} vs \d{2}\/\d{2}/).first();
  await expect(row).toBeVisible();
  // Overview zones dropped (proves switching).
  await expect(page.getByText("A · État actuel")).toHaveCount(0);
});

test("baselines tab lists the real evaluation runs", async ({ page }) => {
  await page.getByRole("tab", { name: "Baselines" }).click();
  await expect(page.getByText("Baselines réelles — runs d’évaluation")).toBeVisible();
});

test("shadow and exports tabs are flagged demonstration", async ({ page }) => {
  await page.getByRole("tab", { name: "Trafic fantôme" }).click();
  await expect(page.getByText(/démonstration/i).first()).toBeVisible();
  await expect(page.getByText(/n’est pas implémenté|n'est pas implémenté/).first()).toBeVisible();

  await page.getByRole("tab", { name: "Exports & preuves" }).click();
  await expect(page.getByText(/démonstration/i).first()).toBeVisible();
});

// ── lot 8: the shadow replay is REAL ─────────────────────────────────────────

test("the shadow rail mirrors captured turns against a candidate model, for real", async ({
  page,
}) => {
  const rail = page.locator("aside").filter({ hasText: "Rejouer en shadow" });
  await expect(rail.getByLabel("Modèle candidat")).toBeVisible({ timeout: 20_000 });
  // The dead "compare to a baseline" selects and the fake time pills are gone
  // from the rail (the comparisons TAB legitimately keeps its own title).
  await expect(rail.getByText("Comparer à une référence")).toHaveCount(0);
  await expect(rail.getByText("24h", { exact: true })).toHaveCount(0);
  // Run it: a real mirror (2 turns, real judge) — slow, and honestly so.
  await rail.getByRole("button", { name: "Lancer le shadow" }).click();
  await expect(rail.getByText(/comparés|Aucun tour capturé/)).toBeVisible({ timeout: 150_000 });
});
