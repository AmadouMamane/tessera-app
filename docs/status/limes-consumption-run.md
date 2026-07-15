# Run status — phase 2: Tessera consumes limes (ADR 0029)

Branch `claude/phase2-tessera-consumes-limes`, cut from `main` `eb9259b8`. **HALTs before merge**
(packaging decision is Amadou's — see ADR 0029 §HALT). Single source of truth for this lot.

## What shipped

| Piece | State | Where |
|---|---|---|
| `limes` added as one-way path dependency (`Tessera → limes`, editable) | ✅ | `pyproject.toml` (`dependencies` + `[tool.uv.sources]`) |
| limes injection backend behind the guard seam | ✅ | `src/tessera/guard/limes_backend.py` (new) |
| `check_user_input` delegates injection detection to limes; `CannotSay` → block (fail-closed) | ✅ | `src/tessera/guard/adapter.py` |
| Single source of truth: YAML `deny_patterns` empty + **load refuses re-adds**; field derived from limes | ✅ | `src/tessera/guard/decisions.py`, `guard/policy.yaml` |
| RAG-poison scanner sources limes' patterns (raw snippet kept, limes redacts) | ✅ | `src/tessera/observability/corpus_injection.py` |
| Badge greens only on a **dated limes F1** (detector identity + `observed_at`) | ✅ | `firewall_efficacy.py`, `system_profile.py` |
| Ratchet + mutation + badge fail-closed tests | ✅ | `tests/unit/test_guard_limes_injection.py` (new) |
| Guard tests repointed to the single source | ✅ | `tests/unit/test_guard.py`, `tests/unit/test_system_profile.py` |
| ADR 0029, this status note, README repositioning | ✅ | `docs/decisions/0029-*`, here, `README.md` |

## The number (case 08, real Tessera path via `check_user_input`)

```
AVANT (limes debranche = regex Tessera d'origine, = main):
  08|fr: allowed=True  -> OBEI (trou ouvert)
  08|de: allowed=True  -> OBEI (trou ouvert)
  08|en: allowed=True  -> OBEI (trou ouvert)

APRES (limes branche = detecteur complet):
  08|fr: allowed=False -> DETECTE et REFUSE [injection.limes.deny]
  08|de: allowed=False -> DETECTE et REFUSE [injection.limes.deny]
  08|en: allowed=False -> DETECTE et REFUSE [injection.limes.deny]
```

Efficacy on the real path: **25/33 blocked, 0/8 false positives, precision 1.00, recall 0.76,
F1 0.86**, detector `injection@0.1.0` — identical to limes isolation. Legitimate turns pass.

## Non-regression

- First-party guards untouched: allowlist, auth-floor, language/argument checks, exfiltration,
  third-party-PII, output redaction. The `TestInjectionDenyFloor` benign/attack floor and the
  guarded-invoke tests pass unchanged.
- 148 tests across every `prompt_injection_deny` consumer (display counts, trajectory,
  guard-retraction, RAG scan, signal catalogue, parameters, état-à-date, policies, fleet, garde-fous)
  pass with the derived-from-limes field — cockpit counts now show limes' 25 rules, not a stale 22
  or a false 0.

## Gate

- `mypy` clean on all changed source files; `ruff check` + `ruff format --check` clean.
- **Full `make gate-twice`**: see the git trailer of the lot commit for the recorded tree digests.
- CI remains billing-blocked → the local gate is the only witness (repo doctrine).

## Owed / open (for Amadou)

1. **Packaging (HALT, blocks merge).** The local path `../../../limes` is correct from the agent
   worktree (depth 3) but wrong from the reference checkout `tessera/` (depth 2, needs `../../limes`);
   an absolute path hardcodes the home dir. Decision: vendor / submodule / wait-for-PyPI (ADR 0029 §HALT).
2. **Fail-closed operational note.** limes absent ⇒ every turn refused (correct security, dead app).
   limes must be a hard runtime dep of any deploy, not an optional extra.
