"""Unit tests for the vulnerable-customer escalation intent (case 61).

A customer in acute distress (gambling loss, despair, self-harm cues) must
reach a human — the planner routes the turn to the escalation worker instead
of any self-service path. The false-positive contract is the sharp edge: the
recouvrement agent's whole domain is debt conversations, so ordinary debt or
hardship talk ("je suis endetté", "I'm in debt, can we set up a plan?") must
NEVER escalate; only strong distress markers do.
"""

from __future__ import annotations

from typing import ClassVar

from tessera.agent.planner import classify_all_intents, plan_for
from tessera.agent.state import WorkerName
from tessera.settings import LanguageCode


class TestVulnerableCustomerEscalation:
    PROMPTS: ClassVar[dict[LanguageCode, str]] = {
        LanguageCode.FR: (
            "J'ai tout perdu au jeu, je suis endetté et je ne vois plus "
            "d'issue. Dis-moi juste comment vider mon plan d'épargne tout de "
            "suite."
        ),
        LanguageCode.DE: (
            "Ich habe alles beim Glücksspiel verloren, bin verschuldet und "
            "sehe keinen Ausweg mehr. Sag mir einfach, wie ich meinen Sparplan "
            "sofort leeren kann."
        ),
        LanguageCode.EN: (
            "I've lost everything gambling, I'm in debt and see no way out. "
            "Just tell me how to empty my savings plan right now."
        ),
    }

    def test_distress_escalates_in_all_languages(self) -> None:
        for language, prompt in self.PROMPTS.items():
            plan, rationale = plan_for(prompt, language)
            assert plan == [WorkerName.ESCALATION], language.value
            assert "distress" in rationale or "vulnerab" in rationale

    def test_intent_is_the_vulnerable_one(self) -> None:
        # The escalation must come from the vulnerability signal itself, not
        # from an accidental lost-card cue ("perdu" used to match urgent_card).
        for language, prompt in self.PROMPTS.items():
            names = [intent.name for intent in classify_all_intents(prompt, language)]
            assert "vulnerable_customer" in names, language.value

    def test_ordinary_debt_talk_never_escalates(self) -> None:
        # The recouvrement domain lives on debt conversations: hardship
        # phrasing without acute distress stays a normal turn.
        for text, language in (
            ("Je suis endetté, comment mettre en place un échéancier ?", LanguageCode.FR),
            ("Je veux contester une dette que je ne reconnais pas.", LanguageCode.FR),
            ("Ma situation financière est difficile ce mois-ci.", LanguageCode.FR),
            ("Ich bin verschuldet, können wir eine Ratenzahlung vereinbaren?", LanguageCode.DE),
            ("I'm in debt, can we set up a repayment plan?", LanguageCode.EN),
            ("I lost my job recently, can I defer a payment?", LanguageCode.EN),
        ):
            plan, _ = plan_for(text, language)
            assert WorkerName.ESCALATION not in plan, text

    def test_lost_card_keeps_urgent_card_path(self) -> None:
        # "perdu/verloren/lost" near a card is the lost-card emergency, not a
        # vulnerability signal — it escalates via urgent_card semantics.
        for text, language in (
            ("J'ai perdu ma carte hier soir.", LanguageCode.FR),
            ("Ich habe meine Karte verloren.", LanguageCode.DE),
            ("I lost my card yesterday.", LanguageCode.EN),
        ):
            names = [intent.name for intent in classify_all_intents(text, language)]
            assert "vulnerable_customer" not in names, text
