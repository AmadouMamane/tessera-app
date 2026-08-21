# Tessera — Claude Code context

This file is read automatically by Claude Code at the start of every session in this repository. Its purpose is to give the assistant a stable, versioned understanding of what Tessera is, what it is not, and how work must be done here. Keep it concise. When a decision becomes load-bearing enough to deserve its own page, capture it as an ADR under `docs/decisions/` and link it from this file instead of expanding the prose here.

## Pitch

Tessera is a production-grade reference implementation of a multilingual (FR / DE / EN) banking support LLM agent for the European retail market. The agent is grounded in EU regulatory corpora (DORA, CNIL, BaFin, GDPR), enforces runtime guardrails through a first-party guard at a single tool-call chokepoint, ships with a non-regression harness over 63 publicly documented agent failures, and is deployed on Google Cloud Run with an alternate on-premises mode running Llama 3.3 70B locally on Apple Silicon. The name comes from the Roman *tessera*, an identification token granting access — the semantic theme is identity and permission check at every call.

## Honest positioning (non-negotiable, first page of README)

Tessera is neither a new firewall, nor a new test framework, nor a new safety methodology. The guard layer is first-party behind one declared seam (`guard/adapter.py`), and its reference implementation is being extracted into the separate `limes` package (ADR 0028); `mcp-firewall` is the category's prior art. The harness draws its patterns from AgentAssay and Promptfoo. The audit approach is inspired by AEGIS. What Tessera contributes is a complete, opinionated, deployed assembly of the four quality layers — runtime guard, offline regression harness, structured audit trail, human-in-the-loop escalation — wired end to end for one specific use case: European retail banking customer support in three languages with explicit regulatory grounding. The value is in the assembly and the EU business semantics, not technical invention. Any framing of the project that drifts toward "new framework" must be rejected.

Competitors and inspirations cited explicitly on the front page: `mcp-firewall` (ressl), AEGIS, DFAH, AgentAssay, Promptfoo, STING, Bernstein, ALTK. External academic citations must be verified against the actual papers before being committed to `docs/differentiation.md`.

## Stack (frozen)

Python 3.12. Dependency management via `uv` exclusively — no `requirements.txt`, no `pip`, no `poetry`. Code quality via `ruff` (lint + format) and `mypy` in strict mode. Testing via `pytest` with `pytest-asyncio` for the agent paths. Pre-commit hooks enforce all of the above at commit time.

Agent orchestration via LangGraph. Retrieval via PostgreSQL with `pgvector`, run locally on M1 Ultra for development and on Cloud SQL for the deployed demo. Embeddings from Vertex AI for the frontier path and from a local Ollama setup for the on-premises path. The frontier LLM is reached through Vertex AI; the local LLM is Llama 3.3 70B served by Ollama. Runtime guardrails through the first-party guard (`src/tessera/guard/`), policy-driven and measured by `firewall_efficacy` (ADR 0028); the reference implementation is being extracted into the separate `limes` package. The "reuse, don't reinvent" positioning is defended by cited patterns and measured claims — an unread dependency defends nothing (ADR 0028).

The HTTP layer is FastAPI. The dashboard is a Next.js application under `webapp/frontend/`. The infrastructure is described in Terraform under `infra/terraform/` and deployed to Google Cloud Run with Cloud SQL, Secret Manager, and Cloud Logging / Cloud Monitoring. CI is GitHub Actions, with four separate workflows: `ci.yml`, `eval.yml`, `deploy.yml`, `security.yml`.

## Non-negotiable disciplines

Ship-or-die at day twenty. If schedule slips, cut scope, never extend time. The repository's daily commit cadence is enforced — one commit minimum per day, using Conventional Commits formatting (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, `perf:`).

The README must document tests that pass and tests that fail with their root causes. No marketing fluff, no hidden failures. Every external citation must point to a verified, reachable source. No notebooks, ever.

OSS dependencies and inspirations must be cited explicitly on the README front page, with links.

## Conventions

Commit messages follow Conventional Commits. Branches follow `kebab/short-purpose` style with the author prefix optional. Pull requests use the template in `.github/PULL_REQUEST_TEMPLATE.md` and are reviewed against the checklist there before merge.

Python code is type-hinted under `mypy --strict`. All public functions have docstrings in the Google style. Module-level docstrings are required on every package entry point. Tests are split between `tests/unit/` for isolated, fast tests and `tests/integration/` for tests that hit Postgres, the LLM, or external services; integration tests are tagged with `pytest.mark.integration` so they can be skipped in fast CI loops.

Prompts live in YAML under `src/tessera/agent/prompts/{fr,de,en}.yaml` — never hardcoded in Python. Policies live in YAML under `src/tessera/guard/`. Failures cataloged for the regression harness live as individual JSON files under `eval/failures/NN_short_name.json`, validated against `eval/failures/_schema.json`.

Secrets never enter the repository. The deployment expects them in GCP Secret Manager, resolved at container start time. Local development uses a gitignored `.env.local` derived from `.env.example`.

## Repository structure (canonical)

This is the canonical tree. Claude Code must scaffold to this layout and refuse to introduce alternative structures without an ADR documenting the deviation.

```
tessera/
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── LICENSE                                        # Apache-2.0
├── CLAUDE.md                                      # this file
├── pyproject.toml
├── uv.lock
├── .pre-commit-config.yaml
├── .python-version
├── .gitignore
├── Makefile
├── docker-compose.yml
│
├── docs/
│   ├── design.md
│   ├── compliance.md
│   ├── multilingual.md
│   ├── safety.md
│   ├── eval.md
│   ├── on_prem.md
│   ├── differentiation.md
│   ├── threat-model.md
│   ├── runbook.md
│   ├── decisions/                                 # ADRs
│   │   ├── 0001-record-architecture-decisions.md
│   │   ├── 0002-license-apache-2.md
│   │   ├── 0003-ci-github-actions.md
│   │   ├── 0004-package-layout-src.md
│   │   └── 0005-tools-vs-workers-separation.md
│   └── images/
│       ├── architecture.svg
│       ├── agent_graph.svg
│       └── eval_flow.svg
│
├── src/
│   └── tessera/
│       ├── __init__.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── graph.py
│       │   ├── state.py
│       │   ├── router.py
│       │   ├── planner.py
│       │   ├── reviewer.py
│       │   ├── reporter.py
│       │   ├── workers/                           # LangGraph nodes (orchestration)
│       │   │   ├── __init__.py
│       │   │   ├── product_lookup.py
│       │   │   ├── regulation_lookup.py
│       │   │   ├── account_lookup.py
│       │   │   ├── simulator.py
│       │   │   └── escalation.py
│       │   ├── tools/                             # typed action targets (ADR 0005 §Amendment 1)
│       │   │   ├── __init__.py
│       │   │   ├── account_balance.py
│       │   │   ├── card_block.py
│       │   │   ├── transaction_search.py
│       │   │   ├── loan_simulate.py
│       │   │   └── ticket_escalate.py
│       │   └── prompts/
│       │       ├── fr.yaml
│       │       ├── de.yaml
│       │       └── en.yaml
│       ├── memory/                                # agent memory (ADR 0007)
│       │   ├── __init__.py                         # get_memory_backend() factory + scope_for()
│       │   ├── protocol.py                        # MemoryBackend Protocol + scope/context types
│       │   ├── transcript.py                       # Mechanism A — durable conversation transcript
│       │   ├── window.py                          # Tier 0 — sliding window (default)
│       │   ├── summary.py                         # Tier 1 — summary buffer + entity ledger
│       │   ├── persistent.py                      # Tier 2 — cross-session, dedicated pgvector table
│       │   ├── entities.py                        # literal entity extraction (amounts, IBAN, dates, refs)
│       │   ├── governance.py                      # PII screening, TTL, erasure, consent, audit hooks
│       │   ├── reflector.py                       # post-turn background memory formation (cold path)
│       │   └── adapters/                          # external engines behind the same Protocol (optional)
│       │       ├── __init__.py
│       │       ├── langmem.py                     # extra: memory-langmem
│       │       ├── mem0.py                        # extra: memory-mem0
│       │       └── zep.py                         # extra: memory-zep
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── embeddings.py
│       │   ├── store.py
│       │   ├── chunking.py
│       │   ├── reranking.py
│       │   └── hybrid_search.py
│       ├── corpus/
│       │   ├── __init__.py
│       │   ├── generator.py
│       │   ├── translator.py
│       │   ├── ingestion.py
│       │   └── data/
│       │       ├── credit_aurore_fr.json
│       │       ├── credit_aurore_de.json
│       │       ├── credit_aurore_en.json
│       │       ├── regulations_dora.json
│       │       ├── regulations_cnil.json
│       │       ├── regulations_bafin.json
│       │       └── regulations_gdpr.json
│       ├── guard/
│       │   ├── __init__.py
│       │   ├── policy.yaml
│       │   ├── adapter.py
│       │   ├── audit.py
│       │   └── decisions.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── frontier.py
│       │   ├── local.py
│       │   ├── router.py
│       │   └── budget.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py
│       │   │   └── audit.py
│       │   └── middleware.py
│       └── observability/
│           ├── __init__.py
│           ├── traces.py
│           ├── metrics.py
│           └── logging.py
│
├── eval/
│   ├── __init__.py
│   ├── failures/
│   │   ├── _schema.json
│   │   ├── 01_prompt_injection.json
│   │   ├── 02_pii_leak.json
│   │   ├── 03_hallucination_fact.json
│   │   ├── 04_overconfident_action.json
│   │   └── 05_citation_hallucination.json
│   ├── runner.py
│   ├── scorecard.py
│   ├── translator.py
│   └── reports/
│       └── .gitkeep
│
├── webapp/
│   ├── frontend/
│   │   ├── package.json
│   │   └── app/
│   │       ├── page.tsx
│   │       ├── audit/page.tsx
│   │       └── eval/page.tsx
│   └── api/
│       └── main.py                                # thin entrypoint, imports from src/tessera/api/
│
├── infra/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── cloud_run.tf
│   │   ├── postgres.tf
│   │   ├── secrets.tf
│   │   ├── observability.tf
│   │   └── variables.tf
│   └── docker/
│       ├── Dockerfile.agent
│       └── Dockerfile.frontend
│
├── scripts/
│   ├── generate_corpus.py
│   ├── ingest_regulations.py
│   ├── run_eval.py
│   ├── run_local.py
│   └── seed_demo.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_agent_graph.py
│   │   ├── test_retrieval.py
│   │   ├── test_guard.py
│   │   ├── test_corpus_generator.py
│   │   └── test_llm_router.py
│   └── integration/
│       ├── test_agent_e2e.py
│       └── test_firewall_adapter.py
│
└── .github/
    ├── workflows/
    │   ├── ci.yml
    │   ├── eval.yml
    │   ├── deploy.yml
    │   └── security.yml
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    ├── PULL_REQUEST_TEMPLATE.md
    ├── CODEOWNERS
    └── dependabot.yml
```

## Repository topology (multi-agent worktrees)

As of 2026-07-07 this repo lives under a shared umbrella:

```
/Users/amadou/local/apps/
├── tessera-app/
│   ├── tessera/                  ← this repo (origin: AmadouMamane/tessera-app.git, private), branch `main`
│   ├── agents/
│   │   ├── claude/               ← worktree, branches `claude/<sujet>`
│   │   ├── codex/                ← worktree, branches `codex/<sujet>`
│   │   └── antigravity/          ← worktree, branches `antigravity/<sujet>`
│   ├── Tessera_private/          ← private steering docs, never tracked by git
│   └── legacy-tessera-2026-07/   ← archived old repo (origin: AmadouMamane/tessera.git)
```

**Branch model: trunk-based.** `main` is the only long-lived branch, protected by the twice-green
gate (`ruff check` + `ruff format --check` + `mypy` + `tsc --noEmit` + `biome check` +
`pytest -m "not integration"`). Each agent works in its own dedicated
worktree under `agents/<name>/` on short-lived branches named `<agent>/<sujet>`, cut from a
fresh `main`, and lands (merges into `main`) as soon as the gate is green — no `develop`, no
long-running feature branches. At every slice boundary, resync the worktree's branch from
`main` before starting the next unit of work (once the previous branch has landed, cut the next
one with `git checkout -b <agent>/<next-sujet> main`).

**Twice-green is `make gate-twice`, never `make gate` twice by hand** (process P0, 2026-07-12).
Running it by hand and *remembering* that both passes were green is exactly what failed: two
`make gate` runs returned **exit 0 on two different trees** — a concurrent agent had stashed the
working changes and switched the worktree's branch between the passes — the test counts silently
differed (1862, then 1858), and it read as a clean twice-green. CI is billing-blocked, so the
local gate is this project's ONLY witness, and a verdict that cannot name the tree it judged is
unfalsifiable.

- **Every gate prints and records its tree** — worktree · branch · HEAD · dirty · a digest of the
  actual content — taken *before and after* the run. A pass whose tree moved underneath it is
  **VOID** (exit 3, deliberately not the red 1: unusable is not the same as failed).
- **`make gate-twice`** runs both passes and asserts **by machine** that they saw the same tree.
  Two green passes on two trees are REFUSED, and the refusal names what moved.
- **Say who you are, then `make claim`.** Identity is **asserted by the SESSION**, never derived
  from a path — `make claim` used to read the *worktree's directory name*, so all seven live Claude
  sessions in `agents/claude/` resolved to the owner `"claude"`, each read the marker, found its own
  name, and believed it was home. **A role is not a writer** (ADR 0027). Mint an id **once** and
  keep it for the whole session — a fresh uuid per command would make every command its own session:

      eval "$(make session)"        # a human shell
      export TESSERA_SESSION_ID=…   # an agent / CI: one uuid, minted once, kept

  Then `make claim` before you work in a worktree, `make release` when you leave. A worktree has ONE
  writer. A caller with no session id gets **CANNOT SAY** and exit 2 — never "you are home". The
  marker is advisory (nothing on a shared filesystem truly locks), and that is enough **provided it
  tells the truth**: it turns a silent collision into a loud refusal. `make whoowns` asks.
- **Never take a verdict on a tree somebody else is writing in.** Destroy nothing — no stash, no
  checkout, no reset — and gate an **isolated copy at the exact commit** (a disposable worktree).
  On 2026-07-12 an agent correctly judged foreign changes *"NOT MINE"* and then **stashed them** to
  get a clean tree: it destroyed the other's work *and* produced a verdict about a tree that no
  longer existed. Both halves are wrong.

Progress across slices/steps is tracked in `docs/status/0017-execution-status.md` — read it
first when resuming work, it is the single source of truth for what's done, in flight, and next.

## Serveurs dev

Local dev servers are managed by Makefile targets — never launch `next dev` or
`run_local.py` by hand; the targets encode the ports, the `/healthz` +
`/api/healthz` health gates, macOS-safe detachment, and a pre-flight port guard:

- `make dev-up` — backend **:8099** (FastAPI) + frontend **:3097** (Next.js) from
  the **current checkout**, detached; waits for health. Logs:
  `/tmp/tessera-{backend,front}.log`.
- `make dev-down` — stop both, by port.
- `make dev-status` — ports, PIDs, the git head of the served checkout, health.
- `make dev-preview PORT=3098` — a **temporary** validation server from an agent
  worktree on another port (backend derived, e.g. `:8098`), killed after validation.

Convention: the **reference** servers run from the **main checkout** (`tessera/`)
so the operator's browser reflects `main`; reviewing **unmerged** work at a
supervised checkpoint uses `dev-preview` from that agent's worktree — never a
long-lived server on an agent worktree. Every worktree mutation (checkout / park /
`git worktree remove`) is preceded by a live-process check (`lsof`); `dev-up`
refuses to start if the port is already in use. Full rationale:
`docs/status/0017-execution-status.md` (Preconditions).

## Instrumentation traps (measured, and they all answer a QUESTION YOU DID NOT ASK)

These four cost a wrong conclusion each, more than once. What they share is the shape this
repository keeps re-learning: **none of them errors.** Every one returns a plausible answer to a
neighbouring question, so the reader is confident and wrong (ADR 0026).

**1 — The owned score table is `tessera.eval_online_scores`, never `default.scores`.**
`default.*` in ClickHouse belongs to LANGFUSE. Tessera's online judge writes its own table in the
`tessera` database (`emit_score` → `clickhouse_scores.record_online_score`). Querying `default.scores`
for recent quality returns EMPTY and reads as "nothing has been scored in forty days" — which was
believed, and was false. Same trap in the other direction: a TTL applied to `default.scores` would
prune Langfuse's rows and leave Tessera's untouched.

**2 — Each observability endpoint speaks its own window dialect, and an unreadable one means ALL HISTORY.**
`/observability/slo` takes `?days=7`. `/observability/fleet` takes `?period=d7` — the rail's
vocabulary (`h24` · `d7` · `d14` · `d30`). A parameter this endpoint does not declare is dropped by
FastAPI without complaint, and `parse_period_days()` returns `None` for anything it cannot read.
`None` means *all history*, **deliberately** — its own docstring says refusing to guess is the
point, because coercing an unreadable window into 7 days would put a period nobody chose behind
numbers they are about to act on. The consequence for a prober: `?days=7` on `/fleet` answers with
LIFETIME totals, no error, no empty `window`. Measured 2026-08-21 — `?days=7` gave 261 turns for
`recouvrement`, `?period=d7` gave 4. Read `window.period_days` in the response before believing any
figure; it is `null` when nothing was applied.

**3 — Pass the ClickHouse password through the ENVIRONMENT, never as an argument.**
`docker exec -e CLICKHOUSE_PASSWORD="$PW" <container> clickhouse-client -q "…"`. The
`--password X` form is rejected by the client *and* echoes the secret into the error text. The
value lives in the agent container's env, so read it from there rather than from a file.

**4 — Never rewrite a message catalogue with `json.dumps` alone.**
`json.dumps(indent=2)` expands the inline arrays biome keeps on one line: 104 lines of diff for
15 lines of intent, twice in one session. And deleting a key by hand leaves an orphan comma that
breaks the JSON. The safe pair is `json.dumps(…, indent=2)` **then** `biome check messages/ --write`
— biome is the formatter of record here, so it restores the canonical shape and the diff collapses
to what was actually changed. Verify with `git diff --stat` before committing.

## Decision records

Read these before making any architecture-shaping change. They are short and binding.

- `docs/decisions/0001-record-architecture-decisions.md` — why and how we record decisions
- `docs/decisions/0002-license-apache-2.md` — Apache-2.0 license choice
- `docs/decisions/0003-ci-github-actions.md` — GitHub Actions over GitLab CI and Cloud Build
- `docs/decisions/0004-package-layout-src.md` — `src/` layout over flat layout
- `docs/decisions/0005-tools-vs-workers-separation.md` — LangGraph nodes versus LLM-callable tools
- `docs/decisions/0006-locale-prefixed-routing.md` — dashboard pages live under `app/[locale]/`, supersedes the single-locale `app/page.tsx` shape in the canonical tree above
- `docs/decisions/0007-agent-memory-architecture.md` — agent memory: durable conversation transcript (Mechanism A) + pluggable `MemoryBackend` (window/summary/persistent tiers on pgvector, with langmem/mem0/zep adapters); adds the `src/tessera/memory/` package to the canonical tree
- `docs/decisions/0024-every-governed-act-names-its-author.md` — every governed act names its author (verified) and its reason (declared); no identity field may carry a default that names somebody
- `docs/decisions/0026-a-witness-interrogates-the-thing.md` — **a witness interrogates the thing, never its neighbourhood.** A gate reports its own exit code; a guard is what refuses a stranger; a server states which code it loaded; a contract is what it honours. And: a witness that cannot see reports a blind spot — it may never report "ok". Read it before writing any check, ratchet or status command: three guard-rails have already reported success over a hole because they asked an adjacent question
- `docs/decisions/0051-served-surfaces-are-declared-and-checked.md` — **landing is not serving, and it does not fail to serve uniformly.** Some paths are baked into an image and frozen at the commit that built it (`src/`, `eval/` incl. the baselines and the grader, the whole front); others are bind-mounted and move the instant the file changes (`eval/reports`, the obs configs). Touch both and the stack is a **chimera** — old code reading new data — which is how a re-grade landed without a rebuild put the deployed cockpit into `CannotSay`. `infra/deploy/served-surfaces.yaml` declares each path's medium and why; **`make served-check`** asks the running stack which commit it serves and refuses when a served surface has moved. **Read the printed line, not the exit code**: the SCRIPT speaks 0 ok · 1 refused · 2 blind, but make exits **2 on any failed recipe**, so through the target a refusal and a blind spot are the same number — opposite instructions, one integer (measured in `tests/unit/test_make_flattens_exit_codes.py`; same caveat on `make preflight` and `make deploy-diff`). Call `scripts/served_check.py` directly when you need the verdict as a number. Run it after every land, before believing any surface
- `docs/decisions/0052-a-monitoring-surface-names-the-consequence.md` — **a page called « observabilité » answered « est-ce que ça tourne ».** Twenty flat rows cannot say that ONE dead node explains three of them, and the assembly a reader performs unaided is wrong here: metrics reach Prometheus by TWO routes (a dead collector does not blind them) and business events never cross the collector at all. So the chain is declared with the file that wires each edge, read as a PATH from the emitter; each store names what its silence costs (declared capability, **computed** state, `cannot_say` when a dependency could not be interrogated); and verdicts are journalled over time — where **a gap is a hole, never uptime**: a phase absorbs an observation only within 120 s, every percentage travels with `observed_ratio`, and availability divides by DECIDABLE time, because blind minutes decide nothing and dividing by watched time printed **0.0 % available** over « nobody could ask »

## Communication rules (permanent, no exception)

Before every significant tool call (Bash, Edit, Write, Agent), output exactly one sentence prefixed with 🟢 in ALL CAPS.
Format: `🟢 UNE PHRASE EN MAJUSCULES.`
Never ask for confirmation unless the action is destructive/irreversible.

## Memory hygiene (permanent)

After fixing a non-obvious bug, discovering an architectural lesson, or solving a tricky UI/CSS problem, update the two memory files (their machine-specific paths live in `AGENTS.local.md`, gitignored): add a numbered Insight to `insights_tessera.md` (Symptom / Root cause / Fix / Architectural lesson), and update the relevant section + the "Statut à jour" block in `synthesis_tessera.md`.

Do this during the session, not at the end. If in doubt whether something is worth saving, save it.

**ONE registry, ONE file, ONE number (2026-07-13).** The registry lived in **two** diverged
copies of the same name, one per harness, and nobody read both. The **bigger** file was the
**dead** one: "keep the most recent" would have destroyed 98 insights in silence. They are now
merged (union — nothing deleted, number collisions renumbered with the elder keeping its number)
into a single canonical file; every harness path is a **symlink** to it. Two rules are enforced by
`make memory-check`, which `make gate` runs:

- **no second file of the same name** — the one you write must be the one the next agent reads;
- **no two insights sharing a number** — during the very merge that fixed the first rule, a third
  agent appended two insights under numbers already taken twice. A number that names two insights
  names neither.

**And that second rule was itself green over a hole until 2026-07-13.** It matched only headings
of the form `## Insight N` — 139 of the registry's **199** — while the other 60 use `### N. Title`.
It policed 70 % of the file and reported on all of it, and in the 30 % it could not see, `### 2.`
already named two different insights. Made to see, it found **58 numbers that each name more than
one insight**. Those are frozen (`_FROZEN_COLLISIONS`, a debt that may only go down); a **59th is
red**. ADR 0026's sixth instance, and the corollary exactly: *a witness that cannot see may never
report "ok"*.

**So "take the highest number and add one" is a trap, and it caught me.** With two conventions in
one file, the highest number among *the headings that look like yours* is not the highest number.
Counting only `### N.` answers **60** — and `## Insight 60` has existed for months. Read it from
the whole file:

```bash
uv run python -c "from tests.unit.test_memory_registry_single_source import next_free_number; \
from pathlib import Path; print(next_free_number(Path.home().joinpath('.claude/projects/-Users-amadou-local-apps-tessera-app-tessera/memory/insights_tessera.md').read_text()))"
```

Never renumber an **existing** insight: its number is cited from other insights, from
`synthesis_tessera.md`, and from commit messages.

## How Claude Code should behave in this repository

Default to reading the relevant ADR before changing structural choices. When a request would deviate from the canonical tree above, ask before doing it and propose an ADR draft. When introducing a new dependency, justify it in the relevant ADR or open a new one — Tessera's positioning depends on minimal, well-cited reuse, not feature creep. When in doubt about scope, prefer cutting over extending: the day-twenty deadline takes precedence over completeness.

When asked to make a cockpit/agent page "real" or "functional", read `docs/functional-page-playbook.md` first — it is the step-by-step recipe (real data source → backend build → durable mutation endpoint → wired frontend → real sparklines → probe for derived metrics → e2e verification) plus the gotchas. Never call a deterministic fixture "real": separate "displayed values are real" from "interactions are wired", and say which holds.
