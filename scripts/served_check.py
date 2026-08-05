"""Served-check — does the running stack actually serve what the repo has landed? (ADR 0051)

``deploy-diff`` (ADR 0048) asks whether the two targets agree with EACH OTHER. That is a real
question and it has a real blind spot: two hosts both three commits stale agree perfectly. It
compares neighbours; this compares the stack to the thing it claims to serve — the commit in the
working tree — which is the question "do I need to rebuild?" actually reduces to.

It answers BY EXIT CODE:

* ``0`` — the stack serves this commit, or the only changes since it cannot reach a served
  surface (docs, tests, CI).
* ``1`` — REFUSED. Something the stack serves has moved since it was built. Either baked code is
  stale (rebuild) or — worse — mounted data has already moved under baked code that has not
  (the chimera: new reports read by an old grader, which is how the deployed cockpit was put
  into ``CannotSay`` with no error anywhere).
* ``2`` — blind: nothing is serving, the stack cannot name its commit, or it was built from a
  dirty tree so there is no commit to diff against. A witness that cannot see may never report
  "ok" (ADR 0026).

The classification is driven by ``infra/deploy/served-surfaces.yaml`` and the pure
:func:`verdict` is unit-tested without a network or a git repo.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

_REPO = Path(__file__).resolve().parents[1]
_MANIFEST_PATH: Final = _REPO / "infra" / "deploy" / "served-surfaces.yaml"

#: Where the local full-local front answers by default (`make fulllocal-up`).
_DEFAULT_URL: Final = "http://localhost:3090"

#: Values `/api/version` returns that are an ADMISSION rather than a build id (see the front's
#: route: `dev` = never stamped, `unverified:` = the agent half never answered).
_CANNOT_SAY_PREFIXES: Final = ("unverified:",)
_CANNOT_SAY_EXACT: Final = frozenset({"", "dev", "unknown"})

#: The front reports this when its two halves disagree. It is not a blind spot — it is a
#: divergence, already inside the pair, and it must refuse rather than go quiet.
_MIXED_PREFIX: Final = "mixed:"

#: A `-dirty` stamp means the image contains a tree, not a commit. There is nothing to diff.
_DIRTY_SUFFIX: Final = "-dirty"

_MEDIA: Final = frozenset({"baked", "mounted", "absent"})

#: What an unlisted path is assumed to be. `baked` on purpose: the safe answer to "I do not
#: recognise this file" is "assume a rebuild is needed", never "assume it is harmless".
_DEFAULT_MEDIUM: Final = "baked"

_USER_AGENT: Final = "tessera-served-check/1.0"
_TIMEOUT_S: Final = 5.0

#: `git status --porcelain` writes two status columns and a space before the path.
_PORCELAIN_PREFIX: Final = 3

#: How many paths a verdict lists before summarising. A DISPLAY cap, printed as "… and N more"
#: rather than silently truncated — a bounded list that does not say it is bounded reads as the
#: whole set.
_MAX_LISTED: Final = 12

EXIT_OK: Final = 0
EXIT_STALE: Final = 1
EXIT_BLIND: Final = 2


@dataclass(frozen=True)
class Surface:
    """One manifest entry: a repo path prefix and how it reaches the running stack."""

    path: str
    medium: str
    why: str


@dataclass
class Verdict:
    """The judgement, plus everything needed to explain it without re-deriving anything."""

    exit_code: int
    headline: str
    baked: list[str] = field(default_factory=list)
    mounted: list[str] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def load_surfaces(path: Path | None = None) -> list[Surface]:
    """Read the manifest. Raises rather than defaulting — a missing manifest is not "no rules"."""
    raw = yaml.safe_load((path or _MANIFEST_PATH).read_text(encoding="utf-8"))
    entries = raw.get("surfaces") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        msg = f"served-surfaces manifest has no surfaces: {path or _MANIFEST_PATH}"
        raise ValueError(msg)
    surfaces = []
    for entry in entries:
        medium = str(entry.get("medium", ""))
        if medium not in _MEDIA:
            msg = f"unknown medium {medium!r} for {entry.get('path')!r} (expected one of {_MEDIA})"
            raise ValueError(msg)
        surfaces.append(
            Surface(path=str(entry["path"]), medium=medium, why=str(entry.get("why", "")).strip())
        )
    return surfaces


def classify(changed: list[str], surfaces: list[Surface]) -> dict[str, list[str]]:
    """Group changed repo paths by the medium through which they reach the stack.

    Longest matching prefix wins, which is what makes ``eval/reports/`` (mounted) override
    ``eval/`` (baked) rather than fight it. An unmatched path counts as :data:`_DEFAULT_MEDIUM`.
    """
    ordered = sorted(surfaces, key=lambda s: len(s.path), reverse=True)
    grouped: dict[str, list[str]] = {medium: [] for medium in _MEDIA}
    for changed_path in changed:
        medium = next(
            (s.medium for s in ordered if changed_path.startswith(s.path)), _DEFAULT_MEDIUM
        )
        grouped[medium].append(changed_path)
    return grouped


def _unusable_stamp(served_sha: str | None) -> Verdict | None:
    """The cases where the stack's own answer cannot be compared to a commit at all.

    Separated from :func:`verdict` because they are a different question — *can this be judged?*
    rather than *what is the judgement?* — and because collapsing them would let a stack that
    cannot name itself fall through to a comparison against an empty string.
    """
    if served_sha is None:
        return Verdict(
            EXIT_BLIND,
            "CANNOT SAY — nothing answered. Start the stack, or point this at the host that "
            "serves it; a check that looked at nothing may not report 'ok'.",
        )
    if served_sha.startswith(_MIXED_PREFIX):
        return Verdict(
            EXIT_STALE,
            f"REFUSED — the served pair disagrees with itself ({served_sha}). Its frontend and "
            "agent were built from different commits, so no single commit describes what runs.",
        )
    if served_sha in _CANNOT_SAY_EXACT or served_sha.startswith(_CANNOT_SAY_PREFIXES):
        return Verdict(
            EXIT_BLIND,
            f"CANNOT SAY — the stack cannot name its own commit ({served_sha!r}). An un-stamped "
            "or half-answered build cannot be compared to anything.",
        )
    if served_sha.endswith(_DIRTY_SUFFIX):
        return Verdict(
            EXIT_BLIND,
            f"CANNOT SAY — the stack was built from a DIRTY tree ({served_sha}). It contains a "
            "working tree, not a commit, so there is nothing to diff it against.",
        )
    return None


def verdict(
    *,
    served_sha: str | None,
    head_sha: str,
    changed: list[str] | None,
    surfaces: list[Surface],
    dirty_paths: list[str] | None = None,
) -> Verdict:
    """The whole judgement, as a pure function (no network, no git, no filesystem).

    Args:
        served_sha: What the stack says it serves, or ``None`` if it could not be asked.
        head_sha: The commit the working tree is on.
        changed: Repo-relative paths differing between the two, or ``None`` if undiffable.
        surfaces: The manifest.
        dirty_paths: Uncommitted paths in the working tree, which the stack cannot be serving.
    """
    unusable = _unusable_stamp(served_sha)
    if unusable is not None:
        return unusable
    assert served_sha is not None

    notes: list[str] = []
    if dirty_paths:
        grouped_dirty = classify(dirty_paths, surfaces)
        reachable = grouped_dirty["baked"] + grouped_dirty["mounted"]
        if reachable:
            notes.append(
                f"{len(reachable)} uncommitted file(s) touch served surfaces "
                f"({', '.join(sorted(reachable)[:3])}…). They are in NEITHER the served stack nor "
                "this comparison — commit them before reading this verdict as complete."
            )

    if served_sha == head_sha:
        return Verdict(EXIT_OK, f"MATCH — the stack serves {head_sha}, this commit.", notes=notes)

    if changed is None:
        return Verdict(
            EXIT_BLIND,
            f"CANNOT SAY — the stack serves {served_sha}, which this repo does not contain, so "
            "the change set cannot be computed. Fetch it, or rebuild from a known commit.",
            notes=notes,
        )

    grouped = classify(changed, surfaces)
    baked, mounted, absent = grouped["baked"], grouped["mounted"], grouped["absent"]

    if baked and mounted:
        headline = (
            f"REFUSED — CHIMERA. The stack serves {served_sha}; since then "
            f"{len(baked)} baked file(s) changed (frozen in the image) AND {len(mounted)} mounted "
            f"file(s) changed (already live). Old code is reading new data right now. Rebuild."
        )
    elif baked:
        headline = (
            f"REFUSED — STALE. The stack serves {served_sha}; {len(baked)} baked file(s) have "
            f"changed since and are invisible until the image is rebuilt and recreated."
        )
    elif mounted:
        headline = (
            f"REFUSED — DRIFTED. The stack serves {served_sha}; no baked file changed, but "
            f"{len(mounted)} mounted file(s) did and are already being read by an image built "
            f"from the older commit. Rebuild so the pair names one commit."
        )
    else:
        return Verdict(
            EXIT_OK,
            f"OK — the stack serves {served_sha}, not {head_sha}, but the {len(absent)} file(s) "
            "changed since reach no served surface. No rebuild needed.",
            absent=absent,
            notes=notes,
        )
    return Verdict(EXIT_STALE, headline, baked=baked, mounted=mounted, absent=absent, notes=notes)


def _served_sha(url: str) -> str | None:
    """Ask the running front which commit the pair serves. ``None`` when it cannot be asked."""
    request = urllib.request.Request(  # noqa: S310 — http(s) only, operator-supplied host
        f"{url.rstrip('/')}/api/version", headers={"User-Agent": _USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:  # noqa: S310
            payload: Any = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    sha = payload.get("sha") if isinstance(payload, dict) else None
    return sha if isinstance(sha, str) else None


def _git(*args: str) -> str | None:
    """Run a git command in the repo; ``None`` when it fails (never a fabricated empty answer)."""
    try:
        done = subprocess.run(
            ["git", "-C", str(_REPO), *args], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def _changed_since(served_sha: str) -> list[str] | None:
    """Repo paths whose CONTENT differs between the served commit and HEAD.

    A two-tree diff (``a b``), never a range (``a..b``): what matters is whether the bytes the
    stack baked differ from the bytes here, not whether one commit descends from the other. On a
    rolled-back or rebased stack a range diff reads empty and would report a match over a stack
    serving different code.
    """
    if _git("cat-file", "-e", f"{served_sha}^{{commit}}") is None:
        return None
    out = _git("diff", "--name-only", served_sha, "HEAD")
    return None if out is None else [line for line in out.splitlines() if line]


def _dirty_paths() -> list[str]:
    """Uncommitted paths, from `git status --porcelain`'s `XY <path>` lines."""
    out = _git("status", "--porcelain") or ""
    return [
        line[_PORCELAIN_PREFIX:].strip()
        for line in out.splitlines()
        if len(line) > _PORCELAIN_PREFIX
    ]


def _render(result: Verdict) -> None:
    print(f"[served-check] {result.headline}")
    for medium, paths in (("baked", result.baked), ("mounted", result.mounted)):
        if paths:
            print(f"  {medium} ({len(paths)}):")
            for path in sorted(paths)[:_MAX_LISTED]:
                print(f"    - {path}")
            if len(paths) > _MAX_LISTED:
                print(f"    … and {len(paths) - _MAX_LISTED} more")
    for note in result.notes:
        print(f"  note: {note}")
    if result.exit_code == EXIT_STALE:
        print("  fix: TESSERA_AGENT_STATE=<state dir> make fulllocal-up   # rebuilds and recreates")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=_DEFAULT_URL, help="host serving the front")
    args = parser.parse_args(argv)

    head = (_git("rev-parse", "--short=8", "HEAD") or "").strip()
    if not head:
        print("[served-check] CANNOT SAY — this is not a git checkout.")
        return EXIT_BLIND
    served = _served_sha(args.url)
    result = verdict(
        served_sha=served,
        head_sha=head,
        changed=_changed_since(served) if served else None,
        surfaces=load_surfaces(),
        dirty_paths=_dirty_paths(),
    )
    _render(result)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
