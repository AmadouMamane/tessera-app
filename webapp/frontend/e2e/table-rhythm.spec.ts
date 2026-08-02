import { type Page, expect, test } from "@playwright/test";

/**
 * Column rhythm, MEASURED on the rendered page.
 *
 * The complaint that produced this file was "the column widths look a bit random, it does not
 * feel premium". That is a statement about geometry, and geometry is the one thing a class
 * scan cannot see. Counting `pr-4` occurrences would report a tidy repo over a table whose
 * columns are visibly uneven, because what reaches the screen is the resolved cascade over the
 * actual content — `tailwind-merge` lets the last caller win, a `w-24` sits among six auto
 * columns, and a long label in one cell pushes every neighbour.
 *
 * So this reads `getBoundingClientRect` off the real DOM in a real browser and asserts on
 * pixels:
 *
 *  1. **One gutter, everywhere but one column.** Every column is sized by its content; a
 *     single named column absorbs whatever the card has left over. An operator reads a table
 *     by its vertical alignment, and gaps of 16, 8, 24, 16 px are what "random" looks like.
 *  2. **The slack goes to the column holding a sentence**, not to the one holding a link — so
 *     the leftover width reads as prose instead of as a hole. (This is why the rule is "one
 *     column" and not "the last column": an earlier version demanded the last one, which put
 *     the slack on "Investiguer" and wrapped the impact sentence beside it onto three lines.)
 *  3. **The rhythm survives a narrower viewport.** A table that is even at 1672 px and ragged
 *     at 1280 px is even by luck.
 *
 * Run it against a BUILT server (see playwright.config.ts): `next dev` recompiles routes on
 * demand and the first paint of a page can be measured mid-layout.
 */

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page): Promise<void> {
  await page.goto("/fr/login");
  await page.fill("#login-username", process.env.E2E_USER ?? "admin");
  await page.fill("#login-password", process.env.E2E_PASSWORD ?? "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

/**
 * Wait until the header geometry stops changing.
 *
 * A table can exist and still be resizing: data arrives, a column's longest cell grows, the
 * auto layout redistributes. Measuring in that moment produces numbers that are real and
 * meaningless. Two identical consecutive reads is the cheapest honest "it has settled".
 */
async function settle(page: Page): Promise<void> {
  // Fonts FIRST: every assertion in this file is a text measurement, and a fallback face has
  // different glyph widths, so a width read before the real face has loaded is a width of some
  // other page. (Added while chasing a red on the signal registry that this did NOT explain —
  // it is still red, on both builds, for the reason recorded at `SHORT_TEXT_CHARS`.)
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  let previous = "";
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const current = await page.evaluate(() =>
      Array.from(document.querySelectorAll("table thead tr"))
        .map((row) =>
          Array.from(row.children)
            .map((c) => Math.round(c.getBoundingClientRect().width))
            .join(","),
        )
        .join("|"),
    );
    if (current !== "" && current === previous) return;
    previous = current;
    await page.waitForTimeout(250);
  }
}

interface CellBox {
  left: number;
  right: number;
  width: number;
  /** Where the cell's ink actually ends — the widest child's right edge. */
  inkRight: number;
  text: string;
}

/**
 * Every table's COLUMNS, with the extent of the widest ink each one holds.
 *
 * The first version of this measured the header row alone, and it was wrong in a way that
 * produced confident numbers: it reported the "Agent" column as 100-157 px wider than its
 * content on three pages. It is not. The header says "Agent"; the body says
 * "recouvrement-collections", and the column is sized by the body — which is auto-layout
 * doing exactly the right thing. A gutter is the distance from the widest ink IN THE COLUMN
 * to where the next column begins, so that is what is measured.
 */
async function measureTables(page: Page): Promise<CellBox[][]> {
  return page.evaluate(() => {
    /** The rightmost edge of a cell's actual ink, not of its padded box. */
    const ink = (cell: Element): number => {
      const box = cell.getBoundingClientRect();
      const children = Array.from(cell.children);
      if (children.length > 0) {
        return children.reduce((r, c) => Math.max(r, c.getBoundingClientRect().right), box.left);
      }
      if (cell.firstChild) {
        const range = document.createRange();
        range.selectNodeContents(cell);
        return range.getBoundingClientRect().right || box.right;
      }
      return box.left;
    };

    return Array.from(document.querySelectorAll("table"))
      .map((table) => {
        const head = table.querySelector("thead tr");
        if (!head) return [];
        const rows = [head, ...Array.from(table.querySelectorAll("tbody tr"))];
        return Array.from(head.children).map((headCell, column) => {
          const box = headCell.getBoundingClientRect();
          // A column's content width is the WIDEST ink in it, across every row. Taking the
          // header alone reports a column sized by its body as one padded by nothing.
          let inkRight = box.left;
          for (const row of rows) {
            const cell = row.children[column];
            // A `colspan` row (an empty state, a group heading) has fewer cells than the
            // header. Skipping it is not a blind spot — it belongs to no single column.
            if (cell && row.children.length === head.children.length) {
              inkRight = Math.max(inkRight, ink(cell));
            }
          }
          return {
            left: box.left,
            right: box.right,
            width: box.width,
            inkRight,
            text: (headCell.textContent ?? "").trim().slice(0, 24),
          };
        });
      })
      .filter((cells) => cells.length > 1);
  });
}

/** Distinct gaps between the ink of one column and the start of the next, rounded to 1 px. */
function gutters(cells: CellBox[]): number[] {
  const gaps: number[] = [];
  for (let i = 0; i < cells.length - 1; i += 1) {
    const here = cells[i];
    const next = cells[i + 1];
    if (!here || !next) continue;
    gaps.push(Math.round(next.left - here.inkRight));
  }
  return gaps;
}

/** Pages whose cards the complaint was about — the multi-column surfaces an operator lives in. */
const PAGES = [
  "/fr/surveiller/vue-ensemble",
  "/fr/surveiller/qualite-ia",
  // The signal registry, which lives behind its own tab. Reached explicitly because the
  // default tab does not render it — and a probe that silently measures a different table
  // than the one it names is the shape this file has already fallen into twice.
  "/fr/surveiller/qualite-ia?tab=signals",
  "/fr/surveiller/securite-privacy",
] as const;

/**
 * Pages measured for DEAD WIDTH — the four above plus the five other lenses of the per-agent
 * breakdown, which is the card `MAX_DEAD_SHARE` was written for.
 *
 * They are a separate list, and the reason is a measurement rather than a preference. Putting
 * them through the gutter rule above turns three OTHER tables on those pages red, all three
 * pre-existing and none of them touched by this card's fix — verified by running this file
 * against the previous build, where they fail identically:
 *
 *  - `/fr/surveiller/fiabilite-cout`, «Modèle | Fournisseur | …»: gutters [38,35,8,8,8] px. A
 *    513 px panel with ~73 px of leftover, split between its two left-aligned text columns.
 *  - `/fr/surveiller/amelioration`, «Action | Cause probable | …»: gutters [8,68,8,37,42,49] px.
 *  - `/fr/prouver/audit-logs`, the ten-column journal: gutters [27,24,23,24,26,28,21] px —
 *    a 6 px spread on a table that is 98 % saturated, i.e. auto-layout noise, not a design.
 *
 * Naming them here with their numbers is the point: each is a sized debt someone can pick up,
 * not a silence. What is NOT acceptable is dropping the pages so the file looks green — and
 * what is not acceptable either is redesigning three unrelated cards in a change about one, on
 * the evidence of this same file that a rhythm fix can put a hole somewhere else.
 */
const WIDE_TABLE_PAGES = [
  ...PAGES,
  "/fr/surveiller/conformite",
  "/fr/surveiller/observabilite",
  "/fr/surveiller/fiabilite-cout",
  "/fr/surveiller/amelioration",
  "/fr/prouver/audit-logs",
] as const;

for (const path of PAGES) {
  test(`${path} — every table keeps one gutter between its columns`, async ({ page }) => {
    await login(page);
    await page.goto(path);
    // NOT `networkidle`: a cockpit page polls, so it never goes idle and the wait times out
    // after 30 s having measured nothing. Wait for the thing being measured to exist instead —
    // and then for it to stop moving, because a table measured mid-hydration reports the
    // skeleton's geometry and would have passed this file for the wrong reason.
    await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
    await settle(page);
    const tables = await measureTables(page);
    expect(
      tables.length,
      `no multi-column table found on ${path} — the probe went blind`,
    ).toBeGreaterThan(0);

    for (const [index, cells] of tables.entries()) {
      const gaps = gutters(cells).filter((g) => g >= 0);
      if (gaps.length < 3) continue;
      // ONE column may absorb the card's leftover width, and exactly one. That is the design
      // rule: every column is sized by its content, and whatever the card has left over goes
      // to a single named column — the one holding a sentence, so the slack reads as prose
      // rather than as a hole. Drop the widest gutter (that column's); the rest must be one
      // value.
      //
      // Written this way after a version that demanded the LAST gutter be the odd one. That
      // forces the slack onto whichever column happens to be last: on Contrôles critiques
      // that is a one-word "Investiguer" link, and giving it the leftover wrapped the impact
      // sentence beside it onto three lines. On Sécurité the slack sits on "Action demandée",
      // the fifth of seven columns, and the old rule reported a defect that was the design.
      const rhythm = [...gaps].sort((a, b) => a - b).slice(0, -1);
      const spread = Math.max(...rhythm) - Math.min(...rhythm);
      expect(
        spread,
        `table ${index} on ${path}: gutters ${JSON.stringify(gaps)} px between columns ` +
          `[${cells.map((c) => c.text).join(" | ")}] — one column may absorb the slack; the ` +
          `other ${rhythm.length} should be one value, and they are ${new Set(rhythm).size}`,
      ).toBeLessThanOrEqual(TOLERANCE_PX);
    }
  });
}

/**
 * How far two gutters may differ and still read as one rhythm.
 *
 * Not zero: sub-pixel layout and font metrics move an ink edge by a fraction, and a test that
 * demands exactness fails on a machine with different font rendering rather than on a defect.
 * Four pixels is under a quarter of the smallest gutter in the design.
 */
const TOLERANCE_PX = 4;

test("the rhythm holds at a laptop width, not only at a wide desktop", async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/fr/surveiller/vue-ensemble");
  await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
  await settle(page);
  for (const cells of await measureTables(page)) {
    const gaps = gutters(cells).filter((g) => g >= 0);
    if (gaps.length < 3) continue;
    const rhythm = [...gaps].sort((a, b) => a - b).slice(0, -1);
    expect(
      Math.max(...rhythm) - Math.min(...rhythm),
      `at 1280 px the gutters are ${JSON.stringify(gaps)} — even at 1672 px is even by luck`,
    ).toBeLessThanOrEqual(TOLERANCE_PX);
  }
});

/**
 * A short cell must not wrap.
 *
 * This is the other half of "widths fit their content", and the half that is easy to break
 * while fixing the first: once ONE column absorbs the card's leftover width, every other
 * column collapses to its narrowest legal box, and for a text column that box is "wrap at
 * every space". The first pass at the slack column did exactly that — «≤ 0.10%» broke across
 * two lines and «Fidélité (objectif de service)» across three.
 *
 * Twelve characters is the threshold because it separates the two cases cleanly: a threshold,
 * a percentage, a state badge, a count are all shorter; a sentence in the impact column is
 * far longer and SHOULD wrap. A two-word header like «Valeur actuelle» sits between them and
 * is deliberately left alone — forcing it onto one line would widen the column past its data.
 */
const SHORT_TEXT_CHARS = 12;

for (const path of PAGES) {
  test(`${path} — no short cell is narrower than its own text`, async ({ page }) => {
    await login(page);
    await page.goto(path);
    await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
    await settle(page);

    const wrapped = await page.evaluate((limit) => {
      const offenders: string[] = [];
      for (const cell of Array.from(document.querySelectorAll("table td, table th"))) {
        const text = (cell.textContent ?? "").trim();
        if (text.length === 0 || text.length > limit || !text.includes(" ")) continue;
        // A cell that stacks BLOCK children is meant to be several lines — a value with its
        // detail line beneath it. Only inline content can be said to have wrapped.
        if (cell.querySelector("div, p, ul, table")) continue;
        // Measure the TEXT, not the cell. A `<td>` is as tall as its ROW, so a threshold
        // sitting beside a three-line signal name reports as wrapped while rendering on one
        // line — which is what the first version of this probe did, on every page at once.
        const range = document.createRange();
        range.selectNodeContents(cell);
        const ink = range.getBoundingClientRect();
        const line = Number.parseFloat(getComputedStyle(cell).lineHeight) || 16;
        if (ink.height > line * 1.6) {
          offenders.push(
            `«${text}» in a ${Math.round(cell.getBoundingClientRect().width)}px column`,
          );
        }
      }
      return offenders;
    }, SHORT_TEXT_CHARS);

    expect(wrapped, `short cells wrapped: ${wrapped.join("; ")}`).toEqual([]);
  });
}

/**
 * How much of its own width a table may leave unpainted.
 *
 * **This is the assertion this file did not have, and its absence is what shipped the defect
 * it was written to prevent.** Every rule above measures the space BETWEEN columns, and all of
 * them were green while the nine per-agent breakdown tables left 626 to 838 px of a 1338 px
 * card empty. One column had taken the entire leftover, so the gutters were perfectly regular
 * — the file asked "is the rhythm even?" and answered honestly, about a table whose columns
 * were piled into the left third of the card. The operator's words were that they were "piled
 * up on the left instead of spread over the card", and they were describing 60 % of it.
 *
 * ADR 0026's shape exactly: a witness that interrogates the neighbourhood reports on the
 * neighbourhood. So this one asks the thing — how much of this table is nothing?
 *
 * Twenty-five per cent is MEASURED, not chosen. Swept over every table on thirty-one cockpit
 * routes at 1672 px, the worst is 11 % (`/fr/configurer/parametres`, whose last column holds a
 * short status), the breakdown tables are at 4 %, and the defect was 47-63 %. The threshold
 * has margin on both sides: it cannot fail on a design that is merely ragged, and it cannot
 * pass a column that has eaten the card.
 */
const MAX_DEAD_SHARE = 0.25;

for (const path of WIDE_TABLE_PAGES) {
  test(`${path} — no table leaves a quarter of itself empty`, async ({ page }) => {
    await login(page);
    await page.goto(path);
    await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
    await settle(page);

    const offenders = await page.evaluate(() => {
      const found: { head: string; width: number; dead: number }[] = [];
      for (const table of Array.from(document.querySelectorAll("table"))) {
        const head = table.querySelector("thead tr");
        if (!head || head.children.length < 3) continue;
        const box = table.getBoundingClientRect();
        // Narrow tables sit in a column of a grid and are sized by that column, not by a
        // card's leftover width. The complaint is about full-width cards.
        if (box.width < 800) continue;

        let ink = box.left;
        for (const row of [head, ...Array.from(table.querySelectorAll("tbody tr"))]) {
          // A colspan row is a sentence, not columns. A right-aligned footer that spans the
          // table reaches the edge on its own and would report a crammed BODY as full — which
          // is precisely how the defect looked on screen.
          if (row.children.length !== head.children.length) continue;
          for (const cell of Array.from(row.children)) {
            if ((cell as HTMLTableCellElement).colSpan > 1) continue;
            const range = document.createRange();
            range.selectNodeContents(cell);
            for (const rect of Array.from(range.getClientRects())) {
              if (rect.width > 0) ink = Math.max(ink, rect.right);
            }
          }
        }
        found.push({
          head: Array.from(head.children)
            .map((c) => (c.textContent ?? "").trim().slice(0, 16))
            .join(" | "),
          width: Math.round(box.width),
          dead: Math.round(box.right - ink),
        });
      }
      return found;
    });

    expect(
      offenders.length,
      `no full-width table found on ${path} — the probe went blind`,
    ).toBeGreaterThan(0);

    for (const t of offenders) {
      expect(
        t.dead / t.width,
        `[${t.head}] paints nothing in its last ${t.dead} px of ${t.width} — crammed left`,
      ).toBeLessThanOrEqual(MAX_DEAD_SHARE);
    }
  });
}

/**
 * The per-agent breakdown spreads its VALUE columns evenly.
 *
 * "Spread evenly over the whole card" is two claims, and the rule above only holds the first:
 * a table could reach its right edge with columns of 90, 300, 90 and 600 px and still read as
 * random. This holds the second, on the one card that renders seven different column sets from
 * one component — so a lens added later inherits the geometry instead of re-deciding it.
 *
 * The first and last columns are DECLARED exceptions and named as such in
 * `lib/breakdown-columns.ts`: the agent identity is the only left-aligned column, and the
 * release verdict is a sentence. Everything between them holds a number and gets an equal
 * share. Asserted at two viewports, because even at 1672 px alone is even by luck.
 */
for (const width of [1672, 1280]) {
  test(`the per-agent breakdown shares one column width at ${width} px`, async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width, height: 1000 });
    for (const path of ["/fr/surveiller/fiabilite-cout", "/fr/surveiller/amelioration"]) {
      await page.goto(path);
      await page.waitForSelector('table[data-breakdown="agent"]', { timeout: 30_000 });
      await settle(page);
      const columns = await page.evaluate(() => {
        const table = document.querySelector('table[data-breakdown="agent"]');
        const head = table?.querySelector("thead tr");
        if (!head) return null;
        return Array.from(head.children).map((c) => Math.round(c.getBoundingClientRect().width));
      });
      expect(columns, `no breakdown table on ${path} — the probe went blind`).not.toBeNull();
      // Identity and verdict are the two declared exceptions; the rest hold numbers.
      const values = (columns as number[]).slice(1, -1);
      expect(values.length, `${path} has no value column to measure`).toBeGreaterThan(1);
      expect(
        Math.max(...values) - Math.min(...values),
        `${path} at ${width} px: value columns ${JSON.stringify(values)} px — they should be ` +
          `one width, and they are ${new Set(values).size}`,
      ).toBeLessThanOrEqual(TOLERANCE_PX);
    }
  });
}
