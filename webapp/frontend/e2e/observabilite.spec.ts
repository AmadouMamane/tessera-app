import { type Page, expect, test } from "@playwright/test";

/**
 * The page is called "observabilité" and used to answer "is it running".
 *
 * Those are two questions: health asks *is it alive*, observability asks *can I know what
 * happened*. What follows checks the second one is now on the screen — and, more importantly,
 * that each block refuses to answer when it cannot see. Every assertion below is an `or` between
 * a real reading and an honest empty state, because these run against whatever stack happens to
 * be up: a spec that demanded green numbers would be red on a laptop and green in CI, which
 * teaches nobody anything. What it will NOT tolerate is a block that renders reassurance out of
 * a store it could not reach.
 *
 * Rewritten with the mould pass (ADR 0052 §Amendment 1): the ribbon verdict, the page-question
 * KPI row, the three zones, the phase timeline with the scheduler's heartbeat, the filterable
 * component table with its drawer, and the click-reachable edge citations. The previous version
 * asserted strings two editorial passes old ("Ce que chaque magasin porte", "Acheminement") —
 * a spec pinned to yesterday's catalogue polices nothing.
 */

const PAGE = "/fr/surveiller/observabilite";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

test("the verdict leads the page as a ribbon instead of twenty rows to scan", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  // Not « J'observe … » — the cockpit was speaking in the first person in exactly one string
  // out of the whole catalogue, and nowhere else does it say "I".
  const observing = page.getByText(/\d+\/\d+ composants de la pile observés/);
  const unreadable = page.getByText(/Verdict illisible/);
  await expect(observing.or(unreadable).first()).toBeVisible();
  // No eyebrow assertion: `slim` is one line by design and never drew one. The prop was
  // accepted and DISCARDED, so this asserted text that could not exist — and said nothing,
  // because an e2e spec nobody runs against a served build polices nothing.
});

test("the KPI row answers this page's question, not the process's", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Composants observés", { exact: true })).toBeVisible();
  await expect(page.getByText("Signaux acheminés", { exact: true })).toBeVisible();
  await expect(page.getByText("Capacités assurées", { exact: true })).toBeVisible();
  await expect(page.getByText("Couverture d'instrumentation", { exact: true })).toBeVisible();
  // The process facts still exist — as one compact card in the detail zone, not as the lead.
  // `.first()`: the card's title also appears in its own MetricInfo tooltip, so a strict
  // locator resolves to two nodes and fails on a page where the text is plainly there.
  await expect(page.getByText("Service Tessera", { exact: true }).first()).toBeVisible();
});

test("the page is sectioned into the three zones of its question", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("La chaîne et ce qu'elle porte", { exact: true })).toBeVisible();
  await expect(page.getByText("Ce qui a changé dans le temps", { exact: true })).toBeVisible();
  await expect(page.getByText("Le détail, composant par composant", { exact: true })).toBeVisible();
});

test("the chain is drawn with its four stages", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("La chaîne d'observabilité", { exact: true })).toBeVisible();
  const stages = page.getByText("Transport", { exact: true });
  const unreadable = page.getByText("Données indisponibles", { exact: true });
  await expect(stages.or(unreadable).first()).toBeVisible();
});

test("an edge citation is reachable by CLICK, not only by hover", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  const node = page.getByRole("button", { name: /Ouvrir les arêtes de agent/ });
  const unreadable = page.getByText("Données indisponibles", { exact: true });
  await expect(node.or(unreadable).first()).toBeVisible();
  if ((await node.count()) > 0) {
    await node.click();
    await expect(page.getByText("Arêtes déclarées", { exact: true })).toBeVisible();
    // The citation itself — the file that wires the edge — is on screen, not in a title=.
    await expect(page.getByText(/collector\.onprem\.yaml|prometheus\.yml/).first()).toBeVisible();
    await page.keyboard.press("Escape");
  }
});

test("each store says what its silence costs", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Ce que le cockpit sait répondre", { exact: true })).toBeVisible();
  // The row that carries the consequence an operator actually pays for…
  await expect(
    page.getByText("Preuve qu'un agent traite des demandes", { exact: true }),
  ).toBeVisible();
  // …and the sentence that says what its silence COSTS. Naming the capability was what the
  // block did before, and it is what made an operator ask what the block meant: the title
  // announced a loss and every row answered with a noun.
  await expect(page.getByText(/le gate de mise en ligne refuse par défaut/)).toBeVisible();
  // The badge counts in agreement with itself. « 1 capacités … touchées » shipped, because the
  // count was interpolated into a sentence written for the plural only.
  const badge = page.getByText(/capacités? (touchées?|assurées?)/).first();
  await expect(badge).toBeVisible();
  await expect(badge).not.toHaveText(/^1 capacités/);
});

test("the history draws phases and names the scheduler's heartbeat", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Historique", { exact: true })).toBeVisible();
  // The scheduler line is derived from the stamp the loop wrote — one of its three states, or
  // the on-demand sentence; a page that cannot say is `Données indisponibles`.
  // « Sonde » was jargon too — the line now says what happens, in words anyone reads.
  const probeLine = page.getByText(/Vérification automatique/);
  const unreadable = page.getByText("Données indisponibles", { exact: true });
  await expect(probeLine.or(unreadable).first()).toBeVisible();
  // Either the timeline table is there WITH its observed-share column, or the honest empty
  // state. What must never exist is an availability column standing on its own.
  // « Frise » was jargon on a page read by operators; the column is a chronology.
  const timelineColumn = page.getByRole("columnheader", { name: "Chronologie" });
  const observedColumn = page.getByRole("columnheader", { name: "Observé" });
  const nothingRecorded = page.getByText(/Rien d'enregistré sur cette fenêtre/);
  await expect(timelineColumn.or(nothingRecorded).first()).toBeVisible();
  await expect(observedColumn.or(nothingRecorded).first()).toBeVisible();
});

test("a component row opens its drawer with the verbatim answer", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Composants de la pile", { exact: true })).toBeVisible();
  const row = page.getByRole("row", { name: /Ouvrir le détail de/ }).first();
  const empty = page.getByText(/Aucun composant/);
  const unreadable = page.getByText("Données indisponibles", { exact: true });
  await expect(row.or(empty).or(unreadable).first()).toBeVisible();
  if ((await row.count()) > 0) {
    await row.click();
    const drawer = page.getByTestId("component-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("Ce qu'on lui a demandé", { exact: true })).toBeVisible();
    await expect(drawer.getByText(/mot pour mot/)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
  }
});

test("the component table filters by verdict and by text", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  const blindFilter = page.getByRole("button", { name: /Angles morts/ });
  const unreadable = page.getByText("Données indisponibles", { exact: true });
  await expect(blindFilter.or(unreadable).first()).toBeVisible();
  if ((await blindFilter.count()) > 0) {
    const search = page.getByPlaceholder("Rechercher un composant…");
    // The placeholder must FIT. It shipped cut at « Rechercher un composa » because a flex item
    // shrinks below its declared width by default, and no assertion here could see it: a
    // truncated placeholder still matches its selector. So the witness measures the text
    // against the box that holds it, rather than asking whether the box exists.
    const fit = await search.evaluate((element) => {
      const input = element as HTMLInputElement;
      const style = getComputedStyle(input);
      const context = document.createElement("canvas").getContext("2d");
      if (context === null) return null;
      context.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      return {
        text: context.measureText(input.placeholder).width,
        usable:
          input.clientWidth -
          Number.parseFloat(style.paddingLeft) -
          Number.parseFloat(style.paddingRight),
      };
    });
    if (fit !== null) {
      expect(fit.text).toBeLessThanOrEqual(fit.usable);
    }
    await search.fill("postgres");
    await expect(page.getByRole("row", { name: /postgres/ }).first()).toBeVisible();
    await search.fill("zzz-nothing");
    await expect(page.getByText(/Aucun composant ne correspond/)).toBeVisible();
    await search.fill("");
  }
});

test("instrumentation coverage names its evidence rather than implying spans", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Ce que chaque agent estampille", { exact: true })).toBeVisible();
  const proxy = page.getByText(/repères que chaque événement métier doit porter/);
  const unreadable = page.getByText(/Source muette/);
  const noAgents = page.getByText(/Aucun agent déclaré/);
  const failed = page.getByText("Données indisponibles", { exact: true });
  await expect(proxy.or(unreadable).or(noAgents).or(failed).first()).toBeVisible();
});

test("a tool door is always a real link, labelled host-only when it is", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Ouvrir les outils", { exact: true })).toBeVisible();

  const grafana = page.getByTitle(/13000/).first();
  const none = page.getByText(/Aucune adresse navigateur configurée/);
  const failed = page.getByText("Données indisponibles", { exact: true });
  await expect(grafana.or(none).or(failed).first()).toBeVisible();

  // The property worth pinning since the 2026-08-06 correction: the door is ALWAYS an anchor
  // (withholding a door that would have opened is its own dishonesty); what is known — that
  // the address is host-local — is labelled, never used to disable.
  if ((await grafana.count()) > 0) {
    const tag = await grafana.evaluate((node) => node.tagName.toLowerCase());
    expect(tag).toBe("a");
  }
});

test("the tail-sampling panel renders real retention or an honest empty state", async ({
  page,
}) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Conservation ciblée des traces", { exact: true })).toBeVisible();
  // Either real counters (buffer has traces) or the honest empty state.
  const counters = page.getByText("Traces vues");
  const empty = page.getByText(/tampon replay est vide/);
  await expect(counters.or(empty).first()).toBeVisible();
});
