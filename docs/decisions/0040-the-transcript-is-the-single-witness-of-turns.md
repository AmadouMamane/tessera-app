# 0040 — The durable transcript is the single witness of agent turns

Date: 2026-07-19
Status: accepted
Extends: 0026 (a witness interrogates the thing, never its neighbourhood), 0007 (agent memory — the durable transcript is Mechanism A), 0019 (a synthetic canary turn must never move a business counter)

## Context

An operator opened the Recouvrement space, worked several real turns, and the
agent's **Synthèse** read all zeros: "Conversations touchées (24 h) 0", "Tours
traités (24 h) 0", résolution and temps de réponse "—". The turns had happened;
the dashboard denied them.

The Synthèse's operational KPIs (conversations, tours, résolution, temps de
réponse) are all derived from one query over the durable transcript
(`conversation_messages`, `agent_synthese.py`). But that table has exactly **one
writer**: `append_messages` at `chat.py`, reached only by `POST /chat`. A turn
appears in the Synthèse *if and only if* it flowed through `/chat`.

Recouvrement's structured turns do not: they go through
`/recouvrement-assistant/message` → `run_recouvrement_graph_v1`, which emits ~30
business events per turn but never writes the transcript. Same for the
recouvrement actions and the HTTP-binding Console invoke. So the transcript —
the thing the Synthèse interrogates — was blind to an entire class of real
turns. This is exactly ADR 0026's failure mode: a witness that cannot see must
never report "ok", yet the Synthèse reported a confident **0**.

The audit surfaced the symmetric defect. Operator **test** turns from the Agent
Console (in-process, `Surface.COCKPIT_EMBEDDED`) *do* write the transcript, and
the Synthèse counted them as real customer traffic — because the transcript had
no way to mark a turn as a test, and the reads had no way to exclude one. The
business-event surfaces already exclude synthetic turns (ADR 0019); the
transcript-derived Synthèse and Flotte did not. So one agent under-reported
(recouvrement, real turns dropped) while others over-reported (support-client /
onboarding, test turns counted). Both are the same root error: the transcript
was not treated as *the* record of a turn.

## Decision

**The durable transcript is the single witness of agent turns. Every seam that
produces a turn writes it; every "real traffic" read excludes marked test
turns.**

1. **Every turn-producing seam writes the transcript.** The recouvrement message
   route now calls `append_messages` after its graph returns — attributing the
   turn to the `recouvrement` agent and the served case, measuring the latency at
   the route (the graph does not return it), mirroring the `/chat` PII/degrade
   seam. Recouvrement *actions* and the Console *HTTP-invoke* are deliberately not
   persisted: an action is a governed artifact transition whose "user" leg is a
   canonical action name, not an utterance, and an HTTP-invoke is an operator
   test — persisting either would inflate "Tours traités" with non-turns.

2. **The transcript marks test turns.** `conversation_messages` gains a
   `synthetic boolean NOT NULL DEFAULT false` column; `append_messages` threads
   it, and `/chat` passes the `is_test_turn(surface)` value it already computes.
   The default backfills every existing row as real — the honest prior behaviour,
   since a pre-marker row cannot be re-distinguished.

3. **Every real-traffic read excludes synthetic.** The Synthèse (`_fetch_transcript`)
   and the Flotte rollup (`fleet.py`, and the `dedup_org_total` /
   `shared_entities_among` helpers via a validated `synthetic_col` identifier —
   never the raw predicate the P0.3 audit removed) all add `AND NOT synthetic`.
   Because the column defaults false, no existing figure moves; only a turn
   explicitly marked as a test is dropped.

4. **The turn carries the client it served.** `conversation_messages` gains a
   nullable `subject_id`; `/chat` passes `effective_subject`, recouvrement passes
   the case id. "Utilisateurs servis" becomes a real `count(DISTINCT subject_id)`
   over identified turns — honest, not fabricated. It reads small on the customer
   plane (one shared seeded demo identity today) and is already meaningful for
   recouvrement (distinct cases); an anonymous turn carries no subject and is not
   counted, so the cell is a real count or an honest "—", never an invented one.

## Consequences

- Recouvrement's Synthèse and the Flotte reflect its real traffic; the four
  transcript KPIs light up together because they are one query.
- Operator test turns no longer inflate any agent's Synthèse or Flotte, at parity
  with the business-event surfaces (ADR 0019).
- "Satisfaction / CSAT" stays honestly empty: no real customer-satisfaction
  signal is captured anywhere, and the doctrine (`agent_synthese.py` header, the
  AT-01 trap) bars the eval scores from this page. Instrumenting it honestly
  requires capturing a new customer-feedback signal — a separate, opt-in lot, not
  a relabelled proxy.
- The schema grows two nullable/defaulted columns via `ADD COLUMN IF NOT EXISTS`
  (the existing `agent_id` / `latency_ms` migration idiom); no migration tool and
  no backfill of live rows.
