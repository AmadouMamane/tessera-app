# 0048 — Two deployment targets, one image, one witness against divergence

- Status: accepted (code core); the domain attachment is operator-run (see runbook)
- Date: 2026-07-30
- Supersedes: none
- Superseded by: none
- Relates to: [0044](0044-the-agent-runs-as-many-processes.md) (multi-process agent), [0045](0045-full-local-co-locates-the-front-with-the-agent.md) (full-local co-location), [0026](0026-a-witness-interrogates-the-thing.md) (a witness interrogates the thing)

## Context

Two ways to run the cockpit now coexist: **Cloud Run** (the front on GCP, reaching the on-prem
agent across a public tunnel — ADR 0044/0045 context) and **full-local** (the front co-located with
the agent, ADR 0045). The operator wants both reachable at once to compare their performance, one
config to choose which is canonical, and — above all — a guarantee they never silently diverge.

Three facts shape the decision:

- **One hostname resolves to one origin.** "Put the domain on both" is not a comparison, it is a
  flip. Comparing them live needs two distinct hostnames.
- **DNS is at OVH, not Cloudflare.** So each hostname is a record the operator adds at OVH; the
  full-local tunnel is fronted by ngrok (an OVH `CNAME` to the ngrok edge — matching the ngrok the
  operator already runs), and Cloud Run is fronted by a domain mapping (an OVH `CNAME` to
  `ghs.googlehosted.com`). A bare-apex `CNAME` is invalid DNS, so the canonical switch lives on a
  `www` record, never the apex.
- **The divergence risk is the frontend image, not the agent.** The agent is a single on-prem
  process both fronts reach; it cannot diverge from itself. The frontend, though, is built in two
  places today — `make fulllocal-up` runs a local `docker build`, and CI builds and pushes a
  separate image for Cloud Run. Two builds are two chances for the two live fronts to be running
  different code while everyone assumes they match.

## Decision

**Both targets run the same SHA-tagged frontend image, declared in one tracked config, and a witness
interrogates the two live fronts and refuses when their served SHAs differ.**

1. **One image, pulled by both.** The frontend image is built once from
   `infra/docker/Dockerfile.frontend` and tagged by commit SHA. CI already builds and pushes
   `tessera-frontend:<sha>`; the build now **bakes that SHA into the image** (`ARG TESSERA_BUILD_SHA`
   → `ENV`), so the running container carries its own provenance rather than a runtime label anyone
   can override. Full-local stops building locally when `TESSERA_FRONTEND_IMAGE` is set: it **pulls
   the same registry tag Cloud Run runs**. Same bytes in both places — divergence becomes impossible
   by construction, not merely detectable.

2. **One config, the source of truth.** `infra/deploy/targets.yaml` declares the apex `domain`, the
   pinned `image`, which target is `primary` (the canonical `www` switch), and per target its
   `subdomain`, how its front is exposed, and the `agent_url` it uses. Choosing which environment is
   canonical is editing one field. Secrets never live here — only non-secret wiring.

3. **One witness against divergence.** The frontend serves `GET /api/version` returning the SHA
   baked into its image. `scripts/deploy_diff.py` (via `make deploy-diff`) fetches that from every
   target's live host and **exits by verdict**: `0` the SHAs match, `1` they diverge (named), `2` it
   is blind — a host unreachable or the domain unset (ADR 0026: a witness that cannot see may never
   report "ok"). This turns "don't let them diverge" from a hope into a machine verdict that a gate
   or a cron can run.

### What is code, and what is the operator's

Everything in (1)–(3) is tracked, reviewed, and gated. The **domain attachment is not code and not
mine to do**: creating the ngrok custom domain, the Cloud Run domain mapping, and the OVH `CNAME`
records requires the operator's credentials, consoles, and DNS. The exact OVH-specific steps —
including which record points where and where the `www` switch lives — are in
`docs/runbook-two-targets.md`. Publishing on the domain (the flip) stays a deliberate operator act,
exactly as ADR 0045 made `make fulllocal-tunnel` gated.

## Consequences

- Full-local gains a dependency when run in parity mode: it needs registry read access to pull the
  pinned image (`gcloud auth configure-docker`). Unset `TESSERA_FRONTEND_IMAGE` keeps the old
  local-build path for development — the parity guarantee holds only in pull mode, and the witness
  makes that visible (an un-stamped local build reports `sha=dev`, which `deploy-diff` treats as a
  divergence against a real SHA, not a match).
- The witness can only compare what is live. Before the operator attaches the domains it reports
  `CannotSay` (exit 2), by design — it never fabricates a green from an unreachable host.
- `/api/version` is public and aggregate (a build SHA, a build time, a target label). It carries no
  subject data and no secret; it is the same posture as the launcher signal (ADR 0009).
- This does not itself deploy anything or touch DNS. It makes the two-target topology declarable,
  the images identical, and the divergence checkable — the operator performs the attachment once,
  then `make deploy-diff` keeps them honest.
