# Making a cockpit page 100% functional (real data + real interactions)

This is the transferable recipe distilled from turning **Connaissances**
(`/agent/connaissances`) from a deterministic fixture into a page backed by the
live system. Point any future "make page X real/functional" task at this file —
it tells you exactly what to do.

## The one mental model: two independent axes

A page is only "done" when **both** axes hold. State explicitly which holds; a
fixture that visually matches the normative is NOT "real".

1. **Real data** — every displayed value traces to a real artifact (pgvector,
   eval reports, corpus files, prompt YAML, guard policy/audit log), not an
   invented literal. If a metric has no real source, render `-`, never a fake
   number.
2. **Real interactions** — search / filter / add / detach / toggle / nav
   actually mutate the live store or navigate, verified end-to-end.

## NON-NEGOTIABLE UI RULES (read before touching any cockpit table)

These are mandatory and override the normative screenshots:

- **EVERY main-table row click MUST open a detail drawer.** This is the *single
  allowed deviation from the normative images* — even if a normative shows an
  inline detail panel (or no detail at all), the row click opens a right-anchored
  **drawer**. Reuse the Connaissances pattern exactly (`agent-connaissances.tsx`):
  overlay `fixed z-50 flex justify-end`, a runtime-measured rect of `<main>`
  (`getBoundingClientRect` on open + resize, top below the tab strip when present),
  a `<dialog open aria-modal>` panel (`max-w-[440px]`, `border-l`, shadow), close
  on backdrop `onMouseDown` (target === currentTarget), Escape handler, and a
  focus-return on close. No `?? rows[0]` fallback — nothing opens until a click.
- **EVERY main table MUST have the full Connaissances treatment, identical look:**
  a filter bar above (controlled search `<input>` + `FilterDropdown`s keyed on
  **stable keys**, not display strings), **sortable** column headers
  (`aria-sort`, click toggles col/dir, arrow on the active col, dim
  `ChevronsUpDown` on the rest), and a **client-side pagination footer identical
  to Connaissances** ("{start}-{end} sur {total}" + centered page window +
  prev/next chevrons + "Lignes par page" select, default 10, `useEffect` resets
  to page 1 on filter/sort/size change). `table-fixed` + explicit `<th>` widths.
- **EVERY filter / sort / search / dropdown / button MUST actually work,
  verified e2e** (the row count or order changes, the drawer opens, the state
  mutates). A control that renders but does nothing is a FAILURE — this is the
  same bar as "dead button = failure", applied to filters and sorts too.
- **Never omit a control for lack of a backing store — build the store.** If a
  normative shows "save snapshot" / "export" / any action and no persistence
  exists, create the durable store (a JSON next to the audit log, a table, a
  probe) and wire it. Omitting is only OK when the control would be meaningless
  (e.g. editing a Git-managed file from the UI), never merely because the
  persistence isn't built yet.
- **EVERY control in a control bar must be a real, working input — never a static
  `<span>` dressed as a field.** Tenant / Agent / "Source du contexte" etc. are
  native `<select>`s (styled `appearance-none` + an overlaid `ChevronDown`), the
  reference is a real `<input>` (commits on Enter), the primary button actually
  mutates state. A field that only displays a value is a failure even if it looks
  right.
- **CALENDARS — two premium types, pick by what you select, never ship the raw
  control:**
  - *Day / window* (Journal d'audit, Synthese period): reuse the canonical
    `components/cockpit/window-control.tsx` (`WindowControl`) — segmented presets +
    range readout + the "Aller a une date" calendar popover. This is the shared
    premium calendar; do not re-implement a month grid.
  - *Instant (date + time)* (Etat a date, where T carries an hour like 16:20): a
    day-only window picker is the WRONG type, and the **native `datetime-local`
    looks cheap even when shelled/`[color-scheme:dark]`** — so build a small
    **homemade date+time popover**: a styled trigger (CalendarDays icon +
    Intl-formatted value or "Maintenant" with a live dot), a Monday-first month
    grid (`monthGrid` of 42 cells, prev/next nav, today ring, selected = violet,
    out-of-month dimmed — same look as `window-control`), a `type="time"` input,
    and a "Maintenant" reset. Feed the same `draft` "YYYY-MM-DDTHH:MM" so the
    commit path (Reconstituer / reference code) is unchanged. Close on
    outside-click via the shared `useDismiss`. Do NOT force `WindowControl` onto
    an instant — it has no time and its range readout is meaningless for one T.
- **FRENCH MUST CARRY ITS ACCENTS — backend strings AND hardcoded frontend
  strings.** "Réglementation", "État reconstruit à T", "Réponse d'origine",
  "Intégrité vérifiée", "Règles déclenchées", "décisions journalisées", "Requête
  de test", "Pas encore indexée"… `ruff` is fine with accented Latin (RUF001 only
  flags confusable glyphs — keep apostrophes ASCII `'`). Accent the module's
  emitted strings, the relabels, AND any French literal hardcoded in the `.tsx`.
  Gotcha: adding accents **breaks every e2e/`getByText` selector** that used the
  accent-free spelling — `getByText`/`getByRole({name})` are accent-sensitive, so
  update the specs in lockstep ("Etat reconstruit a T" -> "État reconstruit à T",
  menuitem "Reglementation" -> "Réglementation", etc.).

## Step 1 — find the real source (don't assume there isn't one)

Check what's actually populated before declaring something a fixture:

- pgvector: `SELECT count(*), <group cols> FROM documents` (238 chunks, 15
  categories, real `inserted_at`, `metadata.{category,locator,language}`).
- eval runs: `eval/reports/*.json` via `observability/eval_data.py`
  (`load_eval_snapshot()` — pass rates, sessions w/ latency+tokens).
- corpus on disk: `src/tessera/corpus/data/*.json`.
- prompts: `src/tessera/agent/prompts/{fr,de,en}.yaml`.
- guard: `src/tessera/guard/policy.yaml` + the audit log.

If the data needs generating, **run the smallest model only** (`llama3.2:3b`,
`bge-m3` for embeddings) and cache the result to JSON — never fabricate.

## Step 2 — backend: build from the live source

- Add `observability/<area>.py` with an async `build_<area>()` that reads the
  live source and assembles the payload. Keep the **same payload shape** as the
  existing fixture so the frontend/zod are untouched where possible.
- Emit colours/statuses as keys; free-text **ASCII-only** (RUF001: no `·`, `€`,
  `’`, `−` — use `-`, `/`, `EUR`; accents é/è are fine).
- For metrics with no source, return `-` (see `_pct_or_dash`).
- Rewire the GET route to `await build_<area>()`; keep the `try/except ->
  {available: false}` guard.

## Step 3 — durable mutation state + endpoint

- Persist per-entity state to a JSON next to the guard audit log:
  `get_settings().guard.audit_file.parent / "<area>_state.json"` (dev:
  `/tmp/tessera/`, outside the repo, so it is never committed).
- Expose `set_<area>_state(key, **changes)` (load → merge → save) and an
  `available_<keys>()` set for validation.
- Add `POST /observability/<area>/<thing>-state` taking a Pydantic body, 404 on
  unknown key, and **return the refreshed payload** so the client can replace
  its cache in one round-trip.

## Step 4 — frontend: wire every control

- `useMutation({ mutationFn, onSuccess: (fresh) => qc.setQueryData([key], fresh) })`.
- Search → a controlled `<input>` filtering rows client-side (not a `<span>`).
- Filters → cycle buttons (`Tous → A → B → Tous`) filtering rows by field.
- Add/attach → a dropdown fed by an `attachable` list in the payload (entities
  not currently attached), each item calling the mutation with `attached:true`.
- Detach/toggle → buttons calling the mutation; `disabled` while pending.
- Cross-app nav (e.g. "Gérer le catalogue") → `Link` to the real route
  (`/configurer/sources-memoire`), not a dead button.
- **zod is non-strict** (it strips unknown keys): add any field the component
  needs (e.g. `key`) to the schema or it vanishes after parse.

## Step 5 — real sparklines / curves

- If the data has a real time axis, bucket it chronologically.
- If it is a single snapshot (e.g. `inserted_at` spans 60s — one ingest batch),
  **do not fake a time-series**. Plot a real **distribution** instead
  (per-source chunk counts, per-source citation, per-category pass rate). Never
  flat-fill `[value]*7`.
- Visual reference: the curves in `/prouver/audit-logs`.

## Step 6 — derived metrics need a probe, not a guess

Retrieval citation / hit-rate have no stored source, so measure them:
`scripts/probe_retrieval.py` embeds the real catalogue queries, runs
`knn_search` over each corpus, counts hits above a similarity threshold
(`>= 0.55`), and caches per-source + overall numbers to
`<audit_dir>/knowledge_citations.json`. The backend reads the cache; absent →
`-`. Re-run: `PYTHONPATH=.:src .venv/bin/python -m scripts.probe_retrieval`.

## Step 7 — verify the interaction, not just the render

Playwright, logged in as `admin / tessera-admin`, asserting **state changed**:
detach → the row disappears and the count drops; toggle → `aria-pressed`
flips; filter → row count changes. Then **reset the durable state**
(`rm /tmp/tessera/<area>_state.json` or re-attach via curl) so you don't leave
it dirty.

## Gotchas that cost time

- Restart the backend after backend edits (module import / any in-proc cache):
  `for pid in $(lsof -ti tcp:8290); do kill -9 $pid; done` then relaunch with
  `PYTHONPATH=$PWD/src TESSERA_API__PORT=8290 ...`.
- Next dev must point at the right backend: launch with
  `TESSERA_BACKEND_URL=http://localhost:8290` or it falls back to the stale
  `:8099` and you debug a ghost.
- ruff: name magic numbers (PLR2004); extract helpers if a function exceeds 50
  statements (PLR0915); move runtime-unused typing imports under
  `TYPE_CHECKING` (TCH003).
- `pyvector`/`eval/` are not in the strict mypy gate; `src/tessera/**` is.
- The Next dev server (3390) can be killed by the parallel process - if Playwright
  hits `ERR_CONNECTION_REFUSED`, relaunch it (see above) before debugging.
- Playwright on these pages: (1) a label rendered uppercase via CSS `uppercase`
  keeps its **lowercase DOM text** - match `getByRole({name:"de"})`, not `"DE"`,
  and `exact:true` is case-sensitive; (2) `getByRole(name)` is a **case-insensitive
  substring** match - searching "Filtres" also matches "Reinitialiser les filtres"
  (strict-mode violation) - use `.first()` or the exact name; (3) the **first
  compile of a Next dev route is slow** - the first `click()` can time out, so warm
  the route (longer `waitForTimeout`) before asserting.

## Round-4 skills (drawer, real traces, filters, table widths)

- **Detail panel -> drawer.** See the DONE notes under Round-3 (root `relative
  overflow-hidden`, full-width table, `absolute inset-0 z-30` backdrop + `<dialog>`,
  no `?? details[0]` fallback so nothing opens until a row click).
- **Expandable long text.** Don't lengthen a truncation (still cut off) or always
  show everything (kills density). Store the full text in the payload, render with
  `line-clamp-3` + a "Voir plus / Voir moins" toggle gated on `text.length > N`.
- **Dead button -> advanced-filters popover.** A button with no `onClick` is a
  failure. Wire it to real extra axes absent from the inline dropdowns (langue,
  couverture minimale, "avec echanges ancres") with a live count badge.
- **A reset labelled "all" must reset all.** "Reinitialiser les filtres" first
  cleared only the popover filters - inconsistent with the inline dropdowns. Make
  it global (search + inline + advanced) and show it whenever ANY filter is active.
- **`overflow-hidden` on a flex item clips instead of scrolls.** The page root
  carried `overflow-hidden` (added so the `absolute inset-0` drawer would clip
  cleanly). As a flex child of the AppShell `h-full` column, `overflow-hidden`
  set its automatic `min-height` to 0, so flexbox shrank it to the container
  height and clipped the bottom rows with no scroll once "Lignes par page" was
  high. Two ways out, and the choice matters:
  - *Viewport-constrain* (`min-h-0 flex-1` chain + `overflow-auto` table area +
    `sticky` header) keeps KPIs/filters fixed and scrolls rows in-card - but the
    table then fills the viewport and leaves a big empty gap below the last row
    when few rows are shown.
  - *Content-size (chosen here)*: just **drop `overflow-hidden`** from the root
    (keep `relative` for the drawer). The root then sizes to its content
    (default `min-height:auto` blocks the shrink), so the card hugs the rows
    (no gap at 10/page) and the AppShell `<main>` (`overflow-y-auto`) scrolls the
    whole page at 50/page. The `absolute inset-0` drawer still works; the backdrop
    has its own `overflow-hidden rounded-lg`, so the root does not need it.
- **Client-side pagination footer.** Below a filtered table: "Afficher {start} -
  {end} sur {total}" + centered page buttons (prev/next chevrons, a centered
  window of numbers, active = violet `#b9a6ff`) + "Lignes par page" `<select>`
  (default 10). Hold `page`/`perPage` in the table; `useEffect(() => setPage(1),
  [totalRows, perPage])` resets to page 1 when the filtered count or page size
  changes; slice `rows.slice((page-1)*perPage, ...)`. Clamp `safePage` on render.
- **Uniform column widths = `table-fixed` + per-`<th>` `style={{width}}`.** A
  `w-full` auto-layout table sizes columns to content and looks arbitrary. Apply
  `table-fixed` and explicit widths summing to 100% (Connaissances: Source 32 /
  Type 18 / Statut 12 / Couverture 14 / Fraicheur 12 / Taux 12). Tailwind
  `w-[X%]` classes are unreliable here; inline `style` on `<th>` works.

## Round-6 skills (full FR/DE/EN localization)

- **Backend builder takes `lang`.** `build_connaissances(lang)` localizes every
  display label via a small `_TR: {key: (fr, de, en)}` table + `_t(key, lang)`;
  templated text (summary, freshness, relative time, chunk label) gets per-locale
  helpers. The GET route and the mutation route both accept a `lang` query param.
  ASCII-only in Python source per file convention (German uses ae/oe/ue/ss).
- **Filter/sort on STABLE KEYS, never display strings.** Once labels are
  localized, comparing `r.status === "Active"` or keying a sort `switch` on the
  column label "Couverture" breaks in DE/EN. Filter on `status_tone`/`type_tone`
  (and period days, lang codes), and sort by **column index**, not label.
- **Frontend chrome via next-intl.** Backend owns data labels; the frontend owns
  its own widget chrome (filters, chips, pagination, advanced popover, voir plus,
  empty/loading/error states) under the page's i18n namespace. Status/Type filter
  *option labels* come from i18n too (`tCommon("all")` + per-tone keys).
- **Locale plumbing.** `useLocale()` -> pass to `fetch(?lang=)` and into the
  react-query `queryKey` (so switching locale refetches) and to mutations (the
  mutation route returns the localized payload). `page.tsx` prefetch must use the
  same `["key", locale]` queryKey and `?lang=` or hydration won't match.

## Round-9 skills (committed frontend e2e)

- **Commit a Playwright e2e, don't rely on throwaway scripts.** The repo had the
  `test:e2e` script + `@playwright/test` dep but NO `playwright.config.ts` and no
  tests - so all the rich frontend logic was unprotected. Add the config
  (`testDir ./e2e`, `baseURL` from `E2E_BASE_URL`, a `webServer` that reuses a
  running `:3390` and sets `TESSERA_BACKEND_URL`) and a spec covering the
  behaviour that must survive refactors: tone-based filtering, **index** sorting,
  drawer open + Escape close, dropdown outside-click dismissal, URL-synced filters.
- **E2e selector lessons (same as the throwaway runs, now permanent).** Use
  web-first assertions (`expect(locator).toBeVisible()/toHaveCount()`), not manual
  waits. Disambiguate: sortable header buttons collide with filter triggers, so
  target the trigger by its full accessible name (`"Statut Tous"`) and the header
  by exact (`{name:"Volume", exact:true}`); a substring name like `"Active"` also
  matches `"Desactivee"` -> use `exact`. For "outside click" dismissal, click a
  real neutral element (the search input via `getByPlaceholder`), not raw
  coordinates - coordinates can land on a row and open the drawer instead.
- `playwright-report/` and `test-results/` are already git/biome-ignored.

## Round-8 skills (testability, source-name i18n, URL state)

- **Extract a pure assembler so the payload is unit-testable.** `build_<area>`
  did DB fetch + assembly together (untestable without Postgres). Split it: the
  async fn just fetches (`raw_rows`, state, probe, traffic) and delegates to a
  pure `_assemble(raw_rows, state, probe, traffic, lang, now=None) -> payload`.
  Unit tests then feed synthetic pgvector rows and assert the whole payload
  (localized columns/KPIs, Volume share summing to 100, `status_tone`/`type_tone`
  /`hits`, detached -> `attachable`) with zero I/O. See `tests/unit/test_knowledge.py`.
- **Localize data labels too, keeping logic keys.** Source display names move to
  `_SOURCE_NAME: {cat: (fr, de, en)}` (regulation acronyms RGPD/DSGVO/GDPR + the
  brand suffixes translate; the brand stays). `_SOURCE_META` collapses to a
  `cat -> tone` map - safe because the corpus scripts only iterate its keys.
- **Sync filter/selection state to the URL.** Initialize each filter `useState`
  from `useSearchParams().get(...)` and write them back in one effect via the
  locale-aware `router.replace({ pathname, query }, { scroll: false })` (drop
  defaults from the query). Persisting the open row (`sel`) reopens the drawer on
  reload - a shareable, bookmarkable view. With `typedRoutes`, pass `Link`/router
  hrefs as `{ pathname, query }` objects, not template strings.
- **Cheap a11y wins.** `aria-label` on a placeholder-only search input;
  `aria-live="polite"` on the active-filter chips region (it stays mounted while
  >=1 chip, so add/remove is announced); deep-link cross-page actions with the
  entity key (`?source=<key>`) instead of a bare route.

## Round-7 skills (metric honesty, mutation errors, drawer anchoring, accents)

- **A label must compute what it says.** The "Couverture" column actually
  computed `chunks/max_chunks` (volume share vs the biggest source), not query
  coverage. Renamed to "Volume" + recomputed as the real corpus share
  (`chunks/total`). Same for the KPI "Couverture des requetes" -> "Couverture des
  sources" (it measures the share of sources cited >=1x, not a per-query figure).
  If a value can't be sourced for the label, change the label, don't fake the value.
- **Renaming a metric means auditing every surface that names it.** After
  "Couverture" -> "Volume", the advanced filter was still "Couverture minimale"
  (filtering the renamed field) and the KPI still said "des requetes". When you
  rename a field's meaning, grep every place it surfaces - column header, inline
  filter label, chip label, detail usage row, KPI - and the sort accessor that
  keys off it; fix them together or you ship a half-renamed, contradictory UI.
- **Don't duplicate a metric under a new name.** Per-source "query coverage" IS
  the existing citation rate (same probe number) - adding a second column would be
  a misleading twin. Surface the genuinely-distinct **absolute hit count** in the
  detail (Usage), not as a redundant table column. The three retrieval metrics are
  distinct: per-source **citation** (% queries hitting this source), global
  **source coverage** (% sources ever hit), global **hit-rate** (% queries that hit
  anything).
- **Mutations need an `onError`.** Attach/detach/toggle that only had `onSuccess`
  failed silently; add an `onError` -> inline alert banner (i18n key).
- **Full-height overlay drawer anchored to the content area.** The right pattern,
  distilled from several wrong turns: keep the page root **content-sized** (so no
  empty gap under a short table), and position the drawer overlay `fixed` with a
  runtime-measured rect of `<main>` (`getBoundingClientRect` on open + resize) -
  `top` = the agent **tab strip** bottom (`[data-agent-tabs]`), `left/width/bottom`
  = `<main>`. Result: full content-area height regardless of row count, **below the
  header AND the page tab strip** (both are persistent nav chrome, like the audit
  page), not over the sidebar. Wrong turns to avoid: `absolute inset-0` on a
  content-sized root (drawer too short when few rows); `fixed inset-0` (covers the
  header/nav). Float it: overlay `p-2.5` + panel `rounded-lg border` + soft shadow
  for a small inset gap rather than edge-to-edge. Non-modal `<dialog open>` needs a
  manual Escape handler AND a Tab focus-trap (query focusables, cycle first/last).
- **French needs accents; ruff is fine with them.** Backend French was emitted
  accent-free; add proper accents (Resilience -> Résilience, Desactivee ->
  Désactivée, Credit -> Crédit) and German umlauts. `RUF001/2/3` only flag
  *confusable* characters (fancy quotes, en-dash, Cyrillic look-alikes), NOT
  accented Latin or umlauts - keep apostrophes ASCII (`'`) and you pass.

## Round-5 skills (robustness, a11y, sort, chips)

- **One `useDismiss(open, onClose)` hook for every popover.** Custom dropdowns
  built from `useState(open)` don't close on outside-click or Escape, and opening
  one leaves the others open. A shared hook (ref + `document` `mousedown`/`keydown`
  listeners while open, returning the ref for the root `<div>`) fixes all three at
  once - and the outside-mousedown naturally closes a sibling when you open the
  next. Add `aria-haspopup`/`aria-expanded` to the trigger.
- **biome a11y: prefer `menu`/`menuitem` over `listbox`/`option`.** `role="listbox"`
  trips `useFocusableInteractive` (needs focus) + `useSemanticElements` (wants
  `<select>`); `role="menu"` on a div + `role="menuitem"` on buttons passes.
- **Keyboard-reachable table rows.** A clickable `<tr onClick>` is mouse-only. Add
  `role="button"` (with a `biome-ignore lint/a11y/useSemanticElements`), `tabIndex
  ={0}`, `aria-label`, an `onKeyDown` for Enter/Space, and a `focus-visible:ring`.
- **Column sort on a fixed-layout table.** Header `<th>` gets `aria-sort`
  (ascending/descending/none) and wraps its label in a `<button>` that toggles
  `sortCol`/`sortDir`; a `useMemo` sorts a COPY of the filtered rows before
  pagination (nulls always last; numeric vs `localeCompare`); reset page to 1 on
  sort change. Show an up/down arrow on the active column, a dim `ChevronsUpDown`
  on the rest.
- **Removable active-filter chips.** Build a `{key,label,onRemove}[]` from the
  active filter state, render chips with an X each plus a "Tout effacer" that calls
  the global reset - a visible, one-click-removable summary above the table.
- **Loading skeleton that mirrors the layout.** Distinguish loading
  (`data === undefined` -> `<Skeleton>` grid matching KPIs + rows) from unavailable
  (`data && !data.available` -> message), instead of one bare centered string.
  Use stable string keys for the skeleton arrays (biome `noArrayIndexKey`).

## Round-2 skills (premium polish, learned on Connaissances)

- **Premium KPI tile.** Don't cram the sparkline to the right of the value.
  Reuse `components/overview/metric-sparkline.tsx` (`MetricSparkline`,
  full-width, `tone` from `@/lib/overview`) and lay the tile out as: icon+label
  row, big value, then the **full-width** sparkline pinned to the bottom
  (`mt-auto`). `components/cockpit/metric-card.tsx` is the canonical version.
- **Row-click → detail selection.** Backend returns a `details` list (one entry
  per row, each with a `key`). Frontend holds a `selected` key; compute
  `detail = details.find(d => d.key === selected) ?? details[0]`; row
  `onClick={() => onSelect(r.key)}` + highlight the selected row; put
  `key={detail?.key}` on the detail `<section>` so its internal tab state resets
  when you switch source.
- **Dropdown filters, not cycle buttons.** When the user expects a list, build a
  reusable `FilterDropdown({label,value,options,onSelect})` (open state +
  absolute menu). Cycle-on-click is a stopgap.
- **Functional time filter without a time axis.** Add a numeric `fresh_days`
  per row; filter `fresh_days <= selectedDays`; show an honest empty state when
  nothing is fresh enough (don't fake rows).
- **Distribution-as-curve.** No time series (single ingest batch) → plot a real
  per-entity distribution (per-source chunks / citation / hits). Never
  `[value]*7`.
- **Match the normative labels with real values.** Keep the normative field
  labels ("Taux de citation", "Couverture des requêtes", "Dernière …") and fill
  them from the real source; substitute an unsourced field with the closest real
  fact (e.g. "Réponses ancrées" → real document locators, "Dernière utilisation"
  → real `inserted_at` date) rather than dropping or faking it.
- **Map each action label to its real route.** "Gérer le catalogue" →
  `/configurer/signal-catalog`, "Sources & mémoire" / "Voir la fiche complète" →
  `/configurer/sources-memoire`. Dead buttons are a failure.
- **zod is non-strict** — when you change a payload field shape (e.g. `detail`
  object → `details` array, or add `fresh_days`/`attachable`), update the schema
  or the data is silently stripped after parse.

## Round-3 skills (real usage data + tabs)

- **Detail tabs must drive content.** A tab strip whose `tab` state doesn't gate
  the rendered sections is a fake — clicking "Reponses ancrees"/"Parametres"
  showed nothing. Gate each section with `tab === d.tabs[i]`; keep always-on
  actions (detach/toggle) outside the gate so they stay reachable.
- **Generate real traffic to fill usage data.** "Reponses ancrees" / "Derniere
  utilisation" have no source until the agent is exercised. `scripts/
  generate_traffic.py` runs realistic EU-banking questions through the live
  retrieval store (`embed` + `knn_search`, cosine >= 0.55) and records, per
  source, the grounded questions + timestamp to `knowledge_traffic.json`; the
  backend reads it.
- **DONE - real request/response traces from the transcript.** The richer source
  is now wired: `scripts/ingest_transcript_traffic.py` reads the durable
  conversation transcript (`conversation_messages`, `memory/transcript.py`),
  pairs each real user question with the assistant answer that followed it
  (`itertools.pairwise` over rows ordered by `(conversation_id, id)`, deduped by
  question), embeds the question and `knn_search`-attributes it to the source it
  actually retrieves (cosine >= 0.55), and writes the SAME `knowledge_traffic.json`
  but with each entry carrying `{text (question), answer (assistant snippet),
  time}`. The "Reponses ancrees" tab now renders real Q->A pairs. OTel/Phoenix/
  Langfuse spans (`observability/traces.py`) export to Cloud Trace / an OTLP
  collector / console - they are NOT a local queryable store, so the transcript
  table (not the spans) is the right dev source for request/response history.
  Re-run: `PYTHONPATH=.:src .venv/bin/python -m scripts.ingest_transcript_traffic`
  (supersedes the synthetic `generate_traffic` when a transcript exists).
- **Parametres from real config, no run needed.** Fill a "settings" tab from the
  actual config (embedding model `bge-m3`, dim 1024, cosine, top-k, corpus,
  languages) — cheap and fully real.
- **DONE - detail is now a drawer.** The fixed right column became a
  click-to-open **drawer** like `/prouver/audit-logs`: the root is `relative ...
  overflow-hidden`, the table spans full width, and `{detail ? <DetailDrawer
  .../> : null}` renders an `absolute inset-0 z-30 flex justify-end` backdrop
  (close on backdrop `onMouseDown` when `target === currentTarget`) holding a
  `<dialog open aria-modal>` panel (`max-w-[460px]`, `border-l`, slide shadow,
  `onCancel` -> close, X button labelled `common.close`). Key the drawer with
  `key={detail.key}` so the internal tab state resets per source. The selection
  is now `find(d => d.key === selected)` with **no `?? details[0]` fallback** so
  nothing opens until a row is clicked. Verified e2e: 0 dialogs -> row-click
  opens 1 (correct title, 3 tabs) -> X closes back to 0.

## Round-10 skills (Garde-fous: policy.yaml + the live audit log)

- **Two real sources, one page.** The rules come from the compiled guard policy
  (`tessera.guard.decisions.load_policy()` over `policy.yaml`: deny-pattern count,
  pii-pattern count, per-tool `allow`/`requires_confirmation`/`max_calls`/arg
  counts) and the firing stats come from the JSON-Lines audit log
  (`GuardSettings.audit_file`). Key each rule off the **`policy_rule` id the guard
  actually emits** (`prompt_injection.deny_patterns`, `tool.<name>.allow`,
  `memory.{read,write}.governance`) so a single scan attributes decisions/blocks/
  last-fired correctly. The audit log is huge (15k lines) but a one-pass scan is
  fine; reuse the reader shape from `guard_explain.py`.
- **Audit-chain integrity is a free, on-theme real signal.** `verify_audit_chain`
  returns `(verified, length, broken_at)`. Surface it in the watch list and the
  detail's logging block. Ours is genuinely **broken** (multiple restart writers
  resumed the in-proc chain) -> show it honestly; `length` is *entries-until-break*,
  so label that field "Entrees verifiees", NOT total decisions (15 484 vs 400).
- **Relabel slots you can't source instead of faking them.** The normative
  snapshot had "Jeu d'evaluations: Prod Safety Set v2.1" and "Version v3.7.2" with
  no backing store. Repurposed to real facts in the same slots: policy version
  (`v{policy.version}`), `policy.yaml` mtime, total logged decisions, active-rule
  coverage. The "Dernier test" column became "Dernier declenchement" (real
  last-fired); the detail's "Tests"/"Acces RBAC" tabs became "Journalisation"
  (real decision counts + chain status) because there is no test-run or RBAC store.
- **Activity share, not invented coverage.** The per-rule "Couverture" % had no
  meaning; recomputed as the real **share of logged decisions** (`rule.decisions /
  total`). It is dominated (~98%) by a redteam injection campaign -- that is the
  true picture, so keep it and explain it in the watch list ("Campagne
  d'evaluation : N tours d'injection bloques").
- **Right-column detail (not a drawer) when the normative shows one.** Garde-fous
  27 shows a persistent detail column, so selection drives an inline
  `xl:col-span-4` panel (default `details[0]`), tabs gate content
  (Resume/Configuration/Journalisation), and the enable/disable **toggle**
  (`role="switch"`, `aria-checked`) calls the durable `rule-state` mutation.
  Mirror the rest from Connaissances: `useDismiss` popovers, stable-key filtering
  (`category_key`/`status_tone`/`sev_tone`/`mode_tone`), an advanced "Filtres"
  popover wiring the formerly-dead button to the Mode axis, removable chips, pure
  `_assemble` for unit tests, committed e2e.
- **E2e viewport gotcha.** The Playwright project spreads `devices["Desktop
  Chrome"]` (1280x720), which **overrides** the config's `use.viewport`. At 1280
  the filter bar wraps and a `right-0` popover can land over the sidebar -> add
  `test.use({ viewport: { width: 1672, height: 1000 } })` at the top of the spec.

## Round-11 skills (Prompts: the YAML source of truth, read-only)

- **The source IS the page.** Prompts read
  `src/tessera/agent/prompts/{fr,de,en}.yaml` (14 keys x 3 langs) - the same
  files the agent loads. Every value is real: category (editorial grouping of the
  key), languages present, template variables (`{name}` via regex, deduped),
  char/word length per language, file mtime. The detail's **Content** tab renders
  the actual prompt text per language in a `<pre>` with a copy button - the
  highest-signal real feature, and free.
- **Read-only is a legitimate "functional".** Prompts live in Git (edited via PR,
  loaded at start-up); editing files from the UI is out of scope and a fake
  toggle would be a meaningless control. So there is NO mutation endpoint - the
  two axes are satisfied by real data + wired search/filter/select/nav (verified
  e2e). Do NOT invent a durable mutation just to have one; a dead/meaningless
  control is worse than none. State the read-only nature in the module docstring.
- **Pick filters that actually bite.** All 14 prompts are present in all 3 langs,
  so a "Language" filter would never change the row count (a weak control).
  Replaced it with a **Variables** filter (Toutes / Avec variables / Sans
  variables) which genuinely partitions the rows. When choosing a filter axis,
  prefer one whose values are non-uniform across the data.
- **Relabel the KPI/column slots honestly.** No per-prompt version/quality/owner/
  test-run store exists, so the normative's Version/Qualite/Proprietaire/Tests
  columns became Langues / Variables / Source(file) / Longueur(chars), and the
  KPIs became Prompts / Categories / Couverture i18n / Variables uniques /
  Longueur moyenne / Langues manquantes - all computed from the YAML.
- **e2e accent gotcha.** `getByText`/`getByRole({name})` do NOT strip accents:
  the FR detail eyebrow is "Détails du prompt", so a selector written
  "Details du prompt" silently never matches. Copy the accented string verbatim.

## Round-12 skills (Configurations: an editable, persisted settings form)

- **Make the form actually save.** The page already showed real settings
  (model/profile/counts/mtimes) but every control was static and "Enregistrer"
  was dead. Added a durable agent-profile override store
  (`agent_config.json` next to the audit log) with `_DEFAULTS` + `_OPTIONS`, a
  `set_agent_config(changes)` (coerce + merge + save) and `_effective()`
  (defaults <- overrides). `compute` merges overrides over the real defaults, so
  the save round-trips. A `POST .../agent-configurations/config` body
  `{changes:{...}}` validates keys (422 on unknown) and returns the fresh payload.
- **Tag every field as editable or read-only - never fake a control.** Each field
  carries `editable` + a stable `key`; the frontend renders a real control only
  when `editable` (text/textarea/`<select>`/range slider/`role=switch`
  toggle/tag chips), and read-only facts (active model, identifiant, counts)
  stay plain text (the identifiant gets a real clipboard-copy button, not a
  decorative icon). A `<select appearance-none>` + overlaid chevron keeps the
  normative look while being a native, accessible control.
- **Draft-diff state, not a cloned form.** Hold only the pending edits
  (`draft: Record<key, value>`); effective value = `draft[key] ?? serverValue`;
  delete a key from the draft when it returns to the server value so `dirty`
  (and the Save/Annuler buttons) is accurate. On save success clear the draft and
  `setQueryData` the fresh payload; the header shows "Modifications
  enregistrees" when clean, an inline error on failure. Coerce + clamp on the
  backend (`temperature` to [0,1]) so a bad client value can never persist.
- **Slider truth.** The range `value`/`pct` must read from the draft number when
  present (not the server `num`), or the thumb won't move as you drag. Recompute
  `pct` from the live number for the fill gradient.
- **A field whose default is settings-derived can't live in a static dict.**
  `default_language` is persisted but its base is `settings.default_language`, so
  it is kept out of `_DEFAULTS` (special-cased in `available_config_keys`,
  `_coerce`, and read straight from the overrides in `compute`).
- **Configurations stays FR-only** (it never had a `lang` param); don't localize
  it just for parity - match the page's existing contract.

## Round-13 skills (A faire / A traiter: a shared derived backlog)

- **Two queue pages, one real source.** "A faire" and "A traiter" were both
  fixtures. Instead of inventing a task store, derive the backlog from artifacts
  that already exist: `tessera.observability.operator_items` turns every **failed
  eval case** (`load_eval_snapshot().sessions` where `not passed`) into a queue
  item (id = `case_id.lang`), mapping category -> priority/source and a
  per-priority SLA target; `now`-relative age/overdue are computed on read. One
  shared module feeds both `inbox.py` (a-traiter) and `agent_a_faire.py`, each
  shaping it to its own existing payload.
- **Durable status/assignee = the functional axis.** A single
  `operator_items_state.json` + `set_item_state(id, status?, assignee?)` backs
  both pages; each page got a `.../item-state` POST (404 on unknown id) returning
  its fresh payload. a-traiter wires a status-badge that cycles
  todo->in_progress->resolved; a-faire wires row-click selection + the detail's
  "Prendre en charge"/"Marquer resolu"/"M'assigner" buttons.
- **Don't let SLA breach mask workflow status.** First cut folded "overdue" into
  the status badge, so "Prendre en charge" on an overdue item showed no visible
  change (77/84 items are overdue - the eval run is hours old). Separate the two:
  the **status badge** reflects only the durable workflow state (A traiter / En
  cours / Resolu); the **SLA cell** carries the breach ("En retard", red). Now
  the action is visibly effective. (Unit-tested explicitly.)
- **Honest distributions over fake sparklines.** No per-KPI time-series exists,
  so the compact KPI sparkline uses a real per-priority/per-type **distribution**;
  KPI deltas with no historical basis are `-`, and "avg handling time" is `-`
  (not instrumented) rather than a fabricated number.
- **Endpoint ordering with a shared Pydantic body.** `_ItemStateBody` lives next
  to the inbox route; the a-faire mutation must be declared **after** it (FastAPI
  resolves the annotation at decoration time), or place the model earlier.

## Round-14 skills (Synthese: a dashboard sourced end to end, no fixture)

- **A multi-panel dashboard is "real" panel-by-panel, with one shared rule:
  every value traces to an artifact or renders an honest relabel.** Synthese had
  ~13 panels, mostly invented literals (Conversations "1 842", Satisfaction
  "4,6 / 5", prompt versions "v3.2", channel %s, a fake timeline). The fix wires
  each panel to a real source: transcript (`conversation_messages`) for
  conversations / turns / messages / activity feed / recent conversations;
  `eval_data` for resolution / latency / failures / escalations / topics /
  performance / model; pgvector `documents` for knowledge sources; the prompts
  YAML for active prompts; the `agent/tools/` files for capabilities; the
  persisted agent config for the profile; `verify_audit_chain` for an alert.
- **Relabel the unsourceable slots to a real distribution; never keep the fake.**
  No per-channel or satisfaction store exists, so "Utilisation par canal" became
  "Repartition par langue (evaluation)" (real eval language mix) and the
  Satisfaction/Active-users/Sessions KPIs were replaced by real ones
  (Conversations, Tours utilisateur, Messages, Sources de connaissances). The
  fabricated change "Timeline" became "Derniers changements" built from real
  file mtimes (prompts, policy.yaml) + ingest `inserted_at` + eval `run_at` +
  the last transcript activity, sorted newest-first.
- **The dashboard's functional axis is navigation, not mutation.** Like Prompts
  (read-only), there is no durable mutation here -- the interactions are the CTAs
  and quick-config shortcuts, which must be **real `Link`s** to the sibling agent
  pages (a dead button is a failure). Added an optional `ctaHref` to each panel
  and a `{label, href}[]` quick-config; the command-bar "Exporter" button (no
  real export target) was removed rather than left dead.
- **psycopg parses `%` in the SQL string itself.** An `ILIKE '%escalad%'` literal
  raises `only '%s','%b','%t' are allowed as placeholders, got '%e'` even when
  the query has unrelated `%s` params. Double every literal percent (`'%%...%%'`)
  or pass the pattern as a parameter.
- **Normalize every datetime to tz-aware before sorting/comparing.** The timeline
  mixed DB `created_at`/`inserted_at` (tz-aware) with `Path.stat().st_mtime` (UTC
  aware) and `snap.run_datetime()` (could be naive) -> "can't compare
  offset-naive and offset-aware". A tiny `_aware(dt)` that attaches UTC to naive
  values, applied in the formatter and the timeline builder, fixes it.
- **Sparkline honesty on a gappy time axis.** The transcript spans ~16 days with
  empty days, so the KPI series uses the last 7 **day-buckets that had activity**
  (`GROUP BY date_trunc('day', ...)`), and the delta is "vs jour precedent"
  (previous bucket), NOT "vs veille" -- buckets skip empty calendar days, so
  "yesterday" would be a lie. eval-derived KPIs (resolution/latency/errors) keep
  their chronological 7-bucket series; the sources KPI uses the real per-category
  chunk distribution (no time axis).
- **Test the pure assembler; abstract the DB behind the fetch.** `_assemble(snap,
  tx, chain_ok, now)` is I/O-free (the transcript dict `tx` is the only DB-shaped
  input), so `tests/unit/test_agent_synthese.py` feeds a synthetic snapshot +
  transcript and asserts the 7 KPIs, profile, language mix, escalation heuristic,
  singular/plural "echange(s)", timeline ordering, alert tone and the wired
  hrefs -- with zero Postgres. (The FS reads -- tools/prompts/policy -- are
  deterministic repo files, so they stay un-mocked.)
- **e2e: a label can collide with a nav tab.** "Garde-fous" is both a quick-config
  link and a top nav tab -> scope the click to the panel (`page.locator("section",
  { hasText: "Configuration rapide" })`) before `getByRole("link", {name})`.

### Round-14 quality pass (sparkline reuse, period wiring, skeleton)

- **KPI tiles must use the canonical full-width sparkline.** The first build
  crammed a 64px `<svg>` into the tile's bottom-right; the normative (and the
  Round-2 skill) want the **full-width `MetricSparkline`** pinned to the bottom
  (`mt-auto`), tone from `kpi.good`. Reusing `components/overview/metric-sparkline.tsx`
  instead of a bespoke `<path>` matched the normative immediately. Group integer
  KPIs French-style (`1008 -> "1 008"`, `f"{n:,}".replace(",", " ")`).
- **A period selector that changes nothing is a dead control -- and a lie.** The
  shared `TemporalRail` shows "Periode : 7 jours" but the synthese `useQuery`
  keyed on `["agent-synthese"]` ignored it, so the page showed all 16 days of
  transcript under a "7 jours" label. Fix: thread `temporal.periodKey` into the
  queryKey + `fetch(?period=)`, map `h24/d7/d30 -> 1/7/30` days in the route, and
  filter every transcript figure to `created_at >= now() - interval 'N days'`
  (the eval run is a fixed snapshot; knowledge counts are period-agnostic). Now
  h24/d7/d30 genuinely return 3 / 99 / 1008 conversations. NOTE the rail's period
  `<select>` only renders in **replay** mode (live mode shows the period as text);
  the e2e must click "Relire a T" first, then `selectOption`. The as-of-T
  scrubber stays inert here (ADR 0011 Phase 2, deferred) -- wiring the period
  window is the bounded, honest win.
- **An interval literal cannot be a psycopg placeholder.** `interval '%s days'`
  fails; interpolate a **validated int** (`int(period_days)`) and silence the
  resulting `S608` with `# noqa: S608` on the flagged string line (the diagnostic
  points at the SQL string start, not the `cur.execute(` line).
- **Distinguish loading from unavailable.** `data === undefined` -> a
  `SyntheseSkeleton` mirroring the KPI grid + card row (stable string keys, not
  array indices); `data && !available` -> the unavailable message. Per-panel
  empty states (`rows.length === 0 -> <EmptyRow/>`) on the transcript-fed cards
  so a narrow period window degrades gracefully (new i18n key `empty` x3 locales).

## Round-15 skills (Etat a date: as-of reconstruction + premium polish)

- **As-of-T from the streams that actually have history.** The corpus is one
  ingest batch (no real version history), so reconstruct point-in-time state from
  the streams that DO carry time: the guard **audit log** (`occurred_at`, real
  multi-day stream) and the **transcript** (the anchored "original response" =
  the real Q->A at/<= T). Knowledge accessibility flips at the single ingest
  boundary; say so, don't fabricate per-source versions.
- **"Diff vs current" must be a real two-point computation, never invented
  version numbers.** Compare T against now from real signals: decisions logged
  after T (`audit_total - decisions_at_T`), file mtime vs T (prompt/policy
  changed after T?), eval `run_at` vs T. Emit each line **typed** `{kind, text}`
  with kind in `added|removed|changed|unchanged`, and render a colour-coded glyph
  (`+` emerald / `-` red / `~` amber / `=` muted) — the normative diff has a
  colour code, not plain bullets.
- **Homogenise a row of cards so separators line up.** Equal-height cards (grid
  `items-stretch`) is not enough — give each card the **same number of rows** and
  make every row a single fixed-height line (`dt` whitespace-nowrap + `dd`
  truncate) so the mid-card separator ("Diff vs etat actuel") sits at the same y
  across all cards; bottom-align the CTAs with `mt-auto`. Drop/relabel rows to
  reach a common count (e.g. add a real "Statut vs actuel" to fill a 5th row)
  rather than leaving ragged cards.
- **Match the normative's icons, and give each card icon its own colour.** Read
  the normative glyphs (FileText / MessageSquare / ShieldCheck / Terminal /
  Package / History / Bookmark) instead of one generic icon, and pass a per-card
  `iconClass` (violet / sky / emerald / amber / cyan / fuchsia / rose...) so the
  header logos are visually distinct, not a uniform violet.
- **Place page-level actions without wasting a row.** The shared `Topbar`
  `actions` only do predefined behaviours (no client handlers), and a dedicated
  buttons row wastes vertical space. Put "save / export" type actions on the
  **right of an existing row** (e.g. the honesty banner row, `flex` with the
  banner `flex-1`); keep the primary action (Reconstituer) inline at the end of
  the field row so it stays on the same line as Tenant/Agent.
- **The Topbar description is single-line (`truncate`).** Page subtitles must be
  short or they get cut ("... une heure do"). Keep the one-liner terse; let a
  banner carry the long explanation.
- **Section-header right slot.** A `Panel` that needs a status chip on the title
  line (e.g. "Integrite verifiee" next to "Etat reconstitue a T") takes a `right`
  prop rendered in the header flex row — don't drop the badge below the content.

## Round-16 skills (Console: wiring a live-chat debug surface end to end)

- **A "real data" page can still be riddled with dead buttons.** Console already
  streamed the live agent (real SSE turns, real debug panels) but its chrome was
  inert: StatusBar `Relire a T` / `24h` / `Nouvelle session`, the KPI rail's
  `Timeline incidents`, four footer actions, the panel `Voir toutes` ctas, and
  the thumbs feedback all had no `onClick`. "Real data" and "real interactions"
  are independent axes (Step 0) - audit EVERY button, not just the metrics.
- **Wire by stable key, dispatch in the parent.** Restructured the backend
  `footer_actions` from `["label", ...]` to `[{key, label}]` (keys
  replay/compare/export/close) so the frontend dispatches real behaviour by key,
  not by index or display string (which break under i18n). `compare` renders as
  a locale-aware `<Link>` to `/prouver/etat-a-date`; the rest are buttons calling
  a parent `onFooterAction(key)`.
- **Each action maps to a genuinely real effect.** replay -> re-send the last
  user turn through the live agent; export -> a client-side JSON `Blob` download
  of the current transcript; close/new-session -> `resetSession`; the StatusBar
  `Relire a T` -> `temporal.changeMode("replay")`; the `24h` button -> a real
  `<select>` bound to `temporal.periodKey` (h24/d7/d30); KPI `Timeline incidents`
  + panel ctas -> `<Link>`s to `/prouver/audit-logs` / `/agent/connaissances`. No
  control left that doesn't do what it says.
- **Durable feedback needs a real key; the live envelope provides one.** Thumbs
  up/down persist to `console_feedback.json` (next to the audit log) keyed by the
  real `conversation_id` from the SSE end-envelope + the assistant turn index;
  `record_console_feedback(conv, turn, rating)` toggles off when the same rating
  is re-clicked, and the GET seeds the query so a reload shows the saved rating.
  The seed-transcript example (a canned illustrative turn, NOT a logged
  conversation) has NO rateable identity, so its thumbs row was removed rather
  than left dead - don't fake feedback on a non-real turn.
- **Accent the emitted French even on a "debug" surface.** The console module
  shipped accent-free ("Qualite & securite", "Sources utilisees", "Trace en
  temps reel", "Genere", "Autorise", "Francais", "non-conformite") - same
  non-negotiable as every other page; fix the module strings (ASCII apostrophes
  keep RUF001 happy). `tests/unit/test_console_feedback.py` + `e2e/console.spec.ts`
  cover the store and the non-LLM controls (the chat stream needs Ollama).

## Round-17 skills (Historique: a real-data table that was inert)

- **"Real data, read-only" is not an excuse for a dead table.** Historique
  already showed real eval-run numbers but every control was cosmetic: the search
  was a `<span>`, the four filter "selects" were dead buttons, the headers did not
  sort, pagination was a static `[1,2,3...]`, and the detail was frozen on one
  session (longest-latency `focus`), ignoring row clicks. Same bar as every other
  table - the Connaissances treatment (controlled search input, key-based
  `FilterDropdown`s, sortable headers with `aria-sort`, client pagination footer,
  row-click selection) is mandatory even when the data is immutable.
- **Send ALL rows + raw keys so the client owns filter/sort/pagination.** The
  backend stopped pre-slicing to 12 rows; it now emits every session (174) with
  display cells AND raw fields (`category_key`/`lang`/`status_tone`/`score_num`/
  `latency_ms`/`tokens_num`) so filtering/sorting key off stable values, not i18n
  strings. Sort accessors are keyed by **column index** (a `rowSortKey` switch),
  numeric columns in a `Set`, `localeCompare(..., "fr")` for the rest.
- **Build the whole detail from the selected row - no second round-trip.** Each
  row also carries everything the detail needs (`case_id`, `escalation`,
  `tools_count`, `input/output_tokens`, the real `question` + `response`), plus a
  shared `meta` (model, catalogue) and static `detail_labels`. Row click sets the
  selected sid; the right-column detail (the normative shows a persistent panel,
  like Garde-fous Round-10 - so a panel, not a drawer) rebuilds from that row,
  with **tab-gated** content. The Messages tab shows the real Q->A (the model's
  actual answer) - the highest-signal real feature, free from the row payload.
- **Wire the chrome to real effects or real routes.** Export -> a client-side CSV
  `Blob` of the (filtered, sorted) rows; the action bar `Comparer`/`Creer un
  rapport` -> `<Link>`s to `/prouver/etat-a-date` / `/prouver/evidence-store`; the
  quick actions dispatch by key (failed -> set the status filter to `bad`, scores
  -> `/agent/evaluations`, export -> CSV, evaluate -> `/agent/console`); the
  panel ctas carry a `cta_href`. No dead buttons left.
- **Same accent + test discipline.** Accent every emitted + hardcoded FR string
  ("Reussie"->"Réussie", "Messages echanges"->"Messages échangés", "Duree
  totale"->"Durée totale", "Reinitialiser"->"Réinitialiser"); split a pure
  `_assemble(snap)` for `tests/unit/test_agent_historique.py`; cover
  filter/sort/row-detail/pagination in `e2e/historique.spec.ts`. E2e gotcha: the
  filter trigger's accessible name is "Statut Tous" (label+value) and collides
  with the "Statut" sort header - target the full name.

## Round-18 skills (Configurations: the last three dead buttons + an accent trap)

- **A "done" page can still hide dead buttons - re-scan with grep.** Configurations
  was Round-12 "real + functional" yet `grep 'type="button"'` surfaced three with
  no handler: the header kebab (`...`), the Tags "Archiver cet agent", and the
  history "Voir tout". Wired all three: the kebab -> a `useDismiss` menu with a
  real JSON export (`Blob` download of the payload) + a `<Link>` to advanced
  settings; the history cta -> `<Link>` to `/prouver/audit-logs`; archive -> a
  **durable** toggle (new `archived` key in the config store) on its own mutation
  (so it never clobbers pending field edits), flipping the status badge
  Actif/Archivé + the button label, persisted across reload.
- **Accenting a localized enum value silently breaks any string-equality logic.**
  The toggle inferred its boolean from `field.value === "Active"`; accenting the
  backend value to "Activé" turned every toggle permanently off (the compare
  failed). When you accent an option/enum string that doubles as a comparison
  key, grep every `=== "OldValue"` and the e2e `getByRole("switch",{name})` /
  `selectOption` that names it, and fix them in lockstep. Better still, drive
  booleans from a real boolean, not a display string - but at minimum keep the FE
  compare and the BE value spelled identically.
- **e2e: archived shows in two places.** Once archived, both the status badge and
  the status-row value read "Archivé" -> `getByText(...).first()` to avoid a
  strict-mode violation; restore the flag at the end so the durable profile stays
  clean.

## Round-19 skills (Evaluations: the Historique twin, same rebuild)

- **Same inert-table pattern, same fix.** Evaluations was the structural twin of
  Historique (real eval-run numbers, dead search `<span>` + dead filter buttons +
  static pagination + frozen `data.detail`). Applied the identical treatment:
  emit every category row with stable keys (`category_key`/`quality_key`/`is_fact`
  /`score_num`/`pass_rate`/`passed`/`total`/`failed`), a shared `meta` (model,
  catalogue, languages, run score, escalations, tool calls, RBAC) and static
  `detail_labels`; the frontend owns search/filters/sort/pagination and rebuilds
  the tab-gated detail from the selected row.
- **Pick filters that bite (again).** Every row's Statut is "Actif" and owner is
  "Tessera Eval", so the normative's Statut/Proprietaire filters would never
  change the count. Replaced them with Type (real catalogue categories), Quality
  band (Bon/Moyen/Faible from the score) and Hallucinations (with/without =
  `is_fact`) - all partitioning. Search + the three dropdowns + sortable headers
  + pagination, verified e2e.
- **Wire the snapshot/quick/cta chrome.** The snapshot bar's `Voir a date` ->
  rail replay; `Comparer` -> `<Link>` to `/prouver/etat-a-date`; quick actions
  dispatch by key to real routes (`/agir/curation-eval-set`,
  `/prouver/etat-a-date`, `/agent/historique`); the watch cta carries a
  `cta_href`; the top `Creer une evaluation` -> the eval-set curation page. No
  dead button remains.
- **Accent the whole localized-but-French module.** Sécurité/Confidentialité/
  Conformité/Factualité types, "Derniere execution"->"Dernière exécution",
  "Modele evalue"->"Modèle évalué", "Eleve"/"Maitrise"->"Élevé"/"Maîtrisé",
  "Fidelite"->"Fidélité", "Complete"->"Complète". `tests/unit/test_agent_evaluations.py`
  asserts the keyed rows/options/accents; `e2e/evaluations.spec.ts` covers
  filter/sort/row-detail/quick-link.

## Status of the agent pages (update as you go)

- **Real + functional:** A faire + A traiter (shared `operator_items` backlog =
  failed eval cases, per-priority SLA, durable status/assignee via the item-state
  endpoints; search + filters + status mutation; `tests/unit/test_operator_items.py`
  + `e2e/{a-faire,a-traiter}.spec.ts`). Configurations (real settings/repo
  introspection +
  editable agent-profile overrides persisted via `agent_config.json` and the
  `config` endpoint: name/description/language/owner/behaviour selects +
  sampling sliders/routing/parallel-tools toggle/tags, dirty-gated Save+Annuler;
  `tests/unit/test_configurations.py` + `e2e/configurations.spec.ts`). Prompts
  (live `prompts/{fr,de,en}.yaml` inventory:
  categories, languages, template variables, lengths + the real prompt text per
  language in the detail Content tab; search + category/variables filters +
  removable chips; FR/DE/EN; read-only by design - no UI mutation;
  `tests/unit/test_prompts.py` + `e2e/prompts.spec.ts`). Garde-fous (policy.yaml
  rules + live audit-log firing
  stats + chain integrity, durable enable/disable toggle, search + category/
  status/severity dropdowns + advanced Mode popover + removable chips, row-click
  detail with tab-gated content, FR/DE/EN, `tests/unit/test_garde_fous.py` +
  `e2e/garde-fous.spec.ts`). Connaissances (pgvector inventory, durable
  attach/active, search/type/status filters, Rattacher, real probe sparklines,
  click-to-open detail drawer, transcript-grounded answers, and an **advanced
  Filtres popover** wiring the formerly-dead "Filtres" button to real extra axes
  -- langue (FR/DE/EN from `agg.langs`), couverture minimale, "avec echanges
  ancres" (real transcript traffic count) -- with a live count badge + reset).
- **Real + functional (dashboard, nav-wired):** Synthese (every panel sourced
  end to end -- transcript conversations/turns/messages/activity/recent convs,
  eval resolution/latency/failures/topics/performance/model, pgvector sources,
  prompts YAML, real tool capabilities, agent-config profile, audit-chain alert;
  unsourceable slots relabelled to real distributions -- language mix, change
  timeline from file mtimes/ingest/eval; CTAs + quick-config are real `Link`s;
  `tests/unit/test_agent_synthese.py` + `e2e/synthese.spec.ts`).
- **Real data (read-only):** Evaluations, Historique (eval run).
- **Real + functional (prouver):** Etat a date (`/prouver/etat-a-date`) -
  point-in-time reconstruction: original Q->A from the transcript at T, guard /
  prompt&model / release cards with real two-point diffs, sources-at-T table
  (Connaissances treatment + drawer), durable snapshots, premium homemade
  calendar; `tests/unit/test_etat_a_date.py` + `e2e/etat-a-date.spec.ts`.
- **Still fixture / blocked:** Other pages' filters/exports/RBAC are static.
