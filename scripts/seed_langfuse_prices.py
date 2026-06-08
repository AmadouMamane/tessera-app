import requests
import json
import base64

auth = base64.b64encode(b"pk-lf-1234567890:sk-lf-1234567890").decode('utf-8')
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

models = [
    {
        "modelName": "llama3.2:3b",
        "matchPattern": "(?i).*llama3\\.2:3b.*",
        "startDate": "2024-01-01",
        "unit": "TOKENS",
        "inputPrice": 0.00005,
        "outputPrice": 0.00015,
        "tokenizerId": "openai"
    },
    {
        "modelName": "llama3.3:70b",
        "matchPattern": "(?i).*llama3\\.3:70b.*",
        "startDate": "2024-01-01",
        "unit": "TOKENS",
        "inputPrice": 0.0007,
        "outputPrice": 0.0009,
        "tokenizerId": "openai"
    },
    {
        "modelName": "gemma-3:27b",
        "matchPattern": "(?i).*gemma-3:27b.*",
        "startDate": "2024-01-01",
        "unit": "TOKENS",
        "inputPrice": 0.0003,
        "outputPrice": 0.0006,
        "tokenizerId": "openai"
    },
    {
        "modelName": "mistral:7b",
        "matchPattern": "(?i).*mistral:7b.*",
        "startDate": "2024-01-01",
        "unit": "TOKENS",
        "inputPrice": 0.0001,
        "outputPrice": 0.0002,
        "tokenizerId": "openai"
    },
    {
        "modelName": "deepseek-r1:7b",
        "matchPattern": "(?i).*deepseek-r1:7b.*",
        "startDate": "2024-01-01",
        "unit": "TOKENS",
        "inputPrice": 0.00014,
        "outputPrice": 0.00028,
        "tokenizerId": "openai"
    },
    {
        "modelName": "fake",
        "matchPattern": "(?i).*fake.*",
        "startDate": "2024-01-01",
        "unit": "TOKENS",
        "inputPrice": 0.00001,
        "outputPrice": 0.00001,
        "tokenizerId": "openai"
    }
]

for payload in models:
    resp = requests.post("http://localhost:3080/api/public/models", json=payload, headers=headers)
    print(f"{payload['modelName']} -> {resp.status_code}")
    if resp.status_code >= 400:
        print(resp.text)
