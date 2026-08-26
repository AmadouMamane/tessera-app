/**
 * Column widths for the "Vue par agent" tables — the third layout, each one a measured defect.
 *
 * **Auto layout** hands its leftover width to a column of its own choosing. It picked the
 * identity column, which carried a 54 px lead at 1672 px and 20 px at 1280 px while every
 * other gutter was 12 px. That is what "the widths look a bit random" is, from the outside.
 *
 * **One named slack column** fixed the rhythm and made the table worse. It did not share the
 * leftover, it took all of it: measured on the built server at 1672 px, the nine breakdown
 * tables left **626 to 838 px of a 1338 px card dead**, every value column was squeezed to the
 * width of the number it holds, and «Erreurs outils (erreurs / appels)» wrapped onto four
 * lines above a 61 px column. The operator's words were that the columns were piled up on the
 * left instead of spread over the card, and they were describing 60 % of the card.
 *
 * **A fixed layout** distributes the leftover over every column at once, which is the property
 * that was actually wanted: the values land on evenly spaced rails and the last column reaches
 * the card's edge. Two columns are named exceptions, because neither holds a number:
 *
 *  - {@link COL_IDENTITY} — the only LEFT-aligned column. Given an equal share it would hold
 *    its leftover as air after the agent's name, inside the table, instead of between columns.
 *    Sized to fit the longest agent name and the «Total de la flotte» footer on one line.
 *  - {@link verdictColumnWidth} — the release verdict is a SENTENCE («Bloqué : moins fiable
 *    que sans modèle»), so it holds two shares and is aligned right like the values.
 *
 * Both live on the header CELLS rather than in a `<colgroup>`: under `table-layout: fixed` the
 * first row sets the columns, so there is no second list to keep in step with the header when
 * a lens gains a column — a `<colgroup>` one entry short is silent, and this component renders
 * seven different column sets.
 *
 * Held by `e2e/table-rhythm.spec.ts`, which measures the rendered geometry. A class scan
 * cannot see any of this: what reaches the screen is the resolved cascade over real content.
 *
 * **Laying out another wide table? Read `docs/table-rhythm-playbook.md` first.** It is this
 * layout as a reusable contract, with the bars to check it against and the traps that cost a
 * build each — including the two that no tool reports.
 */

/** `table-layout: fixed` — without it the widths below are suggestions, not columns. */
export const TABLE_BREAKDOWN = "w-full table-fixed text-[0.72rem]";

/**
 * The agent-name column: left-aligned, and sized to its CONTENT — the widest ink it holds is
 * «Total de la flotte» at 89 px, so 6.5 rem clears it on one line with room to spare.
 *
 * Responsive, and the reason is a measurement. This column is the only one that does not
 * shrink with the card, so a width that reads well at 1672 px is 80 px of trailing air at
 * 1280 px — and since the space a reader sees is that air PLUS the next column's, the gap
 * after the agent name became the odd one at laptop widths (127 px against a median of 71).
 * Two literals, one per size, rather than a percentage: a percentage small enough for 946 px
 * leaves «Total de la flotte» to wrap, which is where this whole card started.
 */
export const COL_IDENTITY = "w-[6.5rem] 2xl:w-[9rem]";

/**
 * The release-verdict column: a quarter of the table, aligned RIGHT like every value column.
 *
 * Equal shares filled the card and left one thing unequal, which is what an operator saw next:
 * *"l'espace entre Transferts et Mise en ligne est très petit tandis que l'espace entre les
 * autres colonnes est beaucoup plus grand"*. Measured ink-to-ink, that space was **12 px
 * against a median of 93-211**, on every lens.
 *
 * The cause was a mixed alignment, not a width. A right-aligned value's ink sits at the RIGHT
 * edge of its column, so the space a reader sees before the next column is that column's
 * LEADING air. A left-aligned column has none — its ink starts at its own left edge — and where
 * the two meet the inks touch with only the padding between them. Right-aligning the verdict
 * gives it leading air at all; this width makes that air the size of its neighbours'.
 *
 * **A flat share, and not a share of the column count.** The share rule (`2 / (values + 2)`)
 * is the one that reads correctly and measures badly: with two value columns it hands the
 * verdict half the table and squeezes its neighbours to 23 px of separation, and with five at
 * 1280 px it drives gaps NEGATIVE — inks overlapping. A flat value wins because a value
 * column's ink is usually its HEADER, not its number, so shrinking those columns costs more
 * than the verdict gains.
 *
 * **18 %, re-measured 2026-08-26.** The original sweep chose 25 % when every lens ended in a
 * verdict SENTENCE. The served verdicts today are short chips («PRÊT», «Non évalué»), and
 * measured ink-to-ink over the nine pages x two viewports, the quarter had become mostly air:
 * every lens without the «Dernière évaluation» column ran 2.11-2.23x the median before the
 * verdict at 1672 px, against a 1.6 ceiling. At 18 % the same walk runs 1.03-1.44 with every
 * floor at 0.56+. The blocking sentence («Bloqué : moins fiable que sans modèle», ~209 px)
 * still fits on one line at 1672 px (241 px box); at 1280 px it wraps to two lines, and that
 * trade is accepted — a rare blocked verdict may take two lines, a permanent quarter of air
 * may not.
 *
 * A percentage is also what the browser accepts. Under `table-layout: fixed` Chromium SILENTLY
 * DROPS a cell width whose `calc()` mixes a percentage with a length: `calc((100% - 10rem) * 2
 * / 6)` resolved to the plain equal share — no warning, plausible-looking table. A literal
 * percentage is honoured, and Tailwind's scanner emits it.
 */
export const COL_VERDICT = "w-[18%]";
