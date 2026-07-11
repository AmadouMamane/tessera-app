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
| 0008 ⚠️ | [Security hardening](0008-security-hardening.md) — *senior, 2026-05-31* |
| 0008 ⚠️ | [Agent audience and surface](0008-agent-audience-and-surface.md) — *junior, 2026-06-22* |
| 0009 | [Dashboard auth & RBAC](0009-dashboard-auth-rbac.md) |
| 0010 ⚠️ | [Frontier observability](0010-frontier-observability.md) — *senior, 2026-06-08* |
| 0010 ⚠️ | [Recouvrement internal operator agent](0010-recouvrement-internal-operator-agent.md) — *junior, 2026-06-22* |
| 0011 | [Temporal as-of-T dimension](0011-temporal-as-of-t-dimension.md) |
| 0012 | [Agent registry and seed](0012-agent-registry-and-seed.md) |
| 0013 | [Entry routing by audience](0013-entry-routing-by-audience.md) |
| 0014 | [Environment isolation](0014-environment-isolation.md) |
| 0015 | [Runtime telemetry spine and scope](0015-runtime-telemetry-spine-and-scope.md) |
| 0015 ⚠️ | [Hica seal design note](0015-hica-seal-design-note.md) — *an annex to 0015, not a separate decision* |
| 0016 | [Business-events fan-out contract](0016-business-events-fanout-contract.md) |
| 0017 | [Agent observability contract](0017-agent-observability-contract.md) |
| 0018 | [Assistant runtime turn contract](0018-assistant-runtime-turn-contract.md) |
| 0019 | [Invocation binding](0019-invocation-binding.md) |

## The three remaining number collisions (⚠️) — known, frozen, not yet renumbered

Two pairs of *genuine* ADRs share a number (0008, 0010), and the Hica seal design note is an
annex filed under 0015.

They are **deliberately not renumbered yet**, and the reason is worth writing down. "ADR 0010"
is referenced **138 times** across code comments, docs and ADRs — and it means
*frontier-observability* in some of them and *recouvrement* in others (`operator.py` says "ADR
0010 Phase B/C", meaning recouvrement). "ADR 0008" is referenced 55 times, ambiguously in the
same way. Renumbering means correctly reassigning every one of those references by judgment.
Get a single one wrong and the decision record — the project's memory — states something false.
A duplicate number is an annoyance; a decision record that lies is a defect.

So the renumbering is a lot of its own, done deliberately, in daylight, with the reference
sweep as its actual subject. What is done here instead:

* the logs that were squatting ADR numbers are gone from this directory;
* the collisions are **named** rather than silently tolerated;
* a ratchet (`tests/unit/test_adr_hygiene.py`) freezes them at exactly these three and fails on
  any NEW duplicate prefix — the set can shrink, never grow.

Plan when it is done: juniors move to 0020+ (`0008-agent-audience-and-surface` → 0020,
`0010-recouvrement-internal-operator-agent` → 0021), the seal note becomes
`0015-annex-hica-seal.md`, every reference is disambiguated by reading it, and the ratchet's
frozen set drops to empty.
