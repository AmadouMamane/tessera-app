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
| 0 | Evidence freeze: `pg_dump` of `audit_ledger` + SHA-256 recorded (chain of custody) — before any code change | ✅ done | `fbffbd04` | Dump `Tessera_private/evidence/TESS-LEDGER-001/audit_ledger-20260707T105358Z.sql`; SHA-256 `7affe196…c5a7465`; freeze state `rows=13382, max_seq=17135, fork_groups=29`. +8 rows vs brief (linear, 29 forks unchanged); append-only already trigger-enforced. Custody block appended to the private brief. |
| 1 | Short investigation (documented): temporal distribution of the 29 forks; event families; genesis-seed (`audit.py:264`) ↔ store head (`ledger_store.py:438`) interaction; why `broken_at=2551` vs first fork ~6280 (verify walk order). HALT if it contradicts the root cause. | ✅ done | `5e527c16` | **Root cause CONFIRMED + refined — no contradiction, no halt.** Real `verify_ledger_rows` reproduced `broken_at=2551` (a WALK position, not a seq: the low-seq-first walk dies on the dead child 6281). True first fork = **parent seq 5984** (not 6280); 0 orphan-parent forks; genesis has one child. Dominant driver = **per-process `_last_hash` cache** (audit.py:57) — proven on fork parent 10663 (child 12643 chained 1 h later from the same process's own last write). 20/29 forks in the 07-03 17–22Z parallel-session burst; tail to 07-07 06:06 (bug still live). Fix crux: (re)link at the serialized drain under `pg_advisory_xact_lock`, not at emit. |
| 2 | Writer fix (illegal state unrepresentable): `pg_advisory_xact_lock` + head-read-in-txn + insert; partial unique index `ON audit_ledger(prev_hash) WHERE seq > <anchor>`; drop the `_last_hash` cache for the postgres sink; fix the genesis seed; **N-writer concurrency test → zero forks**. | ✅ done | `12ca1494` | **Illegal state now unrepresentable.** The drain (`_link_and_insert`) reads the true head + links + inserts inside ONE `pg_advisory_xact_lock(TESS,LDGR)` txn → insert order IS chain order; emit stops linking in postgres mode (`_last_hash` dropped) and only stamps a position-independent `event_id` (the drain's idempotence key — a crash-replayed drain never duplicates). Two DB guards: partial UNIQUE `audit_ledger_no_fork` on `prev_hash WHERE seq > <hwm>` (grandfathers the 29; forbids new forks) + UNIQUE `audit_ledger_event_uq` on `event_id`. Genesis-seed landmine gone (unreachable → defer, never genesis-restart). **Live-installed on `tessera_local`** (anchor `seq>17135`, 29 forks preserved). Tests: rewrote spool/cutover units to the drain-linking contract + new `_ledger_fake`; **integration `test_n_parallel_writers_produce_zero_forks`** (8 threads × 20, real advisory-lock contention → 0 forks, chain verifies) + fork-guard rejection. Twice-green: ruff/format/mypy 262/pytest 1341 + 6 live integration. |
| 3 | Tree-aware verifier + badge: output `{content_integrity, linear, forks[], orphans[]}`; badge "Content integrity: verified · Total order: broken (…historical forks, attested)". Orphans REPORTED, never deleted. | ✅ done | `273e2e17` | **The verifier learned the difference.** New `verify_ledger_tree` → `{content_integrity, linear, forks[], orphans[], attested}`; `verify_active_ledger().verified` now = **content integrity** (tamper-evidence), so the whole cockpit stops mis-reading a fork as tampering. Badge (`app-footer.tsx`) is tri-state: green (intact+linear) / **amber ⑂** (content intact, N forks[+orphans], attested|pending) / red (content edited). Signal + `/audit/integrity` carry `content_integrity/linear/fork_count/orphan_count/attested`. **NEW FINDING (refines, doesn't contradict, the root cause → no halt): 1 ORPHAN** — row seq 11814 references parent `11682ad4…` that no row holds = a **lost parent write** (append-only forbids DELETE; same async-drain bug). So the honest live verdict is **content_integrity=True, linear=False, 29 forks + 1 orphan, unattested**. Corrects the brief's "every row chains to its parent". Tests: `TestTreeAwareVerification` (6). Twice-green: py 1347 ×2 + 6 integration; FE tsc/biome/vitest 69. |
| 4 | Re-anchor by attestation (append-only): append a signed attestation entry (fork list, cause, decision, point-0 dump hash); the partial index anchors linearity from there. | ✅ done | `283976b9` | **Re-anchored by attestation, never rewrite.** New reusable `build_ledger_attestation_entry` + `emit_ledger_attestation` (the anchoring pattern point 5 documents). **Live-appended to `tessera_local`** via the fixed serialized path (emit → spool → advisory-locked drain): **seq 17136** (> anchor 17135 → itself fork-guarded), `type=tessera.ledger.attestation`, recording the **29 forks + 1 orphan**, cause, decision, and the **point-0 dump SHA-256** (`7affe196…`) as chain of custody; `prev_hash` = the prior head `af8634ab…`. Pure append: rows 13382→**13383**, the 29 forks + 1 orphan **unchanged** (never rewritten), no DELETE/UPDATE. Verifier now reports **attested=True** → the badge flips to "attested". Tests: builder unit test. Twice-green: py 1348 ×2 + 6 integration. |
| 5 | ADR 0015 §Amendment 3 **Correction**: write-serialization requirement, tree-aware verify semantics, anchoring pattern; priority bump for the external seal (Hica). | ✅ done | `<point-5>` | **§Correction 3c** appended to `0015-runtime-telemetry-spine-and-scope.md` (+ header summary line). Names the ADR gap (Amendment 3 changed the medium, not the write model — the flat file was implicitly single-writer; Postgres opened multi-writer without a serialization contract) and records: (1) writes serialized at the durable point (advisory lock + head-in-txn, `_last_hash` dropped, `event_id` idempotence, partial UNIQUE fork guard); (2) tree-aware verify (content integrity ≠ total order; forks/orphans reported); (3) re-anchor by attestation, never rewrite (the anchoring pattern); (4) Hica seal re-scoped from opposability badge to a **time-bound divergence detector** (would have bounded the 4-day window) — still enrichment, never the store. Docs-only; twice-green py 1348 ×2. |
| 6 | Closure: closing ledger entry; cockpit badge reflects the attested state. | ⬜ pending | — | — |

Status legend: ⬜ pending · 🟡 in progress · ✅ done (twice-green) · ⛔ blocked (see notes).

## Log (newest first)

- 2026-07-07 — **Point 5 done — ADR 0015 §Correction 3c.** Appended to
  `0015-runtime-telemetry-spine-and-scope.md` (+ the header amendment summary). It names the gap
  honestly: **Amendment 3 changed the medium (flat file → Postgres) but not the write model** —
  the flat file was implicitly single-writer; the shared table opened multi-writer access without
  a serialization contract, and the dual-write linked the chain at emit from a per-process cache
  → the fork. The Correction records the four shipped fixes: (1) **serialized writes** at the
  durable point (advisory lock + head-read-in-txn, per-process cache removed, `event_id`
  idempotence, partial UNIQUE fork guard + event_id index added to the Amendment-3 DDL); (2)
  **tree-aware verify** (content integrity ≠ total order; forks + orphans reported, never
  deleted); (3) **re-anchor by attestation, never rewrite** (the reusable anchoring pattern); (4)
  **Hica external seal priority raised** from opposability badge to a time-bound divergence
  detector (a head-seal would have bounded the 4-day fork window) — still enrichment, never the
  store. Nothing about ownership / append-only / hash-chaining / never-third-party changes.
  Docs-only; twice-green py 1348 ×2.

- 2026-07-07 — **Point 4 done — re-anchor by attestation (append-only).** New reusable
  `build_ledger_attestation_entry` + `emit_ledger_attestation` (audit.py) — the "anchoring
  pattern" point 5 records in the ADR. **One deliberate append to the live `tessera_local`
  table** through the FIXED serialized path (emit → spool → advisory-locked drain): a
  `tessera.ledger.attestation` entry at **seq 17136** (> the fork-guard anchor 17135, so the
  attestation is itself fork-proof), linked to the prior head `af8634ab…`, recording the **29
  forks + 1 orphan**, the cause (the `_last_hash`/unlocked-head ADR gap), the decision
  (re-anchor, never rewrite), and the **point-0 evidence dump SHA-256** `7affe196…` as chain of
  custody. **Pure append**: rows 13382 → 13383, `fork_groups` still **29**, orphan still **1** —
  nothing rewritten, no DELETE/UPDATE (the trigger forbids it anyway). The tree verifier now
  reports **attested=True**, so the badge reads "…forks, attested" instead of "pending".
  Idempotent-guarded (skips if already attested). Twice-green: ruff/format/mypy 262/pytest
  **1348** ×2 + 6 live integration. External cryptographic seal (Hica) stays the enrichment,
  never the store — its priority is bumped in point 5.

- 2026-07-07 — **Point 3 done — tree-aware verifier + badge.** New `verify_ledger_tree` returns
  `{content_integrity, linear, forks[], orphans[], attested}`: content integrity (every present
  row hashes correctly — the tamper guarantee) is now judged SEPARATELY from total order (forks)
  and completeness (orphans). `verify_active_ledger().verified` is re-pointed to content integrity
  so the ~10 cockpit consumers stop mis-reporting a historical fork as tampering; the dedicated
  integrity badge (`components/layout/app-footer.tsx`) carries the nuance — tri-state green /
  amber ⑂ (content verified · N historical forks[+orphans], attested|pending) / red (real edit).
  The signal + `GET /audit/integrity` now emit `content_integrity/linear/fork_count/orphan_count/
  attested` (+ the fork/orphan lists on the signal for evidence). **NEW FINDING while wiring the
  verifier — refines but does NOT contradict the root cause, so no halt: there is 1 ORPHAN** —
  row `seq 11814` (2026-07-05) points at parent `11682ad4…` that no row holds. Its parent entry
  was **never persisted** (a lost write — append-only forbids DELETE, so not tampering); same
  async-drain-without-serialization bug as the forks. This corrects the brief's impact line
  ("every row chains correctly to its parent") — the honest live verdict on `tessera_local` is
  **content_integrity=True, linear=False, 29 forks + 1 orphan, unattested**. Point 4's attestation
  must ratify the orphan too. Tests: `TestTreeAwareVerification` (6 cases: clean/fork/orphan/edit/
  attested/empty). Twice-green: ruff/format/mypy 262/pytest 1347 ×2 + 6 live integration; FE
  tsc + biome (changed) + vitest 69. i18n keys added to `appFooter` in en/fr/de.

- 2026-07-07 — **Point 2 done — writer fix (illegal state unrepresentable).** The chain linkage
  moves off the per-process `_last_hash` cache (the fork cause) to the single serialized write
  point. `audit._append_to_chain` in postgres mode stamps only a position-independent
  `event_id` and spools; `ledger_store._link_and_insert` reads the true head + links + inserts
  inside ONE `pg_advisory_xact_lock(TESS,LDGR)` transaction, so insert order IS chain order and
  two writers can never extend the same head. Belt-and-suspenders at the DB: partial UNIQUE
  `audit_ledger_no_fork (prev_hash) WHERE seq > <hwm>` (grandfathers the 29 historical forks —
  append-only is absolute — and forbids every new one) + UNIQUE `audit_ledger_event_uq` on
  `event_id` (crash-replayed drain = no-op; the drain pre-filters by it, plain INSERT, retry on
  the guard's conflict). Genesis-seed landmine removed: an unreachable table defers (spool kept),
  never restarts the chain from genesis. File-escape mode is untouched (single writer → emit
  linking is correct). **Live-installed on `tessera_local` via the real `ensure_audit_ledger_schema`**
  (anchor `seq > 17135`; the 29 forks are all below it, untouched). Tests: rewrote the spool +
  cutover units to the drain-linking contract (+ hermetic `tests/unit/_ledger_fake.py`), added
  the integration test the incident lacked — `test_n_parallel_writers_produce_zero_forks` (8
  threads × 20 writes, own connections, real advisory-lock contention → **0 forks**, one chain
  verifies) + `test_fork_guard_rejects_a_second_child_of_a_parent`. Twice-green: ruff / format /
  mypy (262) / pytest **1341** ×2 + **6 live ledger integration** (tessera_ci schema, isolated
  from the incident data). No frontend surface. Docstrings realigned off the old `ON CONFLICT
  (hash)` idempotence to the `event_id` + advisory-lock model.

- 2026-07-07 — **Point 1 done — investigation. Root cause CONFIRMED + refined; NO halt.**
  Rejoue le verify réel (`verify_ledger_rows`) en lecture seule + analyse topologie/temporalité
  (`scratchpad/investigate_forks.py`). (1) **`broken_at=2551` élucidé** : c'est une *position de
  marche*, pas un seq — la marche « seq-bas d'abord » suit la branche courte et meurt sur l'enfant
  mort seq 6281 (fourche parent 6280) ; le gros de la table vit sur la branche sœur 6303. (2)
  **Topologie** : vraie 1ʳᵉ fourche = **parent seq 5984** (pas 6280) ; **0 fourche orphan-parent**,
  genesis a un seul enfant → intégrité de contenu intacte, aucun redémarrage-genesis. (3) **Pilote
  dominant = cache `_last_hash` par process** (audit.py:57), prouvé sur la fourche parent 10663
  (enfant 12643 chaîné 1 h plus tard depuis la propre dernière écriture du même process — drain
  prompt, donc pas une latence de spool). (4) **Seed-genesis (audit.py:264) ↔ tête (:438)** :
  consultée 1×/process au 1ᵉʳ append ; la ligne 264 n'est qu'un fallback → landmine latent (seed
  genesis sur injoignabilité) qui **n'a pas tiré** ici. (5) **Temporel** : 20/29 fourches dans la
  rafale 07-03 17–22Z (sessions parallèles), queue jusqu'à 07-07 06:06 → **bug encore vivant**
  (630 écritures/24 h). Familles : guard.audit domine ; agents support-client + recouvrement.
  **Crux du fix (point 2)** : (ré)assigner `prev_hash`/`hash` au **drain sérialisé** sous
  `pg_advisory_xact_lock` (lire la vraie tête dans la txn), supprimer `_last_hash` pour le sink
  postgres, + index unique partiel `ON audit_ledger(prev_hash) WHERE seq > <ancre>` + retry.
  Corrections mineures aux *Faits* (cadrage) : 13382 lignes (+8) ; 1ʳᵉ fourche = 5984 ;
  `broken_at` = position. Investigation documentée en détail dans le brief privé. Docs-only →
  Python gate twice-green, webapp untouched.

- 2026-07-07 — **Point 0 done — evidence freeze.** `pg_dump` of `tessera_local.audit_ledger`
  captured at `2026-07-07T10:53:58Z` (13 382 rows, structure + trigger + index), SHA-256
  `7affe19665b577c4e97e0059482adb8c9c6ebbe01265c1ee1b2297141c5a7465` recorded in the private
  brief (chain of custody). Confirmed against the brief's facts: **29 fork groups** (unchanged),
  `max_seq=17135`; rowcount is **13 382** (+8 vs the brief — linear appends, no new fork). Noted
  for point 1 (no code touched): the earliest fork by child-seq is `b6714ba4…` (children
  `{5985,6303}`), not the brief's `00f3306d…` (children `{6281,6282}`) — resolve by ordering on
  the **parent** seq. `mypy src/tessera` clean (262 files) — baseline green before any change.
  Docs-only point → Python gate is the affected surface; webapp untouched.
