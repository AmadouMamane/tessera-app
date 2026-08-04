"""ADR 0049 ratchet — a secret never leaves, and PII the regex missed is recalled.

Two seams in :mod:`tessera.guard.redaction`, run at both transports (reporter node +
the SSE route):

* :func:`apply_egress_guard`, on the RAW answer (before the regex output guard) — the
  one outbound capability Tessera lacked: a secret **block**;
* :func:`apply_pii_egress_recall`, on the already-masked answer (after the regex
  guard, ADR 0049 §Amendment 1) — a second, checksum-gated pass that **masks PII the
  regex left behind** (a Corsica NIR, a PAN/IBAN grouping the regex pattern misses)
  without re-firing on the regex's own masks.

These tests pin the thesis for both:

1. a credential (assembled at runtime — never a literal, ADR 0009) **blocks** the
   whole answer, which is replaced by the localized withheld message; a NIR the regex
   missed is **redacted** to ``[REDACTED:pii]``, the answer standing;
2. ordinary content forwards; the secret leg does not touch PII, and the recall leg
   does not re-fire on an already-masked PAN/IBAN/e-mail/phone;
3. the MUTATION that proves each ratchet bites: unplug limes (its backend always
   forwards) and the secret **leaves in the clear** / the NIR **stays unmasked** — so
   the seams genuinely depend on limes, not on any refusal being present.

Secrets are assembled from fragments so no credential-shaped literal is committed to
this repository either (the reason limes' own corpus is assembled, ADR 0010). The NIR
is a synthetic vector (recomputed control key, fictional identity — limes corpus
``nir_04_corsica``); PII vectors, like the test PAN, are literals here.
"""

from __future__ import annotations

import uuid
from typing import cast

from tessera.agent import reporter
from tessera.agent.state import AgentState, new_state
from tessera.guard.decisions import DecisionKind
from tessera.guard.limes_egress_backend import (
    EgressOutcome,
    PiiEgressOutcome,
    check_egress,
    check_pii_egress,
    egress_witness,
    pii_egress_witness,
)
from tessera.guard.redaction import (
    apply_egress_guard,
    apply_output_guard,
    apply_pii_egress_recall,
    egress_withheld_notice,
)
from tessera.settings import LanguageCode

_TS = "2026-08-04T00:00:00Z"

# A published test PAN (Luhn-valid) and an assembled synthetic secret. Neither is a
# real datum; the secret is spliced so no `sk_live_…` literal exists in the file.
_TEST_PAN = "4242 4242 4242 4242"
_SECRET = "sk_" + "live_" + "EXAMPLEONLY0000000000000"
# A synthetic Corsica NIR (control key recomputed valid, identity fictional). Its
# `2A` department code breaks the regex guard's digit-only shapes, so the regex leaves
# it clear and the recall pass is what catches it. Its 15 digits fail Luhn, so it can
# never read as a card number and muddy the assertion.
_CORSICA_NIR = "1 75 12 2A 123 456 53"


class TestBackend:
    """check_egress maps limes' secret-egress disposition, fail-closed."""

    def test_clean_text_forwards(self) -> None:
        out = check_egress("Your balance is 1234,56 EUR.", observed_at=_TS)
        assert not out.blocked and out.rule == "egress.limes.allow"

    def test_pii_forwards_this_leg_does_not_touch_it(self) -> None:
        # PII is the first-party regex guard's job, not this one — it must not block.
        out = check_egress(f"Your card {_TEST_PAN} was charged.", observed_at=_TS)
        assert not out.blocked

    def test_a_secret_blocks(self) -> None:
        out = check_egress(f"Config uses {_SECRET} now.", observed_at=_TS)
        assert out.blocked and out.rule == "egress.limes.secret.block"

    def test_witness_names_the_detector(self) -> None:
        assert egress_witness() == ("secrets-egress", "0.1.0")


class TestSeam:
    """apply_egress_guard composes the backend with the decision/audit machinery."""

    def test_block_withholds_the_answer_and_records_a_deny(self) -> None:
        text, record = apply_egress_guard(f"The deploy key is {_SECRET}.", language=LanguageCode.EN)
        assert text == egress_withheld_notice(LanguageCode.EN)
        assert record is not None and record.decision == DecisionKind.DENY.value

    def test_clean_text_passes_through_with_no_decision(self) -> None:
        text, record = apply_egress_guard("Your balance is fine.", language=LanguageCode.EN)
        assert text == "Your balance is fine." and record is None

    def test_pii_passes_through_untouched_here(self) -> None:
        raw = f"Your card {_TEST_PAN} was charged."
        text, record = apply_egress_guard(raw, language=LanguageCode.EN)
        assert text == raw and record is None

    def test_the_sandbox_pii_override_skips_the_whole_pass(self) -> None:
        # Disabled → the credential is NOT blocked (the console playground probes raw).
        text, record = apply_egress_guard(f"key {_SECRET}", language=LanguageCode.EN, disabled=True)
        assert text == f"key {_SECRET}" and record is None


class TestMutationRatchetBites:
    """Unplug limes → the secret leaves in the clear. A ratchet never seen red is none."""

    def test_unplugging_limes_lets_the_secret_leave(self, monkeypatch) -> None:
        def _always_forward(text: str, **_: object) -> EgressOutcome:
            return EgressOutcome(
                blocked=False,
                rule="egress.limes.allow",
                rationale="MUTATION: limes unplugged",
                policy_hash="mutation",
            )

        monkeypatch.setattr("tessera.guard.limes_egress_backend.check_egress", _always_forward)
        text, record = apply_egress_guard(f"The deploy key is {_SECRET}.", language=LanguageCode.EN)
        assert _SECRET in text, (
            "MUTATION: with limes unplugged the secret must leave in the clear — "
            "if it is still withheld, the seam does not depend on limes"
        )
        assert record is None


class TestReporterIntegration:
    """The seam runs end-to-end in the reporter node (the non-SSE / eval transport)."""

    async def test_run_withholds_a_secret_carried_in_the_draft(self) -> None:
        # The draft path (no retrieval docs) renders the draft verbatim, so a
        # credential a tool result carried into it reaches the output guard. It must
        # be withheld, not shown — end to end, through the real reporter node.
        state = new_state(
            conversation_id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            user_input="show me the deploy key",
            language=LanguageCode.EN,
            language_confidence=1.0,
        )
        state["draft_response"] = f"The deploy key is {_SECRET}."
        update = await reporter.run(cast(AgentState, state))
        final = str(update["final_response"])
        assert _SECRET not in final
        assert final == egress_withheld_notice(LanguageCode.EN)


class TestPiiRecallBackend:
    """check_pii_egress maps limes' pii-egress recall disposition."""

    def test_clean_text_forwards(self) -> None:
        out = check_pii_egress("Your balance is fine.", observed_at=_TS)
        assert out.action == "forward" and not out.redacted
        assert out.content == "Your balance is fine."

    def test_a_nir_the_regex_misses_is_redacted(self) -> None:
        out = check_pii_egress(f"Assuré {_CORSICA_NIR} au dossier.", observed_at=_TS)
        assert out.redacted and out.action == "redact"
        assert out.content is not None and _CORSICA_NIR not in out.content
        assert "[REDACTED:pii]" in out.content
        assert out.redactions == ("pii=[REDACTED:pii]",)

    def test_it_does_not_refire_on_the_regex_own_masks(self) -> None:
        # The recall runs on text the regex already masked; those forms must forward,
        # or the PCI last-four display and the harness cases (02/45) would be lost.
        for masked in (
            "Your card XXXX XXXX XXXX 6467 was charged.",
            "Account FRXX XXXX 0123 is active.",
            "Reach me at XXXX@XXXX please.",
            "Call XXXX 78 tomorrow.",
        ):
            out = check_pii_egress(masked, observed_at=_TS)
            assert out.action == "forward", f"recall re-fired on the regex mask {masked!r}"

    def test_witness_names_the_detector(self) -> None:
        assert pii_egress_witness() == ("pii-egress", "0.1.0")


class TestPiiRecallSeam:
    """apply_pii_egress_recall composes the backend with the decision/audit machinery."""

    def test_it_masks_a_nir_the_regex_missed_end_to_end(self) -> None:
        # Precondition: the first-party regex leaves the Corsica NIR clear (2A breaks
        # its digit-only shapes). The recall, run on that output, is what masks it.
        raw = f"Assuré {_CORSICA_NIR} (Corse-du-Sud)."
        regex_masked, _ = apply_output_guard(raw, language=LanguageCode.FR)
        assert _CORSICA_NIR in regex_masked, "precondition: the regex must miss this NIR"
        text, record = apply_pii_egress_recall(regex_masked, language=LanguageCode.FR)
        assert _CORSICA_NIR not in text and "[REDACTED:pii]" in text
        assert record is not None and record.decision == DecisionKind.TRANSFORM.value

    def test_clean_text_passes_through_with_no_decision(self) -> None:
        text, record = apply_pii_egress_recall("Your balance is fine.", language=LanguageCode.EN)
        assert text == "Your balance is fine." and record is None

    def test_an_already_masked_pan_is_untouched(self) -> None:
        masked = "Your card XXXX XXXX XXXX 6467 was charged."
        text, record = apply_pii_egress_recall(masked, language=LanguageCode.EN)
        assert text == masked and record is None

    def test_the_sandbox_pii_override_skips_the_whole_pass(self) -> None:
        raw = f"Assuré {_CORSICA_NIR} au dossier."
        text, record = apply_pii_egress_recall(raw, language=LanguageCode.FR, disabled=True)
        assert text == raw and record is None


class TestPiiRecallMutationRatchetBites:
    """Unplug limes → the NIR the regex missed stays clear. A ratchet never seen red is none."""

    def test_unplugging_limes_lets_the_missed_nir_leave(self, monkeypatch) -> None:
        def _always_forward(text: str, **_: object) -> PiiEgressOutcome:
            return PiiEgressOutcome(
                action="forward",
                content=text,
                redactions=(),
                rule="egress.limes.pii.allow",
                rationale="MUTATION: limes unplugged",
                policy_hash="mutation",
            )

        monkeypatch.setattr("tessera.guard.limes_egress_backend.check_pii_egress", _always_forward)
        raw = f"Assuré {_CORSICA_NIR} (Corse-du-Sud)."
        regex_masked, _ = apply_output_guard(raw, language=LanguageCode.FR)
        text, record = apply_pii_egress_recall(regex_masked, language=LanguageCode.FR)
        assert _CORSICA_NIR in text, (
            "MUTATION: with limes unplugged the NIR the regex missed must stay clear — "
            "if it is still masked, the seam does not depend on limes"
        )
        assert record is None


class TestPiiRecallReporterIntegration:
    """The recall runs end-to-end in the reporter node (the non-SSE / eval transport)."""

    async def test_run_masks_a_nir_the_regex_missed_in_the_draft(self) -> None:
        # The draft path (no retrieval docs) renders the draft verbatim, so a NIR a
        # tool result carried into it reaches the output guard, survives the regex
        # (2A), and must be masked by the recall — end to end, through the real node.
        state = new_state(
            conversation_id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            user_input="rappelle mon numéro de sécurité sociale",
            language=LanguageCode.FR,
            language_confidence=1.0,
        )
        state["draft_response"] = f"Votre NIR est {_CORSICA_NIR} (Corse-du-Sud)."
        update = await reporter.run(cast(AgentState, state))
        final = str(update["final_response"])
        assert _CORSICA_NIR not in final
        assert "[REDACTED:pii]" in final
