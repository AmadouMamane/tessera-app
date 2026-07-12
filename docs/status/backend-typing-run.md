# Backend typing — the fleet pilot (2026-07-12)

Audit P1.4 `untyped-api`: **10 `response_model` on ~174 routes**. Typing the API is what unlocks
the OpenAPI→zod codegen, closes the front/back validation gap, and makes the read-plane
classification (the open P1 from the security seam) tractable at all.

**Status: HALT for ratification.** The pattern is proven end to end on 6 routes; two design
questions must be answered before it is replicated across ~164 more. Base: `origin/main` =
`ba62652d`. Twice-green local (CI still billing-blocked).

---

## What the brief assumed, and what was actually there

**The front does not cast — it already validates, and its schemas are faithful.** There are
**zero `as` casts** in `client.ts`. 101 of its 132 `request()` calls pass a hand-written zod
schema, `request()` runs `safeParse` and **throws** on mismatch. Running the **real backend
output** through the **real front schemas** (15 routes, live): all 15 parse, and only **5 field
paths** are silently stripped across the entire domain.

So the validation gap is not "the front doesn't check". It is subtler and worse.

---

## The three findings

### 1. `available: false` means two different things, under one key

Sixteen of the eighteen fleet handlers are written like this:

```python
try:
    return {"available": True, **compute(lang)}
except Exception:
    return {"available": False}          # honest-empty: never break the page
```

Every route therefore has **two shapes**. But `available` is *also* used, nested, as a **business
fact** — and there it arrives **with its full payload**:

| object | `available: true` | `available: false` | |
|---|---|---|---|
| the 16 routes, `agent-evaluations.judge` | 7–19 keys | **1 key** | exception degrade → **union** |
| `fleet.agents[].release` | 20 keys | **20 keys** | *"Éval non exécutée"* → **`bool`, not a union** |
| `north_star.trend` | — | 4 keys | *"insufficient_data"* → **`bool`** |

**The first draft of the models made every `available` a union** — the obvious reading of the
name — and FastAPI therefore **silently dropped 20 fields on every agent of the flagship route.**
Nothing raised. Nothing logged. The round-trip test is what caught it.

That is the entire argument for deriving models from **observed output** rather than from a
plausible reading of the code, and it is why this was a pilot rather than a sweep.

### 2. The front's schemas model the union as "everything optional" — which guarantees nothing

13 of the 14 hand-written schemas accept `{available: false}` **by having made every payload
field optional**. They therefore cannot catch a backend that drops `agents` entirely. They are
validation in name.

### 3. And once, it is wrong in the other direction — a live bug

`AccessOverviewSchema` **rejects** `{available: false}` (12 required fields missing). `request()`
throws `ApiError` on a rejected schema. So when `/observability/access` degrades, **the front
breaks the page on the exact response that exists so the page would not break.** The honest-empty
doctrine is defeated end to end, and nobody knew.

---

## The pattern

**A discriminated union on `available`, and only where the observed `false` shape collapses.**

```python
class FleetUnavailable(BaseModel):
    available: Literal[False]          # no default: a discriminator with a default is not one

class FleetPayload(BaseModel):
    available: Literal[True]           # ...declared AT ITS OBSERVED POSITION, see below
    agents: list[FleetAgentsItem]      # REQUIRED — `available: True` now GUARANTEES it
    ...

@router.get("/observability/fleet", response_model=FleetPayload | FleetUnavailable)
```

Derivation, mechanised in a script and verified by test:

1. **Sample the route across its real parameter space** — 3 languages × 6 agents × periods → 123
   live responses. Optionality cannot be learned from one call.
2. A key present in every payload sighting → **required**; missing from any → `| None = None`;
   ever `null` → `| None`; **never seen with a value → `None`** (honest-empty preserved, not typed
   away — 6 such fields exist).
3. The degraded sighting is **excluded from the payload's requiredness arithmetic**, or every
   field becomes optional and the union guarantees nothing.
4. **No `extra="forbid"`.** The shapes are observed, not proven exhaustive.

### Two traps the pattern had to be taught

* **The discriminator must be REQUIRED.** `available: Literal[True] = True` makes it *optional*
  in OpenAPI, and an optional discriminator discriminates nothing — the generated zod union
  degenerates.
* **Field order is part of the contract.** Pydantic serialises in declaration order, so hoisting
  the discriminator to the top reorders the JSON keys. Semantically null, textually not — and the
  constraint is byte-identity. `available` is declared **where it was observed**.

---

## The proof

| | |
|---|---|
| **Byte-identical** | 31 captured live responses replayed through the models; `model_dump(mode="json")` compared as a **string** to the captured body. Keys, order, values, nulls. |
| **Strips nothing** | key-set comparison, separately — because a dropped field is not an error, it is a silence. |
| **The degrade survives** | the compute is **forced to raise**, through the real router: `/observability/fleet` still answers **200 `{"available": false}`**. This path never appeared in the 123 samples (every compute succeeded), so it is proven by construction, not by observation. |
| **Existing suite** | 1787 backend tests green (+46), 198 frontend (+13). |

---

## The codegen, on real types

`scripts/generate_zod.py` — 200 lines, no dependency — emits
`webapp/frontend/lib/api/generated/fleet.ts` from the backend's own OpenAPI.

* **6 routes emitted**, 12 explicitly **skipped and named**: a route with no `response_model`
  yields `z.record(z.unknown())` — a schema that validates nothing *while `request()` reports the
  response as validated*. A rubber stamp the front cannot see through is worse than no schema.
* A ratchet (`tests/unit/test_zod_codegen.py`) regenerates and diffs: **a generator whose output
  is not pinned is a generator nobody re-runs.**
* The generator runs `biome format` on its own output, so the formatter and the ratchet cannot
  fight.

**Verified against reality** (`lib/api/generated/fleet.test.ts`, 13 tests): the generated schemas
parse every captured live response **stripping nothing**, accept `{available: false}` (**the
`access` bug, fixed**), and **reject** `{available: true}` with no payload — the guarantee no
hand-written schema in this domain can give.

---

## Cost, measured

| | |
|---|---|
| Models per route | **11.7** (70 models / 6 routes) — mechanically generated, hand-verified |
| Domain total | 18 routes, **161 distinct object shapes** |
| Backend diff | +860 lines of models (generated), 6 × `response_model=` |
| Sampling | 123 live responses, ~4 min |
| Human time | the *generation* is minutes; the **adjudication** is the cost — see finding 1 |

Extrapolated to ~164 routes: **≈1900 models**. That number is only tolerable because they are
generated and machine-verified. Hand-writing them would be indefensible.

---

## Genuinely dynamic shapes — the operator rules

**None in this domain.** The two candidates my heuristic flagged were both false positives:
`agent-evaluations.judge` is a stable 7-key object (it was flagged because it *degrades*), and
`agent-configurations.status.rows[]` is a heterogeneous row object (`{badge,label,value}` /
`{label,live,online,value}` / `{label,value}`), not a data-keyed map. **Zero `dict[str, object]`
is legitimate here.** Whether that holds across the other 156 routes is unknown; the sampler
reports open-key maps, so the question is answerable per domain rather than by opinion.

---

## HALT — the two questions before scaling

**Q1. The front migration is a real refactor, and it is the point.** Wiring `client.ts` to the
generated schemas does not compile: the declared return types come from the *old* hand-written
`z.infer` (`{available: boolean; agents?: …}`), and the generated type is a discriminated union.
**9 files** consume the 6 pilot client functions and would each have to handle `available: false`
explicitly — which is the correct behaviour and is what fixes the `access` bug. **I reverted the
client wiring**; the generated module and its tests are checked in and pure gain. *Do we migrate
the front domain by domain, alongside the backend typing?*

**Q2. The generated schema is stronger on structure and WEAKER on value domains.** The
hand-written zod carries **97 `z.enum` / `z.literal`** — `tone: "warning" | "danger" | "neutral"`,
`type: "systeme" | "metier"`, `status: "active" | … | "disabled"`. The backend declares `str`,
so the generated schema says `z.string()` and **that precision is lost**. Replacing the
hand-written schemas as-is would be a **regression in type strength**, traded for a gain in
structural strength.

The fix is to make the backend declare what it already knows: `Literal["warning", "danger",
"neutral"]` where the value set is closed. The sampler can propose the candidates (a string field
whose observed values form a small closed set), but **whether a closed observed set is a closed
domain is a judgment**, not an observation — that is exactly the class of guess this pilot
refuses to make on its own.

**Recommendation:** answer Q2 first (it changes the models), then scale **one domain per lot**,
front and back together, with the sampler + generator + byte-identity ratchet as the pattern.
