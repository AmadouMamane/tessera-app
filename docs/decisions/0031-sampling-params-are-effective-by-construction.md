# 31. A behaviour knob obeys its slider — sampling parameters are effective by construction

Date: 2026-07-17

## Status

Accepted. Direction chosen by Amadou on 2026-07-17 ("il faut lancer et le faire de la façon la
plus premium possible"), after the audit found the sliders cosmetic.

## Context

The per-agent Configurations page (`/agents/<id>/configurations`) has always shown four sampling
sliders — temperature, top-p, frequency penalty, presence penalty — backed by a real durable
store (`agent_config.json`), a real save endpoint and a real change-log. Yet **none of those
values ever reached an LLM call**: the only chat-path invocation (the reporter's synthesis)
hardcodes `temperature=0.2`, and nothing passes top-p or the penalties at all. Worse, the
displayed defaults (0.3 / 0.7 / 0.2 / 0.1) were **fabricated**: numbers no runtime ever used,
presented as the agent's current behaviour. This is exactly the *cosmetic override* failure mode
ADR 0030 names — a Save that "worked" while the system keeps serving the old value — living one
page away from the knob ADR 0030 fixed.

ADR 0030 also poses a boundary question this ADR must answer: should sampling become new keys in
its closed registry (`config_overrides`, superadmin), or stay in the agent-configurations store
(operator)? Two stores both claiming the same knob would recreate the ambiguity the cockpit
audit exists to purge.

## Decision

1. **Identity and behaviour split, one home each.** *Which model speaks* is identity: ADR 0030's
   registry, superadmin-gated (models carry cost and kill-switch implications). *How it samples*
   is behaviour: the per-agent configurations store, operator-gated, edited where it has always
   been displayed — the agent's Configurations page. Neither store ever grows keys of the other
   kind; this ADR is the boundary.

2. **The default is the runtime truth, never a plausible number.** Temperature defaults to
   **0.2** — the value the runtime has actually sent since the first commit. Top-p and the two
   penalties default to **unset**: unset means *not sent*, the backend's own default serves, and
   the UI says "défaut backend" instead of inventing a number. The fabricated 0.3/0.7/0.2/0.1
   defaults are purged. Changing the display is a bugfix of a lie, not a behaviour change: until
   an operator moves a slider, every backend receives exactly what it received before.

3. **Effective by construction, at the same seam as the model.** Sampling is resolved **once per
   turn** at the routing seam (after the supervisor picks the agent), from the agent's effective
   configuration, written into the LangGraph state, and passed by the reporter to the backend
   call — the single chat-path LLM invocation. There is no second path: the slider value and the
   served value cannot diverge, because they are the same read. Eval and shadow turns flow
   through the same seam, so measurement sees the serving behaviour — which is the point.

4. **Honest per backend — a declared capability the tests interrogate.** Backends do not all
   accept the same parameters: Ollama applies all four; Vertex applies temperature and top-p;
   the OpenAI backend applies **none** (reasoning models reject non-default sampling — already
   documented at the call site). The capability of each backend is *declared* next to the
   backends and *verified against the thing* (unit tests assert what each backend actually hands
   its client — ADR 0026). The Configurations page derives, from the agent's **effective model**
   (ADR 0030 resolution) and its serving backend, which sliders apply — and says plainly which
   do not, instead of letting a slider pretend org-wide effect it does not have.

5. **The save is a governed act.** Moving a slider now changes production behaviour, so the save
   names its author — the verified session principal, never a default (ADR 0024) — in the
   durable change-log and in a governance mutation on the audit trail. The existing operator
   gate on the mutations router remains the permission; attribution is the addition.

6. **What serves is what is recorded.** The resolved sampling is stamped on the turn's root span
   (`gen_ai.request.temperature`, and the set parameters) and surfaced in the Debug usage
   payload, alongside the effective model — the trace answers "what was actually sent" without
   trusting the UI.

## Consequences

* The sliders stop being the cockpit's last cosmetic knob: value shown = value resolved = value
  sent (or an explicit "this backend does not apply it").
* Reads fail open to the runtime defaults with a loud log — a corrupt store can never take the
  chat path down; writes keep failing closed (unknown key/value refused, never stored).
* Internal non-chat temperatures stay deliberate and untouched: reflector 0.0, summary 0.1,
  translator 0.1, consistency sampling 0.7 — they are measurement or background tasks, not the agent's
  voice, and no slider governs them.
* The e2e proof writes **safe values** (restoring the runtime default afterwards) because the
  store is shared with the running stack — same discipline as ADR 0030's override tests.
