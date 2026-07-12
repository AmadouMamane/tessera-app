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

- F-5 (memory/GDPR mutations behind `require_bearer` only) is the *next* window; the
  ratchet deliberately recognises `require_bearer` as an auth floor so that finding stays
  a "weaker guard" finding, not an "absent guard" one.
- The e2e path (`recouvrement-product-experience`) still calls these routes as a logged-in
  collections operator — expected unaffected (the BFF mints for it), to be confirmed by the
  seeded e2e run when the CI witness returns.
- Front demo note: the assistant drawer is now honestly auth-gated — an anonymous visitor
  of the public demo can *see* the recouvrement page only if routed there, and its assistant
  actions now 401 at the edge instead of silently writing to the ledger.
