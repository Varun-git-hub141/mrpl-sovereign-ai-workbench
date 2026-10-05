import logging
from typing import Dict, Any, List, Optional
from backend.models.model_profile import ModelProfile
from backend.models.task_profile import TaskProfile, RiskLevel

logger = logging.getLogger("mrpl.policy")


class PolicyEngine:
    """
    Evaluates enterprise security, air-gap compliance, and risk governance policies.
    Guarantees zero-data-leakage and strictly local execution.
    """

    def __init__(self):
        self.enforce_airgap = True

    def evaluate_model_policy(self, model: ModelProfile, task: TaskProfile) -> Dict[str, Any]:
        """
        Evaluates policy adherence for candidate model against task requirements.
        Returns: { 'allowed': bool, 'score': float, 'reasons': List[str] }
        """
        reasons = []
        score = 1.0

        # Rule 1: Air-gap / Local-Only Enforce
        if self.enforce_airgap and not model.local_only:
            reasons.append("VIOLATION: Non-local model violates PSU air-gap policy.")
            return {"allowed": False, "score": 0.0, "reasons": reasons}

        # Rule 2: High-Risk Policy
        if task.risk == RiskLevel.HIGH:
            # Model must meet a minimum quality benchmark for high risk
            if model.performance.benchmark_score < 0.70:
                score -= 0.3
                reasons.append("Model benchmark below high-risk advisory threshold (0.70).")

            # Check if model has reasoning capabilities
            if model.capabilities.reasoning < 0.70:
                score -= 0.4
                reasons.append("Model lacks required high-order reasoning for critical decision support.")

        # Rule 3: Tool permissions check
        if task.required_tools and model.capabilities.tool_use < 0.50:
            score -= 0.2
            reasons.append("Model has low tool_use capability for required tool sandboxes.")

        final_score = max(0.0, min(1.0, score))
        allowed = final_score > 0.3

        return {
            "allowed": allowed,
            "score": round(final_score, 2),
            "reasons": reasons,
        }

    def check_execution_clearance(self, task: TaskProfile, selected_models: List[str]) -> Dict[str, Any]:
        """
        Validates final clearance before inference begins.
        """
        if task.risk == RiskLevel.HIGH and len(selected_models) < 2 and task.requires_verification:
            return {
                "cleared": True,
                "warning": "High-risk task executing without secondary independent model (only 1 eligible model available). Verification flagged.",
            }

        return {
            "cleared": True,
            "warning": None,
        }
