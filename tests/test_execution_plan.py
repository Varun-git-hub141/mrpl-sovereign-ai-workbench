import pytest
from backend.services.execution_planner import ExecutionPlanner
from backend.services.registry import ModelRegistry
from backend.models.task_profile import TaskProfile, TaskType, RiskLevel, InputModality
from backend.models.routing_decision import RoutingDecision, SelectedModelRole, CandidateEvaluation, CandidateSubscores


class MockPlanRegistry:
    def get_by_id(self, mid):
        class MockP:
            def __init__(self, fid):
                self.family = fid
        if "coder" in mid:
            return MockP("qwen2")
        elif "reasoner" in mid:
            return MockP("qwen3")
        return MockP("qwen25vl")


def test_execution_plan_creation_high_risk():
    planner = ExecutionPlanner(registry=MockPlanRegistry())

    task = TaskProfile(
        task_type=TaskType.EQUIPMENT_APPROVAL,
        intent="pump_p101_approval",
        risk=RiskLevel.HIGH,
        modality=InputModality.TEXT,
        requires_verification=True,
    )

    decision = RoutingDecision(
        request_id="req-plan-1",
        task=task,
        selected_models=[
            SelectedModelRole(model_id="model-reasoner", ollama_name="qwen3:4b", role="primary", display_name="Qwen 3 4B"),
            SelectedModelRole(model_id="model-coder", ollama_name="qwen2.5-coder:3b", role="independent_verifier", display_name="Qwen Coder"),
        ],
        verification_required=True,
        candidates=[
            CandidateEvaluation(
                model_id="model-reasoner",
                ollama_name="qwen3:4b",
                score=0.92,
                eligible=True,
                subscores=CandidateSubscores(),
            ),
            CandidateEvaluation(
                model_id="model-coder",
                ollama_name="qwen2.5-coder:3b",
                score=0.85,
                eligible=True,
                subscores=CandidateSubscores(),
            ),
        ],
    )

    plan = planner.create_execution_plan(task, decision)

    assert plan.risk == RiskLevel.HIGH
    assert plan.primary_model.ollama_name == "qwen3:4b"
    assert plan.verifier_model is not None
    assert plan.verifier_model.ollama_name == "qwen2.5-coder:3b"
    assert plan.verification_spec.cross_model_required is True
    assert plan.verification_spec.cross_model == "REQUIRED"
    assert plan.human_approval_required is True
    assert plan.local_only is True
    # Distinct architectures: qwen3 vs qwen2 -> HIGHER independence
    assert plan.verification_independence == "HIGHER"
