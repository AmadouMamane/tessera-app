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

## Status of the agent pages (update as you go)

- **Real + functional:** Connaissances (pgvector inventory, durable
  attach/active, search/type/status filters, Rattacher, real probe sparklines,
  click-to-open detail drawer, transcript-grounded answers, and an **advanced
  Filtres popover** wiring the formerly-dead "Filtres" button to real extra axes
  -- langue (FR/DE/EN from `agg.langs`), couverture minimale, "avec echanges
  ancres" (real transcript traffic count) -- with a live count badge + reset).
- **Real data (read-only):** Evaluations, Historique, Synthese (eval run);
  Configurations (repo introspection — form not yet persisted).
- **Still fixture / blocked:** Garde-fous (needs guard-decision logs), Prompts
  (real source = prompt YAML; per-prompt scores unsourced). Other pages'
  filters/exports/RBAC are static.
