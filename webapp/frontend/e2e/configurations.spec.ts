import { type Page, expect, test } from "@playwright/test";

// Covers the editable agent-profile form: the Save button is gated on a dirty
// edit, a changed select persists across a reload (durable override store), and
// the test restores the default so it leaves the profile clean.

const PAGE = "/fr/agents/support-client/configurations";

test.use({ viewport: { width: 1672, height: 1000 } });
// These tests mutate + restore one shared durable store (agent_config.json) and
// the live readiness probe, so they must not race each other across workers.
test.describe.configure({ mode: "serial" });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

const save = (page: Page) => page.getByRole("button", { name: "Enregistrer les modifications" });

/**
 * Click Save and wait for the durable write to land.
 *
 * The button is disabled both while the request is in flight and once the form is clean
 * again, so `toBeDisabled()` alone is satisfied the instant the click fires. Reloading on
 * that signal races the POST: the fresh server render can read the store before the write
 * commits, and the test then reports the *old* value as a persistence failure while the
 * write lands a moment later. Wait for the response instead.
 */
async function saveAndSettle(page: Page) {
  await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().includes("/agent-configurations/config") &&
        r.request().method() === "POST" &&
        r.ok(),
    ),
    save(page).click(),
  ]);
  await expect(save(page)).toBeDisabled(); // clean again after success
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByLabel("Ton")).toBeVisible();
});

// The tone options the backend declares (`agent_configurations.py`). The form marks itself
// dirty by *difference* — `setField` drops the key again when the chosen value equals the
// server's (`agent-configurations.tsx:80`) — so an edit is only an edit when it changes
// something. Selecting a hardcoded "Amical" was therefore a no-op whenever the durable
// store already held "Amical", which is where a previous run had left it: the restore step
// lives in the second test, and serial mode had skipped it ever since the first went red.
// Nine tests in this file were never running. Read the current value, pick another.
const TONES = ["Professionnel", "Amical", "Direct", "Pédagogique"];

async function otherTone(page: Page): Promise<string> {
  const current = await page.getByLabel("Ton").inputValue();
  const other = TONES.find((t) => t !== current);
  expect(other, `no tone differs from ${current}`).toBeTruthy();
  return other as string;
}

test("save is disabled until an edit makes the form dirty", async ({ page }) => {
  await expect(save(page)).toBeDisabled();
  await page.getByLabel("Ton").selectOption(await otherTone(page));
  await expect(save(page)).toBeEnabled();
});

test("a behaviour edit persists across a reload, then restores", async ({ page }) => {
  // Change the tone away from whatever the store currently holds, and persist it.
  const original = await page.getByLabel("Ton").inputValue();
  const next = await otherTone(page);
  await page.getByLabel("Ton").selectOption(next);
  await saveAndSettle(page);

  // Reload: the durable override is reflected by the backend.
  await page.reload();
  await expect(page.getByLabel("Ton")).toHaveValue(next);

  // Restore what was there before — not a guessed default. The store is shared with every
  // other run against this stack, and this test is the only thing that puts it back.
  await page.getByLabel("Ton").selectOption(original);
  await saveAndSettle(page);
  await page.reload();
  await expect(page.getByLabel("Ton")).toHaveValue(original);
});

test("the identity selects (language, owner) are operable and dirty the form", async ({ page }) => {
  const lang = page.getByLabel("Langue par défaut");
  await expect(lang).toBeVisible();
  await lang.selectOption("Anglais");
  await expect(lang).toHaveValue("Anglais");
  await expect(save(page)).toBeEnabled();
  const owner = page.getByLabel("Propriétaire");
  await owner.selectOption("Équipe Produit");
  await expect(owner).toHaveValue("Équipe Produit");
  // Identifiant has a real copy button (not a decorative icon).
  await expect(page.getByRole("button", { name: "Copier l'identifiant" })).toBeVisible();
  await page.getByRole("button", { name: "Annuler" }).click();
});

test("the archive button toggles the durable status badge", async ({ page }) => {
  const status = page.locator("section", { hasText: "Statut de l'agent" });
  await expect(status.getByText("Actif", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Archiver cet agent" }).click();
  await expect(status.getByText("Archivé", { exact: true }).first()).toBeVisible();
  // Persisted: reload still shows archived, then restore so the profile is clean.
  await page.reload();
  await expect(status.getByText("Archivé", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Désarchiver cet agent" }).click();
  await expect(status.getByText("Actif", { exact: true }).first()).toBeVisible();
});

test("the change history is real (file mtimes / console saves, no invented author)", async ({
  page,
}) => {
  const panel = page.locator("section", { hasText: "Historique des modifications" });
  await expect(panel).toBeVisible();
  // Two real event shapes, and only two: a repo file's mtime ("… mis à jour") or a console
  // save ("N champ(s) modifié(s) : …"). Which of the two you see is a property of the stack —
  // the panel keeps the six most recent events (`agent_configurations.py`, `events[:6]`), so
  // a handful of console saves legitimately evicts every file row. Asserting "mis à jour" is
  // present was asserting nobody had used the form recently. Assert the shape instead.
  await expect(panel.getByText(/mis à jour|champs? modifiés?/).first()).toBeVisible();
  // Never the old fabricated author.
  await expect(panel.getByText("Tessera Ops")).toHaveCount(0);
});

test("the overflow menu offers a real config export", async ({ page }) => {
  await page.getByRole("button", { name: "..." }).click();
  await expect(
    page.getByRole("menuitem", { name: "Exporter la configuration (JSON)" }),
  ).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Paramètres avancés" })).toBeVisible();
});

test("the parallel-tools toggle flips and enables save", async ({ page }) => {
  const toggle = page.getByRole("switch", { name: "Exécution parallèle d'outils" });
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect(save(page)).toBeEnabled();
  // Cancel the pending edit (no persistence) to leave the profile clean.
  await page.getByRole("button", { name: "Annuler" }).click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
});

test("the agent status reflects the real /readyz probe, not a literal", async ({
  page,
  context,
}) => {
  const status = page.locator("section", { hasText: "Statut de l'agent" });
  // Nominal: backend reachable -> En ligne.
  await expect(status.getByText("En ligne")).toBeVisible();
  // Force the readiness probe to fail -> the row flips to the real degraded state.
  await context.route("**/api/readyz", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"status":"llm_unreachable","version":"x"}',
    }),
  );
  await page.reload();
  await expect(status.getByText("LLM injoignable")).toBeVisible({ timeout: 15_000 });
  await context.unroute("**/api/readyz");
});

test("the 'Outils autorisés' control opens the real allowed-tools list", async ({ page }) => {
  // It used to be a static span with a misleading chevron; now it's a real disclosure.
  await page.getByRole("button", { name: /sélectionnés/ }).click();
  const menu = page.getByRole("menu").filter({ hasText: "Gérer dans les garde-fous" });
  await expect(menu.getByText("Blocage de carte")).toBeVisible();
  await expect(menu.getByText("Consultation de solde")).toBeVisible();
  await menu.getByRole("link", { name: /Gérer dans les garde-fous/ }).click();
  // The link is per-agent since the multi-agent routes landed: `/agents/<id>/garde-fous`.
  // The old `/agent/garde-fous` shape never matched, so this waited out its full 15 s on a
  // navigation that had already happened.
  await page.waitForURL(/\/agents\/support-client\/garde-fous/, { timeout: 15_000 });
});

test("the Modèle section shows the EFFECTIVE model with its provenance and links to the registry", async ({
  page,
}) => {
  const model = page.locator("div", { hasText: "Modèle servi (effectif)" }).first();
  await expect(model).toBeVisible();
  // ADR 0030 — the row carries the provenance of the effective model. The shared
  // stack may or may not hold an override right now: any of the three honest
  // labels is valid; a missing label is not.
  await expect(
    page.getByText(/Base \(config gelée\)|Override org|Override agent/).first(),
  ).toBeVisible();
  await page.getByRole("link", { name: /Gérer dans le registre des modèles/ }).click();
  await page.waitForURL(/\/configurer\/modeles/, { timeout: 15_000 });
  expect(page.url()).toContain("/configurer/modeles");
});

// --- ADR 0031 — the sampling sliders are effective by construction -----------

test("the runtime-effectiveness block names the serving backend and its model", async ({
  page,
}) => {
  const runtime = page.getByTestId("behavior-runtime");
  await expect(runtime).toBeVisible();
  // The backend chip is one of the three real backend names, never a blank.
  await expect(runtime.getByText(/^(ollama|vertex-ai|openai)$/).first()).toBeVisible();
  await expect(runtime.getByText(/Résolus à chaque tour/)).toBeVisible();
});

test("the behaviour selects wear their effectiveness badges and top-k is the fifth slider (ADR 0032)", async ({
  page,
}) => {
  // Tone/detail say they are injected into the system prompt; max length says
  // its declared hard cap. The exact cap follows the shared store's value, so
  // assert the shape, not one number.
  await expect(page.getByText("Injecté au prompt").first()).toBeVisible();
  await expect(page.getByText(/≤ \d+ tokens/)).toBeVisible();
  const topK = page.getByRole("slider", { name: "Top K" });
  await expect(topK).toBeVisible();
  await expect(topK).toHaveAttribute("step", "1");
});

test("the escalation-threshold block is real: slider, formula, honest default (ADR 0033)", async ({
  page,
}) => {
  const block = page.getByTestId("behavior-escalation");
  await expect(block).toBeVisible();
  // The note carries the REAL reviewer formula, not prose approximations.
  await expect(block.getByText(/fondement x 0,5/)).toBeVisible();
  // The shared store may or may not hold an override: the slider is present
  // either way; when unset it names the org default instead of inventing one.
  await expect(block.getByRole("slider", { name: "Seuil d'escalade" })).toBeVisible();
});

test("the retrieval block is real: depth slider with honest per-lookup default, rerank toggle ON (ADR 0035)", async ({
  page,
}) => {
  const block = page.getByTestId("behavior-retrieval");
  await expect(block).toBeVisible();
  await expect(block.getByRole("slider", { name: "Profondeur de recherche" })).toBeVisible();
  // The shared store may hold an override; when unset the label names BOTH
  // historical defaults instead of inventing one number.
  const toggle = block.getByRole("switch", { name: "Reranking (RRF)" });
  await expect(toggle).toBeVisible();
  // Flip the toggle to prove it is operable, then cancel — no persistence.
  const before = await toggle.getAttribute("aria-checked");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", before === "true" ? "false" : "true");
  await page.getByRole("button", { name: "Annuler" }).click();
});

test("the memory block is real: tier select with honest org default, window slider (ADR 0036)", async ({
  page,
}) => {
  const block = page.getByTestId("behavior-memory");
  await expect(block).toBeVisible();
  const tier = block.getByLabel("Mémoire (tier)");
  await expect(tier).toBeVisible();
  // The org-default option is offered explicitly — honest absence, not a copy.
  await expect(tier.locator("option", { hasText: "Défaut org" })).toHaveCount(1);
  await expect(block.getByRole("slider", { name: "Fenêtre de mémoire" })).toBeVisible();
  // Changing the tier dirties the form; cancel leaves the store untouched.
  await tier.selectOption("Fenêtre (Tier 0)");
  await expect(page.getByRole("button", { name: "Enregistrer les modifications" })).toBeEnabled();
  await page.getByRole("button", { name: "Annuler" }).click();
});

// --- the page scrolls to its end with a WHEEL, like a human ------------------
//
// The root and its grid carried `min-h-0`: inside the shell's `h-full` chain the
// flex column squeezed the page, and `<main>`'s scroll range stopped ~370px short
// of the left column's end — the Tags/archive block was unreachable by mouse
// wheel at EVERY window size (measured live: fully scrolled, the archive button
// sat at y=1361 in a 1000px viewport). No other agent page constrains its root.
//
// The witness must scroll the way a human does: `scrollIntoViewIfNeeded` (and
// any programmatic scroll) can scroll the `overflow-hidden` body and reach the
// element even on the broken page — it asks the neighbourhood, not the thing.
// Wheel + IntersectionObserver-backed `toBeInViewport` sees what the user sees.
// Red before the fix, green after.
test("the bottom of both columns is reachable by wheel scrolling", async ({ page }) => {
  await page.mouse.move(836, 500); // over <main>, so the wheel scrolls the page
  for (let i = 0; i < 30; i++) await page.mouse.wheel(0, 800);
  await expect(page.getByRole("button", { name: /rchiver cet agent/ })).toBeInViewport();
  await expect(page.locator("main aside > *:last-child")).toBeInViewport();
});

test("a temperature edit persists, the history names its author, and reset restores the runtime default", async ({
  page,
}) => {
  // The store is shared with the running stack: the journey ends UNSET, i.e.
  // the runtime default (0.2) serves — the safe end state (ADR 0031 e2e rule).
  const slider = () => page.getByRole("slider", { name: "Température" });
  await expect(slider()).toBeVisible();
  await slider().fill("0.4");
  await expect(save(page)).toBeEnabled();
  await saveAndSettle(page);
  await page.reload();
  await expect(slider()).toHaveValue("0.4");

  // The governed save named its author in the durable history (ADR 0024/0031).
  const panel = page.locator("section", { hasText: "Historique des modifications" });
  await expect(panel.getByText(/par admin/).first()).toBeVisible();

  // Reset → "défaut backend" (unset). Saving it restores the runtime default.
  await page
    .getByRole("button", { name: /Réinitialiser \(défaut backend\) — Température/ })
    .click();
  await expect(save(page)).toBeEnabled();
  await saveAndSettle(page);
  await page.reload();
  await expect(slider()).toHaveValue("0.2");
});
