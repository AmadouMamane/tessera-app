# Tessera — Differentiation

This document situates Tessera against the open-source projects and research it
builds on, and records what makes the assembly defensible.

## Scope

Tessera deliberately reuses proven components instead of reinventing them:

- **Runtime guard** — first-party, behind the single declared seam
  `src/tessera/guard/adapter.py` (ADR 0028). `mcp-firewall` (ressl) is the
  category's prior art; the earlier claim that it provided this layer was
  false — the dependency was never invoked.
- **Regression harness** — declarative-case + assertion patterns in the spirit of
  [AgentAssay](https://arxiv.org/abs/2603.02601) and
  [Promptfoo](https://github.com/promptfoo/promptfoo). The schema, runner, and scorecard are
  purpose-built glue over those patterns.
- **Pre-execution and structured audit trail** — informed by
  [AEGIS](https://arxiv.org/abs/2603.12621).

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

| Project | Primary source | What Tessera actually borrows or compares |
| --- | --- | --- |
| `mcp-firewall` (Robert Ressl) | [GitHub](https://github.com/ressl/mcp-firewall) | Guard-category prior art and the single policy-seam idea. Tessera does not use its MCP proxy (ADR 0028). |
| AEGIS — *No Tool Call Left Unchecked* | [arXiv:2603.12621](https://arxiv.org/abs/2603.12621) | Pre-execution interception, approval and tamper-evident audit comparator. Tessera implements a banking-specific first-party seam. |
| DFAH — Determinism & Faithfulness Assurance Harness | [IBM Client Engineering reference implementation](https://github.com/ibm-client-engineering/output-drift-financial-llms/blob/main/DFAH.md) | Repeated-run action/trajectory determinism and faithfulness comparator. It is **not** the source of Tessera's failure taxonomy; the earlier description was wrong. |
| AgentAssay — *Token-Efficient Regression Testing for Non-Deterministic AI Agent Workflows* | [arXiv:2603.02601](https://arxiv.org/abs/2603.02601) · [GitHub](https://github.com/qualixar/agentassay) | Regression testing, mutation operators and PASS/FAIL/INCONCLUSIVE reference. Tessera's case schema and domain graders are independent. |
| Promptfoo | [GitHub](https://github.com/promptfoo/promptfoo) | Declarative case files, assertions and prompt-evaluation interoperability reference. |
| STING — *Helpful to a Fault: Measuring Illicit Assistance in Multi-Turn, Multilingual LLM Agents* | [arXiv:2602.16346](https://arxiv.org/abs/2602.16346) | Multi-turn multilingual red-team methodology and a documented gap: Tessera's public catalogue is still primarily single-turn. |
| Bernstein | [project introduction](https://bernstein.run/blog/introducing-bernstein) | Deterministic orchestration, worktree isolation and replayable audit-lineage comparator. The earlier “multilingual evaluation” attribution was wrong. |
| ALTK — Agent Lifecycle Toolkit | [arXiv:2603.15473](https://arxiv.org/abs/2603.15473) · [documentation](https://agenttoolkit.github.io/altk-main/) | Modular pre/post-tool lifecycle middleware comparator; Tessera keeps its own narrow, measured guard seam. |

## Citations

References stated as fact are verified against their source (last check:
2026-07-21):

- Yuan, Su and Zhao, “AEGIS: No Tool Call Left Unchecked — A Pre-Execution Firewall and Audit
  Layer for AI Agents”, arXiv:2603.12621 (2026). Verified on arXiv (title, authors, interception,
  approval and hash-chained audit claims).
- Bhardwaj, “AgentAssay: Token-Efficient Regression Testing for Non-Deterministic AI Agent
  Workflows”, arXiv:2603.02601 (2026). Verified on arXiv and the `qualixar/agentassay` source
  repository.
- Talokar et al., “Helpful to a Fault: Measuring Illicit Assistance in Multi-Turn, Multilingual
  LLM Agents”, arXiv:2602.16346 (2026). Verified on arXiv (STING expansion, multi-turn and
  multilingual scope).
- Wright et al., “Agent Lifecycle Toolkit (ALTK): Reusable Middleware Components for Robust AI
  Agents”, arXiv:2603.15473 (2026). Verified on arXiv and the project's official documentation.
- DFAH is sourced to IBM Client Engineering's public `output-drift-financial-llms` repository; it
  is treated as a reference implementation, not as a peer-reviewed paper or a failure taxonomy.
- Bernstein is sourced to the project's own published introduction; it is treated as a product
  comparator, not an academic paper.

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
3. **A 63-case non-regression harness over sourced or explicitly project-originated failures.**
   Ten categories, three languages, machine-checked pass criteria, replayed
   against the live graph nightly in CI and per agent on demand, with a
   two-level release gate (non-derogable security floor + per-agent domain
   threshold, waivers governed and currently zero). This turns "we tested it"
   into a continuously-enforced contract.
4. **Transparent test reporting.** The README documents the tests that pass *and*
   the tests that fail, with root causes. The evaluation contract is enforced in
   CI on every push, which keeps the assembly honest and current.
