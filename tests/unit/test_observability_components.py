"""The components surface reports what the probe saw, including that it could not see.

`/fr/surveiller/observabilite` rendered four KPI cards fed by `/healthz` and `/readyz` — two
probes about the agent process — and no component list at all, while its own contextual help
promised one ("commencez par la composante indisponible ou dégradée, puis lisez sa dernière
vérification"). On 2026-08-05 `tessera.preflight` reported ClickHouse FAIL and that page showed
everything operational, because nothing it rendered could go red for a dependency.

What is asserted here is the property that made the old page useless rather than merely thin:
a surface with two states cannot carry the third. ``blind`` — the probe could not look at all —
must reach the reader as itself, never folded into ``ok`` and never into ``fail``: the repairs
differ, and ADR 0026's rule is that a witness which cannot see may not report "ok".
"""

from __future__ import annotations

import asyncio

import pytest

from tessera.api.routes.observability import components as components_route
from tessera.preflight import Check, PreflightReport, Verdict


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """The route caches its probes; a leaked entry would make each test judge the last one's."""
    components_route._cache = None
    components_route._stack_cache = None


def _serve(report: PreflightReport, stack: tuple[Check, ...] = ()) -> dict[str, object]:
    """Serve the route with BOTH witnesses stubbed.

    The stack probe opens twelve real sockets. Left live, these tests would depend on the
    machine's network and on a compose project being up — a unit test that is red on a laptop
    and green in CI teaches nobody anything.
    """
    components_route._cache = None
    components_route._stack_cache = None
    original_preflight = components_route.run_preflight
    original_stack = components_route.probe_stack
    components_route.run_preflight = lambda **_: report  # type: ignore[assignment]
    components_route.probe_stack = lambda *_, **__: stack  # type: ignore[assignment]
    try:
        return asyncio.run(components_route.observability_components())
    finally:
        components_route.run_preflight = original_preflight  # type: ignore[assignment]
        components_route.probe_stack = original_stack  # type: ignore[assignment]


def _by_name(payload: dict[str, object], group: str) -> dict[str, dict[str, object]]:
    """Rows of one group, keyed by name.

    Keyed per GROUP on purpose: `postgres` legitimately appears twice — once as a stack
    component (does the port accept?) and once as a precondition (does the ledger's own
    `connect` succeed?). Those are different questions with different answers, and the morning
    of 2026-08-05 is the proof: ClickHouse's port was open while its credentials were refused.
    """
    return {
        str(c["name"]): c  # type: ignore[index]
        for c in payload["components"]  # type: ignore[union-attr]
        if c["group"] == group  # type: ignore[index]
    }


def test_a_clear_stack_says_clear_and_counts_itself() -> None:
    payload = _serve(
        PreflightReport(
            (
                Check("postgres", Verdict.OK, "postgresql://tessera:***@localhost:5432/tessera"),
                Check("clickhouse", Verdict.OK, "http://localhost:18123"),
            )
        )
    )
    assert payload["verdict"] == "clear"
    assert payload["counts"] == {
        "total": 2,
        "ok": 2,
        "fail": 0,
        "blind": 0,
        "stack_total": 0,
        "stack_ok": 0,
    }


def test_a_dependency_that_is_down_turns_the_headline_red() -> None:
    """The case that was live and invisible: ClickHouse 403 under a page showing all green."""
    payload = _serve(
        PreflightReport(
            (
                Check("postgres", Verdict.OK, "ok"),
                Check("clickhouse", Verdict.FAIL, "403 AUTHENTICATION_FAILED"),
            )
        )
    )
    assert payload["verdict"] == "fail"
    assert payload["counts"]["fail"] == 1
    listed = _by_name(payload, "precondition")
    assert listed["clickhouse"]["verdict"] == "fail"
    assert "403" in listed["clickhouse"]["detail"], "the probe's own evidence must reach the page"


def test_a_probe_that_could_not_look_is_neither_ok_nor_fail() -> None:
    """ADR 0026, as a payload assertion rather than a comment."""
    payload = _serve(
        PreflightReport(
            (
                Check("postgres", Verdict.OK, "ok"),
                Check("prometheus", Verdict.BLIND, "probe could not run: OSError"),
            )
        )
    )
    assert payload["verdict"] == "blind", "a blind check must not leave the headline clear"
    assert payload["counts"]["blind"] == 1
    assert payload["counts"]["fail"] == 0, "blind is not a failure of the thing"
    listed = _by_name(payload, "precondition")
    assert listed["prometheus"]["verdict"] == "blind"


def test_a_failure_outranks_a_blind_spot_in_the_headline() -> None:
    """Both present: the reader is told something is DOWN, which is the actionable one."""
    payload = _serve(
        PreflightReport(
            (
                Check("clickhouse", Verdict.FAIL, "down"),
                Check("prometheus", Verdict.BLIND, "could not run"),
            )
        )
    )
    assert payload["verdict"] == "fail"
    assert payload["counts"] == {
        "total": 2,
        "ok": 0,
        "fail": 1,
        "blind": 1,
        "stack_total": 0,
        "stack_ok": 0,
    }


def test_every_component_says_what_was_interrogated() -> None:
    """A verdict without its question is the shape of witness this repo keeps getting wrong."""
    payload = _serve(PreflightReport((Check("postgres", Verdict.OK, "ok"),)))
    entry = _by_name(payload, "precondition")["postgres"]
    assert entry["interrogates"], "a known check must name what it asked"
    assert "connect" in entry["interrogates"]


def test_an_unknown_check_gets_no_subtitle_rather_than_a_guessed_one() -> None:
    """Negative control: adding a probe must not silently attribute somebody else's question."""
    payload = _serve(PreflightReport((Check("brand-new-probe", Verdict.OK, "ok"),)))
    assert _by_name(payload, "precondition")["brand-new-probe"]["interrogates"] == ""


def test_the_published_instant_is_when_the_probe_ran_not_when_it_was_asked() -> None:
    """The cache is why this matters: a cached list that implies "now" misleads by omission."""
    report = PreflightReport((Check("postgres", Verdict.OK, "ok"),))
    first = _serve(report)
    components_route.run_preflight = lambda **_: report  # type: ignore[assignment]
    try:
        second = asyncio.run(components_route.observability_components())
    finally:
        components_route._cache = None
    assert (
        second["observed_at"] == first["observed_at"]
    ), "the second read was served from cache, so it must publish the FIRST probe's instant"


def test_one_component_can_carry_two_answers_without_them_being_confused() -> None:
    """The morning of 2026-08-05, as a payload: the port was open and the credentials refused.

    `postgres`/`clickhouse` appear in BOTH groups because two different questions are asked of
    them — "does the port accept?" and "does the adapter's own read succeed?". A surface that
    merged them into one row would have had to pick one answer, and either pick is a lie: the
    stack was up, and the agent could not read it.
    """
    payload = _serve(
        PreflightReport((Check("clickhouse", Verdict.FAIL, "403 AUTHENTICATION_FAILED"),)),
        stack=(Check("clickhouse", Verdict.OK, "clickhouse:8123/ping -> HTTP 200"),),
    )
    stack = _by_name(payload, "stack")["clickhouse"]
    precondition = _by_name(payload, "precondition")["clickhouse"]
    assert stack["verdict"] == "ok", "the component itself is up"
    assert precondition["verdict"] == "fail", "…and the agent still cannot read it"
    assert payload["verdict"] == "fail", "the headline must follow the failure, not the ok"
    assert payload["counts"]["stack_ok"] == 1, (  # type: ignore[index]
        "the stack's own count must not be dragged down by a precondition failure"
    )
