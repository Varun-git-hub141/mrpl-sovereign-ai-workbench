import logging
from typing import Dict, List, Any, Tuple
from backend.models.model_profile import ModelProfile, ModelHealthStatus
from backend.services.ollama_adapter import OllamaAdapter
from backend.services.hardware import HardwareDetector
from backend.services.registry import ModelRegistry

logger = logging.getLogger("mrpl.health")


class ModelHealthManager:
    """
    Assesses runtime health, reachability, hardware constraints, and operational eligibility
    of models registered in the workbench.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        adapter: OllamaAdapter,
    ):
        self.registry = registry
        self.adapter = adapter

    def perform_system_health_check(self) -> Dict[str, Any]:
        """
        Runs comprehensive system check: Ollama connectivity + Hardware telemetry + Model health evaluations.
        """
        ollama_health = self.adapter.check_health()
        hw_telemetry = HardwareDetector.get_hardware_telemetry()
        models = self.registry.get_all()

        model_health_results = {}
        for m in models:
            health_status, is_eligible, reason = self.evaluate_model_eligibility(m, hw_telemetry, ollama_health)
            # Update live health on profile
            self.registry.update_model_health(m.id, health_status, is_eligible)
            model_health_results[m.id] = {
                "ollama_name": m.ollama_name,
                "display_name": m.display_name,
                "status": health_status.value,
                "eligible": is_eligible,
                "reason": reason,
            }

        return {
            "ollama": ollama_health,
            "hardware": hw_telemetry,
            "models": model_health_results,
            "system_ready": ollama_health.get("reachable", False) and len(models) > 0,
        }

    def evaluate_model_eligibility(
        self,
        model: ModelProfile,
        hw_telemetry: Dict[str, Any],
        ollama_health: Dict[str, Any],
    ) -> Tuple[ModelHealthStatus, bool, str]:
        """
        Determines if a model can reasonably be invoked right now.
        Returns: (HealthStatus, IsEligible, StatusReason)
        """
        if not ollama_health.get("reachable", False):
            return (
                ModelHealthStatus.UNAVAILABLE,
                False,
                "Ollama server is unreachable. Check local Ollama daemon.",
            )

        if not model.availability:
            return (
                ModelHealthStatus.UNAVAILABLE,
                False,
                "Model is currently flagged unavailable in registry.",
            )

        # Check hardware limits
        est_vram = model.hardware.estimated_vram_gb
        fit_check = HardwareDetector.can_fit_model(est_vram)

        if not fit_check["can_run"]:
            return (
                ModelHealthStatus.RESOURCE_LIMITED,
                False,
                fit_check["reason"],
            )

        # Check recent failure rate
        if model.performance.total_calls >= 5 and model.performance.success_rate < 0.40:
            return (
                ModelHealthStatus.DEGRADED,
                True,
                f"Model degraded due to low success rate ({int(model.performance.success_rate * 100)}%).",
            )

        return (
            ModelHealthStatus.HEALTHY,
            True,
            f"Healthy — {fit_check['reason']}",
        )

    def get_eligible_models(self) -> List[ModelProfile]:
        """
        Returns list of healthy, eligible model profiles ready for routing.
        """
        ollama_health = self.adapter.check_health()
        hw_telemetry = HardwareDetector.get_hardware_telemetry()
        all_models = self.registry.get_all()

        eligible = []
        for m in all_models:
            status, is_eligible, _ = self.evaluate_model_eligibility(m, hw_telemetry, ollama_health)
            if is_eligible:
                eligible.append(m)

        return eligible
