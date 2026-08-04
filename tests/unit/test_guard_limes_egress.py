"""ADR 0049 ratchet — a secret never leaves in the agent's answer.

The seam is :func:`tessera.guard.redaction.apply_egress_guard`, run on the RAW
answer (before the regex output guard) at both transports (reporter node + the SSE
route). It adds the one outbound capability Tessera lacked: a secret **block**. PII
stays with the first-party regex guard. These tests pin the thesis:

1. a credential (assembled at runtime — never a literal, ADR 0009) **blocks** the
   whole answer, which is replaced by the localized withheld message;
2. ordinary content, and even PII, **forwards** — this leg does not touch PII;
3. the MUTATION that proves the ratchet bites: unplug limes (its backend always
   forwards) and the same secret **leaves in the clear** — so test 1 genuinely
   depends on limes, not on any refusal being present.

Secrets are assembled from fragments so no credential-shaped literal is committed
to this repository either (the reason limes' own corpus is assembled, ADR 0010).
"""

from __future__ import annotations

import uuid
from typing import cast

from tessera.agent import reporter
from tessera.agent.state import AgentState, new_state
from tessera.guard.decisions import DecisionKind
from tessera.guard.limes_egress_backend import EgressOutcome, check_egress, egress_witness
from tessera.guard.redaction import apply_egress_guard, egress_withheld_notice
from tessera.settings import LanguageCode

_TS = "2026-08-04T00:00:00Z"

# A published test PAN (Luhn-valid) and an assembled synthetic secret. Neither is a
# real datum; the secret is spliced so no `sk_live_…` literal exists in the file.
_TEST_PAN = "4242 4242 4242 4242"
_SECRET = "sk_" + "live_" + "EXAMPLEONLY0000000000000"


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
