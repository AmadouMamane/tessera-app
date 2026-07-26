"""Env-aware resolution of the eval report archive (ADR 0014, layer 3).

Eval reports are *file-based* cross-environment state — they live under
``eval/reports/`` in the repo, not under the Postgres ``search_path`` that
isolates the durable tables (layer 1). So they isolate the same way the schema
does: **by path, per environment**.

Contract (the layer-3 guardrails):

* **Writes go to ``eval/reports/<env>/`` exclusively** (:func:`reports_write_dir`).
* **Reads** prefer ``<env>/`` and fall back, read-only, to the legacy flat
  ``eval/reports/`` as an *archive bridge* — never to another environment's
  subfolder (:func:`report_read_dirs`, :func:`iter_report_files`).

Once the existing flat files are moved into their ``<env>/`` subfolder the flat
root holds no ``*.json`` and the bridge disappears on its own, so the fallback
can later be removed without ceremony.

A third, lowest-priority read location is the committed **seed** archive
(``eval/reports/seed/``). Unlike the generated per-env reports it is *tracked*, so
it travels inside the built image (``Dockerfile.agent`` ``COPY eval``). It is the
floor that keeps the eval-driven dashboards (agent history, evaluations, control
signals) from degrading to ``available: false`` on a deployment that has no host
directory to mount and no run of its own yet. It is consulted **only when the env
archive is empty** — any real per-env run always wins — and it is skipped entirely
when ``TESSERA_REPORTS_DIR`` pins an exact directory. It never fabricates a number;
it is real ``llama3.2:3b`` catalogue output, committed as a guaranteed minimum.
"""

from __future__ import annotations

import os
from pathlib import Path

from tessera.settings import get_settings

__all__ = [
    "iter_report_files",
    "report_files_for",
    "report_read_dirs",
    "reports_flat_root",
    "reports_seed_root",
    "reports_write_dir",
    "resolve_report_file",
]

# src/tessera/observability/eval/report_paths.py → parents[4] == repo root.
_FLAT_ROOT = Path(__file__).resolve().parents[4] / "eval" / "reports"
# The committed, read-only floor archive — the only reports tracked in git, so the
# only ones that travel inside the built image.
_SEED_ROOT = _FLAT_ROOT / "seed"


def _override_dir() -> Path | None:
    """Explicit pin for the report directory, bypassing env resolution.

    ``TESSERA_REPORTS_DIR`` forces both reads and writes to one directory — used
    by tests/CI to read a fixed archive deterministically (the same escape hatch
    pattern as ``TESSERA_BUDGET_FILE``). Unset → normal per-env resolution.
    """
    value = os.environ.get("TESSERA_REPORTS_DIR")
    return Path(value) if value else None


def reports_flat_root() -> Path:
    """The legacy flat archive root (``eval/reports``), environment-independent."""
    return _FLAT_ROOT


def reports_seed_root() -> Path:
    """The committed, read-only floor archive (``eval/reports/seed``).

    The only reports tracked in git, and therefore the only ones the built image
    ships. Read as a last resort by :func:`iter_report_files` when the per-env
    archive is empty.
    """
    return _SEED_ROOT


def _env_name(env: str | None) -> str:
    return env or get_settings().environment.value


def reports_write_dir(env: str | None = None) -> Path:
    """Directory this environment writes reports to: ``eval/reports/<env>/``."""
    return _override_dir() or (_FLAT_ROOT / _env_name(env))


def report_read_dirs(env: str | None = None) -> list[Path]:
    """Directories to read reports from, most-specific first.

    ``<env>/`` always; then the flat root as a read-only archive bridge, but only
    while it still holds loose ``*.json`` files (i.e. before the one-time move).
    Never another environment's subfolder.
    """
    write = reports_write_dir(env)
    dirs = [write]
    if write != _FLAT_ROOT and any(_FLAT_ROOT.glob("*.json")):
        dirs.append(_FLAT_ROOT)
    return dirs


def iter_report_files(env: str | None = None) -> list[Path]:
    """All report ``*.json`` across the read dirs; ``<env>/`` wins on a name clash.

    Falls through to the committed seed floor (:func:`reports_seed_root`) ONLY when
    the per-env archive is empty, so a real per-env run always wins and the seed can
    never dilute or outrank live output. The fall-through is skipped when
    ``TESSERA_REPORTS_DIR`` pins an exact directory (tests read precisely that dir).
    """
    seen: dict[str, Path] = {}
    for directory in report_read_dirs(env):
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            seen.setdefault(path.name, path)  # first dir (env) wins
    if not seen and _override_dir() is None and _SEED_ROOT.exists():
        for path in _SEED_ROOT.glob("*.json"):
            seen.setdefault(path.name, path)
    return list(seen.values())


def report_files_for(reports_dir: Path | None = None) -> list[Path]:
    """Report ``*.json`` to read, for a loader that accepts an optional directory.

    An explicit ``reports_dir`` is honoured as-is (the test path globs exactly
    that directory); ``None`` means the env-aware set — ``<env>/`` plus the flat
    archive bridge — so production code isolates by environment automatically.
    """
    if reports_dir is not None:
        return sorted(reports_dir.glob("*.json")) if reports_dir.exists() else []
    return iter_report_files()


def resolve_report_file(name: str, env: str | None = None) -> Path:
    """Resolve a single named cache file (e.g. ``_agent_judge.json``) for reading.

    Returns ``<env>/<name>`` when it exists, else the flat ``<name>`` as the
    archive bridge, else the ``<env>/<name>`` path (which a caller may then write).
    """
    candidate = reports_write_dir(env) / name
    if candidate.exists():
        return candidate
    flat = _FLAT_ROOT / name
    if flat.exists():
        return flat
    return candidate
