"""Unit tests for the worker-count wiring in ``cli()`` (ADR 0044).

The load-bearing invariant is that the default (``workers=1``) is byte-identical to the
pre-ADR single-process boot: no ``workers`` kwarg to uvicorn, no ``PROMETHEUS_MULTIPROC_DIR``.
Only ``workers>1`` flips uvicorn into multiprocess and (when metrics are on) prepares the
Prometheus mmap directory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _run_cli() -> dict[str, object]:
    """Call ``cli`` with uvicorn.run + the multiproc-dir prep captured, returning the run kwargs."""
    captured: dict[str, object] = {}

    def _capture_run(app: object, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    from tessera.api import main

    with (
        mock.patch("uvicorn.run", side_effect=_capture_run),
        mock.patch.object(main, "_prepare_multiprocess_metrics") as prep,
    ):
        main.cli()
    captured["_prep_called"] = prep.called
    return captured


def test_workers_default_is_one() -> None:
    assert get_settings().api.workers == 1


def test_single_worker_passes_workers_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESSERA_API__WORKERS", "1")
    get_settings.cache_clear()
    kwargs = _run_cli()
    # workers=None is exactly uvicorn's own default → identical to the pre-ADR single-process
    # boot (no multiprocess supervisor).
    assert kwargs["workers"] is None
    assert kwargs["_prep_called"] is False
    assert kwargs["factory"] is True


def test_multi_worker_passes_workers_kwarg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESSERA_API__WORKERS", "4")
    # metrics disabled (suite default): still multi-worker, but no mmap dir to prepare.
    get_settings.cache_clear()
    kwargs = _run_cli()
    assert kwargs["workers"] == 4
    assert kwargs["_prep_called"] is False  # metrics off → nothing to aggregate


def test_multi_worker_with_metrics_prepares_multiproc_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESSERA_API__WORKERS", "4")
    monkeypatch.setenv("TESSERA_OBSERVABILITY__METRICS_ENABLED", "true")
    get_settings.cache_clear()
    kwargs = _run_cli()
    assert kwargs["workers"] == 4
    assert kwargs["_prep_called"] is True


def test_workers_floor_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    # A nonsensical 0 must not silently disable the server; it floors to a single process.
    monkeypatch.setenv("TESSERA_API__WORKERS", "0")
    get_settings.cache_clear()
    kwargs = _run_cli()
    assert kwargs["workers"] is None


def test_prepare_multiprocess_metrics_creates_empty_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tessera.api.main import _prepare_multiprocess_metrics

    # Let monkeypatch OWN the key so its raw os.environ write is restored on teardown,
    # never leaking into a test that expects the single-process (env-unset) branch.
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "placeholder")
    target = tmp_path / "prometheus"
    # A stale file from a previous run must be wiped — else it would inflate every counter.
    target.mkdir()
    (target / "counter_123.db").write_text("stale", encoding="utf-8")

    _prepare_multiprocess_metrics(target)

    assert target.is_dir()
    assert list(target.iterdir()) == []  # wiped clean
    import os

    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == str(target)
