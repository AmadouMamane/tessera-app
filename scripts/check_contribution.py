#!/usr/bin/env python
"""Grade a model on its contribution over the null floor (the eval gate).

The absolute pass rate is not the grade and cannot be: llama3.2:3b and gemma3:27b both
score 157/174, yet one of them breaks a case the agent passes with no model at all. This
gate reads the delta instead (see :mod:`eval.contribution`):

* Rule 1 — the model must break **zero** of the 122 runs the null control passes. A break
  is only fatal once **reproduced**: sampling is stochastic, so every candidate is replayed
  three times and confirmed on a majority. Measured over five full passes of llama3.2:3b
  (2026-07-13): the real regression breaks 4 times in 5, every noise candidate exactly 1 in
  5 — so a single replay, which is what this did before, decides a release on one sample of
  a coin that lands the wrong way one time in five, in BOTH directions.
* Rule 2 — the model must close at least ``--min-contribution`` of the 52 runs the null
  control fails. That is the only population where a model can prove anything.

An **agent-scoped** report (one carrying an ``eval_set``) is graded against that set's
OWN floor — the null control restricted to the set's cases (ADR 0021 §3a). Two things
follow, and both are load-bearing: the restriction is *required* (Rule 2's denominator is
read off the baseline, so an unrestricted floor measures a twenty-case set against the
catalogue's fifty-two-run population), and once restricted, ``--min-contribution`` no
longer applies — 30 was reasoned against that 52-run population, and rescaling it would
invent the very kind of number ADR 0021 removed. A per-set run therefore gates on **Rule 1
alone**, and its contribution is measured and printed. Gating it needs the set's own
history: ADR 0021's debt (b).

Exit codes — a refusal and a failure are different facts and never share one:

* ``0`` PASS — the model was graded and cleared the rules.
* ``1`` BLOCK — the model was graded and failed. A verdict *on the model*.
* ``2`` INCONCLUSIVE — a candidate break could not be replayed (no model answered), so it
  can be neither confirmed nor cleared.
* ``3`` REFUSED — the model was **not graded at all**: the floor cannot be shown to apply
  to this run (the catalogue moved, or a side does not say which catalogue it means). The
  absence of a verdict, not a bad one. Same code, and the same reason, as the gate
  witness's VOID: unusable is not the same as failed.

Usage:
    uv run python scripts/check_contribution.py \\
        --report eval/reports/sweep/gemma3-27b.json --min-contribution 30
    uv run python scripts/check_contribution.py \\
        --report eval/reports/local/latest_recouvrement.json   # per-set: rule 1 gates
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from eval.contribution import (
    MIN_CONTRIBUTION_UNCALIBRATED,
    UNCALIBRATED_NOTICE,
    evaluate_contribution,
    floor_populations,
    restrict_baseline,
)
from eval.ratchet import Baseline, floor_mismatch, load_baseline, model_spoke, report_verdicts
from eval.sets import catalogue_categories, load_eval_set

NULL_BASELINE = Path("eval/baselines/null-control.json")

#: Exit code for "the model was NOT graded". Deliberately not 1: a BLOCK is a verdict on
#: the model, a REFUSAL is the absence of one, and a caller that cannot tell them apart
#: will eventually report "the model failed" about a run nobody judged.
EXIT_REFUSED = 3


#: A replay in which no model answered proves nothing — but it is usually transient (a
#: model swap under memory pressure, observed live during the first sweep), not a dead
#: backend. Retry before giving up, rather than reporting a whole run inconclusive on one
#: hiccup.
_REPLAY_ATTEMPTS = 3

#: How many times a candidate break is replayed, and how many failures confirm it.
#:
#: MEASURED, not chosen (2026-07-13, `make eval-noise`): five full-catalogue passes of
#: llama3.2:3b at temp 0.2 with no seed. `56_policy_violation_disparage_bank|de` — the real
#: regression — broke in **4 of 5** passes; every other candidate broke in exactly **1 of
#: 5**. So a break is roughly p≈0.8 when real and p≈0.2 when noise.
#:
#: A SINGLE replay (what this did before) therefore falsely CLEARS the real regression ~20%
#: of the time and falsely CONFIRMS noise ~20% of the time — it is barely better than a coin
#: weighted the right way. Best of three lifts that to ~90% / ~10% against the measured
#: frequencies, and costs three single-case runs (a few seconds), not three catalogues.
_CONFIRMATION_REPLAYS = 3
_CONFIRMATION_FAILURES = 2


def _replay_once(case_id: str, language: str, model: str, report: Path) -> bool | None:
    """One replay. True/False = the case passed/failed; None = no model answered."""
    subprocess.run(
        [
            sys.executable,
            "scripts/run_eval.py",
            "--case",
            case_id,
            "--lang",
            language,
            "--model",
            model,
            "--report",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if not report.exists():
        return None
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not model_spoke(payload):
        # 0 generated tokens: the model never answered, so this replay neither confirms
        # nor clears the break. Never treat it as a clearance — a dead backend would
        # otherwise absolve every regression at once.
        return None
    return report_verdicts(payload).get(f"{case_id}|{language}")


def _replay(case_id: str, language: str, model: str, tmp: Path) -> bool | None:
    """Replay a case once, retrying past transient no-answer runs. None = still inconclusive."""
    tmp.mkdir(parents=True, exist_ok=True)
    for attempt in range(_REPLAY_ATTEMPTS):
        report = tmp / f"{case_id}_{language}_{attempt}.json"
        verdict = _replay_once(case_id, language, model, report)
        if verdict is not None:
            return verdict
        sys.stdout.write("(no model answer, retrying) ")
        sys.stdout.flush()
    return None


def _confirm_breaks(candidates: list[str], model: str) -> tuple[set[str], list[str]]:
    """Replay each candidate break ``_CONFIRMATION_REPLAYS`` times; confirm on a majority.

    Best-of-three, not best-of-one. The measured break frequencies (see
    ``_CONFIRMATION_REPLAYS``) are p≈0.8 for the real regression and p≈0.2 for noise, so a
    single replay decides a release on one sample of a coin that lands the wrong way one
    time in five — in BOTH directions.
    """
    confirmed: set[str] = set()
    inconclusive: list[str] = []
    with tempfile.TemporaryDirectory(prefix="tessera-reproduce-") as raw:
        tmp = Path(raw)
        for key in candidates:
            case_id, language = key.split("|", 1)
            sys.stdout.write(f"  replaying {key} ({_CONFIRMATION_REPLAYS}x) … ")
            sys.stdout.flush()
            verdicts = [
                _replay(case_id, language, model, tmp / str(i))
                for i in range(_CONFIRMATION_REPLAYS)
            ]
            if any(v is None for v in verdicts):
                # A replay nobody could get an answer out of neither confirms nor clears.
                # Never treat it as a clearance: a dead backend would absolve every
                # regression at once.
                inconclusive.append(key)
                sys.stdout.write("no verdict (a replay got no model answer)\n")
                continue
            failures = sum(1 for v in verdicts if v is False)
            if failures >= _CONFIRMATION_FAILURES:
                confirmed.add(key)
                sys.stdout.write(
                    f"failed {failures}/{_CONFIRMATION_REPLAYS} — CONFIRMED regression\n"
                )
            else:
                sys.stdout.write(
                    f"failed {failures}/{_CONFIRMATION_REPLAYS} — sampling noise, not counted\n"
                )
    return confirmed, inconclusive


def _floor_for(report: dict[str, Any], baseline: Baseline) -> tuple[Baseline, bool]:
    """Return (the floor to grade against, whether it is an agent set's own floor).

    An agent-scoped report is graded against the null control **restricted to its set**
    (ADR 0021 §3a). Restricting is not cosmetic: Rule 2's denominator is read off the
    baseline, so an unrestricted floor would measure a twenty-case set against the
    catalogue's fifty-two-run population and under-report its contribution by
    construction.
    """
    slug = str(report.get("eval_set") or "")
    if not slug:
        return baseline, False
    eval_set = load_eval_set(slug)
    return restrict_baseline(baseline, set(eval_set.effective_case_ids)), True


def main(argv: list[str] | None = None) -> int:
    """Exit code is the gate verdict."""
    parser = argparse.ArgumentParser(description="Grade a model on its contribution.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=NULL_BASELINE)
    parser.add_argument(
        "--min-contribution",
        type=int,
        default=None,
        help=(
            "Rule 2's bar: how many of the floor-failing runs the model must close. "
            f"Defaults to {MIN_CONTRIBUTION_UNCALIBRATED} for a CATALOGUE run — a weak-model "
            "floor, NOT calibrated (see eval.contribution.UNCALIBRATED_NOTICE). For an "
            "AGENT-SCOPED run it defaults to no bar at all: 30 was reasoned against the "
            "catalogue's 52-run population and rescaling it to a smaller set would invent a "
            "number. Rule 1 still gates; Rule 2 is measured and reported."
        ),
    )
    parser.add_argument(
        "--no-reproduce",
        action="store_true",
        help="Skip the replay pass. Every candidate break then counts (fails closed).",
    )
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not model_spoke(report):
        sys.stderr.write(
            f"no model spoke in {args.report}: 0 output tokens. A modelless run has no "
            f"contribution to grade.\n"
        )
        return 1

    # Restrict FIRST, then check the version. An agent-scoped run is scored against its own
    # set, so its catalogue_version is that set's (`28-990f1447`), never the full
    # catalogue's (`63-071edbdc`) — comparing it to the unrestricted floor would refuse
    # every legitimate per-set run. `restrict_baseline` re-derives the floor's identity from
    # the cases it actually holds, which is what makes the two comparable at all.
    try:
        baseline, per_set = _floor_for(report, load_baseline(args.baseline))
    except ValueError as exc:  # the floor holds NO run for this set — a moved catalogue
        sys.stderr.write(f"[contribution-gate REFUSED] NOT GRADED — {exc}\n")
        return EXIT_REFUSED

    # And refuse BEFORE the replay pass: replaying candidate breaks against a floor that
    # cannot judge this run spends ~20 minutes of model time to produce a number with no
    # referent.
    stale = floor_mismatch(baseline, report)
    if stale is not None:
        sys.stderr.write(
            f"[contribution-gate REFUSED] NOT GRADED — this floor cannot judge this run:\n"
            f"  - {stale}\n"
            f"  floor: {args.baseline}"
            + (f" restricted to set {report.get('eval_set')!r}" if per_set else "")
            + f" → catalogue {baseline.catalogue_version!r}\n"
            f"  run:   {args.report} → catalogue "
            f"{str(report.get('catalogue_version') or '') !r}\n"
            f"No lift is reported: every rule counts against a population that no longer "
            f"exists.\nRegenerate the floor with `make eval-null-write` and commit the diff.\n"
        )
        return EXIT_REFUSED

    min_contribution = args.min_contribution
    if min_contribution is None and not per_set:
        min_contribution = MIN_CONTRIBUTION_UNCALIBRATED
    if per_set:
        sys.stdout.write(
            f"agent-scoped report (set '{report.get('eval_set')}'): grading against that set's "
            f"OWN floor — {baseline.passed}/{baseline.total} runs the null control passes there"
            + (
                ".\n"
                if min_contribution is None
                else f", with an EXPLICIT rule-2 bar of {min_contribution} (yours, not derived).\n"
            )
        )
    model = str(report.get("model") or "")
    run = report_verdicts(report)
    floor_pass, _ = floor_populations(baseline)
    candidates = sorted(k for k in floor_pass if run.get(k) is False)

    confirmed: set[str] | None = None
    if candidates and not args.no_reproduce:
        sys.stdout.write(
            f"{len(candidates)} candidate floor regression(s) — replaying to separate a real "
            f"regression from sampling noise:\n"
        )
        confirmed, inconclusive = _confirm_breaks(candidates, model)
        if inconclusive:
            sys.stderr.write(
                f"inconclusive replays (no model answered): {', '.join(inconclusive)}\n"
            )
            return 2

    verdict = evaluate_contribution(
        report,
        baseline,
        min_contribution=min_contribution,
        categories=catalogue_categories(),
        confirmed=confirmed,
    )
    sys.stdout.write(verdict.render() + "\n")
    if min_contribution == MIN_CONTRIBUTION_UNCALIBRATED:
        # Print it every time the default bar is used. A number that is not measured must
        # say so at the moment it is applied, not only in a docstring nobody opens.
        sys.stdout.write(f"\n! {UNCALIBRATED_NOTICE}\n")
    if min_contribution is None:
        sys.stdout.write(
            "\n! Rule 2 was MEASURED, not gated: this set's contribution has no bar, because "
            "any per-set bar would be invented rather than measured. What gates here is Rule 1 "
            "— zero regression on the set's own floor. Gating the contribution needs that set's "
            "measured HISTORY (ADR 0021, debt (b)), which does not exist yet.\n"
        )
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
