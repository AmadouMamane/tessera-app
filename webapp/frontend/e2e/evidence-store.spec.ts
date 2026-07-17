import { type Page, expect, test } from "@playwright/test";

// The Evidence store shipped with a dead 5-tab bar (static buttons hardcoded to
// "overview"). This covers the wired behaviour: the tab bar switches content,
// the "Chaîne de preuve" tab carries the REAL verify_audit_chain zone, and the
// flagged SIEM zones stay flagged on their focused tabs.

const PAGE = "/fr/prouver/evidence-store";

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

test("overview is selected by default and comprehensive", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("État actuel")).toBeVisible();
  await expect(page.getByText("Vérification cryptographique")).toBeVisible();
});

test("the chain tab focuses on the real crypto verification", async ({ page }) => {
  await page.getByRole("tab", { name: "Chaîne de preuve" }).click();
  await expect(page.getByRole("tab", { name: "Chaîne de preuve" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("Vérification cryptographique")).toBeVisible();
  // The overview KPI zone and the SIEM pipeline are dropped (proves switching).
  await expect(page.getByText("État actuel")).toHaveCount(0);
  await expect(page.getByText("Pipeline de preuve")).toHaveCount(0);
  // The real chain algorithm is displayed (SHA-256, not the old fixture claim).
  await expect(page.getByText("SHA-256").first()).toBeVisible();
});

test("packs and destinations tabs render their flagged zones", async ({ page }) => {
  await page.getByRole("tab", { name: "Evidence packs" }).click();
  await expect(page.getByText("Evidence packs récents")).toBeVisible();
  await expect(page.getByText("Répartition des artefacts")).toBeVisible();

  await page.getByRole("tab", { name: "Destinations & rétention" }).click();
  await expect(page.getByText("Rétention & obligations")).toBeVisible();
  await expect(page.getByText("Evidence packs récents")).toHaveCount(0);
});

test("exporters tab links to the real integrations page", async ({ page }) => {
  await page.getByRole("tab", { name: "Exporteurs" }).click();
  await expect(page.getByText("Exporteurs & destinations")).toBeVisible();
  const link = page.getByRole("link", { name: /exporteurs/i }).first();
  await expect(link).toBeVisible();
});

// ── lot 7: the evidence packs are REAL (durable manifests, governed freeze) ──

test("freeze → verify → download: the evidence-pack lifecycle is real", async ({ page }) => {
  // Freeze one pack from the rail quick action (a governed, journalled act).
  await page.getByRole("button", { name: "Créer dossier de preuves" }).click();
  // The fresh payload lands: the current pack shows a real PK- id and its digest.
  const packId = page.locator("span.font-mono", { hasText: /^PK-/ }).first();
  await expect(packId).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/sha256: /).first()).toBeVisible();

  // Verify: two independent facts, displayed as such (digest + live chain).
  await page.getByRole("button", { name: "Vérifier", exact: false }).first().click();
  await expect(page.getByText(/Manifeste intègre/)).toBeVisible({ timeout: 15_000 });

  // Download: the manifest itself, verbatim.
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "Télécharger", exact: false }).first().click();
  expect((await dl).suggestedFilename()).toMatch(/^PK-.*\.json$/);
});

test("the SIEM export downloads the real normalised events", async ({ page }) => {
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter vers SIEM" }).click();
  expect((await dl).suggestedFilename()).toBe("tessera-siem-events.json");
});

test("the assembly pipeline shows only the real stages, with derived badges", async ({ page }) => {
  const pipeline = page.locator("ol").filter({ hasText: "Collecte" }).first();
  await expect(pipeline).toBeVisible();
  // The export stage is GONE (no external export exists in this build)…
  await expect(pipeline.getByText("Export", { exact: true })).toHaveCount(0);
  await expect(pipeline.getByText("Normalisation", { exact: true })).toHaveCount(0);
  // …and the per-stage badge derives from the real status (OK on a green chain).
  await expect(pipeline.getByText("OK").first()).toBeVisible();
});
