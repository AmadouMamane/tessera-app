"""Build the frontend's bundled eval snapshot FROM the repo, so the two cannot diverge.

`webapp/frontend/lib/eval-sweep.ts` resolves its sources in two ways: the live repo
(`eval/reports/sweep/`, `eval/baselines/`, `eval/failures/`) when a `pyproject.toml` sits above
the working directory, and `data/eval/` otherwise. The second branch is not a fallback for
convenience — **it is the only source inside the standalone image**, which is what production
serves. There is no `pyproject.toml` above `/app`.

Both copies were tracked, and both were maintained BY HAND. Measured on 2026-08-05, on the
serving container:

* **36 of the 63 catalogue cases carried stale `pass_criteria`** — including every case corrected
  the day before. The eval screen therefore displayed criteria the grader no longer applies.
* **`discrimination.json` was absent entirely**, so the catalogue-power surface answered
  `not-measured`. The code is honest — that branch means "nobody ran the measurement" — but the
  measurement HAD been run; it simply was not shipped. An honest reader over a dishonest bundle
  still misinforms.
* `null-control.json` was the 13 July copy: three verdicts apart from the live baseline, and no
  `grader_criteria_sha` at all, so nothing downstream could tell which ruler had scored it.
* Every sweep report differed, and five of seven disagreed about
  `grader_criteria_unstampable` — the *blind-run* list. The shipped copy named FEWER blind runs
  than the repo's, which is the over-claim direction: a surface reporting more coverage than was
  measured.

No verdict differed, which is the only reason this was a drift and not an incident.

So the bundle stops being a second original and becomes a **derived artefact**. This script
writes it; `tests/unit/test_eval_bundle_is_derived.py` fails when what is committed is not what
this script would produce. Regenerate with ``make eval-bundle`` after any eval change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "webapp" / "frontend" / "data" / "eval"
SWEEP_SRC = ROOT / "eval" / "reports" / "sweep"
BASELINES = ROOT / "eval" / "baselines"
FAILURES = ROOT / "eval" / "failures"

#: Baselines the frontend reads by name (`eval-sweep.ts::sources`). `discrimination.json` is here
#: because its ABSENCE was indistinguishable from "not measured yet" on the served surface.
_BASELINES = ("null-control.json", "discrimination.json")


def catalogue() -> list[dict[str, object]]:
    """The 63 failure cases as one array, ordered by file name (= by case id)."""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FAILURES.glob("*.json"))
        if path.name != "_schema.json"
    ]


def planned() -> dict[str, str]:
    """Every bundled path mapped to the exact bytes it must hold.

    Returned rather than written, so the ratchet can compare without a temporary directory —
    a check that regenerates into the tree it is judging would pass by having changed it.
    """
    files: dict[str, str] = {
        "catalogue.json": json.dumps(catalogue(), ensure_ascii=False, indent=2) + "\n",
        "case-schema.json": (FAILURES / "_schema.json").read_text(encoding="utf-8"),
    }
    for name in _BASELINES:
        source = BASELINES / name
        if source.exists():
            files[name] = source.read_text(encoding="utf-8")
    for report in sorted(SWEEP_SRC.glob("*.json")):
        files[f"sweep/{report.name}"] = report.read_text(encoding="utf-8")
    return files


def write() -> list[str]:
    """Write the bundle and return the paths that changed."""
    wanted = planned()
    (BUNDLE / "sweep").mkdir(parents=True, exist_ok=True)
    changed = []
    for rel, content in wanted.items():
        target = BUNDLE / rel
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            target.write_text(content, encoding="utf-8")
            changed.append(rel)
    # A file the repo no longer has must not survive in the bundle: a stale run kept there is a
    # run the served surface counts and the gate has never seen.
    for existing in sorted(BUNDLE.rglob("*.json")):
        rel = existing.relative_to(BUNDLE).as_posix()
        if rel not in wanted:
            existing.unlink()
            changed.append(f"- {rel}")
    return changed


def main() -> int:
    """Write the bundle, print what moved."""
    changed = write()
    if not changed:
        print("eval bundle already derived — nothing to write")
        return 0
    print(f"eval bundle rebuilt from the repo — {len(changed)} file(s):")
    for rel in changed:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
