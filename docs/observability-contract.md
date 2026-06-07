# Tessera Observability Contract

Status: draft v1  
Related ADR: `docs/decisions/0010-observability-assurance-layer.md`

Tessera emits a stable, privacy-gated observability contract before any signal
is exported to Google Cloud, an on-premises collector, Langfuse, logs, metrics,
or evidence bundles.

## Canonical Spans

- `tessera.turn`
- `tessera.langgraph.router`
- `tessera.langgraph.planner`
- `tessera.langgraph.product_lookup`
- `tessera.langgraph.regulation_lookup`
- `tessera.langgraph.account_lookup`
- `tessera.langgraph.simulator`
- `tessera.langgraph.reviewer`
- `tessera.langgraph.reporter`
- `tessera.guard.decision`
- `tessera.retrieval.query`
- `tessera.llm.call`
- `tessera.memory.operation`
- `tessera.escalation`

## Canonical Metrics

- `tessera_agent_turns_total`
- `tessera_agent_turn_duration_seconds`
- `tessera_langgraph_node_duration_seconds`
- `tessera_guard_decisions_total`
- `tessera_escalations_total`
- `tessera_retrieval_documents_total`
- `tessera_citations_total`
- `tessera_llm_tokens_total`
- `tessera_llm_cost_eur_total`
- `tessera_memory_degradations_total`
- `tessera_language_mismatches_total`
- `tessera_observability_completeness`
- `tessera_proof_consensus`
- `tessera_sensitive_action_transactions_total`

## Privacy Rules

Allowed attributes are defined in `src/tessera/observability/schema.py`.
Forbidden attributes include raw prompts, raw completions, PAN, IBAN, email,
phone numbers, access tokens, full names, raw account ids, raw card ids, and
high-cardinality metric labels such as raw conversation ids or turn ids.

Raw prompts are not exported. Prompt lineage is carried by `prompt_family`,
`prompt_version`, and `prompt_hash`; evidence bundles store hashes and redacted
fragments instead of user secrets.

## Evidence Bundle V1

Every persisted bundle uses schema `tessera.evidence_bundle.v1` and links:

- hashed conversation id and turn id
- trace id when present
- prompt, policy, and corpus hashes
- profile and target assurance level
- guard decision fragments
- proof-carrying tool-call references
- retrieval and citation evidence
- audit evidence counts
- rejected paths and evidence gaps
- privacy status and signature when required by profile

The bundle is the portable audit object. Langfuse is a cockpit view, not the
source of truth.
