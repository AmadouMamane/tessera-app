import { type Page, expect, test } from "@playwright/test";

/**
 * `recouvrement` — the product surface of the collections agent (ADR 0010 Phase C).
 *
 * This is a PRODUCT plane, not the cockpit, and the lexicon rule is load-bearing: the word
 * "Tessera" never appears to a business user. The assistant here is not a test bench — turns
 * taken on this surface are real work and are counted (`business-counting.spec.ts` proves that
 * half; this file covers the surface itself).
 *
 * Selectors are roles and visible text, never CSS classes.
 */

const PAGE = "/fr/recouvrement";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
});

test("the operator's day is the landing view, with its real work queues", async ({ page }) => {
  // The rail's queues carry live counts — `Relances 14`, not a bare label.
  await expect(page.getByRole("button", { name: "Ma journée" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Dossiers", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Relances \d+$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Échéanciers \d+$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Situations à vérifier \d+$/ })).toBeVisible();
  // The identity is the business persona, never a cockpit role name.
  await expect(page.getByRole("button", { name: /chargée de recouvrement/ })).toBeVisible();
});

test("the product plane never says « Tessera » to a business user", async ({ page }) => {
  // The lexicon rule (ADR 0013): the platform brand belongs to the operator plane only.
  await expect(page.getByText(/Tessera/i)).toHaveCount(0);
});

test("the assistant drawer opens and exposes a real composer", async ({ page }) => {
  await page.getByRole("button", { name: "Ouvrir l'assistant complet" }).click();
  const drawer = page.getByRole("dialog", { name: "Assistant de traitement" });
  await expect(drawer).toBeVisible();

  const composer = page.getByRole("textbox", { name: "Question assistant" });
  const send = page.getByRole("button", { name: "Envoyer la question" });
  await expect(composer).toBeVisible();
  // Send is gated on a non-empty question — an empty turn is never sendable.
  await expect(send).toBeDisabled();
  await composer.fill("Quelles sont les options de paiement ?");
  await expect(send).toBeEnabled();

  // Two controls share this label: the scrim behind the drawer and the drawer's own ✕.
  await drawer.getByRole("button", { name: "Fermer l'assistant" }).click();
  await expect(drawer).toHaveCount(0);
});

test("the case search is a real, labelled control", async ({ page }) => {
  const search = page.getByRole("textbox", { name: "Rechercher un dossier ou un client" });
  await expect(search).toBeVisible();
  await expect(search).toHaveAttribute("placeholder", /Rechercher un dossier, un client/);
});

// ── lot 9: the case queue is REAL (durable store, derived counters) ──────────

test("nav counters, notifications and the priority dossier derive from the real queue", async ({
  page,
}) => {
  // The notification badge is the real open-case count (no hardcoded "3").
  const bell = page.getByRole("button", { name: /Notifications, \d+ dossiers ouverts/ });
  await expect(bell).toBeVisible({ timeout: 20_000 });
  // Internal consistency: the nav "Relances" badge equals the "Relances" tile —
  // both derive from the same real counter, so they can never diverge.
  const navRelances = page.getByRole("button", { name: /^Relances/ }).first();
  const navCount = (await navRelances.innerText()).replace(/\D/g, "");
  const tile = page.getByRole("button", { name: /Relances\s+à valider/s }).first();
  const tileCount = (await tile.innerText()).match(/\d+/)?.[0] ?? "";
  expect(navCount).toBe(tileCount);
  // The "Pourquoi ce dossier ?" reasons carry the REAL case facts (days late).
  await expect(page.getByText(/Retard significatif : \d+ jours/)).toBeVisible();
});
