import requests
import json
import base64
import uuid
import random

auth = base64.b64encode(b"pk-lf-1234567890:sk-lf-1234567890").decode('utf-8')
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

# 1. Fetch recent traces to attach scores
resp = requests.get("http://localhost:3080/api/public/traces?limit=50", headers=headers)
data = resp.json()
traces = data.get("data", [])

if not traces:
    print("No traces found to attach scores.")
    exit(0)

# 2. Prepare scores ingestion
base_url = "http://localhost:3080/api/public/ingestion"
events = []

for trace in traces:
    trace_id = trace["id"]
    timestamp = trace["timestamp"]
    
    # 70% chance to have a Helpful score (0 to 1)
    if random.random() > 0.3:
        events.append({
            "type": "score-create",
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "body": {
                "id": str(uuid.uuid4()),
                "traceId": trace_id,
                "name": "Helpfulness",
                "value": random.choice([0.8, 0.9, 1.0, 0.5, 1.0]),
                "comment": "Auto-graded"
            }
        })
        
    # 30% chance to have User Feedback
    if random.random() > 0.7:
        events.append({
            "type": "score-create",
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "body": {
                "id": str(uuid.uuid4()),
                "traceId": trace_id,
                "name": "User Feedback",
                "value": random.choice([0, 1, 1, 1]), # mostly positive
                "comment": "User clicked thumbs up/down"
            }
        })

    # 100% chance to have a Guardrail / Threat Score
    events.append({
        "type": "score-create",
        "id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "body": {
            "id": str(uuid.uuid4()),
            "traceId": trace_id,
            "name": "Threat Score",
            "value": random.choice([0.0, 0.0, 0.0, 0.0, 0.1, 0.8]), # mostly safe
            "comment": "mcp-firewall check"
        }
    })

payload = {"batch": events}
resp = requests.post(base_url, json=payload, headers=headers)
print("Seeding scores status:", resp.status_code)
print(f"Pushed {len(events)} scores.")
