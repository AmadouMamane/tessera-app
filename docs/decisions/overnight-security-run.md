# Overnight security-remediation run — 2026-07-11

Remediation of the 2026-07-10 code audit (`Tessera_private/artifacts/tessera-audit-2026-07-10.html`,
6 P0 + ~60 findings; structure in `audit-code-2026-07-10.md`). Base: `origin/main` = `60ec9d99`.

Two lanes, decided before the run:

- **Lane A — safe corrections.** Either no behaviour change, or a bug with a single
  unambiguous fix. ONE `make gate` pass per lot, autonomous merge to `main`.
- **Lane B — the security seam.** The four P0s that change who is allowed to do what.
  Branch `claude/security-seam`, **twice-green local**, then **HALT — no merge**. Reviewed
  by Claude, then Amadou gives the go.

**Protocol note — the safety net is gone.** GitHub Actions is billing/quota-blocked, so
"CI is the second pass" does not hold tonight. There is no independent witness. Lane A
therefore takes one full local gate per lot; Lane B takes two consecutive full local
passes, which is the only guard rail it has.

---

## MORNING SUMMARY

*(kept at the top; updated as the run proceeds)*

### Landed on `main` (lane A)

| Lot | What | Hash |
|---|---|---|
| A0 | `main` was **red at the gate** — repaired before anything else | `a56bb287` |
| A1 | P0 — dunning letters asserted a payment promise the file never recorded | `749bf9cb` |

### Waiting for review (lane B)

*(nothing yet)*

### What needs Amadou

1. **`main` was red at the gate when the run opened** (see A0). A lint error
   (`scripts/ledger_restore_drill.py:108`, E501) sat on `main` from the ledger backup+drill
   lot in the 2026-07-10 audit window. That lot landed while Actions was billing-blocked, so
   no independent witness ran. This is precisely the failure the "CI = second pass" net used
   to catch, and it is the second consecutive night in which its absence has cost something.
   **Restoring GitHub Actions billing is now the single highest-leverage repo action.**

---

## Lot log

### A0 — `main` was red at the gate (`a56bb287`)

Not in the mission brief. Found while running the first lot's gate: `ruff check .` — which is
exactly what `make gate` runs — failed on `origin/main` at `scripts/ledger_restore_drill.py:108`
(E501, 101 chars, a comment). Comment-only reflow, no behaviour change.

Landed **first and alone**, because every subsequent lot would otherwise have inherited a red
gate and any "green" claim I made about them would have been false.

### A1 — the fabricated promise date (`749bf9cb`)

**Audit**: P0 `fabricated-regulated-output`, `recouvrement/message_templates.py:56, :76, :95`.

Three *approved* dunning templates hardcoded the sentence *"Votre promesse de paiement du
12 juin n'a pas pu être tenue"*. Only `{days_late}` was a field. Every letter Crédit Aurore
drafted therefore asserted a specific broken payment promise that was **never read from the
case file** — a fabricated financial claim inside a regulated artifact.

The witness, rendering the pre-fix template against a case that records no promise at all:

```
Bonjour Mme R.,
Nous vous contactons au sujet du dossier RC-9001. Sauf erreur de notre part,
le montant restant dû est de 1 240,00 €.

Votre promesse de paiement du 12 juin n'a pas pu être tenue et le dossier
présente un retard de 17 jours.
```

Mme R. never promised anything. The letter says she broke a promise on 12 June.

**Fix.** The date is sourced from the dossier, and the clause is *omitted* when the dossier
carries no promise — never defaulted:

- `RecouvrementCaseSnapshot.missed_promise: str` (free prose — which is *how* the template
  drifted from the data) becomes `missed_promise_date: date | None`, the single source of
  truth. `missed_promise_label` derives from it and is `None` when absent, so **no surface**
  can assert a promise the file does not carry.
- `render_missed_promise_clause(date | None)` returns `""` for `None`. The lateness sentence
  is real case data and survives the omission.
- The five other surfaces that echoed the prose (context items, priority reasons, the summary
  sentence, three slot dicts) now drop the fragment rather than emit an empty one.
- Month names are spelled out rather than taken from `strftime`: a regulated letter must not
  depend on the container's locale database.

**Non-regression**: RC-2048 (the only case on file, which *did* promise on 12 June) renders
identically — `test_recouvrement_graph_v1.py:274` passes untouched.

**Closure tests** (`tests/unit/test_recouvrement_message_templates.py`, 17 cases). Each fails
against the pre-fix templates, which had no way to express "no promise": a letter for a case
without a promise never contains "promesse de paiement"; a letter for a case that promised on
3 May says *3 mai*, not *12 juin*.
