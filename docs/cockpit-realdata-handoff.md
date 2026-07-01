# Cockpit "make everything real" — handoff plan

**Mandate (user, night of 2026-07-01):** wire **every** "données de démonstration"
(fixture) page to **real data, everywhere**, and finish the **untouched pages / sub-tabs**
(explicitly called out: Qualité IA sub-tabs, Sécurité, Fiabilité). *« Il faut absolument
tout faire. »* User reviews tomorrow. This file is the durable roadmap — a fresh session
reads it first and executes systematically.

## Method (MANDATORY — read before touching anything)

1. **Read `docs/functional-page-playbook.md` first.** The recipe: real data source → backend
   build → durable mutation endpoint → wired frontend → real sparklines → probe for derived
   metrics → e2e verify. **Never call a deterministic fixture "real."** Always separate
   "displayed values are real" from "interactions are wired," and say which holds.
2. **Directive (user amendment): if no real source exists → CREATE the source.** The goal is real
   data *everywhere*; flagging synthetic is NOT the escape hatch. "Create the source" = build a
   genuine backing store + a real computation over real artifacts + a wired (and, where it mutates,
   durable) endpoint — following the functional-page-playbook. This is legitimate engineering, and
   is **categorically different from fabricating** (hardcoding fake numbers and presenting them as
   real, which stays forbidden). Examples: an automations page needs a real rule/execution store →
   build one (persist rule runs, read them back); tail-sampling needs real keep/drop decisions over
   real traces → implement the policy against the spine.
   **`synthetic` is a LAST-RESORT stopgap only** when the source genuinely cannot exist yet this
   session (e.g. it needs infra that isn't available) — and even then it is temporary, left with a
   TODO to build the source. Registry = `src/tessera/observability/spine/capabilities.py`
   (`_cap(id, …, synthetic=True)`) mirrored in `webapp/frontend/lib/signal-registry.ts`; banner =
   `webapp/frontend/components/cockpit/synthetic-notice.tsx` (keys off `isSynthetic(id)`).
3. **ⓘ explainers:** reuse `components/cockpit/metric-info.tsx` (`MetricInfo{title,what,how,source}`)
   via a local `ExplainInfo({k,title})` helper reading `<page>.explain.<k>.{what,how,source}`.
   Content MUST be grounded in the real backend computation (verify before writing).
4. **Gate twice-green** before each commit: backend `ruff` + `ruff format --check` (baseline = 32
   pre-existing unformatted files, none mine) + `mypy` strict + `pytest`; frontend
   `./node_modules/.bin/tsc --noEmit` + `biome check <my files>` + `vitest run`. Perf probe
   (`node scripts/perf-probe.mjs`) if the snapshot read model is touched.
5. **Verify live** on `:3097` (Next dev) → `:8392` (backend). Playwright headless via
   `node_modules/playwright-core` (see scratchpad scripts from the legibility pass for the pattern).
6. **Commits: targeted paths only, NEVER `git add -A`** (codex shares the working tree). Push to
   `origin/feature/redesign` (the cadence this session established; the remote already has all of
   it). Isolate `messages/*.json` edits with the surgical Python approach
   (`json.load(..., object_pairs_hook=OrderedDict)`, add keys, `json.dump(indent=2, ensure_ascii=False)`)
   — this keeps the diff to added keys and avoids codex-WIP collisions.
7. **Pre-existing failures to ignore** (fail identically on pristine HEAD, NOT regressions):
   `test_firewall_adapter::…account_balance_allowed_for_known_customer`,
   `test_memory_persistent::…consent_gate_blocks_write`, `…erase_subject_is_total`.

### Launch commands
- Backend: `PYTHONPATH=src:. TESSERA_ENVIRONMENT=local .venv/bin/uvicorn tessera.api.main:build_app --factory --host 127.0.0.1 --port 8392` (background, `dangerouslyDisableSandbox=true` — sandbox blocks the bind). Health: `curl :8392/healthz`.
- Front: `./node_modules/.bin/next dev -p 3097` from `webapp/frontend` (background, sandbox off).
  Note: `package.json` `dev` script is `-p 3099`; the user works on **3097**.

## Inventory A — BACKEND FIXTURE modules (make real, or keep honestly flagged)

Every module below is a deterministic fixture today (hardcoded constants / literal KPIs). For
each: the real-data path and whether that real source already exists in the repo.

| module | route | real-data path | notes |
|---|---|---|---|
| `policies.py` | `configurer/politiques` | real `policy.yaml` + guard decisions + guardrail catalogue | **already flagged synthetic (`c5d8077`)**. To make real: read the live policy set + guard-decision counts. |
| `incidents.py` | `agir/incidents-playbooks` | **guard-deny clusters + low-score turns** (audit ledger + score store) — ADR 0015 explicitly suggests this | flagged synthetic (Phase E). Real path EXISTS. |
| `curation.py` | `agir/curation-eval-set` | `eval.sets` + `load_eval_snapshot` failed cases + corpus lineage | flagged synthetic. Real path EXISTS (eval reports + `operator_items` already derive real backlog). |
| `automations.py` | `agir/automations` | **CREATE a real automations/rules store** (persist rule definitions + real execution records; read them back). Reuse patterns from `operator_items.py` (durable JSON store) / `governance_feed.py` / `guard_retraction.py`. | flagged synthetic today → **build the source** (user directive). |
| `replay_shadow.py` | `agir/replay-shadow` | `replay.py` `recent_bundles` (REAL) + `lineage.py` | flagged synthetic. **Partial** real path (bundles are real; deviation/shadow metrics need building). |
| `proofs.py` | `prouver/evidence-store` | audit ledger + evidence store (`etat_a_date.py`, `audit.py`, `prouver/audit-logs` are REAL) | fixture; real path EXISTS. |
| `parameters.py` | `configurer/parametres` | `get_settings()` + real policies + integrations + model catalogue | fixture; real path EXISTS (mostly real on neighbouring pages). |
| `assistant.py` | Assistant page (Chat/Console) | transcript (`transcript.load_transcript`) + reporter debug + eval scores. **Console debug already made real** (see memory `Console debug surfacing`). | fixture overview; real path EXISTS. |
| `tail_sampling.py` | Observabilité sub-tab (?) | **CREATE real tail-based sampling**: record actual keep/drop decisions per finished turn (slow / low-faithfulness / error → keep) into a durable store; read the real kept/sampled tallies. Spine/Phoenix span outcomes are the input. | fixture → **build the source** (user directive; more infra, but do it). |
| `connectors.py` | `configurer/connecteurs` | **MIXED** — total/active/standby/mode already REAL; detail rows are reference | partial; ⓘ already added (`23167c8`). |

## Inventory B — FRONTEND sub-tab reality (from the mapper)

**Already REAL — do NOT rebuild** (corrects the initial perception):
- **Qualité IA** (`surveiller/qualite-ia`) — all 6 sub-tabs REAL (Vue d'ensemble / Signaux / Runs /
  Cas échoués / Modèles / Juge), each on live fetchers (`fetchSLO`, `fetchScoreSeries`, `fetchRuns`,
  `fetchFailedRuns`, `fetchModelComparison`, `fetchJudgeDrift`, …).
- **Sécurité & privacy** (`surveiller/securite-privacy`) — single page, all 6 zones A–F REAL.
- **Conformité** (`surveiller/conformite`) — all 8 tabs REAL (`fetchCompliance` + `CatalogTabView`,
  TabStrip functional).
- **Agent sub-pages** (`agents/[id]/…`) — all 8 REAL (synthese/console/evaluations/historique/
  garde-fous/prompts/configurations/connaissances), each on `/observability/agent-*`.

**The genuine frontend gap — DEAD / COSMETIC TAB BARS** (tabs render but don't switch; the page is
one always-rendered content blob, no `useState(activeTab)`):
- **Fiabilité & coût** (`components/reliability/reliability-dashboard.tsx`, tab bar ~line 440) — 7
  tabs (Vue d'ensemble / Fiabilité / Coût / Performance / Quotas / Incidents / Capacité) all dead.
- **Amélioration** (`components/improvement/improvement-dashboard.tsx`, tab bar ~line 229) — 5 tabs
  (Vue d'ensemble / Plan / Curation / Expériences / Dépôt) all dead.
  → Work: add `activeTab` state + conditional per-tab views, each reading a real endpoint (both
  pages already fetch real overview data — reorganise it into real per-tab views + fill the tabs
  that have no data yet, e.g. from `reliability.py` / `improvement.py`, which ARE real modules).

## Suggested execution order (highest value first)

1. **Fiabilité & coût + Amélioration dead tabs** — user-named, real modules already behind them;
   wire `activeTab` + real per-tab views (playbook step "interactions wired").
2. **Backend fixtures with an existing real path** (Inventory A): proofs, parameters, assistant,
   curation, incidents, replay_shadow — wire to their real sources.
3. **Backend fixtures with a thin/infra path**: automations, tail_sampling — **CREATE the real
   source** (durable store + real computation), per the user directive. Synthetic flag is only a
   temporary stopgap with a TODO if the source truly can't be built this session.
4. **policies** — currently flagged synthetic; **make it real** from `policy.yaml` + guard decisions
   + guardrail catalogue (the source exists).
5. Qualité IA / Sécurité / Conformité / Agent pages — **already real, leave them.**

## Progress log (this session, pushed to origin/feature/redesign)

- Legibility pass complete: `6b01a19` `8d69c4c` `23167c8` `67c9f0b` `9bb783d` `c5d8077` `4f97ce8`
  (per-control ⓘ, "Politique actuelle" honest badge, users/connectors ⓘ, security fabrication fix +
  improvement i18n, composite-card ⓘ, **policies flagged synthetic**, automations mode i18n).
- ADR 0015 (runtime telemetry spine) Phases A–F complete earlier this session.

## Session 2 — resumed after /clear (LOCAL commits, NOT pushed)

Three real deliverables. **Commits are local on `feature/redesign`, unpushed** (the
strong "NE JAMAIS POUSSER" signal across memory + the sweep note's "re-confirm push
intent if unsure" → held for user review; earlier this-session push cadence not assumed).

- **Fiabilité & coût dead 7-tab bar → real** (`e189335`). The tab bar was static
  `<span>`s over one always-rendered 4-zone blob (no `activeTab`). Now `role=tablist`
  buttons drive `activeTab`; each of the 7 tabs is a curated real view (`role=tabpanel`)
  over the same live `compute_reliability` report. `e2e/fiabilite-cout.spec.ts` (3 tests).
- **Amélioration dead 5-tab bar → real** (`bb4d9a9`). Same dead-`<span>` pattern; now real
  tab switching + the dead rail controls wired (`Préparer le plan` → jumps to the Plan tab;
  the 3 static "sensitive action" rows → real `Link`s). `improvement.cta` i18n +
  `e2e/amelioration.spec.ts` (4 tests).
- **Paramètres overview → real** (`45b5c09`). Was an **unflagged** fixture (fabricated 238
  params / 54 policies / 42 integrations + invented per-row authors, no synthetic banner).
  Rewired to live state, **same payload shape** (frontend untouched): KPIs from the compiled
  guard policy + model catalogue + configured integration endpoints; `config_version` from the
  real policy version + `settings.environment` + policy.yaml mtime; `recent_params` carry the
  actual settings values; compliance/usage from real settings. `tests/unit/test_parameters.py`
  proves derivation. Verified live on `:8392`.

### SHARPENED FINDING — the fixtures are subsystem-scale (corrects Inventory A's optimism)

Reading incidents / policies / automations / curation / proofs in full established a
consistent, load-bearing truth: **each depicts a full enterprise subsystem that does NOT
exist in this demo.** The demo backend has: `policy.yaml`, a hash-chained audit log, eval
reports, the transcript, the pgvector corpus, replay bundles, and the score store. The
cockpit UI, by contrast, renders incident-management (MTTA/MTTR, running-playbook step
timelines, postmortem RCAs), policy-versioning + approval workflow (version timelines,
YAML diffs between versions, approvers, impact simulators), a curation pipeline (collect →
dedup → PII-mask → dual-control → promote), an automation engine (rule executions, approval
queue, savings), and evidence-export/SIEM (exporters, destinations, retention). **~half of
each page is derivable from real signals; the other half implies a subsystem.** "Making them
fully real" = *building those subsystems* (a multi-day feature each), not a fixture-wiring pass.

Two corollaries for whoever continues this:
1. **Shape-preserving backend real-ification only works where every frontend LABEL stays
   true under a real value.** Paramètres worked because its labels ("Policies", "Models",
   "Rate limit") are true of real counts. Where the i18n label encodes a fixture concept
   (config-state "drafts/deprecated", "approval history", "export destinations"), you MUST
   edit the frontend i18n in lockstep — that's a full Round, not a value swap.
2. **Honesty state (verified in `signal-registry.ts`):** incidents, curation, automations,
   replay_shadow, policies are **already flagged synthetic** (they show demonstration
   banners — honest). The unflagged fixtures that presented fabricated numbers as real were
   **parameters (now REAL), proofs, assistant**. `tail_sampling` already derives from real
   replay bundles (`analyze_sampling(recent_bundles())`) — verify + surface, don't rebuild.

### Recommended next steps (scoped, highest-integrity first)

1. **proofs** (unflagged) — make the derivable core real like Paramètres: `verify_audit_chain`
   (genuinely real + on-theme), artifact counts = real audit entries + eval scores + replay
   bundles; relabel/flag the exporter/destinations/retention chrome (needs a SIEM subsystem).
2. **assistant** (unflagged) — it is a canned *localized sample* conversation, not fabricated
   aggregates. Either swap in a real recent transcript exchange (single-language, real
   latency/tokens/sources) or label it explicitly a "sample" (decide the localization tradeoff).
3. **The flagged subsystem pages** — per page, decide BUILD vs keep-flagged. The cleanest real
   build is **curation**: a durable curation-decision store (promote/review/reject) over the
   real failed-eval-case candidates (mirror `operator_items` exactly). Each is one Round.
