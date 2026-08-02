# The mould for a wide data table

A card-width table with an identity column, some value columns, and often a sentence at the
end. Four rebuilds of the per-agent breakdown produced this; the numbers below are all measured
on a built image at 1672 px (card 1372, table 1338) and at 1280 px (table 946).

Read it before laying out a new table of that shape, and before "tidying" the ones that follow
it. Every rule here replaced something that looked right and measured wrong.

---

## 1. The contract

```tsx
import { COL_IDENTITY, COL_VERDICT, TABLE_BREAKDOWN } from "@/lib/breakdown-columns";

<table data-breakdown="agent" className={TABLE_BREAKDOWN}>
  <thead>
    <tr>
      <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>Agent</th>
      <th className="pb-2 text-center font-medium">Volume</th>
      {/* …every other value column: no width, centred… */}
      <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>Mise en ligne</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td className="py-1.5 pr-3 font-medium">…</td>
      <td className="py-1.5 text-center tabular-nums">…</td>
      <td className="py-1.5 pr-2 text-right">…</td>
    </tr>
  </tbody>
</table>
```

**`table-fixed`.** Auto layout hands its leftover width to a column of its own choosing, and the
choice changes with the viewport. That is what "the column widths look random" is.

**The identity column is left-aligned and sized to its CONTENT, responsively.** It is the only
column that does not shrink with the card, so one fixed width is either too narrow at 1672 px or
80 px of dead trailing air at 1280 px. `w-[6.5rem] 2xl:w-[9rem]`: 6.5 rem clears its widest ink
(«Total de la flotte», 89 px).

**Value columns declare no width and are CENTRED.** Under `table-fixed` they then share what is
left, equally. Centring is not a taste — see §2.

**The prose column takes a flat `w-[25%]`, is right-aligned, and carries `pr-2`.** Right-aligned
so it has leading air at all; 25 % so that air is the size of its neighbours'; `pr-2` so its ink
stops 25 px from the card rather than 17.

**Widths live on the header CELLS, never in a `<colgroup>`.** Under `table-fixed` the first row
sets the columns, so a colgroup is a second list to keep in step — and one entry short, it is
silent. The breakdown renders seven different column sets from one component.

---

## 2. Why centred, and not right-aligned

With right-aligned columns, **the space a reader sees before a column is that column's leading
air** — `width − content`. The contents differ, so equal widths give unequal spaces. Centring
splits each column's air onto both sides, which halves every contribution and levels the run:

| | ink-to-ink gaps (vue-ensemble, 1672 px) | max/median |
|---|---|---|
| right-aligned | `[236, 122, 166, 119, 96]` | 1.93 |
| centred | `[150, 149, 148, 146, 138]` | **1.01** |

The cost is real and small: in a column of mixed-width magnitudes («3 253» over «888») the
digits no longer align on the right. `tabular-nums` keeps the glyph widths equal, and at this
size the column still reads as one block under its own centred header.

---

## 3. How to check a new table

Add its page to `WIDE_TABLE_PAGES` in `e2e/table-rhythm.spec.ts`, put `data-breakdown` on the
table if it follows this mould, and run the spec **against a built server** — `next dev`
recompiles on demand and the first paint can be measured mid-layout.

| what it asserts | bar | this layout | the defect it replaced |
|---|---|---|---|
| dead width — the share of a table right of its last ink | ≤ 25 % | 4 % | 47-63 % |
| ink-to-ink gap, floor (≥ 1536 px) | ≥ 0.5 × median | 0.63 | 0.06 |
| ink-to-ink gap, ceiling (≥ 1536 px) | ≤ 1.6 × median | 1.25 | 1.93-2.02 |
| ink-to-ink gap, floor (below 1536 px) | ≥ 0.3 × median | 0.34 | — |
| the value columns share one width | ± 4 px | exact | 63/69/80 px |

Every bar was measured on both sides before being written down: under what this layout holds,
over what the defect scored. **Never set a bar you do not meet** — it gets lowered later,
quietly, by whoever is unlucky enough to trip it.

There is no ceiling below 1536 px, and that is a measurement rather than a concession: at 946 px
the columns are content-bound. «Erreurs outils (erreurs / appels)» wraps and fills its column,
leaving 31 px of leading air with no width anywhere to redistribute.

`lib/breakdown-columns.test.ts` holds the two failures a browser will never report: a class
assembled from a variable (Tailwind's scanner only finds literals, so it emits no CSS at all),
and a width mixing units (§4).

---

## 4. The traps, each of which cost a build

**A gutter measured to the next column's BOX is the padding, not the space.** It is one constant
for right-aligned content and half the leftover for centred content. The rhythm spec measured it
and reported an even table over a 12 px collision and over 838 px of empty card. What a reader
sees is ink to **ink**.

**An exemption is a place a defect lives.** The identity gap was excluded from the rule as
"structurally the largest". It was — at 1.9 × the median, which is exactly what got reported
next.

**Chromium silently drops a cell width whose `calc()` mixes a percentage with a length.** Under
`table-fixed`, `calc((100% - 10rem) * 2 / 6)` resolves to the plain equal share: 294.5 px where
471 was intended, no warning, plausible-looking table. Honoured: `25%`, `393px`,
`calc(100% * 2 / 6)`. Not honoured: `calc((100% - 160px) * 2 / 6)`.

**A column's ink is the widest of its ROWS, and that is usually the HEADER.** Every width rule
derived from the values alone was wrong.

**Narrowing the identity column does not fix its gap.** 10 rem → 6.5 rem moved it 236 → 194
while pushing its neighbours 122 → 136: a narrower identity widens the value columns and
re-inflates their leading air. The fix was the alignment, not the width.

**A share of the column count over-allocates.** `2 / (values + 2)` for the prose column reads
correctly and measures badly: with two value columns it takes half the table and squeezes its
neighbours to 23 px, and with five at 1280 px it drives gaps NEGATIVE — inks overlapping.

**This mould is for a table that fills a wide card.** A narrow panel (a 513 px table in a grid
cell) is a different problem: an equal share there is ~85 px and the headers break. Those tables
keep auto layout, and the three whose gutters are measurably irregular are named with their
numbers in `e2e/table-rhythm.spec.ts` rather than fixed in passing — this file is itself the
evidence that a rhythm fix can open a hole somewhere else.

---

## 6. The second table, and which half of the mould transferred

«Contrôles critiques» (Vue d'ensemble) was laid out to this playbook on 2026-08-02, and the
useful part is what did NOT carry over. Seven columns of real content in a 1020 px card
(814 px at 1280) means an equal share of ~99 px where «Valeur actuelle» alone inks 160 — and
`whitespace-nowrap` then **overflows the cell** instead of wrapping. Swept on the live page,
every `table-fixed` candidate put inks on top of each other: −29, −49, −70 px at 1672, −139 at
1280. §4's last trap, met in the wild. **Auto layout stayed.**

What transferred is the finding, not the recipe:

| | before | after |
|---|---|---|
| ink-to-ink, 1672 px | `[17,25,16,16,16,` **`69`** `]` | `[26,25,16,16,16,30]` |
| max/median | **4.06** | **1.20** |

- **the value columns are CENTRED** — §2, unchanged, and it is what does the work;
- **no single slack column.** `w-full` on «Impact» handed it the whole leftover, and a
  left-aligned column's *trailing* air is the next gap: 69 px before «Action» against a 17 px
  median. Auto layout spreads the leftover across all seven instead. Check the row height when
  you do this: the previous comment in that file feared the sentence would wrap further, and it
  is a reasonable fear — it just does not happen here (71 px at 1672, 97 at 1280, unchanged).

So the transferable rule is: **`table-fixed` when the card has slack to distribute, auto layout
when it does not — and centre the value columns either way.** The alignment is the mould; the
widths are a case analysis.

### Two ways the witness lied while this was being checked

Both are general, and both reported a clean table over a defect.

**Stillness is not arrival.** `settle()` waits for two identical consecutive header reads. This
page holds each of its *loading* states perfectly still for seconds — rows appear as their reads
land, then the trend column swaps a text label for a sparkline. Three different tables measured
on one page: `[56,25,16,36,36,30]` early, `[26,25,16,36,36,30]` at 3-7 s, `[26,25,16,16,16,30]`
once every read had answered. The spec now waits for the page's in-flight `/api/` reads to drain.

**A chart is ink.** The ink walker ranged over text nodes only. A column whose body holds a
sparkline and no text therefore measured as its *header* — 57 px centred in a 112 px box — and
the rule reported 36 px of empty space on either side of a chart that fills the cell edge to
edge. It stretches over `svg` boxes now.

---

## 5. Where the pieces are

- `webapp/frontend/lib/breakdown-columns.ts` — the three constants, each with the measurement
  that set it.
- `webapp/frontend/lib/breakdown-columns.test.ts` — the two silent failures.
- `webapp/frontend/e2e/table-rhythm.spec.ts` — the geometry, measured in a browser.
- `webapp/frontend/components/agent/agent-breakdown.tsx` — seven lenses; and its client twin
  `temporal-monitoring-breakdown.tsx`, which is easy to forget: **eight tables, two files**.
