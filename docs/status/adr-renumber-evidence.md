# ADR renumbering — the reference map, and why the rename is not the hard part

Produced 2026-07-12 while attempting the A8 renumbering lot. **The renumbering was HALTED**
(see `day-cleanup-run.md`). This file is the part that survives: *which bare `ADR NNNN`
reference means which ADR, and by what proof.* Redoing the rename is an afternoon; redoing
this adjudication is the whole risk.

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

**2. `spine/runtime.py:27` is irreducibly ambiguous.**

```python
class SandboxDefaults:
    """Live defaults for the Console sandbox playground (ADR 0010 Phase C)."""
```

The *Console* is the cockpit (frontier's surface). *Phase C* is recouvrement's phase letter.
Two plausible readings, no proof either way — not from the file, not from the commit, not from
the dates. **This is the HALT.** One ambiguous reference in the decision registry is one too
many, and guessing it is precisely what the brief forbade.

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

## The safe plan

1. **Do 0015 → 0022 on its own.** File rename + 5 filename links. Zero bare references. Provably
   safe, and it shrinks the frozen set from three to two.
2. **Do 0008 → 0020 next.** 75 refs, and the date test (2026-05-31 vs 2026-06-22) resolves nearly
   all of them mechanically. Adjudicate the ~10 leftovers by commit.
3. **Do 0010 → 0021 last, and only with CI green.** 245+ refs, wrapped references, and at least
   one irreducibly ambiguous site that needs a human ruling on what `SandboxDefaults`'
   "Phase C" meant. Resolve `spine/runtime.py:27` *first* — ask whoever wrote it — then run the
   sweep.
4. **Verify semantically, not textually.** "Zero occurrences of the old filename" proves nothing.
   The property to assert is: *no reference to the moved sense still carries the old number* —
   which requires reading the sense, and cannot be done with a grep.
