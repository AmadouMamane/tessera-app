"""The URL gate refuses what it claims to refuse — and still opens what it must.

Seven call sites used to carry a ``# noqa: S310`` whose justification was prose about where the
URL came from. Prose is not a check, and the first CI runner to see this tree (2026-08-04, after
158 commits without one) reported every one of them. :mod:`tessera.urlfetch` replaced the prose
with a gate; this file is the reason to believe the gate.

The decisive test is the negative one: ``file:///etc/passwd`` must be refused **before** any I/O.
A gate that let it through would return an object that reads exactly like an HTTP response —
which is why the hole was invisible for so long.
"""

from __future__ import annotations

import urllib.request
from typing import TYPE_CHECKING

import pytest

from tessera.urlfetch import (
    ALLOWED_SCHEMES,
    UnsupportedSchemeError,
    check_scheme,
    urlopen_http,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestItRefusesEverythingButHttp:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.invalid/x",
            "gopher://example.invalid/",
            "data:text/plain,hello",
            "/no/scheme/at/all",
            "",
        ],
    )
    def test_a_non_http_url_is_refused(self, url: str) -> None:
        with pytest.raises(UnsupportedSchemeError):
            check_scheme(url)

    def test_a_request_object_is_checked_by_its_url_not_its_type(self) -> None:
        """``urlopen`` accepts a ``Request``; the gate must look through it, not around it."""
        request = urllib.request.Request("file:///etc/passwd")  # noqa: S310  refused below
        with pytest.raises(UnsupportedSchemeError):
            check_scheme(request)

    def test_the_refusal_names_the_url_and_the_scheme(self) -> None:
        with pytest.raises(UnsupportedSchemeError) as caught:
            check_scheme("file:///etc/passwd")
        message = str(caught.value)
        assert "file" in message
        assert "/etc/passwd" in message, "a refusal that does not name its subject is unusable"

    def test_no_file_is_read_even_when_it_exists(self, tmp_path: Path) -> None:
        """The point, stated as behaviour: refusal happens before any I/O."""
        secret = tmp_path / "secret.txt"
        secret.write_text("the-content-that-must-not-be-returned")
        with pytest.raises(UnsupportedSchemeError):
            urlopen_http(secret.as_uri(), timeout=1)


class TestItStillOpensWhatItMust:
    @pytest.mark.parametrize("url", ["http://example.invalid/x", "https://example.invalid/x"])
    def test_http_and_https_pass_the_gate(self, url: str) -> None:
        assert check_scheme(url) in ALLOWED_SCHEMES

    def test_the_scheme_is_compared_case_insensitively(self) -> None:
        assert check_scheme("HTTPS://example.invalid/x") == "https"

    def test_a_permitted_url_reaches_the_network_layer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Anti-vacuity: prove the gate OPENS, not merely that it fails to raise.

        Without this, every assertion above would still pass if ``urlopen_http`` refused
        everything — including the schemes it exists to allow.
        """
        seen: list[tuple[object, float]] = []

        def _fake_urlopen(target: object, timeout: float = 0.0) -> object:
            seen.append((target, timeout))
            return object()

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
        urlopen_http("https://example.invalid/x", timeout=7)
        assert seen == [("https://example.invalid/x", 7)]
