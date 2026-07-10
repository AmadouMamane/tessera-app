import { type Page, expect, test } from "@playwright/test";

/**
 * The Métier tab — the one cockpit surface built from real business events (ADR 0016/0017 §5).
 *
 * `recouvrement` is the only agent that emits them (`src/tessera/agent/recouvrement.py` holds
 * every `record_business_event` call site), so it is the only agent whose Métier tab can be
 * anything but honest-empty. Both halves are asserted here: the populated agent, and an agent
 * that emits nothing must SAY so rather than render a table of zeros.
 *
 * The counts are read from the owned ClickHouse table (`business_events` defaults to `spine`),
 * so this spec also exercises that read path end to end. Nothing is stubbed: if the store is
 * unreachable the page is honest-empty and this spec fails, which is the correct outcome.
 *
 * Selectors are roles and visible text, never CSS classes.
 */

const METIER = (agent: string) => `/fr/agents/${agent}/metier`;

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

test.describe("recouvrement — the agent with a real business record", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(METIER("recouvrement"));
  });

  test("the tab reports a computed level and a real event count", async ({ page }) => {
    await expect(page.getByText("Signaux métier")).toBeVisible();
    // `Niveau L{n}` is derived from observed facts, never declared here.
    await expect(page.getByText(/Niveau L[0-3]/)).toBeVisible();
    // `{count} événements` — a real count from the owned store. Zero would mean the read
    // path is broken (or the store is empty), which is a finding, not a fixture to invent.
    const events = page.getByText(/\d+ événements/);
    await expect(events).toBeVisible();
    const count = Number((await events.textContent())?.match(/(\d+)/)?.[1] ?? "0");
    expect(
      count,
      "no business events: is the owned ClickHouse read reaching the table?",
    ).toBeGreaterThan(0);
  });

  test("the capability table lists the agent's declared capabilities", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Capacités", exact: true })).toBeVisible();
    // The five workflow capabilities the agent declares. Each row is labelled through the
    // manifest's `label_key` (`capability.<id>` → the locale catalogue), never by a per-agent
    // string in `webapp/frontend/`. A row without a `label_key` is not even selectable.
    for (const label of [
      "Proposition d'échéancier",
      "Rédaction d'une relance",
      "Vérification de la règle de contact",
      "Explication des options de paiement",
      "Résumé du dossier",
    ]) {
      await expect(
        page.getByRole("button").filter({ hasText: label }).first(),
        `capability "${label}" missing from the table`,
      ).toBeVisible();
    }
  });

  test("clicking a capability drills down into its runs and deep-links", async ({ page }) => {
    // Before any selection the runs panel does not render at all — `WorkflowRunsPanel` is
    // gated on `activeCapabilityId`. (Punch-list P3 item 23 asks for a real pre-selection
    // empty state here; today its absence is the honest reading, and this asserts today.)
    await expect(page.getByText(/^Exécutions ·/)).toHaveCount(0);

    await page.getByRole("button").filter({ hasText: "Proposition d'échéancier" }).first().click();

    // The drill-down retitles to the selected capability AND puts it in the URL, so the
    // reading survives a reload (BR-01 §5: the deep-linked scope is part of the read identity).
    await expect(page.getByText(/Exécutions · Proposition d'échéancier/)).toBeVisible();
    await expect(page).toHaveURL(/capability_id=propose_schedule/);
  });
});

test("an agent that emits no business events says so, and shows no table of zeros", async ({
  page,
}) => {
  await login(page);
  await page.goto(METIER("support-client"));
  // The honest-empty invariant: never fabricate a business record for an agent that has none.
  await expect(page.getByText("Données métier indisponibles")).toBeVisible();
  await expect(page.getByText(/n'a pas encore atteint le niveau requis/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Capacités", exact: true })).toHaveCount(0);
});
