"""CLASS B (second half) — the catalogues answer the keys the CODE ACTUALLY CALLS.

`/observability/localization` compares three catalogues against each other. That is a real
measurement and it is not the one the operator's question is about. Three catalogues can agree
key-for-key and still lack every string a component asks for: consistency between copies says
nothing about coverage of the thing being copied.

So this file measures the OTHER direction — `useTranslations("ns")` + `t("key")` against the
declared catalogues — and it lives here rather than in the route on purpose: it must scan the
`.tsx` tree, which the agent image does not ship. A production endpoint that walks a directory
absent from its own container is exactly the defect this lot removed; rebuilding it one measure
over would be a poor way to celebrate.

**What the endpoint could not see, and why.** It compared every locale against `en`, so a key
authored in `fr` and never back-ported was invisible: `fr` had it, `en` did not, and `en` was
the reference, so nothing was missing from anything. Two such keys existed —
`product.apercu.widget.minimize` and `.maximize`, called at `chat-widget.tsx:226` for the expand
button's `aria-label`. An English or German customer's screen reader read them in French.
Measuring against the UNION found both immediately.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from tessera.observability.localization import flatten_keys
from tessera.observability.message_catalogues import load_catalogues

_FRONT = Path(__file__).resolve().parents[2] / "webapp" / "frontend"

#: `const t = useTranslations("quality.signalsTable")` — the namespace a component binds.
_NAMESPACE = re.compile(
    r"const\s+(\w+)\s*=\s*(?:await\s+)?(?:get|use)Translations\(\s*[\"'`]([^\"'`]+)"
)
#: `t("status.ok")` — a literal key on a bound translator. Template/computed keys are skipped
#: deliberately: `t(`x.${k}`)` cannot be resolved statically, and guessing would produce
#: findings nobody can act on. They are COUNTED, so the blind spot has a size.
_CALL = re.compile(r"\b(\w+)\(\s*[\"']([A-Za-z][\w.]*)[\"']\s*[,)]")
_DYNAMIC = re.compile(r"\b(\w+)\(\s*`")

#: Anti-vacuity. 324 sources, 3 125 resolved calls over 2 444 distinct keys, 441 dynamic calls
#: skipped. A floor under each is what separates "every called key is declared" from "the regex
#: stopped matching" — and with the offender list at zero it is the ONLY thing that does,
#: besides the dynamic-count assertion at the bottom.
_MIN_SOURCES = 250
_MIN_RESOLVED = 2500


def _sources() -> list[Path]:
    out: list[Path] = []
    for pattern in ("*.tsx", "*.ts"):
        out += [
            p
            for p in _FRONT.rglob(pattern)
            if "node_modules" not in p.parts
            and ".next" not in p.parts
            and "e2e" not in p.parts
            and not p.name.endswith((".test.ts", ".test.tsx", ".spec.ts"))
        ]
    return sorted(out)


def _called_keys() -> tuple[dict[str, list[str]], int, int]:
    """Return (dotted key -> call sites, resolved calls, dynamic calls skipped)."""
    called: dict[str, list[str]] = defaultdict(list)
    resolved = 0
    dynamic = 0
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        binders = {m.group(1): m.group(2) for m in _NAMESPACE.finditer(text)}
        if not binders:
            continue
        rel = str(path.relative_to(_FRONT))
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            for match in _CALL.finditer(line):
                namespace = binders.get(match.group(1))
                if namespace is None:
                    continue
                resolved += 1
                called[f"{namespace}.{match.group(2)}"].append(f"{rel}:{i}")
            for match in _DYNAMIC.finditer(line):
                if match.group(1) in binders:
                    dynamic += 1
    return called, resolved, dynamic


def test_the_scan_sees_the_tree_and_resolves_real_calls() -> None:
    """A witness that cannot see may never report ok (ADR 0026)."""
    assert len(_sources()) >= _MIN_SOURCES
    _, resolved, _ = _called_keys()
    assert resolved >= _MIN_RESOLVED, (
        f"resolved only {resolved} translation calls — the binding or call shape changed and "
        "this scan went blind. 'No missing key' would then mean 'no key was looked at'."
    )


def test_every_key_the_code_calls_is_declared_in_every_locale() -> None:
    """A called key absent from a catalogue is a string the operator reads in another language.

    next-intl does not raise for a missing key under a bound namespace when a fallback exists —
    it renders the fallback locale's text. Nothing fires, and the only witness is a human who
    reads all three languages.
    """
    load = load_catalogues()
    assert load.found, f"no catalogue could be read; tried {load.tried}"

    called, _, _ = _called_keys()
    per_locale = {loc: flatten_keys(cat) for loc, cat in load.catalogues.items()}

    missing: dict[str, list[str]] = {}
    for key, sites in sorted(called.items()):
        absent = sorted(loc for loc, keys in per_locale.items() if key not in keys)
        # A key absent from EVERY locale is very likely a false positive of the call regex (a
        # non-translator function that happens to be bound to the same name), not 200 missing
        # strings. A key present in some locales and absent from others is the real defect —
        # that asymmetry is what a fallback silently papers over.
        if absent and len(absent) < len(per_locale):
            missing[key] = [f"{loc} (called at {sites[0]})" for loc in absent]

    assert missing == {}, (
        "these keys are called by the code and declared in SOME locales only — the missing "
        "ones\nrender in the fallback language with nothing raised:\n  "
        + "\n  ".join(f"{k}: {', '.join(v)}" for k, v in missing.items())
    )


def test_the_dynamic_blind_spot_has_a_size() -> None:
    """`t(`x.${k}`)` cannot be resolved statically. Count it, so the gap is not silent.

    A scan that quietly skips a shape is the bug it hunts. This does not fail on the count; it
    fails if the count is ZERO, which would mean the dynamic-call detector stopped matching and
    the skip stopped being visible.
    """
    _, _, dynamic = _called_keys()
    assert dynamic > 0, (
        "no dynamic translation call found. The tree uses them (status pills, tone maps), so "
        "zero means this detector went blind and the blind spot lost its size."
    )
