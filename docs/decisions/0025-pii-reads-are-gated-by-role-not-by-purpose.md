# 25. Subject reads will be gated by DECLARED PURPOSE — the target, ruled. Today's posture: role only, said out loud

Date: 2026-07-12

## Status

**Accepted — direction and sequencing ruled; implementation not started.**
(Operator rulings, 2026-07-12.)

Everything on this page is now settled, including the question this ADR originally left open:

* **The target shape is `declared purpose`.** Not per-dossier, not per-tenant — those are rejected,
  and the reason is *fit*, not cost. See §*Why not per-dossier, and why not per-tenant*.
* **The sequencing is `record → measure → perhaps refuse`.** A purpose may **not** be refused today,
  and possibly never: refusing needs a taxonomy, a policy and a review process that do not exist —
  and a purpose-check that is bypassed under pressure is **worse than no check**. See §*Sequencing*.
* **Today's posture — role only — ships, stated plainly.** The README says so, and
  `tests/unit/test_subject_read_posture.py` pins it, including its sharpest case. **We publish with
  this posture said in the clear. We do not publish pretending better.**

What remains is **work, not decisions**: phase 1 (recording) is scoped in §*What implementing it
looks like* and has not been built. It is not a commit — it changes the wire contract of every
subject read, so the cockpit has to *ask*, and that is a lane.

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

## What phase 1 looks like (a shape, not a spec)

> **A correction, kept on the record.** The first draft of this section specified *"a typed reason
> (`incident`, `réclamation`, `audit`, `support`)"*. That is **an invented taxonomy, written before
> a single purpose has been declared** — precisely the mistake §*Sequencing* exists to forbid, made
> inside the paragraph that forbids it. A dropdown would have measured *this list*, and the phase-2
> data would have confirmed the hypothesis it was fitted to. It is struck, and the reason is left
> visible because the mistake is that easy to make.

1. A subject-scoped read carries a **purpose**: **free text**, plus a **required reference**
   (`INC-4412`, `CL-9981`) — the reference being the only part checkable against something that
   exists outside this system. **No enum. No dropdown. Not yet**: the vocabulary is phase 2's
   *output*, never phase 1's input.
   **Required, and with no default** — the same clause, for the same reason, as `Actor` in ADR 0024:
   a default hands a plausible reason to an operator who never had one, and the trail then reads
   *justified* while explaining nothing.
2. It **replaces** the system-generated `rationale` on `memory.read`. One field, one meaning: *why
   this happened*, said by whoever caused it.
3. It rides the existing chain to the existing readers. No new store, no new surface, no migration.
4. **Ratchet #3 grows a clause.** `test_governed_acts_name_their_author.py` already asserts that a
   guarded route's entry names its principal. It gains: *a subject read whose `rationale` was
   generated by the system, rather than declared by the caller, is a red.* The ratchet that closed
   the author gap is the same one that closes the reason gap — which is the strongest evidence that
   this really is one doctrine and not two.
5. **It is a lane, not a commit** — and the reason is worth stating, because it is the only real
   cost in the whole design. A *required* field on a subject read means **the cockpit has to ask**.
   Shipping the backend half alone would answer **422** to every transcript the console opens; the
   UI surface (a purpose prompt on the read path, in three languages) is the work.

## What phase 2 reports, and in which order

The first number is **not** the distribution of purposes. It is the **null floor**:

| # | the question | why it comes first |
|---|---|---|
| 1 | what share of reads were justified by a string that appears in more than *N*% of all declarations? | the **null declaration** — `"check"`, `"-"`, the same text every time. This is the population a taxonomy must be built *against*. If it is high, **the ask is not landing**, and no policy built on it will land either. |
| 2 | the distribution of the remaining declarations | only now is there anything to categorise |
| 3 | which references (`INC-…`, `CL-…`) resolve to something real | the one part of a declaration that is checkable outside this system |
| 4 | is there a class of read that should never have happened? | **the only thing that authorises phase 3** |

## What a declared purpose actually buys — said plainly

It is **deterrence with evidence, not prevention.** The server cannot check that *"incident
INC-4412"* is true. It can make the declaration **mandatory, attributed, and permanent** — so that
reading a stranger's record without a reason becomes impossible, and reading it with a false one
becomes a durable, signed, personally-attributable act that a DPO can find later.

That distinction matters and must not be blurred in a sales conversation: this closes *purpose
limitation as a mechanism*. It does not make a determined insider unable to read a record. If the
threat model needs **prevention**, purpose alone does not deliver it.

And — this is the part a compliance deck will want to smooth over — **prevention may never be worth
building here.** §*Sequencing* rules that a refusal is only worth having if it can hold without an
emergency bypass, and every SOC has a break-glass. If it turns out it cannot hold, then *this*, the
recording, is the whole control. It should be sold as the whole control: **an act on someone's
private record is impossible to perform anonymously, impossible to perform without stating why, and
impossible to erase afterwards.** That is a real guarantee and a defensible one. What it is not is
prevention, and the day we call it prevention is the day it stops being worth anything.

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

## Sequencing — ruled 2026-07-12: record, then measure, then *perhaps* refuse

**May a declared purpose ever be refused? Not now** — and the reason is not that it is hard.

Refusing needs three things that do not exist: a **taxonomy** of legitimate purposes; a **policy**
(which role may invoke which purpose); and a **review process** for the grants — knowing that a real
incident does not wait for an approval.

### The trap, and it is the whole argument

**A purpose-check that gets bypassed under pressure is worse than no check at all.** It manufactures
the *appearance* of prevention while the emergency path stays wide open. Every SOC has its
break-glass account. Building purpose-refusal and then giving yourself a break-glass is building
compliance theatre on top of an unguarded door — and the theatre is what gets shown to the auditor.

So, in this order:

1. **NOW — RECORD.** Mandatory, attributed, permanent. No refusal, no policy, no taxonomy. The read
   happens; the reason is in the chain, beside the author, forever. **Deterrence with evidence.**
2. **THEN — MEASURE.** Once purposes are recorded, we can see **what people actually declare**. A
   taxonomy built on purposes invented in advance is one more invented number.
3. **ONLY THEN — REFUSE**, and only *if* the data shows a class of read that should never happen —
   and only if it can be refused **without an escape hatch** (see below).

### Why: do not set a threshold before you have measured both populations

This project has already paid for this lesson once, in the eval lane
([ADR 0021](0021-eval-gate-on-measured-contribution.md)). The failure catalogue scores **122/174 —
70% — with no language model at all**: the deterministic layers do that much on their own. And the
three per-agent domain bars, set at 55/65/55%, sat **below** the null control's 72/89/61%. **Every
one of them was a gate a disconnected agent already clears.** They were thresholds chosen before the
null population had been measured, and they graded nothing while printing a confident PASS.

A purpose taxonomy designed before the first purpose is declared is that same mistake, in a
different column.

### Phase 2 has its own null floor — and skipping it is how phase 2 fails

The eval lane's lesson was not merely *"measure first"*. It was sharper: **measure what the system
produces when the thing under test is absent.** The purpose field has exactly such a floor.

**What does a purpose field produce when the human is not thinking?** The first option in the
dropdown. `"check"`. `"-"`. The same string, every time. That is the **null declaration**, and it is
the population a taxonomy must be built *against*, not on top of. A taxonomy fitted to reflexive
declarations grades nothing — it prints a category next to a read that nobody justified.

Two consequences for how phase 1 is built. They are design constraints, not preferences:

* **No dropdown during the measurement window.** A dropdown measures *your taxonomy*, not *their
  reasons*: it fits the data to the hypothesis before the hypothesis has been tested. Free text plus
  a **required reference** (`INC-4412`, `CL-9981`) — the reference is what makes a declaration
  checkable against something that exists outside this system.
* **The degenerate declarations get counted, by name, and reported first.** *"What share of reads
  were justified by a string that appears in more than N% of all declarations?"* is the null-floor
  question, and it is phase 2's first number. If it is high, the answer is not a taxonomy — it is
  that **the ask is not landing**, and no policy built on top of it will land either.

### The precondition for phase 3, which follows from the trap

> **If a refusal cannot be built without an emergency bypass, do not build the refusal.**

The moment a break-glass exists, the refusal is theatre and the recording was the real control all
along. That is not an argument against recording — it is the argument that **recording IS the
control**, and that it should be sold as exactly what it is: deterrence with evidence, honest about
its nature. A refusal is only worth building if it can hold on the day it is inconvenient, and that
is a question about the organisation, not about the code.

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
