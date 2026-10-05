import yaml
import logging
from typing import List, Dict, Any, Optional
from backend.config import ROUTING_WEIGHTS_FILE
from backend.models.model_profile import ModelProfile, CapabilityVector
from backend.models.task_profile import TaskProfile, RiskLevel
from backend.models.routing_decision import (
    RoutingDecision,
    CandidateEvaluation,
    CandidateSubscores,
    SelectedModelRole,
)
from backend.services.registry import ModelRegistry
from backend.services.health_manager import ModelHealthManager
from backend.services.policy_engine import PolicyEngine
from backend.services.hardware import HardwareDetector

logger = logging.getLogger("mrpl.router")


class IntelligentModelRouter:
    """
    Evaluates every registered model using dynamic multi-factor mathematical scoring.
    Produces comprehensive, auditable RoutingDecision objects.
    """

    DEFAULT_WEIGHTS = {
        "capability_match": 0.40,
        "benchmark_score": 0.15,
        "context_suitability": 0.10,
        "hardware_suitability": 0.10,
        "latency_score": 0.05,
        "task_performance": 0.08,
        "risk_compatibility": 0.07,
        "policy_compatibility": 0.05,
        "resource_penalty": 0.00,
    }

    def __init__(
        self,
        registry: ModelRegistry,
        health_manager: ModelHealthManager,
        policy_engine: Optional[PolicyEngine] = None,
    ):
        self.registry = registry
        self.health_manager = health_manager
        self.policy_engine = policy_engine or PolicyEngine()
        self.load_weights()

    def load_weights(self) -> Dict[str, float]:
        self.weights = dict(self.DEFAULT_WEIGHTS)
        if ROUTING_WEIGHTS_FILE.exists():
            try:
                with open(ROUTING_WEIGHTS_FILE, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    w_file = data.get("weights", {})
                    for k, v in w_file.items():
                        if k in self.weights:
                            self.weights[k] = float(v)
            except Exception as e:
                logger.error(f"Failed to load routing weights: {e}")
        return self.weights

    def route(self, task: TaskProfile) -> RoutingDecision:
        """
        Executes full routing evaluation over all registered models.
        """
        all_models = self.registry.get_all()
        if not all_models:
            all_models = self.registry.refresh_discovery()
        hw_telemetry = HardwareDetector.get_hardware_telemetry()
        ollama_health = self.health_manager.adapter.check_health()

        candidates: List[CandidateEvaluation] = []

        for model in all_models:
            eval_result = self._evaluate_candidate(model, task, hw_telemetry, ollama_health)
            candidates.append(eval_result)

        # Sort eligible candidates by score descending
        eligible_candidates = [c for c in candidates if c.eligible]
        eligible_candidates.sort(key=lambda c: c.score, reverse=True)

        selected_models: List[SelectedModelRole] = []
        verification_required = task.requires_verification or (task.risk == RiskLevel.HIGH)

        # Entity-First Guard: If an organization-specific entity is NOT FOUND in MRPL KB,
        # route strictly to MRPL_CONTEXT_GUARD with Primary Model: NONE.
        status_str = str(task.entity_resolution_status)
        if "NOT_FOUND_IN_KB" in status_str:
            import uuid
            selected_models = [
                SelectedModelRole(
                    model_id="MRPL_CONTEXT_GUARD",
                    ollama_name="NONE",
                    display_name="NONE (MRPL_CONTEXT_GUARD)",
                    role="primary",
                )
            ]
            reason = "Organization-specific entity was not found in the MRPL Local Knowledge Base."
            return RoutingDecision(
                request_id=task.request_id or f"req-{uuid.uuid4().hex[:8]}",
                task=task,
                required_capabilities=task.required_capabilities.to_dict(),
                candidates=candidates,
                selected_models=selected_models,
                verification_required=False,
                reason=reason,
                weights_used=self.weights,
                hardware_telemetry=hw_telemetry,
            )

        if not eligible_candidates:
            # Fallback if no candidate is eligible: pick least degraded model or return empty
            reason = "No fully eligible models found. Hardware or health constraints active."
            if candidates:
                # Force fallback to highest scoring candidate
                fallback = max(candidates, key=lambda c: c.score)
                selected_models.append(
                    SelectedModelRole(
                        model_id=fallback.model_id,
                        ollama_name=fallback.ollama_name,
                        display_name=fallback.display_name,
                        role="primary",
                    )
                )
                reason = f"Notice: Hardware constrained. Running best available fallback: {fallback.display_name}"
        else:
            primary_candidate = eligible_candidates[0]
            selected_models.append(
                SelectedModelRole(
                    model_id=primary_candidate.model_id,
                    ollama_name=primary_candidate.ollama_name,
                    display_name=primary_candidate.display_name,
                    role="primary",
                )
            )

            # For High-Risk tasks, select an Independent Verifier Model
            is_high_risk = (
                task.requires_verification
                or task.risk in (RiskLevel.HIGH, "high", "HIGH")
                or (hasattr(task.risk, "value") and task.risk.value == "high")
            )
            verification_required = is_high_risk

            if is_high_risk and len(eligible_candidates) > 1:
                verifier_candidate = None
                primary_model_profile = self.registry.get_by_id(primary_candidate.model_id) or self.registry.get_by_name(primary_candidate.ollama_name)
                primary_family = primary_model_profile.family if primary_model_profile else ""

                # Prefer candidate from different family if available, else next-best
                for cand in eligible_candidates[1:]:
                    cand_prof = self.registry.get_by_id(cand.model_id) or self.registry.get_by_name(cand.ollama_name)
                    cand_fam = cand_prof.family if cand_prof else ""
                    if cand_fam != primary_family and cand_fam != "":
                        verifier_candidate = cand
                        break

                if not verifier_candidate:
                    verifier_candidate = eligible_candidates[1]

                selected_models.append(
                    SelectedModelRole(
                        model_id=verifier_candidate.model_id,
                        ollama_name=verifier_candidate.ollama_name,
                        display_name=verifier_candidate.display_name,
                        role="independent_verifier",
                    )
                )
                reason = (
                    f"Selected {primary_candidate.display_name} as primary (Score: {primary_candidate.score:.2f}) "
                    f"and {verifier_candidate.display_name} as independent verifier due to HIGH risk protocol."
                )
            else:
                reason = (
                    f"Selected {primary_candidate.display_name} with highest composite score ({primary_candidate.score:.2f}) "
                    f"matching task requirements ({task.task_type.value})."
                )

        import uuid
        req_id = task.request_id or f"req-{uuid.uuid4().hex[:8]}"

        return RoutingDecision(
            request_id=req_id,
            task=task,
            required_capabilities=task.required_capabilities.to_dict(),
            candidates=candidates,
            selected_models=selected_models,
            verification_required=verification_required,
            reason=reason,
            local_only=True,
        )

    def _evaluate_candidate(
        self,
        model: ModelProfile,
        task: TaskProfile,
        hw_telemetry: Dict[str, Any],
        ollama_health: Dict[str, Any],
    ) -> CandidateEvaluation:
        """
        Calculates all subscores and composite score for a single model candidate.
        """
        # 1. Health & Hardware Eligibility Check
        health_status, is_eligible, rejection_reason = self.health_manager.evaluate_model_eligibility(
            model, hw_telemetry, ollama_health
        )

        # 2. Capability Match Score
        capability_match = self._calc_capability_match(model.capabilities, task.required_capabilities)

        # 3. Context Suitability
        context_suitability = self._calc_context_suitability(model.context_length, task.context_requirement)
        if context_suitability < 0.2:
            is_eligible = False
            rejection_reason = f"Context length ({model.context_length}) too small for task requirement ({task.context_requirement})"

        # 4. Hardware Suitability
        hardware_suitability = self._calc_hardware_suitability(model.hardware.estimated_vram_gb, hw_telemetry)

        # 5. Benchmark Score
        benchmark_score = model.performance.benchmark_score

        # 6. Latency Score
        latency_score = model.performance.latency_score

        # 7. Task Performance (historical reliability)
        task_performance = model.performance.success_rate

        # 8. Risk Compatibility
        risk_compatibility = self._calc_risk_compatibility(model, task.risk)

        # 9. Policy Adherence
        policy_result = self.policy_engine.evaluate_model_policy(model, task)
        policy_compatibility = policy_result["score"]
        if not policy_result["allowed"]:
            is_eligible = False
            rejection_reason = "; ".join(policy_result["reasons"])

        # 10. Availability Score
        availability_score = 1.0 if (model.availability and ollama_health.get("reachable", False)) else 0.0
        if not model.availability:
            is_eligible = False
            rejection_reason = "Model flagged unavailable in local registry"

        # 11. Resource Penalty
        resource_penalty = self._calc_resource_penalty(model, task)

        subscores = CandidateSubscores(
            capability_match=round(capability_match, 3),
            benchmark_score=round(benchmark_score, 3),
            context_suitability=round(context_suitability, 3),
            hardware_suitability=round(hardware_suitability, 3),
            latency_score=round(latency_score, 3),
            task_performance=round(task_performance, 3),
            risk_compatibility=round(risk_compatibility, 3),
            policy_compatibility=round(policy_compatibility, 3),
            availability_score=round(availability_score, 3),
            resource_penalty=round(resource_penalty, 3),
        )

        # Composite weighted scoring formula
        w = self.weights
        composite_score = (
            subscores.capability_match * w.get("capability_match", self.DEFAULT_WEIGHTS["capability_match"])
            + subscores.benchmark_score * w.get("benchmark_score", self.DEFAULT_WEIGHTS["benchmark_score"])
            + subscores.context_suitability * w.get("context_suitability", self.DEFAULT_WEIGHTS["context_suitability"])
            + subscores.hardware_suitability * w.get("hardware_suitability", self.DEFAULT_WEIGHTS["hardware_suitability"])
            + subscores.latency_score * w.get("latency_score", self.DEFAULT_WEIGHTS["latency_score"])
            + subscores.task_performance * w.get("task_performance", self.DEFAULT_WEIGHTS["task_performance"])
            + subscores.risk_compatibility * w.get("risk_compatibility", self.DEFAULT_WEIGHTS["risk_compatibility"])
            + subscores.policy_compatibility * w.get("policy_compatibility", self.DEFAULT_WEIGHTS["policy_compatibility"])
            + subscores.availability_score * w.get("availability_score", 0.0)
            - subscores.resource_penalty * w.get("resource_penalty", self.DEFAULT_WEIGHTS["resource_penalty"])
        )

        final_score = round(max(0.0, min(1.0, composite_score)), 3)

        return CandidateEvaluation(
            model_id=model.id,
            ollama_name=model.ollama_name,
            display_name=model.display_name,
            score=final_score,
            eligible=is_eligible,
            rejection_reason=rejection_reason if not is_eligible else None,
            subscores=subscores,
        )

    def _calc_capability_match(self, model_caps: CapabilityVector, task_caps: CapabilityVector) -> float:
        """
        Computes weighted capability match focusing specifically on high-demand task capabilities.
        """
        m_dict = model_caps.to_dict()
        t_dict = task_caps.to_dict()

        total_weight = 0.0
        weighted_score = 0.0

        for dim, task_val in t_dict.items():
            if task_val > 0.05:
                # Exponentiate high requirements so specialized needs dominate
                w = task_val ** 3.0
                model_val = m_dict.get(dim, 0.0)
                if task_val > 0.70:
                    match_val = (model_val / max(task_val, 0.01)) ** 2.0
                else:
                    match_val = min(1.0, model_val / max(task_val, 0.01))
                weighted_score += w * min(1.0, match_val)
                total_weight += w

        if total_weight == 0:
            return 0.70

        return weighted_score / total_weight

    def _calc_context_suitability(self, model_context: int, task_context: int) -> float:
        if model_context < task_context:
            return 0.0
        ratio = model_context / max(task_context, 1)
        if ratio >= 2.0:
            return 1.0
        return 0.5 + 0.5 * (ratio - 1.0)

    def _calc_hardware_suitability(self, est_vram: float, hw_telemetry: Dict[str, Any]) -> float:
        gpu = hw_telemetry.get("gpu", {})
        if gpu.get("available"):
            free_vram = gpu.get("free_vram_gb", 0.0)
            if free_vram >= est_vram:
                return 1.0
            elif gpu.get("total_vram_gb", 0.0) >= est_vram:
                return 0.85
        return 0.65  # CPU offload

    def _calc_risk_compatibility(self, model: ModelProfile, risk: RiskLevel) -> float:
        if risk == RiskLevel.HIGH:
            if model.capabilities.reasoning >= 0.88 and model.performance.benchmark_score >= 0.80:
                return 1.0
            elif model.capabilities.reasoning >= 0.75:
                return 0.75
            return 0.40
        elif risk == RiskLevel.MEDIUM:
            return 0.90
        else:  # LOW risk
            # Fast, lean models score highest on low-risk tasks
            if model.performance.latency_score >= 0.80:
                return 1.0
            return 0.85

    def _calc_resource_penalty(self, model: ModelProfile, task: TaskProfile) -> float:
        # Simple/low complexity task on large resource model receives slight penalty to conserve energy/VRAM
        if task.complexity < 0.3 and task.risk == RiskLevel.LOW:
            if model.hardware.estimated_vram_gb > 6.0:
                return 0.4
            elif model.hardware.estimated_vram_gb > 3.5:
                return 0.1
        return 0.0
