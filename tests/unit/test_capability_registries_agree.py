"""CLASS E — the two capability registries are one declaration, asserted.

`spine/capabilities.py` and `webapp/frontend/lib/signal-registry.ts` describe the same thing:
which dimensions a signal can be sliced by, and whether it is a deterministic fixture. Both
files say, in their own docstring, that they mirror the other. **Neither checked.**

They had drifted three ways by 2026-08-01, and one of the three was not cosmetic:

* `embedding_inversion` — backend `synthetic=True`, frontend `synthetic: false`. The probe runs
  over `DEMO_MEMORIES`, five invented sentences in `embedding_inversion.py`, "so the dashboard
  always shows a concrete number". The maths is real; the memories are not. `<SyntheticNotice>`
  renders from the FRONTEND flag, so `securite-privacy` showed "Inversion embedding · Critique ·
  100 %" with no notice at all, and fed it into the failure distribution beside real
  measurements. Two registries, one truth, and the UI read the wrong one.
* `disclosure`, `embedding_skew` — declared by the backend, absent from the frontend. An absent
  entry is not neutral: `capabilityFor()` returns `undefined`, `signalSupports()` turns that
  into `false`, and the surface badges "org-wide" on no basis at all. A declaration nobody made,
  rendered as one that was.

This is the whole chantier's pattern in one place — a derivation copied instead of shared, with
nothing reconciling the copies — and it is the copy the operator SEES that was wrong.

**The right fix would be one file.** The frontend cannot import Python and the backend cannot
ship TypeScript, so the honest second-best is two files and a witness that reads both and
refuses any disagreement. The doctrine's real name for this is: never call two copies a mirror
unless something checks.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessera.observability.spine.capabilities import CAPABILITIES

_REGISTRY_TS = (
    Path(__file__).resolve().parents[2] / "webapp" / "frontend" / "lib" / "signal-registry.ts"
)

#: `  signal_id: cap(DIMS, { synthetic: true }),` — the whole declaration on one line.
_ENTRY = re.compile(r"^ {2}([a-z_][a-z0-9_]*):\s*cap\(([^)]*)\)", re.M)

#: Anti-vacuity: the parse must find a registry, not an empty match set. ~50 entries stand
#: today; a floor well under it catches a regex that stopped matching without going red every
#: time a signal is legitimately added or removed.
_MIN_PARSED = 40


def _frontend_registry() -> dict[str, bool]:
    """Signal id → `synthetic`, parsed from the TypeScript source.

    Parsed rather than executed. A Node round-trip would be a second toolchain in a Python
    test, and the declaration is a flat object literal — the one shape where a regex is honest.
    The floor below is what keeps that honesty falsifiable.
    """
    source = _REGISTRY_TS.read_text(encoding="utf-8")
    body = source.split("export const SIGNAL_REGISTRY", 1)[1].split("\n};", 1)[0]
    return {m.group(1): "synthetic: true" in m.group(2) for m in _ENTRY.finditer(body)}


def test_the_parse_sees_a_registry() -> None:
    """A witness that cannot see may never report ok (ADR 0026).

    If the regex stopped matching, every assertion below would compare two empty sets and pass.
    """
    front = _frontend_registry()
    assert len(front) >= _MIN_PARSED, (
        f"parsed only {len(front)} frontend entries — the declaration shape changed and this "
        "witness went blind. Every agreement assertion below would be vacuous."
    )
    assert len(CAPABILITIES) >= _MIN_PARSED


def test_both_registries_declare_the_same_signals() -> None:
    """Set equality, both directions. A signal in one and not the other is a silent default."""
    front = set(_frontend_registry())
    back = set(CAPABILITIES)

    only_back = sorted(back - front)
    only_front = sorted(front - back)

    assert only_back == [], (
        "declared by capabilities.py, absent from lib/signal-registry.ts:\n  "
        + "\n  ".join(only_back)
        + "\n\n`capabilityFor()` returns undefined for these, `signalSupports()` turns that "
        "into\n`false`, and the surface badges org-wide on no declaration at all."
    )
    assert only_front == [], (
        "declared by lib/signal-registry.ts, absent from capabilities.py:\n  "
        + "\n  ".join(only_front)
        + "\n\nThe backend is the source of truth: a front-only entry describes a signal the "
        "read\nlayer will not honour."
    )


def test_both_registries_agree_on_which_signals_are_fixtures() -> None:
    """The flag the OPERATOR sees must equal the flag the backend declares.

    `<SyntheticNotice>` renders from the frontend flag alone. A disagreement here is not an
    inconsistency between two files — it is a fixture presented as a measurement.
    """
    front = _frontend_registry()
    disagree = {
        signal: (cap.synthetic, front[signal])
        for signal, cap in CAPABILITIES.items()
        if signal in front and cap.synthetic != front[signal]
    }

    assert disagree == {}, (
        "these signals disagree on `synthetic` (backend, frontend):\n  "
        + "\n  ".join(f"{s}: back={b}, front={f}" for s, (b, f) in sorted(disagree.items()))
        + "\n\nThe UI renders its notice from the FRONTEND flag. Where the backend says fixture "
        "and\nthe frontend says real, a deterministic demo is on screen labelled as a "
        "measurement —\nwhich is exactly what `embedding_inversion` did, at 100 % Critique, "
        "inside the\nfailure distribution."
    )


def test_the_witness_has_teeth() -> None:
    """Show the parser a divergence and require it to be visible.

    The parse is a regex over TypeScript, so it can go subtly wrong in exactly the way a
    silent mirror does. These assertions are the control.
    """
    parsed = {
        m.group(1): "synthetic: true" in m.group(2)
        for m in _ENTRY.finditer(
            "  real_one: cap(ORG),\n  fixture_one: cap(ORG, { synthetic: true }),\n"
        )
    }
    assert parsed == {"real_one": False, "fixture_one": True}

    # …and a nested/indented line is NOT an entry: only two-space keys at the object's top
    # level declare a signal, so a comment or a nested literal cannot invent one.
    assert _ENTRY.findall("    nested: cap(ORG),\n") == []
