# Audit-360 remediation run — opened 2026-07-12

Remediation ledger for the 2026-07-12 360° audit (`Tessera_private/audit-360-2026-07-12.md`,
1 P0 open + P1/P2 backlog; the earlier 2026-07-10 audit's remediation lives in
`overnight-security-run.md`). Base: `main` = `5cf51435`. Work happens on
`claude/fix-recouvrement-auth` (worktree `agents/claude`), twice-green gate before merge,
targeted staging, never `git add -A`.

---

## F-1 — P0 · recouvrement mutations without authentication, spoofable audit attribution

**Status: closed on the branch — HALT before merge (host gate owed, see witness note).**

The finding, in one sentence: `POST /recouvrement-assistant/{message,action}` were mounted
with no dependency at all (`main.py:351`) while their BFF routes proxied *anonymous*
visitors through with the service bearer attached, and the action route's `requested_by` —
the name the ledger records as having acted — was a **body field with a default**. Same
class as the 26 cockpit mutations closed 2026-07-11; these two POSTs sat outside the
hardened router. For a project whose product IS the audit trail, "anonymous writer, caller-
chosen attribution" was the one hole that unpriced everything else.

### What changed (four seams, one doctrine)

- **Role set** — `COLLECTIONS_MUTATION_ROLES = {collections, admin, superadmin}`
  (`operator.py`): the business-plane counterpart of `MUTATION_ROLES`, differing by exactly
  one role. `collections` acts (this console is its purpose; it keeps zero cockpit
  authority), the `auditor` enters the console and does not write from it — reads-don't-
  write holds on every plane.
- **Agent guard** — `require_collections_operator` (`security.py`): 401 with no verified
  assertion, 403 for a verified operator without write authority here. Declared **on the
  router** (`recouvrement_assistant.py`), not at the mount site — the `mutations.py` model:
  a route added to that module cannot forget it. The guard *returns* the verified
  `SessionContext`; the action route depends on the same callable (FastAPI caches it
  per-request) and stamps `requested_by = session.subject_id` — the ledger now records who
  **proved** they asked.
- **Contract** — `requested_by` is **gone** from `RecouvrementAssistantActionRequest` and
  from the front's client lib. With `extra="forbid"` a body that still asserts an identity
  is a 422: the spoof vector is a loud contract violation, not a silently dropped field.
- **BFF edge** — both `app/api/recouvrement-assistant/{message,action}/route.ts` now do
  `auth()` → 401 anonymous / 403 non-writers (`canActOnCollections`, the edge copy of the
  role set) → mint the signed assertion (`dedicated-ui`) carrying the session's principal →
  only then proxy with the service bearer. Friendly gate at the edge, real gate in the agent.

### The ratchet (the class, not the instance)

`tests/unit/test_mutation_routes_carry_auth.py` walks the **fully assembled app**
(`build_app()` — the finding lived at the mount site, so the unit-mounted router is not the
thing to test): every POST/PUT/PATCH/DELETE must carry a recognised auth dependency
(`require_operator` / `require_collections_operator` / `require_bearer`) or sit in the
frozen `SELF_AUTHENTICATING` set (`/chat`, `/agents/{id}/invoke`, `/session/login`,
`/session/logout` — each with its documented reason), asserted with `==` so it can neither
grow nor go stale silently. `UNGATED_EXCEPTIONS` — mutations with no auth story at all, the
set F-1 lived in — **is frozen at zero**. `test_recouvrement_assistant_auth_closed.py`
proves the instance: anonymous → 401 before the body is read (all four paths, aliases
included), auditor → 403, collections admitted, spoofed `requested_by` → 422, and the
workflow receives the assertion's principal, not the body's claim.

### Witness note (who verified what, honestly)

This session ran in a sandbox whose only Python is 3.10; the codebase is 3.12-only (PEP 695
`type` aliases, `StrEnum`) and every 3.12 acquisition path was network-blocked. So:

- **Ran here, green** — `ruff check .` + `ruff format --check .` at the lock's pinned
  0.7.4 (0 findings); full web gate on an isolated copy: `tsc --noEmit` EXIT 0,
  `biome check .` EXIT 0 (0 diagnostics on touched files), `vitest run` **210/210** —
  including the 10 new BFF guard tests (anonymous 401 / auditor 403 / assertion minted and
  decoded / 503 on unset key / error sanitization preserved).
- **Owed on the host before merge** — `make gate` **twice**, which adds `mypy` and
  `pytest -m "not integration"` (the two new test files run there). Same discipline as the
  2026-07-11 lane B: no independent witness ran tonight (CI still billing-blocked), so the
  two consecutive local passes are the only guard rail — do not merge on one.

### 2026-07-12 · host gate pass 1 — RED, cause understood, fixed on the branch

The first host `make gate` broke on two **pre-existing** tests that call the action
handler *directly*, outside FastAPI's injection
(`test_recouvrement_event_loop.py::test_action_route_does_not_pin_the_event_loop`,
`test_recouvrement_graph_v1.py::test_recouvrement_assistant_action_endpoint_returns_governed_action_contract`):
`TypeError: recouvrement_assistant_action() missing 1 required positional argument:
'session'`. Correct consequence of the fix — the handler now demands the verified
identity — wrong tests. Fixed (`69603f10^..`) by supplying the identity the way the
runtime does: a genuinely signed assertion pushed through `require_collections_operator`
(never a hand-assembled `SessionContext` literal, which would re-teach asserted-not-proven
identity). **The parameter kept NO default** — a default identity on that argument is F-1
reintroduced for test convenience, "Julie Dubois" one level up — and both files now pin
the seam: direct call without a session refuses (`TypeError` at bind), and
`inspect.signature` asserts the `session` parameter has no default. The governed-contract
test also gained the end-to-end attribution assert:
`artifact.content.last_action_requested_by == "aline.durand"`, the assertion's principal.

### 2026-07-12 · the attack, closed on a running server (not only in tests)

Proven against the branch booted on the canonical ports (`dev-status`: git `812e37e3` on
both), with the **same URLs and the same ports** that answered `200 OK` the day before on
`main` (`dev-status`: git `5cf51435`) — so the before/after reads directly:

| call | main (`5cf51435`) | branch (`812e37e3`) |
|---|---|---|
| `GET :8099/healthz` (positive control) | 200 | **200** |
| `POST :8099/recouvrement-assistant/action`, anonymous | **200** | **401** |
| `POST :3097/api/recouvrement-assistant/action`, anonymous, `requested_by: "Mallory"` | **200** | **401** |

The `healthz` 200 is what makes the two 401s mean *"the route refuses"* rather than
*"the server is down"*. The first attempt to prove this failed for reasons that had
nothing to do with the fix, and the reasons are worth recording: the servers under test
were the **reference checkout's** (main, pre-fix) — `dev-status` exists precisely to say
so and was the tool that caught it — and the subsequent worktree preview died on a
**metrics-port collision** (see the `chore(dev)` commit below), leaving an orphan frontend
that blocked the retry. Two lessons, both cheap: *always read `dev-status` before trusting
a curl*, and *a failing boot must refuse loudly, not bury an `OSError` in a log*.

### Owed follow-ups

- The e2e path (`recouvrement-product-experience`) still calls these routes as a logged-in
  collections operator — expected unaffected (the BFF mints for it), to be confirmed by the
  seeded e2e run when the CI witness returns.
- Front demo note: the assistant drawer is now honestly auth-gated — an anonymous visitor
  of the public demo can *see* the recouvrement page only if routed there, and its assistant
  actions now 401 at the edge instead of silently writing to the ledger.

---

## F-4 + F-5 + F-9 — P1 · PII reads, GDPR mutations, and published default credentials

**Status: closed on `claude/fix-pii-reads-and-default-accounts`, all four witnesses green.**
Base: `main` = `6b78055f` (carries F-1). Three commits: the agent identity model
(`29f1f71d`), the BFF edge (`494a2721`), the default accounts (`44f20795`).

One sentence each. **F-5**: `DELETE/PATCH/PUT /memory/*` and `PUT /settings/synthesis-admin`
sat behind `require_bearer` alone — provenance, not identity — and the *ratchet built to
close F-1 was certifying them as safe*. **F-4**: `GET /observability/conversation-messages`
returned any conversation's transcript to anyone, and `GET /observability/conversations`
published the ids next to the opening user message (`title`) — a directory, then a read.
**F-9**: `admin/tessera-admin` and its siblings, published in this repo, stayed valid in any
deployment missing three env vars — fail-OPEN, the bearer's old shape.

### The one that mattered: the guard-rail embodied the confusion

F-5's first gesture was to remove `require_bearer` from the mutation ratchet's
`KNOWN_AUTH_GUARDS`. The ratchet went red on exactly `/memory/*` and `/settings/*` — *that
red was F-5* — and it is green again by giving those routes an identity guard
(`require_operator`, `require_superadmin`), never by an exception. `UNGATED_EXCEPTIONS` stays
frozen at zero.

### The payload is the judge, and it found what review missed

The read ratchet (`test_subject_reads_carry_auth.py`) does not reason about which store a
handler touches — it seeds a canary into every store holding a person's words, sweeps every
GET as an anonymous caller, and fails if the canary comes back. It caught **three leaks the
audit and a dedicated payload survey had both filed as aggregates**: `/observability/handoffs`
and `/observability/context-overflow` (each echoes a turn's question as a row label) and
`/observability/agent-historique` (a synthetic dashboard with one real `live_conversations`
block). Mutation-tested: with the guard removed it goes red and names all eleven+three
leaking routes with the exact strings they emit.

### An empty state is not a refusal (the trap in the fix itself)

`historique/[sessionId]/page.tsx` returned `null` on failure and rendered "aucune
conversation"; the security dashboard rendered `?? 0`. Gating the endpoints without fixing
these callers would have told an anonymous visitor the transcript was *empty* and *0 memories
were expiring* — trading a leak for a lie. Both now distinguish "there is no data" from "you
may not see it" (`isAccessDenied`, three locales).

### Live proof — reference server (`02ad18dc`, "before") vs preview from this worktree (`44f20795`, "after")

`make dev-status` confirmed the HEAD under test on both sides before every curl. `/healthz`
200 throughout is what makes each 401 mean *"refuses"*, not *"server down"*.

| call | before (main-ish) | after (branch) |
|---|---|---|
| `GET /healthz` (positive control) | 200 | **200** |
| `GET :8099/observability/conversation-messages`, anon (agent direct) | **200** | **401** |
| `GET :3097/api/observability/conversation-messages`, anon (public BFF door) | **200** | **401** |
| `GET /observability/conversations`, anon (the enumerator — 7.4 kb of ids+titles) | **200** | **401** |
| `GET /observability/erasure-coverage`, anon (public aggregate, 3 ints) | 200 | **200** |
| `GET /observability/scores · snapshot · fleet · tail-sampling · memory`, anon | 200 | **200** |
| `GET /observability/{conversations,memory-inventory}`, **auditor** assertion | — | **200** |
| `GET /observability/conversations`, **collections** assertion (its console) | — | **200** |
| `DELETE /memory/{id}`, anon | 200/bearer | **401** |
| `DELETE /memory/{id}`, **auditor** (reads, does not write) | — | **403** |
| `PUT /settings/synthesis-admin`, **admin** (may not grant itself) | — | **403** |
| `PUT /settings/synthesis-admin`, **superadmin** (the one role that may) | — | **200** |
| `GET /session/transcript`, id only (leaked) | — | **403** |
| `GET /session/transcript`, valid token for *another* conversation, swapped | — | **403** |
| `GET /session/transcript`, matching signed capability | — | **200** |

Non-regression, in one line: the public aggregate cockpit is untouched (200), the auditor and
collections still read their surfaces (200), and the customer still resumes their own chat
(200) — while every anonymous PII read and every under-gated GDPR mutation now refuses.

F-9 is a boot-time module decision, proven by the 13 vitest cases exercising the real
`accounts.ts` (no logic mocked): defaults refused under staging/production/`NODE_ENV=production`,
kept under unset/local/ci, an explicit password accepted, the refusal named in the log.

### Witnesses

- **gate ×2**, real exit codes `0` and `0` (1811 pytest + 251 vitest + mypy strict + ruff +
  tsc + biome). Not echo-piped — `$?` captured directly.
- **live refusal** proven on servers booted from *this* worktree (`dev-status`: `44f20795`),
  same URLs/ports that answered 200 the moment before on the reference checkout.
- **positive control** (`/healthz` 200) on every probe.
- **non-regression**: aggregates public, auditor/collections read, superadmin writes, customer
  resumes — all 200.

### Known-open / owed

- **CI witness still absent** (billing-blocked): the two consecutive local gates are the only
  guard rail, same posture as every merge since 2026-07-10.
- **The seeded e2e run** for the resume flow and the gated cockpit pages is owed when CI
  returns; the vitest layer covers the units, not the browser round-trip.
- ~~**`main` advanced to `02ad18dc`**~~ — **resolved**: the branch was rebased onto it
  (`30cab63a`) and the gate re-run on the rebased tree. A rebase is not a merge: the gate that
  ran before it does not vouch for the tree after it.
- **Systemic class, logged not fixed here** (operator ruling): three defects this week share
  one shape — `extra="ignore"` swallowing a wrong Ollama field, a wrong `response_model`
  stripping fields, `audit_sink=stdout` cutting the chain — *silent union where a loud failure
  belonged*. Owed as a debt sweep (`extra="forbid"` on settings), not this lane.

---

## The guard-rail was blind to its own class (2026-07-12, later)

F-5 above was closed **by hand**: `require_bearer` was removed from `KNOWN_AUTH_GUARDS`, one
name deleted from a frozenset. That closes the instance and leaves the class wide open —
nothing in the repository asserted the list, so the next author could put a provenance
dependency back into it and pass review. The ratchet built to forbid the anonymous writer had
been *certifying* the GDPR mutations, because each of them carried a "recognised guard".

A list can be wrong. So the list stops being a claim and becomes a test.

### The invariant, in one line

> **A guard is what refuses a stranger. A bearer says where a call comes from, never who makes it.**

Every member of `IDENTITY_GUARDS` — the write plane's guards **and** the read plane's
`require_subject_reader` — is now *called* with the request a stranger actually sends, and
must raise 401. The doctrine is a property of a guard, not of the write plane: a read guard
that degraded to provenance would hand a transcript to the same stranger.

**The request is the whole subtlety, and getting it wrong would make this a rubber stamp.**
"Anonymous" does not mean "carries nothing": the BFF attaches the service bearer *on the
caller's behalf*, so a stranger reaches the agent holding a perfectly valid one. A test that
sent *no* bearer would let `require_bearer` answer 401 and **look like a guard** — proving
only that the stranger had not pasted a secret nobody asked them for. So the stranger presents
the **correct** bearer and no identity. Whatever refuses that is a guard; whatever admits it
is provenance, whatever its name.

Asserted in **both postures**, because the no-op is invisible in exactly one of them: with no
token configured — the posture every `make gate` and every CI run uses — `require_bearer`
returns `None` without looking at anything, so a guard that degraded to a no-op there would be
certified green *by the very suite meant to catch it*.

### Mutation-tested, under sha control

A ratchet nobody has seen red is not a ratchet. `require_bearer` put back into
`KNOWN_AUTH_GUARDS`, nothing else touched:

| step | `test_mutation_routes_carry_auth.py` (sha256, 12) | pytest | real exit |
|---|---|---|---|
| baseline, as committed | `78af61da2835` | 12 passed | **0** |
| `require_bearer` back in the set | `04ae4e4a44f8` | **2 failed**, 12 passed | **1** |
| restored | `78af61da2835` | 12 passed | **0** |

The red names the doctrine rather than a line number, on **both** postures:

```
FAILED …::test_every_known_guard_refuses_a_stranger_who_carries_a_valid_bearer[require_bearer]
FAILED …::test_every_known_guard_refuses_a_stranger_in_the_ci_posture_too[require_bearer]
E   Failed: DID NOT RAISE <class 'fastapi.exceptions.HTTPException'>
        guard = <function require_bearer …>
```

### Two traps that each manufactured a false reading first

Both are recorded because the table above is only worth what the method behind it is worth.

1. **`${PIPESTATUS[0]}` is empty in zsh.** The array is `$pipestatus`, and it is 1-indexed.
   Every "real exit code" in the first pass was the empty string, printed next to a `tail`ed
   pytest summary — the exact false-green this repository has manufactured before. Every exit
   code in the table is `$?`, captured with **no pipe in between**.
2. **A test result is only evidence if you can name the bytes it ran against.** The first
   mutation run read `4 passed` at baseline *and* `4 passed` under mutation — a rubber-stamp
   verdict — because a concurrent process had moved `HEAD` under the worktree mid-run. The file
   being tested was not the file that had been committed. Hence the sha column: it is not
   decoration, it is what makes the row a fact. (`dev-status` before every curl is the same
   discipline, one level up; this is its unit-test-level twin.)
