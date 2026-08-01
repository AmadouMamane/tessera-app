"""C1, corrected: which rendered strings have NO translation mechanism at all.

The first pass counted 780 and was wrong twice over: it split multi-line `pick(locale, fr, de,
en)` calls across lines and flagged each argument, and it flagged the in-TS locale catalogues
(`recouvrement-product-copy.ts` and friends), which are catalogues, not hardcoded text.

This version strips both before counting, and carries its own controls: a string known to be
inside a `pick()` must NOT be reported, and a string known to be hardcoded MUST be.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

FRONT = Path("/Users/amadou/local/apps/tessera-app/tessera/webapp/frontend")

# `pick(locale, "…", "…", "…")` — possibly spanning several lines.
PICK = re.compile(r"pick\(\s*locale\s*,.*?\)\s*(?=[,;)\]}\n])", re.S)
# A per-locale copy catalogue, recognised by PATH, never by a stray `fr: {` in the body.
# The first version matched any file containing a locale-keyed object literal and so excluded
# `agent-console.tsx` — a component that genuinely hardcodes strings. The negative control
# caught it, which is the only reason this line is not still wrong.
CATALOGUE_PATH = re.compile(r"(?:-copy\.ts|-fallback-i18n\.ts|/messages/|/i18n/)$|/messages/")

FRENCH = re.compile(r"[«»]|[éèêëàâäîïôöùûüçÉÈÊÀÂÎÔÙÇ]")
COMMENTish = re.compile(r"^\s*(?://|\*|/\*)")
SAFE = re.compile(r"(from \"|from '|import |// |describe\(|it\(|expect\(|console\.)")
LITERAL = re.compile(r"(?:`[^`\n]{4,}`|\"[^\"\n]{4,}\"|'[^'\n]{4,}')")


def sources() -> list[Path]:
    out: list[Path] = []
    for pat in ("*.tsx", "*.ts"):
        out += [
            p
            for p in FRONT.rglob(pat)
            if "node_modules" not in p.parts
            and ".next" not in p.parts
            and "e2e" not in p.parts
            and not p.name.endswith((".test.ts", ".test.tsx", ".spec.ts"))
        ]
    return sorted(out)


def scan() -> tuple[list[dict[str, object]], list[str], int]:
    hits: list[dict[str, object]] = []
    catalogues: list[str] = []
    pick_calls = 0
    for path in sources():
        raw = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(FRONT))
        if CATALOGUE_PATH.search(rel):
            catalogues.append(rel)
            continue
        pick_calls += len(PICK.findall(raw))
        # blank out pick() calls so their arguments are not counted as hardcoded
        masked = PICK.sub(lambda m: " " * len(m.group(0)), raw)
        for i, line in enumerate(masked.splitlines(), 1):
            if COMMENTish.match(line) or SAFE.search(line):
                continue
            for lit in LITERAL.findall(line):
                body = lit[1:-1]
                if not FRENCH.search(body):
                    continue
                if body.startswith(("http", "/", "var(", "--", "@/")):
                    continue
                hits.append({"file": rel, "line": i, "literal": body[:90]})
    return hits, catalogues, pick_calls


def main() -> int:
    hits, catalogues, picks = scan()

    print("CONTRÔLES DE LA SONDE")
    inside_pick = [h for h in hits if h["file"].endswith("historique-tabs.tsx") and h["line"] == 160]
    print(f"  [-] ligne 160 de historique-tabs (DANS un pick) signalée ? {bool(inside_pick)}  → doit être False")
    hard = [h for h in hits if h["file"].endswith("agent-console.tsx")]
    print(f"  [+] agent-console.tsx a des littéraux nus ? {bool(hard)}  → doit être True")
    print()

    print(f"CATALOGUES DE LOCALES EN TS (exclus, légitimes) : {len(catalogues)}")
    for c in catalogues:
        print(f"    {c}")
    print()
    print(f"APPELS pick(locale, fr, de, en) — 2e mécanisme de traduction : {picks}")
    print()
    print(f"CHAÎNES FRANÇAISES SANS AUCUN MÉCANISME : {len(hits)}")
    for f, n in Counter(str(h["file"]) for h in hits).most_common(20):
        print(f"    {n:4d}  {f}")
    print()
    print("  échantillon :")
    for h in hits[:25]:
        print(f"    {h['file']}:{h['line']}  «{h['literal']}»")

    Path(
        "/private/tmp/claude-501/-Users-amadou-local-apps-tessera-app-tessera/"
        "c6235f23-6ea3-4480-b157-384a6eb7f591/scratchpad/i18n_gaps.json"
    ).write_text(json.dumps(hits, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
