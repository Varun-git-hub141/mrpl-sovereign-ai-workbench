import urllib.request
import json

url = "http://127.0.0.1:8000/api/execute"
payload = json.dumps({
    "query": "Generate V-201 Inspection Review Note",
    "selected_model": "qwen2.5-coder:3b"
}).encode("utf-8")

req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    print("Keys in response:", list(res.keys()))
    print("generated_work_product:", res.get("generated_work_product"))
    print("deliverable_verification_receipt:", res.get("deliverable_verification_receipt"))
    print("is_verified_work_product:", res.get("is_verified_work_product"))
    print("detected_intent:", res.get("detected_intent"))
    print("inferred_output_format:", res.get("inferred_output_format"))
    print("context_mode:", res.get("context_mode"))
    print("tools_invoked:", res.get("tools_invoked"))
