# 0052 — A monitoring surface names the chain and the consequence, and a gap in a record is not uptime

- Status: **accepted** (2026-08-06)
- Date: 2026-08-06
- Deciders: Tessera maintainers
- Related: 0026 (a witness interrogates the thing, never its neighbourhood),
  0017 §4/§5 (the L0–L3 ladder, signal 92, owned ClickHouse),
  0015 (telemetry spine and scope), 0051 (served surfaces are declared and checked),
  `src/tessera/observability/stack_topology.py`,
  `src/tessera/observability/component_history.py`,
  `tests/unit/test_observability_chain.py`, `tests/unit/test_component_history.py`

## Context

`/surveiller/observabilite` was called *observability* and answered *is it running*. Those are two
questions. Health asks **is it alive**; observability asks **can I know what happened**. The page
had four KPI cards over `/healthz` and `/readyz`, a flat table of twenty component rows added on
2026-08-05, and a tail-sampling card. Every one of those answers the first question.

Three specific holes followed from that, and none of them is cosmetic:

1. **A flat list cannot express a dependency.** Twenty independent rows can say three things are
   red. They cannot say ONE thing is red and the other two are its consequence — which is the
   sentence an operator is assembling in their head anyway. Worse, the assembly a reader would
   perform unaided is wrong here: metrics reach Prometheus by two independent routes (the
   `tessera-agent` scrape job hits the agent's own `/metrics` directly), so a dead collector does
   **not** blind them; and business events never cross the collector at all (0017 §5, direct
   insert). A reader "reasoning about the pipeline" from a list of names gets both backwards.

2. **Nothing connected a red component to what it costs.** An operator could see ClickHouse down
   and had no way to learn that turn evidence had just become *cannot say*, and that an agent
   might therefore be refused at the release gate. The store and the blocked agent lived on two
   screens with no sentence between them. This is the same class as the 2026-08-05 finding that
   built the component table in the first place: the fact existed, and no surface carried it.

3. **The page had no past tense.** It polled every fifteen seconds and rendered *now*. Now is the
   one instant the operator did not need help with — they are looking because something happened,
   and *happened* is a word about the past. A component that fell and came back between two polls
   left no trace anywhere in the system.

And one thing that was computable and never computed: **signal 92**, instrumentation coverage,
declared `active` in the catalogue and implemented in `quality_nets.coverage_descriptor` since
step 6b — reachable only as `/observability/quality-nets?agent=<id>`, one agent at a time, from a
page that never called it. A fleet has no per-agent page to ask from.

## Decision

### 1. The chain is declared, cited, and walked as a path

`stack_topology.py` declares the nodes, the edges, and — on every edge — **the file that wires
it**. The citation reaches the screen. A diagram is a claim about the system; a claim whose
evidence a reader cannot reach is decoration, which is 0026 applied to a drawing.

Declared, not discovered, for 0026's other reason: a topology inferred from what is currently
reachable cannot go red for a component that has disappeared.

Reachability is computed as a **path from the emitter**, never tallied edge by edge. Edge by edge,
`langfuse-worker → minio` between two healthy nodes reads as traces flowing while the collector
upstream has been dead for an hour. Two healthy nodes downstream of a break are not a pipeline.

### 2. Every store names what its silence costs

`CONSEQUENCES` maps each capability to the components it needs and to **the module that reads
them** — a fact about this codebase, so it is written down and cited. The capability is declared;
the **state is computed** from the live probe and never asserted. Rows that can *block an agent*
rather than blank a chart are marked, because that is what an operator triages on.

The three-valued alphabet is preserved end to end: `served` / `lost` / `cannot_say`. A component
nobody could interrogate degrades its capability to `cannot_say` — never to `lost`, never to
`served`.

### 3. A gap in the record is a hole, and it is published

`component_history.py` journals each probe run as **phases** ("clickhouse was `fail` from 09:12
to 09:41"), not one row per observation — at one poll every fifteen seconds, a browser left open
overnight writes 5 760 rows that say nothing changed.

The probe only runs when somebody asks. Three rules follow, and each of them is a refusal:

- **A phase absorbs an observation only within `CONTINUITY_WINDOW` (120 s).** A later one starts a
  new phase, even for the same verdict. Extending across a closed cockpit would manufacture uptime
  out of nobody looking.
- **Every percentage travels with `observed_ratio`.** "99.9 % available" over a window watched for
  four of its twenty-four hours is a true statement about four hours and a false one about the
  day. The reader gets both numbers or neither.
- **Availability is a share of *decidable* time, not of watched time.** Blind minutes are observed
  — looking and failing to see is still looking — and they decide nothing about the component, so
  they stay out of the denominator. This one shipped and was caught on the screen: three minutes
  of "does not resolve" rendered as **0.0 % available**, in the same column and the same ink as a
  real outage. That is "the database is down" printed over "nobody could ask the database" — the
  exact confusion this whole surface exists to prevent, reintroduced in a denominator.

A first-ever observation is **not** a transition: nothing changed, the record began. A component
may have been failing for a week before anyone looked.

### 4. A link is offered only where it opens

The published tool addresses are loopback — true from the deployment host, false anywhere else. A
link is therefore rendered live only when the page is itself served over loopback; otherwise the
address is shown as host-only, without being promised. A dashboard that offers closed doors is
worse than one that offers none.

## Consequences

- The page answers *can I know what happened*. The component table remains, as the detail under
  the chain rather than as the page's substance.
- Two new public reads: `/observability/component-history` and
  `/observability/instrumentation-coverage`. Both carry aggregate facts, no subject, no scope.
- **The history is only as good as the watching.** Nothing schedules the probe; it runs when the
  cockpit asks. That is a real limitation, and it is published on every row rather than hidden —
  but a deployment wanting real availability numbers must poll the endpoint on a timer. Adding
  that scheduler is deliberately out of scope here: a number nobody can explain the coverage of is
  the thing this ADR refuses. *(Superseded by Amendment 1: the scheduler exists, and the coverage
  it produces is explained by the same `observed_ratio` machinery.)*
- `coverage_descriptor` now reads `business_event_read` instead of `business_event_rows`. The
  latter says in its own docstring that it is "wrong for anything that derives a coverage claim
  from the absence", and the coverage claim was calling it: a ClickHouse outage rendered as an
  agent instrumenting nothing, with every required attribute listed as missing. Blind now yields
  `unverifiable` with **nothing** named as missing, because nothing is known to be.
- **The journal has several writers.** Under 0044 the agent is N uvicorn processes, each probing
  and each folding its observations into one file with a read-modify-write; no cross-process lock
  exists, so an interleave can lose a phase. This is acceptable only because of the *direction* of
  the loss: a lost phase removes observed time, so it can only lower `observed_ratio` and widen a
  hole. It under-claims coverage; it cannot over-claim uptime. A deployment needing a complete
  journal rather than an honest one wants a single writer (the 0046 leader) — a change to who
  probes, not to what is recorded.
- The consequence map is a second place that must move when a store's readers change. It is a
  declaration, so it can go stale — `tests/unit/test_observability_chain.py` pins that every
  declared dependency is a component something actually probes, which catches a renamed or
  removed component but not a capability that quietly acquired a new store.

## Amendment 1 (2026-08-07) — the probe is scheduled, the phases are published, and a capability's witness is its own read

Three additions, each closing a hole the original decision named and left open. Every payload
change is by addition; the five endpoints keep their existing fields and meanings.

### 1. The leader watches (`probe_interval_s`, default 60 s)

The original consequences section said it plainly: nothing scheduled the probe, so the history
covered whatever a cockpit happened to watch — **1.3 % of the day, the day the page shipped**.
`observed_ratio` published the sliver honestly, and an operator cannot act on "99 % of 18
minutes".

The ADR 0044 **leader** now probes on a cadence (`TESSERA_OBS_PROBE_INTERVAL_S`, seconds, `0`
disables). The loop lives with its siblings in `api/main.py`, probes first and sleeps after,
and goes through the same 15 s cache as the page's reads, so a beat landing beside a page poll
reuses the observation instead of opening twelve more sockets. The original refusal — "a number
nobody can explain the coverage of" — is not reintroduced: coverage is still explained by
`observed_ratio`, which now approaches 1 because somebody is actually looking.

Two consequences of the original design soften but do not disappear:

- **The journal keeps several writers.** Workers still record on a request-path cache miss; the
  leader is merely the steady one. The loss direction is unchanged (a clobbered write can only
  under-claim coverage, never over-claim uptime).
- **A dead leader must not read as a running scheduler.** The loop stamps every beat to
  `probe_scheduler.json` (interval, instant, pid), and `/observability/component-history`
  reports the scheduler **from that stamp, never from configuration**: `never` (no beat has
  landed), `active` (last beat within two intervals plus slack), `stale` (the beats stopped —
  a dead leader loop, which is a different repair from "not configured"). Interrogate the
  thing, not its declaration (0026).

### 2. The phases travel to the screen

`component-history` served totals (`seconds_by_verdict`) and transitions; the phases themselves
stayed in the journal. A total cannot say *when* the fail was, and "when" is the question an
operator opens a history window with. The endpoint now also returns the phases clipped to the
window — `clipped_phases()` — so the page can draw a timeline in which a hole in the record is
visibly a hole, which was always this ADR's point rendered as ink.

### 3. A capability's state merges its component's OWN READ (the socket is the neighbourhood)

On 2026-08-06 this page said `langfuse-web OK` — its health endpoint answered 200 — and
`llm-observability · assurée`, while the overview's traces panel said *"Stack d'observabilité
injoignable"*: the module the consequence row itself cites (`langfuse_obs.py`) could not
complete one authenticated read. Two surfaces contradicted each other about one system because
this one's witness interrogated the neighbourhood (the socket) instead of the thing (the read).

`consequence_states()` therefore now accepts a second map — component → the verdict of its own
**adapter-level read** — merged with `_worst`, so a read can only degrade a state, never
improve it. Four reads exist today and cost nothing new: preflight already *is* the adapter
read for postgres, clickhouse and prometheus; Langfuse gains `langfuse_read_health()`, one
authenticated `limit=1` query through the same URL, credentials and parser the real numbers
use, cached on the probe's TTL. Each consequence row names which of its dependencies carried a
read this cycle (`checked_by_read`), so "assurée" over a socket-only check can never be
mistaken for the stronger claim — and `because` is computed from the same merge as the state,
so the two cannot disagree.

## Amendment 2 (2026-08-16) — the twelve are asked from inside; a thirteenth is asked from outside

Every component this ADR declares is interrogated over the **private compose network**, from the
agent container. That is the right vantage point for the question they answer — *is the thing the
operator runs up?* — and it is structurally incapable of answering the one an operator is
actually woken by: *can a visitor reach us?*

The two came apart on **2026-08-12**. The front container returned from a host reboot without
`restart: unless-stopped`, and `https://tessera.<domain>` served **502 for thirty-two hours**.
Every one of the twelve was green throughout, and correctly so: postgres, ClickHouse, Prometheus,
the collector, Langfuse and the rest were all up. The outage lived in the one hop none of them
crosses. It was found by a human opening the site.

The tool to ask already existed — `make deploy-diff` fetches `/api/version` on every declared
host and refuses on unreachable. What did not exist was anything that asked **without being
asked**. For thirty-two hours nobody typed it. A witness that only speaks when addressed is a
manual procedure wearing a witness's clothes.

So the registry gains a thirteenth entry, `public-canonical`, and the existing machinery does the
rest: the Amendment 1 scheduler probes it on the same cadence, the journal records it, and the
history divides by decidable time exactly as before.

Four properties, each of which had to be decided rather than defaulted:

- **HTTPS, at `/api/version`.** Not a health path. It traverses the whole browser-facing chain —
  edge → tunnel → front — and its answer *names the build being served* rather than proving a
  socket is open. `http://` would be redirected or refused at the edge and journalled as an
  outage on a component in perfect health.
- **It identifies itself.** Measured against the live edge on 2026-08-16: the default
  `Python-urllib/3.x` User-Agent gets **HTTP 403**, `tessera-stack-probe/1.0` gets **200**. Without
  the header this component would have reported a permanent, confident, entirely false outage —
  with a status code to back it up. `scripts/deploy_diff.py` carries the same header, learned the
  same way; that neither of them had told the other is why it is now a module-level constant.
- **Eight seconds, not three.** Three is generous for a socket on the same host and far too tight
  for a round trip that leaves the machine, crosses an edge network and returns through a tunnel.
  A timeout recorded as `unreachable` manufactures outages out of latency, which is worse than not
  watching: it teaches the operator to ignore the row.
- **No domain is declared in the code.** `docker-compose.fulllocal.yml` is explicit that the same
  image must serve `localhost` and a public host unchanged, and `infra/deploy/targets.yaml`
  already owns the hostname. `make fulllocal-up` reads it from there and exports
  `TESSERA_STACK_PUBLIC_CANONICAL`. **An undeclared public host makes the row BLIND, never OK** —
  on a laptop, in CI, or on any deployment that publishes nothing, "we cannot see a public URL
  because none was declared" is a fact about the observer, and the three wrong answers (`ok`,
  `fail`, `probe_failed`) each send the reader somewhere different and useless.

**What this still cannot see, stated because ADR 0026 requires it.** The probe runs inside the
deployment. It catches the outage that actually happened — front down, agent up — and it cannot
catch one that takes the host with it: no process, no probe, no record. That is not papered over.
A cycle that does not run leaves a **gap**, and this ADR's history already divides availability by
**decidable** time, so silence narrows `observed_ratio` instead of accumulating as uptime. An
operator reading "100 % available, observed 43 % of the window" is being told the truth twice. The
only vantage point that closes this hole is a prober outside the deployment, which is a decision
about a third-party service and not one this ADR takes.
