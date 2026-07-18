# Architecture decision records

The binding decisions. Read the relevant one before making an architecture-shaping change
(see `0001-record-architecture-decisions.md` for why and how).

**This directory holds decisions and nothing else.** Execution logs, incident reports and
overnight-run journals used to live here, squatting real ADR numbers — three of the six
number collisions the 2026-07-10 audit found were not ADR collisions at all, just logs
wearing an ADR's number. They now live in `docs/status/` and `docs/incidents/`.

| # | Decision |
|---|---|
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md) |
| 0002 | [Apache-2.0 license](0002-license-apache-2.md) |
| 0003 | [CI on GitHub Actions](0003-ci-github-actions.md) |
| 0004 | [`src/` package layout](0004-package-layout-src.md) |
| 0005 | [Tools vs workers separation](0005-tools-vs-workers-separation.md) |
| 0006 | [Locale-prefixed routing](0006-locale-prefixed-routing.md) |
| 0007 | [Agent memory architecture](0007-agent-memory-architecture.md) |
| 0008 | [Agent audience and surface](0008-agent-audience-and-surface.md) |
| 0009 | [Dashboard auth & RBAC](0009-dashboard-auth-rbac.md) |
| 0010 ⚠️ | [Frontier observability](0010-frontier-observability.md) — *keeps the number: 183 references* |
| 0010 ⚠️ | [Recouvrement internal operator agent](0010-recouvrement-internal-operator-agent.md) — *will become 0021; held for CI, see below* |
| 0011 | [Temporal as-of-T dimension](0011-temporal-as-of-t-dimension.md) |
| 0012 | [Agent registry and seed](0012-agent-registry-and-seed.md) |
| 0013 | [Entry routing by audience](0013-entry-routing-by-audience.md) |
| 0014 | [Environment isolation](0014-environment-isolation.md) |
| 0015 | [Runtime telemetry spine and scope](0015-runtime-telemetry-spine-and-scope.md) |
| 0016 | [Business-events fan-out contract](0016-business-events-fanout-contract.md) |
| 0017 | [Agent observability contract](0017-agent-observability-contract.md) |
| 0018 | [Assistant runtime turn contract](0018-assistant-runtime-turn-contract.md) |
| 0019 | [Invocation binding](0019-invocation-binding.md) |
| 0020 | [Production security hardening](0020-security-hardening.md) — *was a second 0008* |
| 0021 | [The eval gate grades measured contribution; the absolute domain bars are removed](0021-eval-gate-on-measured-contribution.md) |
| 0022 | [Hica external opposability seal — design note](0022-hica-seal-design-note.md) — *annex to 0015; was a second 0015* |
| 0023 | [The audit chain is independent of the audit sink](0023-audit-chain-independent-of-sink.md) — *audit F-6; annex to 0015* |
| 0024 | [Every governed act names its author; every configuration that cannot hold a guarantee refuses to boot](0024-every-governed-act-names-its-author.md) — *audit F-1/F-5/F-6/F-B, one doctrine; generalises 0023* |
| 0025 | [Subject reads will be gated by DECLARED PURPOSE](0025-pii-reads-are-gated-by-role-not-by-purpose.md) — *audit F-C; **ruled** 2026-07-12: purpose, not dossier, not tenant. Today's posture (role only) ships stated plainly, pinned by a test* |
| 0026 | [A witness interrogates the thing, never its neighbourhood](0026-a-witness-interrogates-the-thing.md) — *the methodological twin of 0024. Three guard-rails reported success over a hole because each asked an adjacent question: the gate read a pipeline's last line instead of its exit code; a guard checked a name in a list instead of calling it with a stranger's request; `dev-status` asked git about a **directory** instead of asking the server what it **loaded**. And: a witness that cannot see reports a blind spot — it may never report "ok"* |
| 0027 | [A verdict carries its evidence — and is taken on a tree that holds still](0027-a-verdict-carries-its-evidence.md) — *0026's structural half, and its **fourth** instance: `make claim` asked the **directory** who was working here, so all seven live Claude sessions in `agents/claude/` resolved to the owner "claude" and each believed it was home. `Verdict = Ok(evidence) \| NotOk(reason) \| CannotSay(blind_spot)` — an `Ok` is unconstructible without its evidence, and a verdict may not be a boolean. Debt frozen at **44**. A test that cannot run is a `CannotSay`, counted and impossible inside the gate. And: never judge a tree another writer is in — judge an isolated copy at the exact commit* |
| 0028 | [The firewall that never ran](0028-the-firewall-that-never-ran.md) — *`mcp-firewall` was a ghost: imported at `guard/adapter.py:106`, assigned once, read by nobody — an MCP transport proxy for an application that speaks no MCP, while ~45 mentions across 30 files (three tests included) attested "guarded by mcp-firewall". Decision: remove the ghost, correct every attesting surface (enforced by `test_no_ghost_attestations.py`), keep and promote the seam, build the first-party reference guard as a separate package (`limes`) under the admission rule "no detector without eval cases and a null control", and fix the case-08 grader first — a word the attacker can make the model say is not proof of refusal. Carries its own incident: the diagnosis author and the reviewer were each bitten by a wrong witness (a 3.10 sandbox reading "not there"; `/pypi/json` reading "free" for a registered-empty name) — the remedy is mechanical, never vigilance. Voided two CLAUDE.md non-negotiables, edited in the accepting commit* |
| 0029 | [Tessera consumes limes (phase 2 — the hole is closed for real)](0029-tessera-consumes-limes.md) — *0028's second half: the guard extracted into `limes` is now **consumed** behind `guard/adapter.py`. `check_user_input` delegates injection detection to limes' detector (`Deny`/`CannotSay` → block, `CannotSay` fail-closed); Tessera keeps NO copy of the patterns — the YAML deny list is empty, `load_policy` refuses a re-add, and `Policy.prompt_injection_deny` is derived from limes so every read surface reflects one source. Case 08, measured on the real path: **obeyed (fr/de/en) BEFORE → refused AFTER** (`injection.limes.deny`); 25/33 blocked, 0/8 false positives, F1 0.86. The badge greens only on a dated limes F1 (detector identity, not `F1 > 0`). Ratchet + mutation-tested (unplug limes → case 08 reopens). **HALTs before merge**: the local path dependency has a worktree-vs-checkout depth mismatch — vendor / submodule / PyPI is Amadou's call* |
| 0030 | [An operable knob carries a governed override — never a generic config editor](0030-operable-knobs-carry-a-governed-override.md) — *The Paramètres page had a Save with nothing to save: config truth is frozen (env + git), no field is editable. The real need was operational — change the serving chat model without a redeploy, org-wide or per agent. Decision: a **closed registry** of operable knobs (`llm.chat_model`, `llm.chat_model.agent.<id>`) on a durable `config_overrides` store; a write is a superadmin act carrying its author (verified assertion) and a mandatory reason, journalled, and driven by the governance ratchet; values are validated against the real catalogue — refused, never stored. Effective by construction: resolved once per turn at the routing seam (picker > agent override > org override > frozen base) and stamped on audit entries, trace dimensions and eval lineage, so what serves is what is recorded. Reads fail open to base with a loud log; writes fail closed; the base stays visible and revert is always possible. The mutation lives where the knob lives (`/configurer/modeles`); Paramètres drops the objectless global Save/Import* |
| 0031 | [A behaviour knob obeys its slider — sampling parameters are effective by construction](0031-sampling-params-are-effective-by-construction.md) — *The per-agent Configurations sliders (temperature, top-p, penalties) were the cockpit's last cosmetic knob: a real store, a real Save, a real change-log — and no LLM call ever read them; the runtime hardcodes `temperature=0.2` and the displayed defaults (0.3/0.7/0.2/0.1) were fabricated. Decision: identity/behaviour split (which model = ADR 0030, superadmin; how it samples = the agent-configurations store, operator — one home each, this ADR is the boundary); defaults become the runtime truth (temperature 0.2; top-p and penalties **unset** = not sent, "défaut backend" said plainly); resolved once per turn at the same routing seam as the model, carried in the graph state, passed by the reporter — slider and served value are the same read. Honest per backend: a declared capability (Ollama all four, Vertex temperature+top-p, OpenAI none — reasoning models reject) verified by tests against what each backend hands its client; the page derives applicability from the agent's effective model. The save becomes an attributed governed act; the resolved sampling is stamped on the turn span and the Debug payload* |
| 0032 | [The behaviour selects are effective by construction (tone, detail, max length, top-k)](0032-behaviour-selects-are-effective-by-construction.md) — *Same disease, one row above the sliders 0031 just cured: Ton / Détail / Longueur max were stored, journalled, displayed — and read by no prompt and no call, while the `ChatBackend` protocol had carried `max_output_tokens` on all three backends since it was written. Decision: same recipe, no new machinery — resolved once per turn at the routing seam, carried in the state, consumed by the reporter. Tone and detail become prompt directives living in the YAML bundles (slug-keyed, three languages, completeness-tested); max length becomes a soft directive **and** a hard declared cap (512/2048/8192 — Moyenne is the historical Vertex truth); a console `system_prompt_override` stays verbatim (no style block). Top-k joins as the fifth slider (Ollama+Vertex apply, OpenAI refuses-and-says; integer-coerced). Effectiveness is said next to each control (badges "Injecté au prompt" / "≤ N tokens"); `gen_ai.request.max_tokens` is stamped on the turn span and Debug carries style+cap. Paths that never cross the seam keep their historical behaviour* |
| 0033 | [The escalation threshold is an operable, governed knob](0033-escalation-threshold-is-an-operable-governed-knob.md) — *The reviewer's confidence fuse (grounding×0.5 + coverage×0.3 + guard×0.2) escalates below `GuardSettings.escalation_confidence_threshold` (0.6) — THE business knob of the human-in-the-loop layer, frozen in env+git until now. Decision: per-agent knob in the agent-configurations store, unset = the org settings value serves ("Défaut org (0,60)", never an invented number), clamped [0,1]; resolved once per turn at the routing seam into `state["escalation_threshold"]`, the reviewer reads THE STATE (settings fallback only off-seam — the eval harness stays deterministic); saved through the same governed endpoint (operator, author, change-log — no new act, the 12th grows one key); said on the page (formula included) and in the Debug reviewer surface; stamped as `tessera.escalation.threshold` on the turn span* |
| 0034 | [The daily LLM budget ceiling is an operable, governed knob](0034-llm-budget-ceiling-is-an-operable-governed-knob.md) — *The cost tracker was a meter with no breaker — and its docstring attested "per-conversation caps" that no caller enforced (a claim in prose with no enforcer, ADR 0026). Decision: two org-wide knobs in the ADR 0030 closed registry — `llm.budget.daily_eur` (positive decimal, refused-not-stored; unset = no ceiling, the historical truth) and `llm.budget.overrun` (`block` \| `local_fallback`; unset = block — a ceiling means stop spending). Per-knob-family validation in `set_override`; the tracker learns the Europe/Paris day (per-day counters beside cumulative, same JSON, auto-rolled); the breaker sits at the routing seam and gates PAID models only — `local_fallback` serves the frozen base when it is zero-cost, else degrades to block; a blocked turn short-circuits the graph like an injection block with a localized YAML `budget_exceeded` message. Fail-open reads, fail-closed writes; the registry panel gains kind-aware controls; the catalogue KPIs gain the day's real spend + the ceiling; `tessera.budget.overrun` stamped. Deliberately NOT: per-conversation/per-agent caps, forecasting, or gating the eval runner* |
| 0035 | [Retrieval depth and reranking are per-agent, effective by construction](0035-retrieval-depth-and-reranking-are-per-agent.md) — *The chat path's retrieval knobs were frozen in code: top-4 product / top-6 regulation, RRF reranking always on — while the observability page measures reranker lift nobody can act on. Decision: two per-agent knobs in the agent-configurations store — `retrieval_top_k` (unset = each worker's historical default, said as "Défaut par recherche (4 produit / 6 réglementaire)", never one number pretending to be both; set = both lookups, [1,10] integer) and `retrieval_rerank` (ON by default — the historical truth; off = vector order serves and the ×3 over-fetch is skipped). Same seam recipe: `resolve_retrieval` → `state["retrieval"]` → the lookup workers read THE STATE (off-seam = historical constants, eval numbers stay comparable); `hybrid_search.search` gains an explicit `rerank` parameter — a skipped reranker is a declared decision. The regulation worker's 0.75 score-cut is deliberately NOT a knob (calibrated against the RRF scale)* |

*(0021 is reserved for `recouvrement-internal-operator-agent` — see below.)*

## Renumbering — two collisions dissolved, one held for CI (2026-07-12)

The rule, decided after counting rather than assumed: **the sense that is referenced most keeps
its number.** Every rewritten reference is a chance to make the decision record assert something
false, so the *smaller* side moves. A duplicate number is an annoyance; a decision record that
lies is a defect.

### Done

**`0008-security-hardening` → `0020`.** Settled by dates, which is proof rather than heuristic:
security-hardening was created **2026-05-31**, `agent-audience-and-surface` **2026-06-22**, so
every reference written before that cutoff *could only ever have meant* security-hardening. 25
bare references rewritten; the ~46 that mean audience/surface were left untouched. The handful of
post-cutoff references were adjudicated by reading the **origin commit** — `session.py`'s
`(ADR 0008/0009)`, for instance, was written by the commit that *created* the audience ADR, so it
stays at 0008.

**`0015-hica-seal-design-note` → `0022`.** Free: the annex was referenced **only by filename**.
Zero bare `ADR 0015` references meant it — because the seal was **decided** in the spine ADR
(§Amendment 3 / §Correction 3c) and only **designed** in the annex. `guard/seal.py`,
`guard/audit.py` and `settings.py` all say "ADR 0015 §…" and are correct *exactly as they are*;
they were not touched. Reading them as annex references is the trap, not the fix.

### Held — `0010`, and this is not laziness

`recouvrement-internal-operator-agent` → `0021` **waits for CI.**

* **245+ references.** 183 mean *frontier-observability* (which therefore keeps 0010); 52 mean
  *recouvrement*. The discriminator is strong — frontier numbers its rollout `Phase 1..6` and its
  features by canonical idea IDs (`docs/observability-ideas.md`), recouvrement uses `Phase A/B/C`
  and has no ideas — but *strong* is not *verified*.
* **Some references wrap across lines** — `ADR` ends one line, `0010 Phase C` begins the next. No
  grep sees them, so **no grep-based verification of this rename can be complete**: it will report
  "0 remaining" while the record still lies.
* A first automated attempt **produced exactly that lie**, re-pointing *"## 4. The audit ledger
  (ADR 0015)"* at the seal annex on nothing but word proximity.

Rewriting the project's memory *semantically*, at that scale, with **no independent witness**, is
precisely what a bounded tolerance of an absent CI must forbid. This is the **first live item
waiting on CI's return**.

Per-reference evidence, the discriminators, and the order of operations:
**[`docs/status/adr-renumber-evidence.md`](../status/adr-renumber-evidence.md)**.

The ratchet (`tests/unit/test_adr_hygiene.py`) now freezes exactly one collision — `0010` — and
fails both on a NEW duplicate and on a stale entry left in the frozen set.
