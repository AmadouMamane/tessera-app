"""Repo-wide detector for the 'one measurement, several truths' class.

It finds every THRESHOLD literal rendered by a component and every STATUS rule computed
next to it, groups them by the payload field they read, and reports each field that is
rendered with more than one threshold, or more than one displayed expression.

Deliberately blunt: it over-reports rather than under-reports, because the follow-up is a
human read of each group. A detector that silently skips a shape is the bug it hunts.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/amadou/local/apps/tessera-app/tessera/webapp/frontend")

# A threshold as it reaches the screen: "≤ 10%", "≥ 0.80", "= 0", "F1 ≥ 0.90", "< 5%".
THRESHOLD = re.compile(r'["`]\s*(?:[A-Za-z0-9 ]{0,6})?\s*(?:[≤≥<>]=?|=)\s*-?[\d.]+\s*%?\s*["`]')
# A numeric comparison in a status rule: >= 0.9, <= 0.005, > 0.3
COMPARE = re.compile(r"(?:>=|<=|>|<)\s*(0?\.\d+|\d+(?:\.\d+)?)")
# The payload fields a control reads.
FIELD = re.compile(
    r"\b(?:good_rate|toxicity_rate|leak_rate|over_refusal_rate|under_refusal_rate|"
    r"conformance_rate|validity_rate|recall|precision|f1|attack_success_rate|"
    r"recovery_rate|completeness|fallback_rate|coverage|jailbreak_success_rate|"
    r"error_rate|p95|burn_rate|good_is_up|n_recoverable|blockRate|invRate)\b"
)

WINDOW = 6  # lines of context on each side
#: How many unattributed thresholds to print before summarising the rest.
_SAMPLE = 40


def scan() -> dict[str, list[dict[str, object]]]:
    hits: dict[str, list[dict[str, object]]] = defaultdict(list)
    files = [
        p
        for p in ROOT.rglob("*.tsx")
        if "node_modules" not in p.parts and not p.name.endswith(".test.tsx")
    ] + [
        p
        for p in ROOT.rglob("*.ts")
        if "node_modules" not in p.parts and not p.name.endswith(".test.ts")
    ]
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = THRESHOLD.search(line)
            if not m:
                continue
            lo, hi = max(0, i - WINDOW), min(len(lines), i + WINDOW + 1)
            ctx = "\n".join(lines[lo:hi])
            fields = sorted(set(FIELD.findall(ctx)))
            compares = sorted(set(COMPARE.findall(ctx)))
            key = ",".join(fields) if fields else "(champ non identifié)"
            hits[key].append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "line": i + 1,
                    "threshold": m.group(0).strip('"`'),
                    "compares": compares,
                    "snippet": line.strip()[:110],
                }
            )
    return hits


def main() -> int:
    hits = scan()
    divergent = {
        k: v
        for k, v in hits.items()
        if k != "(champ non identifié)" and len({h["threshold"] for h in v}) > 1
    }
    single = {
        k: v
        for k, v in hits.items()
        if k != "(champ non identifié)" and len({h["threshold"] for h in v}) == 1 and len(v) > 1
    }
    unknown = hits.get("(champ non identifié)", [])

    print("=" * 78)
    print(f"SEUILS DIVERGENTS — {len(divergent)} champ(s) rendus avec PLUSIEURS seuils")
    print("=" * 78)
    for field, rows in sorted(divergent.items(), key=lambda kv: -len(kv[1])):
        thresholds = sorted({str(r["threshold"]) for r in rows})
        print(f"\n### {field}   → {len(thresholds)} seuils : {thresholds}")
        for r in rows:
            print(f"    {r['file']}:{r['line']}  «{r['threshold']}»  cmp={r['compares']}")

    print()
    print("=" * 78)
    print(f"MÊME SEUIL, PLUSIEURS SITES — {len(single)} champ(s) (duplication sans divergence)")
    print("=" * 78)
    for field, rows in sorted(single.items(), key=lambda kv: -len(kv[1])):
        print(f"  {field}: {len(rows)} sites, seuil «{rows[0]['threshold']}»")
        for r in rows:
            print(f"      {r['file']}:{r['line']}")

    print()
    print(f"SEUILS SANS CHAMP IDENTIFIÉ : {len(unknown)} (à lire à la main)")
    for r in unknown[:_SAMPLE]:
        print(f"    {r['file']}:{r['line']}  «{r['threshold']}»  {r['snippet']}")
    if len(unknown) > _SAMPLE:
        print(f"    … et {len(unknown) - _SAMPLE} autres")

    Path(sys.argv[1] if len(sys.argv) > 1 else "/dev/null").write_text(
        json.dumps(hits, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
