import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { type Page, expect, test } from "@playwright/test";

// ADR 0037 — the governed prompt-overlay lifecycle on /agents/<id>/prompts:
// an operator proposes (guard-screened server-side), only a superadmin
// approves / rejects / revokes, never the draft's own author. Every test
// leaves the shared durable store CLEAN (no draft, no serving overlay).

const PAGE = "/fr/agents/support-client/prompts";

test.use({ viewport: { width: 1672, height: 1000 } });
// One shared durable store (agent_prompt_overlay.json) — never race workers.
test.describe.configure({ mode: "serial" });

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

const panel = (page: Page) => page.getByTestId("prompt-overlay");

test("full two-person lifecycle: admin proposes, superadmin approves then revokes", async ({
  page,
}) => {
  // Operator (admin) proposes; the review affordances are honestly disabled.
  await login(page, "admin", "tessera-admin");
  await page.goto(PAGE);
  await expect(panel(page)).toBeVisible({ timeout: 20_000 });
  await panel(page).getByLabel("Proposer").fill("E2E ADR 0037 : mentionner les horaires d'été.");
  await panel(page).getByRole("button", { name: "Proposer" }).click();
  await expect(panel(page).getByText("Proposition en attente")).toBeVisible({ timeout: 15_000 });
  await expect(panel(page).getByText(/proposé par admin/)).toBeVisible();
  await expect(panel(page).getByRole("button", { name: "Approuver" })).toBeDisabled();

  // Superadmin approves: the overlay SERVES, with full provenance.
  await login(page, "superadmin", superadminPassword());
  await page.goto(PAGE);
  await expect(panel(page)).toBeVisible({ timeout: 20_000 });
  await panel(page).getByRole("button", { name: "Approuver" }).click();
  await expect(panel(page).getByText(/mentionner les horaires d'été/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(panel(page).getByText(/approuvé par superadmin/)).toBeVisible();

  // Revoke: back to the honest empty state — the base YAML prompt serves alone.
  await panel(page).getByRole("button", { name: "Révoquer l'overlay" }).click();
  await expect(panel(page).getByText(/Aucun overlay servi/)).toBeVisible({ timeout: 15_000 });
});

test("self-approval is refused server-side; the author cleans up with reject", async ({ page }) => {
  await login(page, "superadmin", superadminPassword());
  await page.goto(PAGE);
  await expect(panel(page)).toBeVisible({ timeout: 20_000 });
  await panel(page).getByLabel("Proposer").fill("E2E ADR 0037 : brouillon auto-approuvé ?");
  await panel(page).getByRole("button", { name: "Proposer" }).click();
  await expect(panel(page).getByText("Proposition en attente")).toBeVisible({ timeout: 15_000 });

  // The server refuses the two-person violation — the draft survives, said loudly.
  await panel(page).getByRole("button", { name: "Approuver" }).click();
  await expect(panel(page).getByText(/deux personnes|two people|403/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(panel(page).getByText("Proposition en attente")).toBeVisible();

  // Cleanup: reject the own draft (allowed — it promotes nothing).
  await panel(page).getByRole("button", { name: "Rejeter" }).click();
  await expect(panel(page).getByText("Proposition en attente")).toHaveCount(0, {
    timeout: 15_000,
  });
});
