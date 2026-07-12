# Architecture decision records

The binding decisions. Read the relevant one before making an architecture-shaping change
(see `0001-record-architecture-decisions.md` for why and how).

**This directory holds decisions and nothing else.** Execution logs, incident reports and
overnight-run journals used to live here, squatting real ADR numbers — three of the six
number collisions the 2026-07-10 audit found were not ADR collisions at all, just logs
wearing an ADR's number. They now live in `docs/status/` and `docs/incidents/`.

| # | Decision |
|---|---|
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md) |
| 0002 | [Apache-2.0 license](0002-license-apache-2.md) |
| 0003 | [CI on GitHub Actions](0003-ci-github-actions.md) |
| 0004 | [`src/` package layout](0004-package-layout-src.md) |
| 0005 | [Tools vs workers separation](0005-tools-vs-workers-separation.md) |
| 0006 | [Locale-prefixed routing](0006-locale-prefixed-routing.md) |
| 0007 | [Agent memory architecture](0007-agent-memory-architecture.md) |
| 0008 | [Agent audience and surface](0008-agent-audience-and-surface.md) |
| 0009 | [Dashboard auth & RBAC](0009-dashboard-auth-rbac.md) |
| 0010 ⚠️ | [Frontier observability](0010-frontier-observability.md) — *keeps the number: 183 references* |
| 0010 ⚠️ | [Recouvrement internal operator agent](0010-recouvrement-internal-operator-agent.md) — *will become 0021; held for CI, see below* |
| 0011 | [Temporal as-of-T dimension](0011-temporal-as-of-t-dimension.md) |
| 0012 | [Agent registry and seed](0012-agent-registry-and-seed.md) |
| 0013 | [Entry routing by audience](0013-entry-routing-by-audience.md) |
| 0014 | [Environment isolation](0014-environment-isolation.md) |
| 0015 | [Runtime telemetry spine and scope](0015-runtime-telemetry-spine-and-scope.md) |
| 0016 | [Business-events fan-out contract](0016-business-events-fanout-contract.md) |
| 0017 | [Agent observability contract](0017-agent-observability-contract.md) |
| 0018 | [Assistant runtime turn contract](0018-assistant-runtime-turn-contract.md) |
| 0019 | [Invocation binding](0019-invocation-binding.md) |
| 0020 | [Production security hardening](0020-security-hardening.md) — *was a second 0008* |
| 0021 | [The eval gate grades measured contribution; the absolute domain bars are removed](0021-eval-gate-on-measured-contribution.md) |
| 0022 | [Hica external opposability seal — design note](0022-hica-seal-design-note.md) — *annex to 0015; was a second 0015* |
| 0023 | [The audit chain is independent of the audit sink](0023-audit-chain-independent-of-sink.md) — *audit F-6; annex to 0015* |
| 0024 | [Every governed act names its author; every configuration that cannot hold a guarantee refuses to boot](0024-every-governed-act-names-its-author.md) — *audit F-1/F-5/F-6/F-B, one doctrine; generalises 0023* |

*(0021 is reserved for `recouvrement-internal-operator-agent` — see below.)*

## Renumbering — two collisions dissolved, one held for CI (2026-07-12)

The rule, decided after counting rather than assumed: **the sense that is referenced most keeps
its number.** Every rewritten reference is a chance to make the decision record assert something
false, so the *smaller* side moves. A duplicate number is an annoyance; a decision record that
lies is a defect.

### Done

**`0008-security-hardening` → `0020`.** Settled by dates, which is proof rather than heuristic:
security-hardening was created **2026-05-31**, `agent-audience-and-surface` **2026-06-22**, so
every reference written before that cutoff *could only ever have meant* security-hardening. 25
bare references rewritten; the ~46 that mean audience/surface were left untouched. The handful of
post-cutoff references were adjudicated by reading the **origin commit** — `session.py`'s
`(ADR 0008/0009)`, for instance, was written by the commit that *created* the audience ADR, so it
stays at 0008.

**`0015-hica-seal-design-note` → `0022`.** Free: the annex was referenced **only by filename**.
Zero bare `ADR 0015` references meant it — because the seal was **decided** in the spine ADR
(§Amendment 3 / §Correction 3c) and only **designed** in the annex. `guard/seal.py`,
`guard/audit.py` and `settings.py` all say "ADR 0015 §…" and are correct *exactly as they are*;
they were not touched. Reading them as annex references is the trap, not the fix.

### Held — `0010`, and this is not laziness

`recouvrement-internal-operator-agent` → `0021` **waits for CI.**

* **245+ references.** 183 mean *frontier-observability* (which therefore keeps 0010); 52 mean
  *recouvrement*. The discriminator is strong — frontier numbers its rollout `Phase 1..6` and its
  features by canonical idea IDs (`docs/observability-ideas.md`), recouvrement uses `Phase A/B/C`
  and has no ideas — but *strong* is not *verified*.
* **Some references wrap across lines** — `ADR` ends one line, `0010 Phase C` begins the next. No
  grep sees them, so **no grep-based verification of this rename can be complete**: it will report
  "0 remaining" while the record still lies.
* A first automated attempt **produced exactly that lie**, re-pointing *"## 4. The audit ledger
  (ADR 0015)"* at the seal annex on nothing but word proximity.

Rewriting the project's memory *semantically*, at that scale, with **no independent witness**, is
precisely what a bounded tolerance of an absent CI must forbid. This is the **first live item
waiting on CI's return**.

Per-reference evidence, the discriminators, and the order of operations:
**[`docs/status/adr-renumber-evidence.md`](../status/adr-renumber-evidence.md)**.

The ratchet (`tests/unit/test_adr_hygiene.py`) now freezes exactly one collision — `0010` — and
fails both on a NEW duplicate and on a stale entry left in the frozen set.
