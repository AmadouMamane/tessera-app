# 0032 — The behaviour selects are effective by construction (tone, detail, max length, top-k)

Date: 2026-07-18
Status: accepted
Extends: 0031 (sampling params are effective by construction), 0026 (a witness interrogates the thing)

## Context

ADR 0031 cured the sampling sliders of the cosmetic disease: a real store, a real
Save, a real change-log — and no LLM call that ever read them. The same page
carries three **selects** with exactly the same disease, one row above the
sliders that were just made honest:

- **Ton** (`tone`: Professionnel / Amical / Direct / Pédagogique) — stored,
  journalled, displayed in the Résumé card… and read by no prompt, no call, no
  node of the chat path.
- **Détail des réponses** (`detail`: Concis / Équilibré / Détaillé) — same.
- **Longueur max des réponses** (`max_length`: Courte / Moyenne / Longue) —
  same, although the `ChatBackend` protocol has carried a `max_output_tokens`
  parameter on all three backends **since it was written** (Ollama
  `num_predict`, Vertex `max_output_tokens`, OpenAI `max_completion_tokens`).
  Nobody passes it from the reporter. The plumbing exists; the tap was never
  connected.

Separately, the sampling family is missing **top-k**, which both Ollama and
Vertex apply and which belongs to the same store, the same governed save, and
the same seam as its four siblings.

## Decision

1. **Same recipe as ADR 0031 — no new machinery.** The behaviour selects are
   resolved **once per turn at the routing seam** (`chat.py`, right after the
   model and the sampling), carried in the graph state (`state["style"]`,
   `state["max_output_tokens"]`), and consumed by the reporter. What the page
   displays and what the turn serves are the same read.

2. **Tone and detail become prompt directives — and the directives live in the
   YAML bundles.** The reporter appends a style block to the system prompt,
   built exclusively from keys in `src/tessera/agent/prompts/{fr,de,en}.yaml`
   (`style_header`, `tone_directive_<slug>`, `detail_directive_<slug>`,
   `length_directive_<slug>`). No prompt text in Python — the repository
   doctrine holds. The durable store keeps the canonical French option values;
   the resolver maps them to ASCII slugs (`Pédagogique → pedagogique`,
   `Équilibré → equilibre`, …) so the YAML keys are locale-stable.

3. **Max length becomes both a soft directive and a hard cap.** The select maps
   to a declared token budget — `Courte = 512`, `Moyenne = 2048`,
   `Longue = 8192` — passed as `max_output_tokens` to the backend (all three
   apply it), *and* to a length directive in the prompt so the model aims for
   the size instead of being truncated mid-sentence. The hard cap is the
   backstop, not the styling tool. `Moyenne = 2048` is deliberately the number
   the Vertex settings default has always sent — on the frontier path the
   default is exactly the historical runtime truth; on Ollama/OpenAI the
   default introduces a cap far above any real support answer.

4. **The sandbox override stays exact.** A console `system_prompt_override`
   replaces the system prompt *verbatim* — no style block is appended. An
   operator probing a raw prompt gets the raw prompt.

5. **Top-k joins the sampling family as the fifth slider** — same store, same
   `resolve_sampling`, same governed save (the existing 12ᵉ act covers it: same
   endpoint, same author attribution), same honesty: unset by default ("Défaut
   backend"), applied by Ollama and Vertex (declared in `SAMPLING_APPLIED`,
   verified against the kwargs each backend hands its client), refused-and-said
   by OpenAI. Integer-valued: the store coerces to a whole number, the backends
   cast to `int`.

6. **Effectiveness is said on the page, next to the control.** Each select
   carries a badge: tone/detail say "Injecté au prompt", max length says
   "≤ N tokens". The runtime block's note now covers the selects as well as the
   sliders. A knob that is not applied somewhere must say so — never silently.

7. **Served = recorded.** `max_output_tokens` is stamped on the turn's root
   span (`gen_ai.request.max_tokens`) beside the sampling attributes, and the
   Debug usage payload carries `style` and `max_output_tokens` alongside
   `sampling`. The assembled system prompt — directives included — was already
   visible verbatim in the Debug prompt surface; that remains the primary
   witness.

## What this deliberately does NOT change

- **Paths that never cross the seam** (eval harness, internal summarisation,
  reflector, translator) keep their historical behaviour: no style block, no
  cap beyond each backend's own defaults. The knobs govern the chat path, as
  the sampling sliders do (ADR 0031).
- **`default_language` stays an identity field** (registry-bound, ADR 0008
  routing); it is not part of this lot.

## Consequences

- The three selects and the five sliders are now uniformly honest: every
  behaviour control on the Configurations page either provably reaches the
  serving call or wears a badge saying it does not.
- The YAML bundles gain 11 keys per language; a unit test asserts the three
  bundles carry the complete directive set, so a missing translation is red,
  not silently English.
- The `_generation_config` helper and `_sampling_options` helper gain a top-k
  parameter; the `ChatBackend` protocol gains `top_k`. `SAMPLING_APPLIED`
  becomes: Ollama ×5, Vertex temperature+top-p+top-k, OpenAI ∅.
