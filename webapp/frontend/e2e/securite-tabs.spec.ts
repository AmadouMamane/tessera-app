import { type Page, expect, test } from "@playwright/test";

// Sécurité & Privacy shipped as one monolithic page while the normatives
// (32-1..32-8) specify an 8-tab bar. This covers the wired behaviour: the tab
// bar switches content, each focused tab is a curated REAL view over the same
// live security signals, and the overview stays comprehensive.

const PAGE = "/fr/surveiller/securite-privacy";

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

test("overview is selected by default and comprehensive (6 zones)", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("État actuel").first()).toBeVisible();
  await expect(page.getByText("Actions recommandées")).toBeVisible();
});

test("the prompt-injection tab focuses the real firewall signals", async ({ page }) => {
  await page.getByRole("tab", { name: "Instructions malveillantes" }).click();
  await expect(page.getByRole("tab", { name: "Instructions malveillantes" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("Attaques testées (harnais)")).toBeVisible();
  await expect(page.getByText("Taux de réussite d’attaque")).toBeVisible();
  // The overview-only zones are dropped (proves switching).
  await expect(page.getByText("Actions recommandées")).toHaveCount(0);
});

test("the guard tab shows precision/recall and real governance links", async ({ page }) => {
  await page.getByRole("tab", { name: "Protections & règles" }).click();
  await expect(page.getByText("Précision du guard")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Politiques & garde-fous (registre)" }),
  ).toBeVisible();
});

test("the isolation tab carries the real cross-tenant probe", async ({ page }) => {
  await page.getByRole("tab", { name: "Séparation des environnements" }).click();
  await expect(page.getByText("Tours sondés (cross-tenant)")).toBeVisible();
  await expect(page.getByText("Cloisonnement de cette instance")).toBeVisible();
});

test("the red-team tab shows the harness campaign and failed cases", async ({ page }) => {
  await page.getByRole("tab", { name: "Tests d'attaque & efficacité" }).click();
  await expect(page.getByText("Attaques testées (harnais)")).toBeVisible();
  await expect(page.getByText("Cas échoués du domaine (harnais)")).toBeVisible();
});

test("memory and pii and tools tabs render their focused real panels", async ({ page }) => {
  await page.getByRole("tab", { name: "Mémoire & vie privée" }).click();
  await expect(page.getByText("Complétude d’effacement")).toBeVisible();

  await page.getByRole("tab", { name: "Données personnelles" }).click();
  await expect(page.getByText("Tours avec fuite PII")).toBeVisible();

  await page.getByRole("tab", { name: "Outils & droits d'accès" }).click();
  await expect(page.getByText("Outils sur-provisionnés").first()).toBeVisible();

  // Back to overview restores the comprehensive layout.
  await page.getByRole("tab", { name: "Vue d’ensemble" }).click();
  await expect(page.getByText("Actions recommandées")).toBeVisible();
});
