"""Unit tests for :func:`tessera.fsutil.atomic_write_text` (ADR 0044).

The helper exists so a concurrent reader on another worker never sees a truncated document.
The tests assert the observable contract: the file ends with the full new contents, the parent
directory is created, no temp sibling is left behind, and — the load-bearing property — a
reader that opens the target at ANY point sees either the whole old file or the whole new one,
never a partial write.
"""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from tessera.fsutil import atomic_write_text

if TYPE_CHECKING:
    from pathlib import Path


def test_writes_full_contents(tmp_path: Path) -> None:
    target = tmp_path / "doc.json"
    atomic_write_text(target, '{"a": 1}')
    assert target.read_text(encoding="utf-8") == '{"a": 1}'


def test_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "doc.json"
    atomic_write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "doc.json"
    target.write_text("OLD", encoding="utf-8")
    atomic_write_text(target, "NEW")
    assert target.read_text(encoding="utf-8") == "NEW"


def test_leaves_no_temp_sibling(tmp_path: Path) -> None:
    target = tmp_path / "doc.json"
    atomic_write_text(target, "x")
    # Only the target remains — the temp file was renamed over it, not left behind.
    assert [p.name for p in tmp_path.iterdir()] == ["doc.json"]


def test_replace_is_the_publish_step(tmp_path: Path) -> None:
    """The new bytes become visible ONLY at the rename — never a truncate-then-write window.

    We fail the rename after the temp file is fully written and assert the reader still sees
    the OLD contents intact: proof the target is never the thing being written into.
    """
    target = tmp_path / "doc.json"
    target.write_text("OLD", encoding="utf-8")
    with (
        mock.patch("pathlib.Path.replace", side_effect=OSError("boom")),
        pytest.raises(OSError, match="boom"),
    ):
        atomic_write_text(target, "NEW")
    # The failed write did not touch the target; the old document is whole.
    assert target.read_text(encoding="utf-8") == "OLD"
    # And the half-published temp file was cleaned up rather than left as litter.
    assert [p.name for p in tmp_path.iterdir()] == ["doc.json"]


def test_temp_file_is_fsynced(tmp_path: Path) -> None:
    """Durability: the bytes are fsynced before the rename publishes them."""
    target = tmp_path / "doc.json"
    with mock.patch("tessera.fsutil.os.fsync") as fsync:
        atomic_write_text(target, "x")
    assert fsync.called


def test_respects_encoding(tmp_path: Path) -> None:
    target = tmp_path / "doc.txt"
    atomic_write_text(target, "café — €", encoding="utf-8")
    assert target.read_bytes() == "café — €".encode()


def test_temp_sibling_lives_in_target_directory(tmp_path: Path) -> None:
    """The temp file must be a sibling so the rename stays same-filesystem (hence atomic)."""
    target = tmp_path / "sub" / "doc.json"
    captured: dict[str, object] = {}
    real_ntf = tempfile.NamedTemporaryFile

    def _spy(*args: object, **kwargs: object) -> object:
        captured["dir"] = kwargs.get("dir")
        return real_ntf(*args, **kwargs)  # type: ignore[arg-type]

    with mock.patch("tessera.fsutil.tempfile.NamedTemporaryFile", side_effect=_spy):
        atomic_write_text(target, "x")
    assert captured["dir"] == target.parent
