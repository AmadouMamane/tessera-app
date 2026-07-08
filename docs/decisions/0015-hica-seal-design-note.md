# 0015 — Hica external opposability seal: design note (Lot 1)

> **Status: APPROVED 2026-07-08** (review *"Hica seal design review"*). **Lots 1–3 complete.**
> Companion to ADR `0015-runtime-telemetry-spine-and-scope.md` (§Amendment 3 pt 3, §Correction 3c
> pt 4) and to the incident record `0015-incident-TESS-LEDGER-001-status.md`. This note does **not**
> re-decide the seal (ADR 0015 already accepted it) — it decides the **mechanism** and the **wiring**.
> Kept as a **companion note** (Q7 ruling — not folded into the ADR). The review rulings are recorded
> in §9bis; they add the **qualified-vs-non-qualified TSA** distinction (Q1) and the **footer suffix**
> (Q5) to the design below.

This is the design note for the external opposability seal that ADR 0015 §Correction 3c raised in
priority: an external seal that periodically attests the ledger **head** would have bounded the
TESS-LEDGER-001 divergence window from **four days** to **one seal interval**. The seal is an
**opposability enrichment, never the store** — *owned first, sealed second*.

---

## 1. Mandate (the binding sources)

Four sources fix the contract; this note may not weaken any of them.

- **ADR 0015 §Amendment 3, point 3** — *"External seal (Hica) = opposability ENRICHMENT, not the
  store. The owned ledger is the truth; the third-party seal periodically **attests the chain
  head** … Owned first, sealed second — the seal being unavailable degrades to «Intégrité partielle»
  (chain valid, seal unverifiable), never to «no ledger»."*
- **ADR 0015 §Correction 3c, point 4** — the seal is re-scoped from a mere badge to a **time-bound
  divergence detector**: *"a fork changes the head lineage, so the next seal would have flagged it
  within the seal interval instead of letting 29 forks accumulate across four days undetected …
  while remaining best-effort and non-authoritative."*
- **Rails register §9** (`Tessera_private/registre-rails-temporels.md`) — the badge is **dynamic,
  computed at display from the verification result, never stored, never cosmetic**. Four states:
  **Scellé · opposable** (chain hash verified **AND** third-party seal verified), **Intégrité
  partielle** (chain valid **but** seal absent / unverifiable), **Non scellé** (integrity failure —
  chain broken), transient **Vérification en cours**. Mandatory sub-mention: *« Statut attribué
  uniquement après vérification réussie. »*
- **Absolute honesty rule** (mission + post-mortem lessons 2–4) — **no fake seal.** If no seal
  service is configured/reachable, the badge is **never** "Scellé". A cosmetic green is the one thing
  the whole incident taught us to refuse.

### 1.1 Pre-existing honesty gap this work must correct

`webapp/frontend/components/proofs/etat-a-date.tsx:266` renders the **"Scellé"** badge (and
`:154`, the printable report's `SCELLE - Etat opposable`) whenever `reconstructed.verified` is true —
i.e. on **chain content-integrity alone, with no external seal behind it**. Under register §9,
"Scellé · opposable" requires *chain verified **AND** third-party seal verified*. Today's badge
therefore **over-claims**: it says "sealed / opposable" for a state that is only internally
tamper-evident. This is precisely the fake-seal the mission forbids. Correcting it is in scope for
Lot 2 and — importantly — **turning on honesty makes this badge go from green to amber** (Intégrité
partielle) until a real seal provider is configured. That visible downgrade is called out for the
reviewer in §8 and §9; it is a feature, not a regression.

---

## 2. Requirements the mechanism must satisfy

| # | Requirement | Source |
|---|---|---|
| **R1** | **Attests the head, does not store.** The mechanism binds the *hash of the current head* to a time; it never becomes a second home for ledger content. | Am3 p3, "never the store" |
| **R2** | **Owned first, sealed second.** The owned Postgres ledger stays the sole truth. The seal is best-effort; its absence degrades to «Intégrité partielle», never to «no ledger». | Am3 p3 |
| **R3** | **Verifiable outside Tessera.** A third party (auditor, regulator, court) can verify the seal **without Tessera's code, cooperation, or continued existence** — offline, against a public trust root. | §9 "opposable"; opposabilité = legal admissibility |
| **R4** | **Time-bound divergence detector.** Each cycle pins the head; a fork/rewrite between two cycles is flagged **within one interval**. The interval is the guaranteed upper bound on undetected-anomaly time. | Corr3c p4 |
| **R5** | **Composes with `verify_ledger_tree`, never replaces it.** The seal is a *fifth* fact layered on `{content_integrity, linear, forks, orphans, attested}` — it does not re-implement chain verification. | Corr3c p2, "the seal is enrichment" |
| **R6** | **Self-hostable OR a neutral service.** Not a Tessera-controlled store (that would defeat R3). Must work in both the deployed (Cloud Run) and the on-prem (Apple Silicon) postures. | mission constraint |
| **R7** | **Honest by construction.** No provider configured ⇒ the code path *cannot* emit "Scellé". The badge is recomputed live from a real cryptographic verification, never a stored boolean. | honesty rule, §9 "jamais cosmétique" |
| **R8** | **Best-effort, non-authoritative.** The seal never gates a release, never blocks a write, never becomes load-bearing. The chain remains the evidence; the seal *bounds detection latency* and *adds third-party opposability*. | Corr3c p4 |

---

## 3. Mechanism evaluation

Candidates evaluated against R1–R8. "Neutral/self-host" = R6; "3rd-party-verifiable offline" = R3;
"attests ≠ stores" = R1.

| Mechanism | Attests vs stores (R1) | Offline 3rd-party verify (R3) | Self-host **or** neutral (R6) | EU legal opposability | Divergence-detector fit (R4) | Complexity |
|---|---|---|---|---|---|---|
| **A. RFC 3161 TSA** (signed timestamp token over the head hash) | **Attests** — a TST is a signed assertion about `(digest, time)`; stores nothing of ours | **Yes** — `openssl ts -verify` against the TSA cert; standard CMS, no Tessera code | **Both** — self-host `openssl ts` CA (on-prem/dev) **or** a qualified public TSA (demo) | **Strongest** — eIDAS **qualified electronic timestamp** is directly opposable under EU law (DORA/BaFin/eIDAS) | **Excellent** — per-cycle TST pins the head lineage; a moved head is provable | **Low** |
| **B. Transparency log** (Rekor / Trillian / CT-style) — append head to a Merkle log, keep inclusion proof + STH | **Attests + witnesses** — the log is append-only and gossiped; our data isn't "stored" by us | **Yes** — inclusion proof + signed tree head against the log's public key | **Both** — self-host Trillian/Rekor **or** public Sigstore Rekor | Weaker *legally* (not a named eIDAS instrument), technically superb | **Excellent** — a second append-only witness of head lineage | **High** (run a log) or medium (public Rekor, external dep) |
| **C. S3 Object-Lock (WORM)** — write head to a COMPLIANCE-mode locked object | **Stores** — it is a WORM *store*, not a signed assertion; PUT-time only, no signed timestamp token | **Weak** — verifier must query the bucket and *trust the provider's* lock enforcement; no offline cryptographic proof | Self-host (MinIO) weakens R3 (we control it); AWS is trust-the-provider | Weak (provider attestation, not a signed timestamp) | Weak — it stores a copy; it does not *sign* head-at-T | Medium |
| **D. OpenTimestamps** (Bitcoin-anchored) | **Attests** — commits the head hash into Bitcoin via calendar servers | **Yes** — verify offline against Bitcoin headers; fully decentralized | **Neutral** — public calendars; trust-minimized | Not a named eIDAS instrument; strong existence-proof | Good, but **coarse** (block time) and **high latency** (hours to confirm) | Medium; perception/latency baggage |
| **E. Tessera self-signs the head with its own KMS key** | — | — | — | **None** | — | — |

**E is rejected outright.** A signature by a Tessera-controlled key adds **zero** third-party
opposability — it proves nothing against Tessera itself, and dressing it as a "seal" is exactly the
fake-seal trap (looks sealed, opposable value nil). Named only to forbid it.

**C is rejected as a *seal*.** Object-Lock is a **store**, and ADR 0015 is categorical: *the seal
attests, it does not store; never the store*. It also fails R3 cleanly (its guarantee is "trust the
provider's WORM control plane", not a signed proof a regulator can validate offline). Object-Lock is
a fine *retention* control for the owned ledger backups — but that is a different job, not the seal.

---

## 4. Recommendation

> **Ship RFC 3161 TSA (A) as the one real provider, behind a small `SealProvider` protocol so B
> (transparency log) and D (OpenTimestamps) can be added later without touching the wiring. Reject C
> and E as seals.**

Why TSA is the right first (and default-real) anchor:

1. **Best "attests, not stores" fit (R1).** A TST is a signed statement about a hash and a time; it
   is the textbook realization of "attest the head" and stores nothing of ours.
2. **Strongest EU opposability (R3, and Tessera's whole raison d'être).** "Opposabilité" is a legal
   word. eIDAS **qualified electronic timestamps** are directly admissible under EU law — precisely
   the DORA/BaFin/GDPR posture Tessera exists to demonstrate. The instrument should be the legally
   recognized one, not merely the technically clever one.
3. **Fully verifiable outside Tessera (R3).** `openssl ts -verify -in head.tst -data head.txt
   -CAfile tsa-ca.pem` — standard tooling, offline, no Tessera involvement, survives Tessera's death.
4. **Dual-posture (R6).** Self-hosted `openssl ts` CA for on-prem/dev; a qualified public TSA
   (e.g. FreeTSA for dev, an eIDAS-qualified TSA for the deployed demo) for the frontier path. Mirrors
   the existing frontier/on-prem split.
5. **Low complexity, high leverage (R8).** ~KB per cycle, one well-supported standard, one thin
   dependency (`rfc3161-client`/`rfc3161ng`, or shell out to `openssl ts`), no service to operate.

The `SealProvider` protocol is not gold-plating — Corr3c calls the seal "best-effort and
non-authoritative", and a future move to a transparency log (stronger tamper-witnessing) or
OpenTimestamps (trust-minimized) is then a drop-in. **But Lot 2 ships exactly one real provider
(TSA) plus the honest `none` default — never a stub that pretends.**

---

## 5. Proposed architecture (for ratification, not yet built)

### 5.1 The seal subsystem — `src/tessera/guard/seal.py` ("Hica")

"Hica" is the design's name for the third-party-seal subsystem; RFC 3161 is the concrete anchor it
uses. New module beside `ledger_store.py` / `audit.py`, so it composes with the existing chain code.

```python
class SealToken(Protocol):     # opaque, provider-specific (a TST for RFC 3161)
    sealed_head: str           # the head hash this token attests
    sealed_at: str             # ISO-8601, from the TOKEN (TSA time), not our clock
    provider: str              # "rfc3161" | ...
    material: str              # base64 of the verifiable artifact (the TST)

class SealProvider(Protocol):
    def seal(self, head_hash: str) -> SealToken: ...            # obtain a fresh attestation
    def verify(self, token: SealToken, head_hash: str) -> SealVerification: ...  # offline crypto check
```

A `NoOpProvider` is the default (`seal_provider="none"`) and it **cannot** produce a token — every
call raises / returns "absent", so the badge can never go green without a real provider. This is the
honesty invariant made structural (R7).

### 5.2 Where the seal token lives — an appended `tessera.ledger.seal` entry

Reuse the attestation precedent (`build_ledger_attestation_entry` / `emit_ledger_attestation`,
`audit.py:547`). Each successful seal appends **one** entry through the *serialized* append path
(`_append_to_chain` → spool → advisory-locked drain — `ledger_store.py:299`), carrying:

```json
{ "type": "tessera.ledger.seal", "version": 1,
  "sealed_head": "<hash of the head at seal time>",
  "prev_sealed_head": "<the previous seal's sealed_head, or null>",
  "provider": "rfc3161", "tsa": "<url>",
  "token_b64": "<the TST — the externally-verifiable artifact>",
  "sealed_at": "<TSA time>", "occurred_at": "…" }
```

- **This keeps "one consolidated chain"** (§Corr3b) and reuses the fork-proof serialized writer. The
  seal record is itself inside the tamper-evident chain; the *token inside it* is what a third party
  re-validates cryptographically, independent of us — so R1 holds (**the TSA attests; we merely keep
  the receipt in our own store**; the TSA never stores our data).
- **Subtlety (flagged):** appending the seal entry **moves the head** (new head = hash(seal entry)).
  That is expected and self-consistent: the seal attests the head *as of the seal instant*; the next
  cycle seals the new head, which now includes the prior seal entry. This yields a clean chain of
  seals, each pinning the previous head.
- **Alternative considered:** a sidecar `ledger_seals` table (head does not move). Rejected as the
  default because it introduces a *second* store to verify and breaks the one-chain property; kept as
  a fallback if the reviewer prefers the head to be immovable. **Open question Q2.**

### 5.3 The seal cycle (writer side), interval τ

Runs off-chrono (a periodic job, like the Prometheus exporter), never on a request path:

1. `H_c = ledger_head_hash()`; `S_prev` = latest `tessera.ledger.seal` entry (→ `H_prev`, its token).
2. **Continuity check** — walk forward from `H_prev` over present rows (the `children` map that
   `verify_ledger_tree` already builds):
   - `H_c` reachable from `H_prev` by a single unbroken, content-intact path, **no new fork** in
     `(H_prev, H_c]` → **continuous**. Proceed to seal.
   - a **new fork** appeared since the last seal → **divergence detected** (this is the R4 catch,
     bounded to τ). Do **not** paper over it: increment a Prometheus divergence counter, and append a
     `tessera.ledger.seal` entry with `divergence: true` recording the fork rather than a clean seal.
     Badge downgrades (see §6). Loud, not silent.
   - `H_prev` no longer present / `H_c` unreachable from it → **rewrite alarm**: `H_prev` was
     externally TST-sealed, so its disappearance is *provable* tampering → red, alert.
3. On **continuous**: `token = provider.seal(H_c)`; append the `tessera.ledger.seal` entry via the
   serialized path. If the provider is unreachable (TSA down) → **no entry appended**, badge stays
   «Intégrité partielle» until a real seal lands (R2/R7). Never a placeholder.

First-ever seal (no `S_prev`): seal the current head, `prev_sealed_head = null`.

### 5.4 Display-time verification (badge side), as of instant T — pure, cached, live

Extends `active_ledger_tree_status` (`ledger_store.py:732`) / `_audit_integrity`
(`api/routes/audit.py:393`). For payloads ≤ T:

1. `tree = verify_ledger_tree(payloads≤T)` → `{content_integrity, linear, forks, orphans, attested}`
   (**unchanged** — R5).
2. `seal = evaluate_seal(payloads≤T)`:
   - latest `tessera.ledger.seal` with `sealed_at ≤ T`; if none **or** provider not configured →
     `SEAL_ABSENT`.
   - else re-verify the token **cryptographically, offline** against the pinned TSA cert **and**
     that the timestamped digest == `sealed_head` **and** `sealed_head` is present ≤ T and is a
     content-intact ancestor of head(T) **and** freshness `T − sealed_at ≤ staleness_budget` (a stale
     seal → `SEAL_STALE`, because the R4 detection guarantee has lapsed).
   - → one of `SEAL_VERIFIED | SEAL_STALE | SEAL_UNVERIFIABLE | SEAL_ABSENT`.
3. Map to the §9 badge (§6). Every field is recomputed live from the token — **never** a stored
   badge string (R7, §9 "jamais cosmétique").

### 5.5 Config (honest defaults) — new `GuardSettings` fields (`settings.py:164`)

```
TESSERA_GUARD_SEAL_PROVIDER          = "none"   # "none" | "rfc3161"     ← default OFF
TESSERA_GUARD_SEAL_TSA_URL           = None     # required iff provider="rfc3161"
TESSERA_GUARD_SEAL_TSA_CERT          = None     # pinned CA/verify cert (the trust root)
TESSERA_GUARD_SEAL_TSA_QUALIFIED     = False    # eIDAS-qualified? (Q1) → "opposable" vs "non qualifié"
TESSERA_GUARD_SEAL_INTERVAL_S        = 3600     # τ — the bounded detection window (configurable)
TESSERA_GUARD_SEAL_STALENESS_BUDGET_S= 7200     # 2τ — beyond this the seal is "stale" → partial
```

`provider="none"` (the default, and the state of every current environment) ⇒ `SEAL_ABSENT` ⇒ badge
**can never be "Scellé"**. Enforced by a test (§8, H1).

---

## 6. Badge composition — the §9 truth table (tree-aware)

The seal layers onto the tree verdict. `content_integrity` is the tamper guarantee (Corr3c p2), so
"chaîne rompue" in §9 = `content_integrity == false`; a fork is **not** a break.

| # | `content_integrity` | seal state | linear / attested | **Badge (§9)** | Colour |
|---|---|---|---|---|---|
| 1 | **false** | any | any | **Non scellé** — chain broken/edited, non-opposable | red |
| 2a | true | `SEAL_VERIFIED` · **qualified** TSA | linear **or** (forked **and** attested) | **Scellé · opposable** | green |
| 2b | true | `SEAL_VERIFIED` · **non-qualified** TSA | linear **or** (forked **and** attested) | **Scellé (non qualifié)** — sealed, not legally opposable | green (muted) |
| 3 | true | `SEAL_VERIFIED` (either) | forked **and not** attested | **Intégrité partielle** (+ "divergence non ratifiée") | amber |
| 4 | true | `ABSENT / STALE / UNVERIFIABLE` | any | **Intégrité partielle** | amber |
| 5 | verify not finished | — | — | **Vérification en cours** (no status) | neutral |

Always render beneath: *« Statut attribué uniquement après vérification réussie. »* The **provider
and its qualification are always visible in the badge popover** (Q1 ruling) — a non-qualified seal
never borrows the word "opposable". `SealVerification` therefore carries a `qualified: bool` (from
config `seal_tsa_qualified`, default `false`), and rows 2a/2b are the only place it splits the verdict.

**Recommended (Q3):** opposability requires `content_integrity ∧ SEAL_VERIFIED ∧ (linear ∨
attested)` — row 3 says a **fresh, unratified fork downgrades to partial even with a valid seal**,
because the total order is in dispute and the seal's own job is to surface exactly that. Conservative
and honest; dovetails with R4. Flagged for ratification.

This composes with, and does not replace, the **footer** badge (`app-footer.tsx`, the whole-ledger
tamper/fork state) — the §9 badge is the **TE-01 / État à date opposability** badge. Whether the
footer also gains a seal facet is **Q5**.

---

## 7. What Lot 2 / Lot 3 will build (preview, not this lot)

- **Lot 2 (impl):** `seal.py` (`SealProvider` protocol + `rfc3161` provider + `NoOp` default);
  the off-chrono seal cycle with the continuity/divergence check; `evaluate_seal` folded into
  `active_ledger_tree_status` + `_audit_integrity` (new `seal_*` fields on `AuditIntegrity`); the
  §6 badge on the TE-01 page (**correcting** `etat-a-date.tsx:266` + the printable report `:154`);
  the mandatory sub-mention; config in `settings.py`. Targeted staging, twice-green, ledger, HALT.
- **Lot 3 (test):** (a) **seal unavailable → «Intégrité partielle» proven** (default `none`, and TSA
  unreachable, both → amber, never green); (b) **head sealed, then chain extended → re-seal next
  cycle** (continuity holds, new seal pins the new head); (c) **fork between seals → divergence
  flagged within τ**; (d) **tampered/rewritten sealed head → red alarm**; (e) the honesty invariants
  of §8 as explicit tests.

---

## 8. Honesty guarantees (each is test-enforced in Lot 3)

- **H1 — No config, no green.** Default settings (`provider="none"`) over a *clean linear* chain ⇒
  badge = «Intégrité partielle», never «Scellé». (Structural: `NoOpProvider` cannot mint a token.)
- **H2 — No live verify, no green.** The badge is derived from a live `provider.verify(token)`; a
  token that fails cryptographic verification ⇒ `SEAL_UNVERIFIABLE` ⇒ amber, never green.
- **H3 — Provider down ≠ sealed.** TSA unreachable at seal time ⇒ no entry appended ⇒ amber; no
  placeholder, no optimistic "pending-sealed" green.
- **H4 — Stale ≠ sealed.** A seal older than the staleness budget ⇒ amber (the R4 guarantee lapsed).
- **H5 — The pre-existing over-claim is removed.** `etat-a-date.tsx:266` stops equating
  `reconstructed.verified` with "Scellé"; post-change, with no provider configured, the page shows
  the honest «Intégrité partielle». The e2e test (`etat-a-date.spec.ts:95`, currently asserts
  "Scellé") and the printable report are updated to the honest states, with a **new** test path
  asserting "Scellé · opposable" **only** under a configured+verified seal.

---

## 9. Open questions for the reviewer (ratify at the HALT)

- **Q1 — Provider default & demo TSA.** Confirm `none` as the shipped default (⇒ the deployed demo
  shows «Intégrité partielle» until a TSA is wired). Which TSA for the demo — FreeTSA (free, not
  qualified) as a first cut, or hold for an eIDAS-qualified TSA? On-prem uses a self-hosted
  `openssl ts` CA.
- **Q2 — Seal-token home.** Appended `tessera.ledger.seal` entry (recommended, one chain, head
  moves) **vs** a sidecar `ledger_seals` table (head immovable, second store).
- **Q3 — Fork × seal.** Ratify row 3: a fresh unattested fork downgrades to «Intégrité partielle»
  even with a valid seal.
- **Q4 — Cadence.** τ = 1 h and staleness = 2τ acceptable? (τ is the guaranteed detection bound.)
- **Q5 — Footer scope.** Does the whole-ledger footer badge (`app-footer.tsx`) also gain a seal
  facet, or does the seal stay on the TE-01 / État à date badge only?
- **Q6 — The visible downgrade.** Acknowledge that Lot 2 makes the État à date badge go **green →
  amber** in every un-configured environment (including the current demo) until a real TSA is wired.
  This is the honest state; confirm we accept it rather than keeping the cosmetic green.
- **Q7 — Doc graduation.** Keep this as a companion note, or fold the ratified mechanism back into
  ADR 0015 as a new "§Seal mechanism" subsection?

---

## 9bis. Review rulings (2026-07-08 — *"Hica seal design review"*)

Design **APPROVED**; Lot 2 authorized. Resolutions (each binds Lot 2/3):

- **Q1 → RFC 3161 TSA; `none` default; FreeTSA first cut; eIDAS = the named *production* path.**
  **New §9 nuance:** "**Scellé · opposable**" is **reserved for qualified (eIDAS) TSAs**. A verified
  but **non-qualified** TSA renders "**Scellé (non qualifié)**" — sealed, but not claiming legal
  opposability. **Provider + qualification are always shown in the badge popover.** (See §6 rows
  2a/2b and §5.5 `seal_tsa_qualified`.)
- **Q2 → appended `tessera.ledger.seal` chain entry** (one journal; each seal transitively covers all
  prior ones). §5.2 as written.
- **Q3 → yes** — a fresh, unattested fork ⇒ «Intégrité partielle» even with a valid seal (§6 row 3).
- **Q4 → τ = 1 h, staleness = 2τ as *configurable defaults*;** a stale seal degrades to the honest
  «Intégrité partielle» facet (§5.5, §6 row 4).
- **Q5 → full seal facet on TE-01 / Prouver only.** The global **footer** gains just a **compact
  suffix "· scellé \<t\>"** when a valid seal exists — nothing otherwise (no facet, no partial text
  in the footer).
- **Q6 → yes** — correcting `etat-a-date.tsx`'s over-claim is a **correction, not a regression** (the
  green→amber move has the incident badge as precedent). Accepted.
- **Q7 → keep as a companion note** (this file); do not fold into ADR 0015.

## 10. Non-goals / unchanged (reinforced, not touched)

Ownership, append-only, hash-chaining, "never third-party for the *store*", the serialized writer,
the fork-guard index, the tree-aware verifier, and the attestation pattern are all **unchanged**.
The seal adds a layer **on top**; it gates nothing, blocks no write, and is never load-bearing. If
every seal provider vanished tomorrow, the ledger remains exactly as opposable-internally as it is
today — only the *third-party* opposability enrichment and the bounded-divergence guarantee would be
absent, and the badge would honestly say so.

---

## 11. Lot ledger

| Lot | Scope | Status | Commit | Notes |
|---|---|---|---|---|
| 1 | Design note: mechanism evaluation + wiring + honesty contract; HALT for review | ✅ done | `eab3ad58` | RFC 3161 TSA chosen; C (Object-Lock) & E (self-sign) rejected; badge truth-table + honesty invariants specified. **Reviewed & APPROVED 2026-07-08** — rulings in §9bis (Q1 qualified/non-qualified split; Q5 footer suffix). Docs-only. |
| 2 | Implementation: `seal.py` (`SealProvider`+`rfc3161`+`NoOp`), off-chrono seal cycle w/ continuity+divergence check, `evaluate_seal` composed into tree status + `/audit/integrity`, §6 badge on TE-01 (corrects the over-claim) + footer suffix (Q5), config incl. `seal_tsa_qualified`, mandatory mention | ✅ done (this commit) | — | Backend: `guard/seal.py`, seal-entry builder in `audit.py`, `GuardSettings` seal fields, `AuditIntegrity` seal facet + badge, `etat_a_date` real `opposability` block (drives the honest badge; `verified` no longer a constant). Frontend: `OpposabilityBadge` on TE-01 + printable-report + footer suffix + i18n (en/fr/de) + honest e2e. 27 unit tests (`test_seal.py`). Twice-green: py **1437** ×2 · FE tsc/biome/vitest **78** ×2. |
| 3 | Tests: seal-unavailable → «Intégrité partielle» proven; sealed-then-extended → re-seal next cycle; fork-between-seals → divergence within τ; rewrite → red; honesty invariants H1–H5 | ✅ done (this commit) | — | 4 acceptance scenarios added to `test_seal.py` — end-to-end degradation through `active_ledger_opposability` (NoOp ⇒ `integrite_partielle`; qualified seal ⇒ `scelle_opposable`; non-qualified ⇒ `scelle_non_qualifie`) + the sealed-then-extended re-seal (continuity holds, seal 2 pins the new head, references seal 1). 31 tests total. Twice-green: py **1441** ×2. |

Status legend: ⬜ pending · 🟡 in progress / awaiting review · ✅ done (twice-green) · ⛔ blocked.
