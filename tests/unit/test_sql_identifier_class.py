"""P0.3 `sql-fstring` — the class of interpolated SQL identifiers, closed.

Audit 2026-07-10. None of the interpolated names came from user input, so this was never a
live exploit — it was a *class* risk: a dozen modules splicing configuration strings into
query text, each relying on "it's safe because of where it comes from". The audit asked for
the class to be closed, not for seven lines to be patched.

An identifier **cannot be parameterised**. `FROM %s` is not a query — a driver binds values,
never names. So the only defence is to prove, before splicing, that the string cannot be
anything but a name. That is `tessera.sql.safe_identifier`, and this file pins it.

What was actually there before (none of it in the audit's list):

* **Two divergent private validators** — `agent_scope._ident` (`^[a-z_][a-z0-9_]*$`) and
  `clickhouse._IDENTIFIER` (`^[A-Za-z_][A-Za-z0-9_]*$`). Same idea, two spellings, neither
  reused.
* **Both used `re.match`**, which with a `$` anchor still admits a **trailing newline**.
* **Most sites validated nothing at all**, including `retrieval/store.py` — the primary
  consumer of `postgres.vector_table`, which **ruff never flagged**, because S608's heuristic
  misses indented multi-line f-strings. Counting `# noqa: S608` undercounts the class.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tessera.sql import MAX_IDENTIFIER_LENGTH, safe_identifier, safe_qualified_identifier

_SRC = Path(__file__).resolve().parents[2] / "src" / "tessera"


class TestTheGateItself:
    """`safe_identifier` accepts names and nothing else."""

    @pytest.mark.parametrize(
        "name",
        ["documents", "audit_ledger", "_private", "T1", "a", "eval_online_scores", "A_b_9"],
    )
    def test_a_real_identifier_passes_through_unchanged(self, name: str) -> None:
        assert safe_identifier(name) == name

    @pytest.mark.parametrize(
        "name",
        [
            "x; DROP TABLE audit_ledger",  # the finding's own example
            "users; --",
            "documents WHERE 1=1",
            "a b",
            "tbl'",
            '"quoted"',
            "sales-2026",
            "1_starts_with_digit",
            "sché_ma",  # unicode is not an identifier here, deliberately
            "",
            "documents.public",  # a dot is a qualified name, not a bare one
        ],
    )
    def test_anything_that_is_not_an_identifier_is_refused(self, name: str) -> None:
        with pytest.raises(ValueError, match="unsafe SQL identifier"):
            safe_identifier(name)

    def test_a_trailing_newline_is_refused(self) -> None:
        """The exact input both private validators used to let through.

        `re.match(r"^[a-z_][a-z0-9_]*$", "documents\\n")` **matches** — `$` also anchors just
        before a trailing newline. `fullmatch` does not. It is a narrow hole, and it is
        precisely the kind of thing the check exists for: a name that is *almost* a name.
        """
        legacy = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        assert legacy.match("documents\n") is not None, "the old validator accepted this"

        with pytest.raises(ValueError, match="unsafe SQL identifier"):
            safe_identifier("documents\n")

    def test_an_over_long_name_is_refused_rather_than_silently_truncated(self) -> None:
        """Postgres truncates at 63 bytes. A silently *different* table is worse than a crash."""
        safe_identifier("a" * MAX_IDENTIFIER_LENGTH)  # the boundary is allowed

        with pytest.raises(ValueError, match="must be 1"):
            safe_identifier("a" * (MAX_IDENTIFIER_LENGTH + 1))

    @pytest.mark.parametrize("name", ["tessera.business_events", "documents"])
    def test_a_qualified_name_validates_each_part(self, name: str) -> None:
        assert safe_qualified_identifier(name) == name

    @pytest.mark.parametrize(
        "name",
        ["tessera.events; DROP TABLE x", "a.b.c", "tessera.", ".events", "tessera.'x'"],
    )
    def test_a_qualified_name_cannot_smuggle_anything_past_the_dot(self, name: str) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            safe_qualified_identifier(name)


class TestTheSettingsBoundary:
    """The widest door in the class: a table name settable from the environment."""

    def test_an_unsafe_vector_table_cannot_enter_the_process(self) -> None:
        """`TESSERA_POSTGRES__VECTOR_TABLE` is spliced into CREATE TABLE / INSERT / SELECT.

        Validated at ingestion, so the deployment refuses to start rather than building a
        query around it. Before this, the value went straight from the environment into
        `retrieval/store.py`'s f-strings with no check anywhere on the path.
        """
        from tessera.settings import PostgresSettings

        with pytest.raises(ValueError, match="unsafe SQL identifier"):
            PostgresSettings(vector_table="documents; DROP TABLE audit_ledger")

    def test_the_default_is_still_accepted(self) -> None:
        from tessera.settings import PostgresSettings

        assert PostgresSettings().vector_table == "documents"


class TestTheClassRatchet:
    """The point of the lot: a NEW f-string SQL site cannot appear without the gate.

    The check reads the **AST**, and looks only at ``ast.JoinedStr`` — f-strings. That is not
    a detail, it is the whole design:

    * an **f-string** interpolates the name into the query text before the driver ever sees it
      — nothing downstream can save it, so it must be validated first;
    * ``psycopg.sql.SQL("… FROM {table} …").format(table=sql.Identifier(t))`` is a **plain
      string constant** that the *driver* composes and quotes. It is strictly safer and needs
      no gate. It is already the idiom in ``memory/`` and ``api/settings_store.py``.

    The two are textually identical — both read ``FROM {table}`` — so a grep cannot tell them
    apart. A first cut of this ratchet handled that by exempting any module that mentioned
    ``sql.Identifier``, and **that exemption silently whitewashed `retrieval/store.py`**, which
    composes its *schema* the safe way (line 93) and its *table* with a raw f-string. The
    module-level escape hatch made the ratchet pass while the hole was open — the exact failure
    mode it exists to prevent. The AST needs no exemption: a constant is not a JoinedStr.
    """

    #: A name being spliced into SQL: a keyword that takes an identifier, then a placeholder.
    #: `TABLE IF NOT EXISTS {t}` is included — the `CREATE TABLE` shape in `retrieval/store.py`
    #: that ruff's own S608 heuristic misses entirely.
    _SQL_INTERPOLATION = re.compile(
        r"(FROM|INTO|JOIN|UPDATE|TRUNCATE|DATABASE|TABLE(\s+IF\s+NOT\s+EXISTS)?"
        r"|search_path\s+TO)\s+\{[^{}]+\}",
        re.IGNORECASE,
    )

    def _offending_modules(self) -> list[str]:
        offenders: list[str] = []
        for path in sorted(_SRC.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if not _splices_an_identifier_in_an_fstring(source, self._SQL_INTERPOLATION):
                continue
            if _imports_the_gate(source):
                continue
            offenders.append(str(path.relative_to(_SRC.parent.parent)))
        return offenders

    def test_every_module_that_splices_an_identifier_imports_the_gate(self) -> None:
        assert self._offending_modules() == [], (
            "these modules splice a SQL identifier into an f-string without validating it — "
            "import `safe_identifier` from `tessera.sql`, or compose the query with "
            f"`psycopg.sql.SQL(...).format(table=sql.Identifier(...))`: {self._offending_modules()}"
        )

    def test_the_ratchet_catches_the_shape_that_ruff_does_not(self) -> None:
        """A ratchet that cannot fail is not a ratchet.

        The witness is the real one: `retrieval/store.py`'s indented multi-line
        `CREATE TABLE IF NOT EXISTS {table}`, which carried **no `# noqa: S608`** because ruff
        never flagged it — and which splices a table name settable from the environment.
        """
        offending = (
            "async def go():\n"
            '    await cur.execute(f"""\n'
            "        CREATE TABLE IF NOT EXISTS {table} (id bigserial)\n"
            '    """)\n'
        )

        assert _splices_an_identifier_in_an_fstring(offending, self._SQL_INTERPOLATION)
        assert not _imports_the_gate(offending)

    def test_the_driver_native_composition_is_not_flagged(self) -> None:
        """`sql.SQL(...).format(sql.Identifier(...))` is the better tool, not an offence.

        It reads *identically* to the dangerous form — `FROM {table}` — which is why this is
        asserted rather than assumed. It is a plain constant; the driver quotes the name.
        """
        safe = (
            "from psycopg import sql\n"
            'query = sql.SQL("DELETE FROM {table} WHERE id = %s").format(table=sql.Identifier(t))\n'
        )

        assert not _splices_an_identifier_in_an_fstring(safe, self._SQL_INTERPOLATION)

    def test_no_module_keeps_a_private_identifier_validator(self) -> None:
        """One rule, one implementation. Two divergent copies is how the hole survived.

        Reads the AST, not the text: several modules now *describe* the old pattern in a
        comment explaining why it was replaced, and a grep would flag the explanation as the
        offence. Only a real ``re.compile("<identifier pattern>")`` counts.
        """
        duplicates = [
            str(path.relative_to(_SRC.parent.parent))
            for path in sorted(_SRC.rglob("*.py"))
            if path.name != "sql.py" and _compiles_an_identifier_pattern(path.read_text())
        ]

        assert (
            duplicates == []
        ), f"a module re-implements the identifier check instead of importing it: {duplicates}"


def _imports_the_gate(source: str) -> bool:
    """True when the module imports `safe_identifier`/`safe_qualified_identifier`."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    gates = {"safe_identifier", "safe_qualified_identifier"}
    return any(
        node.module == "tessera.sql" and any(alias.name in gates for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )


def _fstring_text(node: ast.JoinedStr) -> str:
    """Render an f-string back to text, with every ``{expr}`` collapsed to a placeholder.

    ``f"SELECT * FROM {self.table} WHERE x = {{v:String}}"`` → ``SELECT * FROM {} WHERE …``.
    The *expression* does not matter — what matters is that a hole exists where an identifier
    goes. Escaped braces (ClickHouse's ``{{conv:String}}`` server-side params) are literal
    constants in the AST, so they never look like a hole. That is exactly right: they are
    bound by the server, not spliced by us.
    """
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append("{_}")
    return "".join(parts)


def _splices_an_identifier_in_an_fstring(source: str, pattern: re.Pattern[str]) -> bool:
    """True when the module builds SQL by interpolating a name into an **f-string**.

    Only ``ast.JoinedStr`` counts. A ``psycopg.sql.SQL("… FROM {table} …")`` template is a
    plain ``ast.Constant`` — same text, entirely different safety — and the driver composes it.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(
        pattern.search(_fstring_text(node))
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
    )


#: The shape of an ad-hoc SQL-identifier regex, in either spelling that was found in the tree.
_IDENTIFIER_PATTERN_SHAPE = re.compile(r"\[[Aa]-[Zz]_]\[[Aa]-[Zz]0-9_]\*")


def _compiles_an_identifier_pattern(source: str) -> bool:
    """True when the module calls ``re.compile`` on its own identifier pattern.

    AST-based on purpose: a comment quoting the retired regex — which several modules now
    carry, to explain what was wrong with it — is documentation, not a duplicate. A text grep
    cannot tell the two apart, and a ratchet that fires on its own explanation gets deleted.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_re_compile = isinstance(func, ast.Attribute) and func.attr == "compile"
        if not is_re_compile or not node.args:
            continue
        first = node.args[0]
        if (
            isinstance(first, ast.Constant)
            and isinstance(first.value, str)
            and _IDENTIFIER_PATTERN_SHAPE.search(first.value)
        ):
            return True
    return False
