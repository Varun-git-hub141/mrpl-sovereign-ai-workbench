import time
import logging
from typing import Dict, Any, List, Optional
from backend.models.routing_decision import RoutingDecision, CandidateEvaluation
from backend.services.ollama_adapter import OllamaAdapter
from backend.services.registry import ModelRegistry

logger = logging.getLogger("mrpl.fallback")


class FallbackManager:
    """
    Manages automatic, transparent model failover when primary execution encounters
    timeouts, CUDA out-of-memory errors, or runtime exceptions.
    Preserves full audit traceability of routed vs executed models and fallback reasons.
    """

    def __init__(self, adapter: OllamaAdapter, registry: ModelRegistry):
        self.adapter = adapter
        self.registry = registry

    def execute_with_fallback(
        self,
        decision: RoutingDecision,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Attempts execution on the primary selected model, and seamlessly falls back
        to the next eligible ranked candidate if execution fails.
        Records both routed_model and executed_model, fallback reason, and latency.
        """
        selected_primary = next((m for m in decision.selected_models if m.role == "primary"), None)
        if not selected_primary:
            return {
                "success": False,
                "error": "No primary model assigned in routing decision.",
                "routed_model": "none",
                "executed_model": "none",
                "fallback_triggered": False,
                "fallback_reason": None,
                "execution_trace": [],
            }

        execution_trace = []
        attempted_models = set()
        start_ts = time.time()

        # Step 1: Attempt Primary Selected Model
        primary_name = selected_primary.ollama_name
        attempted_models.add(primary_name)
        logger.info(f"Executing Primary Model: {primary_name}")

        p_t0 = time.time()
        result = self.adapter.generate(
            model=primary_name,
            prompt=prompt,
            system=system_prompt,
            images=images,
        )
        p_t1 = time.time()
        p_latency = result.get("latency_ms", round((p_t1 - p_t0) * 1000, 2))

        err_msg = str(result.get("error") or "")
        primary_success = result.get("success", False)

        # Categorize primary failure reason
        primary_fail_reason = None
        if not primary_success:
            err_lower = err_msg.lower()
            if "timed out" in err_lower or "timeout" in err_lower or "read timeout" in err_lower:
                primary_fail_reason = "timeout"
            elif "out of memory" in err_lower or "cuda" in err_lower or "vram" in err_lower:
                primary_fail_reason = "cuda_oom"
            elif "connection" in err_lower or "refused" in err_lower or "unreachable" in err_lower:
                primary_fail_reason = "connection_error"
            else:
                primary_fail_reason = "model_error"

        trace_entry = {
            "model": primary_name,
            "role": "primary",
            "success": primary_success,
            "latency_ms": p_latency,
            "error": result.get("error"),
            "failure_category": primary_fail_reason,
            "start_time": p_t0,
            "end_time": p_t1,
        }
        execution_trace.append(trace_entry)

        # Update registry metrics
        if self.registry:
            self.registry.record_execution(
                model_name_or_id=primary_name,
                latency_ms=p_latency,
                success=primary_success,
                task_type=decision.task.task_type.value,
            )

        if primary_success:
            return {
                "success": True,
                "routed_model": primary_name,
                "executed_model": primary_name,
                "model_used": primary_name,
                "response": result.get("response", ""),
                "latency_ms": p_latency,
                "fallback_triggered": False,
                "fallback_reason": None,
                "is_fallback": False,
                "start_timestamp": start_ts,
                "end_timestamp": p_t1,
                "execution_trace": execution_trace,
            }

        logger.warning(
            f"Primary model {primary_name} failed ({primary_fail_reason}): {result.get('error')}. "
            f"Initiating automatic fallback..."
        )

        # Step 2: Iterate through remaining ranked eligible candidates
        eligible_fallback_candidates = [
            c for c in decision.candidates
            if c.eligible and c.ollama_name not in attempted_models
        ]

        # Enforce vision constraint: if task has images, only consider fallback models with vision capability
        if images and len(images) > 0:
            def _candidate_supports_vision(name: str) -> bool:
                if "vl" in name.lower() or "vision" in name.lower():
                    return True
                if self.registry:
                    p = self.registry.get_by_name(name) or self.registry.get_by_id(name)
                    if p and p.capabilities.vision >= 0.5:
                        return True
                return False

            eligible_fallback_candidates = [
                c for c in eligible_fallback_candidates
                if _candidate_supports_vision(c.ollama_name)
            ]

        eligible_fallback_candidates.sort(key=lambda c: c.score, reverse=True)

        for candidate in eligible_fallback_candidates:
            fallback_name = candidate.ollama_name
            attempted_models.add(fallback_name)
            logger.info(f"Attempting Fallback Model: {fallback_name} (Candidate Score: {candidate.score})")

            fb_t0 = time.time()
            fallback_result = self.adapter.generate(
                model=fallback_name,
                prompt=prompt,
                system=system_prompt,
                images=images,
            )
            fb_t1 = time.time()
            fb_latency = fallback_result.get("latency_ms", round((fb_t1 - fb_t0) * 1000, 2))
            fb_success = fallback_result.get("success", False)

            fb_trace = {
                "model": fallback_name,
                "role": "fallback",
                "score": candidate.score,
                "success": fb_success,
                "latency_ms": fb_latency,
                "error": fallback_result.get("error"),
                "start_time": fb_t0,
                "end_time": fb_t1,
            }
            execution_trace.append(fb_trace)

            if self.registry:
                self.registry.record_execution(
                    model_name_or_id=fallback_name,
                    latency_ms=fb_latency,
                    success=fb_success,
                    task_type=decision.task.task_type.value,
                )

            if fb_success:
                total_latency = round((fb_t1 - start_ts) * 1000, 2)
                return {
                    "success": True,
                    "routed_model": primary_name,
                    "executed_model": fallback_name,
                    "model_used": fallback_name,
                    "response": fallback_result.get("response", ""),
                    "latency_ms": fb_latency,
                    "total_latency_ms": total_latency,
                    "fallback_triggered": True,
                    "fallback_reason": primary_fail_reason or "model_execution_failure",
                    "fallback_from": primary_name,
                    "is_fallback": True,
                    "start_timestamp": start_ts,
                    "end_timestamp": fb_t1,
                    "execution_trace": execution_trace,
                }

        return {
            "success": False,
            "routed_model": primary_name,
            "executed_model": primary_name,
            "fallback_triggered": True,
            "fallback_reason": primary_fail_reason or "all_models_failed",
            "error": "All eligible models failed execution.",
            "execution_trace": execution_trace,
        }
