import { type Page, expect, test } from "@playwright/test";

const EMPTY_FR = [
  "— aucun signal reçu · la flotte n'a encore rien publié",
  "— aucun échange aujourd'hui",
  "— aucun verdict · aucune évaluation enregistrée",
  "— chaîne non vérifiée depuis le démarrage",
] as const;

const LOCALES = [
  {
    locale: "fr",
    title: "Comprendre Tessera — en 3 minutes",
    fiction: "Crédit Aurore est fictive — c'est une démonstration.",
  },
  {
    locale: "en",
    title: "Understand Tessera — in 3 minutes",
    fiction: "Crédit Aurore is fictional — this is a demonstration.",
  },
  {
    locale: "de",
    title: "Tessera verstehen — in 3 Minuten",
    fiction: "Crédit Aurore ist fiktiv — dies ist eine Demonstration.",
  },
] as const;

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

test("a virgin read shows four dashes with their exact reasons", async ({ page }) => {
  await page.route("**/api/comprendre", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ available: false }),
    });
  });

  await page.goto("/fr/comprendre");
  for (const reason of EMPTY_FR)
    await expect(page.getByText(reason, { exact: true })).toBeVisible();
  await expect(page.locator('[data-testid^="comprendre-live-tile-"]')).toHaveCount(4);
  await page
    .getByTestId("comprendre-live-section")
    .screenshot({ path: "/tmp/tessera-comprendre-v2-empty-fr.png" });
});

test("the five proof links resolve through their real locale routes", async ({ page }) => {
  test.setTimeout(90_000);
  await login(page);
  await page.goto("/fr/comprendre");
  const proofLinks = page.locator('[data-proof-link="true"]');
  await expect(proofLinks).toHaveCount(5);
  const hrefs = await proofLinks.evaluateAll((links) =>
    links.map((link) => link.getAttribute("href")),
  );
  expect(hrefs).toEqual([
    "/fr/recouvrement",
    "/fr/agents",
    "/fr/surveiller",
    "/fr/eval",
    "/fr/prouver",
  ]);

  for (const href of hrefs) {
    expect(href).not.toBeNull();
    const response = await page.goto(href as string);
    expect(response?.ok(), href ?? "missing href").toBe(true);
    await expect(page.locator("body")).not.toContainText(/404|page introuvable/i);
  }
});

for (const { locale, title, fiction } of LOCALES) {
  test(`${locale} renders the closed title and fiction disclosure`, async ({ page }) => {
    const response = await page.goto(`/${locale}/comprendre`);
    expect(response?.ok()).toBe(true);
    await expect(
      page.getByRole("main").getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await expect(page.getByText(fiction, { exact: false })).toBeVisible();
    await expect(
      page.getByRole("link", { name: /lecture détaillée|detailed reading|ausführliche Lektüre/i }),
    ).toHaveAttribute("href", `/${locale}/comprendre/en-detail`);
    await page.screenshot({ path: `/tmp/tessera-comprendre-v2-${locale}.png` });
  });
}
