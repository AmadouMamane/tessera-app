# 0038 — The operator backlog is partitioned by nature

Date: 2026-07-18
Status: accepted
Extends: 0015 (§Migration E — ventilate the inbox), 0026 (a witness interrogates the thing)
Amends: the "both queue pages read the whole backlog" behaviour of `operator_items`

## Context

`operator_items.load_items()` derives ONE real backlog from two natures of
artifact: failed evaluation cases (`source_kind="eval_failure"`) and pending
business-grammar events — validations requested, actions blocked
(`source_kind="business_event"`). Both queue pages read that whole backlog:
`compute_agent_a_faire` ("À faire", governance plane, `routes/observability/fleet.py`)
and `compute_inbox_overview` ("À traiter", business plane,
`routes/observability/business.py`) each listed all of it. The two pages were
therefore the same queue rendered twice — 64 identical items on the live stack
at the time of this decision (18 eval + 46 business) — and an operator could
not tell which page owned which work. One consumer (`fleet._business_card_facts`)
had already started filtering by `source_kind` **by hand**: the partition rule
was being invented locally, without a declaration anybody else could read.

## Decision

The backlog is **partitioned by nature**, and the partition is declared once,
in `operator_items`:

* **"À faire"** = the eval/governance half: `source_kind == "eval_failure"`.
* **"À traiter"** = the business half: `source_kind == "business_event"`.

Mechanics:

* `load_items()` stays the **unfiltered union** — it is the reference the
  partition ratchet measures both halves against.
* `nature_of(source_kind)` is the ONE rule. It **raises**
  (`UnknownSourceKindError`) on a kind no page owns — an item must never
  vanish in silence, the same spirit as an exhaustive `Verdict` match.
* `partition_items(items)` splits a backlog exhaustively;
  `load_items_for(nature, agent_id)` is the per-page read. No consumer may
  hand-roll a `source_kind` comparison.
* Every consumer goes through the rule: the two computes, the fleet card's
  pending-business count, the chrome badges **and** the bell notifications
  (each chrome number counts the half of the page it deep-links to), and the
  two item-state mutation endpoints (each validates ids against its own half
  and returns its own filtered view).
* **Honest-empty:** a page whose half is empty is legitimately empty — never
  a fallback that re-swallows the other half. Empty-by-nature is distinct
  from "backend unreachable".

## Consequences

* The two pages stop being copies: "À faire" is the eval-review queue,
  "À traiter" the business-decision queue. Their KPIs, donuts, SLA buckets
  and drawers now describe only their own work.
* A new `source_kind` cannot ship half-declared: until it is added to
  `_NATURE_KINDS`, both pages refuse loudly (500), and the partition ratchet
  in `tests/unit/test_operator_items.py` is red.
* The invariant is ratcheted: union == both halves, intersection == ∅,
  exhaustive on unknown kinds, and each compute is tested through the REAL
  filter path (stubbing at the source), so deleting a page's filter re-swallows
  the other half and turns the ratchet red.
* Out of scope, noted for a separate lot: the frontend i18n namespaces
  (`agentAFaire` / `inbox`) still carry pre-partition wording; the backend
  payload strings (inbox rail/footer) were realigned here.
