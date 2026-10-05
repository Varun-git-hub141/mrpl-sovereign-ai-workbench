import pytest
from backend.models.model_profile import (
    ModelProfile,
    CapabilityVector,
    HardwareRequirements,
    PerformanceStats,
    ModelHealthStatus,
)
from backend.models.task_profile import TaskProfile, TaskType, RiskLevel, InputModality
from backend.services.router import IntelligentModelRouter


class MockRegistry:
    def get_all(self):
        return [
            ModelProfile(
                id="model-coder",
                ollama_name="qwen2.5-coder:3b",
                display_name="Qwen 2.5 Coder 3B",
                family="qwen2",
                parameter_size="3.1B",
                quantization="Q4_K_M",
                context_length=32768,
                capabilities=CapabilityVector(
                    reasoning=0.85,
                    coding=0.96,
                    vision=0.05,
                    document_understanding=0.78,
                    mathematics=0.88,
                    ocr=0.05,
                    tool_use=0.85,
                    general=0.80,
                ),
                hardware=HardwareRequirements(estimated_vram_gb=2.8),
                performance=PerformanceStats(benchmark_score=0.88, latency_score=0.90),
                availability=True,
                health=ModelHealthStatus.HEALTHY,
            ),
            ModelProfile(
                id="model-reasoner",
                ollama_name="qwen3:4b",
                display_name="Qwen 3 4B",
                family="qwen3",
                parameter_size="4.0B",
                quantization="Q4_K_M",
                context_length=262144,
                capabilities=CapabilityVector(
                    reasoning=0.95,
                    coding=0.82,
                    vision=0.05,
                    document_understanding=0.92,
                    mathematics=0.90,
                    ocr=0.05,
                    tool_use=0.88,
                    general=0.94,
                ),
                hardware=HardwareRequirements(estimated_vram_gb=3.5),
                performance=PerformanceStats(benchmark_score=0.92, latency_score=0.75),
                availability=True,
                health=ModelHealthStatus.HEALTHY,
            ),
            ModelProfile(
                id="model-vision",
                ollama_name="qwen2.5vl:3b",
                display_name="Qwen 2.5-VL 3B",
                family="qwen25vl",
                parameter_size="3.8B",
                quantization="Q4_K_M",
                context_length=128000,
                capabilities=CapabilityVector(
                    reasoning=0.78,
                    coding=0.45,
                    vision=0.96,
                    document_understanding=0.94,
                    mathematics=0.75,
                    ocr=0.94,
                    tool_use=0.70,
                    general=0.82,
                ),
                hardware=HardwareRequirements(estimated_vram_gb=4.0),
                performance=PerformanceStats(benchmark_score=0.86, latency_score=0.70),
                availability=True,
                health=ModelHealthStatus.HEALTHY,
            ),
        ]

    def get_by_id(self, mid):
        for m in self.get_all():
            if m.id == mid:
                return m
        return None


class MockHealthManager:
    class MockAdapter:
        def check_health(self):
            return {"reachable": True, "status": "healthy"}
    adapter = MockAdapter()

    def evaluate_model_eligibility(self, model, hw, ollama):
        return (ModelHealthStatus.HEALTHY, True, "Healthy")


class HardwareConstrainedHealthManager(MockHealthManager):
    def evaluate_model_eligibility(self, model, hw, ollama):
        if "coder" in model.ollama_name:
            return (ModelHealthStatus.RESOURCE_LIMITED, False, "Insufficient available GPU memory for requested context (Requires 2.8 GB, 0.5 GB available).")
        return (ModelHealthStatus.HEALTHY, True, "Healthy")


def test_routing_general_reasoning_task():
    router = IntelligentModelRouter(
        registry=MockRegistry(),
        health_manager=MockHealthManager(),
    )

    task = TaskProfile(
        task_type=TaskType.GENERAL_REASONING,
        intent="general_knowledge_query",
        risk=RiskLevel.LOW,
        modality=InputModality.TEXT,
        required_capabilities=CapabilityVector(general=0.90, reasoning=0.85, document_understanding=0.60),
    )

    decision = router.route(task)

    assert len(decision.candidates) == 3
    assert len(decision.selected_models) == 1
    primary = decision.selected_models[0]
    assert primary.ollama_name == "qwen3:4b"


def test_routing_coding_task():
    router = IntelligentModelRouter(
        registry=MockRegistry(),
        health_manager=MockHealthManager(),
    )

    task = TaskProfile(
        task_type=TaskType.CODING,
        intent="write_python_script",
        risk=RiskLevel.LOW,
        modality=InputModality.SOURCE_CODE,
        required_capabilities=CapabilityVector(coding=0.95, reasoning=0.80, mathematics=0.80),
    )

    decision = router.route(task)

    assert len(decision.candidates) == 3
    assert len(decision.selected_models) == 1
    primary = decision.selected_models[0]
    assert primary.ollama_name == "qwen2.5-coder:3b"
    assert primary.role == "primary"


def test_routing_vision_task():
    router = IntelligentModelRouter(
        registry=MockRegistry(),
        health_manager=MockHealthManager(),
    )

    task = TaskProfile(
        task_type=TaskType.MULTIMODAL_DOCUMENT_ANALYSIS,
        intent="analyze_pid",
        risk=RiskLevel.MEDIUM,
        modality=InputModality.VISION,
        required_capabilities=CapabilityVector(vision=0.95, ocr=0.90, document_understanding=0.90, reasoning=0.70),
    )

    decision = router.route(task)

    primary = decision.selected_models[0]
    assert primary.ollama_name == "qwen2.5vl:3b"


def test_high_risk_multi_model_plan():
    router = IntelligentModelRouter(
        registry=MockRegistry(),
        health_manager=MockHealthManager(),
    )

    task = TaskProfile(
        task_type=TaskType.EQUIPMENT_APPROVAL,
        intent="evaluate_pump_approval",
        risk=RiskLevel.HIGH,
        requires_verification=True,
        modality=InputModality.TEXT,
        required_capabilities=CapabilityVector(reasoning=0.95, document_understanding=0.90, mathematics=0.85),
    )

    decision = router.route(task)

    assert decision.verification_required is True
    assert len(decision.selected_models) == 2
    roles = {m.role: m.ollama_name for m in decision.selected_models}
    assert "primary" in roles
    assert "independent_verifier" in roles
    assert roles["primary"] == "qwen3:4b"
    assert roles["independent_verifier"] in ["qwen2.5-coder:3b", "qwen2.5vl:3b"]


def test_ineligible_model_cannot_be_selected():
    """
    When a model is deemed ineligible due to insufficient VRAM / hardware constraints,
    it must be marked eligible=False with a descriptive rejection reason, and CANNOT be selected.
    """
    router = IntelligentModelRouter(
        registry=MockRegistry(),
        health_manager=HardwareConstrainedHealthManager(),
    )

    task = TaskProfile(
        task_type=TaskType.CODING,
        intent="write_python_script",
        risk=RiskLevel.LOW,
        modality=InputModality.SOURCE_CODE,
        required_capabilities=CapabilityVector(coding=0.95, reasoning=0.80),
    )

    decision = router.route(task)

    coder_eval = next(c for c in decision.candidates if "coder" in c.ollama_name)
    assert coder_eval.eligible is False
    assert "Insufficient available GPU memory" in coder_eval.rejection_reason

    # Coder cannot be selected even if it has highest raw capability match
    selected = decision.selected_models[0]
    assert selected.ollama_name != "qwen2.5-coder:3b"
    assert selected.ollama_name == "qwen3:4b"


def test_score_transparency_and_subscores():
    router = IntelligentModelRouter(
        registry=MockRegistry(),
        health_manager=MockHealthManager(),
    )

    task = TaskProfile(
        task_type=TaskType.ENGINEERING_CALCULATION,
        intent="calculate_corrosion",
        risk=RiskLevel.MEDIUM,
        required_capabilities=CapabilityVector(mathematics=0.95, coding=0.85, reasoning=0.75),
    )

    decision = router.route(task)

    for cand in decision.candidates:
        assert 0.0 <= cand.score <= 1.0
        sub = cand.subscores
        assert 0.0 <= sub.capability_match <= 1.0
        assert 0.0 <= sub.benchmark_score <= 1.0
        assert 0.0 <= sub.context_suitability <= 1.0
        assert 0.0 <= sub.hardware_suitability <= 1.0
        assert 0.0 <= sub.latency_score <= 1.0
        assert 0.0 <= sub.task_performance <= 1.0
        assert 0.0 <= sub.availability_score <= 1.0
