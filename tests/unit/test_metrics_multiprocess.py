"""Unit tests for the multi-worker metrics wiring (ADR 0044).

Two behaviours matter and are unit-testable without spawning workers or binding a socket:

* the exposition registry is the module registry in single-process mode and a *fresh*,
  multiprocess-collector-backed registry when ``PROMETHEUS_MULTIPROC_DIR`` is set;
* ``configure(serve=...)`` binds the HTTP server only when this process is the leader — a
  non-leader records but never opens the port, so N workers cannot fight over it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from tessera.observability import metrics

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_started() -> object:
    """``configure`` latches a module-global; reset it around each test."""
    metrics._started = False
    yield
    metrics._started = False


def test_exposition_registry_is_module_registry_when_single_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    assert metrics._exposition_registry() is metrics.registry


def test_exposition_registry_aggregates_when_multiproc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    agg = metrics._exposition_registry()
    # A distinct registry (fed by MultiProcessCollector), never the process-local one.
    assert agg is not metrics.registry


def test_configure_leader_binds_the_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESSERA_OBSERVABILITY__METRICS_ENABLED", "true")
    from tessera.settings import get_settings

    get_settings.cache_clear()
    with mock.patch("tessera.observability.metrics.start_http_server") as start:
        metrics.configure(serve=True)
    assert start.called


def test_configure_non_leader_records_but_never_binds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESSERA_OBSERVABILITY__METRICS_ENABLED", "true")
    from tessera.settings import get_settings

    get_settings.cache_clear()
    with mock.patch("tessera.observability.metrics.start_http_server") as start:
        metrics.configure(serve=False)
    # Non-leader: the mmap store still records; the socket is never opened.
    assert not start.called
    assert metrics._started is True  # latched, so a second call is a no-op


def test_configure_disabled_never_binds(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default suite posture: metrics disabled. Neither leader nor follower binds.
    with mock.patch("tessera.observability.metrics.start_http_server") as start:
        metrics.configure(serve=True)
    assert not start.called
