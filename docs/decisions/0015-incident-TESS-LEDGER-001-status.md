# Incident TESS-LEDGER-001 — execution status

Single source of truth for **where the `audit_ledger`-forks remediation is**. Executing
session updates this file after **every point**; a resuming session reads this first, then
continues the next `pending` point — no re-work. Companion to
`docs/decisions/0015-runtime-telemetry-spine-and-scope.md` (§Amendment 3, the promotion this
incident retrofits with write-serialization).

- **Incident**: 29 forks in the append-only hash-chain `audit_ledger` (concurrent writers
  extended the same head — TOCTOU). Per-row inviolability INTACT; what is lost is **total
  order** at the 29 fork points. Full brief: `Tessera_private/incident-ledger-forks-2026-07-07.md`.
- **Protocol** (per point, strict order 0→6): implement → full gate **twice green**
  (`ruff check` + `ruff format --check` + `mypy src/tessera` + `pytest -m "not integration"`;
  `tsc` + `biome` + `vitest` when the point touches the webapp) + point-specific verification
  → commit (**targeted staging, never `git add -A`**) → update this ledger → advance.
- **Absolutes**: NEVER `DELETE`/`UPDATE` on `audit_ledger` — append-only is absolute (also
  enforced by a DB trigger). History is NEVER rewritten; re-anchoring is an **appended
  attestation entry** (point 4). **HALT + report** if the investigation contradicts the
  presumed root cause.
- **Branch**: `claude/incident-ledger-forks` (from `main`).

## Point ledger

| Point | Scope (short) | Status | Commit | Notes |
|---|---|---|---|---|
| 0 | Evidence freeze: `pg_dump` of `audit_ledger` + SHA-256 recorded (chain of custody) — before any code change | ✅ done | — | Dump `Tessera_private/evidence/TESS-LEDGER-001/audit_ledger-20260707T105358Z.sql`; SHA-256 `7affe196…c5a7465`; freeze state `rows=13382, max_seq=17135, fork_groups=29`. +8 rows vs brief (linear, 29 forks unchanged); append-only already trigger-enforced. Custody block appended to the private brief. |
| 1 | Short investigation (documented): temporal distribution of the 29 forks; event families; genesis-seed (`audit.py:264`) ↔ store head (`ledger_store.py:438`) interaction; why `broken_at=2551` vs first fork ~6280 (verify walk order). HALT if it contradicts the root cause. | ⬜ pending | — | — |
| 2 | Writer fix (illegal state unrepresentable): `pg_advisory_xact_lock` + head-read-in-txn + insert; partial unique index `ON audit_ledger(prev_hash) WHERE seq > <anchor>`; drop the `_last_hash` cache for the postgres sink; fix the genesis seed; **N-writer concurrency test → zero forks**. | ⬜ pending | — | — |
| 3 | Tree-aware verifier + badge: output `{content_integrity, linear, forks[]}`; badge "Content integrity: verified · Total order: broken (29 historical forks, attested)". Orphans REPORTED, never deleted. | ⬜ pending | — | — |
| 4 | Re-anchor by attestation (append-only): append a signed attestation entry (fork list, cause, decision, point-0 dump hash); the partial index anchors linearity from there. | ⬜ pending | — | — |
| 5 | ADR 0015 §Amendment 3 **Correction**: write-serialization requirement, tree-aware verify semantics, anchoring pattern; priority bump for the external seal (Hica). | ⬜ pending | — | — |
| 6 | Closure: closing ledger entry; cockpit badge reflects the attested state. | ⬜ pending | — | — |

Status legend: ⬜ pending · 🟡 in progress · ✅ done (twice-green) · ⛔ blocked (see notes).

## Log (newest first)

- 2026-07-07 — **Point 0 done — evidence freeze.** `pg_dump` of `tessera_local.audit_ledger`
  captured at `2026-07-07T10:53:58Z` (13 382 rows, structure + trigger + index), SHA-256
  `7affe19665b577c4e97e0059482adb8c9c6ebbe01265c1ee1b2297141c5a7465` recorded in the private
  brief (chain of custody). Confirmed against the brief's facts: **29 fork groups** (unchanged),
  `max_seq=17135`; rowcount is **13 382** (+8 vs the brief — linear appends, no new fork). Noted
  for point 1 (no code touched): the earliest fork by child-seq is `b6714ba4…` (children
  `{5985,6303}`), not the brief's `00f3306d…` (children `{6281,6282}`) — resolve by ordering on
  the **parent** seq. `mypy src/tessera` clean (262 files) — baseline green before any change.
  Docs-only point → Python gate is the affected surface; webapp untouched.
