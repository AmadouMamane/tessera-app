"""Metamorphic wiring proof — Phase 2, Table A.1 first half.

Extends the Phase 1 harness (``tests/support/wiring.py``, ``test_signal_wiring.py``
— both frozen) to the first nine ``real-computed`` rows of Table A.1 in
``docs/design/signal-wiring-map.md``: the pure/injectable turn & text scans.

Per the map's load-bearing rule, every ``compute`` below reproduces the
*route's* source-assembly from ``src/tessera/api/routes/observability.py`` —
the exact tuple/dict shape and f-string concatenation the route builds from
``replay_mod.recent_bundles()`` — rather than a shortcut call to the bare
provider. None of the nine routes alias or freeze their source the way
``embedding_skew``/``disclosure`` do, so all nine are *expected* WIRED; this
file proves that empirically instead of assuming it (Rule 3: empirical truth
beats the map).

Four of the nine observables are *rate*-typed (``leak_rate`` appears twice,
plus ``toxicity_rate``, ``retraction_rate``); each gets an additional
duplication-invariant probe — concatenating the whole input series with
itself must leave the rate unchanged — per the map's Table B footer. The
other five observables are counts (``n_anomalies``, ``n_anomalous``,
``n_contradictions``, ``n_hidden``) or a boolean flip (``attributed``), for
which duplication is not a meaningful invariant and is intentionally omitted.

Signals covered (route -> function):
  * #38 output-pii-leak           - /observability/pii-leak     -> pii_leak.aggregate_leaks
  * #60 toxicity-rate              - /observability/toxicity     -> toxicity.scan_toxicity
  * #33 cost-anomaly-security      - /observability/cost         -> cost_anomaly.analyze_costs
  * #69 anomalous-conversations    - /observability/anomalies    -> anomalies.detect_anomalies
  * #17 what-changed-rootcause     - /observability/what-changed -> whatchanged.what_changed
  * #30 multiturn-contradiction    - /observability/contradictions
    -> contradiction.detect_contradictions
  * #90 midstream-guard-retraction - /observability/guard-retraction
    -> guard_retraction.analyze_retractions
  * #74 cross-tenant-leakage       - /observability/cross-tenant -> cross_tenant.detect_cross_tenant
  * #72 unicode-steganography      - /observability/steganography/{id}
    -> steganography.scan_text

None of these routes pass an ``agent``/``at`` filter that would change the
*shape* handed to the provider (only which bundles populate it), so the seam
is ``fn-arg`` for all nine, matching the map.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from tessera.guard.decisions import load_policy
from tessera.observability.anomalies import AnomalyReport, detect_anomalies
from tessera.observability.contradiction import detect_contradictions
from tessera.observability.cost_anomaly import CostReport, analyze_costs
from tessera.observability.cross_tenant import CrossTenantReport, detect_cross_tenant
from tessera.observability.guard_retraction import RetractionReport, analyze_retractions
from tessera.observability.lineage import Lineage
from tessera.observability.pii_leak import PIILeakSummary, aggregate_leaks
from tessera.observability.steganography import StegoReport, scan_text
from tessera.observability.toxicity import ToxicityReport, scan_toxicity
from tessera.observability.whatchanged import WhatChangedReport, what_changed
from tests.support.wiring import Probe, Verdict, assert_invariant_ok, assert_wired, evaluate

if TYPE_CHECKING:
    from collections.abc import Sequence

# --------------------------------------------------------------------------- #
# Observers — payload -> scalar
# --------------------------------------------------------------------------- #


def _obs_leak_rate(payload: object) -> float:
    return cast("PIILeakSummary", payload).leak_rate


def _obs_toxicity_rate(payload: object) -> float:
    return cast("ToxicityReport", payload).toxicity_rate


def _obs_n_anomalies(payload: object) -> int:
    return cast("CostReport", payload).n_anomalies


def _obs_n_anomalous(payload: object) -> int:
    return cast("AnomalyReport", payload).n_anomalous


def _obs_attributed(payload: object) -> bool:
    return cast("WhatChangedReport", payload).attributed


def _obs_contradiction_total(payload: object) -> int:
    return cast("int", payload)


def _obs_retraction_rate(payload: object) -> float:
    return cast("RetractionReport", payload).retraction_rate


def _obs_cross_tenant_rate(payload: object) -> float:
    return cast("CrossTenantReport", payload).leak_rate


def _obs_n_hidden(payload: object) -> int:
    return cast("StegoReport", payload).n_hidden


# --------------------------------------------------------------------------- #
# #38 output-pii-leak. Route (/observability/pii-leak, ~L2601-2611) builds
# turns as (b.original_answer, f"{b.question}\n{b.context}") for each bundle
# from replay_mod.recent_bundles(at, _agent_or_none(agent)), then returns
# asdict of pii_leak_mod.aggregate_leaks(turns). Straight passthrough from
# the bundle store, no alias/freeze -> seam fn-arg. The route calls
# aggregate_leaks(turns) with no `policy=` kwarg, so the default resolves the
# real load_policy() — our compute does the same.
# --------------------------------------------------------------------------- #

_LEAK_IBAN = "FR76 3000 6000 0112 3456 7890 189"
_LEAK_OTHER_IBAN = "DE89 3704 0044 0532 0130 00"

_PII_LEAK_TRIPLES: list[tuple[str, str, str]] = [
    ("Quel est mon IBAN ?", f"IBAN enregistre {_LEAK_IBAN}", f"Votre IBAN est {_LEAK_IBAN}."),
    ("Quel est le taux du pret ?", "Pret Aurore taux 3", "Le taux du pret est de 3 pourcent."),
]
_PII_LEAK_BASE: list[tuple[str, str]] = [
    (answer, f"{question}\n{context}") for question, context, answer in _PII_LEAK_TRIPLES
]


def _pii_leak_compute(turns: list[tuple[str, str]]) -> object:
    return aggregate_leaks(turns)


def _pii_leak_perturb(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    leaked = (
        f"Le virement precedent est parti vers {_LEAK_OTHER_IBAN}.",
        "Bonjour, comment allez-vous ?",
    )
    return [*turns, leaked]


def _duplicate_pii_leak(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [*turns, *turns]


_pii_leak_probe: Probe[list[tuple[str, str]]] = Probe(
    key="output-pii-leak#38",
    compute=_pii_leak_compute,
    observe=_obs_leak_rate,
    base_source=_PII_LEAK_BASE,
    perturb=_pii_leak_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

_PII_LEAK_MIXED = _pii_leak_perturb(_PII_LEAK_BASE)  # 1 leak / 3 turns

_pii_leak_dup_probe: Probe[list[tuple[str, str]]] = Probe(
    key="output-pii-leak#38-dup",
    compute=_pii_leak_compute,
    observe=_obs_leak_rate,
    base_source=_PII_LEAK_MIXED,
    perturb=_duplicate_pii_leak,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #60 toxicity-rate. Route (/observability/toxicity, ~L2415-2425) builds turns
# as (b.question, b.original_answer) for each bundle from
# replay_mod.recent_bundles(at, _agent_or_none(agent)), then returns asdict
# of toxicity_mod.scan_toxicity(turns). Straight passthrough, seam fn-arg.
# --------------------------------------------------------------------------- #

_TOXICITY_BASE: list[tuple[str, str]] = [
    ("Quel est mon solde ?", "Votre solde est de 1200 EUR."),
    ("Comment bloquer ma carte ?", "Votre carte a ete bloquee avec succes."),
]


def _toxicity_compute(turns: list[tuple[str, str]]) -> object:
    return scan_toxicity(turns)


def _toxicity_perturb(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    toxic_turn = (
        "Pourquoi votre service est si lent ?",
        "Vous etes vraiment un idiot de demander ca.",
    )
    return [*turns, toxic_turn]


def _duplicate_toxicity(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [*turns, *turns]


_toxicity_probe: Probe[list[tuple[str, str]]] = Probe(
    key="toxicity-rate#60",
    compute=_toxicity_compute,
    observe=_obs_toxicity_rate,
    base_source=_TOXICITY_BASE,
    perturb=_toxicity_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

_TOXICITY_MIXED = _toxicity_perturb(_TOXICITY_BASE)  # 1 toxic / 3 turns

_toxicity_dup_probe: Probe[list[tuple[str, str]]] = Probe(
    key="toxicity-rate#60-dup",
    compute=_toxicity_compute,
    observe=_obs_toxicity_rate,
    base_source=_TOXICITY_MIXED,
    perturb=_duplicate_toxicity,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #33 cost-anomaly-security. Route (/observability/cost, ~L2503-2513) builds
# turns as (b.question, f"{b.question}\n{b.context}\n{b.original_answer}")
# for each bundle from replay_mod.recent_bundles(at, _agent_or_none(agent)),
# then returns asdict of cost_anomaly_mod.analyze_costs(turns). Straight
# passthrough, seam fn-arg. n_anomalies is a count, not a rate — no
# duplication invariant (out of scope per the map's Table B footer).
# --------------------------------------------------------------------------- #

_COST_BASE_TRIPLES: list[tuple[str, str, str]] = [
    ("Quel est mon solde ?", "Compte courant Aurore.", "Votre solde est de 1200 EUR."),
    ("Comment bloquer ma carte ?", "Carte Visa Aurore.", "Votre carte a ete bloquee avec succes."),
    (
        "Quel est le taux du pret ?",
        "Pret personnel Aurore.",
        "Le taux nominal est de 3,2 pourcent.",
    ),
]
_COST_BASE: list[tuple[str, str]] = [
    (question, f"{question}\n{context}\n{answer}")
    for question, context, answer in _COST_BASE_TRIPLES
]


def _cost_compute(turns: list[tuple[str, str]]) -> object:
    return analyze_costs(turns)


def _cost_perturb(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    huge_context = "contexte reinjecte en boucle par un prompt malveillant. " * 400
    loop_question = "requete anormalement volumineuse"
    loop_turn = (loop_question, f"{loop_question}\n{huge_context}\nreponse")
    return [*turns, loop_turn]


_cost_probe: Probe[list[tuple[str, str]]] = Probe(
    key="cost-anomaly-security#33",
    compute=_cost_compute,
    observe=_obs_n_anomalies,
    base_source=_COST_BASE,
    perturb=_cost_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #69 anomalous-conversations. Route (/observability/anomalies, ~L2614-2624)
# groups each bundle's question under
# by_conversation[bundle.conversation_id or "<none>"], then returns asdict of
# anomalies_mod.detect_anomalies(by_conversation). Straight passthrough, seam
# fn-arg. n_anomalous is a count — no duplication invariant.
# --------------------------------------------------------------------------- #

_ANOMALIES_BASE: dict[str, list[str]] = {
    "conv-normal": ["Quel est mon solde ?", "Comment bloquer ma carte ?"],
}


def _anomalies_compute(sessions: dict[str, list[str]]) -> object:
    return detect_anomalies(sessions)


def _anomalies_perturb(sessions: dict[str, list[str]]) -> dict[str, list[str]]:
    looping = ["Quel est mon solde ?", "quel est mon solde ?", "QUEL EST MON SOLDE ?"]
    return {**sessions, "conv-looping": looping}


_anomalies_probe: Probe[dict[str, list[str]]] = Probe(
    key="anomalous-conversations#69",
    compute=_anomalies_compute,
    observe=_obs_n_anomalous,
    base_source=_ANOMALIES_BASE,
    perturb=_anomalies_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #17 what-changed-rootcause. Route (/observability/what-changed, ~L2627-2649)
# filters recent_bundles(at, agent) down to those with a non-None lineage,
# takes the last two (prev, curr) of that filtered list, and calls
# whatchanged_mod.what_changed with prev/curr lineage and original_score.
# compute reproduces the route's own "last two of a longer list" selection,
# not a bare 2-arg call — seam fn-arg.
# --------------------------------------------------------------------------- #

_LINEAGE_A = Lineage(
    model="llama-3.3-70b",
    prompt_version="hash-p1",
    guard_policy_version="hash-g1",
    doc_sources=["credit_aurore_fr#1"],
)

_WHATCHANGED_BASE: list[tuple[Lineage, float]] = [
    (_LINEAGE_A, 0.92),
    (_LINEAGE_A, 0.90),
    (_LINEAGE_A, 0.88),
]


def _whatchanged_compute(bundles: list[tuple[Lineage, float]]) -> object:
    prev_lineage, prev_score = bundles[-2]
    curr_lineage, curr_score = bundles[-1]
    return what_changed(
        prev_lineage=prev_lineage,
        prev_score=prev_score,
        curr_lineage=curr_lineage,
        curr_score=curr_score,
    )


def _whatchanged_perturb(bundles: list[tuple[Lineage, float]]) -> list[tuple[Lineage, float]]:
    *rest, last = bundles
    curr_lineage, curr_score = last
    changed_lineage = replace(curr_lineage, prompt_version="hash-p2-edited")
    return [*rest, (changed_lineage, curr_score)]


_whatchanged_probe: Probe[list[tuple[Lineage, float]]] = Probe(
    key="what-changed-rootcause#17",
    compute=_whatchanged_compute,
    observe=_obs_attributed,
    base_source=_WHATCHANGED_BASE,
    perturb=_whatchanged_perturb,
    relation="changes",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #30 multiturn-contradiction. Route (/observability/contradictions,
# ~L2687-2708) groups each bundle's (question, answer) pair into a
# per-conversation-id dict keyed by `conversation_id or "<none>"`, awaits
# contradiction_mod.detect_contradictions(turns) per conversation with the
# real embedder, and sums len(report.contradictions) across conversations.
# The route never overrides the embedder — it always uses the real one. The
# map's own test column sanctions `unit+fake` here: we substitute a
# deterministic toy embedder for determinism/no-I/O, exactly like the Phase 1
# corpus-coverage probe substitutes `_bow_embed` for its embedder. This is a
# test-harness necessity, not a route-level alias/freeze — seam stays fn-arg.
# --------------------------------------------------------------------------- #

_CONTRA_VECTORS: dict[str, list[float]] = {
    "card status?": [1.0, 0.0, 0.0],
    "is my card ok?": [1.0, 0.0, 0.0],  # same topic as above
    "blocked": [0.0, 1.0, 0.0],
    "active": [0.0, 0.0, 1.0],  # orthogonal to "blocked" -> disagree
}


async def _contra_embed(texts: Sequence[str]) -> list[list[float]]:
    return [_CONTRA_VECTORS.get(t, [0.0, 0.0, 0.0]) for t in texts]


async def _contradiction_gather(by_conversation: dict[str, list[tuple[str, str]]]) -> int:
    total = 0
    for turns in by_conversation.values():
        report = await detect_contradictions(turns, embedder=_contra_embed)
        total += report.n_contradictions
    return total


def _contradiction_compute(by_conversation: dict[str, list[tuple[str, str]]]) -> object:
    return asyncio.run(_contradiction_gather(by_conversation))


def _contradiction_perturb(
    by_conversation: dict[str, list[tuple[str, str]]],
) -> dict[str, list[tuple[str, str]]]:
    # Same topic ("card status?" ~ "is my card ok?"), opposite answers
    # ("blocked" vs "active") -> a contradiction the base source has none of.
    return {**by_conversation, "c1": [("card status?", "blocked"), ("is my card ok?", "active")]}


_CONTRADICTION_BASE: dict[str, list[tuple[str, str]]] = {
    "c1": [("card status?", "blocked"), ("is my card ok?", "blocked")],
}

_contradiction_probe: Probe[dict[str, list[tuple[str, str]]]] = Probe(
    key="multiturn-contradiction#30",
    compute=_contradiction_compute,
    observe=_obs_contradiction_total,
    base_source=_CONTRADICTION_BASE,
    perturb=_contradiction_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #90 midstream-guard-retraction. Route (/observability/guard-retraction,
# ~L2528-2534) collects b.original_answer for each bundle from
# replay_mod.recent_bundles(), then returns asdict of
# guard_retraction_mod.analyze_retractions(answers, policy=load_policy()).
# Straight passthrough with the real, live policy — seam fn-arg.
# --------------------------------------------------------------------------- #

_RETRACTION_IBAN = "DE89 3704 0044 0532 0130 00"

_GUARD_RETRACTION_BASE: list[str] = [
    "Votre solde est disponible dans l'application mobile.",
    "Le rendez-vous est confirme pour demain a 10h.",
]


def _guard_retraction_compute(answers: list[str]) -> object:
    return analyze_retractions(answers, policy=load_policy())


def _guard_retraction_perturb(answers: list[str]) -> list[str]:
    prefix = "Merci pour votre message, voici le detail complet de l'operation demandee. " * 3
    late_leak = f"{prefix}Le virement a ete envoye vers {_RETRACTION_IBAN}."
    return [*answers, late_leak]


def _duplicate_strings(answers: list[str]) -> list[str]:
    return [*answers, *answers]


_guard_retraction_probe: Probe[list[str]] = Probe(
    key="midstream-guard-retraction#90",
    compute=_guard_retraction_compute,
    observe=_obs_retraction_rate,
    base_source=_GUARD_RETRACTION_BASE,
    perturb=_guard_retraction_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

_GUARD_RETRACTION_MIXED = _guard_retraction_perturb(_GUARD_RETRACTION_BASE)  # 1 retraction / 3

_guard_retraction_dup_probe: Probe[list[str]] = Probe(
    key="midstream-guard-retraction#90-dup",
    compute=_guard_retraction_compute,
    observe=_obs_retraction_rate,
    base_source=_GUARD_RETRACTION_MIXED,
    perturb=_duplicate_strings,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #74 cross-tenant-leakage. Route (/observability/cross-tenant, ~L2408-2412)
# builds turns as (b.conversation_id or "", b.context) for each bundle from
# replay_mod.recent_bundles(), then returns asdict of
# cross_tenant_mod.detect_cross_tenant(turns). Straight passthrough, seam
# fn-arg.
# --------------------------------------------------------------------------- #

_TENANT_A = "434b766f-9e5a-4c21-8d0e-111111111111"
_TENANT_B = "76721fda-f230-4a55-9c1b-222222222222"

_CROSS_TENANT_BASE: list[tuple[str, str]] = [
    (_TENANT_A, f"Contexte reserve au client {_TENANT_A}."),
    (_TENANT_B, f"Contexte reserve au client {_TENANT_B}."),
]


def _cross_tenant_compute(turns: list[tuple[str, str]]) -> object:
    return detect_cross_tenant(turns)


def _cross_tenant_perturb(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    *rest, last = turns
    conversation_id, context = last
    leaked_context = f"{context} Voir aussi le dossier de {_TENANT_A}."
    return [*rest, (conversation_id, leaked_context)]


def _duplicate_cross_tenant(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [*turns, *turns]


_cross_tenant_probe: Probe[list[tuple[str, str]]] = Probe(
    key="cross-tenant-leakage#74",
    compute=_cross_tenant_compute,
    observe=_obs_cross_tenant_rate,
    base_source=_CROSS_TENANT_BASE,
    perturb=_cross_tenant_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)

_CROSS_TENANT_MIXED = _cross_tenant_perturb(_CROSS_TENANT_BASE)  # 1 leak / 2 turns

_cross_tenant_dup_probe: Probe[list[tuple[str, str]]] = Probe(
    key="cross-tenant-leakage#74-dup",
    compute=_cross_tenant_compute,
    observe=_obs_cross_tenant_rate,
    base_source=_CROSS_TENANT_MIXED,
    perturb=_duplicate_cross_tenant,
    relation="invariant",
    seam="fn-arg",
    declared_class="real-computed",
)

# --------------------------------------------------------------------------- #
# #72 unicode-steganography. Route (/observability/steganography/{bundle_id},
# ~L2721-2727) loads one bundle via replay_mod.get_bundle(bundle_id) and
# returns asdict of
# steganography_mod.scan_text(f"{bundle.question}\n{bundle.context}").
# Source is ONE bundle's text, not a list — seam fn-arg. n_hidden is a count
# over a single string, not a rate over a series — no duplication invariant.
# --------------------------------------------------------------------------- #

_STEGO_BASE: tuple[str, str] = (
    "Quel est le solde de mon compte ?",
    "Le solde est disponible dans l'application.",
)


def _stego_compute(source: tuple[str, str]) -> object:
    question, context = source
    return scan_text(f"{question}\n{context}")


def _stego_perturb(source: tuple[str, str]) -> tuple[str, str]:
    question, context = source
    hidden = chr(0x200B)  # zero-width space, built via chr() -- no literal hidden char here
    return (question, f"{context}{hidden}surprise")


_stego_probe: Probe[tuple[str, str]] = Probe(
    key="unicode-steganography#72",
    compute=_stego_compute,
    observe=_obs_n_hidden,
    base_source=_STEGO_BASE,
    perturb=_stego_perturb,
    relation="up",
    seam="fn-arg",
    declared_class="real-computed",
)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_output_pii_leak_is_wired() -> None:
    """An answer-only IBAN (absent from its source) moves leak_rate up."""
    result = assert_wired(_pii_leak_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_output_pii_leak_rate_invariant_under_duplication() -> None:
    """Duplicating the whole turn series leaves leak_rate unchanged."""
    result = assert_invariant_ok(_pii_leak_dup_probe)
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_toxicity_rate_is_wired() -> None:
    """A toxic-lexicon term in an answer moves toxicity_rate up."""
    result = assert_wired(_toxicity_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_toxicity_rate_invariant_under_duplication() -> None:
    """Duplicating the whole turn series leaves toxicity_rate unchanged."""
    result = assert_invariant_ok(_toxicity_dup_probe)
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_cost_anomaly_security_is_wired() -> None:
    """A turn > 3x the median token footprint (>=3 turns) moves n_anomalies up."""
    result = assert_wired(_cost_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_anomalous_conversations_is_wired() -> None:
    """A looping session of 3 near-identical questions moves n_anomalous up."""
    result = assert_wired(_anomalies_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_what_changed_rootcause_is_wired() -> None:
    """A prompt_version change concurrent with a regression flips attributed."""
    result = assert_wired(_whatchanged_probe)
    assert result.d0 == 0.0
    assert result.d1 == 1.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_multiturn_contradiction_is_wired() -> None:
    """Same-topic questions with opposite answers move n_contradictions up."""
    result = assert_wired(_contradiction_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_midstream_guard_retraction_is_wired() -> None:
    """A late-offset IBAN in a streamed answer moves retraction_rate up."""
    result = assert_wired(_guard_retraction_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_midstream_guard_retraction_rate_invariant_under_duplication() -> None:
    """Duplicating the whole answer series leaves retraction_rate unchanged."""
    result = assert_invariant_ok(_guard_retraction_dup_probe)
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_cross_tenant_leakage_is_wired() -> None:
    """A foreign UUID injected into one turn's context moves leak_rate up."""
    result = assert_wired(_cross_tenant_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_cross_tenant_leakage_rate_invariant_under_duplication() -> None:
    """Duplicating the whole turn series leaves leak_rate unchanged."""
    result = assert_invariant_ok(_cross_tenant_dup_probe)
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_unicode_steganography_is_wired() -> None:
    """A zero-width codepoint inserted into the text moves n_hidden up."""
    result = assert_wired(_stego_probe)
    assert result.delta > 0.0
    print(f"A1a  {result.key:32} {result.verdict.value:14} {result.detail}")


def test_a1a_probe_summary() -> None:
    """Diagnostic sweep over every probe in this file, in Table A.1 order."""
    probes: list[Probe[Any]] = [
        _pii_leak_probe,
        _pii_leak_dup_probe,
        _toxicity_probe,
        _toxicity_dup_probe,
        _cost_probe,
        _anomalies_probe,
        _whatchanged_probe,
        _contradiction_probe,
        _guard_retraction_probe,
        _guard_retraction_dup_probe,
        _cross_tenant_probe,
        _cross_tenant_dup_probe,
        _stego_probe,
    ]
    for probe in probes:
        result = evaluate(probe)
        assert result.verdict in {Verdict.WIRED, Verdict.INVARIANT_OK}, (
            f"{probe.key}: expected WIRED/INVARIANT_OK, got {result.verdict.value} "
            f"— {result.detail}"
        )
        print(
            f"A1a  {probe.key:32} {result.verdict.value:14} "
            f"d0={result.d0:.6g} d1={result.d1:.6g} Δ={result.delta:+.6g} "
            f"seam={result.seam}"
        )
