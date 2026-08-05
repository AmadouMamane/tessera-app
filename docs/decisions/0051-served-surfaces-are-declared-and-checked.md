# 0051 — Every repo surface declares how it reaches the running stack, and a witness checks it

- Status: **accepted** (2026-08-06)
- Date: 2026-08-06
- Deciders: Tessera maintainers
- Related: 0043 (cutover container-input preflight), 0045 (full-local co-locates the front with
  the agent), 0048 (two deployment targets share one image — `/api/version`, `make deploy-diff`),
  0026 (a witness interrogates the thing, never its neighbourhood),
  `infra/deploy/served-surfaces.yaml`, `scripts/served_check.py`,
  `tests/unit/test_served_surfaces_manifest.py`

## Context

Landing a commit on `main` does not change what the deployed stack serves. That much is obvious.
What is not obvious, and what has cost this project real time, is that landing **does not fail to
change it uniformly** either.

Some paths are copied into an image at build time and stay frozen at the commit that built it:
`src/`, `eval/` (the failure catalogue, the eval sets, the **baselines**, the grader), the whole
Next.js app. Others are bind-mounted from the working tree and move the instant the file changes
on disk: `eval/reports`, the Prometheus and Grafana and OTel-collector configs.

Land a change touching both and the served stack becomes a **chimera** — old code reading new
data — with nothing on any surface saying so. This is not hypothetical:

- A re-grade landed without a rebuild put the deployed cockpit into `CannotSay`. Fresh reports
  arrived through the mount; the grader and baselines that score them stayed frozen in the image.
  The stack was wrong in a way that looked exactly like an honest refusal.
- ADR 0048 already gave every host a build stamp and `make deploy-diff` to compare them. But
  deploy-diff asks whether the two targets agree **with each other**, and two hosts three commits
  stale agree perfectly. It compares neighbours. That is ADR 0026's failure shape, in the very
  tooling built to prevent divergence.
- `make fulllocal-status` reported `healthy`, which answers whether the container is *up* — never
  whether it runs *this* commit.

The knowledge of which path is baked and which is mounted existed only in the Dockerfiles, the
compose overlays, and whoever last read them. That is exactly the kind of load-bearing knowledge
this repository has agreed to write down and then verify.

## Decision

**Every repo surface declares how it reaches the running stack, in one manifest, and a witness
checks both the manifest and the stack.**

### 1. The manifest — `infra/deploy/served-surfaces.yaml`

One entry per path prefix, each with a `medium` and a `why`:

- `baked` — copied into an image. Frozen at build time; a change is invisible until the image is
  rebuilt **and** the container recreated.
- `mounted` — bind-mounted from the working tree. Live immediately (or at the next container
  restart for config read once at boot). No rebuild needed — and none *possible*: rebuilding does
  not change what is served here.
- `absent` — in no served image or mount. Changing it cannot affect the running stack.

Longest matching prefix wins, which is what lets `eval/reports/` (mounted) sit correctly inside
`eval/` (baked) instead of fighting it. That pair *is* the chimera, so the manifest must be able
to express it.

**The default for an unlisted path is `baked`.** The safe answer to "I do not recognise this
file" is "assume the stack must be rebuilt", never "assume it does not matter". `absent` entries
are therefore written one by one with a reason each, never by wildcard: `absent` is the claim
*"changing this cannot affect what runs"*, and a wrong one silences the check.

### 2. The witness — `make served-check`

It asks the running stack which commit it serves (`/api/version`, ADR 0048's stamp), diffs that
commit against `HEAD` **as two trees rather than as a range** (what matters is whether the bytes
differ, not whether one commit descends from the other — a rolled-back stack must not read as a
match), classifies every changed path through the manifest, and answers by exit code:

- `0` — the stack serves this commit, or the only changes since reach no served surface.
- `1` — REFUSED. `STALE` (baked code changed), `DRIFTED` (mounted data changed under an older
  image), or `CHIMERA` (both — old code reading new data *right now*).
- `2` — blind: nothing serving, the stack cannot name its commit (`dev`, `unverified:…`), or it
  was built from a dirty tree, in which case it contains a working tree rather than a commit and
  there is nothing to diff. A witness that cannot see may never report "ok" (ADR 0026).

It also reports uncommitted files touching served surfaces: a green verdict computed over a tree
with uncommitted served code is only half a verdict.

`make fulllocal-status` prints the verdict (non-gating — the exit code belongs to
`served-check`), so the status an operator reads every day can no longer say `healthy` over a
stack that is three commits stale.

### 3. The manifest is checked against the build files

A manifest nobody verifies is a declaration, and this repository does not take declarations for
facts. `tests/unit/test_served_surfaces_manifest.py` reads the Dockerfiles and the compose files
themselves and asserts that every `COPY` lands under a `baked` path, every repo-relative bind
mount under a `mounted` one, and that nothing claimed `mounted` is actually unmounted. Each
detector is tested before it is trusted, because "no findings" and "the pattern stopped matching"
are otherwise the same sentence.

This is the assertion that closes the class: add `COPY config ./config` to a Dockerfile without
touching the manifest, and without this test `served-check` would keep classifying every change
under `config/` as harmless — reporting "no rebuild needed" about baked code, confidently.

## Consequences

- "Do I need to rebuild?" becomes a machine verdict instead of a memory. That question was
  previously answered by whoever remembered the compose layout.
- The chimera state has a name and an exit code. Previously it had neither, and presented as an
  honest-looking `CannotSay` on the deployed cockpit.
- The manifest is a maintenance surface: adding a `COPY` or a bind mount now requires an entry,
  enforced by the gate. That cost is the point — it is what keeps the check from going stale.
- `served-check` is **not** in `make gate`. The gate runs against a checkout, not a deployment;
  a check that needs a live stack would be permanently blind there, and a permanently-blind check
  in a gate teaches people to ignore exit codes. The manifest *test* is in the gate; the stack
  question is asked where a stack exists.
- It does not verify image **digests**, only the commit each host reports. Two hosts can serve the
  same SHA from different builds. ADR 0048 already made that trade explicitly, and this ADR
  inherits it rather than reopening it.

## Alternatives considered

- **Rebuild on every land.** Correct and far too slow: most commits touch nothing served, and a
  rebuild that is always required is a rebuild nobody waits for.
- **Mount everything.** Removes the chimera by removing the baking — and with it the reproducible
  image that ADR 0048's whole two-target parity story rests on.
- **Bake everything.** `eval/reports` is per-environment host state, generated per run. Baking it
  would mean rebuilding the image to publish a report.
- **Infer the classification from the Dockerfiles at runtime instead of a manifest.** Tempting,
  and it would need no maintenance. Rejected because a `COPY` tells you a path is baked but never
  tells you a path is *deliberately* absent, and `why` is the field that makes the file reviewable.
  The test gets the inference anyway, and uses it to police the declaration.
