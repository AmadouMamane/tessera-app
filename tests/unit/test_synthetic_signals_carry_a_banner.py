"""A signal that is not LIVE says so on screen — and a LIVE one does not apologise.

``SignalCapability.synthetic`` is derived from ``provenance`` in
:mod:`tessera.observability.spine.capabilities`, and it is the whole point of the declaration:
a fallback, a preview, a simulation or a reference table must never present itself as a live
measurement. The cockpit honours it by mounting ``<ProvenanceNotice signalId="…">`` on the
surfaces that render those signals.

Nothing connected the two. The declaration lives in Python, the banner in TSX, and the only
thing keeping them aligned was that somebody had aligned them — measured on 2026-08-04, all
eleven non-LIVE signals carried a banner and no LIVE one did. That is a good state and it was
entirely undefended: flipping a provenance to ``SIMULATION`` in one file makes a page claim a
live measurement it no longer takes, with nothing red anywhere.

Both directions are asserted, because both are wrong:

* a non-LIVE signal with no banner presents a fixture as a measurement;
* a LIVE signal with one tells an operator to discount a real number — which is how a genuine
  measurement gets ignored on the day it matters.

The scan is textual and says so. It sees ``signalId="x"`` as a literal, so a banner whose id is
computed at runtime would read as absent; that is a deliberate trade, since an id worth
declaring is worth writing down. The counters below refuse a vacuous pass if the scan stops
finding files at all.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessera.observability.spine.capabilities import CAPABILITIES

_REPO = Path(__file__).resolve().parents[2]
_FRONTEND = _REPO / "webapp" / "frontend"
_MOUNT = re.compile(r'ProvenanceNotice\s+signalId="([^"]+)"')


def _mounted_banners() -> tuple[set[str], int]:
    """Signal ids with a mounted provenance banner, and how many files were read."""
    ids: set[str] = set()
    files = 0
    for path in _FRONTEND.rglob("*.tsx"):
        if "node_modules" in path.parts or ".test." in path.name:
            continue
        files += 1
        ids.update(_MOUNT.findall(path.read_text(encoding="utf-8", errors="replace")))
    return ids, files


class TestTheScanCanSee:
    """A zero here must mean "none", never "did not look" (ADR 0026)."""

    def test_it_reads_the_frontend_at_all(self) -> None:
        _, files = _mounted_banners()
        assert files > 150, f"the component scan read {files} files — the tree moved"

    def test_it_finds_banners(self) -> None:
        ids, _ = _mounted_banners()
        assert len(ids) >= 8, f"only {len(ids)} banners found: {sorted(ids)}"

    def test_the_declaration_still_distinguishes_the_two(self) -> None:
        synthetic = {c.id for c in CAPABILITIES.values() if c.synthetic}
        live = {c.id for c in CAPABILITIES.values() if not c.synthetic}
        assert synthetic, "no capability is declared non-LIVE — the flag stopped meaning anything"
        assert live, "every capability is declared non-LIVE — likewise"


class TestEveryNonLiveSignalSaysSo:
    def test_no_fixture_presents_itself_as_a_measurement(self) -> None:
        ids, _ = _mounted_banners()
        synthetic = {c.id for c in CAPABILITIES.values() if c.synthetic}
        missing = sorted(synthetic - ids)
        assert not missing, (
            f"{missing} declare a non-LIVE provenance and mount no ProvenanceNotice — the "
            "cockpit renders a fallback, preview or simulation as a live measurement"
        )

    def test_no_real_measurement_is_told_to_be_discounted(self) -> None:
        ids, _ = _mounted_banners()
        live = {c.id for c in CAPABILITIES.values() if not c.synthetic}
        spurious = sorted(ids & live)
        assert not spurious, (
            f"{spurious} are declared LIVE and still carry a provenance banner — a real number "
            "wearing a disclaimer is a real number nobody acts on"
        )

    def test_every_mounted_banner_names_a_declared_signal(self) -> None:
        ids, _ = _mounted_banners()
        undeclared = sorted(ids - set(CAPABILITIES))
        assert not undeclared, (
            f"{undeclared} mount a banner for a signal that declares no capability — the notice "
            "renders from nothing, which is a declaration nobody made"
        )
