import { type Page, expect, test } from "@playwright/test";

/**
 * "À un instant" must change the NUMBERS, not just the badge.
 *
 * Measured on 2026-08-01, on a deep-linked `?lecture=asof&asof=<T-20d>`:
 *
 *     Lecture      : À un instant     ← the mode took
 *     Total flotte : 415 (394 live)   ← the fleet card took
 *     Fidélité     : 61 % · 216/353   ← identical to live
 *
 * The backend was right the whole time — `/observability/slo?days=30` answers `n=353` live and
 * `n=370` at T-20d. The instant simply never reached the query: the page hands T to its heavy
 * fan-out only once the narrow fleet read reports settling, and that hand-off travels through
 * a child component's callback which did not fire on a deep link. Every control therefore read
 * live under a header that said otherwise — the same shape as the period selector that steered
 * nothing, one dimension over.
 *
 * A unit test cannot see this: the components are individually correct and the wiring is what
 * fails. So this drives the assembled page, exactly as `one-window-per-page.spec.ts` does for
 * the window.
 */

test.use({ viewport: { width: 1672, height: 1200 } });

async function login(page: Page): Promise<void> {
  await page.goto("/fr/login");
  await page.fill("#login-username", process.env.E2E_USER ?? "admin");
  await page.fill("#login-password", process.env.E2E_PASSWORD ?? "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

/** The faithfulness row's denominator, and the fleet total, as the page renders them. */
async function reading(page: Page): Promise<{ controls: number | null; fleet: number | null }> {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const controls = /(\d+)\s*\/\s*(\d+)\s+conformes/.exec(text);
    const fleet = /Total de la flotte\s+(\d+)/.exec(text);
    return {
      controls: controls ? Number(controls[2]) : null,
      fleet: fleet ? Number(fleet[1]) : null,
    };
  });
}

const daysAgo = (days: number): string => new Date(Date.now() - days * 86_400_000).toISOString();

async function open(page: Page, query: string): Promise<void> {
  await page.goto(`/fr/surveiller/vue-ensemble${query}`);
  await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
  // The as-of hand-off is deliberately staged behind the fleet read, so the controls settle
  // after it. Waiting on the fleet alone would measure the half that always worked.
  await page.waitForTimeout(9_000);
}

test("a past instant moves the controls, not only the fleet card", async ({ page }) => {
  await login(page);

  await open(page, "?period=d30");
  const live = await reading(page);
  expect(live.controls, "the live page reported no faithfulness sample at all").not.toBeNull();

  await open(page, `?period=d30&lecture=asof&asof=${encodeURIComponent(daysAgo(20))}`);
  const past = await reading(page);

  // The fleet card is the half that already worked; asserting it keeps this test honest about
  // WHICH half broke if it ever breaks again.
  expect(past.fleet, "the fleet total did not move — the instant reached nothing at all").not.toBe(
    live.fleet,
  );
  expect(
    past.controls,
    `the controls table reports ${past.controls} scored answers both live and at T-20d, under a header reading «À un instant» — the instant is not reaching the card queries`,
  ).not.toBe(live.controls);
});

test("an instant before any data reads honestly empty rather than live", async ({ page }) => {
  await login(page);
  await open(page, `?period=d30&lecture=asof&asof=${encodeURIComponent(daysAgo(120))}`);
  const ancient = await reading(page);

  // Four months back the store holds nothing. "Nothing" is the correct answer, and the failure
  // this guards against is the page quietly showing today's numbers instead — which is
  // indistinguishable from a working time machine until you check the date.
  expect(
    ancient.controls,
    `at T-120d the controls table still reports ${ancient.controls} scored answers; the store holds none that far back, so this is the live reading wearing a historical badge`,
  ).toBeNull();
});
