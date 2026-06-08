import requests
import json
import base64
import uuid
import random
import time
from datetime import datetime, timedelta

auth = base64.b64encode(b"pk-lf-1234567890:sk-lf-1234567890").decode('utf-8')
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

base_url = "http://localhost:3080/api/public/ingestion"
models = ["llama3.2:3b", "llama3.3:70b", "gemma-3:27b"]

def generate_events(num_traces=50):
    events = []
    now = datetime.utcnow()
    
    for i in range(num_traces):
        trace_id = str(uuid.uuid4())
        # distribute over the last 24 hours
        offset = timedelta(minutes=random.randint(0, 1440))
        timestamp = (now - offset).isoformat() + "Z"
        
        # 1. Create trace
        events.append({
            "type": "trace-create",
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "body": {
                "id": trace_id,
                "name": "chat_session_mock",
                "userId": random.choice(["user_A", "user_B", "user_C", "anonymous"]),
                "tags": ["synthetic", "historical-fill"]
            }
        })
        
        # 2. Create generation
        model = random.choice(models)
        inp_toks = random.randint(50, 400)
        out_toks = random.randint(20, 200)
        
        events.append({
            "type": "generation-create",
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "body": {
                "id": str(uuid.uuid4()),
                "traceId": trace_id,
                "name": "llm_generation",
                "model": model,
                "usage": {
                    "input": inp_toks,
                    "output": out_toks,
                    "unit": "TOKENS"
                }
            }
        })
    
    return events

payload = {"batch": generate_events(100)}
resp = requests.post(base_url, json=payload, headers=headers)
print("Seeding status:", resp.status_code)
print("Seeding body:", resp.text)
