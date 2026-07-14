# The observability stack refuses default credentials (F-9, one storey up)

**Branch:** `claude/obs-stack-refuses-default-credentials`, cut from `main` @ `d7ee40d7`.
**Date:** 2026-07-14. **Author:** Claude (session `98821e86…`), on Amadou's instruction.

## The finding the review dropped

`docker-compose.obs.claude.yml` brings up the LLM-observability plane — Langfuse, ClickHouse,
MinIO, Redis, Grafana. **Langfuse holds the LLM traces, and the LLM traces are customer
conversations.** Until this branch, every credential in that file was a literal, readable on
GitHub:

| service | old literal | what it guards |
|---|---|---|
| Langfuse login | `claude@tessera.local` / `claude-demo-pw` | the transcript UI |
| ClickHouse | `clickhouse` / `clickhouse` | where the transcripts are STORED |
| MinIO | `minio` / `miniosecret` | uploaded trace payloads |
| Langfuse `ENCRYPTION_KEY` | sixty-four `0`s | field-level encryption of the traces |
| Redis | `claude-redis` | the queue |
| Grafana | `${GF_ADMIN_PASSWORD:-changeme}` | the ops dashboards |
| NextAuth | `claude-nextauth-secret` | Langfuse session signing |

And every port was published as `"3900:3000"` — a bare mapping Docker binds to **`0.0.0.0`, every
interface**, not loopback. So the question is never *"is this production?"*; it is **"can a stranger
reach it?"**, and the answer was **yes, by default**. This is **F-9** verbatim — "default accounts
stay valid when the env vars are missing" — closed in the app (`webapp/frontend/lib/auth/`), and
left wide open in the plane that holds the transcripts.

The most dangerous line was not a password. It was `${GF_ADMIN_PASSWORD:-changeme}` sitting under a
comment that read **"No hardcoded credential in the repo."** `changeme` *is* a hardcoded credential,
and a false assurance is worse than the hole it denies, because it stops the next reader from
looking.

## ⚠ THE VULNERABLE STACK IS LIVE RIGHT NOW — an operational action is owed, and it is Amadou's

The fix below secures the *next* `make obs-up`. It does **not** touch the containers already
running. On 2026-07-14, on this host, the old stack was **up 5 days** and reachable **off-loopback**:

```
tessera-claude-langfuse     0.0.0.0:3900->3000    GET http://192.168.1.19:3900/…  -> HTTP 200
tessera-claude-clickhouse   0.0.0.0:18123->8123   GET http://192.168.1.19:18123/ping -> HTTP 200
tessera-claude-langfuse-db  0.0.0.0:55433->5432
tessera-claude-minio        0.0.0.0:19100/19101
tessera-claude-grafana      0.0.0.0:13000   (GF_AUTH_ANONYMOUS_ENABLED=true — no login at all)
```

`192.168.1.19` is this Mac's LAN address (`en1`), not localhost. Anyone on that network segment
could open the Langfuse UI and reach ClickHouse. The Langfuse login endpoint answered the demo
credentials with an HTTP 302 (the NextAuth flow ran; I did **not** follow the session or read any
transcript — confirming the door is open does not require walking through it).

**Recommended, and left for the operator to run — it stops a running service, so it is not mine to
execute:**

```
make obs-down                 # stop the exposed stack
make obs-secrets              # generate random creds into gitignored .env.obs.local
make obs-up                   # brings it back loopback-only, on real credentials
```

## The fix — two witnesses, because a stranger only needs one gap

1. **The compose file itself.** Every credential is now `${VAR:?message}` — Compose's MANDATORY
   form: unset ⇒ Compose *refuses to start* and names the missing variable. Proven by running
   `docker compose -f … config` **directly, no `make`**, with no credentials: exit 1,
   `required variable TESSERA_OBS_REDIS_PASSWORD is missing`. A stranger who bypasses the Makefile
   entirely is still refused **by the thing**. Every published port is now
   `"${TESSERA_OBS_BIND:-127.0.0.1}:host:container"` — loopback by default (13 of 13 ports;
   `config` confirms 0 bound to `0.0.0.0`). A bind address is not a credential, so it may keep a
   default — the *safe* one; reaching the network is now a declared act (`TESSERA_OBS_BIND=0.0.0.0`).

2. **The `make obs-guard` recipe**, a prerequisite of `obs-up` and `obs-up-core`. It refuses with a
   verdict — `[NOT OK]`, the twelve unset variables named, `make obs-secrets` as the remedy, and
   *why it matters* ("the LLM traces are customer conversations") — and exits 2 before Docker is
   ever reached. It does **not** depend on `obs-secrets`: a guard that generates the credentials it
   demands is F-14 (a check that repairs its own condition checks nothing). The escape hatch,
   `make obs-secrets`, writes **random** creds (`openssl rand`, `umask 077`) into a gitignored
   `.env.obs.local` — it removes the typing, never the security, so dev/CI lose nothing.

## The ratchet — `tests/unit/test_obs_stack_has_no_default_credentials.py`, mutation-tested

Interrogates the parsed compose document and the real `make` recipe, never a grep of the text:

* every credential KEY is `${VAR:?…}`, no default reachable, no inline password in a URL;
* the 8 literals of 2026-07-13 never come back — asserted over **tokenised values**, after the
  substring form flared red on `container_name: tessera-claude-redis` (the `39b`-as-`39` bug, inside
  the ratchet built to police it);
* no port publishes without an explicit loopback default; at least one port exists (the control);
* `obs-up`/`obs-up-core` depend on `obs-guard`; `obs-guard` does **not** depend on `obs-secrets`;
* `.env.obs.local` is gitignored — asked of `git check-ignore`, not of the `.gitignore` text;
* **the mutation:** `make obs-guard` with every `TESSERA_OBS_*` stripped from the environment →
  exit 2 naming `TESSERA_OBS_CLICKHOUSE_PASSWORD` and `make obs-secrets`; with all 12 set → exit 0;
  with 11 of 12 → exit 2 naming the one gap. Registered in the exit-witness registry
  (`obs-guard: VERDICT`, `obs-secrets: action`).

Two defects were found and fixed **in my own guard** while building it, both the house disease:
* `docker compose --env-file <missing>` exits 1 even when the vars are exported — so the flag is now
  passed only when the file exists (`OBS_ENV_ARG`), or the guard would advertise a road ("or export
  them yourself") it then blocks;
* the guard sourced `"./$(OBS_ENV_FILE)"`, breaking on an absolute path, and never said what file it
  read; it now normalises the path and prints `Looked at: the environment, and <file> (ABSENT)`.

## detect-secrets

Green **having looked**: whole-tree `detect-secrets-hook --baseline .secrets.baseline` exits 0 with
the baseline staged; a planted AWS key makes it exit 1 naming the file and `AWS Access Key`. The
baseline lost the 8 detections for the deleted compose literals (492 → 484; 57 → 49 human verdicts),
and gained detect-secrets' standard `is_baseline_file` self-exclusion filter — no surviving
detection lost its verdict. The one new detection (the dead base64 header in the ratchet's
banned-list) carries an inline `pragma: allowlist secret`, detect-secrets' declared mechanism for a
credential written out on purpose.

## Recorded, NOT fixed (not this lot)

`infra/terraform/postgres.tf:91` carries `postgresql+asyncpg://` — the SQLAlchemy dialect scheme
that **psycopg rejects at connect time**. It is one of the 6 fatal GCP defects of the 360 audit; a
deploy built on it 503s on the first query. Confirmed in passing, left for its own branch.
