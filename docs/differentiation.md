# Tessera — Differentiation

This document situates Tessera against the open-source projects and research it
builds on, and records what makes the assembly defensible.

## Scope

Tessera deliberately reuses proven components instead of reinventing them:

- **Runtime guard** — `mcp-firewall`, consumed as a pinned dependency.
  `src/tessera/guard/adapter.py` is an adapter: when `mcp_firewall` is importable
  it delegates decision logic to it; otherwise it falls back to a local policy
  engine exposing the same interface.
- **Regression harness** — declarative-case + assertion patterns in the spirit of
  AgentAssay and Promptfoo. The schema, runner, and scorecard are purpose-built
  glue over those patterns.
- **Structured audit trail** — informed by the AEGIS research line.

## What Tessera is

Tessera is a **complete, opinionated, deployed assembly** of four quality layers
— runtime guard, offline regression harness, structured audit trail, and
human-in-the-loop escalation — wired end to end for one specific, demanding use
case: European retail banking customer support in French, German, and English,
with explicit grounding in EU regulatory corpora (DORA, CNIL, BaFin, GDPR).

The engineering work is the end-to-end integration and the EU banking domain
semantics:

- A LangGraph agent (router → planner → parallel workers → reviewer →
  reporter/escalation) over a pgvector hybrid-search retrieval layer with
  cross-lingual regulation search.
- A dual LLM path: Vertex AI for the frontier deployment and Ollama-served local
  models (up to Llama 3.3 70B) for an on-premises Apple Silicon deployment,
  behind one backend Protocol.
- The four layers integrated so they reinforce each other: guard decisions feed
  the reviewer's confidence, the harness asserts on the guard's observable
  effects, and every guard decision is audited.

## Built on / inspired by

| Project | Role in Tessera | Relationship |
| --- | --- | --- |
| `mcp-firewall` (ressl) | Runtime guard / tool-call policy engine | Dependency (pinned) |
| AEGIS | Structured audit-trail design | Inspiration |
| DFAH | Failure-taxonomy framing for the catalogue | Inspiration |
| AgentAssay | Declarative-case + assertion pattern | Inspiration |
| Promptfoo | Case-file structure, per-language expansion, scorecard | Inspiration / interop |
| STING | Adversarial / prompt-injection probe patterns | Inspiration |
| Bernstein | Compliance / audit framing reference | Inspiration |
| ALTK | Agent-evaluation tooling reference | Inspiration |

## Citations

References stated as fact are verified against their source (last check:
2026-07-04):

- Greshake et al., "Not what you've signed up for: Compromising Real-World
  LLM-Integrated Applications with Indirect Prompt Injection", arXiv:2302.12173
  (2023). Verified on arxiv.org (title, first author, year, topic). Used by
  `eval/failures/01_prompt_injection.json`.
- OWASP Top 10 for LLM Applications v1.1 (2023/2024), "LLM06: Sensitive
  Information Disclosure". Verified on owasp.org; note the 2025 revision
  renumbers this entry LLM02 (some newer failure cases cite it as such). Used
  by `eval/failures/02_pii_leak.json`.
- Regulation (EU) 2022/2554 (DORA) — scope (art. 2(1): "credit institutions"
  verified verbatim), incident reporting (art. 19(4)), entry into force and
  application from 17 January 2025 (art. 64; official EUR-Lex summary).
  Verified on EUR-Lex (CELEX:32022R2554). Used by
  `src/tessera/corpus/data/regulations_dora.json` and the router's grounded
  DORA corrections.
- Commission Delegated Regulation (EU) 2025/301 — major-incident reporting
  time limits (initial ≤ 4 h from classification / ≤ 24 h from awareness,
  intermediate ≤ 72 h, final ≤ 1 month). Verified on EUR-Lex
  (CELEX:32025R0301, art. 5). Used by the `DORA/art-19` corpus document and
  `policy_dora_incident_deadline`.

## Competitive moats

Tessera's defensibility comes from the specificity and completeness of the
assembly, not from any single component:

1. **EU regulatory grounding across three jurisdictions.** The agent retrieves
   over DORA, CNIL, BaFin, and GDPR corpora, with cross-lingual search
   (`knn_search` with `language=None`) so a French question can match a German
   BaFin circular. The regulatory semantics are baked into the prompts, the
   citation records, and the failure taxonomy. This is hard to replicate without
   the same domain work.
2. **A real deployment on two substrates.** The frontier path runs on Google
   Cloud Run with Cloud SQL, Secret Manager, and Cloud Logging/Monitoring
   (Terraform under `infra/terraform/`). The on-premises path runs Llama 3.3 70B
   on Apple Silicon via Ollama. Both sit behind one `ChatBackend` Protocol, so
   the same agent code serves both — a deployed system with a data-residency
   story, not a demo notebook.
3. **A 63-case non-regression harness over documented real-world failures.**
   Ten categories, three languages, machine-checked pass criteria, replayed
   against the live graph nightly in CI and per agent on demand, with a
   two-level release gate (non-derogable security floor + per-agent domain
   threshold, waivers governed and currently zero). This turns "we tested it"
   into a continuously-enforced contract.
4. **Transparent test reporting.** The README documents the tests that pass *and*
   the tests that fail, with root causes. The evaluation contract is enforced in
   CI on every push, which keeps the assembly honest and current.
