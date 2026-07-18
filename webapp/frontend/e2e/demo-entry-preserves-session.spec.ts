import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { type Page, expect, test } from "@playwright/test";

// Bug of 2026-07-18: superadmin logs in, clicks « Entrer dans le cockpit » on
// the demo launcher, and the demo 1-click login silently replaces the session
// with the seeded admin account. The rule under test: a session that can
// already enter the target is NAVIGATED — the demo login runs only for a
// visitor who cannot (anonymous, or a role the target rejects).

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
  await page.getByRole("button", { name: "Entrer dans le cockpit" }).click();
  await page.waitForURL(/\/surveiller\/vue-ensemble/, { timeout: 20_000 });
  expect(await sessionRole(page)).toBe("superadmin");
  await expect(roleChip(page, "Super-administrateur")).toBeVisible({ timeout: 20_000 });
});

test("the espaces recouvrement card keeps a superadmin session (supervising, not demoted)", async ({
  page,
}) => {
  await login(page, "superadmin", superadminPassword());
  await page.goto("/fr/espaces");
  // The recouvrement surface card: for an operator it must NAVIGATE (supervision),
  // never re-log the session as the seeded `collections` account.
  await page
    .getByRole("button", { name: /Entrer en démo \(recouvrement\)/ })
    .first()
    .click({ timeout: 20_000 });
  await page.waitForURL(/\/recouvrement/, { timeout: 20_000 });
  expect(await sessionRole(page)).toBe("superadmin");
});

test("the anonymous demo flow still works — one click into the cockpit as the seeded admin", async ({
  page,
}) => {
  // No login: the demo shortcut's whole audience. It must still open a REAL
  // session on the seeded account and land in the cockpit.
  await page.goto("/fr/select-space");
  await page.getByRole("button", { name: "Entrer dans le cockpit" }).click({ timeout: 20_000 });
  await page.waitForURL(/\/surveiller\/vue-ensemble/, { timeout: 20_000 });
  expect(await sessionRole(page)).toBe("admin");
  await expect(roleChip(page, "Administrateur")).toBeVisible({ timeout: 20_000 });
});
