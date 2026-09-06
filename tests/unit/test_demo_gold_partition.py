"""The gold partition is total and disjoint, and the reset honours it (ADR 0058).

The partition lives in ``scripts/demo_gold.py``. These tests pin the three properties the
ADR promises: a state file the code names must be classified (a new store cannot ship
unclassified), the two classes never overlap, and the reset restores operational state
byte-for-byte while never touching history — refusing strangers instead of guessing.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("demo_gold", _REPO / "scripts" / "demo_gold.py")
assert _SPEC is not None and _SPEC.loader is not None
demo_gold = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(demo_gold)

_STATE_LITERAL = re.compile(r'audit_file\.parent / "([^"]+)"')


def test_the_partition_is_disjoint() -> None:
    overlap = demo_gold.OPERATIONAL_STATE & demo_gold.PRESERVED
    assert overlap == frozenset(), f"classified twice: {sorted(overlap)}"


def test_every_state_file_the_code_names_is_classified() -> None:
    """A new store literal in src/ must be classified before it can ship.

    This is the ratchet of ADR 0058 §1: the runtime refusal catches strangers on disk,
    this catches them at development time, in the code that will create them.
    """
    named: set[str] = set()
    for path in (_REPO / "src" / "tessera").rglob("*.py"):
        named.update(_STATE_LITERAL.findall(path.read_text(encoding="utf-8")))
    unclassified = named - demo_gold.OPERATIONAL_STATE - demo_gold.PRESERVED
    assert unclassified == set(), (
        f"state files named in code but absent from the partition: {sorted(unclassified)} — "
        "classify each in scripts/demo_gold.py (operational state or preserved history)."
    )


def _seed(state_dir: Path) -> None:
    state_dir.mkdir(parents=True)
    (state_dir / "garde_fous_state.json").write_bytes(b'{"rules": "gold"}')
    (state_dir / "audit_spool.jsonl").write_bytes(b'{"act": 1}\n')


def test_snapshot_reset_roundtrip_restores_state_and_never_touches_history(
    tmp_path: Path,
) -> None:
    state, gold = tmp_path / "state", tmp_path / "gold"
    _seed(state)
    assert demo_gold.main(["snapshot", "--state-dir", str(state), "--gold-dir", str(gold)]) == 0

    # The vandal: mutates a rule store, creates a store absent from gold, and — like any
    # visitor — adds a line of history to the audit spool.
    (state / "garde_fous_state.json").write_bytes(b'{"rules": "vandal"}')
    (state / "incidents.json").write_bytes(b'{"spam": true}')
    with (state / "audit_spool.jsonl").open("ab") as handle:
        handle.write(b'{"act": 2}\n')

    rc = demo_gold.main(
        ["reset", "--state-dir", str(state), "--gold-dir", str(gold), "--reason", "test vandal"]
    )
    assert rc == 0
    assert (state / "garde_fous_state.json").read_bytes() == b'{"rules": "gold"}'
    assert not (state / "incidents.json").exists(), "an absence in gold is restored as absence"
    assert (
        (state / "audit_spool.jsonl").read_bytes() == b'{"act": 1}\n{"act": 2}\n'
    ), "history is never touched — the visitor's act survives the reset"
    journal = (state / "demo_resets.jsonl").read_text().splitlines()
    assert len(journal) == 1
    entry = json.loads(journal[0])
    assert entry["verdict"] == "match"
    assert entry["reason"] == "test vandal"
    assert entry["actor"] == "demo-gold-reset"
    assert demo_gold.main(["verify", "--state-dir", str(state), "--gold-dir", str(gold)]) == 0


def test_a_stranger_file_is_refused_and_nothing_is_changed(tmp_path: Path) -> None:
    state, gold = tmp_path / "state", tmp_path / "gold"
    _seed(state)
    assert demo_gold.main(["snapshot", "--state-dir", str(state), "--gold-dir", str(gold)]) == 0
    (state / "garde_fous_state.json").write_bytes(b'{"rules": "vandal"}')
    (state / "mystery.json").write_bytes(b"?")

    rc = demo_gold.main(
        ["reset", "--state-dir", str(state), "--gold-dir", str(gold), "--reason", "test"]
    )
    assert rc == 1
    assert (
        state / "garde_fous_state.json"
    ).read_bytes() == b'{"rules": "vandal"}', "a refused reset mutates nothing"
    entry = json.loads((state / "demo_resets.jsonl").read_text().splitlines()[0])
    assert entry["verdict"] == "refused-stranger", "a refused act is still a journaled act"
    # The blessing refuses the same stranger: classification comes first.
    assert demo_gold.main(["snapshot", "--state-dir", str(state), "--gold-dir", str(gold)]) == 1


def test_without_a_gold_the_verdict_is_cannot_say_never_ok(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _seed(state)
    gold = tmp_path / "gold"
    assert demo_gold.main(["verify", "--state-dir", str(state), "--gold-dir", str(gold)]) == 2
    assert (
        demo_gold.main(
            ["reset", "--state-dir", str(state), "--gold-dir", str(gold), "--reason", "x"]
        )
        == 2
    )


def test_a_reset_without_a_reason_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        demo_gold.main(["reset", "--state-dir", str(tmp_path), "--gold-dir", str(tmp_path)])
    assert excinfo.value.code == 2
