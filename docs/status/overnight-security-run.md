# Overnight security-remediation run — 2026-07-11

Remediation of the 2026-07-10 code audit (`Tessera_private/artifacts/tessera-audit-2026-07-10.html`,
6 P0 + ~60 findings; structure in `audit-code-2026-07-10.md`). Base: `origin/main` = `60ec9d99`.

Two lanes, decided before the run:

- **Lane A — safe corrections.** Either no behaviour change, or a bug with a single
  unambiguous fix. ONE `make gate` pass per lot, autonomous merge to `main`.
- **Lane B — the security seam.** The four P0s that change who is allowed to do what.
  Branch `claude/security-seam`, **twice-green local**, then **HALT — no merge**.

**Protocol note — the safety net was gone.** GitHub Actions is billing/quota-blocked, so
"CI is the second pass" did not hold. There was no independent witness all night. Lane A
therefore took one full local gate per lot; lane B took two consecutive full local passes,
which is the only guard rail it has.

---

## MORNING SUMMARY

### Landed on `main` (lane A) — 9 lots, all gate-green

| Lot | What | Hash |
|---|---|---|
| A0 | **`main` was red at the gate** — repaired before anything else | `a56bb287` |
| A1 | **P0** — dunning letters asserted a payment promise the file never recorded | `749bf9cb` |
| — | journal opened | `baa336e4` |
| A2 | **P0** — compliance dashboard served fixtures as real data | `b38ab7c5` |
| A3 | **P1** — reliability KPI counted policy denials as outages (error rate 3× too high) | `6709f99e` |
| A4 | **P1** — a Recouvrement turn pinned the FastAPI event loop | `a4040717` |
| A5 | **P1** — the GDPR retention purge was never scheduled | `4930fb83` |
| A6 | **P1/P2** — turn deadline · no raw exception on the wire · money in cents | `9e46fed5` |
| A7 | **P1** — split the 3 219-line observability god-router (152 routes, 11 modules) | `9caea197` |
| A8 | **P1** — ADR hygiene: logs out of `docs/decisions/`, index, collision ratchet | *this commit* |

### Waiting for review (lane B) — `claude/security-seam` @ `e4286be6`, NOT merged

Twice-green locally. **The four P0s of the security seam are closed on that branch**, each with
a test that fails against the pre-fix tree:

| | Finding | Closure |
|---|---|---|
| **B1** | `guard-bypass` — any anonymous caller could disable the whole guard via the `/chat` body | overrides honoured only for `COCKPIT_EMBEDDED` + `OPERATOR`, both server-derived |
| **B2** | `broken-access-control` — 26 operator mutations reachable anonymously | mutations router declares `Depends(require_operator)`; BFF gates + mints the assertion |
| **B3** | `auth-fail-open` — an unset bearer made the auth stack a no-op | fail-closed boot check in production |
| **B4** | `terraform-exposure` + `secret-default` — Cloud Run open to `allUsers`, `REPLACE_ME` secrets | invokers `[]`, internal ingress, generated secrets, DB TLS, locked audit retention |

**Two things found while closing them that the audit did not list — both material:**

1. **B1 was not fully closed by the audit's own fix.** `chat.py:882` computed `pii_guard_off`
   from `request.guard_overrides` — the **raw request body** — so it sat *below* the
   surface/auth gate. An anonymous caller sending `guard_overrides=["pii"]` would still have
   had the streaming PII redactor switched off and received an **unredacted PAN on the wire**,
   which is precisely the harm the P0 describes. Every other consumer reads the gated state;
   this was the last direct read of the body. A ratchet test now forbids the pattern.

2. **`require_bearer` alone could never have closed B2.** The bearer authenticates the
   *frontend service*, and the BFF attaches it **on the caller's behalf** — so an anonymous
   visitor's mutation arrives at the agent carrying a perfectly valid bearer. The bearer
   answers *"did this come from our frontend?"*, never *"who is asking?"*. Only the HMAC-signed
   operator assertion answers the second question. A fix that mounted the mutations behind
   `require_bearer` would have looked right and changed nothing.

### What needs Amadou

1. **Restore GitHub Actions billing.** This is now the single highest-leverage repo action.
   `main` was **red at the gate** when this run opened (lot A0) — a lint error that landed
   during the previous billing-blocked night, with no independent witness to catch it. That is
   two consecutive nights in which the absent CI has cost something real.
2. **Review and give the go on `claude/security-seam`.** Nothing from lane B reached `main`.
   See "Lane B — for review" below for the specific decisions I want a human on.
3. **`is_locked = true` on the audit bucket is IRREVERSIBLE** once applied. It is what makes
   the trail opposable, and it is a one-way door. Deliberate human call.

### Parked, deliberately, with reasons

Each of these was *examined* and then *declined* — not skipped. They fail lane A's own rule
("no behaviour change, or a single unambiguous fix"), and forcing them tonight, with no CI, was
the worse bet.

- **Paginating the audit read in SQL** (`dos-memory`). `read_ledger_entries` is the single read
  seam for 10+ callers, some of which legitimately need the whole chain (`verify` walks
  genesis→tail); the route applies **nine** filters plus free-text in Python; and the ledger has
  **two storage mediums** (file and postgres), only one of which has a SQL `LIMIT`. Silently
  capping the rows would be a navigation lie on the audit surface — the product's opposable
  memory. Needs a design, not a patch.
- **A `statement_timeout` on the main Postgres pool.** The declared
  `postgres.statement_timeout_ms` is applied only by the spine adapter, via its own constant.
  Setting it pool-wide would also bound schema creation and pgvector index builds, which
  legitimately exceed it.
- **Renumbering the colliding ADRs** (see A8). "ADR 0010" is referenced **138 times** and means
  *frontier-observability* in some places and *recouvrement* in others; "ADR 0008" 55 times,
  equally ambiguously. Renumbering means reassigning every reference by judgment, and one wrong
  call makes the decision record assert something false. A duplicate number is an annoyance; a
  decision record that lies is a defect. Frozen by a ratchet instead — the set can shrink, never
  grow — with the full plan in `docs/decisions/README.md`.

---

## Lane B — for review (the decisions I want a human on)

1. **I did not remove `observability` from `ALWAYS_PUBLIC` literally.** The brief said to; taken
   literally it also kills the 126 public **GET** reads (the `allowed` check only admits
   `audit`/`budget`), which would 404 the entire cockpit. The brief's own words — *"lectures
   publiques séparées"* — say the reads stay public. So I gated the **mutation plane** on both
   sides and left the read plane alone. **If the intent was to lock the reads too, say so and it
   is a small change.**
2. **`staging` still boots without a bearer.** `is_production()` is true only for `production`.
   Staging is often internet-reachable. Extending the fail-closed check to staging is one line —
   a policy call, not a technical one.
3. **An `auditor` can currently reach the mutations.** The backend gates on
   `AuthState.OPERATOR`, and `SessionContext` carries no role, so it cannot distinguish
   *admin* from *auditor*. Least privilege says an auditor reads and does not promote agents to
   production. Threading the role through `SessionContext` is the fix, and it is a design change
   beyond tonight's mandate.
4. **The Terraform is NOT machine-verified.** `terraform` is not installed here and the gate does
   not run `terraform validate`. The `.tf` tests are a **text-level ratchet** (the open defaults
   cannot come back silently) — they are *not* a proof the configuration is correct. Someone
   must run `terraform validate` / `plan` before this is trusted.

---

## Lot log

### A0 — `main` was red at the gate (`a56bb287`)

Not in the brief. Found running the first lot's gate: `ruff check .` — exactly what `make gate`
runs — failed on `origin/main` at `scripts/ledger_restore_drill.py:108` (E501, a comment).
Comment-only reflow. Landed **first and alone**, because every subsequent lot would otherwise
have inherited a red gate and any "green" claim about them would have been false.

### A1 — the fabricated promise date (`749bf9cb`)

**P0 `fabricated-regulated-output`**, `message_templates.py:56, :76, :95`. Three *approved*
dunning templates hardcoded *"Votre promesse de paiement du 12 juin n'a pas pu être tenue"*.
Only `{days_late}` was a field. Every letter asserted a specific broken payment promise **never
read from the case file** — a fabricated financial claim in a regulated artifact. The witness,
rendering the pre-fix template against a case that records no promise at all:

```
Bonjour Mme R.,
… Votre promesse de paiement du 12 juin n'a pas pu être tenue et le dossier
présente un retard de 17 jours.
```

Mme R. never promised anything. Fixed by sourcing the date from the dossier and **omitting the
clause** when there is none — never defaulting. `missed_promise: str` (free prose, which is *how*
the template drifted from the data) became `missed_promise_date: date | None`, the single source
of truth; the label derives from it, so no surface can assert a promise the file does not carry.
RC-2048 renders identically (non-regression).

### A2 — fixtures served as real (`b38ab7c5`)

**P0 `fixture-as-real`**. `compliance_tabs.py` calls *itself* "fixed, deterministic fixture
data" for seven governance catalogues, yet `compliance` was not in the signal registry at all
and the dashboard never imported `<SyntheticNotice/>` — while `incidents-overview` renders it
five times. The right pattern existed and was not applied to the most regulatorily sensitive
surface in the product.

**I did not apply the audit's shorthand fix.** It proposed `compliance: cap(ORG, {synthetic:
true})`, which would have stamped "deterministic fixture" on the *derived posture* —
`compliance.py` genuinely computes every control status from a real runtime signal (AI-Act
obligations, conformance, citation validity, PII screening, refusal calibration, GDPR erasure,
firewall efficacy) against a threshold. **Calling real data fake is the same class of dishonesty
as the reverse.** Split instead, following the codebase's own precedent (`policies` real /
`policy_versioning` synthetic): `compliance` REAL, `compliance_catalog` SYNTHETIC. Tested in
both directions.

### A3 — the reliability KPI (`6709f99e`)

**P1 `wrong-metric-shown-real`**, a number on the headline dashboard. Availability read
`(allowed − errored) / total`, but the buckets are mutually exclusive, so it subtracted the
errored bucket from a bucket that never contained it. Measured:

| allowed | denied | errored | displayed error rate | true |
|---|---|---|---|---|
| 90 | 5 | 5 | **15.0 %** | 5.0 % |
| 90 | 10 | 0 | **10.0 %** | 0.0 % |
| 1 | 0 | 9 | **180.0 %** | 90.0 % |

Three defects, not one: the 3× overstatement the audit measured; a non-zero error rate when
**nothing errored at all** (a policy DENY is the guard working as designed, not an outage); and
a rate **above 100 %** rendered on an operator dashboard. The old test asserted
`error_rate == 1 − availability` — true *by construction*, since `error_rate` is *defined* as
`1 − availability`. It was structurally incapable of catching this.

### A4 — the blocked event loop (`a4040717`)

**P1 `async-blocking`**. A sync `.invoke()` (store I/O, ~30 business events per turn) called
straight from an `async` route. Closure test measures the symptom, not the implementation: a
ticker task runs concurrently and we count how far it gets while the route awaits. Against the
pre-fix route it gets **exactly 0 ticks** — the loop is pinned for the whole turn, starving every
other in-flight request including open SSE streams. Both handlers now offload; the audit named
only one, the other blocked identically.

### A5 — GDPR retention (`4930fb83`)

**P1 `gdpr-retention`**. `purge_expired` had **no caller**. The TTL filtered at *read* time while
the rows lived on in Postgres indefinitely — retention enforced in the view, not in the store,
which is not retention at all under Art. 5(1)(e). Now scheduled off-chrono (purge-then-sleep, so
data that expired while the service was down does not linger a further cadence), following the
seal/canary scheduler family exactly. `purge_posture()` is the single source of the decision, so
the boot log line and the scheduler cannot disagree. Second half: `erase_subject` (Art. 17) was
covered **only** in the integration tier — excluded from the gate, skipped when Postgres is down
— so a regression dropping one layer would have shipped green. Now pinned in the gate: erasure
reaches all four layers, and is audited. A partial erasure is a failed erasure.

### A6 — robustness (`9e46fed5`)

Three fixes; the audit's picture was sharper than stated once read against the code. `local.py`
**does** bound Ollama (audit overstated); `frontier.py` read `timeout_seconds` into
`self._timeout` at init and then **never used it** — a deadline the settings advertised but that
did not exist; `api.request_timeout_seconds` was likewise declared and applied to nothing. Now:
one deadline over the whole graph phase, and Vertex honours its declared timeout — bounding the
**gap between chunks**, not the total answer, so a long legitimate response streams freely while
a stalled backend raises. Plus: `turn.error` no longer returns `str(exc)` to the caller, and
regulated money is compared in integer cents (with a second, unlisted instance found next door:
the amount set was built from `str(amount_due)`, so the same amount arriving once as `int` and
once as `float` — `"840"` vs `"840.0"` — became two entries and scored the artifact
`amount_fields_conflict`).

### A7 — the god-router split (`9caea197`)

**P1 `god-router`**, named by the audit as the **root cause** of the authorization drift: one
flat 152-route module where public reads, PII reads and 26 privileged mutations interleave, with
nowhere to attach a single `dependencies=`.

3 219 lines → 11 modules (largest 529). **Route table byte-identical**: 152 paths, methods and
handler names, asserted against a snapshot taken before the first edit; the live app still
mounts every path. The 26 POSTs — exactly the audit's "26 anonymous mutations" — now live in
ONE module behind ONE router, which is the seam B2 hangs on.

Worth noting: **the surface split alone would not have given that seam.** A per-surface module
still mixes public GETs with operator POSTs, so it cannot declare a single `dependencies=`.
Splitting by *auth concern* is what closes the P0.

Three traps a naive mechanical split walks straight into, all caught:
- **six module-level caches are mutated via `global`** — moving one away from its handler
  silently breaks caching, because `global` binds to the *defining* module;
- **three `Path(__file__).resolve().parents[4]`** paths (calibration file, eval failures, i18n
  messages) — the package is one directory deeper, so `parents[4]` now resolves to `src/` rather
  than the repo root. Every one would have broken at runtime, silently;
- **the 20 Pydantic request models must be importable at RUNTIME** (FastAPI resolves body
  annotations via `get_type_hints`). Centralising them tripped ruff's `TCH001`, whose "fix" —
  moving them under `TYPE_CHECKING` — would have broken route registration.

Also: the boundary ratchet was keyed on the **exact path** of the old file, so after the split it
would have policed nothing while still reading green. It now rglobs the package.

### A8 — ADR hygiene (this commit)

**P1 `adr-hygiene`**. Half of the collisions were not ADR collisions at all: execution logs, an
incident report and overnight journals were squatting real ADR numbers. They are not decisions.
Moved to `docs/status/` and `docs/incidents/`, which dissolves the 0015/0017/0019 collisions with
**no renumbering**. Added `docs/decisions/README.md` (index + an honest statement of what is
still broken) and a ratchet that fails on any NEW duplicate prefix — and, symmetrically, fails if
a frozen collision is fixed but left in the exception list, because a stale exception list is how
a ratchet quietly stops ratcheting.

The renumbering itself is **parked with a plan**, for the reason given above: 138 + 55 ambiguous
references, and a decision record that lies is worse than one with a duplicate number.
