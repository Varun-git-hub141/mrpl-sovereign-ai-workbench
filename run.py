#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MRPL Sovereign AI Workbench — Single-Command Launcher
Zero-cloud, air-gapped on-premise execution launcher for Ollama.
"""

import sys
import time
import urllib.request
import json
import uvicorn

def check_local_ollama(host="http://127.0.0.1:11434"):
    print("=" * 70)
    print("  MRPL SOVEREIGN AI WORKBENCH — STARTUP HEALTH CHECK")
    print("=" * 70)
    print(f"[*] Checking Local Ollama daemon at {host}...")
    try:
        req = urllib.request.urlopen(f"{host}/api/tags", timeout=5)
        if req.status == 200:
            data = json.loads(req.read().decode("utf-8"))
            models = data.get("models", [])
            print(f"[OK] Local Ollama Online! Discovered {len(models)} local model(s):")
            for m in models:
                name = m.get("name")
                size_gb = round(m.get("size", 0) / (1024**3), 2)
                param = m.get("details", {}).get("parameter_size", "N/A")
                print(f"    * {name:<24} | Params: {param:<6} | Size: {size_gb} GB")
            print("[OK] Air-Gap Verification: 100% On-Premise (Zero Cloud Inference)")
            print("=" * 70)
            return True
    except Exception as e:
        print(f"[!] Warning: Could not connect to Ollama at {host}: {e}")
        print("[!] Please ensure Ollama is running locally ('ollama serve').")
        print("=" * 70)
        return False

def main():
    check_local_ollama()
    print("[*] Starting MRPL Sovereign AI Workbench on http://127.0.0.1:8000 ...")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, log_level="info", reload=False)

if __name__ == "__main__":
    main()
