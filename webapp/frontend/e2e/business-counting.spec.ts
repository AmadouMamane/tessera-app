import { type Page, expect, test } from "@playwright/test";

/**
 * ADR 0019 §4 — WHICH turns move a business number, seen from the browser.
 *
 * The rule: an operator TESTING an agent must not move its business record; an operator DOING
 * REAL WORK must. `chat.py::is_test_turn(surface)` stamps the first (cockpit Console) synthetic
 * and deliberately leaves the second (`dedicated-ui`, recouvrement's business console) alone.
 *
 * WHAT THIS SPEC PROVES, precisely:
 *   - A real `dedicated-ui` turn, driven through the actual UI, RAISES recouvrement's Métier
 *     event count. The counter is live, the seam is real, and operator work is recorded.
 *   - The cockpit Console leaves that count untouched.
 *
 * WHAT IT DOES **NOT** PROVE, said rather than left to be assumed. The Console's zero is NOT
 * currently caused by §4's synthetic stamp. Every `record_business_event` call site in the repo
 * lives in `src/tessera/agent/recouvrement.py`, and that module is reached only from
 * `POST /recouvrement-assistant/message` — the dedicated-ui route. The cockpit Console enters
 * through `POST /chat`, whose graph emits no business events at all. So the Console moves
 * nothing because it emits nothing, exactly as ADR 0019 §A1.2 criterion (b) holds today "by the
 * absence of an ingestion path, not by the §4 filter". The stamp and the read-seam filter are
 * both correctly pre-positioned and both unit-locked (`test_synthetic_propagation.py`,
 * `test_owned_business_events.py`); neither is load-bearing in a browser yet. The *positive*
 * half below is what keeps this file from being a test that always passes: if the counter ever
 * stops moving for real work, this is what notices.
 *
 * This spec MUTATES the shared dev store: one real workflow run per execution (+N business
 * events into the owned ClickHouse table). That is inherent to asserting "this really counts".
 */

const METIER = "/fr/agents/recouvrement/metier";
const CONSOLE = "/fr/agents/recouvrement/console";
const DEDICATED = "/fr/recouvrement";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page, user = "admin", password = "tessera-admin") {
  await page.goto("/fr/login");
  await page.fill("#login-username", user);
  await page.fill("#login-password", password);
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

/** recouvrement's Métier event count, read from the page the operator actually looks at. */
async function metierEventCount(page: Page): Promise<number> {
  await page.goto(METIER);
  const badge = page.getByText(/\d+ événements/);
  await expect(badge).toBeVisible();
  const text = (await badge.textContent()) ?? "";
  const parsed = Number(text.match(/(\d+)/)?.[1] ?? Number.NaN);
  expect(Number.isFinite(parsed), `unreadable event count: ${text}`).toBe(true);
  return parsed;
}

test("a dedicated-ui turn is real work: it raises the Métier event count", async ({ page }) => {
  test.setTimeout(120_000); // two Métier page loads plus a real workflow run
  await login(page);
  const before = await metierEventCount(page);

  await page.goto(DEDICATED);
  // A real operator action on the business console. `sendRecouvrementAssistantMessage` defaults
  // `surface` to `dedicated-ui`, which `is_test_turn` deliberately does not stamp.
  await page.getByRole("button", { name: "Ouvrir l'assistant complet" }).click();
  const composer = page.getByRole("textbox", { name: "Question assistant" });
  await expect(composer).toBeVisible();
  await composer.fill("Propose un échéancier en 3 fois.");
  await page.getByRole("button", { name: "Envoyer la question" }).click();

  // The workflow is deterministic (no LLM on this path — it returned in 43 ms when measured),
  // so the events land promptly; the retry only absorbs the two page loads.
  await expect
    .poll(async () => metierEventCount(page), {
      message: "a dedicated-ui turn must be recorded as real business activity",
      intervals: [2_000, 3_000, 5_000, 5_000],
      timeout: 60_000,
    })
    .toBeGreaterThan(before);
});

test("the cockpit Console is a test bench: it moves no business number", async ({ page }) => {
  await login(page);
  const before = await metierEventCount(page);

  await page.goto(CONSOLE);
  // Merely reaching the Console — the operator's test bench — must not touch the record.
  await expect(page.getByRole("heading", { name: "Conversation de test" })).toBeVisible();

  expect(
    await metierEventCount(page),
    "the Console must never move recouvrement's business record",
  ).toBe(before);
});
