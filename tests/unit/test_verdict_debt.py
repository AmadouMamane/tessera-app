"""The debt — 44 witnesses in this repo still render a verdict as a bare ``bool``.

`src/tessera/verdict.py` makes it structurally impossible for a *new* witness to publish "ok"
without saying what it looked at. It does nothing at all about the ones already written, and
pretending otherwise would be its own small false green.

So the debt is declared, the way `OWED_COUNT = 17` declared the unbounded ledger reads: **named,
counted, frozen, and only allowed to go down.** An intention is not a plan; a number is.

**What is mechanical here, and what is a judgement.** The scan is an AST walk over every `-> bool`
(and `-> bool | None`) function in `src/` and `scripts/` — 97 of them — and the registry below must
contain *all* of them. That part is airtight: a new bool-returning function cannot be added without
its author writing down which kind it is, and a function that changes its return type cannot be
left rotting in the registry. It is the same two-sided freeze the ledger ratchet uses, for the same
reason: a set that may only shrink is a ratchet, a set that may grow is a wish.

The **VERDICT / not-a-verdict** line is a judgement, and it is recorded per entry rather than
hidden in a heuristic. A verdict *decides whether something passes*: `releasable`, `can_handoff`,
`verify_waiver_chain`, `_refused`. A predicate merely *describes a value*: `is_empty`,
`occurred_before`, `_luhn_valid`… well — `_luhn_valid` is in the debt, because a checksum that
fails has a reason and the caller throws it away. When a call is genuinely close, it is counted as
a verdict: over-counting costs a migration nobody needed, under-counting hides a hole, and those
are not symmetrical.

**What paying it down looks like.** Not a bulk rewrite — that is an ADR's work, not a night's. It
is: when you next touch one of these, return a `Verdict`, delete its line here, and lower
:data:`OWED_VERDICTS`. The number is meant to be read, and it is meant to be embarrassing.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCANNED = (_ROOT / "src" / "tessera", _ROOT / "scripts")

#: Every `-> bool` function in `src/` and `scripts/`, and what kind of thing it is.
#:
#: ``VERDICT`` — it decides whether something PASSES, and it says so with one bit, throwing away
#: what it looked at. **This is the debt.** It has a number, and the number may only go down.
#:
#: Everything else is a predicate, and a predicate returning `bool` is correct:
#:   ``config``   — reads a flag, an env var, a setting. There is nothing to be evidenced.
#:   ``data``     — a property OF a value, not a judgement ON it (`is_empty`, `occurred_before`).
#:   ``text``     — a text/regex classification feeding a verdict somewhere upstream.
#:   ``filter``   — "does this row match", inside a comprehension.
#:   ``dispatch`` — `supports()`: which implementation handles this, not whether it passed.
#:   ``write``    — did a write land / did a row exist. A fact, not a verdict.
#:   ``intent``   — an NLU intent classifier.
_BOOL_FUNCTIONS: dict[str, str] = {
    # ── integrity & chain verifiers — the strongest witness shape, and the barest bit ──────────
    "src/tessera/corpus/lineage.py::verify_lineage_chain": "VERDICT",
    "src/tessera/observability/eval_waivers.py::verify_waiver_chain": "VERDICT",
    "src/tessera/guard/ledger_checkpoint.py::_anchor_holds": "VERDICT",
    "src/tessera/observability/fleet.py::_integrity_broken": "VERDICT",
    "src/tessera/guard/ledger_store.py::LedgerShadowStatus.ok": "VERDICT",
    "src/tessera/guard/audit.py::chain_persists_for": "VERDICT",
    # ── release & gate verdicts ───────────────────────────────────────────────────────────────
    "src/tessera/observability/eval_gate_view.py::GateCaseStatus.blocking": "VERDICT",
    "src/tessera/observability/eval_gate_view.py::GateCaseStatus.is_critical": "VERDICT",
    "src/tessera/observability/eval_gate_view.py::waiver_active": "VERDICT",
    "src/tessera/observability/eval_tiers.py::TierMap.is_critical": "VERDICT",
    "src/tessera/observability/eval_tiers.py::TierMap.waivable": "VERDICT",
    "src/tessera/observability/eval_tiers.py::is_waivable": "VERDICT",
    "src/tessera/observability/eval_waivers.py::WaiverEvent.targets": "VERDICT",
    "src/tessera/observability/agent_release.py::AgentRelease.verdict_stale": "VERDICT",
    "src/tessera/observability/catalogue_consumers.py::_passing": "VERDICT",
    "scripts/check_contribution.py::_replay_once": "VERDICT",
    "scripts/check_contribution.py::_replay": "VERDICT",
    # ── authz & guard verdicts ────────────────────────────────────────────────────────────────
    "src/tessera/authz.py::auth_satisfies": "VERDICT",
    "src/tessera/agent/registry.py::can_handoff": "VERDICT",
    "src/tessera/api/routes/chat.py::sandbox_overrides_allowed": "VERDICT",
    "src/tessera/api/session.py::verify_resume_token": "VERDICT",
    "src/tessera/memory/governance.py::consent_allows": "VERDICT",
    "src/tessera/agent/recouvrement.py::_surface_allowed": "VERDICT",
    "src/tessera/observability/trajectory.py::_guard_denied": "VERDICT",
    "src/tessera/observability/refusal.py::_refused": "VERDICT",
    # ── content & grounding verdicts ──────────────────────────────────────────────────────────
    "src/tessera/guard/redaction.py::contains_pii": "VERDICT",
    "src/tessera/guard/redaction.py::_luhn_valid": "VERDICT",
    "src/tessera/guard/grounding.py::_quant_supported": "VERDICT",
    "src/tessera/guard/grounding.py::declares_unanswerable": "VERDICT",
    # ── evidence & capability verdicts ────────────────────────────────────────────────────────
    "src/tessera/observability/turn_evidence.py::has_turn_evidence": "VERDICT",
    "src/tessera/observability/business_capabilities.py::LevelResolution.proven": "VERDICT",
    "src/tessera/observability/business_capabilities.py::declares_external_effects": "VERDICT",
    "src/tessera/observability/business_capabilities.py::_prevents_external_effect": "VERDICT",
    "src/tessera/observability/agentspec_projection.py::declares_telemetry": "VERDICT",
    "src/tessera/observability/agentspec_projection.py::is_invocable": "VERDICT",
    "src/tessera/observability/tool_validity.py::_has_arg_failure": "VERDICT",
    # ── availability & health verdicts ────────────────────────────────────────────────────────
    "src/tessera/guard/ledger_store.py::ledger_available": "VERDICT",
    "src/tessera/guard/ledger_store.py::_ledger_reachable": "VERDICT",
    "src/tessera/api/routes/health.py::_llm_reachable": "VERDICT",
    # ── business-rule & policy verdicts ───────────────────────────────────────────────────────
    "src/tessera/agent/recouvrement.py::_within_window": "VERDICT",
    "src/tessera/observability/operator_items.py::OperatorItem.overdue": "VERDICT",
    "src/tessera/observability/spine/registry.py::SignalRegistry.registered": "VERDICT",
    "src/tessera/observability/eval/online.py::should_judge": "VERDICT",
    "src/tessera/settings.py::Settings.rate_limit_required": "VERDICT",
    # ── NOT verdicts. A `bool` is the right answer here. ──────────────────────────────────────
    "scripts/generate_zod.py::_is_typed": "data",
    # `check()` is what publishes a Verdict about this tree; this only asks whether a pid runs,
    # and it already answers `None` when it cannot know — which is the same rule, in miniature.
    "scripts/worktree_owner.py::_process_alive": "data",
    "src/tessera/agent/capability_schema.py::_matches": "filter",
    "src/tessera/agent/recouvrement.py::_artifact_mentions_schedule": "text",
    "src/tessera/agent/recouvrement.py::_has_contact_rule_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_draft_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_payment_options_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_schedule_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_summary_intent": "intent",
    "src/tessera/api/routes/audit.py::_matches_text": "filter",
    "src/tessera/api/routes/audit.py::_within": "filter",
    "src/tessera/api/routes/chat.py::is_test_turn": "data",
    "src/tessera/api/routes/observability/_common.py::_bool_payload": "data",
    "src/tessera/api/settings_store.py::_get_flag": "config",
    "src/tessera/api/settings_store.py::_set_flag": "write",
    "src/tessera/api/settings_store.py::get_synthesis_admin": "config",
    "src/tessera/api/settings_store.py::set_synthesis_admin": "write",
    "src/tessera/authz.py::Actor.is_system": "data",
    "src/tessera/guard/grounding.py::_carries_refusal": "text",
    "src/tessera/guard/grounding.py::_same_name": "text",
    "src/tessera/guard/ledger_store.py::drain_spool": "write",
    "src/tessera/guard/ledger_store.py::dual_write_enabled": "config",
    "src/tessera/guard/redaction.py::RedactedText.changed": "data",
    "src/tessera/guard/redaction.py::_iban_context": "text",
    "src/tessera/memory/persistent.py::delete_memory": "write",
    "src/tessera/memory/persistent.py::update_memory_text": "write",
    "src/tessera/memory/protocol.py::EntityLedger.is_empty": "data",
    "src/tessera/observability/_asof.py::occurred_before": "data",
    "src/tessera/observability/agent_garde_fous.py::_enabled": "config",
    "src/tessera/observability/agent_lifecycle.py::_level_at_least": "data",
    "src/tessera/observability/business_capabilities.py::_governed": "filter",
    "src/tessera/observability/business_capabilities.py::_has_capability_stamped_events": "data",
    "src/tessera/observability/business_events.py::_matches_scope": "filter",
    "src/tessera/observability/business_events.py::is_synthetic_turn": "data",
    "src/tessera/observability/business_scoring.py::BusinessScorer.supports": "dispatch",
    "src/tessera/observability/citation_resolver.py::_matches": "filter",
    "src/tessera/observability/clickhouse_business_events.py::_enabled": "config",
    "src/tessera/observability/clickhouse_scores.py::_enabled": "config",
    "src/tessera/observability/connectors.py::_on_prem": "config",
    "src/tessera/observability/eval/failed_runs.py::_is_full": "data",
    "src/tessera/observability/langfuse_scores.py::_enabled": "config",
    "src/tessera/observability/reliability.py::_in_window": "data",
    "src/tessera/observability/spine/adapters/__init__.py::_has_fact_overrides": "config",
    "src/tessera/observability/spine/adapters/langfuse.py::_matches_agent": "filter",
    "src/tessera/observability/spine/capabilities.py::SignalCapability.org_wide": "data",
    "src/tessera/observability/spine/registry.py::SignalSpec.synthetic": "data",
    "src/tessera/observability/tail_sampling.py::_keep_head": "data",
    "src/tessera/observability/turn_evidence.py::turn_evidence_enabled": "config",
    "src/tessera/recouvrement/scoring.py::RecouvrementBusinessScorer.supports": "dispatch",
    "src/tessera/recouvrement/scoring.py::_is_recouvrement": "filter",
    "src/tessera/settings.py::Settings.hsts_enabled": "config",
    "src/tessera/settings.py::Settings.is_on_prem": "config",
    "src/tessera/settings.py::Settings.is_production": "config",
}

#: How many of them decide whether something PASSES, and say it with one bit.
#: **THIS MAY ONLY GO DOWN.**
OWED_VERDICTS = 44


def _returns_bool(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Does this function's ANNOTATION promise a bool? Read from the AST, never from the name.

    `has_turn_evidence` and `is_empty` are indistinguishable by name, and a ratchet that guessed
    from names would be doing the very thing this whole lot is about.
    """
    returns = node.returns
    if returns is None:
        return False
    if isinstance(returns, ast.Name) and returns.id == "bool":
        return True
    if isinstance(returns, ast.BinOp) and isinstance(returns.op, ast.BitOr):  # `bool | None`
        sides = {
            side.id if isinstance(side, ast.Name) else None
            for side in (returns.left, returns.right)
        }
        return "bool" in sides
    if isinstance(returns, ast.Constant) and isinstance(returns.value, str):  # "bool"
        return returns.value.replace(" ", "") in {"bool", "bool|None"}
    return False


def _bool_functions() -> dict[str, int]:
    """Every `-> bool` function in the scanned trees, mapped to its line. Qualified by class."""
    found: dict[str, int] = {}
    for root in _SCANNED:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            stack: list[tuple[ast.AST, str]] = [(tree, "")]
            while stack:
                node, prefix = stack.pop()
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.ClassDef):
                        stack.append((child, f"{prefix}{child.name}."))
                    elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                        if _returns_bool(child):
                            key = f"{path.relative_to(_ROOT)}::{prefix}{child.name}"
                            found[key] = child.lineno
                        stack.append((child, prefix))
    return found


class TestTheDebtIsANumber:
    """It is 44. It may only go down."""

    def test_the_owed_count_is_the_number_of_verdicts_in_the_registry(self) -> None:
        """The count and the list cannot drift: the count IS the list, counted.

        Mutation: lower `OWED_VERDICTS` to 44 without converting anything. Red — the number cannot
        be improved by editing the number, which is the only way a frozen count is worth anything.
        """
        owed = sum(1 for kind in _BOOL_FUNCTIONS.values() if kind == "VERDICT")

        assert owed == OWED_VERDICTS, (
            f"the debt moved ({owed} vs {OWED_VERDICTS}). If you converted a witness to a Verdict, "
            "delete its line and LOWER the number — that is the whole point of it being a number."
        )

    def test_the_debt_never_grows(self) -> None:
        """A new `-> bool` verdict may not be born. Convert it, or justify it in the registry."""
        assert OWED_VERDICTS <= 44, (
            "the debt went UP. A new witness was written that publishes a pass/fail as one bit, "
            "throwing away what it looked at. Return a Verdict instead (src/tessera/verdict.py)."
        )


class TestTheFreeze:
    """The registry may shrink. It may not grow. That is what makes it a ratchet and not a list."""

    def test_no_bool_function_escapes_the_registry(self) -> None:
        """**The teeth.** Every `-> bool` in src/ and scripts/ must be classified, here, by hand.

        Without this, the debt count is a decoration: a new bool-returning verdict would simply not
        be in the frozen dict, the count would still read 45, and the ratchet would be green over a
        hole — the exact failure mode of every incident in ADR 0026.

        Mutation: add `def _is_fine() -> bool` anywhere in src/. Red, naming the file and the line.
        """
        found = _bool_functions()
        unregistered = {key: line for key, line in found.items() if key not in _BOOL_FUNCTIONS}

        assert not unregistered, (
            "these functions return a bare `bool` and are not in the registry. Say which kind they "
            "are — and if one of them decides whether something PASSES, it owes a Verdict:\n"
            + "\n".join(f"  {key}  (line {line})" for key, line in sorted(unregistered.items()))
        )

    def test_no_stale_entry_survives_in_the_registry(self) -> None:
        """A converted witness must be DELETED from the registry, so the debt actually shrinks.

        Otherwise the count stays at 45 while the code improves underneath it — a debt that is paid
        and still reported as owed is a number nobody trusts, and an untrusted number is not a
        ratchet.
        """
        found = _bool_functions()
        stale = sorted(key for key in _BOOL_FUNCTIONS if key not in found)

        assert not stale, (
            "these are in the registry but no longer return a bool — excellent. Delete them, and "
            "if they were VERDICTs, lower OWED_VERDICTS so the debt shrinks ON THE RECORD:\n"
            + "\n".join(f"  {key}" for key in stale)
        )

    def test_every_entry_is_classified(self) -> None:
        """`VERDICT`, or a reason it is not one. An unlabelled entry is a decision not taken."""
        known = {"VERDICT", "config", "data", "text", "filter", "dispatch", "write", "intent"}
        unknown = {key: kind for key, kind in _BOOL_FUNCTIONS.items() if kind not in known}

        assert not unknown, f"unclassified entries: {unknown}"
