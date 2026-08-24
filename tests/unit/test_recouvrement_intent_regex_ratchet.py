"""The measured regex baseline over the labeled intent set is PINNED (ADR 0053 §7).

This is a pin, not a one-way ratchet, on purpose: the regex column is the NULL
FLOOR of ADR 0021's contribution math for the future LLM classifier, and a floor
that drifts silently in EITHER direction corrupts every comparison built on it.
A drop is a regression; a silent rise moves the bar the LLM is judged against
without anyone deciding it. Both must arrive as a visible re-measure.

To re-pin after a deliberate change (to the word lists, the parsers, or the set):
run ``uv run python -m eval.intent_bench``, read the printed counts, update the
constants below with the new figures and set sha, and say so in the commit. The
pin is keyed to the set's content sha: touching the referent invalidates the
numbers by construction, because a baseline is a property of the (set,
classifier) PAIR, never of the classifier alone.
"""

from __future__ import annotations

from eval.intent_bench import build_report, load_intent_set, score_regex_column

#: Measured 2026-08-24 (uv run python -m eval.intent_bench), set 2026-08-23.1 — a
#: deliberate re-pin: the dead German tokens (ae/oe/ue transliterations the normalizer
#: never produces, the separable « fasse … zusammen », the nominal forms Anruf/Rückruf/
#: Zusammenfassung/Begleichung) were fixed in the word lists, and ONLY the German column
#: moved: de 26 → 32 correct. fr and en are unchanged to the case, the remaining misses
#: are genuine paraphrases (the LLM layer's job), and the referent itself is untouched
#: (same sha). Previous pin, 2026-08-23: overall 83/120, de 26/40, defaulted 43.
_PINNED_SET_SHA = "63a4a5aba8e5dfca24cf49e6f54b915fff2cc3ae91ec49cbc806dc768b0bbe67"
_PINNED_OVERALL = {"n": 120, "correct": 89, "defaulted": 35}
_PINNED_BY_LANGUAGE = {
    "fr": {"n": 40, "correct": 28, "defaulted": 11},
    "en": {"n": 40, "correct": 29, "defaulted": 12},
    "de": {"n": 40, "correct": 32, "defaulted": 12},
}
_PINNED_FIELDS = {
    "duration_months": {"n": 18, "exact": 12},
    "requested_time": {"n": 8, "exact": 6},
}


def test_the_referent_is_the_one_the_pin_was_measured_on() -> None:
    """A changed set invalidates the pinned numbers by construction — re-measure, re-pin."""
    intent_set = load_intent_set()
    assert intent_set.sha256 == _PINNED_SET_SHA, (
        "the labeled set changed (sha "
        f"{intent_set.sha256[:12]}… vs pinned {_PINNED_SET_SHA[:12]}…) — the baseline is a "
        "property of the (set, classifier) pair: run `uv run python -m eval.intent_bench`, "
        "then update this pin with the freshly measured counts"
    )


def test_regex_baseline_is_pinned_in_both_directions() -> None:
    """The regex column over the pinned set answers exactly the measured counts."""
    intent_set = load_intent_set()
    verdicts = score_regex_column(intent_set.cases)
    report = build_report(intent_set, verdicts)
    regex_column = report["columns"]["regex"]  # type: ignore[index]
    overall = regex_column["overall"]
    measured_overall = {key: overall[key] for key in ("n", "correct", "defaulted")}
    assert measured_overall == _PINNED_OVERALL, (
        f"regex baseline moved: {measured_overall} vs pinned {_PINNED_OVERALL} — a deliberate "
        "matcher change must re-measure and re-pin; a surprise here is a silent behaviour change"
    )
    for language, pinned in _PINNED_BY_LANGUAGE.items():
        counts = regex_column["by_language"][language]
        measured = {key: counts[key] for key in ("n", "correct", "defaulted")}
        assert measured == pinned, f"{language}: {measured} vs pinned {pinned}"
    assert regex_column["fields"] == _PINNED_FIELDS
