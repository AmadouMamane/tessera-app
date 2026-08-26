# 0054 — Layer 3 opens as an option: tone reformulation, with the approved template as REFERENT

- Status: **accepted** (2026-08-26 — the operator commissioned the chantier: « vas sur le
  chantier reformulation recouvrement jusqu'à atterrir complètement ». Slice 1 done by that
  act; slices 2-3 land with the code this record now governs. The compliance pass named in
  Costs remains a precondition to SHADOW — the mode knob therefore defaults to ``off``, not
  ``shadow``, unlike layer 1 — and slice 4 remains the operator's own act.)
- Date: 2026-08-24 (accepted 2026-08-26)
- Supersedes: none
- Superseded by: none
- Relates to: [0053](0053-the-llm-understands-the-code-decides-the-templates-speak.md)
  (the hybrid this extends — its §5 list of things that stay deterministic is NOT touched),
  [0017](0017-agent-observability-contract.md) (the declaration this will amend: a third
  measured plane for recouvrement), [0021](0021-eval-gate-on-measured-contribution.md)
  (the null floor here is the exact template itself), [0030](0030-operable-knobs-carry-a-governed-override.md) /
  [0034](0034-llm-budget-ceiling-is-an-operable-governed-knob.md) (the switch, the
  threshold and the spend answer to the same governance), [0024](0024-every-governed-act-names-its-author.md)
  (a reformulated letter still names who asked for it and why)

## Context

Recouvrement's replies are template-assembled: approved, versioned, regulated wording
(`message_templates.py`), months spelled out, provenance stamped. ADR 0053 deliberately
left them untouched — the LLM READS, the code DECIDES, the templates SPEAK — and named
tone reformulation as a future option requiring its own ADR. The operator asked
(2026-08-24) whether to open it now.

What opening changes, said plainly: **the letter the bank actually sends stops being
deterministic.** That is a regulated, client-facing surface — the exact class of output
the template system exists to control. It is also the point where the faithfulness judge
becomes meaningful for this agent for the first time: today a judged recouvrement reply
has no referent (measured: July's 132 judge rows gave 78 "bad" scores to perfect
regulated letters — noise); with reformulation, **the approved template IS the referent**,
and template-fidelity is a judge metric that means something.

## Decision (proposed)

Open layer 3 as an **option**, behind the same discipline that carried layer 1 from regex
to a governed active mode — no step skipped:

1. **The template is the referent.** The LLM may rewrite TONE only. Facts, amounts,
   dates, deadlines, legal mentions and mandatory clauses are extracted from the approved
   template and must survive verbatim (checked deterministically, not by a judge).
   Anything the checker cannot prove intact → the exact template is sent instead.
2. **Unconditional fallback, like layer 1's regex.** Judge failure, guard refusal,
   timeout, budget ceiling, fidelity below threshold — every failure path sends the
   approved template unchanged. The fallback is the floor (ADR 0021): a reformulation
   ships only where it measurably beats "send the template as-is" on operator-rated
   usefulness without losing a single compliance check.
3. **Shadow first, off the send path.** Reformulations are generated and judged in
   parallel while the template is what actually goes out; fidelity scores, deterministic
   check results and latency land in the ledger. Nothing client-visible changes until the
   flip.
4. **A labeled referent before any flip.** A bench of (template · case context · tone
   instruction) cases ×3 languages, with human-rated fidelity/compliance labels — the
   judge is calibrated against human review before its threshold governs anything
   (an LLM fidelity judge without a calibrated referent is unverifiable, same rule as
   ADR 0053 §7).
5. **Governed knobs, rule fixed / number measured**: `recouvrement.reformulation.mode`
   (`off` · `shadow` · `active`, active unwritable without a stored threshold),
   `.fidelity_threshold` (calibrated from the bench, never hand-picked), `.model`
   (closed catalogue), `.timeout_s`. Every write names its author and reason (ADR 0024).
6. **The declaration evolves** (ADR 0017 amendment, written with the code): recouvrement
   gains a third measured plane — reading (bench + online agreement) · business signals ·
   reformulation (template-fidelity judge) — three rulers, three units, denominators
   never shared, each surfaced the way the reading plane now is (band row by declaration,
   bench on the Évaluations view, counts on the Métier card).

## Costs (named, not hidden)

- **Compliance review is on the critical path**: the prompt, the deterministic
  must-survive checker and the tone-instruction vocabulary need a human compliance pass
  before shadow even starts — a reformulated regulated letter is a legal surface, not a
  UI polish.
- One judge call (plus one generation) per drafted letter — under the ADR 0034 daily
  ceiling; latency lands on the draft path (operator-facing, not client-facing).
- The human-labeled fidelity referent must be built and re-read — the expensive artifact,
  exactly as the intent referent was.
- The mixed risk: a reformulation can be fluent, faithful and still WRONG in register for
  a regulated context; the bench must carry adversarial tone instructions ("be casual",
  "make it funny") whose correct outcome is refusal/fallback.

## Non-goals

The LLM never invents content, never computes money or dates, never addresses the client
outside the drafted letter; ADR 0053 §5 (deterministic forever: regulated wording as
referent, schedule arithmetic, business scoring, output guard) stands unchanged.

## Slices

1. This ADR accepted by the operator.
2. Referent + bench + the deterministic must-survive checker (measured before any LLM).
3. Shadow generation + calibrated fidelity judge + ledger telemetry + ADR 0017 amendment.
4. Threshold calibration + governed flip — the operator's act, citing the bench and the
   shadow numbers, exactly like the 2026-08-24 layer-1 flip.
