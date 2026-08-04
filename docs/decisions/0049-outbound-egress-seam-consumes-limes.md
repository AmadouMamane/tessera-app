# 49. The outbound answer is guarded for secrets by limes

Date: 2026-08-04

## Status

Accepted. Extends ADR 0028/0029 (Tessera consumes limes for detection) from the
inbound injection leg to the **outbound** leg.

## Context

ADR 0029 made limes the single source of truth for *inbound* injection detection.
The *outbound* leg — what the agent says back — was guarded only by
`tessera.guard.redaction`: a regex-driven, type-aware PII masker
(`apply_output_guard` / `StreamingRedactor`). It masks card numbers, IBANs,
e-mail and phone; it has **no notion of a secret**. A credential a tool result or
a model confabulation put into the answer — an AWS/Stripe/GitHub/Google/Slack key,
a PEM private key, a JWT — would leave in the clear. The null control was the state
of the art.

limes 0.6.0 ships `secrets-egress` (and `pii-egress`), pinned at `b6c368c`. This
ADR wires in the outbound **secret block** — the capability Tessera did not have.

## Decision

**The outbound answer is checked for secrets by limes' `secrets-egress`, on the
RAW answer, before the regex guard.** A secret withholds the whole answer; PII
stays with the first-party guard.

Two decisions inside that, each learned the hard way:

1. **Secrets only; PII stays with the first-party guard.** Tessera *already* masks
   PII on output — and that regex guard is the very baseline limes' `pii-egress`
   was measured against (21/32 vs 32/32, limes ADR 0003). It also owns the PCI
   last-four display (`XXXX XXXX XXXX 4242`) and the harness cases (02/45). Wiring
   `pii-egress` on top would either replace that display with a full `[REDACTED]`
   (breaking PCI presentation and the harness) or double-guard for marginal
   checksum recall. So this leg runs `secrets-egress` only. `pii-egress` recall — a
   second pass over the *already-masked* text to catch a checksummed PAN the regex
   missed — is a clean, deferred follow-up, named here rather than half-built.

2. **On the RAW answer, before the regex guard.** The regex guard's broad IBAN
   shape grazes substrings *inside* a credential: `sk_live_EXAMPLEONLY0000…` reads
   as an `LY`-country IBAN and is masked to `sk_live_EXAMPLEONLYXX XXXX 0000`,
   after which `secrets-egress`'s `sk_(live|test)_…` rule no longer matches and the
   (now partial) secret leaves. A test caught exactly this. So the secret check
   must see the answer *before* the regex touches it. A block short-circuits the
   regex pass entirely (there is nothing left to mask in a withheld answer).

Disposition, fail-closed: a secret `Deny` blocks; `CannotSay` (a detector that
could not look) blocks. There is no redact leg — a credential is withheld whole,
never masked-around.

The guard runs at **both transports**, because `/chat` compiles the graph with
`interrupt_before=[REPORTER]` and the reporter node never executes in production —
a guarantee that lived only in the node the transport skips would not run for real
users (the exact defect ADR-documented for the grounding gate). So:

- **non-SSE** (`reporter.run`, canary/eval/tests): `apply_egress_guard` runs on the
  raw answer before `apply_output_guard`;
- **SSE** (`api/routes/chat.py`, production): each branch captures its RAW answer
  (`"".join(tokens)` for synthesis, the pre-guard text otherwise); after the
  branch, a secret block replaces `final_response` and emits a `turn.correction`
  (reason `egress`) — the same post-hoc correction shape the grounding gate uses.
  The frontend correction schema was widened to accept the new reason.

A withheld answer carries no citations and no confident score, on both legs.

## Consequences

- **A secret never reaches the persisted answer, the transcript, the audit ledger,
  or the eval bundle.** The chain of record is authoritative even when a token
  prefix was shown.
- **Declared residual (SSE synthesis only): a post-hoc correction, not a
  pre-emption.** On the synthesis branch the answer is streamed token-by-token
  before the whole string exists, so `secrets-egress` — which needs the whole
  answer — can only correct mid-stream, identically to the grounding gate. The
  browser may render a fragment of a secret for a frame before the correction; the
  record never does. The draft / fallback / escalation branches do not stream, so
  they have no residual. Pre-empting at the token level would need `StreamingRedactor`'s
  hold-back extended to the secret rules — deferred, named here.
- **The sandbox `pii` override disables the whole egress pass**, as it does the
  first-party guard — the console playground stays able to probe raw output. The
  sandbox is not production.
- **One dependency, one direction.** Tessera imports limes; the egress detector
  adds no new third-party dependency (limes' core is still PyYAML-only). The
  detector identity (`egress_witness`) is available for the same evidence surface
  as the injection witness.
- **Behaviour change.** This is the first outbound *block* Tessera can issue on its
  own answer, measured the same way as every guard (limes' in-package secrets
  matrix plus the Tessera guard suite, with a mutation ratchet that unplugs limes
  and watches the secret leave).
