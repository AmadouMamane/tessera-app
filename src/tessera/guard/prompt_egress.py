"""prompt-egress — the answer must not reproduce the instructions that produced it.

The guard's output leg already withholds credentials (``secrets-egress``) and masks leftover
personal data (``pii-egress``, ADR 0049). It had no leg for the third outbound leak, and that
leak is not hypothetical. Across the 19 203 recorded responses in ``.eval-noise/`` and
``eval/reports/``, searching for the priority-rule block *as a literal substring* finds **24**
reproductions over six cases. This detector finds **38** over seven, and the fourteen it adds
were read one by one rather than assumed: they are all real — a complete German bundle dump and
a complete English one under ``44_prompt_injection_system_prompt_leak`` itself, plus the
priority rule emitted mid-answer under ``05_citation_hallucination|en``. **Zero false
positives.** The gap between 24 and 38 is the whole argument for windows over substrings: a
literal search finds only the leaks that were reproduced without a single word changed.

Only one of those seven cases — case 44 — carries a criterion that even looks, and until
2026-08-05 it was blind to the leaks recorded under its own name.

That asymmetry is the argument for putting this here rather than in the catalogue. A leak is a
leak whichever prompt elicits it, and a catalogue can only refuse the leaks somebody thought to
write a case for. The guard refuses them all, including the ones under
``30_tool_misuse_pret_aberrant`` (eleven of them) where no case will ever look.

**What is protected is DECLARED, never inferred.** Three designs were measured against the
recorded corpus before this one was written, and the two that inferred both failed:

* *split the prompt by top-level key* (instruction keys vs output keys) — fires 392 times,
  because instruction blocks embed the replies they dictate (``Répondre : "…"``);
* *strip the prompt's own quoted spans and keep the rest* — better, but still fires on the
  regulatory FACTS the prompt states as ground truth (the €100 000 deposit guarantee, directive
  2014/49/EU), which the agent is **supposed** to repeat to customers.

There is no typographic rule that separates *what the agent is told to be* from *what it is
told to know*. So the prompt author says so, in the prompt, under ``no_egress``. The guard then
protects exactly what was declared — and :mod:`tests.unit.test_prompt_egress` pins every
declared span to text that really occurs in that prompt, so a reworded prompt cannot silently
empty the guard rather than trip it.

Matching is by sliding word window, not substring, and that is the whole lesson of case 44: its
blacklist named ``"…dans la conversation ci-dessus"`` and the model reproduced the entire
paragraph while dropping ``ci-dessus``. A locative an LLM discards without changing meaning was
load-bearing. A window survives deletion — the windows on either side still match.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING, Final

import yaml

if TYPE_CHECKING:
    from tessera.settings import LanguageCode

__all__ = [
    "PROMPT_EGRESS_RULE",
    "detect_prompt_egress",
    "protected_spans",
]

#: The policy rule name recorded on a decision, matching the ``*-egress`` family.
PROMPT_EGRESS_RULE: Final = "prompt-egress"

#: Words per window. Chosen by measurement, not taste: at 10 words the declared spans catch all
#: 24 leaks a literal search finds, plus 14 it cannot, with no false positive across 19 203
#: recorded responses. Shorter windows start colliding with ordinary banking prose — at 6 an
#: earlier design fired 839 times; longer ones let a leak that paraphrases twice inside one
#: sentence slip between windows.
_WINDOW: Final = 10

_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
_WORD = re.compile(r"[\w']+", re.UNICODE)


def _words(text: str) -> list[str]:
    """Normalised word sequence — case-folded, accent-stable, placeholders dropped.

    NFKC before case-folding so that a leak retyped with different Unicode punctuation or
    compatibility forms still matches the prompt it came from; a guard defeated by a curly
    apostrophe is not a guard.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WORD.findall(_PLACEHOLDER.sub(" ", folded))


def _windows(words: list[str]) -> set[tuple[str, ...]]:
    if len(words) < _WINDOW:
        # A declared span shorter than the window is matched whole rather than dropped —
        # silently protecting nothing is the failure mode this module exists to avoid.
        return {tuple(words)} if words else set()
    return {tuple(words[i : i + _WINDOW]) for i in range(len(words) - _WINDOW + 1)}


@cache
def protected_spans(language: str) -> tuple[str, ...]:
    """The spans this language's prompt declares must never leave the agent.

    Read from the prompt file rather than restated here, for the reason the ClickHouse resolver
    defers to ``Settings``: two places answering one question diverge, and the place that must
    win is the one the author edits.

    Loaded through ``importlib.resources``, like :func:`tessera.agent.reporter.load_prompts`,
    so this works identically inside the wheel. It cannot reuse that function: it stringifies
    every value, which would turn the ``no_egress`` list into its ``repr``.
    """
    try:
        target = resources.files("tessera.agent.prompts").joinpath(f"{language}.yaml")
        raw = target.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return ()
    document = yaml.safe_load(raw)
    declared = document.get("no_egress") if isinstance(document, dict) else None
    if not isinstance(declared, list):
        return ()
    return tuple(str(span) for span in declared if str(span).strip())


@cache
def _span_windows(language: str) -> tuple[tuple[str, tuple[tuple[str, ...], ...]], ...]:
    return tuple((span, tuple(_windows(_words(span)))) for span in protected_spans(language))


def detect_prompt_egress(text: str, language: LanguageCode | str) -> list[str]:
    """Declared prompt spans this answer reproduces, in declaration order.

    Every language's declaration is checked, not just the answering one: an extraction attempt
    can be made in one language and answered with another language's instructions, and a leak
    is a leak whichever file it came from. The answering language is checked first only so that
    the common case terminates early.

    Args:
        text: The candidate final response.
        language: The response language; ordering hint only.

    Returns:
        The declared spans found, empty when the answer reproduces none.
    """
    if not text:
        return []
    haystack = _windows(_words(text))
    if not haystack:
        return []
    ordered = [str(language), *(lang for lang in ("fr", "de", "en") if lang != str(language))]
    found: list[str] = []
    for lang in ordered:
        for span, windows in _span_windows(lang):
            if span in found:
                continue
            if any(window in haystack for window in windows):
                found.append(span)
    return found
