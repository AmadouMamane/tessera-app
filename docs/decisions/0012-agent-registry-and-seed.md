# 0012 — Agent registry (YAML) and demo seed

- Status: accepted
- Date: 2026-06-17
- Supersedes: none
- Related: ADR 0010 (audit chain), ADR 0011 (as-of-T), `docs/design/plan-build-multi-agent.md`

## Context

Phase 0 made the cockpit multi-agent-*ready*: routes are `/agents/:agentId/*`,
and `agent_id` is stamped on every event, metric and message. But there is still
only one agent in the data and no place that declares *which agents exist* or
*what each is bound to*. Phase 1 needs three realistic agents (`support-client`,
`onboarding`, `recouvrement`) with plausible history — including conversations
that span two agents (handoff) — so the fleet, attribution and dedup work can be
tested against non-empty views.

A registry is a new structure, not in the canonical tree of `CLAUDE.md`, so it is
recorded here.

## Decision

1. **Registry as versioned YAML.** `src/tessera/agent/agents.yaml` is the single
   source of truth for the fleet; `src/tessera/agent/registry.py` loads it into
   immutable `Agent` records. An agent is a governed *package* that **binds**
   reusable building blocks from the CONFIGURER catalogue (model, prompts,
   knowledge, guardrails, eval set, tools) — it never redefines them
   (define / choose / govern). Each agent declares a **handoff contract**
   (`to` / `from`): the governed agent graph, with `can_handoff(src, dst)`
   requiring the edge on *both* ends.

   YAML over hard-coded dataclasses: the bindings read like a catalogue, are
   editable without code, and diff cleanly. The YAML `default` must equal
   `DEFAULT_AGENT_ID`, enforced at load, so data stamps and URLs never diverge.

2. **Per-agent config = registry base + durable overrides.** The registry
   provides each agent's identity and bindings (name, owner, model, …); the
   existing durable config store keys editable overrides by `agent_id` and layers
   on top. CONFIGURER stays the place blocks are *defined*; the agent only
   *chooses*.

3. **Idempotent DB seed.** `scripts/seed_agents.py` writes ~30 days of real
   transcript history per agent into `conversation_messages` (backdated
   `created_at`, stamped `agent_id`), **including shared conversations** where one
   `conversation_id` carries turns from two agents plus a `handoff` event in the
   audit chain (S1). Seeded rows live under a fixed UUIDv5 namespace so a re-run
   deletes-then-reinserts only its own rows — never touching real traffic. The
   seed is re-runnable and never fakes numbers: the Synthèse per agent reflects
   its own seeded slice at the turn grain.

## Consequences

- The fleet is enumerable (`list_agents`) and each `/agents/<id>/*` page has a
  non-empty, agent-specific transcript slice.
- Eval-derived KPIs (resolution, latency, failures) still come from the single
  shared catalogue run, so those numbers are identical across agents until
  per-agent eval lands; only transcript-backed surfaces differentiate in Phase 1.
  This is called out rather than hidden.
- The handoff contract is declared now but only *exercised* by the supervisor in
  Phase 2; the seed plants handoff conversations/events so Phase 2 has data to
  attribute and dedup against.
