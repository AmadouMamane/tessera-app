# 0037 — The per-agent system prompt is an overlay, governed by proposal and approval

Date: 2026-07-18
Status: accepted
Extends: 0024 (author + reason), 0026 (a witness interrogates the thing), 0031-0036 (the seam recipe)
Amends: the "prompts are read-only in the UI" posture of the Prompts page (the YAML base REMAINS read-only)

## Context

The repository doctrine is deliberate: prompts live in YAML under
`src/tessera/agent/prompts/{fr,de,en}.yaml`, versioned in git, edited by PR —
and the agent Prompts page says so and mutates nothing. That protects the
guard rules embedded in the system prompt (deposit guarantee, card-theft
escalation, ePrivacy citations…) from casual edits. But it also means NO
prompt adjustment — however small — can happen without a redeploy, and the
business regularly wants exactly that: "add a campaign notice", "mention the
new opening hours", "soften the greeting for this agent".

## Decision

1. **The YAML base stays the only home of the core system prompt.** Nothing
   in this ADR edits, replaces or shadows it. What becomes operable is an
   **overlay**: per-agent complementary directives, appended to the system
   prompt under a clearly-labelled header ("directives complémentaires
   approuvées"), after the ADR 0032 style block. The base's absolute rules
   keep their position and their authority.

2. **Two-person lifecycle, both acts attributed (ADR 0024).**
   - An **operator proposes** a draft (`propose`): free text, capped at 2000
     characters, screened at proposal time by the SAME injection guard that
     screens user input (limes, fail-closed — a draft the guard refuses is
     never stored).
   - A **superadmin reviews** (`review`): `approve` promotes the draft to the
     serving overlay, `reject` discards it, `revoke` retires the serving
     overlay. **Self-approval is refused**: the reviewer must not be the
     proposer — that is the entire point of a two-person rule.
   - Every transition lands in the durable overlay store (draft, approved
     version, capped history) AND in the governance journal
     (`agent_prompt_overlay.*`), each naming its author.
   - Approving an **empty** draft is the governed way to say "no overlay".

3. **Only the APPROVED overlay serves — same seam, same recipe.**
   `resolve_prompt_overlay(agent_id)` runs at the routing seam, lands in
   `state["prompt_overlay"]`, and the reporter appends it (bundle-localized
   header) — never when a console `system_prompt_override` is active
   (verbatim sandbox, ADR 0032 §4). Off-seam paths (eval harness) serve no
   overlay: harness verdicts judge the frozen base. Fail-open to "no
   overlay", loudly.

4. **Said where it lives.** The agent Prompts page — until now fully
   read-only — gains the one governed exception: an "Overlay gouverné" panel
   showing the serving overlay with its full provenance (proposer, approver,
   dates), the pending draft, and the propose/review controls gated by real
   roles (an operator sees propose; only a superadmin sees approve/reject/
   revoke; honest disabled controls otherwise). The page's read-only claim is
   corrected to name the exception.

## Consequences

- Two new governed acts join the frozen registry (13th and 14th), and
  `governed_prefixes` is widened to see their routes (Insight 177 protocol).
- The overlay rides the Debug prompt surface automatically (the assembled
  system prompt is shown verbatim there) — served = visible.
- The guard screening at proposal time is a REUSE of `check_user_input`
  (ADR 0029: limes), not a new detector.
