"""The twelve components of the stack, each interrogated where it actually listens.

The operator's question, asked twice before it was understood: *"pourquoi les 12 composants
n'apparaissent pas sur `/fr/surveiller/observabilite`"*. The twelve are the **stack** — Redis,
ClickHouse, Postgres, MinIO and the rest — and the page showed none of them. It showed four KPI
cards over ``/healthz`` and ``/readyz``, two probes about the agent PROCESS.

:mod:`tessera.preflight` already interrogated four of the twelve, because its question is a
different one: *can this process serve a turn?* Grafana being down does not stop a turn, so it
has no business failing a boot gate — which is exactly why these live here and not there. Two
questions, two witnesses:

* preflight — **preconditions**. A FAIL means the agent cannot do its job.
* this module — **the stack**. A FAIL means something the operator runs is down, which they
  need to see, and which must not pretend the agent is broken.

**Declared, never discovered.** The list below is written out rather than read from Docker, and
that is a deliberate refusal of the easy version. Asking the daemon "what containers exist?"
answers a *neighbouring* question (ADR 0026): a container can be `Up` while the process inside
it refuses every connection, and a component can be missing entirely — the case a discovery
loop reports as "nothing wrong" because it never knew to look. A declared list goes RED when a
component disappears. That is the whole point.

Each entry is interrogated **by the protocol it speaks**, at an address resolved from the
environment with the compose default as fallback (the seam ``ClickHouseConfig`` learned on
2026-08-05). ``langfuse-worker`` publishes no host port at all: from outside the compose
network it is genuinely un-interrogable, and the honest answer there is BLIND — not "ok", and
not "down".
"""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from tessera.preflight import Check, Verdict
from tessera.settings import env_setting
from tessera.urlfetch import UnsupportedSchemeError, urlopen_http

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "STACK_COMPONENTS",
    "StackComponent",
    "StackObservation",
    "base_url_for",
    "component_for",
    "is_loopback",
    "probe_stack",
    "probe_stack_observations",
    "ui_url",
]

#: What a probe found, as a code rather than as a sentence.
#:
#: The sentence still exists — ``Check.detail`` carries it, and the preflight CLI prints it in a
#: terminal where English is the right answer. What did not exist was a machine-readable form,
#: so a French cockpit rendered *"postgres:5432 accepts connections"* verbatim under a French
#: heading. That string is not the machine talking; it is OUR prose, written here, and prose we
#: wrote can be translated. What the machine said — an errno, an HTTP status — is carried
#: separately in ``StackObservation.raw`` and is never rewritten.
StackOutcome = Literal[
    "accepted",  # tcp: the port took the connection
    "refused",  # tcp: the port answered, and said no
    "unresolved",  # the address does not resolve FROM HERE — a fact about the vantage point
    "http_ok",  # http: a response, with its status
    "http_error",  # http: a response, with a bad status
    "unreachable",  # http: no response at all
    "uninterrogable",  # the address cannot be probed by this prober (scheme, shape)
    "probe_failed",  # the probe itself broke — a blind spot, never a verdict about the thing
]

_TIMEOUT_S: Final = 3.0


@dataclass(frozen=True, slots=True)
class StackObservation:
    """What one probe saw: the verdict, the outcome as a CODE, and the machine's own words."""

    check: Check
    outcome: StackOutcome
    #: What was actually contacted — a host:port or a URL. An address, so never translated.
    address: str
    #: The machine's own text: an errno, an HTTP status, a scheme complaint. Empty when the
    #: probe simply succeeded and there was nothing for the machine to say. **Never rewritten**
    #: — the moment a surface paraphrases an errno it is reporting its own reading of the
    #: evidence as the evidence.
    raw: str


def _seen(
    component: StackComponent,
    verdict: Verdict,
    outcome: StackOutcome,
    address: str,
    sentence: str,
    *,
    raw: str = "",
) -> StackObservation:
    """One observation, carrying both the English sentence and its machine-readable form."""
    return StackObservation(
        check=Check(component.key, verdict, sentence), outcome=outcome, address=address, raw=raw
    )


@dataclass(frozen=True, slots=True)
class StackComponent:
    """One declared component of the deployed stack, and how to ask it directly."""

    key: str
    #: What it is, in the operator's words — never the container name, which is an artefact of
    #: the compose project and changes when the project is renamed.
    role: str
    #: ``TESSERA_STACK_<KEY>`` overrides the address; the default is the compose service name,
    #: which is what the agent container resolves.
    default_address: str
    kind: Literal["http", "tcp"]
    #: For ``http``: the path whose answer means "alive". Chosen per component, because
    #: ``/`` on Grafana is a 302 to a login page and proves only that a web server exists.
    path: str = ""
    #: Where an operator's BROWSER opens this component, when it has a UI worth opening.
    #: Deliberately not derived from ``default_address``: that address is resolved inside the
    #: compose network (``grafana:3000``) and means nothing to a browser, while the published
    #: port (``127.0.0.1:13000``) means nothing inside the network. Two vantage points, two
    #: addresses; conflating them is how a dashboard grows links to closed doors.
    #: ``TESSERA_STACK_UI_<KEY>`` overrides it; empty ⇒ this component has no UI and no link.
    default_ui: str = ""


#: The twelve. Ordered as an operator reads a stack: what the agent stores in, what it measures
#: with, what it traces into.
STACK_COMPONENTS: Final[tuple[StackComponent, ...]] = (
    StackComponent("postgres", "ledger + retrieval store", "postgres:5432", "tcp"),
    StackComponent("redis", "agent cache / rate limiting", "tessera-redis:6379", "tcp"),
    StackComponent(
        "clickhouse", "business events + online scores", "clickhouse:8123", "http", "/ping"
    ),
    StackComponent(
        "prometheus",
        "metrics the L-levels are computed from",
        "prometheus:9090",
        "http",
        "/-/healthy",
        # /targets, not /: the question an operator opens Prometheus with from this page is
        # "is it still scraping the agent?", and that page answers it in one screen.
        default_ui="http://127.0.0.1:19090/targets",
    ),
    StackComponent(
        "grafana",
        "metrics dashboards",
        "grafana:3000",
        "http",
        "/api/health",
        default_ui="http://127.0.0.1:13000",
    ),
    StackComponent(
        "otel-collector", "trace intake (OTLP)", "otel-collector:8888", "http", "/metrics"
    ),
    StackComponent(
        "phoenix",
        "trace viewer",
        "phoenix:6006",
        "http",
        "/healthz",
        default_ui="http://127.0.0.1:16006",
    ),
    StackComponent(
        "langfuse-web",
        "LLM observability UI",
        "langfuse-web:3000",
        "http",
        "/api/public/health",
        default_ui="http://127.0.0.1:3900",
    ),
    StackComponent("langfuse-worker", "LLM observability ingestion", "langfuse-worker:3030", "tcp"),
    StackComponent("langfuse-db", "Langfuse's own Postgres", "langfuse-db:5432", "tcp"),
    StackComponent("langfuse-redis", "Langfuse's own queue", "redis:6379", "tcp"),
    StackComponent(
        "minio",
        "trace blob storage (S3)",
        "minio:9000",
        "http",
        "/minio/health/live",
        # The CONSOLE (:9001 → 19101), not the S3 API (:9000 → 19100). Opening the API port in
        # a browser yields an XML error, which is a link that works and helps nobody.
        default_ui="http://127.0.0.1:19101",
    ),
)


def _address(component: StackComponent) -> str:
    """The configured address, or the compose default.

    Read from the environment for the same reason every other address in this codebase is: the
    deployed profile injects it, and a hard-coded service name would make this module true only
    inside one compose file. Resolved through the project's config seam, so the file an operator
    is told to configure reaches the probe as well as everything else.
    """
    key = f"TESSERA_STACK_{component.key.upper().replace('-', '_')}"
    return env_setting(key, component.default_address)


def component_for(key: str) -> StackComponent:
    """The declared component with this key.

    Args:
        key: A key from :data:`STACK_COMPONENTS`.

    Returns:
        The declaration.

    Raises:
        KeyError: When no component is declared under that key — a reader asking about a
            component nobody declared is a bug in the reader, never an address to guess.
    """
    for component in STACK_COMPONENTS:
        if component.key == key:
            return component
    raise KeyError(key)


def base_url_for(key: str, *, env: str = "") -> str:
    """Where a reader reaches this component — the component's ONE address.

    This exists because readers used to keep their own copy. ``langfuse_obs`` defaulted to
    ``http://localhost:3900`` — the address that works **on the host**, and refuses inside the
    container where the cockpit actually runs — while the probe two modules away asked
    ``langfuse-web:3000`` and got a 200. The page then said, of the same component and in the
    same breath, *"OK"* in the table and *"blamed"* in the consequences. Both witnesses were
    honest; they were interrogating two different addresses, and only one of them existed.

    Precedence: the tool's own variable when the caller names one (``LANGFUSE_HOST`` — the name
    its SDK and its documentation use, so a deployment configures it once), then
    ``TESSERA_STACK_<KEY>``, then the declared compose address. Every step goes through the same
    seam ``Settings`` uses, so ``.env.local`` reaches all of them.

    Args:
        key: A key from :data:`STACK_COMPONENTS`.
        env: Optional tool-conventional variable to honour first, e.g. ``"LANGFUSE_HOST"``.

    Returns:
        A base URL with a scheme and no trailing slash.

    Raises:
        KeyError: When ``key`` names no declared component.
        ValueError: When the component speaks TCP — it has no base URL, and inventing one
            would hand a caller a URL that cannot be fetched.
    """
    component = component_for(key)
    if component.kind != "http":
        msg = f"{key} is a {component.kind} component and has no base URL"
        raise ValueError(msg)
    override = env_setting(env, "") if env else ""
    address = override or f"http://{_address(component)}"
    if "://" not in address:
        address = f"http://{address}"
    return address.rstrip("/")


def ui_url(component: StackComponent) -> str:
    """Where a browser opens this component, or ``""`` when it has no UI.

    ``TESSERA_STACK_UI_<KEY>`` overrides the declared default, and setting it to an empty value
    removes the link — a deployment that publishes no ports should promise no doors. That last
    clause is why this reads ``os.environ`` directly rather than through ``env_setting``: here
    an empty value is a DECISION, not an unfilled placeholder.
    """
    key = f"TESSERA_STACK_UI_{component.key.upper().replace('-', '_')}"
    override = os.environ.get(key)
    return (override if override is not None else component.default_ui).strip()


def is_loopback(url: str) -> bool:
    """Whether ``url`` names the loopback interface — i.e. is only true *on the deployment host*.

    This is a fact about the URL, resolved here and **carried** to the browser rather than
    guessed there: the front cannot know that ``127.0.0.1:13000`` is Grafana-on-the-host and not
    Grafana-on-the-reader's-laptop, and a reader on ``tessera.example.com`` clicking a loopback
    link reaches whatever happens to run on *their* port 13000 — nothing, usually, and something
    else entirely at worst. The caller pairs it with its own vantage point before rendering a
    live link.
    """
    host = urllib.parse.urlsplit(url).hostname
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost" or host.endswith(".localhost")


def _probe_tcp(component: StackComponent, address: str) -> StackObservation:
    host, _, port = address.rpartition(":")
    if not host or not port.isdigit():
        return _seen(
            component,
            Verdict.BLIND,
            "uninterrogable",
            address,
            f"no host:port to interrogate — address is {address!r}",
            raw="",
        )
    try:
        with socket.create_connection((host, int(port)), timeout=_TIMEOUT_S):
            return _seen(
                component, Verdict.OK, "accepted", address, f"{address} accepts connections"
            )
    except socket.gaierror as exc:
        # Unresolvable is BLIND, not FAIL: from outside the compose network this name means
        # nothing, and "the probe cannot reach it from here" is not "the component is down".
        return _seen(
            component,
            Verdict.BLIND,
            "unresolved",
            address,
            f"{address} does not resolve from here: {exc}",
            raw=str(exc),
        )
    except OSError as exc:
        return _seen(
            component,
            Verdict.FAIL,
            "refused",
            address,
            f"{address} refused the connection: {exc}",
            raw=str(exc),
        )


def _probe_http(component: StackComponent, address: str) -> StackObservation:
    url = f"http://{address}{component.path}"
    try:
        with urlopen_http(url, timeout=_TIMEOUT_S) as response:
            return _seen(
                component,
                Verdict.OK,
                "http_ok",
                url,
                f"{url} -> HTTP {response.status}",
                raw=f"HTTP {response.status}",
            )
    except urllib.error.HTTPError as exc:
        return _seen(
            component,
            Verdict.FAIL,
            "http_error",
            url,
            f"{url} -> HTTP {exc.code}",
            raw=f"HTTP {exc.code}",
        )
    except UnsupportedSchemeError as exc:
        return _seen(
            component,
            Verdict.BLIND,
            "uninterrogable",
            url,
            f"cannot interrogate {url}: {exc}",
            raw=str(exc),
        )
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            return _seen(
                component,
                Verdict.BLIND,
                "unresolved",
                url,
                f"{url} does not resolve from here",
                raw=str(reason),
            )
        return _seen(
            component,
            Verdict.FAIL,
            "unreachable",
            url,
            f"{url} unreachable: {reason}",
            raw=str(reason),
        )
    except OSError as exc:
        return _seen(
            component, Verdict.FAIL, "unreachable", url, f"{url} unreachable: {exc}", raw=str(exc)
        )


def probe_stack(components: Sequence[StackComponent] | None = None) -> tuple[Check, ...]:
    """The checks alone — what the preflight CLI prints, unchanged."""
    return tuple(o.check for o in probe_stack_observations(components))


def probe_stack_observations(
    components: Sequence[StackComponent] | None = None,
) -> tuple[StackObservation, ...]:
    """Interrogate every declared component and report what each answered.

    An unexpected error inside a probe becomes BLIND rather than a verdict about the component,
    the same rule ``preflight._guard`` applies: a hole in the witness must never be reported as
    a fact about the thing.
    """
    seen: list[StackObservation] = []
    for component in components if components is not None else STACK_COMPONENTS:
        address = _address(component)
        try:
            probe = _probe_http if component.kind == "http" else _probe_tcp
            seen.append(probe(component, address))
        except Exception as exc:  # a broken probe is a blind spot, never a verdict about the thing
            seen.append(
                _seen(
                    component,
                    Verdict.BLIND,
                    "probe_failed",
                    address,
                    f"probe could not run: {type(exc).__name__}: {exc}",
                    raw=f"{type(exc).__name__}: {exc}",
                )
            )
    return tuple(seen)
