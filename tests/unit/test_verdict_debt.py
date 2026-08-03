"""The debt — 44 witnesses in this repo still render a verdict as a bare ``bool`` **annotation**.

`src/tessera/verdict.py` makes it structurally impossible for a *new* witness to publish "ok"
without saying what it looked at. It does nothing at all about the ones already written, and
pretending otherwise would be its own small false green.

So the debt is declared, the way `OWED_COUNT = 17` declared the unbounded ledger reads: **named,
counted, frozen, and only allowed to go down.** An intention is not a plan; a number is.

**READ THE NAME OF THE NUMBER.** It is :data:`OWED_BOOL_VERDICTS`, and it was called
``OWED_VERDICTS`` for exactly one day. That name claimed *the verdicts*; this registry sees **one
syntactic shape of one of them** — an AST walk over `-> bool` annotations in `src/` and `scripts/`.
A witness may just as well publish its verdict as a dict with an ``ok`` key, as the string
``"PASS"``, as ``None``-and-raise, or — and this is the one that matters — **as an exit code**.
*The first incident in this entire story was an exit code*: the empty ``${PIPESTATUS[0]}`` that
manufactured a green. A registry that embodies the doctrine and cannot see the surface the doctrine
was born on is not yet lying, but it is one careless reading away from it: ``OWED_VERDICTS = 44``
invites "44 witnesses left to fix", and the truth is "44 **of one shape**". So the number now says
its shape in its name, and :data:`BLIND_SPOTS` says the rest out loud, in the code, beside it.

That is this repo's own rule, turned on this repo's own instrument: *a witness that cannot see must
report a blind spot — it may never report "ok"* (ADR 0026).

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
:data:`OWED_BOOL_VERDICTS`. The number is meant to be read, and it is meant to be embarrassing.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

_ROOT = Path(__file__).resolve().parents[2]
_SCANNED = (_ROOT / "src" / "tessera", _ROOT / "scripts")

#: **What this registry does not see.** Declared in the code, beside the number, because a
#: number without its scope is read as its scope.
#:
#: The key is the verdict shape this AST scan is blind to. The value names the registry that
#: *does* cover it, or ``None`` — which means **nobody covers it**, and that is stated rather
#: than left for the next reader to discover the way the last four were discovered.
#:
#: A `None` here is not a to-do. It is an honest gap, and the whole difference between this
#: project's guard-rails and the ones that failed is that the gaps are written down.
BLIND_SPOTS: Final[dict[str, str | None]] = {
    # THE ONE THAT MATTERS. Every `make` target, every script, every CI step is an exit-code
    # witness, and the origin instance of ADR 0026 was exactly this: a pipeline's exit code
    # read off the wrong command. Covered — see the module named below.
    "an exit code — `make`, a script, a CI step: the verdict is `$?`": (
        "tests/unit/test_exit_witness_debt.py"
    ),
    # A dict verdict reads as `if result["ok"]:` — a bit again, wearing a key.
    "a dict with an `ok`/`passed` key": None,
    # `\"PASS\"` / `\"FAILED\"` — a bit, spelled. And `if status:` is true for BOTH of them.
    "a string verdict (`PASS` / `FAILED`)": None,
    # Returns `None`, raises on failure. Honest under `set -e`, invisible under `except`.
    "`-> None`, raising on failure": None,
}

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
    # `data`: "was this reading taken over a non-empty sample", a property OF the reading.
    # It feeds the compliance verdict rather than being one — the control's `na` status is
    # what carries the judgement, and it says its cause.
    "src/tessera/observability/compliance.py::SignalReading.measured": "data",
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
    # A route-existence LOOKUP inside the orphan-link probe: it answers "is this path in the
    # app tree", which selects what to report. Nothing passes or fails on it.
    "scripts/audit/scan_ui_invariants.py::known": "filter",
    # Whether any catalogue was read at all. A DATA question about a load result, not a
    # verdict about the localization measurement — the route turns it into `available`.
    "src/tessera/observability/message_catalogues.py::CatalogueLoad.found": "data",
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
    # Same shape, and it arrived the same way: the freeze caught it on the day it was written.
    # `check_advance()` is what publishes the Verdict about the trunk; this only asks a question
    # ABOUT THE GRAPH — is X in Y's history — and it answers `None` when git cannot tell, which is
    # load-bearing: "I have never seen that object" is not "no", and reading one as the other
    # would be a FALSE REFUSAL. It is not the debt, and it does not join the debt: a debt you pay
    # by enrolling in it is not a debt.
    "scripts/main_guard.py::_is_ancestor": "data",
    "src/tessera/agent/capability_schema.py::_matches": "filter",
    "src/tessera/agent/recouvrement.py::_artifact_mentions_schedule": "text",
    "src/tessera/agent/recouvrement.py::_has_contact_rule_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_draft_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_payment_options_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_schedule_intent": "intent",
    "src/tessera/agent/recouvrement.py::_has_summary_intent": "intent",
    # Classifies what the customer ASKED FOR — "does this text request something irreversible" —
    # in the same shape as the three intent predicates above it. It decides nothing that passes
    # or fails: the turn is refused either way, and the escalation that follows is decided by
    # `_blocked_turn`, which reads this the way the others are read. Its reasoning lives in
    # `tests/unit/test_refusal_is_not_a_dead_end.py`, which holds BOTH directions with the
    # catalogue's own prompts — case 55 must escalate, case 06 must not.
    "src/tessera/agent/router.py::requests_irreversible_action": "intent",
    "src/tessera/api/routes/audit.py::_matches_text": "filter",
    "src/tessera/api/routes/audit.py::_within": "filter",
    # Row-level predicate over one timestamp: "is this inside the selected window". It decides
    # nothing about the system — it is the `WHERE` clause the file-backed readers apply in
    # Python because they have no index to push it down to.
    "src/tessera/observability/spine/scope.py::Scope.within": "filter",
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
    # 2026-07-18 (ADR 0034): a property OF a model — does the real price table
    # carry a nonzero tariff for it. Feeds the budget breaker's gate; the gate's
    # own decision is recorded on the span, never reduced to this bit.
    "src/tessera/llm/budget.py::model_is_paid": "data",
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
    # A cache-freshness control decision, not a verdict: it selects whether the leader recomputes
    # the snapshot or only re-stamps it (ADR 0046 amendment). Nothing PASSES — a wrong answer costs
    # only a slightly stale card or a wasted recompute, never a governance or safety outcome.
    "src/tessera/observability/read_snapshot.py::snapshot_needs_recompute": "data",
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

#: How many `-> bool` functions decide whether something PASSES, and say it with one bit.
#: **THIS MAY ONLY GO DOWN.**
#:
#: The name carries the scope on purpose: this is not "the verdicts this repo owes", it is the
#: ones that owe it *in this shape*. See :data:`BLIND_SPOTS` for the shapes it cannot see, and
#: `OWED_EXIT_WITNESSES` (tests/unit/test_exit_witness_debt.py) for the surface the whole
#: doctrine was born on.
OWED_BOOL_VERDICTS = 44


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


class TestTheRegistryDeclaresWhatItCannotSee:
    """The instrument, held to its own rule.

    This registry is itself a witness — it publishes a number about the state of the repo — and
    ADR 0026's corollary applies to it exactly as it applies to everything it scans: *a witness
    that cannot see must report a blind spot; it may never report "ok"*.

    Its blind spot is real and it is not small: it scans a **syntactic proxy** (`-> bool`) for a
    **semantic class** (a witness that publishes a bit). The class it cannot see includes the one
    the whole doctrine was born on — an exit code.
    """

    def test_the_blind_spots_are_declared(self) -> None:
        """The declaration exists, and it names the exit-code surface.

        Mutation: delete the exit-code key from `BLIND_SPOTS`. Red. The number may not be
        published next to a silence about what it does not cover — that silence is precisely how
        `OWED_BOOL_VERDICTS = 44` would come to be read as "44 witnesses left to fix".
        """
        assert BLIND_SPOTS, (
            "BLIND_SPOTS is empty. This registry scans `-> bool` annotations — a syntactic proxy "
            "for a semantic class. It cannot possibly see everything, and a witness that cannot "
            "see must SAY SO (ADR 0026)."
        )

        exit_spots = [spot for spot in BLIND_SPOTS if "exit code" in spot]
        assert exit_spots, (
            "the EXIT-CODE blind spot is no longer declared. It is the one that matters: every "
            "make target, every script and every CI step publishes its verdict as `$?`, and the "
            "very first incident of ADR 0026 was an exit code — the empty `${PIPESTATUS[0]}` "
            "that manufactured a green. Put it back."
        )

    def test_a_declared_cover_must_actually_exist(self) -> None:
        """A blind spot claimed as covered must name a module that IS THERE.

        This is the doctrine applied to the doctrine's own bookkeeping: *a claim is not a fact*.
        `KNOWN_AUTH_GUARDS` certified an anonymous DELETE because membership of a list had been
        asserted by nobody. So a cover named here is opened, not believed.

        Mutation: delete `tests/unit/test_exit_witness_debt.py`. Red — the blind spot goes back to
        being uncovered, and this registry may not go on claiming otherwise.
        """
        missing = {
            spot: cover
            for spot, cover in BLIND_SPOTS.items()
            if cover is not None and not (_ROOT / cover).exists()
        }

        assert not missing, (
            "these blind spots name a registry that covers them, and the registry IS NOT THERE:\n"
            + "\n".join(f"  {spot!r} → {cover}" for spot, cover in sorted(missing.items()))
            + "\nEither the cover was deleted (put it back, or set the value to None and own the "
            "gap honestly), or it was never written."
        )


class TestTheDebtIsANumber:
    """It is 44. It may only go down."""

    def test_the_owed_count_is_the_number_of_verdicts_in_the_registry(self) -> None:
        """The count and the list cannot drift: the count IS the list, counted.

        Mutation: lower `OWED_BOOL_VERDICTS` without converting anything. Red — the number cannot
        be improved by editing the number, which is the only way a frozen count is worth anything.
        """
        owed = sum(1 for kind in _BOOL_FUNCTIONS.values() if kind == "VERDICT")

        assert owed == OWED_BOOL_VERDICTS, (
            f"the debt moved ({owed} vs {OWED_BOOL_VERDICTS}). If you converted a witness to a "
            "Verdict, delete its line and LOWER the number — that is the whole point of it being "
            "a number."
        )

    def test_the_debt_never_grows(self) -> None:
        """A new `-> bool` verdict may not be born. Convert it, or justify it in the registry."""
        assert OWED_BOOL_VERDICTS <= 44, (
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
            "if they were VERDICTs, lower OWED_BOOL_VERDICTS so the debt shrinks ON THE RECORD:\n"
            + "\n".join(f"  {key}" for key in stale)
        )

    def test_every_entry_is_classified(self) -> None:
        """`VERDICT`, or a reason it is not one. An unlabelled entry is a decision not taken."""
        known = {"VERDICT", "config", "data", "text", "filter", "dispatch", "write", "intent"}
        unknown = {key: kind for key, kind in _BOOL_FUNCTIONS.items() if kind not in known}

        assert not unknown, f"unclassified entries: {unknown}"
