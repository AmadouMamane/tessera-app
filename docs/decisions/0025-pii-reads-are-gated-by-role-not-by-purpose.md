# 25. PII reads are gated by ROLE, not by PURPOSE — stated, dated, and not yet decided

Date: 2026-07-12

## Status

**Proposed — posture recorded, decision deferred.** No code changes. The current behaviour is
pinned by a test (`tests/unit/test_subject_read_posture.py`) so that it cannot drift, in either
direction, without somebody reading this page.

This is deliberately not a fix. Choosing *which* operator may read *which* subject is a product
decision about how Tessera is sold and operated, and the person writing this does not have the
inputs to make it.

## Context

Audit 2026-07-12, **F-C**. One line, in `src/tessera/api/operator.py`:

```python
SUBJECT_READ_ROLES: frozenset[str] = OPERATOR_ROLES   # = {admin, auditor, superadmin, collections}
```

So **every operator, of every role, may read the transcript, memory inventory and turn detail of
every subject in the system** — a `collections` operator included, and `collections` is the role
whose console exists to work one debt file at a time.

The anonymous hole is closed and that is real progress: before F-4, `GET
/observability/conversation-messages?conversation_id=…` returned any conversation's complete
transcript to **anyone on the internet**, with no credential at all. What replaced it is *"any
verified operator"*. That is an enormous improvement and it is **not a defensible GDPR posture for
a real tenant**, because it contains no notion of *purpose*:

* Nothing anywhere says **"this subject is mine to look at."**
* A recouvrement agent handling one file can read the chat history of every other customer of the
  bank, including customers who have no debt and no relationship with recouvrement at all.
* The trail now records **who** read a record (this lane's other half, [ADR 0024](0024-every-governed-act-names-its-author.md)) — which makes the gap *visible*
  and, notably, does not close it. Being able to prove after the fact that Alice read Bob's
  transcript is accountability; it is not purpose limitation (GDPR Art. 5(1)(b)), and it is not
  data minimisation (Art. 5(1)(c)).

Two honest observations that bound how urgent this is:

* Today Tessera is a **single-tenant reference implementation with a demo corpus**. "Every
  operator" is a handful of seeded accounts, and the subjects are generated. Nobody's real chat
  history is exposed to anybody.
* The moment there is a second tenant, or one real customer, this line is a finding. It is
  cheaper to decide the shape now, while the answer is still free to choose, than after a schema
  exists that assumes the flat one.

## The decision to be made

**What binds an operator to a subject?** Three shapes, with what each actually costs.

### Option A — scope by *dossier* (case ownership)

A subject is readable by the operators assigned to a case that references it.

* **Needs**: a case↔operator assignment table, and a case↔subject link. Recouvrement already has
  the notion of a *dossier* (`case_id`), so half of this exists.
* **Cost**: every subject-scoped read grows a join and an authorization query. The cockpit's
  "Récents" list stops being "the last N conversations" and becomes "the last N conversations
  *you may see*" — which changes several endpoints from a `SELECT` into a filtered one, and
  changes the front's empty states.
* **Sharp edge**: what does an `auditor` see? An audit role that can only audit its own cases is
  not an audit role. This option needs a documented override, and an override is exactly where a
  purpose limitation quietly becomes a formality again.
* **Fits**: the recouvrement business plane, almost exactly.
* **Does not fit**: the platform-operator surfaces (fleet, eval, guardrails), where there is no
  case at all.

### Option B — scope by *tenant*

A subject belongs to a tenant; an operator belongs to one or more tenants; a read requires overlap.

* **Needs**: a `tenant_id` on the subject, on the operator assertion, and on every subject-scoped
  store. It is a **schema migration and a change to the signed assertion payload** — the widest
  change of the three, and the one that must happen *before* real data exists, not after.
* **Cost**: the highest up-front, the lowest per-endpoint. Once the column is there, the gate is
  one predicate applied uniformly, and it composes with A rather than competing with it.
* **Fits**: the actual commercial shape of a European banking product (a bank is a tenant), and
  it is what a prospect's security questionnaire asks about first.
* **Sharp edge**: it is a lie unless it reaches *every* store — the transcript, the memory, the
  replay bundles, the eval scores, the business events. A tenant boundary with one hole is not a
  tenant boundary.

### Option C — scope by *purpose* (declared, time-boxed access)

An operator declares why they are opening a subject; the grant is recorded, scoped and expires.
"Break-glass with a reason."

* **Needs**: no schema change to the subjects at all — a grant table and a step in the UI.
* **Cost**: friction on every read, and it moves the guarantee from *prevention* to *deterrence*.
  It is only as good as the review of the grants, which is a process, not a mechanism.
* **Fits**: the auditor and the support escalation, where any prior binding is by definition
  wrong — those roles exist precisely to look at things they were not previously assigned.
* **Sharp edge**: with the actor now in the ledger ([ADR 0024](0024-every-governed-act-names-its-author.md)), Tessera already has the *evidence* half of
  this for free. What is missing is the *ask*.

### The likely answer, offered but not taken

**B as the boundary, A inside it, C for the roles that must cross both** — tenant as the hard
wall, dossier as the day-to-day scope, purpose-declaration as the audited exception for the
auditor and the escalation path. That is three mechanisms, and it is a body of work, not a night.
It is written here so that whoever decides is choosing, not discovering.

## What this ADR does now

1. **States the posture out loud.** PII reads are gated by **role**, not by **purpose**. Today,
   every verified operator can read every subject. This is a *conscious, dated choice*, not an
   oversight — and it is recorded as such in the README and the remediation ledger, because a
   posture that is only true in the code is one nobody can hold us to.
2. **Pins it with a test.** `tests/unit/test_subject_read_posture.py` invokes a subject-scoped
   read as a `collections` operator against a subject that has nothing to do with recouvrement,
   and asserts **200**. The test's *purpose is to fail* the day this changes: narrowing the
   posture (good) must be a reviewed edit to this file and that one, not a silent tightening that
   breaks a console nobody was watching; widening it further is impossible (it is already
   maximal), which is itself the finding stated as an assertion.
3. **Refuses to implement.** See Status.

## Consequences

The gap is now **visible, dated, and cheap to find** — in the README, in the ledger, in an ADR,
and in a test that names it. It is not closed. Anyone reading the repository can see exactly what
Tessera does and does not promise about who may look at whom, which is the honest position for a
reference implementation whose front page says *the value is in the assembly, not the invention*.

The alternative — leaving `SUBJECT_READ_ROLES = OPERATOR_ROLES` undocumented because it is "only
a demo" — is how a demo posture becomes a production posture without anyone deciding.

## References

- [ADR 0024](0024-every-governed-act-names-its-author.md) — every governed act names its author. The trail now records *who read*; this ADR is about *who may*.
- `src/tessera/api/operator.py` — `SUBJECT_READ_ROLES`, `OPERATOR_ROLES`, `MUTATION_ROLES`
- `tests/unit/test_subject_reads_carry_auth.py` — the read ratchet (a stranger sees nothing)
- `tests/unit/test_subject_read_posture.py` — this posture, pinned
- GDPR Art. 5(1)(b) purpose limitation, Art. 5(1)(c) data minimisation, Art. 32 security of processing
