"""URL scheme validation — the one gate every ``urlopen`` in this codebase goes through.

``urllib.request.urlopen`` is not an HTTP client. It dispatches on the URL's scheme and will
just as happily open ``file:///etc/passwd``, ``ftp://…``, or anything a handler has been
registered for — returning an object that reads like a perfectly ordinary response. So a
configuration string that reaches it unchecked is not "an endpoint we trust"; it is an
arbitrary read primitive with a plausible-looking result.

Seven call sites reached it directly — the guard's timestamp authority, the Langfuse and
ClickHouse and Prometheus adapters, and two preflight probes. Every one of them carried a
``# noqa: S310`` explaining, in prose, why *that* URL was fine. All seven explanations were
true. None of them was a check:

* ruff's S310 and bandit's B310 are **syntactic** rules. They fire on the call and cannot see
  where the URL came from, so a suppression is the only way to quiet them — and a suppression
  is a promise, kept by whoever edits the line next;
* the promises were about provenance ("operator URL", "self-hosted spine", "fixed https TSA
  endpoint from config"), and provenance is exactly what a later refactor changes silently;
* and none of the seven carried bandit's marker at all, only ruff's. The CI runner that first
  ran bandit on this tree — 2026-08-04, after 158 commits with no runner — reported all seven.

So, the same doctrine as :mod:`tessera.sql`: replace the prose with a gate. The scheme is
checked here, once, at the point of the call, and the suppressions below state a fact that the
three lines above them prove, rather than a fact about somewhere else in the program.

A pleasant consequence: because the scheme is restricted to http/https, the return type is no
longer "whatever handler matched" but always :class:`http.client.HTTPResponse`.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    import http.client
    from collections.abc import Iterable

#: The only schemes this codebase opens. Deliberately not configurable: a setting that widens
#: it would recreate the hole, and no caller here has ever needed anything else.
ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})


class UnsupportedSchemeError(ValueError):
    """A URL was refused before it was opened, because of its scheme.

    A ``ValueError``, so the existing call sites — which already catch ``URLError``/``OSError``
    and degrade honestly — are not silently bypassed by a new exception type they do not know.
    Each site catches this explicitly where it matters; see the adapters.
    """


def _url_of(target: str | urllib.request.Request) -> str:
    return target if isinstance(target, str) else target.full_url


def check_scheme(
    target: str | urllib.request.Request,
    *,
    allowed: Iterable[str] = ALLOWED_SCHEMES,
) -> str:
    """Return the URL's scheme, or raise :class:`UnsupportedSchemeError`.

    Args:
        target: The URL, or the ``Request`` that carries it.
        allowed: The permitted schemes, lower-case.

    Returns:
        The validated, lower-cased scheme.

    Raises:
        UnsupportedSchemeError: If the URL has no scheme, or one outside ``allowed``.
    """
    url = _url_of(target)
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    permitted = frozenset(allowed)
    if scheme not in permitted:
        shown = scheme or "no scheme"
        wanted = ", ".join(sorted(permitted))
        msg = f"refusing to open {url!r}: {shown} is not one of {wanted}"
        raise UnsupportedSchemeError(msg)
    return scheme


def urlopen_http(
    target: str | urllib.request.Request,
    *,
    timeout: float,
) -> http.client.HTTPResponse:
    """Open ``target`` over http/https only, or refuse.

    Args:
        target: The URL, or a prepared ``Request`` (headers, method, body).
        timeout: Seconds, mandatory and keyword-only — an ``urlopen`` without one blocks
            forever on a black-holed host, which is how a probe becomes an outage.

    Returns:
        The response, usable as a context manager exactly like ``urlopen``'s.

    Raises:
        UnsupportedSchemeError: Before any network call, if the scheme is not http/https.
    """
    check_scheme(target)
    # The suppressions state a fact the line above proves: the scheme is http or https, so
    # this cannot open a file, an FTP resource, or a custom handler's target. Both markers
    # must sit on the flagged line itself: bandit ignores a nosec marker written on the line
    # before, and reports "0 lines skipped" while doing it. Note also that bandit reads
    # EVERYTHING after its marker as test ids, so a marker must never be followed by prose.
    opened = urllib.request.urlopen(target, timeout=timeout)  # noqa: S310  # nosec B310
    return cast("http.client.HTTPResponse", opened)
