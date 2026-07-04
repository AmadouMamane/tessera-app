# Design note — Input-side PAN redaction (PCI/GDPR hardening)

**Status: PROPOSAL — awaiting review. No code has been written.**

The output leg is done (`guard/redaction.py`: final response + SSE stream,
type-aware masks). The audit leg is done (`adapter._redacted_arguments`: tool
arguments masked in the audit trail). What remains is the **input leg**: a PAN
pasted by the user still enters the LLM context and the durable stores in
clear text. This note maps exactly where, names the tension, and proposes
three options with their trade-offs and the calibration each requires.

## 1. Where the clear-text PAN goes today

A user turn like « ma carte 4970 1012 3456 7890 est refusée, bloquez-la » flows
to five sinks in clear text:

| # | Sink | Where | Durable? |
|---|------|-------|----------|
| 1 | **LLM context, current turn** | `reporter._build_chat_messages` — `current_user_content` appended as the user message (`reporter.py:151`) | no (but leaves the trust boundary toward the model provider on the frontier path) |
| 2 | **LLM context, every later turn in the window** | `context.recent_verbatim` re-injects the raw transcript messages (`reporter.py:150`; window backend `memory/window.py`) | until window rotation |
| 3 | **Durable transcript** (Mechanism A) | `chat.py` persists `ConversationMessage(role="user", content=request.message)` verbatim via `append_messages` → Postgres `conversation_messages` (`memory/transcript.py:255-267`) | **yes** — survives until GDPR erasure |
| 4 | **Memory formation** (Mechanism B) | `chat.py` passes `TurnRecord(user_input=request.message, …)` to `backend.record`; the summary tier persists a summary **plus a literal entity ledger** into `conversation_memory` — `entities._IBAN_RE`/`_ACCOUNT_RE` deliberately capture literal account references (`memory/entities.py:52,101-108`), and `_render_entities` re-injects them into a **system** message on later turns (`reporter.py:142`) | **yes** |
| 5 | **Console Debug surface** | `state["debug_prompt_messages"]` captures the assembled prompt verbatim (`reporter.py:155`) | per-turn, operator-visible |

Notes. `memory/governance.py` screens memory candidates for **injection**
(anti-poisoning), not for PII. The existing PII regex
(`policy.yaml pii.redact_patterns`, 13–19 digit runs) has **no Luhn check** —
fine for output masking, too trigger-happy to rewrite *inputs* with.

## 2. The tension — and why it is softer than it looks

Feared: tools need the **live** PAN, so early redaction breaks card
operations. Measured: **no Tessera tool consumes a full PAN.** `card_block`
takes `card_last_four` (4 digits, `tools/card_block.py:30`);
`account_balance`/`transaction_search` take `customer_id`. The output masks
already preserve the last four (`XXXX XXXX XXXX 6467`). So a mask that keeps
the last four preserves everything any current flow needs — including « voici
mon numéro complet, bloquez cette carte » (the agent still reads the last
four).

The real boundary is therefore **persistence + model context**, not the tool
argument (already audit-masked, and live argument values must keep working).
Two genuine caveats:

- **Guards and extractors want full fidelity.** The exfiltration /
  third-party-PII input guards and `entities.extract_entities` match on the
  raw text; masking *before* them could blind detection (e.g. an IBAN-based
  third-party ask) or corrupt the entity ledger's usefulness.
- **False positives rewrite what the user said.** Rewriting input is more
  invasive than masking output: a 13–19 digit order reference or an IBAN tail
  wrongly masked corrupts the turn for the model *and* the durable record.
  Any input mask must be Luhn-gated and IBAN-context-aware.

## 3. Options

### Option A — mask at the two exits: model-context assembly + persistence *(recommended)*
Mask PAN (Luhn-valid, keep last four) at exactly the points where text leaves
the trusted turn state: (1) inside `_build_chat_messages` over every message
part (current user content, `recent_verbatim`, summary, entity rendering,
long-term items) — which automatically cleans `debug_prompt_messages`; (2) in
`chat.py` before `append_messages` (user message) and before
`backend.record` (TurnRecord); (3) in the entity ledger: screen
`account_refs` so a Luhn-valid PAN is stored masked (IBANs stay, they are
operationally needed and not PCI-scoped).

- ✅ Guards/extractors keep full fidelity (they run on raw state upstream).
- ✅ Model, transcript, summaries, ledger, debug all clean; card flows intact
  (last four preserved).
- ➖ Two seams to hold instead of one; in-memory `state.user_input` stays raw
  for the turn's lifetime (acceptable: process-local, audit already masked).

### Option B — mask once at ingress (router `check_user_input` transform)
One chokepoint: a Luhn-gated PAN transform pattern rewrites
`sanitised_text`, so *everything* downstream (state, planner, workers, LLM,
transcript, memory, debug) is clean.

- ✅ Strongest posture (PAN never exists past the router), simplest to reason
  about.
- ➖ Blinds downstream detection fidelity (third-party guard, entity ledger)
  to the masked span; changes `user_input` echoes in eval cases; highest
  false-positive blast radius (a wrong mask corrupts the whole turn).
- Fit: good **second step** after Option A ships and the mask is calibrated.

### Option C — persistence-only (transcript + memory record)
Mask only sinks 3–4. The current turn's prompt still carries the raw PAN once.

- ✅ Zero behavioural risk on live turns; smallest change.
- ➖ PAN still crosses to the model (frontier path = third-party processor)
  and lingers in the window via `recent_verbatim` until rotation — weak
  PCI story; Debug surface stays raw.

## 4. Calibration required before any merge (Insight 79 discipline)

1. **Real-replay, zero-FP proof**: run the masker (Luhn-gated, IBAN-context
   excluded) over all real transcript user turns (1,559 at last count): every
   masked span is manually reviewed; every digit-run that must NOT mask
   (IBAN bodies, order/ticket refs, phone numbers, account numbers like
   `00098123`) is asserted unmasked. Freeze both sets as unit fixtures.
2. **Harness non-regression**: full 3-agent replays — socle must stay 18/18
   (especially 02/45/46 PII and 14/15 which carry IBANs in prompts), release
   gates stay 3/3, and the closed deterministic cases stay byte-identical.
3. **Live card flow e2e**: paste a full PAN + « bloquez cette carte » on
   :8392 — the turn must still produce a correct `card_last_four` call path
   and a masked transcript row; then replay the same conversation to verify
   later turns see the masked form only.
4. **Erasure/consent unchanged**: GDPR delete + consent gates
   (`memory/governance.py`) re-run green.

## 5. Out of scope here

- IBAN masking on the input side (GDPR-personal but operationally needed;
  revisit after PAN ships).
- Retro-scrubbing already-persisted transcripts (one-off migration, separate
  runbook entry).
- The eval harness path (no transcript persistence; model exposure only —
  covered by whichever option is chosen for the context leg).
