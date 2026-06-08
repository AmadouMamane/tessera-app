import yaml
from pathlib import Path
import os
import base64
import requests

auth = base64.b64encode(b"pk-lf-1234567890:sk-lf-1234567890").decode('utf-8')
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

# Base URL for langfuse (we use the internal docker network or localhost depending on where we run)
base_url = "http://localhost:3080/api/public/prompts"

prompts_dir = Path("src/tessera/agent/prompts")
for prompt_file in prompts_dir.glob("*.yaml"):
    lang = prompt_file.stem
    with open(prompt_file, "r") as f:
        data = yaml.safe_load(f)
        
    for key, value in data.items():
        if isinstance(value, str):
            # Create or update prompt in Langfuse
            prompt_name = f"tessera_{lang}_{key}"
            payload = {
                "name": prompt_name,
                "prompt": value,
                "isActive": True,
                "labels": ["production", lang],
                "type": "text"
            }
            
            resp = requests.post(base_url, json=payload, headers=headers)
            print(f"Pushed {prompt_name}: {resp.status_code}")
            if resp.status_code >= 400:
                print(resp.text)
