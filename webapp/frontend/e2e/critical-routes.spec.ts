import { type Page, expect, test } from "@playwright/test";

/**
 * Commercial-demo smoke: the routes a buyer or reviewer reaches first must stay usable.
 *
 * This deliberately checks visible native-language business copy, not just HTTP 200. A route
 * can answer successfully while rendering the wrong locale, a logged-out shell, or a partial
 * French fallback. Those are demo failures even when the web server is technically healthy.
 */

const LOCALES = [
  { locale: "fr", understand: "Comprendre Tessera" },
  { locale: "en", understand: "Understand Tessera" },
  { locale: "de", understand: "Tessera verstehen" },
] as const;

const COLLECTIONS = [
  {
    locale: "en",
    greeting: "Hello Julie,",
    queue: "Your queue for today is ready.",
    assistant: "Open full assistant",
    forbidden: /Bonjour Julie|Votre file du jour|Ouvrir l'assistant complet/,
  },
  {
    locale: "de",
    greeting: "Guten Tag Julie,",
    queue: "Ihre heutige Warteschlange ist bereit.",
    assistant: "Vollständigen Assistenten öffnen",
    forbidden: /Bonjour Julie|Votre file du jour|Ouvrir l'assistant complet/,
  },
] as const;

async function loginCollections(page: Page, locale: string) {
  await page.goto(`/${locale}/login`);
  await page.fill("#login-username", "collections");
  await page.fill("#login-password", "tessera-collections");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
  await page.goto(`/${locale}/recouvrement`);
}

test.describe("critical public routes", () => {
  for (const { locale, understand } of LOCALES) {
    test(`${locale}: launcher and understanding page render in the requested locale`, async ({
      page,
    }) => {
      const launcher = await page.goto(`/${locale}`);
      expect(launcher?.ok(), `GET /${locale}`).toBe(true);
      await expect(page).toHaveURL(new RegExp(`/${locale}/select-space$`));

      const comprendre = await page.goto(`/${locale}/comprendre`);
      expect(comprendre?.ok(), `GET /${locale}/comprendre`).toBe(true);
      await expect(page.getByRole("heading", { name: understand, exact: true })).toBeVisible();
    });
  }
});

test.describe("critical collections journey", () => {
  for (const { locale, greeting, queue, assistant, forbidden } of COLLECTIONS) {
    test(`${locale}: collections RBAC opens a fully native business surface`, async ({ page }) => {
      await loginCollections(page, locale);
      await expect(page.getByText(greeting, { exact: true })).toBeVisible({ timeout: 20_000 });
      await expect(page.getByText(queue, { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: assistant, exact: true })).toBeVisible();
      await expect(page.locator("body")).not.toContainText(forbidden);
      await expect(page.getByText(/Tessera/i)).toHaveCount(0);
    });
  }
});
