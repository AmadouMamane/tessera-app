"""Planner node — decides which workers should run for the current turn.

The planner is rule-based first, LLM-assisted second. The rule layer catches
the common, unambiguous intents (balance lookup, card block, regulatory
question) where invoking the LLM would only add latency. The LLM layer
handles ambiguous or multi-intent requests by emitting a structured plan.

Rule-based classification is deterministic and re-playable from the
non-regression harness; LLM-based planning is logged with its inputs so a
replay can substitute the recorded plan when offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from tessera.agent.state import AgentState, WorkerName
from tessera.settings import LanguageCode

__all__ = ["Intent", "classify_intent", "plan_for", "run"]


# ---------------------------------------------------------------------------
# Intent → worker dispatch table
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Intent:
    """A classified user intent and the workers it selects."""

    name: str
    workers: tuple[WorkerName, ...]
    rationale: str


_DEFAULT_PLAN: Final[tuple[WorkerName, ...]] = (
    WorkerName.REGULATION_LOOKUP,
    WorkerName.PRODUCT_LOOKUP,
)


# Multilingual cue tables. Each entry maps a regex pattern (case-insensitive,
# word-boundaries) to the intent it triggers. The order matters: more specific
# patterns first.
_INTENT_RULES: dict[LanguageCode, list[tuple[re.Pattern[str], Intent]]] = {
    LanguageCode.FR: [
        # A customer in acute distress (gambling loss, despair, self-harm cues)
        # must reach a human, never a self-service answer (case 61). Markers are
        # STRONG on purpose: ordinary debt talk — the recouvrement agent's whole
        # domain — must never escalate ("je suis endetté, comment faire un
        # échéancier ?" stays a normal turn).
        (
            re.compile(
                r"(ne\s+vois\s+plus\s+d['\u2019]issue|plus\s+aucune\s+issue|situation\s+sans\s+issue"
                r"|tout\s+perdu\s+au\s+jeu|perdu\w*\s+au\s+jeu|d[ée]tresse|d[ée]sesp[ée]r\w*"
                r"|suicid\w*|en\s+finir\s+avec|envie\s+d['\u2019]en\s+finir)",
                re.IGNORECASE,
            ),
            Intent(
                name="vulnerable_customer",
                workers=(WorkerName.ESCALATION,),
                rationale="French distress/vulnerability signals → ESCALATION (human care)",
            ),
        ),
        # Destructive irreversible ask (close the account + drain it, skipping
        # verification) requires a human by policy — never self-served (case 55).
        (
            re.compile(
                r"(?=.*\b(cl[ôo]tur\w*|ferme[rz]?)\b.{0,40}\bcomptes?\b)"
                r"(?=.*(d[ée]finitiv|sans\s+v[ée]rification|tout\s+le\s+solde|sans\s+question))",
                re.IGNORECASE | re.DOTALL,
            ),
            Intent(
                name="destructive_action",
                workers=(WorkerName.ESCALATION,),
                rationale="French destructive close-and-drain ask → ESCALATION (human only)",
            ),
        ),
        # Urgent card cases must be matched before generic card_block.
        (
            re.compile(
                r"\b(vol(?:é[e]?|er?)|perdu[e]?|avalé.*distributeur|distributeur.*avalé"
                r"|paiements?.*(n'ai pas|pas effectué)|fraude.*carte|carte.*fraude"
                r"|immédiatement.*bloquer|bloquer.*immédiatement)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="urgent_card",
                workers=(WorkerName.ESCALATION,),
                rationale="French urgent/fraud card → ESCALATION directly",
            ),
        ),
        (
            re.compile(r"\b(solde|combien.*compte|état.*compte)\b", re.IGNORECASE),
            Intent(
                name="account_balance",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="French solde/balance query → ACCOUNT_LOOKUP",
            ),
        ),
        (
            re.compile(
                r"\b(derni[eè]res?\s+(transactions?|op[ée]rations?)"
                r"|transactions?\s+r[ée]centes?|op[ée]rations?\s+r[ée]centes?"
                r"|historique\s+(des?\s+)?(transactions?|op[ée]rations?))\b",
                re.IGNORECASE,
            ),
            Intent(
                name="transaction_search",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="French transaction-history query → ACCOUNT_LOOKUP",
            ),
        ),
        (
            re.compile(
                r"\b(bloquer|bloquez|blocage|opposition|vol.*carte|carte.*vol)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="card_block",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="French card-block intent → ACCOUNT_LOOKUP; reviewer decides escalation",
            ),
        ),
        (
            re.compile(r"\b(simul|simuler|mensualit|simulat)\b", re.IGNORECASE),
            Intent(
                name="loan_simulation",
                workers=(WorkerName.SIMULATOR, WorkerName.PRODUCT_LOOKUP),
                rationale="French explicit simulation request",
            ),
        ),
        (
            re.compile(
                r"\b(rgpd|cnil|dora|réglement|réglementation|conformité)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="regulation",
                workers=(WorkerName.REGULATION_LOOKUP,),
                rationale="French regulatory keyword present",
            ),
        ),
    ],
    LanguageCode.DE: [
        (
            re.compile(
                r"(keinen?\s+Ausweg|ausweglos|Gl[üu]cksspiel\s+verloren"
                r"|alles\s+beim\s+(Gl[üu]cks)?spiel\w*\s+verloren|verzweifelt|Verzweiflung"
                r"|suizid\w*|selbstmord|wei[ßs]\s+nicht\s+mehr\s+weiter)",
                re.IGNORECASE,
            ),
            Intent(
                name="vulnerable_customer",
                workers=(WorkerName.ESCALATION,),
                rationale="German distress/vulnerability signals → ESCALATION (human care)",
            ),
        ),
        (
            re.compile(
                r"(?=.*\b(schlie[ßs]\w*|aufl[öo]s\w*|k[üu]ndig\w*)\b.{0,40}\bkontos?\b)"
                r"(?=.*(endg[üu]ltig|ohne\s+(r[üu]ckfragen?|identit[äa]tspr[üu]fung|pr[üu]fung)"
                r"|gesamte\w*\s+guthaben))",
                re.IGNORECASE | re.DOTALL,
            ),
            Intent(
                name="destructive_action",
                workers=(WorkerName.ESCALATION,),
                rationale="German destructive close-and-drain ask → ESCALATION (human only)",
            ),
        ),
        (
            re.compile(
                r"\b(gestohlen|verloren.*karte|karte.*verloren"
                r"|nicht.*getätigt.*Zahlungen?|Zahlungen?.*(nicht|kein).*getätigt"
                r"|Betrug.*karte|karte.*Betrug|sofort.*sperren|sperren.*sofort)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="urgent_card",
                workers=(WorkerName.ESCALATION,),
                rationale="German urgent/fraud card → ESCALATION directly",
            ),
        ),
        (
            re.compile(r"\b(kontostand|saldo|wie viel.*konto)\b", re.IGNORECASE),
            Intent(
                name="account_balance",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="German balance query → ACCOUNT_LOOKUP",
            ),
        ),
        (
            re.compile(
                r"\b(letzte[nr]?\s+(transaktionen?|ums[aä]tze|buchungen?)"
                r"|aktuelle[nr]?\s+(transaktionen?|ums[aä]tze|buchungen?)"
                r"|transaktionsverlauf|umsatzhistorie)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="transaction_search",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="German transaction-history query → ACCOUNT_LOOKUP",
            ),
        ),
        (
            re.compile(
                r"\b(karte sperren|karte zu sperren|sperrung|kartensperre|karte verloren)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="card_block",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="German card-block intent → ACCOUNT_LOOKUP; reviewer decides escalation",
            ),
        ),
        (
            re.compile(r"\b(simulier|simulat|monatliche.*rate|rate.*monatlich)\b", re.IGNORECASE),
            Intent(
                name="loan_simulation",
                workers=(WorkerName.SIMULATOR, WorkerName.PRODUCT_LOOKUP),
                rationale="German explicit simulation request",
            ),
        ),
        (
            re.compile(r"\b(dsgvo|bafin|dora|datenschutz|aufsicht)\b", re.IGNORECASE),
            Intent(
                name="regulation",
                workers=(WorkerName.REGULATION_LOOKUP,),
                rationale="German regulatory keyword present",
            ),
        ),
    ],
    LanguageCode.EN: [
        (
            re.compile(
                r"(no\s+way\s+out|lost\s+everything\s+gambling|gambling.{0,30}lost\s+everything"
                r"|desperate|hopeless|suicid\w*|end\s+it\s+all|can['\u2019]t\s+go\s+on)",
                re.IGNORECASE,
            ),
            Intent(
                name="vulnerable_customer",
                workers=(WorkerName.ESCALATION,),
                rationale="English distress/vulnerability signals → ESCALATION (human care)",
            ),
        ),
        (
            re.compile(
                r"(?=.*\b(close?|closing|terminate)\w*\b.{0,40}\baccounts?\b)"
                r"(?=.*(permanent|no\s+(identity\s+)?(check|verification|questions)"
                r"|whole\s+balance|entire\s+balance))",
                re.IGNORECASE | re.DOTALL,
            ),
            Intent(
                name="destructive_action",
                workers=(WorkerName.ESCALATION,),
                rationale="English destructive close-and-drain ask → ESCALATION (human only)",
            ),
        ),
        (
            re.compile(
                r"\b(stolen|payments.*not.*made|fraudulent.*payments?"
                r"|block.*immediately|immediately.*block|card.*fraud|fraud.*card)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="urgent_card",
                workers=(WorkerName.ESCALATION,),
                rationale="English urgent/fraud card → ESCALATION directly",
            ),
        ),
        (
            re.compile(r"\b(balance|account.*balance|how much.*account)\b", re.IGNORECASE),
            Intent(
                name="account_balance",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="English balance query → ACCOUNT_LOOKUP",
            ),
        ),
        (
            re.compile(
                r"\b(recent\s+(transactions?|payments?|activity)"
                r"|latest\s+(transactions?|payments?)|transaction\s+history)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="transaction_search",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="English transaction-history query → ACCOUNT_LOOKUP",
            ),
        ),
        (
            re.compile(
                r"\b(block.*card|blocking.*card|card.*lost|card.*stolen|freeze.*card)\b",
                re.IGNORECASE,
            ),
            Intent(
                name="card_block",
                workers=(WorkerName.ACCOUNT_LOOKUP,),
                rationale="English card-block intent → ACCOUNT_LOOKUP; reviewer decides escalation",
            ),
        ),
        (
            re.compile(
                r"\b(simulate|simulation|monthly.*payment|payment.*monthly)\b", re.IGNORECASE
            ),
            Intent(
                name="loan_simulation",
                workers=(WorkerName.SIMULATOR, WorkerName.PRODUCT_LOOKUP),
                rationale="English explicit simulation request",
            ),
        ),
        (
            re.compile(r"\b(gdpr|dora|cnil|bafin|regulation|compliance)\b", re.IGNORECASE),
            Intent(
                name="regulation",
                workers=(WorkerName.REGULATION_LOOKUP,),
                rationale="English regulatory keyword present",
            ),
        ),
    ],
}


def classify_intent(text: str, language: LanguageCode) -> Intent | None:
    """Match ``text`` against the cue table for ``language``.

    Returns the first intent whose pattern matches, or ``None`` when nothing
    matches — in which case :func:`plan_for` falls back to the default plan.
    """
    for pattern, intent in _INTENT_RULES[language]:
        if pattern.search(text):
            return intent
    return None


def classify_all_intents(text: str, language: LanguageCode) -> list[Intent]:
    """Return all intents whose patterns match ``text`` for ``language``."""
    return [intent for pattern, intent in _INTENT_RULES[language] if pattern.search(text)]


def plan_for(text: str, language: LanguageCode) -> tuple[list[WorkerName], str]:
    """Return the workers to invoke and a human-readable rationale.

    Collects all matching intents so multi-topic queries (e.g. regulatory
    question that also mentions a card) activate all relevant workers.
    """
    intents = classify_all_intents(text, language)
    if not intents:
        return list(_DEFAULT_PLAN), "No intent matched; fan out to default lookups."

    seen: set[WorkerName] = set()
    workers: list[WorkerName] = []
    for intent in intents:
        for w in intent.workers:
            if w not in seen:
                seen.add(w)
                workers.append(w)

    # ESCALATION is terminal — running it alongside other workers causes
    # a race condition where the account_lookup path can overwrite the
    # escalation response. When any intent requires ESCALATION, return it
    # as the sole worker.
    if WorkerName.ESCALATION in seen:
        escalation_intent = next(i for i in intents if WorkerName.ESCALATION in i.workers)
        return [WorkerName.ESCALATION], escalation_intent.rationale

    rationale = "; ".join(i.rationale for i in intents)
    return workers, rationale


def run(state: AgentState) -> dict[str, object]:
    """Planner node entry point."""
    intents = classify_all_intents(state["user_input"], state["language"])
    plan, rationale = plan_for(state["user_input"], state["language"])
    return {
        "plan": plan,
        "intents": [intent.name for intent in intents],
        "plan_rationale": rationale,
    }
