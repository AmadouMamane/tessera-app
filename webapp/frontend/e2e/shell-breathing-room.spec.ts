import { type Page, expect, test } from "@playwright/test";

/**
 * The end of a scrolled page must not sit ON the footer.
 *
 * The shell used `py-5`, giving the END of a long scroll the same 20px the top gets — and 20px
 * under the last card, with a fixed footer bar immediately beneath it, reads as touching. An
 * operator scrolled to the bottom of `/surveiller/observabilite` and saw the last panel welded
 * to the compliance strip.
 *
 * This is a property of the SHELL, not of any one page, so it is asserted here and on more than
 * one route: a fix applied to a single page's own padding would leave every other long page
 * exactly as it was.
 *
 * It has to be MEASURED. No selector can see this — every element is present, visible, and
 * correctly labelled while the gap is zero. Only the geometry says it.
 *
 * The real cause was one class deeper than the padding. The content box carried `h-full`, so it
 * was exactly the viewport and its children OVERFLOWED it: the scroll container's padding-bottom
 * was declared, applied to a box the content had already escaped, and therefore never seen.
 * Measured before the fix: 1px of clearance on /observabilite, 0px on /qualite-ia.
 *
 * NOT asserted here, and deliberately named rather than quietly excluded (ADR 0026):
 * `/surveiller/vue-ensemble` has a SEPARATE, pre-existing anomaly — its content overflows the
 * shell's scroll container by ~117px, so `scrollTop` moves while the picture does not. The shell
 * fix does not address it and this spec would be red on it for a reason that has nothing to do
 * with the property above. It needs its own diagnosis in `overview-dashboard.tsx`.
 */

test.use({ viewport: { width: 1672, height: 900 } });

/** Minimum clearance, in CSS pixels, between the end of the content and the footer. */
const MIN_GAP = 24;

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

const LONG_PAGES = ["/fr/surveiller/observabilite", "/fr/surveiller/qualite-ia"];

for (const route of LONG_PAGES) {
  test(`the end of ${route} keeps room above the footer`, async ({ page }) => {
    await login(page);
    await page.goto(route);
    const content = page.locator("[data-shell-content]");
    await expect(content).toBeVisible();

    // The page keeps GROWING after it first renders — every panel fetches its own data. Scroll
    // to the bottom too early and the content lengthens underneath the scroll position, which
    // is what made the first version of this test read −33px on a page whose real clearance is
    // 48px. So: wait for the scroll height to stop changing, THEN go to the bottom, and only
    // measure once the browser confirms it is actually there.
    const scrollHeight = () =>
      page.evaluate(() => {
        const main = document.querySelector("[data-shell-content]")?.parentElement;
        return main ? main.scrollHeight : 0;
      });
    let previous = -1;
    let settled = false;
    for (let attempt = 0; attempt < 25 && !settled; attempt += 1) {
      await page.waitForTimeout(400);
      const now = await scrollHeight();
      settled = now === previous;
      previous = now;
    }
    expect(settled, "the page must stop growing before its end can be measured").toBe(true);

    const measured = await page.evaluate(async () => {
      const content = document.querySelector("[data-shell-content]");
      const main = content?.parentElement;
      const footer = document.querySelector("footer");
      if (!content || !main || !footer) return null;
      main.scrollTop = main.scrollHeight;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return {
        gap: footer.getBoundingClientRect().top - content.getBoundingClientRect().bottom,
        // How far the scroll still is from the true end. Anything but ~0 means the measurement
        // was taken somewhere other than the bottom, and the gap below would be a number about
        // a place nobody is looking at.
        remaining: main.scrollHeight - main.scrollTop - main.clientHeight,
      };
    });

    // `null` means the shell is not on screen at all (an unauthenticated redirect, say) —
    // reported as a failure rather than silently passing on a measurement nobody took.
    expect(measured, "the shell, its scroller and its footer must all be present").not.toBeNull();
    expect(
      Math.abs(measured?.remaining ?? Number.NaN),
      "the gap must be measured AT the end of the scroll, nowhere else",
    ).toBeLessThanOrEqual(2);
    expect(measured?.gap ?? 0).toBeGreaterThanOrEqual(MIN_GAP);
  });
}
