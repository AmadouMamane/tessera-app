import { type Page, expect, test } from "@playwright/test";

/**
 * Smoke for the ADR 0019 surfaces and the level badges (2026-07-09 overnight run).
 *
 * These assert the two things the night's merges made true and that no unit test can see:
 *
 * 1. **The fleet shows BOTH badge variants at once.** A computed rung, backed by observed
 *    turns, and an attenuated "L{n} déclaré · aucune preuve" for an agent the cockpit has not
 *    seen emit. Before the evidence read was wired, every card showed the second one; if the
 *    read ever silently reverts to trusting an unknown, this test is what notices.
 * 2. **The Console is generated from the declared binding.** `http` gets a test bench,
 *    `none` gets honest-empty — never a broken chat over config the agent does not have.
 *    An agent that declares an `input_schema` additionally gets a generated form, with no
 *    per-agent frontend code anywhere.
 *
 * Zero fabricated fixtures: this runs against the real dev stack. Consequently the *computed*
 * badge only exists once an agent has actually served a turn, which is exactly the property
 * being asserted — an agent that emits nothing must not display a computed rung.
 *
 * Selectors are roles and visible text, never CSS classes: the craft passes retouch classes,
 * and a smoke that breaks on a colour change protects nothing.
 */

const CREDENTIALS = { user: "admin", password: "tessera-admin" };

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", CREDENTIALS.user);
  await page.fill("#login-password", CREDENTIALS.password);
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 30_000 });
}

test.use({ viewport: { width: 1672, height: 1000 } });

test.describe("fleet — the level badge tells declared from computed", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/fr/agents");
  });

  test("an agent with no observed turns reads « déclaré · aucune preuve », never a bare level", async ({
    page,
  }) => {
    // hello-agent publishes only when its process runs; with nothing emitting, the honest
    // reading is the attenuated badge. The number is the agent's ambition, not the cockpit's
    // observation, and the badge must say so.
    const declared = page.getByText(/L\d déclaré · aucune preuve/).first();
    await expect(declared).toBeVisible();
    // The tooltip must distinguish whose silence it is — the store's or the agent's.
    await expect(declared).toHaveAttribute("title", /n'a observé aucun tour|joindre/i);
  });

  test("an agent the cockpit has observed serving turns shows a computed rung", async ({
    page,
  }) => {
    // support-client has served real turns against this stack, so its rung rests on a fact.
    const computed = page.getByTitle(/Niveau d'observabilité|observabilité/i).first();
    await expect(computed).toBeVisible();
    await expect(computed).not.toHaveText(/déclaré/);
  });

  test("both variants are on screen together — the gap is rendered, never hidden", async ({
    page,
  }) => {
    // The whole point of lot B: a fleet where some agents are proven and some are not must
    // look like exactly that. If either count is zero this smoke is measuring nothing.
    const declaredCount = await page.getByText(/L\d déclaré · aucune preuve/).count();
    const computedCount = await page.getByTitle(/observabilité/i).count();
    expect(
      declaredCount,
      "no attenuated badge — has evidence been wrongly assumed?",
    ).toBeGreaterThan(0);
    // PRECONDITION, deliberately not stubbed: a computed rung exists only once an agent has
    // really served a turn on this stack (`TESSERA_LEVEL_TURN_EVIDENCE=1` + Prometheus up +
    // at least one POST /chat). A zero here means the evidence path is not wired, which is a
    // finding — not a reason to fabricate a fixture.
    expect(
      computedCount,
      "no computed badge: wire the evidence read and serve one turn (see overnight-20260709-run.md, lot 1)",
    ).toBeGreaterThan(0);
  });

  test("the platform witnesses are legible as witnesses", async ({ page }) => {
    const chips = page.getByText("Témoin plateforme");
    // hello-agent, turn-agent, duplex-agent.
    expect(await chips.count()).toBeGreaterThanOrEqual(3);
    await expect(chips.first()).toHaveAttribute("title", /.+/);
  });
});

test.describe("console — generated from the declared invocation binding", () => {
  test("a `none` binding renders honest-empty, not a broken chat", async ({ page }) => {
    await login(page);
    await page.goto("/fr/agents/hello-agent/console");
    await expect(page.getByText("Aucune invocation de test", { exact: true })).toBeVisible();
    // It must point at the surfaces that DO observe the agent, rather than fabricate panels.
    await expect(page.getByText(/observez-le via ses/i)).toBeVisible();
    // And it must NOT render the test bench it has no binding for.
    await expect(page.getByRole("button", { name: /Envoyer le tour/ })).toHaveCount(0);
  });

  test("an `http` binding renders a request/response test bench", async ({ page }) => {
    await login(page);
    await page.goto("/fr/agents/turn-agent/console");
    await expect(page.getByRole("heading", { name: /Invocation de test \(HTTP\)/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Envoyer le tour/ })).toBeVisible();
    // The declared endpoint is shown: the cockpit consumes a declaration, it does not guess.
    await expect(page.getByText("http://127.0.0.1:8500/turn")).toBeVisible();
  });

  test("a declared input_schema renders as a generated form — no hand-written fields", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/fr/agents/duplex-agent/console");
    await expect(page.getByRole("heading", { name: /Invocation de test \(HTTP\)/ })).toBeVisible();
    await expect(page.getByText("Capacités déclarées")).toBeVisible();

    // Every field below comes from `schemas/propose_schedule.json`. Nothing in
    // `webapp/frontend/` names any of them: the labels are the schema's `title`s, and the
    // control TYPE is chosen from the declared JSON Schema type. That is the whole claim.
    await expect(page.getByLabel(/Montant restant dû/)).toBeVisible();
    await expect(page.getByLabel(/Nombre d'échéances/)).toBeVisible();
    await expect(page.getByLabel(/Première échéance/)).toBeVisible();

    // enum → a select; boolean → a checkbox. Neither was written by hand for this agent.
    const channel = page.getByLabel(/Canal de notification/);
    await expect(channel).toBeVisible();
    await expect(page.getByLabel(/Notifier le client/)).toHaveAttribute("type", "checkbox");
  });
});
