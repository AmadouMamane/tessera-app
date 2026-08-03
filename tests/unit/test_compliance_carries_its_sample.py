"""A compliance score states its sample, and a probe that fails stays visible.

Audit 2026-08-03. Three defects in one module, all pointing the same way — towards a greener
screen than the evidence supports, on the surface a regulator reads.

1. **100 % over nothing.** ``citation_validity``, ``pii_leak`` and ``conformance`` all return
   1.0 on an empty set, and the erasure coverage returned a literal 1.0 when there were no
   conversations. In the situation already measured on 2026-08-01 — last conversation
   2026-07-24, seven-day window, so no bundles at all — the screen announced CTRL-04
   "Exactitude des citations 100 %", CTRL-05 "Minimisation & non-fuite PII 100 %" and CTRL-06
   "Droit à l'effacement 100 %" over zero citations, zero turns and zero conversations.

2. **A failing probe IMPROVED the posture.** ``safe()`` swallowed the exception and wrote
   nothing, and the catalogue loop skipped any signal it could not find — so the control left
   the table, the framework roll-up and the non-conformities list, while ``global_score``
   averaged the survivors. An unreadable calibration file raised the compliance score.

3. **The audit chain was asserted, not asked.** ``audit_present=True`` and
   ``audit_chain_verified=True`` were literals, rendered by ``ai_act.py`` into a satisfied
   Art. 12 obligation whose evidence reads "tamper-evident audit chain verified" — while the
   twin route ``/observability/ai-act`` did the real verification. One obligation, two
   surfaces, two answers, and the affirming one was the regulatory screen (ADR 0026).

The front already had the vocabulary for this: ``Unavailability = "no-sample" | "read-failed" |
"no-reader" | "planned"``. The backend simply never produced it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability import compliance

if TYPE_CHECKING:
    import pytest


def test_a_reading_over_an_empty_sample_is_not_a_measurement() -> None:
    assert compliance.SignalReading(value=1.0, n=0).measured is False
    assert compliance.SignalReading(value=None, n=5, cause="read-failed").measured is False
    assert compliance.SignalReading(value=1.0, n=5).measured is True


def test_a_probe_that_raises_is_recorded_as_read_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """It used to vanish from the mapping, and with it the control it scored.

    It also proves the guard still wraps each probe individually: computing the sample sizes
    outside it would be the obvious way to get them, and would make one raising probe take
    down the whole page instead of one control.
    """

    def _explode() -> object:
        msg = "calibration corpus unreadable"
        raise RuntimeError(msg)

    monkeypatch.setattr(compliance.refusal_mod, "compute_refusal_calibration", _explode)
    values = compliance._signal_values()
    assert "refusal" in values, "a failing probe must stay in the mapping, as a failure"
    assert values["refusal"].measured is False
    assert values["refusal"].cause == "read-failed"
    assert any(v.measured for v in values.values()), "one failure must not take the rest down"


def test_an_unmeasured_control_stays_in_the_table_as_na() -> None:
    """The control must be present, `na`, with a cause — never absent."""
    posture = compliance.compute_compliance(lang="fr")
    by_id = {c.id: c for c in posture.controls}
    assert by_id, "no controls at all — the posture would be vacuously green"
    for control in posture.controls:
        if control.status == "na":
            assert control.unavailable, f"{control.id} is na and does not say why"
            assert control.risk == "unknown", "an unmeasured control is not a low-risk one"


def test_the_global_score_ignores_controls_it_could_not_measure() -> None:
    """An `na` must neither count as 1.0 (a lie) nor as 0.0 (an invented failure)."""
    posture = compliance.compute_compliance(lang="fr")
    scored = [c for c in posture.controls if c.status != "na"]
    expected = round((sum(c.value for c in scored) / len(scored)) * 100) if scored else 0
    assert posture.score == expected


def test_frameworks_count_their_unmeasured_controls() -> None:
    """`n_na` was the literal 0 while controls were quietly disappearing."""
    posture = compliance.compute_compliance(lang="fr")
    per_framework = {f.code: f for f in posture.frameworks}
    for code, framework in per_framework.items():
        na = sum(1 for c in posture.controls if c.framework == code and c.status == "na")
        assert framework.n_na == na


def test_the_audit_chain_answer_comes_from_the_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no ledger reachable, the honest answer is `not verified`, never `verified`."""
    monkeypatch.setattr(
        "tessera.guard.ledger_store.ledger_available",
        lambda *_a, **_k: False,
    )
    facts = compliance._audit_chain_facts()
    assert facts.present is False
    assert facts.verified is False
