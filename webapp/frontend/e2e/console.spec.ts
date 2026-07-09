import { type Page, expect, test } from "@playwright/test";

/**
 * Console (Debug) — the contract that exists, not the one that used to.
 *
 * This file was red on `main` (2 of 3) since `71b15b18` (2026-06-19), which deliberately
 * deleted the two controls it pinned: the full-width StatusBar carrying the
 * `Fenetre temporelle` select ("the Console's temporal rail IS XT-01 — no as-of scrubber
 * here") and the KpiRow carrying the `Timeline incidents` link ("SLA/MTTR are ops signals
 * — they belong in SURVEILLER, not a debug console"). The spec was never updated, so it
 * kept asserting a surface the product had renounced. Worse, its own `beforeEach` gate
 * ("Session active") matches the header user-menu, which renders on *every* authenticated
 * page — the precondition proved the header had mounted, never the console.
 *
 * What the Console IS today (ADR 0019 §I2): a surface **generated from the agent's declared
 * invocation binding**. `support-client` declares `in_process_chat`, so it gets the
 * interactive bench. The other three shapes — `none` (honest-empty), `http` (request/response
 * bench), `http` + `input_schema` (generated form) — are owned by `smoke-0019.spec.ts`.
 * This file owns the fourth, and the deterministic non-LLM chrome around it: the chat stream
 * and the thumbs feedback need a live LLM turn and are exercised elsewhere.
 *
 * Selectors are roles, labels and visible text, never CSS classes.
 */

const PAGE = "/fr/agents/support-client/console";

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
  // Gate on a string the CONSOLE owns (the backend's console title), not on header chrome.
  await expect(page.getByRole("heading", { name: "Conversation de test" })).toBeVisible();
});

test("an `in_process_chat` binding renders the interactive bench, and only that one", async ({
  page,
}) => {
  // The interactive shape: a composer bound to the live agent, with its send control.
  await expect(page.getByPlaceholder("Posez votre question à l'assistant...")).toBeVisible();
  await expect(page.getByRole("button", { name: "Envoyer" })).toBeVisible();

  // Generated means *exclusive*: the two other shapes must be absent. If a future refactor
  // makes the console chattable-by-default again, or leaks the HTTP bench into an in-process
  // agent, these two counts are what notices.
  await expect(page.getByRole("button", { name: /Envoyer le tour/ })).toHaveCount(0);
  await expect(page.getByText("Aucune invocation de test", { exact: true })).toHaveCount(0);
});

test("the footer 'compare' action navigates to the as-of page", async ({ page }) => {
  await page.getByRole("link", { name: "Comparer à la version actuelle" }).click();
  await page.waitForURL(/\/prouver\/etat-a-date/, { timeout: 15_000 });
  expect(page.url()).toContain("/prouver/etat-a-date");
});

test("the session controls are live, wired buttons — not decoration", async ({ page }) => {
  // Every one of these comes from the backend payload's `actions.footer_actions`, and every
  // one is bound to a handler (`replay` / `export` / `close`) or a route (`compare`).
  await expect(page.getByRole("button", { name: "Exporter la session" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Clôturer la session" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Rejouer cette session" })).toBeEnabled();
  // Rendered twice (sandbox bar + footer); both reset the session.
  await expect(page.getByRole("button", { name: "Nouvelle session" }).first()).toBeEnabled();
});

test("the debug console carries no ops chrome — the rail invariant of `71b15b18`", async ({
  page,
}) => {
  // The registre des rails temporels pins Console = XT-01 + Live. An as-of scrubber here
  // would be a second, contradicting rail; SLA/MTTR KPIs belong to SURVEILLER. Both were
  // removed on purpose. This is the assertion the old, dead test should have become.
  await expect(page.getByLabel("Fenetre temporelle")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Timeline incidents" })).toHaveCount(0);
});
