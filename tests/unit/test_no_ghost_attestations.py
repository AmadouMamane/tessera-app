"""ADR 0028's enforcer: the ghost may not return, and no surface may re-attest it.

For months, five product surfaces attested "guarded by mcp-firewall" while the
dependency was imported once, assigned to a variable and read by nobody — an MCP
transport proxy for an application that speaks no MCP. The correction landed
with ADR 0028, and a rule asserted in a doc needs an enforcer: this test
interrogates the artifacts themselves — the dependency lists, the source tree,
the UI message catalogues and the live docs.

Citation as *prior art* remains welcome (the README acknowledgements, the
inspirations table). Attestation as a *running component* does not: on live doc
surfaces, any line naming mcp-firewall must carry a citation marker.

History is exempt on purpose: ``CHANGELOG.md``, ``docs/decisions/`` and
``docs/status/`` record what was believed at the time, and rewriting them would
be its own lie.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

# Tokens of the ghost, in both spellings.
_GHOST = re.compile(r"mcp[-_]firewall", re.IGNORECASE)

# On live doc surfaces, a line naming the ghost must also carry one of these —
# the contexts in which citing it is honest.
_CITATION_MARKERS = re.compile(r"prior art|inspiration|shoulders|ADR 0028", re.IGNORECASE)

# Live doc surfaces (history stays exempt: CHANGELOG, decisions/, status/).
_DOC_SURFACES = (
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
)


def _doc_files() -> list[Path]:
    files = [_REPO / name for name in _DOC_SURFACES if (_REPO / name).is_file()]
    for md in sorted((_REPO / "docs").rglob("*.md")):
        rel = md.relative_to(_REPO / "docs")
        if rel.parts[0] in {"decisions", "status"}:
            continue
        files.append(md)
    files.extend(sorted((_REPO / ".github").rglob("*.md")))
    return files


def test_the_dependency_is_gone() -> None:
    """pyproject declares no mcp-firewall anywhere; the lock resolves none."""
    pyproject = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert not _GHOST.search(pyproject), "pyproject.toml names the ghost again"
    parsed = tomllib.loads(pyproject)
    deps = parsed["project"]["dependencies"]
    assert not any("mcp" in d for d in deps), f"an mcp-* dependency is back: {deps}"
    lock = (_REPO / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "mcp-firewall"' not in lock, "uv.lock resolves the ghost again"


def test_no_source_file_names_the_ghost() -> None:
    """src/ carries no import of and no reference to the ghost, in any spelling."""
    offenders = [
        str(py.relative_to(_REPO))
        for py in sorted((_REPO / "src").rglob("*.py"))
        if _GHOST.search(py.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"source files name the ghost: {offenders}"


def test_no_test_asserts_the_ghost() -> None:
    """No test other than this enforcer references the ghost (three once did)."""
    me = Path(__file__).resolve()
    offenders = [
        str(py.relative_to(_REPO))
        for py in sorted((_REPO / "tests").rglob("*.py"))
        if py.resolve() != me and _GHOST.search(py.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"tests reference the ghost: {offenders}"


def test_ui_messages_do_not_attest_the_ghost() -> None:
    """The cockpit message catalogues (fr/de/en) no longer name the ghost."""
    offenders = [
        str(cat.relative_to(_REPO))
        for cat in sorted((_REPO / "webapp" / "frontend" / "messages").glob("*.json"))
        if _GHOST.search(cat.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"UI message catalogues attest the ghost: {offenders}"


def test_docs_name_it_only_as_prior_art() -> None:
    """On live doc surfaces, every line naming the ghost carries a citation marker."""
    offenders: list[str] = []
    for doc in _doc_files():
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            if _GHOST.search(line) and not _CITATION_MARKERS.search(line):
                offenders.append(f"{doc.relative_to(_REPO)}:{lineno}: {line.strip()[:90]}")
    assert not offenders, "docs attest the ghost outside a citation context:\n" + "\n".join(
        offenders
    )
