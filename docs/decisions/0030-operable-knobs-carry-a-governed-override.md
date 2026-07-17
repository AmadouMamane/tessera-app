# 30. An operable knob carries a governed override — never a generic config editor

Date: 2026-07-17

## Status

Accepted. Direction chosen by Amadou on 2026-07-17 ("il faut implémenter un store d'overrides
gouverné avec ADR"), scoped here to a **closed registry** of operable knobs.

## Context

Tessera's configuration truth lives in two frozen places: env-derived settings
(`tessera.settings`, immutable per deploy) and git-versioned files (guard policy, prompts). The
Paramètres cockpit page reads that truth honestly — every number derived from live state, every
change attributed to the config source (git) — and consequently has **no editable field**: its
"Enregistrer" / "Importer" buttons never had an object. They were honestly disabled in the FE
sweep (lot 1a) rather than wired to a lie.

But one real operator need has no home at all: **changing the serving chat model without a
redeploy** — for the whole cockpit, or for one agent (e.g. run `recouvrement` on a different
model than `support-client`). The per-*turn* rail already exists: `ChatRequest.model` (the UI
picker) flows into the LangGraph state, `backend_for_model()` routes it, and both backends accept
a per-call `model=` override. What is missing is exactly a **durable, governed default** between
the picker and the frozen base.

Two failure modes frame the decision:

* **The generic config editor** (override any `Settings` field from the UI) breeds ghost
  configuration: values nobody can trace, competing with env and git, silently surviving deploys.
  Nothing in this repo's doctrine (ADR 0024, 0026) survives contact with that.
* **The cosmetic override** (stored but not consulted by the runtime) is a recorded lie: a Save
  that "worked" while the system keeps serving the old value. This is the exact class of false
  affordance the cockpit audit exists to purge.

## Decision

1. **A closed registry of operable knobs.** A knob is overridable **only** if it is declared in
   the registry (`tessera/api/config_overrides.py`), with its validator and its base-value reader.
   The first — and so far only — knob family is model selection:

   * `llm.chat_model` — the org-wide serving chat model;
   * `llm.chat_model.agent.<agent_id>` — the per-agent serving chat model, one key per fleet
     agent.

   Values are validated against the **real** model catalogue (chat-role models plus the declared
   OpenAI registry) at write time; an unknown key or an uncatalogued model is refused, never
   stored. Adding a knob is a deliberate, reviewed edit to the registry under this ADR's rules —
   there is no generic path.

2. **A durable store with attribution columns.** `config_overrides` (Postgres, materialised in
   the env schema per ADR 0014) stores `key, value, author, reason, updated_at`. Author comes from
   the **signed operator assertion** (`require_superadmin` → `actor_of`), never from the request
   body (`extra="forbid"` keeps a caller from forging one — ADR 0024). `reason` is mandatory.
   Every write and every revert emits a governance mutation to the audit trail.

3. **Effective by construction.** The turn's model is resolved **once, at the routing seam**
   (after the supervisor picks the agent), with explicit precedence:

   > per-turn picker (`request.model`) → per-agent override → org override → frozen base.

   The resolved value goes into the graph state (what `backend_for_model` and the backends'
   per-call `model=` consume) **and** into every attribution surface — the audit context var, the
   trace dimensions, the online-eval lineage — so what served is what is recorded. An override
   that the runtime ignores cannot be written under this design, because the store's only
   consumer *is* the serving path.

4. **Reads fail open to base; writes fail closed.** If the override store is unreachable, a turn
   serves on the frozen base (the base is always valid; the guard chain — which fails closed — is
   untouched by this ADR) and the degradation is logged loudly. Writes and reverts on an
   unreachable store are refused. The UI never renders a base value *as if* it had checked the
   store when it could not.

5. **The mutation lives where the knob lives; provenance is always visible.** The
   "set active model" / "revert to base" actions sit on `/configurer/modeles` (org-wide and
   per-agent), next to the catalogue rows they act on. Wherever an effective value is displayed
   (model catalogue, Paramètres rows), an overridden knob shows its real author, date and reason,
   and the git/env **base value stays displayed** alongside — an override never masquerades as
   the base. The Paramètres page keeps no global "Enregistrer"/"Importer": the former never had
   an object (removed), and importing a config file would bypass the git provenance the page
   itself asserts.

## Consequences

* The operator can change the serving chat model — org-wide or for one agent — from the cockpit,
  with author, reason and audit trail, and can always see and return to the git/env base.
* `tessera.settings` stays frozen and cached; nothing mutates it. The override is consulted at
  one seam, per turn. No client rebuild, no restart, no second source of truth for anything
  outside the registry.
* Per-agent model selection becomes real for the first time (the fleet previously served one
  org-wide pair resolved from the profile).
* Future operable knobs (e.g. a rate limit, a log level) enter **only** by declaring a registry
  entry whose effective read path is wired the same turn — a stored-but-ignored knob is a
  refused design under this ADR.
* The eval/replay surfaces that stamp a model id now receive the **effective** model, which is
  the truthful lineage (previously they stamped the picker value or the base, wrongly attributing
  overridden turns).
