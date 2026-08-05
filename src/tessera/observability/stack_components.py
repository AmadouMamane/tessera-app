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

import os
import socket
import urllib.error
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from tessera.preflight import Check, Verdict
from tessera.urlfetch import UnsupportedSchemeError, urlopen_http

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["STACK_COMPONENTS", "StackComponent", "probe_stack"]

_TIMEOUT_S: Final = 3.0


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
    ),
    StackComponent("grafana", "metrics dashboards", "grafana:3000", "http", "/api/health"),
    StackComponent(
        "otel-collector", "trace intake (OTLP)", "otel-collector:8888", "http", "/metrics"
    ),
    StackComponent("phoenix", "trace viewer", "phoenix:6006", "http", "/healthz"),
    StackComponent(
        "langfuse-web", "LLM observability UI", "langfuse-web:3000", "http", "/api/public/health"
    ),
    StackComponent("langfuse-worker", "LLM observability ingestion", "langfuse-worker:3030", "tcp"),
    StackComponent("langfuse-db", "Langfuse's own Postgres", "langfuse-db:5432", "tcp"),
    StackComponent("langfuse-redis", "Langfuse's own queue", "redis:6379", "tcp"),
    StackComponent("minio", "trace blob storage (S3)", "minio:9000", "http", "/minio/health/live"),
)


def _address(component: StackComponent) -> str:
    """The configured address, or the compose default.

    Read from the environment for the same reason every other address in this codebase is: the
    deployed profile injects it, and a hard-coded service name would make this module true only
    inside one compose file.
    """
    key = f"TESSERA_STACK_{component.key.upper().replace('-', '_')}"
    return os.environ.get(key) or component.default_address


def _probe_tcp(component: StackComponent, address: str) -> Check:
    host, _, port = address.rpartition(":")
    if not host or not port.isdigit():
        return Check(
            component.key,
            Verdict.BLIND,
            f"no host:port to interrogate — address is {address!r}",
        )
    try:
        with socket.create_connection((host, int(port)), timeout=_TIMEOUT_S):
            return Check(component.key, Verdict.OK, f"{address} accepts connections")
    except socket.gaierror as exc:
        # Unresolvable is BLIND, not FAIL: from outside the compose network this name means
        # nothing, and "the probe cannot reach it from here" is not "the component is down".
        return Check(component.key, Verdict.BLIND, f"{address} does not resolve from here: {exc}")
    except OSError as exc:
        return Check(component.key, Verdict.FAIL, f"{address} refused the connection: {exc}")


def _probe_http(component: StackComponent, address: str) -> Check:
    url = f"http://{address}{component.path}"
    try:
        with urlopen_http(url, timeout=_TIMEOUT_S) as response:
            return Check(component.key, Verdict.OK, f"{url} -> HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        return Check(component.key, Verdict.FAIL, f"{url} -> HTTP {exc.code}")
    except UnsupportedSchemeError as exc:
        return Check(component.key, Verdict.BLIND, f"cannot interrogate {url}: {exc}")
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            return Check(component.key, Verdict.BLIND, f"{url} does not resolve from here")
        return Check(component.key, Verdict.FAIL, f"{url} unreachable: {reason}")
    except OSError as exc:
        return Check(component.key, Verdict.FAIL, f"{url} unreachable: {exc}")


def probe_stack(components: Sequence[StackComponent] | None = None) -> tuple[Check, ...]:
    """Interrogate every declared component and report what each answered.

    An unexpected error inside a probe becomes BLIND rather than a verdict about the component,
    the same rule ``preflight._guard`` applies: a hole in the witness must never be reported as
    a fact about the thing.
    """
    checks: list[Check] = []
    for component in components if components is not None else STACK_COMPONENTS:
        address = _address(component)
        try:
            probe = _probe_http if component.kind == "http" else _probe_tcp
            checks.append(probe(component, address))
        except Exception as exc:  # a broken probe is a blind spot, never a verdict about the thing
            checks.append(
                Check(
                    component.key,
                    Verdict.BLIND,
                    f"probe could not run: {type(exc).__name__}: {exc}",
                )
            )
    return tuple(checks)
