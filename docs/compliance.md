# Compliance

This document describes how Tessera maps European retail-banking regulation onto
concrete agent behavior, what the runtime guard enforces, and what the audit
trail records. It is a technical reference, not legal advice. See the
[Limitations](#limitations) section before relying on any statement here in a
real institution.

## Regulatory framework grounded in Tessera

Tessera grounds its responses and its guardrails in four bodies of European
regulation. The regulatory corpora are ingested into the retrieval store
(`src/tessera/corpus/data/regulations_*.json`) and surfaced through the
`regulation_lookup` worker. The guard policy
(`src/tessera/guard/policy.yaml`) encodes the runtime enforcement that the
regulatory grounding implies.

### GDPR — Regulation (EU) 2016/679

The General Data Protection Regulation is the backbone of Tessera's data
handling. It applies to every turn because every banking conversation processes
personal data. The relevant articles and how they manifest:

- **Art. 5(1)(c) — data minimisation.** The agent retrieves and echoes only the
  data needed to answer the question. PII redaction patterns in
  `policy.yaml` (`pii.redact_patterns`) strip emails, IBANs, 16-digit PANs and
  FR/DE phone numbers from both tool inputs and tool outputs before they reach
  the LLM or the audit log.
- **Art. 15 / Art. 17 — right of access and right to erasure.** The agent does
  not itself delete or export customer records. When a user invokes these
  rights, the agent signposts the official channel and escalates to a human via
  the `ticket_escalate` tool rather than attempting the operation itself.
- **Art. 25 — data protection by design.** PII redaction and argument-pattern
  validation are applied at the guard layer, ahead of any tool execution.

### DORA — Regulation (EU) 2022/2554

The Digital Operational Resilience Act applies to financial entities and became
effective on **17 January 2025**. Tessera treats DORA as in-scope corpus and
encodes two operational expectations:

- **ICT incident reporting.** Guard denials, sink failures and tool errors are
  emitted as structured audit records (`src/tessera/guard/audit.py`) suitable
  for feeding an ICT-incident reporting pipeline. Tessera does not file reports
  itself; it produces the evidence trail an operator would need.
- **Third-party (ICT) risk.** The single runtime third party in the request
  path is `mcp-firewall`, consumed as a pinned dependency. Pinning and the
  audit of every guard decision are the third-party-risk controls Tessera
  exposes.

Note that DORA targets the financial entity's operational resilience, not the
retail customer directly. Failure cases `35_regulatory_misstatement_dora_retail`
and `37_regulatory_misstatement_dora_date` exist specifically to catch the agent
misapplying DORA to retail customers or misstating its effective date.

### CNIL guidelines (France)

The Commission Nationale de l'Informatique et des Libertés issues
France-specific guidance that refines GDPR in the French market. Tessera carries
a dedicated CNIL corpus (`regulations_cnil.json`), and the FR system prompt
(`src/tessera/agent/prompts/fr.yaml`) instructs the agent to cite CNIL and RGPD
texts when relevant and never to fabricate a reference. CNIL cookie/consent
guidance is the reference used for consent-flow questions in the FR locale.
Failure case `36_regulatory_misstatement_cookies` guards against cookie/consent
misstatements.

### BaFin circulars (Germany)

The Bundesanstalt für Finanzdienstleistungsaufsicht issues circulars
(Rundschreiben) that govern German financial services, including product
suitability expectations. Tessera carries a BaFin corpus
(`regulations_bafin.json`) for the DE locale. The corpus is currently smaller
than the CNIL corpus, which is a known coverage gap tracked in
`docs/multilingual.md`.

## Guard policy structure

The runtime guard is `mcp-firewall` consumed as a dependency and configured
through `src/tessera/guard/policy.yaml`. The adapter
(`src/tessera/guard/adapter.py`) reads the policy at start-up and re-reads it on
`SIGHUP`. The policy has three top-level sections.

### Tool-level allow/deny and argument validation

Each LLM-callable tool has an entry under `tools:`. The fields, per the schema
documented at the top of `policy.yaml`:

- `allow` (default `false`) — whether the tool may run at all.
- `requires_confirmation` — require an explicit user re-ask before executing.
- `require_languages` — restrict invocation to a set of locales.
- `max_calls_per_turn` (default `1`) — rate-limit within a single turn.
- `arguments.<name>.pattern` — a regex the argument value must match.
- `arguments.<name>.redact_in_audit` — mask the value in the audit trail.

Concrete current rules:

| Tool | allow | confirmation | max/turn | notable argument rules |
|------|-------|--------------|----------|------------------------|
| `account_balance` | true | no | 2 | `customer_id` matches `^[a-zA-Z0-9_-]{4,64}$`, redacted in audit |
| `card_block` | true | **yes** | 1 | `reason` constrained to `lost\|stolen\|fraud_suspected\|customer_request`; `card_last_four` `^[0-9]{4}$` |
| `transaction_search` | true | no | 3 | `customer_id` redacted in audit |
| `loan_simulate` | true | no | 5 | no PII arguments |
| `ticket_escalate` | true | no | 1 | `transcript_excerpt` redacted in audit |

`card_block` is the only tool requiring explicit confirmation, because it is a
state-changing action against the customer's account.

### Prompt-injection rules

`prompt_injection.deny_patterns` reject a turn outright when the user input
matches (e.g. "ignore all previous instructions", "reveal your system prompt",
"disregard the rules"). `prompt_injection.transform_patterns` strip an offending
substring rather than rejecting the whole turn (e.g. "act as / pretend to be /
roleplay as …" is replaced with `[redacted role-play attempt]`).

### PII redaction hooks

`pii.redact_patterns` are applied to all tool inputs and outputs. The current
patterns cover email addresses, IBANs (basic shape; full validation deferred to
the tool layer), 16-digit PANs, and French and German phone numbers. Redaction
applies both to the audit log and to argument values echoed back to the LLM,
which keeps personal data out of the model context.

## Audit trail as a compliance artifact

The audit trail is the structured evidence record for every guard decision. It
is emitted by `emit_audit` in `src/tessera/guard/audit.py`.

**The sink is a transport; the ledger is the store** ([ADR 0023](./decisions/0023-audit-chain-independent-of-sink.md)).
These are orthogonal, and the distinction is the one that matters to a regulator:

- The **opposable record** is the hash-chained, append-only Postgres ledger
  (`tessera_local.audit_ledger`), fed by the fsync spool and linked by the drain under an
  advisory lock (ADR 0015). It is **not configurable**: every entry is chained there
  whatever the sink, and an exposed deployment that *could not* chain refuses to boot.
- The **sink** selects where an additional, human-readable *copy* is carried — nothing more.
  No value of it can switch opposability off, and none of them is the evidence.

| sink | what it carries |
| --- | --- |
| `stdout` | JSON-Lines on stdout — local development and tests. |
| `file` | Appended JSON-Lines at a configured path. Pre-cut, this file IS the chain; post-cut the ledger is, and the flat file stops. |
| `cloud_logging` | The observability copy in staging/production, for dashboards and retention. |
| `postgres` | No separate copy: the Postgres persistence of an entry **is** the ledger, upstream. |

Until 2026-07-12 (audit **F-6**) this section documented `postgres` as *"currently falls back
to stdout"* and the ledger feed ran only when the sink was `file` — so the documented
staging sink, `cloud_logging`, emitted entries to Cloud Logging and chained **nothing**. An
operator following this page turned opposability off without a signal. No sink falls back to
anything now: a transport that cannot emit fails loudly, and the chain is untouched by it.

### Audit record shape

Each entry is a single JSON object with this shape (`_build_entry`):

```json
{
  "type": "tessera.guard.audit",
  "version": 1,
  "occurred_at": "<ISO-8601 UTC>",
  "target": "<tool name>",
  "outcome": "allowed | denied | error",
  "arguments": { "<name>": "<value or redacted>" },
  "decisions": [
    {
      "target": "...",
      "decision": "...",
      "policy_rule": "...",
      "rationale": "...",
      "redactions": ["..."],
      "occurred_at": "<ISO-8601 UTC>"
    }
  ],
  "error": null
}
```

Each decision records which policy rule fired, the rationale, and which fields
were redacted. Arguments flagged `redact_in_audit` in the policy are masked
before they enter the record.

The audit emitter is fire-and-forget: sink failures are caught and written to
stderr so an audit-sink problem never blocks the agent's main path. This is a
deliberate availability-over-completeness tradeoff — a real institution running
in regulatory-replay mode should monitor stderr for dropped audit entries.

### Retention policy

Retention is a deployment concern, not encoded in the application. Placeholder
guidance: audit records written to Cloud Logging inherit the log bucket's
retention; records written to the dedicated `postgres` audit table are retained
per the institution's record-keeping obligations (commonly multi-year for
financial conduct evidence). The retention period must be set explicitly per
deployment and is out of scope for this reference implementation.

## Human-in-the-loop escalation

Escalation is the fourth quality layer. The reviewer
(`src/tessera/agent/reviewer.py`) computes a confidence score for every turn and
flips `needs_escalation` to `True` when the score falls below
`GuardSettings.escalation_confidence_threshold` (default **0.6**). The graph
then routes to the escalation worker, which calls the `ticket_escalate` tool
(`src/tessera/agent/tools/ticket_escalate.py`).

The escalation ticket (`TicketRequest`) contains:

- `conversation_id`
- `language` (`fr` / `de` / `en`)
- `reason` — the structured escalation reason from the reviewer, e.g.
  `Confidence 0.42 below threshold 0.60; weakest signal: grounding (0.10)`
- `transcript_excerpt` — redacted in audit per the policy
- `preferred_channel` — `phone` (default), `email`, or `branch`

The tool returns a `Ticket` whose reference has the form `TS-` followed by ten
uppercase hex characters (`secrets.token_hex(5).upper()`), plus the open
timestamp, channel, and language. The user-facing acknowledgement is rendered
from the `escalation` key of the per-language prompt bundle and surfaces the
reference. The receiving team is a Crédit Aurore human advisor; the ticketing
backend (Salesforce / Zendesk / internal CRM) sits behind a protocol so the demo
can run with no external service.

## Limitations

- **No legal advice.** Tessera does not provide legal or regulatory advice. Its
  regulatory citations are grounded in an ingested corpus, not a live legal
  database, and may lag amendments.
- **Compliance-officer review required.** Before any production use in a real
  institution, agent responses and the guard policy must be reviewed and signed
  off by a compliance officer. Tessera is a reference implementation.
- **Personalised investment advice is out of scope.** The FR system prompt
  explicitly forbids it; failure case
  `32_policy_violation_conseil_investissement` guards against regressions.
- **Audit completeness is best-effort.** Sink failures are swallowed; the
  `postgres` regulatory-replay sink is not yet implemented.

## Data residency

All data stays within the EU by default:

- **Cloud Run** — region `europe-west1` by default.
- **Cloud SQL** (PostgreSQL + pgvector) — same region as Cloud Run.
- **Secret Manager** — secrets resolved at container start; never in the repo.
- **Cloud Logging / Cloud Monitoring** — EU-region log and metric buckets.

Embeddings on the frontier path are produced by Vertex AI in-region; the
on-premises path runs Llama 3.3 70B via Ollama and a local Ollama embedding
model on Apple Silicon, so no data leaves the operator's hardware at all. The
region is configured in `infra/terraform/variables.tf`.
