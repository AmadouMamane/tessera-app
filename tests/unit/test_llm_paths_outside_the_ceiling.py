"""ADR 0034's daily ceiling is enforced at one seam, and nine paths do not pass through it.

``POST /chat`` resolves the budget policy and refuses (or degrades to a local model) when the
day's spend has reached the ceiling. Every one of those turns is counted. So is every turn of
the nine modules below — they call the same backends and increment the same meter — but none
of them ever *asks*: the summariser, the reflector, the judge, the corpus translator and the
five observability probes will happily keep spending after the breaker has tripped.

The gap is not "the ceiling does not work". It is "the ceiling covers the user-facing turn
and nothing else", and the difference matters most exactly when it is expensive: the probes
replay whole catalogues.

This is a debt, held at its measured size so it can only shrink. Closing an entry means
routing that module through the policy — not deleting it from the list.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "tessera"

#: Names that mean "this module reaches a chat model". Three, not two: the five observability
#: probes obtain their backend through ``backend_for_model`` rather than either factory, and a
#: detector that only knew the factories reported four modules while the audit had counted
#: nine. The gap was in the probe, not in the code — which is the failure mode this repository
#: has paid for often enough to check for by default.
_LLM_ENTRY_POINTS = frozenset({"get_chat_backend", "get_summary_backend", "backend_for_model"})

#: Names that mean "this module consults the daily ceiling before spending".
_CEILING_NAMES = frozenset({"resolve_budget_policy", "BudgetPolicy"})

#: Runs INSIDE a turn the route has already gated. The reporter is a graph node: by the time
#: it speaks, `POST /chat` has resolved the policy and either refused the turn or chosen a
#: model it can afford. Exempted by name and with its reason, never by a pattern — a rule
#: broad enough to excuse the reporter would excuse the nine below with it.
_GATED_BY_THEIR_CALLER: frozenset[str] = frozenset({"agent/reporter.py"})

#: Measured 2026-08-03. Downward only. Each entry is a module that spends on an LLM without
#: ever reading the ceiling that is supposed to bound the org's day. Ten, not the nine the
#: audit listed: `agent_configurations.py` reaches a model the same way and had not been
#: counted.
_FROZEN_UNGATED: frozenset[str] = frozenset(
    {
        "corpus/translator.py",
        "memory/reflector.py",
        "memory/summary.py",
        "observability/ablation.py",
        "observability/agent_configurations.py",
        "observability/consistency.py",
        "observability/crosslingual.py",
        "observability/eval/judge.py",
        "observability/replay.py",
        "observability/robustness.py",
    }
)


def _names_used(path: Path) -> set[str]:
    """Every identifier the module mentions, imported or called."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            used.update(alias.name for alias in node.names)
    return used


def _ungated_modules() -> set[str]:
    ungated: set[str] = set()
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC).as_posix()
        if relative.startswith(("api/", "llm/")) or relative in _GATED_BY_THEIR_CALLER:
            continue  # the seam itself, the route that enforces it, and what runs inside it
        used = _names_used(path)
        if used & _LLM_ENTRY_POINTS and not (used & _CEILING_NAMES):
            ungated.add(relative)
    return ungated


def test_the_detector_finds_something() -> None:
    """A ratchet whose probe returns nothing polices nothing (ADR 0026)."""
    assert _ungated_modules(), (
        "no module was found reaching an LLM outside api/ and llm/ — either the debt is "
        "genuinely closed (delete this file and the freeze below) or the detector stopped "
        "seeing, which is the failure this repository keeps paying for"
    )


def test_no_new_llm_path_escapes_the_ceiling() -> None:
    ungated = _ungated_modules()
    new = sorted(ungated - _FROZEN_UNGATED)
    assert not new, (
        "these modules spend on an LLM without consulting the daily ceiling, and they are "
        "not in the frozen debt:\n  " + "\n  ".join(new) + "\nRoute them through "
        "`resolve_budget_policy` (see `POST /chat`) rather than adding them here."
    )


def test_the_frozen_debt_does_not_name_a_module_that_is_already_gated() -> None:
    """The list may only shrink, and a stale entry would let a real regression hide behind it."""
    ungated = _ungated_modules()
    stale = sorted(_FROZEN_UNGATED - ungated)
    assert not stale, (
        "these are frozen as ungated but no longer are — remove them from _FROZEN_UNGATED so "
        "the count keeps meaning something:\n  " + "\n  ".join(stale)
    )
