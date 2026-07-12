#!/usr/bin/env python
"""Fail unless an eval report proves a model actually answered.

The runner does not crash when its LLM backend is unreachable: every case still
completes, the report still records the *configured* model name, and the
scorecard still reads ~70% — the deterministic guard layer scoring itself. So the
``model`` field proves nothing. Generated tokens do.

Any pipeline that files a report as a model verdict must run this first.

Usage:
    uv run python scripts/assert_model_spoke.py eval/reports/replay.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from eval.ratchet import model_spoke


def main(argv: list[str] | None = None) -> int:
    """Exit non-zero if the report carries no evidence that a model spoke."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        sys.stderr.write("usage: assert_model_spoke.py <report.json>\n")
        return 2
    report = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    if not model_spoke(report):
        sys.stderr.write(
            f"no model spoke: the run generated 0 output tokens, yet the report "
            f"claims model={report.get('model')!r}. This is a modelless run — it "
            f"scores the deterministic layer alone and must not be filed as a "
            f"model result.\n"
        )
        return 1
    tokens = int((report.get("cost") or {}).get("output_tokens", 0))
    sys.stdout.write(f"model liveness OK — {tokens} output tokens generated\n")
    return 0


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
