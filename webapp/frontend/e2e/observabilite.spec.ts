import { type Page, expect, test } from "@playwright/test";

// The REAL tail-based sampling endpoint (analyze_sampling over captured replay
// bundles) existed but no page surfaced it. It now renders on Observabilité.

const PAGE = "/fr/surveiller/observabilite";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

test("the tail-sampling panel renders real retention or an honest empty state", async ({
  page,
}) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Échantillonnage tail-based (traces)")).toBeVisible();
  // Either real counters (buffer has traces) or the honest empty state.
  const counters = page.getByText("Traces vues");
  const empty = page.getByText(/tampon replay est vide/);
  await expect(counters.or(empty).first()).toBeVisible();
});
