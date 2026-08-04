"""Boot-time preflight: assert every declared input, or refuse — loudly (ADR 0026).

Three regressions in the on-prem cutover shared one shape: the container was
missing an input the process needed (the ``eval`` package, then the generated
``eval/reports/`` archive, then the operator-assertion key that lived only in
``.env.local``), and each time the application *hid* the gap behind a silent
degradation — ``{"available": false}``, an empty dashboard, a 401 — discovered
page by page by the operator instead of refused at boot. ``run_local.py`` had
masked all three because it ran from the repo with the developer's environment;
the container was the first thing to exercise the bare image path.

This module is the witness that turns each silent hole into one loud, checked
precondition. It interrogates *the thing itself* (ADR 0026): the eval archive by
calling the very loader the dashboards call, Postgres by the same ``ln.connect``
the ledger store uses, ClickHouse / Prometheus / Ollama by their own adapters —
never a neighbour (a directory that *exists* is not an archive that *loads*). A
check that cannot even attempt its observation reports a BLIND spot and the run
refuses to say "ok"; a dependency observed to be down is a FAIL, not blind.

The verdict IS the exit code, so a smoke-test or CI step reads one number:

* ``0`` — every input satisfied (OK/SKIP only).
* ``1`` — at least one FAIL (an input is observably missing or a dep is down).
* ``2`` — nothing failed, but at least one check was BLIND: the witness could
  not see everything, so it may not report "ok" (ADR 0026).

Modes:

* ``--image-only`` — only what the built image must *contain* (the eval package
  imports, the seed reports load, the app factory builds). No external services;
  this is the CI-time witness that would have caught the missing ``eval`` COPY.
* default — the image checks, the config checks (operator key), and the live
  dependencies (Postgres, ClickHouse, Prometheus, Ollama).
* ``--http BASE`` — additionally probe a running server's ``/healthz`` + ``/readyz``.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from tessera.urlfetch import UnsupportedSchemeError, urlopen_http

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "Check",
    "PreflightReport",
    "Verdict",
    "main",
    "run_preflight",
]


class Verdict(Enum):
    """One check's outcome.

    ``BLIND`` (the witness could not even attempt the observation) is deliberately
    distinct from ``FAIL`` (it observed, and the answer was bad) and never counts
    as clear — ADR 0026: a witness that cannot see may not report "ok".
    """

    OK = "ok"
    FAIL = "fail"
    BLIND = "blind"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class Check:
    """A single named precondition and what interrogating it found."""

    name: str
    verdict: Verdict
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """The full set of checks and the one question that matters: are we clear?"""

    checks: tuple[Check, ...]

    @property
    def failures(self) -> tuple[Check, ...]:
        """Checks that observed a bad answer (an input missing, a dep down)."""
        return tuple(c for c in self.checks if c.verdict is Verdict.FAIL)

    @property
    def blind(self) -> tuple[Check, ...]:
        """Checks the witness could not even attempt (a hole it must not paper over)."""
        return tuple(c for c in self.checks if c.verdict is Verdict.BLIND)

    @property
    def exit_code(self) -> int:
        """0 clear · 1 a FAIL · 2 only BLIND (saw a hole, never green over it)."""
        if self.failures:
            return 1
        if self.blind:
            return 2
        return 0


def _guard(name: str, probe: Callable[[], Check]) -> Check:
    """Run a probe; an *unexpected* error means the witness itself could not see.

    Each probe catches the failure it is looking for and returns ``FAIL``. Anything
    else escaping the probe is a hole in the witness, not a verdict about the thing —
    so it becomes ``BLIND``, never a comfortable ``OK`` and never a misattributed FAIL.
    """
    try:
        return probe()
    except Exception as exc:
        return Check(name, Verdict.BLIND, f"probe could not run: {type(exc).__name__}: {exc}")


def _redact_dsn(dsn: str) -> str:
    """A DSN with its password masked — a preflight prints its evidence, not secrets."""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", dsn)


# ── Image checks: what the built image must CONTAIN (no external services) ───────


def _check_eval_package() -> Check:
    """``import eval`` — the first-party package six observability modules need.

    The exact regression that killed the first container boot: the wheel shipped
    ``src/tessera`` but not ``eval/``, so ``import eval`` raised ModuleNotFoundError
    at startup. Interrogates the import itself, not the presence of a directory.
    """

    def probe() -> Check:
        import importlib

        try:
            # B307 fires here on a name, not on a call: our first-party package is literally
            # named `eval`, and bandit resolves the imported module's name against its
            # blacklist. There is no builtin eval() on this line — the marker below records a
            # false positive caused by the package name, and carries no prose after it,
            # because bandit reads everything following its marker as test ids.
            importlib.import_module("eval")  # nosec B307
            importlib.import_module("eval.runner")
        except ModuleNotFoundError as exc:
            return Check(
                "eval-package",
                Verdict.FAIL,
                f"the first-party 'eval' package is not importable ({exc}); the image did "
                "not ship eval/ (Dockerfile COPY eval, in builder AND runtime stages)",
            )
        return Check("eval-package", Verdict.OK, "import eval, import eval.runner")

    return _guard("eval-package", probe)


def _check_eval_reports() -> Check:
    """The ``llama3.2:3b`` catalogue archive the dashboards read.

    Calls ``load_eval_snapshot(None)`` — the very function ``agent_historique`` /
    ``agent_evaluations`` / ``control_signals`` call — so the check passes exactly
    when those pages will. A directory that merely *exists* is not interrogated; the
    loader's own "no usable report" refusal is what this catches.
    """

    def probe() -> Check:
        from tessera.observability.eval.report_paths import reports_write_dir
        from tessera.observability.eval_data import load_eval_snapshot

        try:
            snapshot = load_eval_snapshot(None)
        except FileNotFoundError as exc:
            return Check("eval-reports", Verdict.FAIL, str(exc))
        detail = (
            f"{snapshot.model} catalogue snapshot, {snapshot.total} cases "
            f"(version {snapshot.catalogue_version}) via {reports_write_dir()}"
        )
        return Check("eval-reports", Verdict.OK, detail)

    return _guard("eval-reports", probe)


def _check_app_factory() -> Check:
    """The FastAPI app actually builds — catches an import-time break before boot."""

    def probe() -> Check:
        from tessera.api.main import build_app

        try:
            app = build_app()
        except Exception as exc:
            return Check(
                "app-factory",
                Verdict.FAIL,
                f"build_app() raised {type(exc).__name__}: {exc}",
            )
        return Check("app-factory", Verdict.OK, f"build_app() ok, {len(app.routes)} routes")

    return _guard("app-factory", probe)


# ── Config checks ───────────────────────────────────────────────────────────────


def _check_operator_key() -> Check:
    """The operator-assertion signing key that the operator pages depend on.

    Absent, the BFF's signed assertion cannot be verified, so every operator surface
    (historique, agir, prouver) silently falls back to a 401 / customer widget. It
    must also *match* the front's key — a value this process cannot see — so the
    check asserts presence and states the coupling explicitly.
    """

    def probe() -> Check:
        from tessera.settings import get_settings

        key = get_settings().api.operator_assertion_signing_key
        if key is None or not key.get_secret_value():
            return Check(
                "operator-key",
                Verdict.FAIL,
                "TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY unset — operator pages will 401; "
                "it must be set and identical to the front's key",
            )
        return Check(
            "operator-key",
            Verdict.OK,
            "operator assertion signing key present (verify it matches the front's)",
        )

    return _guard("operator-key", probe)


# ── Dependency checks: the live services the process talks to ────────────────────


def _check_postgres() -> Check:
    """Postgres reachable via the same ``psycopg.connect`` the audit ledger store uses."""

    def probe() -> Check:
        import psycopg

        from tessera.settings import get_settings

        dsn = str(get_settings().postgres.dsn)
        try:
            conn = psycopg.connect(dsn, connect_timeout=2)
        except psycopg.Error as exc:
            return Check("postgres", Verdict.FAIL, f"unreachable: {type(exc).__name__}: {exc}")
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        return Check("postgres", Verdict.OK, _redact_dsn(dsn))

    return _guard("postgres", probe)


def _check_clickhouse() -> Check:
    """ClickHouse reachable via the adapter the online-score/business-event reads use."""

    def probe() -> Check:
        from tessera.observability.spine.adapters.base import SpineUnavailableError
        from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

        adapter = ClickHouseAdapter()
        try:
            adapter.execute("SELECT 1")
        except SpineUnavailableError as exc:
            return Check("clickhouse", Verdict.FAIL, str(exc))
        return Check("clickhouse", Verdict.OK, adapter.config.url)

    return _guard("clickhouse", probe)


def _check_prometheus() -> Check:
    """Prometheus reachable — its own ``/-/healthy`` endpoint, no error-swallowing.

    The turn-evidence read (the L1/L2 level badges) queries Prometheus; a down
    Prometheus is exactly what leaves cards stuck at "declared, no proof". The
    adapter's query path can return an empty list on error, so this witness hits
    Prometheus's canonical health endpoint directly for an unambiguous answer.
    """

    def probe() -> Check:
        from tessera.observability.spine.adapters.prometheus import PrometheusAdapter

        base = PrometheusAdapter().base_url
        url = base.rstrip("/") + "/-/healthy"
        try:
            with urlopen_http(url, timeout=2) as response:
                code = response.status
        except UnsupportedSchemeError as exc:
            return Check("prometheus", Verdict.FAIL, str(exc))
        except urllib.error.HTTPError as exc:
            return Check("prometheus", Verdict.FAIL, f"{url} -> HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return Check("prometheus", Verdict.FAIL, f"{base} unreachable: {exc}")
        return Check("prometheus", Verdict.OK, f"{base} -> HTTP {code}")

    return _guard("prometheus", probe)


def _check_ollama() -> Check:
    """The on-prem LLM backend reachable — skipped on the frontier (managed) profile."""

    def probe() -> Check:
        from tessera.settings import LLMProfile, get_settings

        settings = get_settings()
        if settings.resolved_llm_profile() is not LLMProfile.ON_PREM:
            return Check(
                "ollama",
                Verdict.SKIP,
                "frontier profile — the managed platform gates the LLM",
            )
        import ollama

        host = str(settings.ollama.host)
        try:
            ollama.Client(host=host).list()
        except Exception as exc:
            return Check("ollama", Verdict.FAIL, f"unreachable at {host}: {exc}")
        return Check("ollama", Verdict.OK, host)

    return _guard("ollama", probe)


# ── HTTP checks: probe a running server ──────────────────────────────────────────


def _check_http(base: str, path: str) -> Check:
    """A running server answers 200 at ``path`` (``/readyz`` 503 surfaces as FAIL).

    ``base`` is an operator flag, which is a reason to trust the *intent* and never a reason to
    skip checking the *value*: ``--base file:///etc/passwd`` would otherwise have preflight read
    a local file and report it as a healthy server. :func:`tessera.urlfetch.urlopen_http` is the
    gate; the ``UnsupportedSchemeError`` it raises surfaces as an ordinary FAIL, like any other
    unreachable target, because that is what it is.
    """
    name = f"http {path}"

    def probe() -> Check:
        url = base.rstrip("/") + path
        try:
            with urlopen_http(url, timeout=4) as response:
                code = response.status
        except UnsupportedSchemeError as exc:
            return Check(name, Verdict.FAIL, str(exc))
        except urllib.error.HTTPError as exc:
            return Check(name, Verdict.FAIL, f"{url} -> HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return Check(name, Verdict.FAIL, f"{url} unreachable: {exc}")
        return Check(name, Verdict.OK, f"{url} -> HTTP {code}")

    return _guard(name, probe)


# ── Orchestration ────────────────────────────────────────────────────────────────


def run_preflight(*, image_only: bool = False, http_base: str | None = None) -> PreflightReport:
    """Run the checks for the requested mode and return the collected verdict.

    Args:
        image_only: only the checks the built image must satisfy on its own (no
            external services) — the CI-time witness.
        http_base: when set, additionally probe that base URL's ``/healthz`` and
            ``/readyz``.

    Returns:
        The report; ``report.exit_code`` is the single number a caller acts on.
    """
    checks: list[Check] = [
        _check_eval_package(),
        _check_eval_reports(),
        _check_app_factory(),
    ]
    if not image_only:
        checks.extend(
            [
                _check_operator_key(),
                _check_postgres(),
                _check_clickhouse(),
                _check_prometheus(),
                _check_ollama(),
            ]
        )
    if http_base:
        checks.append(_check_http(http_base, "/healthz"))
        checks.append(_check_http(http_base, "/readyz"))
    return PreflightReport(tuple(checks))


_LABEL: dict[Verdict, str] = {
    Verdict.OK: "OK  ",
    Verdict.FAIL: "FAIL",
    Verdict.BLIND: "BLND",
    Verdict.SKIP: "SKIP",
}
_HEADLINE: dict[int, str] = {0: "CLEAR", 1: "FAIL", 2: "BLIND"}


def _render(report: PreflightReport) -> str:
    """A one-line-per-check table plus a headline verdict, for human eyes and logs."""
    width = max((len(c.name) for c in report.checks), default=0)
    lines = [f"  [{_LABEL[c.verdict]}] {c.name.ljust(width)}  {c.detail}" for c in report.checks]
    lines.append("")
    lines.append(
        f"preflight: {_HEADLINE[report.exit_code]} "
        f"({len(report.checks)} checks · {len(report.failures)} fail · {len(report.blind)} blind)"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Console entry point (``tessera-preflight``). Returns the report's exit code."""
    parser = argparse.ArgumentParser(
        prog="tessera-preflight",
        description="Assert every declared input, or refuse loudly (ADR 0026).",
    )
    parser.add_argument(
        "--image-only",
        action="store_true",
        help="only checks the built image must satisfy on its own (no external services)",
    )
    parser.add_argument(
        "--http",
        metavar="BASE",
        default=None,
        help="also probe a running server's /healthz and /readyz at BASE",
    )
    args = parser.parse_args(argv)
    report = run_preflight(image_only=args.image_only, http_base=args.http)
    sys.stdout.write(_render(report) + "\n")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
