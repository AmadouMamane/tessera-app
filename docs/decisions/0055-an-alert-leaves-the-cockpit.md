# 0055 — An alert leaves the cockpit

Date: 2026-08-27
Status: accepted

## Context

ADR 0052 §Amendment 1 closed the watching hole: the ADR 0044 leader probes the declared
stack every minute and journals what it saw, cockpit open or closed. The stated nuance
remained open, and it is the sharpest one: **nothing pushes**. The cockpit knows a
component is down or a quality objective is breached, and the operator learns it by
opening a page. A breach at 03:00 is discovered at 09:00 with six hours of red already
honestly journalled. For a product whose category is *governance*, knowledge that waits
to be looked at is a promise kept only during office hours.

## Decision

The existing leader beat gains an **alert step** (no second loop): after each stack probe,
the beat reads two conditions and pushes on **state transitions only** —

* `stack_down` — the preflight witness reports at least one failing declared check;
* `slo_breach` — the same SLO derivation the cockpit hero reads (`slo_payload` over the
  7-day window, org scope) reports `breaching` with `n > 0`.

The sink is one **operator-configured webhook** (`TESSERA_OBS_ALERT_WEBHOOK_URL`,
Slack-compatible `{"text": ...}`). Three honest behaviours, enforced in
`observability/alerts.py` and pinned by unit tests:

* **transition** → push once; journal the event with the **delivery outcome read off the
  HTTP response** (status, or the error) — never off the intent (ADR 0026);
* **steady state** → push nothing: a channel that repeats itself trains its reader to
  ignore it; the journal already carries the duration;
* **cannot say** (a reading failed) → freeze the stored state: a blind beat neither pages
  nor declares a recovery (ADR 0026's corollary, applied to egress).

The first sighting of a *quiet* condition records a baseline silently — "recovered" about
an alert that never fired is noise.

`GET /observability/alerts` publishes posture (`configured` — the URL itself never leaves
the process), the last definite state per condition, and the journal tail; the Vue
d'ensemble carries a card reading exactly that, so the channel's own health is governed
like everything else: an unconfigured channel says so on screen instead of looking armed.

## Consequences

* No new dependency, no new loop: `urllib` (the probe's own client), one file of state,
  one append-only journal beside the component journal.
* Unconfigured deployments are unchanged except for the card honestly reading
  « non configurée » — arming it is one env var and a container restart (operator act).
* Re-notification while a condition stays red is deliberately absent from this slice;
  if silence-fatigue appears in practice, a `renotify_after` is the obvious amendment.
* The webhook is infrastructure egress like the edge probe, not agent egress: it does not
  cross the limes seam (ADR 0049), and the payload carries the condition text only —
  never customer content.
