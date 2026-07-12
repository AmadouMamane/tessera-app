# 24. Every governed act names its author; every configuration that cannot hold a guarantee refuses to boot

Date: 2026-07-12

## Status

Accepted. Supersedes nothing. Generalises [ADR 0023](0023-audit-chain-independent-of-sink.md),
whose second clause turns out to be one half of a larger rule.

## Context

Between 2026-07-10 and 2026-07-12 a 360° audit produced what looked like four unrelated
findings, each fixed on its own branch by a different mechanism.

| | the finding | how it was fixed |
|---|---|---|
| **F-1** | `POST /recouvrement-assistant/action` had no auth, and its `requested_by` — the name the ledger records as having acted — was a **body field with a default** | a guard, and the name taken from the verified assertion |
| **F-5** | the GDPR mutations sat behind `require_bearer`, which authenticates the **frontend service**, not a person. An anonymous caller got **204** from `DELETE /memory/{id}` | an identity guard |
| **F-6** | `enqueue_ledger_entry` ran `if sink == "file"`, so the documented staging sink chained **nothing** into the opposable ledger | ADR 0023: the sink is a transport, the ledger is a store |
| **F-B** | after F-5, the door was shut — and the ledger still recorded that *a subject had been erased* with **no field for who erased them**, ever | this ADR |

Filed as four bugs, they were fixed four times. They are one bug, and the fourth is the one that
shows it: **the system was willing to record that something had happened without recording who
caused it, and willing to accept a configuration that removed a guarantee without saying so.**

Two more instances, found while closing F-B, put it beyond doubt:

* the **cockpit Journal** keyed its actor column on `type.startswith("tessera.agent.")`. The
  erasure's type is `tessera.guard.audit`, so it fell through to `model or target` and displayed
  **the LLM's model name** as the person who deleted a customer's record.
* the **SIEM export** did `actor = arguments["subject_id"]` — so a `memory.forget`, which it
  itself classifies `iam`/severity 7, reached the bank's SOC naming **the erased data subject as
  the author of their own erasure**.

Both had passing tests. The tests asserted the bug (`assert export.events[0].actor == "s1"`,
`assert entry.actor == "llama3.2:3b"`). That is *why* two human reviews missed them: the
confusion was green.

For a product whose entire thesis is the **opposable audit trail**, this is the most expensive
class of defect available. It does not fail loudly. It produces a record that *looks* complete.

## Decision

Two rules. They are the same rule, said about facts and about configuration.

> **1. Every governed act names its author, derived from a signal the server verified.**
>
> **1b. And its reason.**
>
> **2. Every configuration that cannot hold a guarantee refuses to start.**

### On rule 1b — the author is *verified*, the reason is *declared*

The two halves are not symmetric, and pretending they are is how a purpose field becomes theatre.

The **author** is a fact the server establishes: the principal of an HMAC-signed assertion whose key
the browser never holds. The caller cannot choose it. The **reason** is a *claim the caller makes*.
The server cannot check that `incident INC-4412` is true, and no amount of engineering will let it.

What it *can* do is make the claim **mandatory, attributed, and permanent** — so that acting without
a reason becomes impossible, and acting under a false one becomes a durable, signed, personally
attributable act somebody can find later. That is purpose limitation **as a mechanism**, and it is
weaker than prevention. It should be sold as exactly what it is.

The slot for it already exists and has since the beginning: `GuardDecisionRecord.rationale` is
hashed into the chain, and it already reaches both readers — the SIEM export (`message`) and the
cockpit Journal (`decisions[]`). What is missing is not a field. It is **the ask**: today a subject
read fills that slot with `"subject access request: 3 item(s)"` — *the system describing what it
did*, where the doctrine wants *the human saying why they did it*. Ruled, and scoped, in
[ADR 0025](0025-pii-reads-are-gated-by-role-not-by-purpose.md).

### What follows from rule 1

* An **actor is a type**, not a string: `Actor(principal, role)` (`tessera/authz.py`), rejecting
  the empty value at construction.
* There are exactly **two** ways to obtain one, and both are explicit at the call site:
  `actor_of(session)` — the principal of an HMAC-signed operator assertion the server verified —
  and `Actor.system(task)` — a **named** non-human origin. `system:retention-purge` is a name.
  `""` is not, and neither is a bare `"system"`.
* **No default, anywhere, ever.** This is the load-bearing clause and it is not a style
  preference. A default on an identity field hands a plausible name to an author who forgot the
  question, and the trail then reads *complete* while naming nobody. **A gap gets found; a
  plausible lie does not.** Every candidate default in this codebase was live at some point:
  `actor="operator"` (a role, not a person), `requested_by="Julie Dubois"` (a fabricated human),
  `arguments["subject_id"]` (the victim), `model` (a program).
* The name may **never** come from the request. Not the body — a caller who can pick the name in
  the ledger can pin an act on a colleague, which is F-1. Not the bearer — it names the frontend
  service the BFF attaches for *every* visitor, which is F-5 and is why a bearer can never
  authenticate a human.
* The actor lives at the **top level** of the entry, beside `target` and `outcome`. A name
  written where no reader looks is durable and unread, which is worse than absent: it lets a
  false assurance ("the erasure is attributed") coexist with a false display ("the model did
  it"). This is not hypothetical — it is exactly what the first attempt at this fix shipped.
* **An act with no entry at all is the same defect, one step further on.** Consent (the *lawful
  basis* for retaining a person's data) and the retention purge (which *deletes* it) each wrote
  nothing whatsoever. Both now write, and the purge names each subject it purged rather than
  reporting a row count — "417 rows deleted" is not a record of processing *anybody*.

### What follows from rule 2

Already law for the audit chain (ADR 0023 → `validate_audit_chain_config`), the three signing
keys (ADR 0020), and the default credentials (F-9). Generalised here: **a posture that cannot
keep a promise the product makes must refuse to run, not run quietly without it.** The shape to
refuse is the *silent union* — a configuration value that removes a guarantee as a side effect
and reports success. Three were live in one week: `extra="ignore"` swallowing a misspelled
settings field; a wrong `response_model` silently stripping 20 fields from a response;
`audit_sink=cloud_logging` cutting the opposable chain.

## Enforcement

The doctrine is a sentence; these are the three mechanisms that make it a fact. Each is
**mutation-tested** — a ratchet nobody has seen red is not a ratchet — and each asks a question
the other two cannot.

| ratchet | question | how it decides |
|---|---|---|
| `test_mutation_routes_carry_auth.py` | **who may come in?** | every identity guard is CALLED with the request a stranger actually sends — the correct service bearer and no identity — and must raise 401. `require_bearer` fails this by construction, so it can never re-enter the set. |
| `test_subject_reads_carry_auth.py` | **what does a stranger see?** | a canary is seeded into every subject store and every GET is swept anonymously. If it comes back, red. **The payload is the judge**, not the handler's intent — it caught three leaks two reviews had filed as aggregates. |
| `test_governed_acts_name_their_author.py` | **does the register name the author?** | every mutating route behind an identity guard is invoked with a *verified* session; the entries it writes are captured **at `_append_to_chain`**, and must name that session's principal — not empty, not `system:`, not the subject, not the model. |

Plus `mypy --strict`, which is the cheapest enforcement of all: `actor` has no default, so a call
site that forgets it does not compile.

The third ratchet's own mutation test is the argument for this ADR, in one line: burying the
actor in `arguments[]` — the first, plausible, *already-written* fix — turns it **red**.

## Consequences

**Good.** The question "who deleted this subject's record?" has an answer, and it is one the
caller could not have chosen. The Journal and the SIEM read the same field the emitter writes.
`purge_expired` accounts for what it deletes, per person. The audit entry is **version 3**, and
the bump is deliberate: a v2 entry has no author because the schema had none — an honest
historical gap — while a v3 entry always has one. Adding the field silently would have collapsed
*old* and *broken* into one unreadable state, and a regulator resolves that ambiguity against the
controller.

**Costly.** Twenty call sites had to answer a question they had been ducking, and every future
one must too. That is the point, and it is the only version of this that survives contact with a
sixth agent and a bad night.

**Owed, and named rather than quietly skipped.** These are governed acts that still write no
ledger entry at all — the same class, out of scope for this lane, and now on the record:

* `POST /observability/agent-garde-fous/rule-state` — **switching a guardrail off** writes nothing.
* `PUT /settings/synthesis-admin` — a superadmin privilege grant, no trace.
* `emit_agent_proposed` / `emit_agent_lifecycle` — **promoting an agent to production** is
  attributed to the literal string `"operator"`, which is a role and not a person.
* `agent/recouvrement.py` — `requested_by: str = "Julie Dubois"` **is still there** as a default
  one level below the handler, and the 32 business events on the human action path still carry
  `actor="system"` on the envelope.
* `curation_store.set_decision(decided_by=body.decided_by)` — an actor **taken from the request
  body**, which is F-1 exactly, still open.

## References

- [ADR 0023](0023-audit-chain-independent-of-sink.md) — the sink is a transport, the ledger is a store (rule 2, first instance)
- [ADR 0020](0020-security-hardening.md) — the fail-closed signing keys (rule 2)
- `src/tessera/api/operator.py` — the signed operator assertion: where a verified principal comes
  from. Cited by file and not by number on purpose: **`0010` is the repository's one unresolved
  ADR collision** (two files carry it; see `docs/status/adr-renumber-evidence.md`), and an ADR
  about not recording things ambiguously will not cite an ambiguous reference.
- `docs/status/audit-360-remediation-run.md` — the run that produced this, with the live before/after
- GDPR Art. 5(2) (accountability), Art. 30 (records of processing), Art. 17 (erasure)
