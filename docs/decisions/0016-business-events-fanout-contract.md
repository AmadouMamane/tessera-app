# 0016 — Business events are a fan-out contract, not an application JSONL store

- Status: accepted
- Date: 2026-07-05
- Related: 0015 (runtime telemetry spine and scope), 0010 (Recouvrement internal
  operator agent), 0008 (agent audience and surface), 0009 (dashboard RBAC)

## Context

`build_recouvrement_graph_v1` introduced typed business events for the first
Recouvrement slice (`workflow_id=recouvrement_collections_v1`, task
`check_contact_rule`). ADR 0015 already decides where core telemetry facts live,
but it did not explicitly name "business events" as a single store type.

Treating those events as a new JSONL projection would reintroduce the convenience
file pattern ADR 0015 retired for cockpit read paths. Treating them as a single
Postgres fact would also be too coarse: one event can be simultaneously a trace
event, an audit fact, a replay input, a metric input, a scoring input, and a
cockpit signal.

## Decision

A business event is a **versioned envelope** that fans out to the existing ADR 0015
homes. It is not itself a new monolithic source of truth.

| Event facet | Home |
|---|---|
| Trace/detail | OTel span event, exported to Phoenix/Langfuse according to the spine |
| Aggregate/count | Prometheus counters |
| Opposable/auditable fact | Owned append-only hash-chained audit ledger |
| Replay context | Replay bundle payload for the captured turn |
| Deterministic business score input | Domain `BusinessScorer` selected through `BusinessScoringRegistry` |
| Cockpit read model | `BusinessEventStore` port; local/test default is bounded in-memory, never JSONL |

Critical events carry `schema_version`, `event_version`, and strict payload
schemas. Generic observability modules may know the event envelope and sink ports,
but not domain constants such as `CONTACT_WINDOW`, `OUTSIDE_CONTACT_WINDOW`, or
`contact_rule_v1`. Those live in the relevant business package.

## Alignment with ADR 0015

ADR 0015 remains the source of truth for data placement. This ADR does not create
a parallel telemetry store and does not move facts away from the homes ADR 0015
already assigns:

- metrics remain Prometheus aggregates;
- trace/detail remains OTel-exported telemetry, with Phoenix/Langfuse as the
  trace drill-down surfaces;
- opposable business events remain in the owned append-only hash-chained audit
  ledger;
- replay context remains attached to replay bundles / captured turns;
- cockpit signals remain read through the spine / read-model seam and Scope
  filters.

This ADR only defines the Recouvrement/business-event envelope and its fan-out
rules so specialised workflows can publish typed business facts into those
existing ADR 0015 sinks without reintroducing application JSONL.

## Consequences

- No core business-event path may depend on `business_events.jsonl`.
- Opposable events are durable through the promoted audit ledger, not through the
  cockpit projection.
- If a future product requires a durable historical business-event read model
  beyond the ledger/replay/traces, it must implement the `BusinessEventStore` port
  with an owned indexed store and record that store decision here or in a
  follow-up ADR.
- Cockpit endpoints filter by declared dimensions (`agent_id`, `workflow_id`,
  `conversation_id`, `turn_id`, `case_id`, `event_name`, `artifact_type`,
  `decision`) and never infer domain meaning from raw payloads.
