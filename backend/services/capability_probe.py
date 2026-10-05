import time
import json
import logging
from typing import Dict, Any, List, Optional
from backend.models.model_profile import ModelProfile, CapabilitySource, CapabilityEntry
from backend.services.ollama_adapter import OllamaAdapter

logger = logging.getLogger("mrpl.probe")


class CapabilityProbeService:
    """
    Executes lightweight, synthetic, non-confidential probes on local models
    to empirically verify capability dimensions (reasoning, coding, math, tools, docs).
    """

    PROBES = {
        "reasoning": {
            "prompt": "If Pump P-101 has higher vibration than P-102, and P-103 has lower vibration than P-102, which pump has the lowest vibration? Answer in one word.",
            "validator": lambda res: "p-103" in res.lower() or "p103" in res.lower(),
            "target_dim": "reasoning",
        },
        "coding": {
            "prompt": "Write a Python function `add(a, b)` that returns their sum. Output ONLY valid Python code.",
            "validator": lambda res: "def add(" in res and "return" in res,
            "target_dim": "coding",
        },
        "mathematics": {
            "prompt": "Calculate (12.7 - 8.6) / 5.7. Return only the numeric value.",
            "validator": lambda res: "0.71" in res or "0.72" in res or "0.7" in res,
            "target_dim": "mathematics",
        },
        "tool_use": {
            "prompt": 'Respond with a valid JSON object containing keys "action": "inspect_valve" and "tag": "V-101". Do not write markdown.',
            "validator": lambda res: "inspect_valve" in res and "V-101" in res,
            "target_dim": "tool_use",
        },
        "document_understanding": {
            "prompt": "Extract the Tag and Status from this text: 'Equipment: P-101A | Status: Operational'. Return as Tag: <value>, Status: <value>.",
            "validator": lambda res: "p-101a" in res.lower() and "operational" in res.lower(),
            "target_dim": "document_understanding",
        },
    }

    def __init__(self, adapter: OllamaAdapter):
        self.adapter = adapter

    def probe_model(self, model: ModelProfile) -> Dict[str, Any]:
        """
        Runs synthetic probes against the model and updates capability evidence.
        Manual overrides are respected and never overwritten.
        """
        logger.info(f"Probing capabilities for {model.ollama_name}...")
        probe_results = {}
        model.last_probe = time.time()

        for probe_name, probe_info in self.PROBES.items():
            dim = probe_info["target_dim"]
            current_entry = getattr(model.capabilities, dim, None)

            # Do not overwrite manual overrides
            if current_entry and current_entry.source == CapabilitySource.MANUAL_OVERRIDE:
                logger.info(f"Skipping {dim} probe for {model.ollama_name}: manual override is authoritative.")
                probe_results[dim] = {
                    "score": current_entry.score,
                    "source": "manual_override (authoritative)",
                    "passed": True,
                }
                continue

            t0 = time.time()
            res = self.adapter.generate(
                model=model.ollama_name,
                prompt=probe_info["prompt"],
                options={"num_predict": 80, "temperature": 0.1},
            )
            elapsed_ms = round((time.time() - t0) * 1000, 2)

            response_text = res.get("response", "")
            passed = probe_info["validator"](response_text)

            # Score based on pass/fail and latency
            if passed:
                probe_score = 0.90 if elapsed_ms < 3000 else 0.80
            else:
                probe_score = 0.45 if res.get("success", False) else 0.20

            # Update capability entry with provenance
            new_entry = CapabilityEntry(
                score=probe_score,
                source=CapabilitySource.PROBE,
                last_updated=time.time(),
                evidence=f"Synthetic probe passed={passed} in {elapsed_ms}ms",
            )
            setattr(model.capabilities, dim, new_entry)

            probe_results[dim] = {
                "score": probe_score,
                "passed": passed,
                "latency_ms": elapsed_ms,
                "evidence": new_entry.evidence,
            }

        return {
            "model_id": model.id,
            "ollama_name": model.ollama_name,
            "probed_at": model.last_probe,
            "results": probe_results,
        }
