import pytest
from backend.services.orchestrator import ExecutionOrchestrator
from backend.services.fallback_manager import FallbackManager
from backend.models.execution_plan import ExecutionPlan, ModelRoleAssignment, VerificationSpec
from backend.models.task_profile import RiskLevel


class TrackingOllamaAdapter:
    def __init__(self):
        self.host = "http://127.0.0.1:11434"
        self.calls = []

    def generate(self, model, prompt, system=None, images=None, options=None):
        self.calls.append({"model": model, "prompt": prompt})
        return {
            "success": True,
            "model": model,
            "response": f"Response generated strictly by {model}",
            "latency_ms": 150.0,
            "eval_count": 45,
        }


def test_displayed_model_matches_actual_ollama_call():
    """
    CRITICAL TEST: Ensures that the model chosen by Router & Execution Plan
    is EXACTLY the model invoked by the Orchestrator via OllamaAdapter.
    Zero fake routing or silent substitution allowed.
    """
    adapter = TrackingOllamaAdapter()
    fallback_mgr = FallbackManager(adapter=adapter, registry=None)
    orchestrator = ExecutionOrchestrator(adapter=adapter, fallback_manager=fallback_mgr)

    target_model = "qwen2.5-coder:3b"
    plan = ExecutionPlan(
        request_id="req-integrity-test",
        risk=RiskLevel.LOW,
        primary_model=ModelRoleAssignment(
            model_id="model-coder",
            ollama_name=target_model,
            display_name="Qwen 2.5 Coder 3B",
            role="primary",
            architecture="qwen2",
        ),
        verification_spec=VerificationSpec(cross_model=False),
        human_approval_required=False,
    )

    result = orchestrator.execute_plan(plan=plan, prompt="Write a quick Python loop.")

    # 1. Result must report the exact model
    assert result["model_actually_executed"] == target_model
    assert result["primary_execution"]["model"] == target_model

    # 2. Adapter must have received the EXACT model tag
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["model"] == target_model
