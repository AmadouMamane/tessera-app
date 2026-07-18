# 0033 — The escalation threshold is an operable, governed knob

Date: 2026-07-18
Status: accepted
Extends: 0031/0032 (effective by construction), 0024 (a governed act names its author)

## Context

The reviewer node fuses three deterministic signals into a confidence score —
grounding × 0.5 + coverage × 0.3 + guard × 0.2 — and flips
`needs_escalation` when the score falls below
`GuardSettings.escalation_confidence_threshold` (default **0.6**). That
threshold is THE business knob of the human-in-the-loop layer: move it up and
the agent hands more turns to a human; move it down and it answers more on its
own. Today it is frozen in the settings (env + git): changing it for one agent,
or at all without a redeploy, is impossible. Every other behaviour knob on the
Configurations page has just been made effective (ADR 0031/0032); the
escalation threshold is the one the business would actually reach for first.

## Decision

1. **Per-agent knob, org default = the settings value.** The durable
   agent-configurations store gains `escalation_threshold` (default unset).
   Unset means the org-wide settings value serves (0.6 unless the deployment
   overrides `TESSERA_GUARD_ESCALATION_CONFIDENCE_THRESHOLD`) — displayed as
   "Défaut org (0,60)", never an invented number. Set means this agent
   escalates at its own bar. Clamped to [0, 1] on save, like every slider.

2. **Same seam, same recipe.** `resolve_escalation_threshold(agent_id)` runs
   once per turn at the routing seam (chat.py, beside the model, the sampling
   and the style), lands in `state["escalation_threshold"]`, and the reviewer
   reads THE STATE — falling back to the settings only on paths that never
   crossed the seam (eval harness, direct graph runs), which keep their
   historical behaviour. Fail-open to the org default, loudly.

3. **Governed save, unchanged surface.** The knob is saved through the same
   agent-configurations endpoint — operator role, author attribution, durable
   change-log, `agent_config.updated` governance event. No new route, no new
   act: the 12th act's scope grows by one key.

4. **Said on the page.** The Configurations page gains an "Escalade humaine"
   block: the slider, the formula (the real reviewer arithmetic, not prose
   approximations), and where the org default comes from. The Debug reviewer
   surface shows the threshold the turn actually used.

5. **Recorded.** The seam stamps `tessera.escalation.threshold` on the turn's
   root span.

## Consequences

- The eval harness stays deterministic: harness states never cross the chat
  seam, so its reviewer verdicts keep reading the frozen settings value.
- A per-agent threshold is a business decision on a guard behaviour — the
  change-log names who moved it and when; the trace names what served.
