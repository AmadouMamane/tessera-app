# 0035 — Retrieval depth and reranking are per-agent, effective by construction

Date: 2026-07-18
Status: accepted
Extends: 0031/0032/0033 (effective by construction, the same seam)

## Context

The chat path's retrieval knobs are frozen in code: `product_lookup` hands the
synthesis its top **4** chunks, `regulation_lookup` its top **6**, and
`hybrid_search` always over-fetches ×3 and reranks with RRF fusion. Quality vs
latency is a real per-agent trade-off (a collections agent wants precision, an
onboarding agent wants recall), and the observability page already *measures*
reranker lift (`reranking_contribution`) — but nothing lets an operator act on
the measurement.

## Decision

1. **Two per-agent knobs in the agent-configurations store** (operator, same
   governed save, same author attribution):
   - `retrieval_top_k` — the documents each lookup hands to synthesis. Unset =
     each worker's historical default (4 product / 6 regulation), said as such
     ("Défaut par recherche (4 produit / 6 réglementaire)") — never one number
     pretending to be both. Set = that many for BOTH lookups, clamped [1, 10],
     integer.
   - `retrieval_rerank` — the RRF reranker, ON by default (the historical
     truth). Off = vector order serves directly and the ×3 over-fetch is
     skipped (it exists only to feed the reranker).

2. **Same seam, same recipe.** `resolve_retrieval(agent_id)` runs once per
   turn at the routing seam, lands in `state["retrieval"]`, and the lookup
   workers read THE STATE — falling back to their historical constants
   off-seam (eval harness unchanged). `hybrid_search.search` gains an explicit
   `rerank: bool = True` parameter; a skipped reranker is a declared decision,
   never a silent behaviour change.

3. **Said on the page.** The Configurations page gains a "Recherche
   documentaire" block: the depth slider (honest unset label), the rerank
   toggle, and a note naming what each state serves. The retrieval span
   already records corpus/hits/top-score per search; depth and rerank ride
   the state and the store's change-log.

## Consequences

- The eval harness and the offline probes keep the frozen constants — their
  numbers stay comparable across runs.
- The regulation worker's 0.75 score-cut is NOT a knob: it is calibrated
  against the RRF scale and moving it belongs to an eval-backed change, not a
  slider.
