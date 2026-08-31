# 2. License: Apache-2.0

Date: 2026-05-27

## Status

Accepted (2026-05-27). **Superseded by [ADR 0057](0057-license-agpl-3-0-only.md)** (2026-08-31): the repository license is AGPL-3.0-only. The body below is the dated record of the original choice and its rationale — annotated, not rewritten. Note for the record: the claim below that `mcp-firewall` is Apache-2.0 was false (it is AGPL-3.0-or-later; caught in [ADR 0028](0028-the-firewall-that-never-ran.md)).

## Context

Tessera is published as open source from inception. The choice of license shapes who can use the code, under what conditions, and how the project's contributors are protected against patent disputes. The two mainstream permissive options for a project of this kind are MIT and Apache-2.0. Both allow commercial use, modification, and redistribution; both require attribution. They diverge meaningfully on three points: explicit patent grant, contributor protections, and the precedent set by neighbouring projects.

MIT is shorter (around 170 words) and has no explicit patent clause. A user of MIT-licensed code receives no defensible patent license from the contributors; if a contributor later asserts patent rights against a downstream user, the user has no contractual recourse rooted in the license itself. This was historically tolerated because patent litigation in OSS was rare, but it has become a meaningful concern as AI-adjacent projects increasingly intersect with patent portfolios held by large vendors.

Apache-2.0 (around 11 000 words) includes an explicit patent grant from contributors to users, a defensive termination clause that revokes the patent grant from anyone who sues claiming the code infringes their patents, and an explicit handling of contributor agreements and NOTICE files. It is the license used by TensorFlow, Kubernetes, LangChain, LangGraph, FastAPI, and the majority of recent serious infrastructure-grade Python and AI projects. It is also the license used by `mcp-firewall`, the dependency at the center of Tessera's positioning, which simplifies any future upstream contribution path.

A third option, copyleft licenses like GPL or AGPL, would limit Tessera's reachability for commercial banking adopters who require permissive terms — and Tessera's value as a reference implementation depends on those adopters being able to lift patterns into closed-source production systems without legal review friction. Copyleft is therefore off the table.

## Decision

Tessera is released under the Apache License 2.0. The `LICENSE` file at the repository root contains the unmodified text of the license. The `pyproject.toml` declares `license = "Apache-2.0"` using the SPDX identifier. Each source file may carry a short SPDX header (`# SPDX-License-Identifier: Apache-2.0`) but a per-file header is not required at this stage.

Contributors retain copyright in their contributions. The repository does not require a separate Contributor License Agreement at this stage; the implicit license-in license-out grant under section 5 of Apache-2.0 is sufficient for a project of this size. If the project grows beyond a single maintainer and starts accepting substantial third-party contributions, the decision to introduce a CLA will be recorded in a follow-up ADR.

## Consequences

Adopters can use Tessera in commercial systems without legal friction, including banks and financial institutions that maintain strict OSS review boards — these adopters are the project's target audience for the reference-implementation framing. Contributors and the project itself are protected by the patent termination clause against retaliatory patent assertions. Alignment with `mcp-firewall` and the broader AI-infrastructure OSS ecosystem reduces friction for upstream PRs and for citation cross-references.

The cost is a more verbose `LICENSE` file and the discipline of maintaining a `NOTICE` file if and when third-party Apache-2.0 code is vendored into the repository — none currently, but the convention is recorded here so the response is predictable when the situation arises.
