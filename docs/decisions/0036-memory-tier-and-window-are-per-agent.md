# 0036 — The memory tier and window are per-agent, effective by construction

Date: 2026-07-18
Status: accepted
Extends: 0007 (agent memory architecture), 0031-0033 (the seam recipe)

## Context

ADR 0007 built a pluggable memory architecture — window / summary / persistent
tiers behind one `MemoryBackend` protocol — and then wired it process-wide:
`get_memory_backend()` is a singleton resolved from `settings.memory.backend`,
and the recency window is `settings.memory.history_window` (6) for everyone.
The architecture was per-agent-ready from day one (every backend constructor
accepts `history_window`); only the selection was global.

## Decision

1. **Two per-agent knobs in the agent-configurations store** (operator,
   governed save):
   - `memory_backend` — the tier: unset = the org default from settings
     (window, said as "Défaut org (window)"), or one of the three first-party
     tiers (Fenêtre / Résumé / Persistante). The external adapters (langmem /
     mem0 / zep) are deliberately NOT offered per agent: they are optional
     extras that may not be installed, and a knob that can select an
     uninstalled backend would be a lie.
   - `memory_window` — the verbatim recency window, unset = the org default
     (settings, 6), clamped [2, 20], integer.

2. **Same seam.** `resolve_memory(agent_id)` runs once per turn at the routing
   seam, lands in `state["memory"]`, and the reporter's message assembly
   resolves its backend through `memory_backend_for(name, history_window)` — a
   cached per-(tier, window) factory that falls back to the process-wide
   singleton when both are unset. Off-seam paths keep the singleton: the eval
   harness and the reflector are unchanged.

3. **Governance is tier-independent.** The persistent tier's consent gate,
   PII screening, TTL and erasure (ADR 0007 §governance) live in the backend,
   not in the selection: an agent flipped to Persistante gets exactly the
   same `governance.py` screens as the org-wide setting would.

4. **Said on the page.** A "Mémoire" block on the Configurations page: the
   tier select (honest org-default option), the window slider (honest unset
   label), and the note naming the ADR 0007 tiers. The Debug memory surface
   already names the backend class that served the turn — that witness now
   varies per agent and stays the proof.

## Consequences

- `get_memory_backend()` remains the org default; nothing constructs external
  adapters per agent.
- A per-agent window changes ONLY the verbatim recency slice; the durable
  transcript (Mechanism A) records everything regardless — no data is lost by
  a narrow window, only less is replayed verbatim.
