# Contributing

Tessera is developed by a single maintainer under a hard scope discipline (ship-or-die: if
schedule slips, scope is cut, never time extended). Issues and pull requests are welcome —
please read this page before opening one.

## Before any code: the CLA (non-negotiable)

Tessera is licensed [AGPL-3.0-only](./LICENSE) and keeps a commercial dual-licensing option
open ([ADR 0057](./docs/decisions/0057-license-agpl-3-0-only.md)). That option survives only
while every line in the repository can be relicensed by the project owner, so **no external
contribution is merged without a signed [Contributor License Agreement](./CLA.md)**. This is
not bureaucracy: one unsigned patch forecloses dual licensing permanently (ADR 0028 §"What
this does not decide", made binding by ADR 0057).

To sign: follow "How to sign" at the end of [`CLA.md`](./CLA.md) — your first pull request
adds your line to its signatories table, in the same PR as your contribution or an earlier
one. You keep the copyright on your work.

## How to contribute

- **Bugs and ideas** — open an issue using the matching template under
  `.github/ISSUE_TEMPLATE/`.
- **Code** — fork, branch from `main` (`kebab/short-purpose`), follow the conventions below,
  open a pull request against `main` using the template in
  `.github/PULL_REQUEST_TEMPLATE.md`.

## Conventions (the gate enforces them)

- Python 3.12; dependencies via `uv` exclusively — no `pip`, no `poetry`, no
  `requirements.txt`.
- `ruff check` + `ruff format --check` and `mypy --strict` must pass; tests via `pytest`
  (`-m "not integration"` is the fast loop). Frontend: `tsc --noEmit` + `biome check`.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, …).
- Prompts live in YAML under `src/tessera/agent/prompts/`, never hardcoded in Python.
  Policies live in YAML under `src/tessera/guard/`. Secrets never enter the repository.
- The canonical repository layout is binding (`CLAUDE.md`); a structural change needs an ADR
  under `docs/decisions/` first.
- Every external citation must point to a verified, reachable source. No notebooks, ever.

Run the whole gate locally with `make gate` before pushing.
