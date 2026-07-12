# 25. Subject reads will be gated by DECLARED PURPOSE — the target, ruled. Today's posture: role only, said out loud

Date: 2026-07-12

## Status

**Accepted — direction ruled, implementation deferred.** (Operator ruling, 2026-07-12.)

Two things are settled here, and one is deliberately not:

* **Settled**: the target shape is **declared purpose**. Not per-dossier, not per-tenant — those are
  rejected, and the reason is below.
* **Settled**: **today's posture is role-only, and it ships stated plainly.** The README says so,
  and `tests/unit/test_subject_read_posture.py` pins it — including its sharpest case. We publish
  with this posture said in the clear. We do not publish pretending better.
* **Open**: whether a declared purpose may ever *refuse* a read, or only *record* it. That is the
  next ruling, and it is a different question. See *What is still not decided*.

## Context

Audit 2026-07-12, **F-C**. One line in `src/tessera/api/operator.py`:

```python
SUBJECT_READ_ROLES: frozenset[str] = OPERATOR_ROLES   # {admin, auditor, superadmin, collections}
```

Every verified operator may read every subject's transcript, memory inventory and turn detail. A
`collections` operator can read the memory of a customer with no debt file, no case, and no
relationship with recouvrement at all. Nothing in the system expresses *"this subject is mine to
look at."*

The anonymous hole is closed, and **that** was the emergency: before F-4, those endpoints returned
any customer's complete transcript to **anyone on the internet**, with no credential at all. What
replaced it is *"any verified operator"* — an enormous improvement, and not a posture a bank's DPO
would sign.

## Decision

> **A subject read is gated by a DECLARED PURPOSE, recorded in the ledger with the read.**

### Why not per-dossier, and why not per-tenant

Both were on the table. Both are **rejected**, and not on cost — on fit.

They are **access-control shapes borrowed from a CRM**: bind the operator to a record, let them see
what they own. That is the right model when the operator's job is *to work a file*. It is the wrong
model here, because **it fights the operator's actual job**, which is to govern agents **across all
files at once** — read a failing turn wherever it happened, chase a guardrail refusal through
whatever conversation triggered it, audit a fleet's behaviour over a population.

Scoped by dossier, the operator who is supposed to notice that an agent is misbehaving *across*
customers can only look at the customers already assigned to them. The control would be real and
the product would be broken; worse, it would be broken in the direction that hides exactly the
failures Tessera exists to surface. A tenant boundary is the same objection at a coarser grain, plus
a schema migration and a change to the signed assertion payload — a large bill for a shape that does
not match the work.

Rejecting them is not a deferral. It is the finding: **the operator's relationship to a subject is
not ownership. It is an errand.** And an errand has a *reason*.

### Why purpose — and why it is not a new mechanism

**Reading a person's record is an act on a governed system.** It is not a lookup, it is not
plumbing: it is a human deciding to open someone's private conversation. And this repository already
has a doctrine for governed acts, ruled one page earlier:

> [ADR 0024](0024-every-governed-act-names-its-author.md) — *every governed act names its author, derived from a signal the server verified.*

Purpose limitation is that same doctrine's second half. An act leaves a trace **with its reason**.
GDPR Art. 5(1)(b) says exactly this under another name; the regulation is not asking for a new
control, it is asking for the one already written into the ledger's schema.

That is the whole argument, and it is why *purpose* is not a fourth option bolted on to three
access-control designs. It is the only one of the three that is **already the project's doctrine**.

### The slot already exists — and both readers already read it

This is the finding that makes the target cheap, and it should be stated before anyone estimates it:

| | |
|---|---|
| `GuardDecisionRecord.rationale: str` (`agent/state.py:116`) | every act already carries a **reason** field |
| `_record_to_dict` (`guard/audit.py`) | it is already **hashed into the opposable chain** |
| `siem.py:133` — `message=rationale` | it already reaches the **bank's SOC** |
| `routes/audit.py:391` — `decisions=decision_maps` | it already reaches the **cockpit Journal** |

And here is what that field contains today, for a subject access read
(`api/routes/memory.py:151`):

```python
rationale=f"subject access request: {len(stored)} item(s)"
```

**The system describing what it did — not the human saying why they did it.**

The doctrine was in the schema all along. The chain carries it. Both surfaces display it. What is
missing is **the ask**.

## What implementing it looks like (a shape, not a spec)

1. A subject-scoped read carries a **purpose**: a typed reason (`incident`, `réclamation`, `audit`,
   `support`) plus a reference (`INC-4412`, `CL-9981`). **Required, and with no default** — the same
   clause, for the same reason, as `Actor` in ADR 0024: a default hands a plausible reason to an
   operator who never had one, and the trail then reads *justified* while explaining nothing.
2. It **replaces** the system-generated `rationale` on `memory.read`. One field, one meaning: *why
   this happened*, said by whoever caused it.
3. It rides the existing chain to the existing readers. No new store, no new surface, no migration.
4. **Ratchet #3 grows a clause.** `test_governed_acts_name_their_author.py` already asserts that a
   guarded route's entry names its principal. It gains: *a subject read whose `rationale` was
   generated by the system, rather than declared by the caller, is a red.* The ratchet that closed
   the author gap is the same one that closes the reason gap — which is the strongest evidence that
   this really is one doctrine and not two.

## What a declared purpose actually buys — said plainly

It is **deterrence with evidence, not prevention.** The server cannot check that *"incident
INC-4412"* is true. It can make the declaration **mandatory, attributed, and permanent** — so that
reading a stranger's record without a reason becomes impossible, and reading it with a false one
becomes a durable, signed, personally-attributable act that a DPO can find later.

That distinction matters and must not be blurred in a sales conversation: this closes *purpose
limitation as a mechanism*. It does not make a determined insider unable to read a record. If the
threat model needs **prevention**, purpose alone does not deliver it, and that is what the open
question below is about.

## Today's posture — shipped, stated plainly

**Role only.** Any verified operator reads any subject. This is recorded:

* in the **README** (`## Security`), in the same words as here;
* in **`tests/unit/test_subject_read_posture.py`**, which asserts today's behaviour *including its
  sharpest case* — the recouvrement operator reading a subject that is none of its business, **200**
  — and which exists to **go red the day someone tightens it**, so the tightening is a reviewed edit
  and not a silent change that breaks a console nobody was watching.

A test that pins a known gap is not a test that blesses it. It is the difference between a weakness
someone chose and a weakness nobody noticed. **We publish with this posture said in the clear. We do
not publish pretending better.**

## What is still not decided

**May a declared purpose ever be refused?** Recording a reason and *checking* one are different
systems. A gate that can refuse needs a policy over purposes ("`collections` may not open a subject
under `audit`"), an escalation path for the refusal, and an answer to the question of who reviews
the grants — which is a process, and a process is not a mechanism. Until that is ruled, the purpose
is **recorded, not adjudicated**, and this ADR does not pretend otherwise.

## Consequences

**Good.** The direction is chosen on doctrine rather than on convenience, and it turns out to be the
doctrine the project already had. The implementation is bounded — one required field, one ratchet
clause, no migration — because the chain and both of its readers already carry the slot.

**Honest.** Until it lands, every verified operator can read every subject, and the repository says
so in four places rather than none.

**Costly, in the right direction.** Every subject read grows a mandatory question. That is friction
on exactly the path where friction is the product.

## References

- [ADR 0024](0024-every-governed-act-names-its-author.md) — every governed act names its author **and its reason**. This ADR is that doctrine applied to reads.
- `src/tessera/api/operator.py` — `SUBJECT_READ_ROLES`, `OPERATOR_ROLES`, `MUTATION_ROLES`
- `src/tessera/agent/state.py` — `GuardDecisionRecord.rationale`, the slot that already exists
- `tests/unit/test_subject_read_posture.py` — today's posture, pinned
- `tests/unit/test_subject_reads_carry_auth.py` — the read ratchet (a stranger sees nothing)
- GDPR Art. 5(1)(b) purpose limitation, Art. 5(1)(c) data minimisation, Art. 5(2) accountability
