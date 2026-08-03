"""Re-derive an eval report's judgements from its recorded responses.

Thin wrapper around :func:`eval.regrade.main`. No token is spent and no sample is drawn: the
responses are already on disk, and only the criteria that judge them have moved.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Invoked directly, sys.path[0] is this script's directory, so the top-level `eval` package is
# not importable. Put the repo root on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.regrade import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
