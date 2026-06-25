# 0014 — Environment isolation (prod / staging / dev as one knob that isolates)

- Status: **proposed** (2026-06-25) — model and audit decided; isolation layers
  to land per-layer (config → compose → tagged data → UI), nothing pushed.
- Date: 2026-06-25
- Deciders: Tessera maintainers
- Branch: `feature/redesign`
- Related: 0008 (security hardening), 0009 (dashboard auth/RBAC), 0010 (frontier
  observability), 0011 (as-of T — env is the *spatial* sibling of T's temporal
  dimension), `src/tessera/settings.py` (the single source of `environment`).
- Coordination: a parallel workstream owns the **header chrome** that *displays*
  the environment (read-only badge `Prod · Llama 3.2 3B · sur site`, promoted to
  a global switcher only when a real per-env dataset exists). This ADR owns the
  **dimension behind that badge** — the data must be real and partitioned before
  the chrome can honestly read it. The UI is the *last* layer here, not the first.

## Context

`environment` (`local | ci | staging | production`, `settings.py:53`) exists as
an enum and is surfaced in a handful of cockpit spots (`agent_configurations`
"Environnement", `signal_catalogue` context row, `system_profile`). **It is
purely cosmetic.** It changes no database, schema, table, directory, container
name, port, or per-record tag. Two backends with different `TESSERA_ENVIRONMENT`
pointed at the same Postgres share *all* state silently.

This is the real, daily problem the project hits: **a local dev process and the
deployed-style stack step on each other** because nothing isolates them. The UI
question ("badge vs dropdown") is downstream — there is no real per-env data to
switch between yet, so a dropdown would be *fabrication*. We fix the substrate
first, then let the header read a real dimension; an env with no data renders
honest-empty.

### Audit — where dev and prod share state today (the collision source)

Verified on `feature/redesign`, 2026-06-25:

1. **Postgres is a single namespace.** `PostgresSettings` defaults to
   `postgresql://tessera:tessera@localhost:5432/tessera`, one database, the
   `public` schema, one `vector_table = documents`. `.env.local` sets no
   override, so the **dev host backend (:8392)** and the base `docker-compose.yml`
   `agent` both resolve to `localhost:5432/tessera` — same DB, same schema, same
   tables, regardless of each process's `TESSERA_ENVIRONMENT`. Every durable
   store (transcript, eval bundles/scores, memory, lineage, settings, retrieval
   counters) lands in that one schema. **This is the primary collision.**
2. **`eval/reports/` is one flat repo directory.** Report filenames are
   `<timestamp>Z_<lang>.json` with **no env tag**. Every backend — host dev,
   composed agent — reads the same directory, so the cockpit's aggregates
   (`eval_data.py`, `eval/runs.py`, `eval/datasets.py`, judges) **mix runs from
   every environment**. A dev eval run pollutes the numbers a "prod" view shows.
3. **Container names and ports are isolated only by manual compose project
   name, not by env.** `docker-compose.yml` hardcodes `tessera-postgres`,
   `5432:5432`, `8099:8080`, `3090:3000` whatever `TESSERA_ENVIRONMENT` says.
   Isolation today is an accident of running prod under a *different compose
   project* (`tessera-observability-refinement`, its own network + unpublished
   internal `postgres`), not a property of the env knob.
4. **No record is tagged with its env.** Nothing in the durable schema carries
   an `environment` column, so even a shared DB cannot be *filtered* back into
   per-env views. Isolation cannot be retrofitted by query alone.

Net: `environment` is a label, not a partition. Co-resident processes collide on
(1) the Postgres schema and (2) `eval/reports/`; (3) and (4) mean the collision
can neither be prevented by the knob nor untangled after the fact.

## Decision

`TESSERA_ENVIRONMENT` becomes **one knob that isolates everything and tags every
record**, read from the existing single source (`get_settings().environment`).
No new source of truth; the enum stays `local | ci | staging | production`.

### Model

- **Per-env Postgres namespace.** Each env gets its own schema (default map:
  `production → public`, others → `tessera_<env>`), applied via the connection
  `search_path` at pool creation. `production → public` is deliberate so the
  **already-running deployed stack keeps its data untouched** when this lands;
  only non-prod envs move into fresh schemas. (A distinct *database* per env is
  the stronger form and stays open for the deployed tier; schema-per-env is the
  pragmatic local isolation that lets dev + prod run on one Postgres without
  touching each other.)
- **Per-env report tree.** `eval/reports/<env>/` replaces the flat dir. Readers
  fall back to the flat dir when `<env>/` is absent so existing archives stay
  visible (honest, not destructive) until re-homed.
- **Per-env compose identity.** Container names, published ports, and volumes
  derive from `TESSERA_ENVIRONMENT` (e.g. `tessera-${ENV}-postgres`, an env-keyed
  port block) so two envs compose up **simultaneously without collision**.
- **Per-env config + secrets.** `.env.<env>` (gitignored, from `.env.example`)
  instead of one `.env.local`; secrets resolved per-env in Secret Manager.
- **Tagged data.** Durable records that feed cross-env views carry the env they
  were produced in, so a shared substrate (CI, future multi-env DB) can still be
  filtered, and the UI can render an env honest-empty when it has no rows.

### Acceptance criterion

Dev and prod backends run **at the same time** with **separate ports, container
names, and Postgres schema/DB**, and neither sees the other's transcript, eval,
or memory state. Pick any durable record → its env is unambiguous.

### Layering (each its own commit; UI last; nothing pushed)

0. **This ADR** — model + audit (done).
1. **Config plumbing** — `Settings` exposes env-derived `pg_schema` and
   `reports_dir`; pool sets `search_path`; readers honor `reports_dir` with
   flat-dir fallback. Default preserves current behavior for `production`, so the
   live `:8099` stack and `:8392` dev are not disturbed.
2. **Compose isolation** — env-keyed names/ports/volumes; dev + prod up together.
3. **Tagged data** — `environment` stamped on the cross-env durable records.
4. **UI (last)** — the header badge/switcher reads the real dimension; an env
   with no data is honest-empty. Owned by the header workstream; this ADR only
   guarantees the dimension it reads is real.
5. **Deployed (out of this lot)** — staging/prod on Cloud Run via per-env
   Terraform workspaces.

## Consequences

- **Positive.** The everyday "dev clobbered prod's data" class of bug is
  structurally impossible once layer 1+2 land. The cockpit's env badge becomes
  honest. `as-of T` (0011, *when*) gains a clean spatial sibling (*where*).
- **Cost.** A migration step the first time a non-prod env starts on its new
  schema (it starts empty — honest, not lost). Compose files grow an env
  indirection. Every new durable store must remember to carry the env tag.
- **Risk / guardrail.** Layers 1–2 touch the Postgres pool and compose, which
  the **live `:8099` prod (ngrok) and `:8392` dev must not be disturbed by**.
  Default mappings are chosen so prod stays on `public`/flat-dir; non-prod moves
  are additive. No layer is pushed; commits are per-layer and reversible.
- **Rejected alternative.** A per-page environment dropdown — it implies a
  multi-env dataset that does not exist, i.e. fabrication. The badge stays
  read-only until a real per-env dataset earns the switcher.
