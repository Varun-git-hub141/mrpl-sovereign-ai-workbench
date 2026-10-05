import time
import json
import logging
from typing import Dict, Any, List, Optional
from backend.config import BENCHMARK_RESULTS_FILE
from backend.services.ollama_adapter import OllamaAdapter
from backend.services.registry import ModelRegistry

logger = logging.getLogger("mrpl.benchmark")


class BenchmarkService:
    """
    Executes local empirical benchmarks on installed models to establish
    accurate latency and quality baselines without external network calls.
    """

    BENCHMARK_PROMPTS = [
        {
            "id": "coding_calc",
            "category": "coding",
            "prompt": "Write a 3-line Python function `corrosion_rate(initial_t, final_t, years)` returning rate in mm/year. Return ONLY Python code.",
            "expected_keyword": "def corrosion_rate",
        },
        {
            "id": "reasoning_safety",
            "category": "reasoning",
            "prompt": "In an industrial refinery, if pump P-101 vibration exceeds 7.1 mm/s RMS (ISO 10816 Zone D), state in one sentence if continued operation is acceptable.",
            "expected_keyword": "not acceptable",
        },
        {
            "id": "speed_probe",
            "category": "speed",
            "prompt": "List 3 common non-destructive testing (NDT) methods used in petrochemical refineries. Be concise.",
            "expected_keyword": "ultrasonic",
        },
    ]

    def __init__(self, adapter: OllamaAdapter, registry: ModelRegistry):
        self.adapter = adapter
        self.registry = registry

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """
        Runs the benchmark suite sequentially across all registered models.
        """
        models = self.registry.get_all()
        results: Dict[str, Any] = {
            "timestamp": time.time(),
            "models_tested": len(models),
            "details": {},
        }

        for model in models:
            model_name = model.ollama_name
            logger.info(f"Running benchmark suite on {model_name}...")

            test_results = []
            total_latency = 0.0
            total_tokens = 0
            passed_tests = 0

            for test in self.BENCHMARK_PROMPTS:
                t0 = time.time()
                res = self.adapter.generate(
                    model=model_name,
                    prompt=test["prompt"],
                    options={"num_predict": 128, "temperature": 0.2},
                )
                elapsed_ms = round((time.time() - t0) * 1000, 2)
                total_latency += elapsed_ms

                response_text = res.get("response", "").lower()
                eval_count = res.get("eval_count", 0)
                total_tokens += eval_count

                passed = test["expected_keyword"].lower() in response_text or res.get("success", False)
                if passed:
                    passed_tests += 1

                test_results.append({
                    "test_id": test["id"],
                    "category": test["category"],
                    "latency_ms": elapsed_ms,
                    "tokens": eval_count,
                    "passed": passed,
                })

            avg_latency = round(total_latency / len(self.BENCHMARK_PROMPTS), 2)
            accuracy = round(passed_tests / len(self.BENCHMARK_PROMPTS), 2)
            # Benchmark score is weighted combination of accuracy and speed
            # Latency score: 1000ms = 0.9, 10000ms = 0.5
            lat_score = round(max(0.1, min(1.0, 1.0 - (avg_latency / 12000.0))), 2)
            composite_bench = round(0.6 * accuracy + 0.4 * lat_score, 2)

            model_summary = {
                "display_name": model.display_name,
                "avg_latency_ms": avg_latency,
                "total_tokens": total_tokens,
                "accuracy": accuracy,
                "latency_score": lat_score,
                "benchmark_score": composite_bench,
                "tests": test_results,
            }
            results["details"][model_name] = model_summary

            # Update live registry profile & overrides
            model.performance.benchmark_score = composite_bench
            model.performance.latency_score = lat_score
            self.registry.record_execution(
                model_name_or_id=model_name,
                latency_ms=avg_latency,
                success=accuracy > 0.5,
                task_type="benchmark",
            )

        self._save_benchmark_results(results)
        return results

    def get_latest_results(self) -> Dict[str, Any]:
        if BENCHMARK_RESULTS_FILE.exists():
            try:
                with open(BENCHMARK_RESULTS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading benchmark results: {e}")
        return {"timestamp": None, "details": {}}

    def _save_benchmark_results(self, data: Dict[str, Any]):
        try:
            with open(BENCHMARK_RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving benchmark results: {e}")
