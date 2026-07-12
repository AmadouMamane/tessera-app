# ADR renumbering — the reference map, and why the rename is not the hard part

> **Status (2026-07-12).** `0008 → 0020` and `0015 → 0022` are **DONE and merged**. `0010 → 0021`
> is the **only collision left, and it is held for CI** — it is the first live item waiting on
> CI's return. Everything below is the adjudication that made the first two safe and that the
> third will need. The rename is an afternoon; this map is the whole risk.
>
> Also done, and deliberately kept separate: `spine/runtime.py`'s `SandboxDefaults` cited
> *"ADR 0010 Phase C"* — a **false** reference (Phase C names recouvrement's *business* console,
> where ADR 0013 forbids exactly that payload). Corrected to cite what actually governs the
> cockpit Console — ADR 0019 §2 (I2) plus the security seam's `sandbox_overrides_allowed`. That
> was a lie being fixed, not a number being moved, so it landed in its own commit.

## The mapping (operator's call, 2026-07-12)

The direction was settled after measuring, and it **inverts the brief** for 0010: the sense
that is referenced most keeps its number, because every rewrite is a chance to make the
decision record lie.

| # | Keeps the number | Moves | Bare refs to rewrite |
|---|---|---|---|
| 0008 | `0008-agent-audience-and-surface` | `0008-security-hardening` → **0020** | ~24 |
| 0010 | `0010-frontier-observability` | `0010-recouvrement-internal-operator-agent` → **0021** | ~52 |
| 0015 | `0015-runtime-telemetry-spine-and-scope` | `0015-hica-seal-design-note` → **0022** | **0** |

0020 / 0021 / 0022 are free (the tree stops at 0019).

## The reference counts nobody had

The index says "ADR 0010 is referenced 138 times, ADR 0008 55 times". The real numbers, counted
over every tracked source and doc:

| # | bare `ADR NNNN` refs | files |
|---|---|---|
| 0008 | 75 | 46 |
| 0010 | **245** | 209 |
| 0015 | 155 | 88 |

And even *those* undercount — see trap 3.

## The discriminators that DO work (structural, not vibes)

**ADR 0010 — the strongest of the three.** The two ADRs number their rollouts differently, and
neither ever uses the other's scheme:

* `0010-frontier-observability` → **`Phase 1..6`** (digits), and cites features by canonical
  idea IDs from `docs/observability-ideas.md`, which opens *"Companion to ADR 0010 —
  Frontier-grade observability … The numbers are canonical IDs … Do not renumber."* So
  `ADR 0010, idea #81`, `ADR 0010 #3`, `ADR 0010 Phase 4` are **all frontier**.
* `0010-recouvrement-internal-operator-agent` → **`Phase A/B/C`** (letters), and has no ideas.
  So `ADR 0010 Phase B/C` is **recouvrement** — which is what `api/operator.py` means.

**ADR 0008.** `0008-security-hardening` owns `deployment_mode` (`cloud_run`/`on_prem`), the
control × deployment-mode matrix, HSTS/CSP/CORS, rate limits, body caps, the edge gateway,
supply-chain. `0008-agent-audience-and-surface` owns `audience`/`surface`/`auth`, `AuthState`,
the widget/cockpit surfaces. Note: the word **"demo" appears 3× in agent-audience-and-surface
and 0× in security-hardening** — which settles `production-posture.md`'s
`ADR 0008 "login-less public demo"`.

**Creation dates settle the rest.** A reference written before the second ADR existed can only
mean the first:

| ADR | created |
|---|---|
| `0008-security-hardening` | 2026-05-31 |
| `0010-frontier-observability` | 2026-06-08 |
| `0008-agent-audience-and-surface` | **2026-06-22** |
| `0010-recouvrement-internal-operator-agent` | **2026-06-22** |
| `0015-runtime-telemetry-spine-and-scope` | 2026-07-01 |
| `0015-hica-seal-design-note` | 2026-07-08 |

`git blame` each ambiguous line; anything before 2026-06-22 is unambiguous. And when the dates
collide, **read the commit**: `session.py:88`'s `(ADR 0008/0009)` was written by `e12a697d`,
whose diff *also edits* `0008-agent-audience-and-surface.md` — so that is the ADR it means.
`webapp/.../session.ts` and `api/session/route.ts` come from `6350cf7f`, the commit that
**created** that ADR (212 lines). All three stay at 0008.

## The four traps — each one drew blood

**1. The seal is DECIDED in 0015 and only DESIGNED in the annex.** This is the one that produced
a real lie. `guard/seal.py`, `guard/audit.py`, `settings.py`, `api/routes/audit.py` all say
`ADR 0015 §Amendment 3` / `§Correction 3c` — those are **sections of the spine ADR**, which is
where the seal was decided. The design note (`0015-hica-seal-design-note`) *implements* that
decision and itself opens *"the seal that **ADR 0015 §Correction 3c** raised"*.

So a bare `ADR 0015` next to the word "seal" means **the spine**, not the annex — the exact
opposite of the naive reading. An automated pass that trusted proximity rewrote
`production-posture.md`'s heading **"## 4. The audit ledger (ADR 0015)" → "(ADR 0022)"**,
re-pointing the audit ledger at a design note. That is a decision record asserting something
false, which the repo's own doctrine calls a defect where a duplicate number is only an
annoyance.

**Consequence, and it is good news:** the seal annex is referenced **only by filename**. Zero
bare references mean it. Renumbering 0015 → 0022 is a file rename plus 5 filename links, and
**nothing else must be touched**.

**2. `spine/runtime.py:27` was not ambiguous — it was FALSE. (Resolved.)**

```python
class SandboxDefaults:
    """Live defaults for the Console sandbox playground (ADR 0010 Phase C)."""
```

It read as ambiguous — the *Console* is the cockpit (frontier), *Phase C* is recouvrement's phase
letter — and it halted the first attempt. The resolution is better than a coin-flip: **`Phase C`
names recouvrement's BUSINESS console (`dedicated-ui`), and ADR 0013 forbids exactly this payload
(a system prompt, a guard-rule count) on a business surface.** The citation pointed at the one
decision record that rules its own behaviour *out*. It was not a stale number; it was a **false
reference**.

Corrected to cite what actually governs the cockpit Console — **ADR 0019 §2 (increment I2**, the
Console as a generated surface) — plus the security seam's `sandbox_overrides_allowed`
(overrides honoured only for `COCKPIT_EMBEDDED` + `OPERATOR`). Landed in **its own commit**: a lie
being fixed must not look like collateral of a rename.

**The lesson generalises.** When a reference resists every discriminator, consider that it may be
*wrong* rather than *ambiguous*. A renumbering sweep is an unusually good detector of false
citations, because it forces someone to read what each one actually claims.

**3. References wrap across lines, so every count is an undercount.** Three references are split
by a line break — `api/operator.py:77` and `lib/auth/roles.ts:70` both end a line with `ADR` and
begin the next with `0010 Phase C`. No grep, no line-based rewriter and no `# noqa`-style census
sees them. Any verification that greps line by line will report "0 remaining" while the record
still lies. (Same family as the ruff S608 blind spot found in lot 1 — a syntactic check with a
shape it cannot see.)

**4. The ADR bodies cross-reference each other.** `0009-dashboard-auth-rbac` and
`0013-entry-routing-by-audience` both cite `ADR 0010 Phase B/C` (recouvrement) in their own
text. A rename pass that skips `docs/decisions/` — the natural instinct, since those files are
"the thing being renamed" — leaves the decision record contradicting itself.

## What was done, and what is left

**DONE — `0015 → 0022`.** File rename + filename links. **Zero** bare references meant the annex,
for the reason in trap 1. Nothing in `guard/seal.py`, `guard/audit.py` or `settings.py` was
touched, and that is correct.

**DONE — `0008 → 0020`.** 25 bare references rewritten. The date test carried 23 of them
(everything written before 2026-06-22 could only mean security-hardening); the remaining two —
`production-posture.md`'s HSTS/TLS line and its "Rate limiting" heading — were adjudicated by
subject. The ~46 references meaning audience/surface were left untouched, and a **bidirectional**
check confirmed it: no `ADR 0008` remains in a security context, and no `ADR 0020` appeared in an
audience context.

A fourth reference *form* surfaced here and is worth knowing: ADR front-matter uses a **bare
number with a gloss** — `- Related: 0006 (locale-prefixed routing), 0008 (security hardening)`.
No `ADR` prefix, so a `ADR\s*0008` sweep misses it entirely. The gloss makes each one
self-disambiguating (`0008 (security hardening)` moves; `0008 (audience/surface/auth)` stays), but
only if you look for the form at all.

**LEFT — `0010 → 0021`, held for CI.** 245+ references; 183 mean frontier (which keeps 0010), 52
mean recouvrement. The discriminator above is strong, but **some references wrap across lines**
(trap 3), so no grep-based verification of this rename can be complete — it will report "0
remaining" while the record still lies. And a first automated attempt produced exactly the class
of error being guarded against.

**Verify semantically, not textually.** "Zero occurrences of the old filename" proves nothing. The
property to assert is *bidirectional*: **no reference to the moved sense still carries the old
number, AND no reference to the kept sense acquired the new one.** Both directions need the sense
read. A grep cannot do it.
