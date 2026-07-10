import { type APIRequestContext, type Page, expect, test } from "@playwright/test";

/**
 * Smoke for the ADR 0019 surfaces and the level badges (2026-07-09 overnight run).
 *
 * These assert the two things the night's merges made true and that no unit test can see:
 *
 * 1. **The badge each card shows agrees with the server's own facts.** An agent whose
 *    manifest declares more than the cockpit has observed gets the attenuated
 *    "L{n} déclaré · aucune preuve"; an agent whose rung rests on observed turns gets a bare
 *    computed rung. If the evidence read ever silently reverts to trusting an unknown, the
 *    cross-check below is what notices.
 * 2. **The Console is generated from the declared binding.** `http` gets a test bench,
 *    `none` gets honest-empty — never a broken chat over config the agent does not have.
 *    An agent that declares an `input_schema` additionally gets a generated form, with no
 *    per-agent frontend code anywhere.
 *
 * STATE-AGNOSTIC BY CONSTRUCTION (rewritten 2026-07-10). The previous version asserted that
 * both badge variants were on screen *at once*, which is a property of the stack's traffic,
 * not of the code: a computed rung exists only after an agent has really served a turn, and
 * `TESSERA_LEVEL_TURN_EVIDENCE` is off in the shipped default, so a freshly booted stack made
 * two of these tests red by construction — the exact mirror of the doctrine that an empty
 * green proves nothing. Here it was an empty red.
 *
 * So the spec no longer asserts a count it does not create. It reads the fleet's facts from
 * `/observability/fleet` — the same facts the page renders from — and asserts the DOM agrees
 * with them, agent by agent. On a dormant stack that reduces to "every card is attenuated,
 * and none is dressed up as computed", which is precisely the regression worth guarding.
 * Serve a turn and the same assertions demand a computed badge instead. Nothing is stubbed.
 *
 * Selectors are roles and visible text, never CSS classes: the craft passes retouch classes,
 * and a smoke that breaks on a colour change protects nothing.
 */

const CREDENTIALS = { user: "admin", password: "tessera-admin" };

/** Same default as playwright.config.ts — the backend this frontend is pointed at. */
const BACKEND = process.env.TESSERA_BACKEND_URL ?? "http://localhost:8290";

type LevelEvidence = "observed" | "dormant" | "unverifiable";
type FleetFact = {
  id: string;
  level?: string | null;
  level_declared?: string | null;
  level_evidence?: LevelEvidence | null;
};

/**
 * The facts the fleet page renders from, read from their source. Mirrors `levelBadgeView`
 * in lib/level-badge.ts: a declared rung that outruns the computed one is shown attenuated;
 * otherwise a computed rung is shown bare; an agent with neither shows no badge at all.
 */
async function fleetFacts(request: APIRequestContext) {
  const response = await request.get(`${BACKEND}/observability/fleet`);
  expect(response.ok(), `GET ${BACKEND}/observability/fleet`).toBeTruthy();
  const agents: FleetFact[] = (await response.json()).agents;
  expect(agents.length, "the fleet is empty — this smoke would assert nothing").toBeGreaterThan(0);

  const attenuated = agents.filter((a) => a.level_declared && a.level_declared !== a.level);
  const computed = agents.filter(
    (a) => a.level && !(a.level_declared && a.level_declared !== a.level),
  );
  return { agents, attenuated, computed };
}

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

  test("the fleet renders exactly the badges its facts imply — nothing is dressed up", async ({
    page,
    request,
  }) => {
    const { attenuated, computed } = await fleetFacts(request);

    // A declared rung that outruns the observed one must never render as computed. Counting
    // both variants against the server's facts catches the regression in either direction:
    // an agent wrongly promoted to computed shifts both numbers at once.
    await expect(page.getByText(/L\d déclaré · aucune preuve/)).toHaveCount(attenuated.length);
    await expect(page.getByTitle(/^Niveau d'observabilité/)).toHaveCount(computed.length);
  });

  test("the attenuated badge names whose silence it is, and never says « recent »", async ({
    page,
    request,
  }) => {
    const { attenuated } = await fleetFacts(request);
    const badges = page.getByText(/L\d déclaré · aucune preuve/);
    await expect(badges).toHaveCount(attenuated.length);

    for (let i = 0; i < attenuated.length; i++) {
      const badge = badges.nth(i);
      // Two silences, two tooltips: the agent emitted nothing (`dormant`), or the metrics
      // store could not be read at all (`unverifiable`). Saying the wrong one blames the
      // wrong party.
      await expect(badge).toHaveAttribute("title", /n'a observé aucun tour|injoignable/i);
      // The evidence query is an unwindowed cumulative counter (turn_evidence.py). A tooltip
      // that promises recency would be lying about what was measured.
      await expect(badge).not.toHaveAttribute("title", /récent|recent/i);
    }

    // And the two tooltips are not interchangeable: each evidence value the server reports
    // must be legible somewhere on the page.
    const titles = await badges.evaluateAll((els) => els.map((e) => e.getAttribute("title") ?? ""));
    if (attenuated.some((a) => a.level_evidence === "dormant")) {
      expect(titles.some((t) => /n'a observé aucun tour/i.test(t))).toBe(true);
    }
    if (attenuated.some((a) => a.level_evidence === "unverifiable")) {
      expect(titles.some((t) => /injoignable/i.test(t))).toBe(true);
    }
  });

  test("a computed badge shows a bare rung — the word « déclaré » never appears on one", async ({
    page,
    request,
  }) => {
    const { computed } = await fleetFacts(request);
    const badges = page.getByTitle(/^Niveau d'observabilité/);
    await expect(badges).toHaveCount(computed.length);

    // On a stack where nothing has served a turn this loop runs zero times, and that is the
    // honest reading: there is no computed badge to inspect. Serve one turn with
    // `TESSERA_LEVEL_TURN_EVIDENCE=1` and the same assertions bite.
    for (let i = 0; i < computed.length; i++) {
      await expect(badges.nth(i)).not.toHaveText(/déclaré/);
      await expect(badges.nth(i)).toHaveText(/^L\d$/);
    }
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
