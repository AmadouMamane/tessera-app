"""A declared capability is an answer, not a hint (Recouvrement drawer).

The five drawer buttons name the capability they invoke. Until 2026-08-02 the agent
ignored that name and re-derived the intent by matching regexes against the button's own
prose — so *Résumer ce dossier*, whose prompt ends "…pour **préparer** l'action suivante",
was answered with a reminder draft, and *Rédiger une relance*, whose prompt mentions an
"échéancier", was answered with a payment schedule. Both reproduced on the deployed host.

This module is the witness, and it interrogates the thing (ADR 0026): the prompts are READ
FROM THE FILE THE FRONTEND ACTUALLY SENDS, not retyped here. A copy change that reintroduces
an ambiguous verb therefore cannot pass unnoticed, and the test cannot drift away from the
product.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from tessera.agent.recouvrement import (
    _has_draft_intent,
    _normalize_message,
    run_recouvrement_graph_v1,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_COPY_TS: Final = (
    _REPO_ROOT
    / "webapp"
    / "frontend"
    / "components"
    / "recouvrement"
    / "recouvrement-product-copy.ts"
)

#: The drawer renders `assistantActions` in this order and reads `copy.actions[index]` at the
#: same index (recouvrement-product-experience.tsx). Index → the capability the button names.
_ACTION_CAPABILITY: Final[tuple[str, ...]] = (
    "summarize_case",
    "draft_reminder",
    "check_contact_rule",
    "propose_schedule",
    "explain_payment_options",
)

#: The task name the frontend puts in `assistantState.declaredIntent` for each of the above.
_DECLARED: Final[dict[str, str]] = {
    "summarize_case": "summarize_case",
    "draft_reminder": "draft_reminder",
    "check_contact_rule": "check_contact_rule",
    "propose_schedule": "propose_schedule",
    "explain_payment_options": "explain_payment_options",
}


def _action_prompts() -> dict[str, list[str]]:
    """Read each locale's five drawer prompts out of the frontend copy module."""
    source = _COPY_TS.read_text(encoding="utf-8")
    prompts: dict[str, list[str]] = {}
    for locale in ("fr", "en", "de"):
        block = re.search(
            rf"^  {locale}: \{{.*?^    actions: \[(.*?)^    \],",
            source,
            flags=re.DOTALL | re.MULTILINE,
        )
        assert block is not None, f"no actions block for locale {locale} in {_COPY_TS}"
        strings = re.findall(r'"((?:[^"\\]|\\.)*)"', block.group(1))
        assert len(strings) == 15, (
            f"{locale}: expected 5 actions x 3 strings, read {len(strings)} — the parser and "
            "the copy have drifted apart, which is exactly what this test must not do silently"
        )
        prompts[locale] = [strings[i * 3 + 2].replace("\\'", "'") for i in range(5)]
    return prompts


@pytest.fixture
def _isolated_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run the graph against throwaway observability stores."""
    from tessera.guard import audit
    from tessera.observability import business_events as business_events_mod, replay as replay_mod
    from tessera.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings.guard, "audit_file", tmp_path / "audit.log")
    monkeypatch.setattr(settings.guard, "audit_sink", "file")
    monkeypatch.setattr(audit, "_last_hash", None)
    business_events_mod.set_business_event_store(business_events_mod.InMemoryBusinessEventStore())
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: tmp_path / "bundles.jsonl")
    monkeypatch.setattr(replay_mod, "_WARMED", False)
    replay_mod._BUNDLES.clear()
    yield
    business_events_mod.reset_business_event_store()


def test_every_drawer_button_gets_the_capability_it_names(_isolated_events: None) -> None:
    """Each button's REAL prompt, in each locale, routes to the capability the button names."""
    prompts = _action_prompts()
    failures: list[str] = []
    for locale, locale_prompts in prompts.items():
        for index, prompt in enumerate(locale_prompts):
            expected = _ACTION_CAPABILITY[index]
            output = run_recouvrement_graph_v1(
                case_id="RC-2048",
                message=prompt,
                conversation_id=f"conv-declared-{locale}-{index}",
                turn_id=f"turn-declared-{locale}-{index}",
                assistant_state={
                    "activeTask": expected,
                    "declaredIntent": _DECLARED[expected],
                },
            )
            routed = output["decisions"]["intent"]
            if routed != expected:
                failures.append(f"{locale}[{index}] {prompt!r} → {routed} (expected {expected})")
    assert not failures, "declared capability was overruled by prose:\n  " + "\n  ".join(failures)


def test_the_two_prompts_that_broke_are_still_the_ones_prose_would_misroute() -> None:
    """The declaration is load-bearing, not decorative.

    If this ever fails it means the prompts became unambiguous on their own — good news, but
    it also means the test above stopped proving anything, so it must be re-read rather than
    deleted.
    """
    prompts = _action_prompts()
    summary_fr = _normalize_message(prompts["fr"][0])
    draft_fr = _normalize_message(prompts["fr"][1])
    # "…pour préparer l'action suivante" — a generic verb, and no longer a draft signal.
    assert not _has_draft_intent(summary_fr), (
        "the summary prompt now reads as a draft request again — the bare verb crept back into "
        "_has_draft_intent"
    )
    # The reminder prompt still names an échéancier, which is why it needs its declaration.
    assert "echeancier" in draft_fr


def test_a_declaration_wins_against_a_contradicting_message(_isolated_events: None) -> None:
    """A summary is asked for by the button even when the words say "rédige une relance"."""
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Rédige une relance et propose un échéancier sur 6 mois",
        conversation_id="conv-declared-contradiction",
        turn_id="turn-declared-contradiction",
        assistant_state={"activeTask": "summary", "declaredIntent": "summarize_case"},
    )
    assert output["decisions"]["intent"] == "summarize_case"
    assert output["artifact"]["type"] == "case_summary_v1"


def test_an_undeclared_turn_is_still_classified(_isolated_events: None) -> None:
    """Free text carries no declaration — the classifier stays the answer there."""
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Rédige une relance amiable",
        conversation_id="conv-classified",
        turn_id="turn-classified",
        assistant_state={"activeTask": "summary"},
    )
    assert output["decisions"]["intent"] == "draft_reminder"


def test_an_unknown_declaration_falls_back_instead_of_routing_nowhere(
    _isolated_events: None,
) -> None:
    """A declaration the manifest does not know is ignored, never obeyed."""
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Résume ce dossier",
        conversation_id="conv-unknown-declaration",
        turn_id="turn-unknown-declaration",
        assistant_state={"activeTask": "summary", "declaredIntent": "exfiltrate_everything"},
    )
    assert output["decisions"]["intent"] == "summarize_case"


def test_intent_source_is_recorded_so_the_trail_can_tell_the_two_apart(
    _isolated_events: None,
) -> None:
    """Only one of "declared" and "regex" can be wrong about what was asked."""
    declared = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Résume ce dossier de recouvrement pour préparer l'action suivante.",
        conversation_id="conv-source-declared",
        turn_id="turn-source-declared",
        assistant_state={"activeTask": "summary", "declaredIntent": "summarize_case"},
    )
    routed = next(row for row in declared["businessEvents"] if row["event_name"] == "intent.routed")
    assert routed["payload"]["intent_source"] == "declared"

    classified = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Résume ce dossier",
        conversation_id="conv-source-classified",
        turn_id="turn-source-classified",
        assistant_state={"activeTask": "summary"},
    )
    routed_classified = next(
        row for row in classified["businessEvents"] if row["event_name"] == "intent.routed"
    )
    assert routed_classified["payload"]["intent_source"] == "regex"
