# 0039 — The operator-queue SLA clock runs from queue-entry, not the case date

Date: 2026-07-19
Status: accepted
Extends: 0038 (the backlog is partitioned by nature), 0026 (a witness interrogates the thing)
Amends: the SLA anchoring in `operator_items` (was `created_at`)

## Context

The two operator queues ("À faire" / "À traiter") derive a real backlog and
score each item against an SLA (crit 1 h, high 4 h, mod 8 h, low 24 h). The SLA
due time was anchored on `created_at` — which for an eval-failure item is the
timestamp of the **evaluation run** (a seeded catalogue run days or weeks ago),
and for a business event is when the event occurred.

The effect on screen: **every item was overdue by construction.** On the live
reference the eval run was dated 04/07; on 19/07 all 18 eval items and 45 of 49
business items read as "hors délai", so every sidebar badge and every SLA cell
was red. When everything is red, red carries no information — the same class of
defect as serving a fixture as real data: a signal that cannot be false is not a
signal. This was pre-existing (the single badge was already always red); ADR
0038 only made it more visible by splitting it into two.

The root cause is a category error: `created_at` is when the underlying *case*
happened; the SLA measures how long a human has left the item *unactioned in
their queue*. An operator cannot breach an SLA on something that only just
appeared in front of them, however old the underlying case is.

## Decision

The SLA clock runs from **queue-entry**, a durable per-item `first_seen`:

* The first time `load_items` observes an item, it records `first_seen` in the
  same durable store as status/assignee (best-effort, `setdefault` so a
  concurrent status write and a racing observer are both preserved). Reads that
  find nothing new never write.
* `OperatorItem.sla_anchor()` = `queued_at or created_at`; `due_at`,
  `remaining_seconds`, `overdue`, `sla_tone` all measure from there. An item
  built off the load path (no `queued_at`) keeps the old `created_at` behaviour,
  so nothing silently changes shape.
* `created_at` stays the case's own timestamp and is surfaced as **provenance**,
  never conflated with the clock. The "À faire" drawer shows both, honestly and
  separately: *En file depuis* (the SLA clock) and *Cas daté du* (provenance),
  plus *Attente en file*.
* The drawer's SLA value/note are coloured by the real `sla_tone`, not a
  hard-coded red — the last "always red" surface. The table cells and chrome
  badges already derive their colour from the tone, so they become honest the
  moment the clock does.

## Consequences

* Red becomes a real signal again: an item is red only once it has genuinely sat
  in the queue past its SLA. On a freshly-deployed store the queue starts calm
  and **ages naturally** — crit items warm within the hour, low items over a day.
* On the seeded demo this means the backlog is green-then-aging on first load
  rather than uniformly red. That is the honest state: nothing has actually
  breached a real SLA yet. We do not fabricate urgency to make the demo dramatic
  (the project's standing rule against fabricated values).
* The clock is durable: it survives restarts and does not restart on every read
  (ratcheted — `test_first_seen_is_stamped_once_on_observation_and_reused`).
* A read now performs a best-effort write (observation). It targets the same
  per-env isolated store as the mutations and never fails a read; unit tests
  default `_save_state` to a no-op and control the store where they assert on it.
* Not in scope: back-dating `first_seen` for items that pre-date this change —
  their first observation is honestly "now". A true production system stamps
  reality as items arrive.
