import { type Page, expect, test } from "@playwright/test";

/**
 * THE DESCENT — does the cockpit still work on a smaller screen?
 *
 * WHY THIS FILE EXISTS. On 2026-08-01 Amadou said the cockpit had to adapt to
 * "16 pouces, 14 pouces, 13 pouces, smartphones". It did not: the alert ribbon's
 * gauge track collapsed to ZERO pixels below 768 and dropped its "95,0 %" label
 * onto the eyebrow beside it; toolbars and card headers ran up to 454px past their
 * card; and cards refused to shrink because a grid item defaults to
 * `min-width: auto`. All of it was fixed by measurement — and then measured by a
 * THROWAWAY script that was deleted, which meant a regression would have been seen
 * by nobody. This is that script, made permanent.
 *
 * THE QUESTION IT ASKS. Exactly one, and it is the one the eye asks: is there
 * content that has been cut off with NO WAY TO REACH IT? Not "does the page
 * overflow" — `<body>` is `overflow-hidden`, so the document CANNOT scroll
 * horizontally and that question is unfailable. The first version of this probe
 * asked it anyway and reported zero findings at eight widths while the phone
 * layout was visibly broken. ADR 0026, in the smallest possible package.
 *
 * WHAT IT TOOK TO MAKE THE ANSWER TRUE. Four corrections, each one a false alarm
 * that would have sent someone to "fix" working code:
 *
 *   1. The NEAREST overflow-managing ancestor decides, and nothing above it can
 *      overrule. A 760px table inside its own `overflow-x-auto` box is REACHABLE
 *      even though it sticks far out of the `overflow-x-hidden` main further up.
 *      Stopping at the first `hidden` ancestor called every scrollable table a bug.
 *   2. Deliberate truncation is not loss. A box that clips with an ellipsis says so
 *      on purpose — the cockpit's <Truncate> reveals the full value on hover.
 *   3. `getBoundingClientRect()` reports the box an element WOULD occupy, so every
 *      row `main` has scrolled past appears to "overlap" the footer. It does not:
 *      the browser clips it.
 *   4. Several pages render their own <footer> INSIDE main ("57 éléments…").
 *      Comparing a container with its own descendant always finds an overlap.
 *
 * WHAT IT CANNOT SEE, said plainly. It reads geometry, so it cannot judge whether a
 * layout that FITS is any good — a page can be legible-by-the-numbers and still be
 * a miserable phone experience. It also visits one locale and a fixed page list; a
 * route added tomorrow is not covered until someone adds it here.
 */

/** Laptop, small laptop, tablet, phone. 1024 is in because it is where the left
 *  panel switches between the icon rail and the full 252px panel. */
const WIDTHS = [
  { w: 1512, h: 982, name: '14"' },
  { w: 1024, h: 768, name: "petit portable" },
  { w: 768, h: 1024, name: "tablette" },
  { w: 390, h: 844, name: "smartphone" },
] as const;

/**
 * Static routes — no `[id]` segments, so the set is stable.
 *
 * THE PUBLIC SURFACES WERE OUTSIDE THIS LIST UNTIL 2026-08-02, and that is how the descent
 * reported 76/76 clean while `/fr/select-space` drew a 272 px decoration over its own card
 * title at 390 px. The file's own header already admitted the shape of the hole — "it visits
 * one locale and a FIXED PAGE LIST; a route added tomorrow is not covered until someone adds
 * it here" — and the page a human reported as broken was one of the ones it never opened.
 * Widening the surface of observation beats sharpening the list of suspects.
 */
const PAGES = [
  // The public surfaces — the front door, the directory, the explainer, the business console.
  "/fr/select-space",
  "/fr/espaces",
  "/fr/comprendre",
  "/fr/recouvrement",
  "/fr/surveiller/vue-ensemble",
  "/fr/surveiller/qualite-ia",
  "/fr/surveiller/securite-privacy",
  "/fr/surveiller/conformite",
  "/fr/surveiller/fiabilite-cout",
  "/fr/surveiller/amelioration",
  "/fr/a-traiter",
  "/fr/a-faire",
  "/fr/agents",
  "/fr/agir/incidents-playbooks",
  "/fr/agir/automations",
  "/fr/agir/release-control",
  "/fr/prouver/audit-logs",
  "/fr/prouver/etat-a-date",
  "/fr/prouver/evidence-store",
  "/fr/configurer/politiques",
  "/fr/configurer/modeles",
  "/fr/configurer/integrations",
  "/fr/admin/profil-systeme",
] as const;

interface Unreachable {
  over: number;
  text: string;
  cls: string;
}

/** Content clipped by an ancestor that hides its overflow, with nothing scrollable
 *  in between and no ellipsis saying the truncation is meant. */
async function unreachableContent(page: Page): Promise<Unreachable[]> {
  return page.evaluate(() => {
    const found: { node: Element; over: number; text: string; cls: string }[] = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width < 12 || r.height < 8) continue;
      const text = (el.textContent ?? "").trim();
      if (text.length < 3) continue;

      let parent = el.parentElement;
      let box: Element | null = null;
      let mode = "";
      while (parent !== null) {
        const o = getComputedStyle(parent).overflowX;
        if (o === "auto" || o === "scroll" || o === "hidden" || o === "clip") {
          box = parent;
          mode = o;
          break;
        }
        parent = parent.parentElement;
      }
      if (box === null || mode === "auto" || mode === "scroll") continue;
      if (getComputedStyle(box).textOverflow === "ellipsis") continue;

      const br = box.getBoundingClientRect();
      if (br.width < 100) continue;
      const over = Math.round(r.right - br.right);
      if (over <= 2) continue;
      // Report the OUTERMOST offender: its children are the same defect.
      if (found.some((f) => f.node.contains(el))) continue;
      found.push({
        node: el,
        over,
        text: text.slice(0, 60),
        cls: (typeof el.className === "string" ? el.className : "").slice(0, 120),
      });
    }
    return found.map(({ over, text, cls }) => ({ over, text, cls }));
  });
}

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.keyboard.press("Enter");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 30_000 });
}

test.describe("the cockpit survives the descent", () => {
  /**
   * THE DETECTOR IS ITSELF UNDER TEST, on every run.
   *
   * Four assertions of the same shape the pages make. Without this, "0 findings"
   * would be indistinguishable from "the query stopped matching" — which is
   * precisely how the first version of this probe reported a clean bill of health
   * at eight widths over a visibly broken phone layout. A manual mutation done once
   * proves the witness worked once; this proves it works now.
   */
  test("the detector still sees a defect when there is one", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await page.goto("/fr/surveiller/vue-ensemble", { waitUntil: "networkidle" });

    // (a) genuinely unreachable: too wide, inside a box that hides its overflow.
    await page.evaluate(() => {
      const clip = document.createElement("div");
      clip.style.cssText = "width:300px;overflow-x:hidden;position:relative";
      clip.innerHTML = '<div style="width:900px">PROBE unreachable content</div>';
      document.body.appendChild(clip);
    });
    let hits = await unreachableContent(page);
    expect(
      hits.some((h) => h.text.includes("PROBE unreachable")),
      "a clipped node must be seen",
    ).toBe(true);

    // (b) same width, but its own box SCROLLS — reachable, must not be reported.
    // (c) same width, but the clip carries an ellipsis — deliberate truncation.
    await page.evaluate(() => {
      document.querySelector("div[style*='overflow-x:hidden']")?.remove();
      const scrollable = document.createElement("div");
      scrollable.style.cssText = "width:300px;overflow-x:auto;position:relative";
      scrollable.innerHTML = '<div style="width:900px">PROBE scrollable content</div>';
      const ellipsed = document.createElement("div");
      ellipsed.style.cssText =
        "width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;position:relative";
      ellipsed.innerHTML = '<div style="width:900px">PROBE truncated content</div>';
      document.body.append(scrollable, ellipsed);
    });
    hits = await unreachableContent(page);
    expect(
      hits.some((h) => h.text.includes("PROBE scrollable")),
      "a scrollable box is reachable",
    ).toBe(false);
    expect(
      hits.some((h) => h.text.includes("PROBE truncated")),
      "an ellipsis is deliberate",
    ).toBe(false);
  });

  for (const vp of WIDTHS) {
    test(`no unreachable content at ${vp.w}px (${vp.name})`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: vp.w, height: vp.h });
      await login(page);

      const failures: string[] = [];
      const neverIdle: string[] = [];
      let looked = 0;
      for (const path of PAGES) {
        // `networkidle` was the wait here, and on a SELF-REFRESHING page it is a wait that
        // never ends: `/fr/surveiller/qualite-ia` repolls its SLO tile every five seconds, so
        // there are never 500 ms of quiet and the whole run died on a 45 s timeout — the
        // descent reporting NOTHING about nineteen pages because one of them is alive.
        // Idle is still ATTEMPTED, because where it is reachable it is the better wait; where
        // it is not, the page settles on a fixed delay and the fallback is COUNTED and named
        // below. A witness that had to look at less than it promised says so (ADR 0026).
        await page.goto(path, { waitUntil: "load", timeout: 45_000 });
        const idle = await page
          .waitForLoadState("networkidle", { timeout: 8_000 })
          .then(() => true)
          .catch(() => false);
        if (!idle) neverIdle.push(path);
        await page.waitForTimeout(idle ? 300 : 1_500);
        // A page that failed to render is NOT a page with no defect.
        await expect(page.locator("main")).toBeVisible();
        looked++;
        for (const hit of await unreachableContent(page)) {
          failures.push(`${path} — +${hit.over}px "${hit.text}" [${hit.cls}]`);
        }
      }

      // Anti-vacuity: a run that visited nothing reports no defect too.
      expect(looked, "every page must have been looked at").toBe(PAGES.length);
      if (neverIdle.length) {
        // An annotation the line reporter does not print would make "settled on a delay" and
        // "reached network idle" the same run to a reader — which is the failure this whole
        // change is about.
        // biome-ignore lint/suspicious/noConsole: the fallback must be SEEN, not recorded.
        console.log(
          `[descent ${vp.w}px] settled on a delay instead of network idle: ${neverIdle.join(", ")}`,
        );
      }
      expect(
        failures,
        `content cut off with no way to reach it:\n${failures.join("\n")}`,
      ).toHaveLength(0);
    });
  }
});
