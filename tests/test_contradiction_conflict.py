import pytest
from backend.models.execution_plan import ExecutionPlan, ModelRoleAssignment, VerificationSpec
from backend.models.task_profile import RiskLevel
from backend.models.verification_result import (
    VerificationStatus,
    DeterministicStatus,
    CrossModelStatus,
)
from backend.services.verification_engine import VerificationEngine
from backend.services.confidence_engine import ConfidenceEngine


def test_contradiction_and_conflict_detection():
    engine = VerificationEngine()
    confidence_engine = ConfidenceEngine()

    plan = ExecutionPlan(
        request_id="req-test-conflict",
        risk=RiskLevel.HIGH,
        primary_model=ModelRoleAssignment(
            model_id="model-1",
            ollama_name="qwen2.5-coder:3b",
            display_name="Primary Coder",
            role="primary",
            architecture="qwen2",
        ),
        verifier_model=ModelRoleAssignment(
            model_id="model-2",
            ollama_name="qwen3:4b",
            display_name="Verifier Reasoner",
            role="independent_verifier",
            architecture="qwen3",
        ),
        verification_independence="HIGHER",
        verification_spec=VerificationSpec(
            cross_model="REQUIRED",
            deterministic="REQUIRED",
            contradiction_check="REQUIRED",
        ),
        human_approval_required=True,
    )

    prompt = "Calculate corrosion rate for thickness 12.7 mm reduced to 11.2 mm over 5.0 years."
    # Expected rate: (12.7 - 11.2)/5 = 0.30 mm/year
    primary_response = "The calculated corrosion rate for the piping section is 0.30 mm/year per API 570 guidelines."
    verifier_response = "Independent review calculates the corrosion rate as 0.45 mm/year with high acceleration."

    report = engine.verify(
        plan=plan,
        prompt=prompt,
        primary_response=primary_response,
        verifier_response=verifier_response,
    )

    # Verifier and deterministic calculator disagree quantitatively -> CONFLICT DETECTED
    assert report.cross_model is not None
    assert report.deterministic is not None
    assert report.deterministic_status == DeterministicStatus.CONFLICT
    assert report.deterministic.match is False
    assert report.deterministic.expected_value == 0.30
    assert report.deterministic.model_values == [0.30, 0.45]
    assert len(report.contradictions) > 0  # Discrepancy between verifier & formula detected
    assert report.status == VerificationStatus.CONTRADICTED
    assert report.human_review_required is True

    # Evaluate Confidence
    confidence = confidence_engine.evaluate_confidence(plan, report, primary_response)
    assert confidence["confidence_tier"] == "CONFLICT_DETECTED"
    assert confidence["deterministic_pass"] is False
    assert confidence["deterministic_status"] == "CONFLICT"
