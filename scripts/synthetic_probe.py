#!/usr/bin/env python3
"""
Synthetic Probing Script
Pings the Tessera API periodically to ensure the LLM and retrieval layers are healthy.
Logs traces and scores to Langfuse to monitor uptime and latency.
"""

import os
import sys
import time
import uuid

import requests

try:
    from dotenv import load_dotenv

    load_dotenv(".env.local")
except ImportError:
    # Fallback basic parse if dotenv not installed
    if os.path.exists(".env.local"):
        with open(".env.local") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v.strip("\"'"))

from langfuse import Langfuse

# Configuration
API_URL = os.getenv("TESSERA_API_URL", "http://localhost:8099/chat")
AUTH_TOKEN = os.getenv(
    "TESSERA_BACKEND_TOKEN", "d7268eab2ba0e423a377cce76231db1be2570f3a647722dfb18b990deaf4a797"
)
PROBE_INTERVAL = int(os.getenv("PROBE_INTERVAL_SECONDS", "300"))  # 5 minutes
PROBE_MODEL = os.getenv("PROBE_MODEL", "llama3.3:70b")

if "LANGFUSE_PUBLIC_KEY" not in os.environ and "NEXT_PUBLIC_LANGFUSE_PUBLIC_KEY" in os.environ:
    os.environ["LANGFUSE_PUBLIC_KEY"] = os.environ["NEXT_PUBLIC_LANGFUSE_PUBLIC_KEY"]

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1234567890"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-1234567890"),
    host=os.getenv("LANGFUSE_HOST", "http://localhost:3080"),
)

from langfuse import get_client, observe, propagate_attributes


@observe(name="synthetic-probe")
def run_probe():
    trace_id = str(uuid.uuid4())
    session_id = f"probe_session_{int(time.time())}"

    propagate_attributes(session_id=session_id, tags=["synthetic", "probe", "monitoring"])

    start_time = time.time()
    payload = {
        "message": "Bonjour, ceci est un test de surveillance active. Quel est mon solde ?",
        "conversation_id": str(uuid.uuid4()),
        "language": "fr",
        "model": PROBE_MODEL,
    }

    headers = {"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}

    success = False
    error_msg = ""
    response_text = ""

    try:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sending synthetic probe...")
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data:"):
                    response_text += decoded + "\n"
        success = True
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Probe successful.")
    except Exception as e:
        success = False
        error_msg = str(e)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Probe failed: {error_msg}", file=sys.stderr)

    latency = time.time() - start_time

    import datetime
    gen_id = str(uuid.uuid4())
    ts = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    langfuse.api.ingestion.batch(batch=[{
        "id": str(uuid.uuid4()),
        "type": "generation-create",
        "timestamp": ts,
        "body": {
            "id": gen_id,
            "traceId": trace_id,
            "name": "llm_generation_mock",
            "startTime": ts,
            "model": PROBE_MODEL,
            "usage": {
                "input": 150,
                "output": 85,
                "unit": "TOKENS"
            }
        }
    }])
    langfuse.flush()

    # and we manually record the score.
    client = get_client()

    client.score_current_trace(
        name="probe-success",
        value=1.0 if success else 0.0,
        comment="Synthetic probe " + ("succeeded" if success else f"failed: {error_msg}"),
    )

    client.flush()
    return success


if __name__ == "__main__":
    print(f"Starting Synthetic Probing... Interval: {PROBE_INTERVAL}s")
    # Run once immediately, then loop if PROBE_INTERVAL > 0
    while True:
        run_probe()
        if PROBE_INTERVAL <= 0:
            break
        print(f"Waiting {PROBE_INTERVAL} seconds until next probe...")
        time.sleep(PROBE_INTERVAL)
