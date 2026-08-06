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
  the thing this ADR refuses.
- `coverage_descriptor` now reads `business_event_read` instead of `business_event_rows`. The
  latter says in its own docstring that it is "wrong for anything that derives a coverage claim
  from the absence", and the coverage claim was calling it: a ClickHouse outage rendered as an
  agent instrumenting nothing, with every required attribute listed as missing. Blind now yields
  `unverifiable` with **nothing** named as missing, because nothing is known to be.
- The consequence map is a second place that must move when a store's readers change. It is a
  declaration, so it can go stale — `tests/unit/test_observability_chain.py` pins that every
  declared dependency is a component something actually probes, which catches a renamed or
  removed component but not a capability that quietly acquired a new store.
