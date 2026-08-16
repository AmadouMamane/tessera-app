"""One component, one address — nobody re-declares where a declared component lives.

On 2026-08-07 the observability page said, of ONE component and in ONE screen, that
``langfuse-web`` was **OK** (component table) and that it was **to blame** for a lost capability
(consequences block). Both witnesses were honest. They were interrogating two different
addresses:

* the probe asked the DECLARED address, ``langfuse-web:3000``, and got HTTP 200;
* the reader asked its own private literal, ``http://localhost:3900`` — inside the container
  that is the container's own loopback, where nothing listens.

Nothing had injected ``LANGFUSE_HOST`` into the agent container (ClickHouse and Prometheus were
injected; Langfuse was forgotten), and the literal default was **plausible enough to hide the
omission**: it is the right address on a developer's host, which is exactly where anyone would
have tested it.

So the rule this file enforces is not "don't hard-code addresses" in the abstract. It is: a
component's address is declared in ``stack_components`` and **read from there**. A second copy
elsewhere cannot be kept in sync by discipline — it was already wrong in five files by the time
anybody noticed, and each copy was written by someone who believed they were writing the right
address.

What this can and cannot see (ADR 0026 — a witness that cannot see must say so rather than
report "ok"):

* it sees string CONSTANTS in ``src/`` and ``scripts/``, not comments, not docstrings, and not
  values assembled at runtime from pieces;
* it can only police the address forms the declaration actually carries: the compose address for
  every component, plus the published ``127.0.0.1:<port>`` door for those declaring a
  ``default_ui``. A component with no declared door (ClickHouse, Postgres, Redis…) has no
  published-port form for this to recognise — :func:`test_the_ratchet_names_what_it_cannot_see`
  keeps that blind spot written down instead of implied.
"""

from __future__ import annotations

import ast
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tessera.observability.stack_components import (
    STACK_COMPONENTS,
    base_url_for,
    component_for,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT = Path(__file__).resolve().parents[2]
_SCANNED = (_ROOT / "src", _ROOT / "scripts")

#: The one module allowed to spell a component's address: the declaration itself.
_DECLARATION = "stack_components.py"


def _banned_forms() -> dict[str, str]:
    """Every address literal that belongs to a declared component, mapped to that component."""
    forms: dict[str, str] = {}
    for component in STACK_COMPONENTS:
        if not component.default_address:
            # NO DECLARED ADDRESS, NOTHING TO POLICE — and the empty string is a substring of
            # every line in the repository, so without this guard the scan below reports the
            # entire codebase as a redeclaration of it. Found the moment `public-canonical`
            # arrived (ADR 0052 §Amendment 2): its host is deliberately undeclared here, because
            # no domain is baked into the image.
            #
            # This leaves a HOLE, recorded as one in the companion test below rather than
            # implied: a private copy of the public hostname would pass this scan unseen. There
            # is no declaration for it to duplicate, and creating one — a hostname in the code —
            # is exactly what the design refuses.
            continue
        forms[component.default_address] = component.key
        if component.default_ui:
            netloc = urllib.parse.urlsplit(component.default_ui).netloc
            _, _, port = netloc.rpartition(":")
            if port.isdigit():
                forms[f"127.0.0.1:{port}"] = component.key
                forms[f"localhost:{port}"] = component.key
    return forms


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Ids of the string nodes that are docstrings — prose may name an address."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def _string_constants(path: Path) -> Iterator[tuple[int, str]]:
    """Every non-docstring string constant in ``path``, as ``(lineno, value)``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            yield node.lineno, node.value


def test_no_module_redeclares_a_component_address() -> None:
    """A component's address is declared once; every reader resolves it from there."""
    forms = _banned_forms()
    offences: list[str] = []
    for root in _SCANNED:
        for path in sorted(root.rglob("*.py")):
            if path.name == _DECLARATION:
                continue
            for lineno, value in _string_constants(path):
                for form, key in forms.items():
                    if form in value:
                        offences.append(
                            f"{path.relative_to(_ROOT)}:{lineno} carries {form!r}, which is "
                            f"{key}'s address — resolve it with "
                            f'base_url_for("{key}") instead of copying it'
                        )
    assert offences == [], "\n".join(offences)


def test_the_ratchet_names_what_it_cannot_see() -> None:
    """The blind spot is written down, not implied.

    A component that declares no browser door publishes no ``127.0.0.1:<port>`` form for the
    scan above to recognise, so a private copy of its HOST-side address would pass unseen. That
    is a real hole; recording it here is what keeps a green run from meaning more than it does.
    """
    doorless = sorted(c.key for c in STACK_COMPONENTS if not c.default_ui)
    assert doorless == [
        # ClickHouse is the live instance of the hole: its reader still carries
        # ``http://localhost:18123`` — the published port, which no declaration names — and this
        # scan cannot see it. It is injected in the container and set in `.env.local`, so it is
        # not currently wrong; it is currently unpoliced, which is a different sentence.
        "clickhouse",
        "langfuse-db",
        "langfuse-redis",
        "langfuse-worker",
        "otel-collector",
        "postgres",
        # The public edge is doorless HERE and not in the running cockpit, which is the whole
        # point: `default_ui` is a literal, and a literal is where a hostname would have to be
        # written. `make fulllocal-up` exports TESSERA_STACK_UI_PUBLIC_CANONICAL from
        # `targets.yaml`, so `ui_url()` gives the operator a live link to the actual public URL
        # while nothing about a domain is compiled in. The cost is stated above: this scan
        # cannot police a private copy of that hostname.
        "public-canonical",
        "redis",
    ], (
        "the set of components whose published address this ratchet cannot police has changed; "
        "confirm the new entry needs no door, or declare its default_ui so it becomes visible"
    )


def test_base_url_resolves_from_the_declaration_when_nothing_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No injected address ⇒ the declared one, which is the address the probe uses."""
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.delenv("TESSERA_STACK_LANGFUSE_WEB", raising=False)
    assert base_url_for("langfuse-web", env="LANGFUSE_HOST") == "http://langfuse-web:3000"
    assert base_url_for("langfuse-web") == "http://langfuse-web:3000"


def test_the_tools_own_variable_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment that injects ``LANGFUSE_HOST`` is obeyed — that is the whole point of it."""
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.eu/")
    assert base_url_for("langfuse-web", env="LANGFUSE_HOST") == "https://langfuse.example.eu"


def test_the_stack_override_wins_over_the_declaration(monkeypatch: pytest.MonkeyPatch) -> None:
    """``TESSERA_STACK_<KEY>`` moves the probe and every reader together, never one of them."""
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setenv("TESSERA_STACK_LANGFUSE_WEB", "langfuse-web.obs:3000")
    assert base_url_for("langfuse-web", env="LANGFUSE_HOST") == "http://langfuse-web.obs:3000"


def test_an_empty_injection_is_an_unfilled_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    """``LANGFUSE_HOST=`` in a compose file is somebody's TODO, never a deliberate address."""
    monkeypatch.setenv("LANGFUSE_HOST", "  ")
    monkeypatch.delenv("TESSERA_STACK_LANGFUSE_WEB", raising=False)
    assert base_url_for("langfuse-web", env="LANGFUSE_HOST") == "http://langfuse-web:3000"


def test_a_tcp_component_has_no_base_url() -> None:
    """Handing back a URL for a TCP component would hand back a URL nobody can fetch."""
    with pytest.raises(ValueError, match="no base URL"):
        base_url_for("postgres")


def test_an_undeclared_component_is_a_bug_not_an_address_to_guess() -> None:
    with pytest.raises(KeyError):
        component_for("langfuse-webb")


def test_the_read_address_and_the_browser_door_stay_apart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service name is unreachable from a browser; the published port is, and vice versa.

    Conflating them is how a dashboard grows links to closed doors — and it is what this fix
    would have caused had ``_traces_url`` kept following the read host.
    """
    from tessera.observability import langfuse_obs

    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.delenv("TESSERA_STACK_UI_LANGFUSE_WEB", raising=False)
    assert langfuse_obs._host() == "http://langfuse-web:3000"
    assert langfuse_obs._door() == "http://127.0.0.1:3900"
    assert langfuse_obs._traces_url().startswith("http://127.0.0.1:3900/project/")
