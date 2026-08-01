"""Repo-wide sweep of the invariant classes a control plane must hold.

Page-by-page auditing answers "is this screen honest about its own source". It structurally
cannot answer "do two screens say the same thing", "does this button do anything", "is this
string translatable". Those are properties of the WHOLE, so they get whole-repo detectors.

Each detector over-reports on purpose; a detector that silently skips a shape is the bug it
hunts. Every hit is printed with file:line so it can be read, not just counted.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

FRONT = Path("/Users/amadou/local/apps/tessera-app/tessera/webapp/frontend")


def sources() -> list[Path]:
    out: list[Path] = []
    for pat in ("*.tsx", "*.ts"):
        out += [
            p
            for p in FRONT.rglob(pat)
            if "node_modules" not in p.parts
            and ".next" not in p.parts
            and not p.name.endswith((".test.ts", ".test.tsx", ".spec.ts"))
            and "e2e" not in p.parts
        ]
    return sorted(out)


# --------------------------------------------------------------------------------------
# C1 — natural-language literals rendered without i18n
# --------------------------------------------------------------------------------------
# A JSX text node or a template literal carrying accented French / a French function word.
FRENCH = re.compile(
    r"[«»]|[éèêëàâäîïôöùûüçÉÈÊÀÂÎÔÙÇ]|"
    r"\b(?:aucun|aucune|sous|sur|dans|avec|sans|pour|depuis|selon|thèmes|viol|"
    r"conversations|réponses|derniers|toutes|tous)\b"
)
# Skip comments and known-safe contexts.
COMMENTish = re.compile(r"^\s*(?://|\*|/\*)")
SAFE = re.compile(
    r"(useTranslations|getTranslations|from \"|from '|import |t\(|\bconsole\.|"
    r"aria-label=\{|className=|data-testid|// |describe\(|it\()"
)
LITERAL = re.compile(r"(?:`[^`\n]{4,}`|\"[^\"\n]{4,}\"|'[^'\n]{4,}')")


def c1_untranslated() -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for path in sources():
        if path.name in {"format.ts"} or "messages" in path.parts:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if COMMENTish.match(line) or SAFE.search(line):
                continue
            for lit in LITERAL.findall(line):
                body = lit[1:-1]
                if FRENCH.search(body) and not body.startswith(("http", "/", "var(", "--")):
                    hits.append({"file": _rel(path), "line": i, "literal": body[:80]})
    return hits


# --------------------------------------------------------------------------------------
# C2 — dead controls: a <button> with no onClick / type=submit / asChild
# --------------------------------------------------------------------------------------
BUTTON_OPEN = re.compile(r"<(Button|button)\b")


def c2_dead_buttons() -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for path in sources():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not BUTTON_OPEN.search(line):
                continue
            # the element's opening tag may span lines — take until the first '>'
            chunk, j = line, i
            while ">" not in chunk and j + 1 < len(lines) and j - i < 14:
                j += 1
                chunk += " " + lines[j]
            head = chunk.split(">")[0]
            if any(
                k in head
                for k in ("onClick", "type=\"submit\"", "type='submit'", "asChild", "onSubmit")
            ):
                continue
            # a <Button> wrapping a <Link> is legitimate only with asChild; without it the
            # click still works through the child anchor, so require a Link on the same chunk
            if "<Link" in chunk or "href" in head:
                continue
            hits.append({"file": _rel(path), "line": i + 1, "snippet": head.strip()[:100]})
    return hits


# --------------------------------------------------------------------------------------
# C3 — internal links whose target route does not exist on disk
# --------------------------------------------------------------------------------------
HREF = re.compile(r"href=[\"'`](/[a-z0-9\[\]/_-]*)")


def app_routes() -> set[str]:
    base = FRONT / "app" / "[locale]"
    out = {"/"}
    for p in base.rglob("page.tsx"):
        rel = p.relative_to(base).parent.as_posix()
        out.add("/" if rel == "." else f"/{rel}")
    return out


def c3_broken_links() -> list[dict[str, object]]:
    routes = app_routes()

    def known(target: str) -> bool:
        t = target.split("?")[0].split("#")[0].rstrip("/") or "/"
        if t in routes or t.startswith("/api/"):
            return True
        # dynamic segments: /agents/foo/console matches /agents/[agentId]/console
        tp = t.strip("/").split("/")
        for r in routes:
            rp = r.strip("/").split("/")
            if len(rp) != len(tp):
                continue
            if all(rs.startswith("[") or rs == ts for rs, ts in zip(rp, tp)):
                return True
        return False

    hits: list[dict[str, object]] = []
    for path in sources():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for target in HREF.findall(line):
                if not known(target):
                    hits.append({"file": _rel(path), "line": i, "href": target})
    return hits


# --------------------------------------------------------------------------------------
# C4 — the same payload field rendered under different time windows
# --------------------------------------------------------------------------------------
WINDOW_CALL = re.compile(r"(fleetQuery\([^)]*\)|period[\"']?\s*[:=]\s*[\"'][^\"']+[\"']|\"d7\"|\"d30\")")


def c4_windows() -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for path in sources():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in WINDOW_CALL.findall(line):
                out[m.strip()].append(f"{_rel(path)}:{i}")
    return out


def _rel(p: Path) -> str:
    return str(p.relative_to(FRONT))


def main() -> int:
    c1 = c1_untranslated()
    c2 = c2_dead_buttons()
    c3 = c3_broken_links()
    c4 = c4_windows()

    def head(title: str, n: int) -> None:
        print("\n" + "=" * 78)
        print(f"{title} — {n}")
        print("=" * 78)

    head("C1 · CHAÎNES EN LANGUE NATURELLE HORS i18n", len(c1))
    for h in c1[:60]:
        print(f"  {h['file']}:{h['line']}  «{h['literal']}»")
    if len(c1) > 60:
        print(f"  … et {len(c1) - 60} autres")

    head("C2 · BOUTONS SANS ACTION (ni onClick, ni submit, ni lien)", len(c2))
    by_file: dict[str, int] = defaultdict(int)
    for h in c2:
        by_file[str(h["file"])] += 1
    for f, n in sorted(by_file.items(), key=lambda kv: -kv[1])[:25]:
        print(f"  {n:3d}  {f}")

    head("C3 · LIENS INTERNES VERS UNE ROUTE INEXISTANTE", len(c3))
    seen: set[str] = set()
    for h in c3:
        k = str(h["href"])
        if k in seen:
            continue
        seen.add(k)
        print(f"  {h['file']}:{h['line']}  → {h['href']}")

    head("C4 · FENÊTRES TEMPORELLES DÉCLARÉES", sum(len(v) for v in c4.values()))
    for k, v in sorted(c4.items(), key=lambda kv: -len(kv[1])):
        print(f"  «{k}» : {len(v)} site(s)")
        for s in v[:6]:
            print(f"      {s}")

    Path(
        "/private/tmp/claude-501/-Users-amadou-local-apps-tessera-app-tessera/"
        "c6235f23-6ea3-4480-b157-384a6eb7f591/scratchpad/invariants.json"
    ).write_text(
        json.dumps({"c1": c1, "c2": c2, "c3": c3, "c4": c4}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
