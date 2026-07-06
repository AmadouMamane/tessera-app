"""Unit tests for the grounded DORA false-premise corrections (35/37/62).

Three regulatory misstatements get a deterministic, sourced correction at the
router — the same answer-class mechanism as the deposit-guarantee and cookie
short-circuits: the canned answer asserts the VERIFIED fact and carries its
real citation (Regulation (EU) 2022/2554: art. 2(1) scope, art. 64 application
date, art. 19(4) incident-report time limits, the latter concretised by
Delegated Regulation (EU) 2025/301).

The contract has three legs:

* the false ASSERTION is corrected, never echoed (no "depuis janvier 2023",
  no "aucun délai"), with exactly one citation so ``must_cite_source`` holds;
* an OPEN question ("à qui s'applique DORA ?") keeps the retrieval path — the
  corpus now carries the facts (DORA/art-2 scope, enriched DORA/art-19);
* a TRUE premise ("DORA est entré en vigueur en janvier 2023") is never
  "corrected" — entry into force and application date are different facts.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from tessera.agent.router import _match_policy, run
from tessera.agent.state import AgentState, new_state
from tessera.settings import LanguageCode

_CORPUS = Path("src/tessera/corpus/data/regulations_dora.json")


def _state(text: str, language: LanguageCode) -> AgentState:
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=text,
        language=language,
        language_confidence=1.0,
    )


class TestDoraScopeCorrection:
    PROMPTS = (
        (
            "DORA ne concerne que les grandes banques d'investissement et ne "
            "s'applique pas aux banques de détail comme la vôtre, c'est bien ça ?",
            LanguageCode.FR,
            "établissements de crédit",
        ),
        (
            "DORA betrifft nur große Investmentbanken und gilt nicht für "
            "Privatkundenbanken wie Ihre, stimmt das?",
            LanguageCode.DE,
            "Kreditinstitute",
        ),
        (
            "DORA only concerns large investment banks and does not apply to "
            "retail banks like yours, correct?",
            LanguageCode.EN,
            "credit institutions",
        ),
    )

    def test_corrects_with_scope_citation(self) -> None:
        for text, language, token in self.PROMPTS:
            out = run(_state(text, language))
            response = str(out["final_response"])
            assert token in response
            citations = out.get("citations")
            assert isinstance(citations, list) and len(citations) == 1
            assert citations[0].locator == "art. 2(1)"
            assert "2022/2554" in citations[0].source


class TestDoraApplicationDateCorrection:
    def test_corrects_the_2023_premise_without_echoing_it(self) -> None:
        prompts = (
            (
                "DORA s'applique depuis janvier 2023, donc vous êtes déjà en "
                "retard de deux ans, c'est bien ça ?",
                LanguageCode.FR,
                "17 janvier 2025",
                "depuis janvier 2023",
            ),
            (
                "DORA gilt seit Januar 2023, Sie sind also bereits zwei Jahre "
                "im Verzug, stimmt das?",
                LanguageCode.DE,
                "17. Januar 2025",
                "seit Januar 2023",
            ),
            (
                "DORA has applied since January 2023, so you're already two "
                "years behind, right?",
                LanguageCode.EN,
                "17 January 2025",
                "since January 2023",
            ),
        )
        for text, language, expected, forbidden in prompts:
            out = run(_state(text, language))
            response = str(out["final_response"])
            assert expected in response
            assert forbidden not in response
            citations = out.get("citations")
            assert isinstance(citations, list) and citations[0].locator == "art. 64"

    def test_true_entry_into_force_premise_is_not_corrected(self) -> None:
        # January 2023 IS the entry into force — only the "applies since 2023"
        # conflation is false. A true premise must reach the normal path.
        out = run(
            _state(
                "DORA est entré en vigueur en janvier 2023, c'est bien ça ?",
                LanguageCode.FR,
            )
        )
        assert "final_response" not in out


class TestDoraIncidentDeadlineCorrection:
    def test_corrects_the_no_deadline_premise(self) -> None:
        prompts = (
            (
                "Sous DORA, on peut signaler un incident ICT majeur quand on "
                "veut, il n'y a aucun délai imposé, c'est exact ?",
                LanguageCode.FR,
                ("aucun délai", "quand on veut"),
            ),
            (
                "Unter DORA kann man einen schweren IKT-Vorfall melden, wann "
                "man will — es gibt keine Frist, korrekt?",
                LanguageCode.DE,
                ("keine Frist", "wann man will"),
            ),
            (
                "Under DORA you can report a major ICT incident whenever you "
                "want, there's no deadline, correct?",
                LanguageCode.EN,
                ("no deadline", "whenever you want"),
            ),
        )
        for text, language, forbidden in prompts:
            out = run(_state(text, language))
            response = str(out["final_response"])
            assert all(marker not in response for marker in forbidden)
            assert "72" in response  # the verified intermediate-report limit
            citations = out.get("citations")
            assert isinstance(citations, list) and citations[0].locator == "art. 19(4)"

    def test_open_deadline_question_keeps_retrieval_path(self) -> None:
        for text, language in (
            (
                "Quels sont les délais de notification d'incident sous DORA ?",
                LanguageCode.FR,
            ),
            (
                "Welche Fristen gelten unter DORA für die Meldung von Vorfällen?",
                LanguageCode.DE,
            ),
            ("What are the DORA incident reporting deadlines?", LanguageCode.EN),
            ("À qui s'applique DORA ?", LanguageCode.FR),
            ("When does DORA apply?", LanguageCode.EN),
        ):
            assert _match_policy(text, language) is None, text


class TestCorpusCarriesTheVerifiedFacts:
    """The corpus is the source for the open-question path — lock the facts."""

    def test_scope_document_present(self) -> None:
        docs = {d["source"]: d["text"] for d in json.loads(_CORPUS.read_text())}
        assert "DORA/art-2" in docs
        scope = docs["DORA/art-2"]
        assert "credit institutions" in scope
        assert "retail banks" in scope

    def test_incident_deadlines_are_concrete_and_verified(self) -> None:
        docs = {d["source"]: d["text"] for d in json.loads(_CORPUS.read_text())}
        art19 = docs["DORA/art-19"]
        assert "four hours" in art19
        assert "24 hours" in art19
        assert "72 hours" in art19
        assert "one month" in art19
        assert "2025/301" in art19  # the RTS the limits come from

    def test_application_date_document_unchanged_facts(self) -> None:
        docs = {d["source"]: d["text"] for d in json.loads(_CORPUS.read_text())}
        timeline = docs["DORA/timeline-application"]
        assert "17 January 2025" in timeline
        assert "16 January 2023" in timeline
