"""ADR 0034's daily ceiling is asked by every path that spends. The debt is zero.

``POST /chat`` has always resolved the budget policy and refused (or degraded) once the day's
spend reached the ceiling. Until 2026-08-04 nothing else did: the summariser, the reflector,
the judge, the corpus translator and five observability probes called the same backends and
incremented the same meter without ever asking. The ceiling bounded the user-facing turn and
nothing else — backwards, since the probes replay whole catalogues.

Ten modules were frozen here as owed. Nine are now routed through
:func:`tessera.llm.ceiling.resolve_spend_model`. The tenth was never a debt:
``observability/agent_configurations.py`` obtains a backend to read its *name* and the
sampling it declares, and never calls it. It is exempt by name and with its reason, the way
``agent/reporter.py`` is — never by a pattern, because a rule broad enough to excuse a
descriptive read would excuse a spending one with it.

**This file must not become vacuous now that the list is empty.** A ratchet whose freeze is
empty and whose detector has quietly stopped seeing looks exactly like a debt that was paid.
So the detector is asked to prove it can still see, twice: that it finds LLM call sites at all,
and that it would flag a module that spends without asking (ADR 0026).
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
_CEILING_NAMES = frozenset(
    {"resolve_budget_policy", "BudgetPolicy", "resolve_spend_model", "DailyCeilingReachedError"}
)

#: Exempt by name, each with its reason. Two kinds, and the distinction is the point:
#:
#: * ``agent/reporter.py`` — SPENDS, but inside a turn ``POST /chat`` has already gated: by the
#:   time it speaks, the route has resolved the policy and either refused the turn or chosen a
#:   model it can afford.
#: * ``observability/agent_configurations.py`` — does NOT spend. It obtains a backend to read
#:   ``backend.name`` and ``SAMPLING_APPLIED``, and never calls ``chat``. Gating it would refuse
#:   to *describe* the configuration once the budget was spent.
_EXEMPT: frozenset[str] = frozenset({"agent/reporter.py", "observability/agent_configurations.py"})

#: Was ten on 2026-08-03. Downward only, and now empty: every module that spends asks first.
#: An entry may only leave this set by being routed through the ceiling — never by being
#: deleted from the list, and never by widening :data:`_EXEMPT`.
_FROZEN_UNGATED: frozenset[str] = frozenset()


def _names_used(source: str) -> set[str]:
    """Every identifier the source mentions, imported or called."""
    tree = ast.parse(source)
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            used.update(alias.name for alias in node.names)
    return used


def _is_ungated(source: str) -> bool:
    used = _names_used(source)
    return bool(used & _LLM_ENTRY_POINTS) and not (used & _CEILING_NAMES)


def _modules_reaching_an_llm() -> set[str]:
    """Every module outside the seam that names an LLM entry point, gated or not."""
    found: set[str] = set()
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC).as_posix()
        if relative.startswith(("api/", "llm/")):
            continue  # the seam itself and the route that enforces it
        if _names_used(path.read_text(encoding="utf-8")) & _LLM_ENTRY_POINTS:
            found.add(relative)
    return found


def _ungated_modules() -> set[str]:
    ungated: set[str] = set()
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC).as_posix()
        if relative.startswith(("api/", "llm/")) or relative in _EXEMPT:
            continue
        if _is_ungated(path.read_text(encoding="utf-8")):
            ungated.add(relative)
    return ungated


class TestTheDetectorCanStillSee:
    """With an empty freeze, these are the only things standing between green and vacuous."""

    def test_it_finds_the_modules_that_reach_a_model(self) -> None:
        found = _modules_reaching_an_llm()
        assert len(found) >= 9, (
            "the detector found almost no module reaching an LLM outside api/ and llm/ — "
            f"either the code moved or the probe stopped seeing. Found: {sorted(found)}"
        )

    def test_it_would_flag_a_module_that_spends_without_asking(self) -> None:
        """The positive control: a synthetic ungated module must be caught."""
        assert _is_ungated(
            "from tessera.llm.router import backend_for_model\nbackend_for_model('x')"
        )

    def test_it_does_not_flag_a_module_that_asks(self) -> None:
        """The negative control: without it, a detector that flags everything would pass above."""
        assert not _is_ungated(
            "from tessera.llm.ceiling import resolve_spend_model\n"
            "from tessera.llm.router import backend_for_model\n"
            "backend_for_model('x')"
        )


def test_no_llm_path_escapes_the_ceiling() -> None:
    ungated = sorted(_ungated_modules() - _FROZEN_UNGATED)
    assert not ungated, (
        "these modules spend on an LLM without consulting the daily ceiling:\n  "
        + "\n  ".join(ungated)
        + "\nRoute them through `tessera.llm.ceiling.resolve_spend_model` rather than adding "
        "them to the freeze — the freeze is empty and may only stay so."
    )


def test_the_frozen_debt_stays_empty() -> None:
    """It reached zero on 2026-08-04. Growing it back is a decision, not a merge."""
    assert not _FROZEN_UNGATED, (
        "the frozen debt is no longer empty. An ungated LLM path was accepted rather than "
        f"routed: {sorted(_FROZEN_UNGATED)}"
    )


def test_the_exemptions_stay_two_and_keep_their_reasons() -> None:
    """An exemption is a place where a defect is allowed to live. These two are not defects —
    but a third arriving unexamined would be, so it has to be a deliberate edit here."""
    assert {"agent/reporter.py", "observability/agent_configurations.py"} == _EXEMPT
    for relative in _EXEMPT:
        assert (_SRC / relative).is_file(), f"{relative} is exempt and no longer exists"
