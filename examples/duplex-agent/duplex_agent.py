"""duplex-agent — the ADR 0019 §Amendment 1 A1.2 integration witness.

It speaks **both directions**, which is the claim no other example makes:

* ``hello-agent`` is observable but not invocable (0017 §F).
* ``turn-agent`` is invocable but not observable (0019 §I3).
* **duplex-agent** serves ``POST /turn`` *and* emits OTLP for the turns it serves, so the proof
  loop closes: invoking it produces the very turn evidence the cockpit reads to compute its level.

And it honours the **A1.1 propagation duty**: a turn arriving with ``"synthetic": true`` is a test
turn, and every span, metric and business event this agent emits for it says so. Nothing else can
say it — a ContextVar cannot cross a process boundary, which is why the flag is on the wire.

Zero tessera imports, on purpose, and the import-absence test enforces it. Every contract this file
depends on — the turn-result wire keys, the L1 span attribute names, the synthetic attribute, the
business-event envelope, the operator-assertion format — is **re-declared here by hand**, exactly as
a real second-runtime agent in another language would have to. That duplication IS the proof: a
foreign runtime onboards by *declaring*, never by importing the platform.

Run (obs stack up, collector on :4418; the cockpit invokes it under the declared binding):

    uv run python examples/duplex-agent/duplex_agent.py

Env: ``OTEL_EXPORTER_OTLP_ENDPOINT`` (default ``http://localhost:4418``), ``DUPLEX_AGENT_PORT``
(default 8501), ``DUPLEX_AGENT_OPERATOR_KEY`` (when set, the operator assertion is verified),
``DEPLOYMENT_ENVIRONMENT`` (default ``demo``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

AGENT_ID = "duplex-agent"
CAPABILITY_ID = "propose_schedule"
ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4418").rstrip("/")
ENVIRONMENT = os.environ.get("DEPLOYMENT_ENVIRONMENT", "demo")
PORT = int(os.environ.get("DUPLEX_AGENT_PORT", "8501"))
MODEL = "duplex-schedule-v1"

# The ADR 0018 TurnResult wire keys. Hard-coded, not imported — see the module docstring.
_TURN_RESULT_KEYS = (
    "visibleReply",
    "artifact",
    "cardUpdates",
    "suggestedActions",
    "businessEvents",
    "businessScores",
    "decisions",
)

# The L1 turn-span Scope-dimension contract (semconv.REQUIRED_TURN_SPAN_ATTRIBUTES) …
_ATTR_AGENT_ID = "tessera.agent_id"
_ATTR_LANGUAGE = "tessera.language"
_ATTR_CONVERSATION_ID = "gen_ai.conversation.id"
_ATTR_TURN_ID = "tessera.turn_id"
_ATTR_ENVIRONMENT = "deployment.environment"
_ATTR_MODEL = "gen_ai.request.model"
# … and the ADR 0019 §A1.1 synthetic dimension. Absent ⇒ false, so a product turn is never
# stamped and a test turn always is. This single attribute is the whole propagation duty.
_ATTR_SYNTHETIC = "tessera.synthetic"

# The ADR 0016 business-event envelope + the ADR 0017 workflow grammar, likewise re-declared.
_GRAMMAR_VERSION = "workflow_grammar.v1"
_SCHEMA_VERSION = "business_event.v1"
_EVENT_INTENT_ROUTED = "intent.routed"

_ASSERTION_HEADER = "x-tessera-operator-assertion"
_MAX_INSTALLMENTS = 24
_MIN_INSTALLMENTS = 2


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_assertion(header_value: str | None, key: str) -> bool:
    """Verify the operator assertion the cockpit forwards (ADR 0010 Phase B wire format).

    Re-implemented in stdlib rather than imported, for the same reason as everything else here.
    Only enforced when ``DUPLEX_AGENT_OPERATOR_KEY`` is set; a demo without the key still runs.
    """
    if not header_value or header_value.count(".") != 1:
        return False
    body, signature = header_value.split(".", 1)
    expected = hmac.new(key.encode(), body.encode(), hashlib.sha256).digest()
    try:
        presented = _b64d(signature)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, presented)


def _schedule(params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Compute the payment schedule the capability promises. Pure, deterministic, no LLM."""
    amount = float(params["outstanding_amount_eur"])
    count = int(params["installments"])
    if not _MIN_INSTALLMENTS <= count <= _MAX_INSTALLMENTS:
        msg = f"installments must be between {_MIN_INSTALLMENTS} and {_MAX_INSTALLMENTS}"
        raise ValueError(msg)
    monthly = round(amount / count, 2)
    last = round(amount - monthly * (count - 1), 2)
    reply = (
        f"Échéancier proposé : {count} mensualités de {monthly:.2f} € "
        f"(dernière : {last:.2f} €), à partir du {params['first_due_date']}."
    )
    artifact = {
        "type": "schedule_proposal",
        "installments": count,
        "monthly_amount_eur": monthly,
        "final_amount_eur": last,
        "first_due_date": params["first_due_date"],
        "channel": params.get("channel", "aucun"),
        "notify_customer": bool(params.get("notify_customer", False)),
    }
    return reply, artifact


def handle_turn(turn_input: dict[str, Any]) -> dict[str, Any]:
    """Serve one turn (ADR 0018 wire contract), returning every declared TurnResult key.

    Accepts either a typed ``action`` (the cockpit's generated capability form) or a free
    ``user_message``. The synthetic posture the platform declared rides through to the business
    event this turn emits — the duty, honoured where it is observable.
    """
    synthetic = bool(turn_input.get("synthetic", False))
    action = turn_input.get("action") or {}
    conversation_id = str(turn_input.get("conversation_id") or f"conv-{uuid.uuid4().hex[:8]}")
    turn_id = str(turn_input.get("turn_id") or f"turn-{uuid.uuid4().hex[:8]}")

    artifact: dict[str, Any] | None = None
    if action.get("type") == CAPABILITY_ID:
        reply, artifact = _schedule(dict(action.get("params") or {}))
    else:
        message = str(turn_input.get("user_message") or "")
        reply = (
            f"duplex-agent a reçu : {message!r}. Utilisez la capacité "
            f"« {CAPABILITY_ID} » pour obtenir un échéancier."
        )

    filled: dict[str, Any] = {
        "visibleReply": reply,
        "artifact": artifact,
        "cardUpdates": [],
        "suggestedActions": [],
        "businessEvents": [_business_event(conversation_id, turn_id, synthetic=synthetic)],
        "businessScores": [],
        "decisions": {},
    }
    # Built FROM the declared key tuple, so the response can never carry a key the contract does
    # not name, nor silently drop one the cockpit's conformance check requires.
    return {key: filled[key] for key in _TURN_RESULT_KEYS}


def _business_event(conversation_id: str, turn_id: str, *, synthetic: bool) -> dict[str, Any]:
    """One grammar-conformant envelope, stamped with the turn's declared posture (§A1.1)."""
    return {
        "event_name": _EVENT_INTENT_ROUTED,
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_id": AGENT_ID,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "schema_version": _SCHEMA_VERSION,
        "grammar_version": _GRAMMAR_VERSION,
        "capability_id": CAPABILITY_ID,
        "synthetic": synthetic,
    }


def emit_turn_telemetry(
    tracer: trace.Tracer,
    turns_counter: metrics.Counter,
    turn_input: dict[str, Any],
    *,
    outcome: str,
) -> None:
    """Emit the L1 turn span + the turn counter, both carrying the synthetic posture.

    The counter is what the collector re-exports as ``tessera_agent_turns_total{agent_id=…}`` —
    the exact fact the cockpit's resolver reads to award L1. Serving a turn therefore *produces*
    the evidence, which is the loop no previous example closed.
    """
    synthetic = bool(turn_input.get("synthetic", False))
    language = str(turn_input.get("language") or "fr")
    conversation_id = str(turn_input.get("conversation_id") or "conv-unknown")
    turn_id = str(turn_input.get("turn_id") or "turn-unknown")

    with tracer.start_as_current_span("invoke_agent") as span:
        span.set_attribute(_ATTR_AGENT_ID, AGENT_ID)
        span.set_attribute(_ATTR_LANGUAGE, language)
        span.set_attribute(_ATTR_CONVERSATION_ID, conversation_id)
        span.set_attribute(_ATTR_TURN_ID, turn_id)
        span.set_attribute(_ATTR_ENVIRONMENT, ENVIRONMENT)
        span.set_attribute(_ATTR_MODEL, MODEL)
        if synthetic:
            span.set_attribute(_ATTR_SYNTHETIC, True)

    turns_counter.add(
        1,
        {
            "agent_id": AGENT_ID,
            "language": language,
            "outcome": outcome,
            "synthetic": str(synthetic).lower(),
        },
    )


class _TurnHandler(BaseHTTPRequestHandler):
    tracer: trace.Tracer
    turns_counter: metrics.Counter

    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's dispatch name
        if self.path != "/turn":
            self._json(404, {"error": "not found"})
            return
        key = os.environ.get("DUPLEX_AGENT_OPERATOR_KEY")
        if key and not _verify_assertion(self.headers.get(_ASSERTION_HEADER), key):
            self._json(401, {"error": "operator assertion required"})
            return
        length = int(self.headers.get("content-length") or 0)
        try:
            turn_input = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        if not isinstance(turn_input, dict):
            self._json(400, {"error": "turn input must be an object"})
            return
        try:
            result = handle_turn(turn_input)
        except (KeyError, TypeError, ValueError) as exc:
            # An honest red for the cockpit: the invocation happened and failed, and the
            # telemetry says so. Never a fabricated green.
            emit_turn_telemetry(self.tracer, self.turns_counter, turn_input, outcome="error")
            self._json(400, {"error": f"{type(exc).__name__}: {exc}"})
            return
        emit_turn_telemetry(self.tracer, self.turns_counter, turn_input, outcome="answered")
        self._json(200, result)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"duplex-agent: {format % args}")


def _build_providers() -> tuple[TracerProvider, MeterProvider]:
    resource = Resource.create({"service.name": AGENT_ID, "deployment.environment": ENVIRONMENT})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{ENDPOINT}/v1/traces"))
    )
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{ENDPOINT}/v1/metrics"), export_interval_millis=2000
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    return tracer_provider, meter_provider


def main() -> None:
    """Serve POST /turn, emitting a turn span + turn counter for every turn served."""
    tracer_provider, meter_provider = _build_providers()
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)
    _TurnHandler.tracer = trace.get_tracer(AGENT_ID)
    _TurnHandler.turns_counter = meter_provider.get_meter(AGENT_ID).create_counter(
        "tessera_agent_turns", description="Agent turns processed.", unit="1"
    )
    server = HTTPServer(("127.0.0.1", PORT), _TurnHandler)
    guarded = "on" if os.environ.get("DUPLEX_AGENT_OPERATOR_KEY") else "off"
    print(f"duplex-agent: POST /turn on :{PORT} (assertion {guarded}) → OTLP {ENDPOINT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        tracer_provider.force_flush()
        meter_provider.force_flush()
        tracer_provider.shutdown()
        meter_provider.shutdown()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
