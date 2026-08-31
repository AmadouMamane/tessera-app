# 57. License: AGPL-3.0-only

Date: 2026-08-31

## Status

Accepted. Supersedes [ADR 0002](0002-license-apache-2.md) (Apache-2.0).

## Context

The license has been decided twice, and for six weeks the repository carried neither decision
honestly. [ADR 0002](0002-license-apache-2.md) chose Apache-2.0, resting partly on a citation
that was never verified and turned out false — "`mcp-firewall` is Apache-2.0" when its metadata
says AGPL-3.0-or-later ([ADR 0028](0028-the-firewall-that-never-ran.md) caught it). Then the
publication-gate decision of 2026-07-12 chose **AGPL-3.0-only** and executed it in commit
`6ac502e4` ("superseding ADR 0002") on two grounds, either sufficient: **CHOSEN** — AGPL deters
the one threat a license can deter — and **REQUIRED** — a Tessera distribution was a combined
work with AGPL `mcp-firewall`, so distributing under Apache terms was never a lawful option.

That commit never landed. It lives on `claude/gate-publication`, six commits ahead and ~480
behind `main`, frozen since 2026-07-13. The next day, ADR 0028 landed on `main` and removed
`mcp-firewall` entirely — killing the REQUIRED ground ("the distribution carries no AGPL code;
publication and dual-licensing are unblocked") and explicitly *not* deciding the license: its
"current lean" — Apache-2.0 for the extracted `limes` guard package, AGPL-3.0 + commercial for
Tessera's engine — sits under a heading named "What this does not decide". So `main` kept saying
Apache-2.0 on every surface while the operator's acted choice sat on an orphaned branch: the
decision existed, and nothing in force recorded it.

On 2026-08-31 the operator re-affirmed the choice and drew the package boundary explicitly:
Tessera goes AGPL, **`limes` stays Apache-2.0**.

## Decision

The Tessera repository is licensed **AGPL-3.0-only**.

**The surviving ground, now a free choice.** The REQUIRED ground is dead and is deliberately not
part of this decision — since ADR 0028 the distribution carries no AGPL code, so nothing forces
this license; it is chosen. The CHOSEN ground of 2026-07-12 stands: section 13 (Remote Network
Interaction) deters the one threat a license can deter — a competitor offering the engine as a
rival hosted service. Unmodified internal self-hosting is untouched; a *modified* deployment
whose users interact remotely owes those users the Corresponding Source — that is the deterrent
working as designed, and the commercial-license path (ADR 0028's lean) is the answer for
adopters who cannot accept it. Recorded correction from the 12/07 debate, kept so nobody
re-imports the error: AGPL does not reach unmodified internal use, and over-expecting it to was
wrong.

**`-only`, not `-or-later`.** The terms adopted are the terms that were read. A future FSF
version is a different contract; it will not be signed in blank.

**Lawfulness.** One copyright holder (1 802 commits, a single author identity), no external
contributions, and a repository that has been private throughout — nothing was ever distributed
under Apache terms, so no third party holds prior Apache rights to this code. The relicense is
an author's plain prerogative.

**Boundary.** `limes`, the extracted first-party guard package, remains **Apache-2.0** — the
permissive adoption wedge (ADR 0028's lean, now operator-confirmed, 2026-08-31). License flow is
one-way: Apache-2.0 code may be combined into this AGPL work; moving Tessera engine code out
into `limes` is a per-change relicensing act by the sole author, never a copy-paste.

**Mechanics.** `LICENSE` carries the verbatim FSF text — the same copy verified in `6ac502e4`
(canonical markers: title, "Version 3, 19 November 2007", §13, the how-to-apply annex,
34 570 bytes). `pyproject.toml` declares the SPDX id `AGPL-3.0-only` and the AGPLv3 trove
classifier; the frontend `package.json` follows. Every attesting surface changes in the same
commit as this ADR: README badge and License section, the cockpit's system-profile edition
strings (fr/de/en) and `edition` field, the canonical-tree comments (CLAUDE.md, AGENTS.md,
`docs/structure.md`), the architecture diagram's stack line, the ADR index. ADR 0002's Status is
annotated, its body left as the dated record it is.

## Consequences

* The repository is private today: this license binds nobody until distribution. What it fixes
  is the gap — publication now ships under the chosen terms instead of under a decision that
  never landed.
* ADR 0002's reachability argument (banks lifting patterns into closed systems without legal
  review) is consciously traded away for the engine. Patterns stay liftable through `limes`
  (Apache-2.0) and through the documentation — a license covers code, not ideas. Adopters who
  need the engine without AGPL terms are the commercial-license audience.
* Dual licensing survives exactly as long as sole authorship does: **a CLA must be in place
  before any external contribution is merged** (ADR 0028's condition, binding from this ADR on —
  the dual-license option dies the day one external patch lands without it).
* The cockpit's edition string is a baked surface (ADR 0051): the deployed stack keeps answering
  "Reference (Apache-2.0)" until its image is rebuilt. `served-check` will refuse — honestly —
  until the operator redeploys; landing this ADR is not serving it.
* ADR 0002's NOTICE-file discipline lapses with it. Vendored Apache-2.0 code remains
  combinable, keeping its own license and notices.
