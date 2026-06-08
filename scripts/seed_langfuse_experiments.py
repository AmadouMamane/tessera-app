import os
import json
import base64
import requests
from pathlib import Path
from datetime import datetime
import uuid

auth = base64.b64encode(b"pk-lf-1234567890:sk-lf-1234567890").decode('utf-8')
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
base_url = "http://localhost:3080/api/public"

dataset_name = "tessera-regression-harness"

# 1. Create Dataset
requests.post(f"{base_url}/datasets", json={"name": dataset_name, "description": "Tessera Multi-lingual Failure Case Evaluation Harness"}, headers=headers)

failures_dir = Path("eval/failures")
cases = []
for file in failures_dir.glob("*.json"):
    if file.name == "_schema.json": continue
    with open(file, "r") as f:
        cases.append(json.load(f))

run_name_3b = f"Nightly-Llama3.2-3B-{datetime.now().strftime('%Y%m%d')}"
run_name_70b = f"Nightly-Llama3.3-70B-{datetime.now().strftime('%Y%m%d')}"

print("Pushing dataset items and generating experiment runs...")
events = []
run_items = []

for case in cases:
    for lang in case.get("languages", ["en"]):
        prompt = case["prompts"][lang]["user"]
        expected = case.get("expected_behavior", "")
        
        # Create dataset item
        resp = requests.post(f"{base_url}/dataset-items", json={
            "datasetName": dataset_name,
            "input": {"language": lang, "message": prompt},
            "expectedOutput": {"behavior": expected},
            "metadata": {"category": case.get("category"), "case_id": case.get("id")}
        }, headers=headers)
        
        if resp.status_code >= 400:
            print("Failed to create item:", resp.text)
            continue
            
        item_id = resp.json()["id"]
        
        # Trace for 3B
        trace_id_3b = str(uuid.uuid4())
        events.append({"type": "trace-create", "id": str(uuid.uuid4()), "timestamp": datetime.utcnow().isoformat() + "Z", "body": {"id": trace_id_3b, "name": "eval_run_3b"}})
        passed_3b = 1 if lang == "en" else 0
        events.append({"type": "score-create", "id": str(uuid.uuid4()), "timestamp": datetime.utcnow().isoformat() + "Z", "body": {"id": str(uuid.uuid4()), "traceId": trace_id_3b, "name": "Regression Pass", "value": passed_3b}})
        
        run_items.append({
            "datasetItemId": item_id,
            "runName": run_name_3b,
            "traceId": trace_id_3b
        })

        # Trace for 70B
        trace_id_70b = str(uuid.uuid4())
        events.append({"type": "trace-create", "id": str(uuid.uuid4()), "timestamp": datetime.utcnow().isoformat() + "Z", "body": {"id": trace_id_70b, "name": "eval_run_70b"}})
        passed_70b = 1
        events.append({"type": "score-create", "id": str(uuid.uuid4()), "timestamp": datetime.utcnow().isoformat() + "Z", "body": {"id": str(uuid.uuid4()), "traceId": trace_id_70b, "name": "Regression Pass", "value": passed_70b}})
        
        run_items.append({
            "datasetItemId": item_id,
            "runName": run_name_70b,
            "traceId": trace_id_70b
        })

# Submit traces and scores
requests.post(f"{base_url}/ingestion", json={"batch": events}, headers=headers)

# Submit run items
for r in run_items:
    requests.post(f"{base_url}/dataset-run-items", json=r, headers=headers)

print("Experiments seeded successfully!")
