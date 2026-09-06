"""Bless, verify and restore the demo's operational state — « l'état d'or » (ADR 0058).

The demo's login gate is theatrical by design (ADR 0009): visitors hold operator accounts
and their governed acts mutate real state. This tool lets the deployment return that state
to a blessed reference without rewriting history:

* the STATE PARTITION below declares, file by file, what is operational state (returned to
  gold) and what is history, money, infrastructure or subject data (never touched). A file
  the partition does not name is REFUSED, never guessed — a stranger is refused loudly, not
  absorbed silently (ADR 0026).
* ``snapshot`` blesses the current operational state as gold (files + recorded absences);
* ``reset`` restores gold and appends the act — actor, declared reason (ADR 0024), gold
  digest, verdict — to its own append-only journal (``demo_resets.jsonl``). The audit
  journal and every other history file are untouched: a reset that rewrote them would
  manufacture a past.
* ``verify`` recomputes the operational digest and compares it to gold. The verdict comes
  from re-reading the state directory, never from the intention.

Exit codes: 0 ok · 1 refused / drift · 2 cannot say. ``make`` flattens any failing recipe
to 2 (measured in ``tests/unit/test_make_flattens_exit_codes.py``; ADR 0051) — call this
script directly when the verdict must be a number.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

#: Operational state a demo visitor can mutate through the cockpit or the collections
#: console. These files — and only these — return to gold on reset. An absence in gold is
#: restored as an absence (the file is removed).
OPERATIONAL_STATE: frozenset[str] = frozenset(
    {
        "agent_config.json",
        "agent_prompt_overlay.json",
        "automation_approvals.json",
        "automation_rules.json",
        "client_space.json",
        "console_feedback.json",
        "curation_decisions.json",
        "etat_a_date_snapshots.json",
        "evidence_packs.json",
        "garde_fous_state.json",
        "incidents.json",
        "knowledge_state.json",
        "operator_items_state.json",
        "recouvrement_cases.json",
    }
)

#: History, measurements, money, infrastructure and derived caches. A reset never touches
#: them: journals stay append-only (``*_transitions.jsonl`` is the history twin of
#: ``operator_items_state.json`` — the design separates state from history, this partition
#: keeps that separation), spend survives (``budget.json``), infra liveness keeps its
#: memory, and this tool's own journal is history like any other.
PRESERVED: frozenset[str] = frozenset(
    {
        "agent_config_history.json",
        "alerts_journal.jsonl",
        "alerts_state.json",
        "audit_spool.jsonl",
        "audit_spool.lock",
        "automation_runs.json",
        "budget.json",
        "budget.lock",
        "bundles.jsonl",
        "component_phases.json",
        "demo_resets.jsonl",
        "eval_waivers.jsonl",
        "ingestion_lineage.jsonl",
        "knowledge_citations.json",
        "operator_items_transitions.jsonl",
        "probe_runs.json",
        "probe_scheduler.json",
        "read_snapshot.json",
        "replay_runs.json",
        "scores.jsonl",
    }
)

RESET_JOURNAL = "demo_resets.jsonl"
_RESET_ACTOR = "demo-gold-reset"  # a declared machine actor, never a default naming a person


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan(state_dir: Path) -> tuple[dict[str, str | None], list[str]]:
    """Read the operational state and spot strangers.

    Returns:
        The operational manifest (name -> sha256, or ``None`` for an absence) and the
        sorted list of top-level regular files the partition does not classify.
    """
    manifest: dict[str, str | None] = {}
    for name in sorted(OPERATIONAL_STATE):
        target = state_dir / name
        manifest[name] = _sha256_file(target) if target.is_file() else None
    strangers = sorted(
        entry.name
        for entry in state_dir.iterdir()
        if entry.is_file() and entry.name not in OPERATIONAL_STATE | PRESERVED
    )
    return manifest, strangers


def _digest(manifest: dict[str, str | None]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _append_journal(state_dir: Path, *, reason: str, gold_digest: str, verdict: str) -> None:
    entry = {
        "at": datetime.now(UTC).isoformat(),
        "actor": _RESET_ACTOR,
        "reason": reason,
        "gold_digest": gold_digest,
        "verdict": verdict,
    }
    with (state_dir / RESET_JOURNAL).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _refuse_strangers(strangers: list[str]) -> bool:
    if strangers:
        print(
            "[demo-gold] REFUSED — the state directory holds files the partition does not "
            f"classify: {', '.join(strangers)}. Classify each one in scripts/demo_gold.py "
            "(operational state or preserved history) before any blessing or reset."
        )
        return True
    return False


def cmd_snapshot(state_dir: Path, gold_dir: Path) -> int:
    """Bless the current operational state as gold."""
    if not state_dir.is_dir():
        print(f"[demo-gold] CANNOT SAY — state directory {state_dir} does not exist.")
        return 2
    manifest, strangers = _scan(state_dir)
    if _refuse_strangers(strangers):
        return 1
    files_dir = gold_dir / "files"
    if gold_dir.exists():
        shutil.rmtree(gold_dir)
    files_dir.mkdir(parents=True)
    for name, digest in manifest.items():
        if digest is not None:
            shutil.copy2(state_dir / name, files_dir / name)
    blessed_digest = _digest(manifest)
    gold: dict[str, object] = {
        "blessed_at": datetime.now(UTC).isoformat(),
        "digest": blessed_digest,
        "files": manifest,
    }
    (gold_dir / "manifest.json").write_text(json.dumps(gold, indent=2, sort_keys=True) + "\n")
    print(
        f"[demo-gold] BLESSED — {sum(1 for d in manifest.values() if d)} file(s), "
        f"{sum(1 for d in manifest.values() if d is None)} recorded absence(s), "
        f"digest {blessed_digest[:12]}…"
    )
    return 0


def _load_gold(gold_dir: Path) -> dict[str, object] | None:
    manifest_path = gold_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    loaded: dict[str, object] = json.loads(manifest_path.read_text())
    return loaded


def cmd_verify(state_dir: Path, gold_dir: Path) -> int:
    """Compare the live operational state to gold. Read-only.

    A drift verdict taken while the agent is running can be a torn read — re-run with the
    agent stopped before acting on it.
    """
    gold = _load_gold(gold_dir)
    if gold is None:
        print(f"[demo-gold] CANNOT SAY — no gold blessed at {gold_dir} (run snapshot first).")
        return 2
    if not state_dir.is_dir():
        print(f"[demo-gold] CANNOT SAY — state directory {state_dir} does not exist.")
        return 2
    manifest, strangers = _scan(state_dir)
    live = _digest(manifest)
    expected = str(gold["digest"])
    if live == expected and not strangers:
        print(f"[demo-gold] MATCH — operational state equals gold ({live[:12]}…).")
        return 0
    gold_files_raw = gold["files"]
    gold_files: dict[str, str | None] = (
        {str(k): (str(v) if v is not None else None) for k, v in gold_files_raw.items()}
        if isinstance(gold_files_raw, dict)
        else {}
    )
    drifted = sorted(name for name, digest in manifest.items() if gold_files.get(name) != digest)
    print(
        f"[demo-gold] DRIFT — live {live[:12]}… vs gold {expected[:12]}…; "
        f"drifted: {', '.join(drifted) or '(none)'}"
        + (f"; strangers: {', '.join(strangers)}" if strangers else "")
    )
    return 1


def cmd_reset(state_dir: Path, gold_dir: Path, reason: str) -> int:
    """Restore gold, journal the act, and verify by re-reading the result."""
    gold = _load_gold(gold_dir)
    if gold is None:
        print(f"[demo-gold] CANNOT SAY — no gold blessed at {gold_dir}; nothing to restore.")
        return 2
    if not state_dir.is_dir():
        print(f"[demo-gold] CANNOT SAY — state directory {state_dir} does not exist.")
        return 2
    expected = str(gold["digest"])
    _, strangers = _scan(state_dir)
    if _refuse_strangers(strangers):
        _append_journal(state_dir, reason=reason, gold_digest=expected, verdict="refused-stranger")
        return 1
    gold_files_raw = gold["files"]
    if not isinstance(gold_files_raw, dict):
        print("[demo-gold] CANNOT SAY — gold manifest is malformed (files is not a map).")
        return 2
    for name in sorted(OPERATIONAL_STATE):
        digest = gold_files_raw.get(name)
        target = state_dir / name
        if digest is None:
            target.unlink(missing_ok=True)
        else:
            shutil.copy2(gold_dir / "files" / name, target)
    manifest, _ = _scan(state_dir)
    live = _digest(manifest)
    verdict = "match" if live == expected else "refused-mismatch"
    _append_journal(state_dir, reason=reason, gold_digest=expected, verdict=verdict)
    if verdict == "match":
        print(f"[demo-gold] MATCH — state restored to gold ({live[:12]}…); act journaled.")
        return 0
    print(
        f"[demo-gold] REFUSED — restored state reads {live[:12]}… but gold is {expected[:12]}…; "
        "the act is journaled with its failure."
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the exit code instead of raising ``SystemExit``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "verify", "reset"))
    parser.add_argument("--state-dir", type=Path, default=Path(".agent-state/local"))
    parser.add_argument("--gold-dir", type=Path, default=Path(".agent-state/gold"))
    parser.add_argument("--reason", default=None, help="required for reset (ADR 0024)")
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        return cmd_snapshot(args.state_dir, args.gold_dir)
    if args.command == "verify":
        return cmd_verify(args.state_dir, args.gold_dir)
    if not args.reason:
        parser.error("reset requires --reason: a governed act declares why (ADR 0024)")
    return cmd_reset(args.state_dir, args.gold_dir, str(args.reason))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
