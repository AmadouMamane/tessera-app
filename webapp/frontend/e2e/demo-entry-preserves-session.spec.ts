import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { type Page, expect, test } from "@playwright/test";

// Bug of 2026-07-18: superadmin logs in, clicks « Entrer dans le cockpit » on
// the demo launcher, and a demo shortcut silently replaces the session with the
// seeded admin account. The launcher now only links to the guarded cockpit:
// authorized sessions enter unchanged; anonymous visitors are sent to login.

test.use({ viewport: { width: 1672, height: 1000 } });

/** The superadmin account exists only when this env var is set — read it from the
 * running stack's own env file so the test uses the real secret, never a guess. */
function superadminPassword(): string {
  const env = readFileSync(resolve(__dirname, "..", ".env.local"), "utf8");
  const password = env.match(/^TESSERA_AUTH_SUPERADMIN_PASSWORD=(.+)$/m)?.[1]?.trim();
  if (!password) {
    throw new Error("TESSERA_AUTH_SUPERADMIN_PASSWORD missing from webapp/frontend/.env.local");
  }
  return password;
}

async function login(page: Page, username: string, password: string) {
  await page.goto("/fr/login");
  await page.fill("#login-username", username);
  await page.fill("#login-password", password);
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

// The witness is the SESSION ITSELF (next-auth's own endpoint, same cookie jar
// as the page) — not a display element that could lag or vary per layout.
async function sessionRole(page: Page): Promise<string | null> {
  const res = await page.request.get("/api/auth/session");
  const body = (await res.json()) as { user?: { role?: string } } | null;
  return body?.user?.role ?? null;
}

// The header chip displays the session's role label — the human-visible half of
// the same fact, asserted where the layout carries it (the cockpit shell).
const roleChip = (page: Page, label: string) =>
  page.getByRole("button", { name: new RegExp(label) });

test("the launcher's cockpit CTA keeps a superadmin session (never the seeded admin)", async ({
  page,
}) => {
  await login(page, "superadmin", superadminPassword());
  await page.goto("/fr/select-space");
  await page.getByRole("link", { name: "Entrer dans le cockpit" }).click();
  await page.waitForURL(/\/surveiller\/vue-ensemble/, { timeout: 20_000 });
  expect(await sessionRole(page)).toBe("superadmin");
  await expect(roleChip(page, "Super-administrateur")).toBeVisible({ timeout: 20_000 });
});

test("the espaces recouvrement card keeps a superadmin session (supervising, not demoted)", async ({
  page,
}) => {
  await login(page, "superadmin", superadminPassword());
  await page.goto("/fr/espaces");
  // The recouvrement surface card navigates through the real route guard; it
  // never re-logs the session as the seeded `collections` account.
  await page.getByRole("link", { name: "Espace recouvrement — Ouvrir" }).click();
  await page.waitForURL(/\/recouvrement/, { timeout: 20_000 });
  expect(await sessionRole(page)).toBe("superadmin");
});

test("espaces stays public and recouvrement returns there after login", async ({ page }) => {
  await page.goto("/fr/espaces");
  await expect(page.getByRole("heading", { name: "Espaces métier" })).toBeVisible();
  await expect(page).toHaveURL(/\/fr\/espaces$/);

  await page.getByRole("link", { name: "Espace recouvrement — Ouvrir" }).click();
  await page.waitForURL(
    (url) => url.pathname.endsWith("/login") && url.searchParams.get("next") === "/recouvrement",
    { timeout: 20_000 },
  );
  expect(await sessionRole(page)).toBeNull();

  await page
    .getByRole("button", {
      name: "Chargé de recouvrement collections·tessera-collections",
      exact: true,
    })
    .click();
  await expect(page.locator("#login-username")).toHaveValue("collections");
  await expect(page.locator("#login-password")).toHaveValue("tessera-collections");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => url.pathname.endsWith("/recouvrement"), { timeout: 20_000 });
  await expect.poll(() => sessionRole(page)).toBe("collections");
});

test("the anonymous cockpit CTA returns to the cockpit after login", async ({ page }) => {
  await page.goto("/fr/select-space");
  await page.getByRole("link", { name: "Entrer dans le cockpit" }).click({ timeout: 20_000 });
  await page.waitForURL(/\/login\?next=%2Fsurveiller%2Fvue-ensemble/, { timeout: 20_000 });
  expect(await sessionRole(page)).toBeNull();
  await expect(page.getByRole("heading", { name: "Connexion opérateur" })).toBeVisible();

  await page
    .getByRole("button", { name: "Administrateur admin·tessera-admin", exact: true })
    .click();
  await expect(page.locator("#login-username")).toHaveValue("admin");
  await expect(page.locator("#login-password")).toHaveValue("tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL(/\/surveiller\/vue-ensemble/, { timeout: 20_000 });
  expect(await sessionRole(page)).toBe("admin");
});
