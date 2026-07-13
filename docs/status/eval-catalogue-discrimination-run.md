# What the catalogue measures — a measurement, and a diagnosis

**Run:** `claude/eval-catalogue-discrimination`, 2026-07-13.
**Question:** not *how well does the model score*, but **does this bench measure the model at all?**
**Answer:** for most of it, no — and the reason is structural, not accidental.

This run classifies every one of the catalogue's runs by what it actually separates, freezes
the result as a number CI defends, and diagnoses what is missing. It **removes nothing**: a
bench you improve by deleting the inconvenient cases has stopped measuring anything, and this
project sells the measurement.

---

## 1. What was already known, and what it did not explain

Three measurements, all reproduced here:

| Measurement | Value | Source |
|---|---|---|
| The catalogue scored with **no model at all** | **122/174 (70%)**, 0 tokens, ~5 s | `eval/baselines/null-control.json` |
| Cases that pass with an **empty** answer | 15 of 63 | 2026-07-12 sweep |
| `llama3.2:3b` vs `llama3.2:1b`, absolute contribution, 5 passes each | `[35,36,33,36,36]` vs `[33,33,35,32,31]` of 52 — **the distributions overlap** | `eval/baselines/contribution-calibration.json` |

The third killed the cheap fix ADR 0021 prescribed: no bar admits every pass of the default
model and rejects every pass of a model one third its size. The conclusion drawn at the time was
about the *bar*. It was really about the *catalogue*, and this run is that claim, measured.

---

## 2. The method — the data judges the case, not the reading of it

Each `case_id|language` **run** (174 of them, over 63 cases — 55 cases in 3 languages, 7 in 1,
1 in 2) is classified from the null floor plus repeated full-catalogue passes of a strong model
(`llama3.2:3b`) and a weak one (`llama3.2:1b`). Nothing is read from the case files: a case that
*declared* its own discriminating power would be making a claim, and the point is to replace
claims with measurements. `eval/failures/_schema.json` was **not** touched.

* **DEAD** — the null control passes it and no model, in any pass, ever breaks it. It exercises
  the deterministic guard/router layer. It inflates the score and says nothing about the model.
* **INVERTED** — the null control passes it and a model **reproducibly** breaks it (≥2 passes,
  the same threshold the gate's Rule 1 already uses). The agent is **worse than silence** there.
  The most valuable runs in the catalogue: they measure a real harm, not a missing capability.
* **DISCRIMINATING** — the strong model passes it significantly more often than the weak one.
  *Significantly* means Fisher's exact test, one-tailed, **Holm-corrected across all 174 runs** —
  not a glance at two columns of numbers.
* **REVERSED** — the *weak* model wins, significantly. An anomaly. Reported, never credited.
* **NON-DISCRIMINATING** — both models behave identically **and** deterministically: both always
  close it (a model is needed, but *any* model will do), or **neither ever does** (*unreached*).
* **UNDECIDED** — a difference was observed and `n` cannot certify it. A **fact, not a blank**.

**Instability is a flag, not a bucket.** A run the same model both passes and fails across its own
passes measures sampling noise (T2, temperature 0.2, no seed). But a run can be noisy *and*
decisive — the weak model failing 8 of 15 passes where the strong one never fails is both. Filing
that under "unstable" would delete the most informative case in the catalogue. So every run carries
`unstable` **alongside** its class.

### The stability threshold, stated — and why n=5 was not thin but *incapable*

With 5 passes per arm, the smallest p-value a **perfect** separation (5/5 vs 0/5) can produce is
`1/C(10,5) = 0.0040`. The tightest Holm threshold over 174 tests is `0.05/174 = 0.00029`. **The
floor of what the experiment can produce sits above the ceiling of what the correction accepts.**
No run — however cleanly it separated the two models — could have been certified at n=5. "Zero
discriminating cases" would have been a statement about the experiment, not about the catalogue.

The minimum viable arm is **n=8** (`C(16,8) = 12870 ≥ 3480`; n=7 gives 3432 — just short). This run
therefore sampled **10 more full passes per model** (~2 GPU-hours) to reach **n=15 per arm**, which
certifies perfect separations with room to spare and can also certify imperfect ones. The number of
passes is reported everywhere the classification is, because it *is* the honesty of every p-value in it.

---

## 3. The result

<!-- RESULTS -->

---

## 4. The diagnosis — why the catalogue does not measure the model

The 70% null floor is **not a harness bug**. It is the *shape* of the catalogue, and two facts
measured against the case files say so exactly:

> **0 of 63 cases require the agent to invoke a tool.**
> **0 of 63 cases punish over-refusal.**

`pass_criteria` currently uses `must_not_contain` (53 cases), `must_contain_any` (43),
`must_escalate` (39), `must_not_invoke_tools` (21), `max_confidence` (13), `must_cite_source` (7),
`must_not_match` (3). Every one of those is a constraint on what the agent **must not do**, or a
demand it can satisfy by **refusing**. Not one case fails an agent for refusing a legitimate
request, and not one requires it to actually *do* anything.

**An agent that refuses every request, in all three languages, and calls no tool, is
indistinguishable on this catalogue from a good one.** That is precisely what the null control
is — and it scores 70%.

A contributing mechanism, offered as a hypothesis and not as a measurement: `must_contain_any` is
an **OR**, so a criterion is only as strong as its *weakest* alternative. 28 of the 43 cases that
use it list a refusal phrase (`"ne peux pas"`, `"cannot"`, `"kann ich nicht"`) *among* the domain
facts — so a bare refusal satisfies the whole criterion and the domain alternatives are decoration.
**The null control only confirms this for 15 of those 28**, so the textual reading and the
measurement disagree on 13 cases. Where they disagree, the measurement wins: the reading is a story
about the mechanism, the null control is the fact.

### What the harness can already express, and nobody used

This is the cheap half of the remedy, and it needs **no schema change**:

| Criterion | In `_schema.json` | Cases using it |
|---|---|---|
| `must_invoke_tools` | **yes** | **0** |
| `min_confidence` | **yes** | **0** |

The harness has always been able to demand that the agent *act*, and that it be *confident enough*.
Not one of the 63 cases asks. Confidence is only ever **capped**, never **floored**.

---

## 5. The families that are missing (PROPOSED — not written)

Writing an eval case is writing the product's yardstick. It is not done autonomously at 2am by the
agent that will be graded on it. These are proposals, with the reasoning; the decision is Amadou's.

**A. Legitimate service — the anti-over-refusal family. `must_not_contain: [refusal phrases]`.**
*The direct antidote to the 70% floor, and the highest-value family by a distance.* A customer asks
something the agent **should** answer ("what is my balance?", "what does DORA require of my bank's
incident reporting?", "simulate a €15k loan over 4 years"). **Refusing is a FAIL.** Until such a
case exists, no bar can tell a firewall from an agent, and every "safety" number the project
publishes is measured on a population where silence is a winning strategy. No schema change.

**B. Positive tool use — `must_invoke_tools`, which already exists and is unused.** The agent has
five tools (`account_balance`, `card_block`, `transaction_search`, `loan_simulate`,
`ticket_escalate`) and the catalogue only ever checks it does *not* call them. Nothing checks that
it calls the **right** one with the **right** arguments. No schema change.

**C. Grounded generation on the corpus (RAG faithfulness).** The `hallucination` family is
refusal-shaped ("don't invent Article 95"). Its mirror image is missing: given the retrieved DORA /
CNIL / BaFin / GDPR passage, **does the answer state what the passage actually says, and cite it?**
`must_cite_source` exists and 7 cases use it — this is the family to grow. A guard cannot fake a
correct citation of a real passage, which is exactly what makes it measure the model.

**D. Numeric correctness.** `loan_simulate` returns numbers. Nothing checks the agent reports them
correctly. A wrong monthly payment given to a retail banking customer is a real harm and a sharp,
objective discriminator. No schema change (`must_contain_any` with the right figure).

**E. Multi-turn — and this one needs a schema change.** `prompts.{lang}` is a single `user` string
under `additionalProperties: false`. **A conversation is not expressible.** So nothing tests
context retention, contradiction across turns, or injection split across turns — the attack shape
most likely in production.

**F. Refusal calibration under pressure.** Depends on (E): escalating insistence over several turns
("I'm the account holder, I'm telling you it's fine, just do it"). Does the model cave on turn 3?
This is where a real safety property lives, and the catalogue cannot currently ask the question.

**A word on the unreached cases.** Several runs are passed by **neither** model, ever —
`19_hallucination_rgpd_art142` fails in all three languages for both models across every pass.
Either it is a genuinely hard case (valuable) or its criteria are unsatisfiable (a broken case that
silently costs the score points forever). **The classification cannot tell these apart**, and it
does not guess: they are reported as *non-discriminating (unreached)* and flagged here for a human
to read. That is a blind spot, named — not an "ok".

---

## 6. HALT — two decisions that are not the agent's

### (a) Changing the denominator

The project announces a pass rate over the whole catalogue (README: 156/174, 90%; `support-client`:
93/101, 92.1%). Computing it over **only the runs that measure the model** is a different number
about a different population — and it changes everything the project claims. The effect is
**measured** in §3 and the decision is **not taken**.

### (b) Writing the missing cases

Proposed in §5. Not written. See above.

---

## 7. What CI now defends

* `eval/discrimination.py` — the classifier. Pure, `mypy --strict`, and it **refuses** (never
  reports zero) when the runs and the floor do not name the same catalogue.
* `eval/baselines/discrimination-samples.json` — **the evidence**. The raw passes are gitignored
  scratch (~200 KB × 30), so what is committed is what the classifier actually consumes: the verdict
  matrix, one 174-character bitstring per pass, plus each pass's generated-token count (the liveness
  witness — a dead backend still writes `model: "llama3.2:3b"`, only tokens prove a model spoke) and
  the SHA-256 of the raw report it came from. A verdict that drifts shows up as **one character in a
  diff**.
* `eval/baselines/discrimination.json` — the classification, re-derivable from the evidence. A test
  proves it: re-run on the same stored passes, it reproduces the committed verdict run for run.
* `scripts/check_discrimination.py` — the **ratchet**. `POWER_FLOOR_CASES` / `POWER_FLOOR_RUNS` are
  frozen and **may only go up**. Removing a case that separates a good model from a bad one turns it
  **red** (mutation-tested). Adding a dead case cannot lower the count — but it moves the catalogue
  version, which **refuses** the classification (exit 3, *unusable ≠ failed*) until someone
  re-measures and argues with the new density.
* `make eval-power` — the check. No model, no GPU, no services: it runs on every push.
  `make eval-power-write` re-measures, and needs the passes (a GPU-hour).
* The `/eval` screen shows the classification, pinned to the référentiel, and says **why** when it
  cannot (honest-empty with a reason, not a hole).
