"""Ratchet — an outbound guard leg is wired on BOTH transports, or it guards nobody.

Three times now, the same shape. A guard leg lands with one call site — the REPORTER node — and
``/chat`` interrupts before REPORTER ever runs, so the leg is live on the canary/eval path and
absent on the customer path. Nothing fails; the eval catalogue even goes green, because the
catalogue runs through REPORTER.

* **grounding** — the P0: the node never ran in production.
* **secrets-egress** (ADR 0049) — fixed by adding the ``chat.py`` Phase 2 transport, and the ADR
  wrote the rule down: *deux transports*.
* **prompt-egress** — landed 2026-08-05 with `reporter.run` only. Found 2026-08-06.

Writing the rule in an ADR did not stop the third instance, so it is a test now. Every guard
function whose job is to withhold or rewrite an outbound answer must be reachable from both
``tessera/agent/reporter.py`` and ``tessera/api/routes/chat.py``.

The detector is checked before it is trusted: "no findings" and "the pattern stopped matching"
are otherwise the same sentence, and this file's whole value is in what it refuses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).resolve().parents[2]
_REPORTER: Final = _ROOT / "src" / "tessera" / "agent" / "reporter.py"
_CHAT: Final = _ROOT / "src" / "tessera" / "api" / "routes" / "chat.py"
_REDACTION: Final = _ROOT / "src" / "tessera" / "guard" / "redaction.py"

#: The outbound legs. Each withholds or rewrites the answer on its way to a customer, so each
#: owes both transports. Asserted with ``==`` below, so adding a leg means editing this file.
OUTBOUND_GUARDS: Final[frozenset[str]] = frozenset(
    {
        "apply_egress_guard",  # secrets (ADR 0049) — limes secrets-egress
        "apply_prompt_egress",  # the agent's own instructions (§10.6)
        "apply_output_guard",  # PII redaction + masking notice
        "apply_pii_egress_recall",  # PII the regex leg missed (ADR 0049 §Amendment 1)
    }
)


def _defined_in_redaction() -> set[str]:
    """The outbound guard functions the redaction module actually defines."""
    source = _REDACTION.read_text(encoding="utf-8")
    return {name for name in OUTBOUND_GUARDS if f"def {name}(" in source}


def _called_in(path: Path) -> set[str]:
    """Which outbound guards this transport calls (its own definitions excluded)."""
    source = path.read_text(encoding="utf-8")
    return {
        name for name in OUTBOUND_GUARDS if f"{name}(" in source and f"def {name}(" not in source
    }


# ── the detector, before it is trusted ───────────────────────────────────────────────────────


def test_every_named_guard_actually_exists() -> None:
    """A ratchet listing a function that has been renamed polices nothing at all."""
    missing = OUTBOUND_GUARDS - _defined_in_redaction()
    assert missing == set(), f"these are not defined in redaction.py any more: {sorted(missing)}"


def test_the_call_detector_sees_the_transports() -> None:
    """Anti-vacuity: if either read returns nothing, every assertion below passes over a hole."""
    assert _called_in(_REPORTER), "found no guard call in reporter.py — the reader is broken"
    assert _called_in(_CHAT), "found no guard call in chat.py — the reader is broken"


# ── the ratchet ──────────────────────────────────────────────────────────────────────────────


def test_every_outbound_guard_is_reachable_from_the_customer_transport() -> None:
    """`/chat` is the path a customer's answer actually takes.

    A leg present only in REPORTER is a leg that runs for the canary and the eval catalogue and
    never for a customer — green everywhere, guarding nobody.
    """
    absent = OUTBOUND_GUARDS - _called_in(_CHAT)
    assert absent == set(), (
        f"these outbound guards are never reached from chat.py: {sorted(absent)}. "
        "REPORTER does not run in production — /chat interrupts before it — so a leg wired only "
        "there protects the eval catalogue and no customer. Wire it in chat.py Phase 2, beside "
        "apply_egress_guard."
    )


def test_every_outbound_guard_is_reachable_from_the_reporter_transport() -> None:
    """And the other half: the canary and the eval catalogue run through REPORTER.

    A leg missing here would make the catalogue unable to observe the very leak it measures.
    """
    absent = OUTBOUND_GUARDS - _called_in(_REPORTER)
    assert absent == set(), (
        f"these outbound guards are never reached from reporter.py: {sorted(absent)}. "
        "The canary and the eval catalogue run through REPORTER, so a leg missing here cannot "
        "be measured by the harness that exists to measure it."
    )


def test_the_guard_list_is_frozen() -> None:
    """Asserted with ``==`` so a new outbound leg cannot be added without facing this rule."""
    assert (
        frozenset(
            {
                "apply_egress_guard",
                "apply_prompt_egress",
                "apply_output_guard",
                "apply_pii_egress_recall",
            }
        )
        == OUTBOUND_GUARDS
    )
