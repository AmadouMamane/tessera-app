# The product database no longer answers the LAN by default (F-9, at the base compose)

**Branch:** `claude/bind-loopback-dev-stack`, cut from `main` @ `ae61af21`.
**Date:** 2026-07-15. **Author:** Claude (session `330599a3…`), on Amadou's instruction.

## The finding, verified live before touching anything

```
tessera-postgres   0.0.0.0:5432->5432   Up 5 days   ← audit ledger, transcripts, GDPR memory
tessera-redis      0.0.0.0:6379->6379   Up 5 days
nc -zv 192.168.1.19 5432  → succeeded    (192.168.1.19 = this Mac's own LAN address, en1)
nc -zv 192.168.1.19 6379  → succeeded
```

Credentials for that Postgres are published in this repository (`tessera`/`tessera`), and the
macOS application firewall does not police Docker's port publishing. So the PRODUCT database —
`tessera_local.audit_ledger`, `conversation_messages`, `long_term_memory`, 19 user tables — was
readable by any host on the network segment. **F-9 for the third time, one file over each time**:
closed in the app, closed in the obs plane on 2026-07-14, still open at the base compose —
because each fix's witness stopped at the file it was written for.

## What the container labels taught us (and why fixing the repo alone would have closed nothing)

The leaking containers were **not created by this repository's compose**. Their labels say:

```
project=tessera   workdir=/Users/amadou/local/apps/tessera   ← the ARCHIVED pre-umbrella checkout
created 2026-05-28 (postgres) / 2026-06-07 (redis)
```

This repo's `docker-compose.yml` names its containers `tessera-local-*` (ADR 0014 env
isolation) and does not even define a `redis` service. Editing the repo re-binds the **next**
`docker compose up`; the **running** leak belonged to a compose project whose source file no
longer exists on disk. Two different acts, both owed — the operator gesture closes the live hole,
the ratchet keeps it closed. One without the other is either a leak that returns at the next
compose file, or a leak that stays open until a merge.

## The operator gesture — done, in this run, and proven

Recreated both containers by *adopting* the legacy `tessera` compose project with a minimal
compose file (same images, same volumes — declared `external`, data untouched — same network,
same names; the ONLY diff is the bind). Full pre-change `docker inspect` snapshot kept in the
session scratchpad (`legacy-containers-inspect-before-rebind.json`).

```
tessera-postgres   127.0.0.1:5432->5432   (healthy)
tessera-redis      127.0.0.1:6379->6379
nc -zv 192.168.1.19 5432 → Connection refused     nc -zv 127.0.0.1 5432 → succeeded
nc -zv 192.168.1.19 6379 → Connection refused     nc -zv 127.0.0.1 6379 → succeeded
psql: 19 user tables intact (audit_ledger, conversation_messages, long_term_memory, …)
backend :8099 /healthz → 200      frontend :3097 /api/healthz → 200   (after the recreate)
```

The untouched orphans of that legacy project (`tessera-agent-1`, `tessera-langfuse`, …) are
stopped containers; they publish nothing.

## The code fix

`docker-compose.yml` publishes the datastore as `"${TESSERA_BIND:-127.0.0.1}:…"` — loopback by
default, exactly the obs stack's pattern (`TESSERA_OBS_BIND`). Publishing to the network stays
possible, but only as a deliberate, declared act: `TESSERA_BIND=0.0.0.0 docker compose up`.
Docker itself was made to render the result (`docker compose config` → `host_ip: 127.0.0.1`) —
the witness is the real tool, not my reading of it.

## The ratchet — `tests/unit/test_compose_datastores_bind_loopback.py`

Reads the **repository**, not a file: every `docker-compose*.yml` (the glob may find more files
than today's four; a sentinel refuses fewer), every service whose `image:` names a datastore,
every published port must carry a **statically resolvable loopback default**. `${VAR:-127.0.0.1}`
passes; a bare `"5432:5432"`, `0.0.0.0`, `${VAR}` and `${VAR:?}` (no static default — the file's
posture would depend on the invoker's shell) are all RED. An unknown YAML tag or unparseable
entry is a RED, not a skip (ADR 0026: a witness that cannot see may never say "ok").
`_FROZEN_EXCEPTIONS` is **empty** and may only shrink — a dedicated test forces deletion of any
entry whose hole is closed.

App/edge services are out of scope on purpose and the docstring says so: the gateway's PURPOSE
is to be reached (ADR 0020); the datastores are where the customer data sits.

The obs stack is asserted to sit **inside this same ratchet's field of view**
(`test_the_obs_stack_is_policed_by_this_same_ratchet`), so the 2026-07-14 correction and this
one cannot diverge. The stricter obs-only contract
(`test_obs_stack_has_no_default_credentials.py` — all ports, credentials, guard) stays as is.

**Mutation-tested against the live tree, both files** (then restored; work committed first):

```
docker-compose.yml       → '${TESSERA_PG_PORT:-5432}:5432'          → exit 1, offender named
docker-compose.obs.…yml  → '${TESSERA_OBS_BIND:-0.0.0.0}:16379:…'   → exit 1, offender named
```

plus the permanent self-test half: ten leaking shapes and six loopback shapes fed through the
real collection path on synthetic documents, every run.

## What still answers 0.0.0.0 — operator debt, NOT this repo

```
tessera-observability-refinement-llmops-langfuse-1   0.0.0.0:3081->3000   Up 5 days
tessera-observability-refinement-llmops-minio-1      0.0.0.0:9012/9011    Up 5 days
```

That stack's compose lives in `~/local/apps/codex/tessera-observability-refinement/` — a
different repository; no lot here can close it. Amadou dismantles it by hand:

```zsh
cd ~/local/apps/codex/tessera-observability-refinement
docker compose -f docker-compose.yml -f docker-compose.unix.yml \
  -f docker-compose.observability.yml -f docker-compose.llmops.yml down
```

Also owed to the operator, non-urgent: `tessera-redis` is legacy — this repo defines no redis
service. If nothing speaks to it, the honest close is `docker stop tessera-redis`, not a bind.
And `tessera-claude-langfuse` still crash-loops on the pre-rotation volume password (known,
not an exposure — it is a container that does not start).
