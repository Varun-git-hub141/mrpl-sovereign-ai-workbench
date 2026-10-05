import pytest
from backend.services.discovery import ModelDiscoveryService
from backend.services.registry import ModelRegistry
from backend.services.health_manager import ModelHealthManager
from backend.services.task_analyzer import TaskAnalyzer
from backend.services.router import IntelligentModelRouter
from backend.services.execution_planner import ExecutionPlanner
from backend.models.task_profile import TaskType, RiskLevel, InputModality


class DynamicMockAdapter:
    def __init__(self, include_fourth_model=False):
        self.include_fourth_model = include_fourth_model

    def list_tags(self):
        models = [
            {
                "name": "qwen2.5-coder:3b",
                "digest": "f72c60cabf62",
                "size": 1929912626,
                "details": {"family": "qwen2", "parameter_size": "3.1B", "quantization_level": "Q4_K_M", "context_length": 32768},
                "capabilities": ["completion", "tools"],
            },
            {
                "name": "qwen3:4b",
                "digest": "359d7dd4bcda",
                "size": 2497293931,
                "details": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": "Q4_K_M", "context_length": 262144},
                "capabilities": ["completion", "tools", "thinking"],
            },
            {
                "name": "qwen2.5vl:3b",
                "digest": "fb90415cde1e",
                "size": 3200627168,
                "details": {"family": "qwen25vl", "parameter_size": "3.8B", "quantization_level": "Q4_K_M", "context_length": 128000},
                "capabilities": ["vision", "completion"],
            },
        ]
        if self.include_fourth_model:
            # Injecting a new 4th model: supercoder:7b
            models.append({
                "name": "supercoder:7b",
                "digest": "99a8b7c6d5e4",
                "size": 4800000000,
                "details": {"family": "supercoder", "parameter_size": "7.0B", "quantization_level": "Q4_K_M", "context_length": 65536},
                "capabilities": ["completion", "tools"],
            })
        return models

    def check_health(self):
        return {"reachable": True, "status": "healthy"}


def test_dynamic_fourth_model_discovery_and_routing():
    """
    CRITICAL TEST: Introducing a 4th synthetic model (supercoder:7b) with custom capability overrides
    MUST be automatically discovered, evaluated, and ranked by the Router WITHOUT ANY ROUTER SOURCE CODE CHANGES.
    """
    adapter = DynamicMockAdapter(include_fourth_model=True)
    discovery = ModelDiscoveryService(adapter=adapter)
    
    # Overrides for the new model can be configured externally
    overrides = {
        "supercoder:7b": {
            "display_name": "SuperCoder 7B High Precision",
            "capabilities": {
                "coding": 0.99,
                "reasoning": 0.92,
                "mathematics": 0.94,
            },
            "performance": {
                "benchmark_score": 0.96,
                "latency_score": 0.85,
            }
        }
    }
    
    profiles = discovery.discover_all_models(overrides=overrides)
    assert len(profiles) == 4
    supercoder = next(p for p in profiles if p.ollama_name == "supercoder:7b")
    assert supercoder.id.startswith("model-99a8b7c6")
    assert supercoder.capabilities.get_score("coding") == 0.99

    # Set up registry and router
    registry = ModelRegistry(discovery_service=discovery)
    registry._overrides = overrides
    registry.refresh_discovery()
    
    health_mgr = ModelHealthManager(registry=registry, adapter=adapter)
    router = IntelligentModelRouter(registry=registry, health_manager=health_mgr)
    planner = ExecutionPlanner(registry=registry)

    # Route a heavy coding task
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Write an advanced Python parser for refinery PID tag telemetry.")
    decision = router.route(task)
    plan = planner.create_execution_plan(task, decision)

    # The newly introduced 4th model must be evaluated and automatically selected as primary
    candidate_names = [c.ollama_name for c in decision.candidates]
    assert "supercoder:7b" in candidate_names
    assert decision.selected_models[0].ollama_name == "supercoder:7b"
    assert plan.primary_model.ollama_name == "supercoder:7b"
