import requests
import json
import base64
import uuid
import random
from datetime import datetime, timedelta

auth = base64.b64encode(b"pk-lf-1234567890:sk-lf-1234567890").decode('utf-8')
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
base_url = "http://localhost:3080/api/public/ingestion"
models = ["llama3.2:3b", "llama3.3:70b", "gemma-3:27b"]

events = []
now = datetime.utcnow()

for i in range(50):
    trace_id = str(uuid.uuid4())
    offset = timedelta(minutes=random.randint(0, 1440))
    start_time = now - offset
    
    # Random latencies
    ttft_seconds = random.uniform(0.2, 1.5)  # Time to first token
    total_latency_seconds = random.uniform(1.5, 5.0)  # Total time
    
    completion_start = start_time + timedelta(seconds=ttft_seconds)
    end_time = start_time + timedelta(seconds=total_latency_seconds)

    events.append({
        "type": "trace-create",
        "id": str(uuid.uuid4()),
        "timestamp": start_time.isoformat() + "Z",
        "body": {
            "id": trace_id,
            "name": "chat_session_latency",
            "tags": ["synthetic", "latency-fill"]
        }
    })
    
    model = random.choice(models)
    
    events.append({
        "type": "generation-create",
        "id": str(uuid.uuid4()),
        "timestamp": start_time.isoformat() + "Z",
        "body": {
            "id": str(uuid.uuid4()),
            "traceId": trace_id,
            "name": "llm_generation",
            "model": model,
            "startTime": start_time.isoformat() + "Z",
            "completionStartTime": completion_start.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z",
            "usage": {
                "input": random.randint(50, 400),
                "output": random.randint(20, 200),
                "unit": "TOKENS"
            }
        }
    })

resp = requests.post(base_url, json={"batch": events}, headers=headers)
print("Latency seeding status:", resp.status_code)
print("Pushed 50 traces with end times.")
