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
 *  - {@link COL_VERDICT} — the release verdict is a SENTENCE («Bloqué : moins fiable que sans
 *    modèle»), and needs about twice a number's width to stay on one line.
 *
 * Both live on the header CELLS rather than in a `<colgroup>`: under `table-layout: fixed` the
 * first row sets the columns, so there is no second list to keep in step with the header when
 * a lens gains a column — a `<colgroup>` one entry short is silent, and this component renders
 * seven different column sets.
 *
 * Held by `e2e/table-rhythm.spec.ts`, which measures the rendered geometry. A class scan
 * cannot see any of this: what reaches the screen is the resolved cascade over real content.
 */

/** `table-layout: fixed` — without it the two widths below are suggestions, not columns. */
export const TABLE_BREAKDOWN = "w-full table-fixed text-[0.72rem]";

/** The agent-name column: left-aligned, sized to its content rather than to a share. */
export const COL_IDENTITY = "w-[10rem]";

/** The release-verdict column: prose, so roughly two numbers wide. */
export const COL_VERDICT = "w-[23%]";
