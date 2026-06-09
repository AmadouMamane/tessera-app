"""Unit tests for toxicity / harmful-output rate (ADR 0010, #60)."""

from __future__ import annotations

from tessera.observability.toxicity import scan_toxicity


def test_empty() -> None:
    report = scan_toxicity([])
    assert report.n_turns == 0
    assert report.toxicity_rate == 0.0


def test_clean_answers() -> None:
    report = scan_toxicity([("q", "Les frais de tenue de compte sont de 2 euros par mois.")])
    assert report.n_toxic == 0
    assert report.toxicity_rate == 0.0


def test_flags_toxic_term() -> None:
    report = scan_toxicity([("q", "You are an idiot and worthless.")])
    assert report.n_toxic == 1
    assert "idiot" in report.flagged[0].terms
    assert "worthless" in report.flagged[0].terms


def test_multilingual() -> None:
    report = scan_toxicity(
        [
            ("q1", "Tu es un imbécile."),
            ("q2", "Halt die Klappe."),
            ("q3", "Réponse polie et correcte."),
        ]
    )
    assert report.n_toxic == 2
    assert abs(report.toxicity_rate - 2 / 3) < 1e-9


def test_word_boundary_no_false_positive() -> None:
    # "stupidity" should not match the standalone term "stupid".
    report = scan_toxicity([("q", "There is no stupidity in this analysis.")])
    assert report.n_toxic == 0
