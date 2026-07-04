# Design note — Input-side PAN redaction (PCI/GDPR hardening)

**Status: ACCEPTED — Option A implemented; the §5 calibration gate has run
green (as-run results at the end of §5). Awaiting pre-push review of the
declared residuals.**

The output leg is done (`guard/redaction.py`: final response + SSE stream,
type-aware masks). The audit leg is done (`adapter._redacted_arguments`: tool
arguments masked in the audit trail). What remains is the **input leg**: a PAN
pasted by the user still enters the LLM context and the durable stores in
clear text. This note maps exactly where, names the tension, and proposes
three options with their trade-offs and the calibration each requires.

## 1. Where the clear-text PAN goes today

A user turn like « ma carte 4242 4242 4242 4242 est refusée, bloquez-la » flows
to six sinks in clear text (the earlier draft of this note used
`4970 1012 3456 7890` here — that number is Luhn-**invalid**, i.e. exactly the
declared residual the accepted mask does *not* rewrite; kept as a test case):

| # | Sink | Where | Durable? |
|---|------|-------|----------|
| 1 | **LLM context, current turn** | `reporter._build_chat_messages` — `current_user_content` appended as the user message (`reporter.py:151`) | no (but leaves the trust boundary toward the model provider on the frontier path) |
| 2 | **LLM context, every later turn in the window** | `context.recent_verbatim` re-injects the raw transcript messages (`reporter.py:150`; window backend `memory/window.py`) | until window rotation |
| 3 | **Durable transcript** (Mechanism A) | `chat.py` persists `ConversationMessage(role="user", content=request.message)` verbatim via `append_messages` → Postgres `conversation_messages` (`memory/transcript.py:231-278`) | **yes** — survives until GDPR erasure |
| 4 | **Memory formation** (Mechanism B) | `chat.py` passes `TurnRecord(user_input=request.message, …)` to `backend.record`; the summary tier persists a summary **plus a literal entity ledger** into `conversation_memory` — `entities._IBAN_RE`/`_ACCOUNT_RE` deliberately capture literal account references (`memory/entities.py:52-56,106-109`), and `_render_entities` re-injects them into a **system** message on later turns (`reporter.py:142`) | **yes** |
| 5 | **Console Debug surface** | `state["debug_prompt_messages"]` captures the assembled prompt verbatim (`reporter.py:155`) | per-turn, operator-visible |
| 6 | **Online eval + replay bundle** | `chat.py` hands the raw `question` (= the user message) to `_run_online_eval`: the LLM judge reads it (`observability/eval/online.py`) and `replay.capture_bundle` appends it to the durable `bundles.jsonl` (`observability/replay.py:95-103`) | **yes** — JSONL append-only, survives restarts |

Sink 6 was found during implementation — the original note stopped at five.
Two further **cold-path model calls** read raw turn text and belong to the same
exposure class as sinks 1–2 (model context, not persistence): the summariser
input (`summary._summarise` over `older_text`) and the reflector's fact
extraction (`reflector._extract_facts`, `Customer: {user_input}` exchange).
Both are masked at their call sites in the implementation.

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

## 4. Design refinements locked at acceptance

1. **One primitive.** A single `mask_pan()` (in `guard/redaction.py`, beside
   the output-leg masks) is the only function any seam calls — same Luhn gate,
   same IBAN-context exclusion, same `XXXX XXXX XXXX 6467` form everywhere. No
   seam re-implements detection.
2. **Defence-in-depth backstop at durable persistence.**
   `transcript.append_messages` and the memory layer's durable writes
   (`summary.save_summary`, `persistent.upsert_memory`) defensively apply
   `mask_pan()` to what they are about to store and log a WARNING («couture
   manquée» / missed seam) when it changes anything — the durable stores
   structurally cannot contain a Luhn-valid PAN even if an upstream seam is
   missed or a new caller appears. **Fail-safe, not fail-closed**: the write
   proceeds with the masked text; it is never rejected (losing the
   conversational record would be the worse failure).
3. **Idempotence invariant.** `mask_pan(mask_pan(x)) == mask_pan(x)` is
   asserted in the unit suite (the masked form carries no 13–19 digit run, so
   a second pass is a no-op by construction).
4. **Declared residual.** A Luhn-INVALID card-shaped run (e.g. a customer
   typo) is **not** masked — the price of the anti-false-positive gating,
   accepted: rewriting what the user said on a ~10 % coincidence budget is
   worse than persisting a number that is not a valid PAN. Written down here
   so the gap is never read later as an oversight.
5. **Option B stays the roadmap.** Ingress masking (router transform) remains
   the planned second step once this mask has real-corpus calibration behind
   it — GDPR data minimisation: the PAN then never exists past the router, so
   even the transient in-process copies this option accepts (`state.user_input`
   for the turn's lifetime) disappear, and less PII is held at rest overall.

As-built precision on Option A seam (2): the `TurnRecord` handed to
`backend.record` stays **raw** so entity extraction keeps full detection
fidelity; the masking sits *inside* the memory layer at its two exit classes —
the cold-path model calls (`summary._summarise` input,
`reflector._extract_facts` exchange) and the durable writes (refinement 2,
plus the designed `account_refs` screening: a Luhn-valid PAN captured as an
account reference is stored masked, IBANs stay). The online-eval leg (sink 6)
is masked at its `chat.py` call site.

## 5. Calibration required before any merge (Insight 79 discipline)

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

### As-run calibration results (2026-07-04)

1. **Real-replay** (`scripts/calibrate_pan_mask.py`, cross-checked with an
   independent SQL census): 3,260 transcript rows / 1,630 user turns (the
   corpus had grown past the 1,559 of the first draft). One masked span — the
   Luhn-valid test PAN a user pasted (`…0343 6467`, correct last four,
   reviewed) — and one declined candidate (a 13-digit Luhn-invalid probe
   reference, untouched, reviewed). Zero false positives; both sets frozen in
   `tests/unit/fixtures/pan_corpus.json` + `test_pan_corpus_fixtures.py`. The
   real corpus carries almost no card-shaped runs, so the discrimination
   burden (IBANs, refs, phones, amounts) is pinned by the 40-case synthetic
   suite in `test_pan_input_mask.py`.
2. **Harness**: release gates 3/3 agents, run **twice** each — all six runs
   exit 0, zero critical failures; socle 18/18 per agent per run (02/45/46
   included); IBAN cases 14/15 pass; the closed deterministic set is
   byte-identical across both runs for all three agents. Standard-tier rates
   (91.9–93.5 % / 94.1–95.1 % / 78.4–82.4 %) sit at the T1 close-out levels
   within known sampling noise.
3. **Live e2e** (:8392, customer session, persistent memory tier): full PAN +
   « bloquez cette carte » → the vetted card-opposition path
   (`ticket_escalate` succeeded; note: no worker invokes the `card_block`
   tool on the deterministic graph — the card flow is escalation/lookup, so
   "last four preserved" is about the *stored and prompted* text); the durable
   transcript row is stored masked; the next turn's assembled prompt carries
   only the masked form; a synthesis turn's prompt carries only the masked
   form; the replay bundle's `question` is stored masked; a Luhn-invalid PAN
   persists verbatim (the declared §4.4 residual, observed live). Zero
   "missed seam" backstop warnings during live traffic — the upstream seams
   are complete.
4. **Erasure/consent**: the governance integration tests (consent gate,
   reflector write, total erasure) run green against live Postgres.

## 6. Out of scope here

- IBAN masking on the input side (GDPR-personal but operationally needed;
  revisit after PAN ships).
- Retro-scrubbing already-persisted transcripts (one-off migration, separate
  runbook entry).
- The eval harness path (no transcript persistence; model exposure only —
  covered by whichever option is chosen for the context leg).
