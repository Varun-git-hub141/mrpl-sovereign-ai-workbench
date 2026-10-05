"""
Phase 4A Unit Tests — Decision and Governance Data Models
Verifies data models, enums, serialization, validation, and safety invariants.
"""

import json
import pytest
from datetime import datetime

from backend.services.decision.decision_models import (
    DecisionRiskLevel,
    GovernanceOutcome,
    PolicyEvaluationStatus,
    TemplateActionCode,
    PolicyActionTemplate,
    PolicyRule,
    StatutoryDecisionPolicy,
    RuleEvaluationResult,
    OperationalDecisionPackage,
)


def test_decision_risk_level_enum_values():
    """Verify all required DecisionRiskLevel enum values exist and match specification."""
    expected_values = {"LOW", "MEDIUM", "HIGH", "STATUTORY", "CRITICAL_SAFETY"}
    actual_values = {e.value for e in DecisionRiskLevel}
    assert actual_values == expected_values


def test_governance_outcome_enum_values():
    """Verify all required GovernanceOutcome enum values exist and match specification."""
    expected_values = {
        "PROCEED_ADVISORY",
        "PROCEED_WITH_CONDITIONS",
        "ESCALATE_HUMAN_REVIEW",
        "GOVERNANCE_GATE_BLOCKED",
    }
    actual_values = {e.value for e in GovernanceOutcome}
    assert actual_values == expected_values


def test_policy_evaluation_status_enum_values():
    """Verify all required PolicyEvaluationStatus enum values exist."""
    expected_values = {
        "NOT_EVALUATED",
        "POLICY_NOT_SUPPLIED",
        "CRITERIA_SATISFIED",
        "CRITERIA_BREACHED",
        "DATA_INSUFFICIENT_FOR_POLICY",
        "CONFLICT_PREVENTS_EVALUATION",
    }
    actual_values = {e.value for e in PolicyEvaluationStatus}
    assert actual_values == expected_values


def test_template_action_code_enum_values_and_safety():
    """Verify TemplateActionCode values, ensuring ENGINEERING_ASSESSMENT_REQUIRED is present."""
    expected_values = {
        "NO_ACTION_REQUIRED",
        "SCHEDULE_INSPECTION",
        "PERFORM_THICKNESS_SURVEY",
        "INITIATE_MOC",
        "CALIBRATE_INSTRUMENT",
        "REVISE_OPERATING_LIMITS",
        "ENGINEERING_ASSESSMENT_REQUIRED",
        "REQUIRES_ENGINEER_DISPOSITION",
    }
    actual_values = {e.value for e in TemplateActionCode}
    assert actual_values == expected_values

    # Strict invariant: ENGINEERING_FITNESS_EVALUATION must NOT exist
    assert "ENGINEERING_FITNESS_EVALUATION" not in actual_values
    assert not hasattr(TemplateActionCode, "ENGINEERING_FITNESS_EVALUATION")


def test_policy_action_template_construction():
    """Verify construction and validation of PolicyActionTemplate."""
    template = PolicyActionTemplate(
        action_code=TemplateActionCode.PERFORM_THICKNESS_SURVEY,
        action_title="Perform UT Thickness Survey",
        action_description="Execute 8-point ultrasonic thickness survey across TMLs.",
        mandatory_parameters={"grid_points": 8, "technique": "UT-A-SCAN"},
    )
    assert template.action_code == TemplateActionCode.PERFORM_THICKNESS_SURVEY
    assert template.action_title == "Perform UT Thickness Survey"
    assert template.mandatory_parameters["grid_points"] == 8


def test_policy_rule_construction():
    """Verify construction of PolicyRule including satisfied and breach action templates."""
    sat_template = PolicyActionTemplate(
        action_code=TemplateActionCode.NO_ACTION_REQUIRED,
        action_title="Continue Nominal Monitoring",
        action_description="No immediate intervention required.",
    )
    breach_template = PolicyActionTemplate(
        action_code=TemplateActionCode.ENGINEERING_ASSESSMENT_REQUIRED,
        action_title="Engineering Assessment for Thinning",
        action_description="Conduct Level 1 engineering review per plant standards.",
    )
    rule = PolicyRule(
        rule_id="RULE-CORR-01",
        rule_name="Minimum Measured Thickness Check",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=6.0,
        threshold_unit="mm",
        on_satisfied_template=sat_template,
        on_breach_template=breach_template,
    )
    assert rule.rule_id == "RULE-CORR-01"
    assert rule.operator == ">="
    assert rule.threshold_value == 6.0
    assert rule.on_satisfied_template.action_code == TemplateActionCode.NO_ACTION_REQUIRED
    assert rule.on_breach_template.action_code == TemplateActionCode.ENGINEERING_ASSESSMENT_REQUIRED


def test_statutory_decision_policy_defaults_and_no_hardcoded_roles():
    """Verify StatutoryDecisionPolicy model has no hardcoded roles or thresholds."""
    policy = StatutoryDecisionPolicy(
        policy_id="POL-OISD-142-2024",
        policy_name="OISD-142 Static Equipment Periodic Review Policy",
        policy_version="2024.1",
        issuing_authority="OISD",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.STATUTORY,
    )
    # required_human_roles must default to empty list, never hardcoded organizational roles
    assert policy.required_human_roles == []
    assert policy.rules == []
    assert policy.applicable_entity_types == []
    assert policy.provenance_lineage == {}
    assert policy.expiration_date is None


def test_rule_evaluation_result_construction():
    """Verify RuleEvaluationResult construction."""
    result = RuleEvaluationResult(
        rule_id="RULE-CORR-01",
        target_property="wall_thickness_mm",
        observed_value=5.4,
        threshold_value=6.0,
        operator=">=",
        satisfied=False,
        evaluation_notes="Observed thickness 5.4mm is below minimum threshold 6.0mm.",
    )
    assert result.rule_id == "RULE-CORR-01"
    assert not result.satisfied
    assert result.observed_value == 5.4


def test_operational_decision_package_construction_and_defaults():
    """Verify OperationalDecisionPackage construction, default empty roles, and audit fields."""
    pkg = OperationalDecisionPackage(
        package_id="PKG-2026-09-001",
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.HIGH,
        governance_outcome=GovernanceOutcome.ESCALATE_HUMAN_REVIEW,
        policy_evaluation_status=PolicyEvaluationStatus.CRITERIA_BREACHED,
        requires_human_approval=True,
        recommended_action="REQUIRES_ENGINEER_DISPOSITION",
        audit_trail_hash="a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
    )
    assert pkg.package_id == "PKG-2026-09-001"
    assert pkg.entity_tag == "11-V-101"
    assert pkg.risk_level == DecisionRiskLevel.HIGH
    assert pkg.governance_outcome == GovernanceOutcome.ESCALATE_HUMAN_REVIEW
    assert pkg.policy_evaluation_status == PolicyEvaluationStatus.CRITERIA_BREACHED
    assert pkg.requires_human_approval is True
    assert pkg.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"
    # required_human_roles must default to empty list, not hardcoded roles
    assert pkg.required_human_roles == []
    assert pkg.rule_evaluations == []
    assert pkg.provenance_source_spans == []
    assert isinstance(pkg.timestamp, datetime)


def test_operational_decision_package_json_serialization():
    """Verify serialization and deserialization roundtrip for OperationalDecisionPackage."""
    template = PolicyActionTemplate(
        action_code=TemplateActionCode.ENGINEERING_ASSESSMENT_REQUIRED,
        action_title="Engineering Assessment",
        action_description="Conduct engineering review",
    )
    rule_eval = RuleEvaluationResult(
        rule_id="R1",
        target_property="thickness",
        observed_value=4.5,
        threshold_value=5.0,
        operator=">=",
        satisfied=False,
        evaluation_notes="Breach",
    )
    pkg = OperationalDecisionPackage(
        package_id="PKG-002",
        entity_tag="PSV-201",
        risk_level=DecisionRiskLevel.STATUTORY,
        governance_outcome=GovernanceOutcome.GOVERNANCE_GATE_BLOCKED,
        policy_evaluation_status=PolicyEvaluationStatus.DATA_INSUFFICIENT_FOR_POLICY,
        applied_policy_id="POL-PSV-01",
        applied_policy_version="1.0",
        rule_evaluations=[rule_eval],
        recommended_action="ENGINEERING_ASSESSMENT_REQUIRED",
        action_template=template,
        requires_human_approval=True,
        required_human_roles=["Statutory_Inspector_Level_III"],
        approval_ticket_id="TICKET-7788",
        evidence_assessment_id="EA-101",
        reconciliation_report_id="REC-202",
        provenance_source_spans=[{"doc_id": "DOC-1", "span": "thickness: 4.5mm"}],
        audit_trail_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )

    json_str = pkg.model_dump_json()
    data = json.loads(json_str)

    assert data["package_id"] == "PKG-002"
    assert data["risk_level"] == "STATUTORY"
    assert data["governance_outcome"] == "GOVERNANCE_GATE_BLOCKED"
    assert data["recommended_action"] == "ENGINEERING_ASSESSMENT_REQUIRED"
    assert data["required_human_roles"] == ["Statutory_Inspector_Level_III"]

    # Deserialization test
    reconstructed = OperationalDecisionPackage.model_validate_json(json_str)
    assert reconstructed.package_id == pkg.package_id
    assert reconstructed.recommended_action == pkg.recommended_action
    assert reconstructed.rule_evaluations[0].rule_id == "R1"


def test_recommended_action_validator_rejects_freeform_ai_text():
    """Verify that arbitrary free-form strings in recommended_action raise ValueError."""
    # Valid options: None, REQUIRES_ENGINEER_DISPOSITION, or a valid TemplateActionCode value
    with pytest.raises(ValueError, match="Invalid recommended_action"):
        OperationalDecisionPackage(
            package_id="PKG-INVALID",
            entity_tag="11-V-101",
            risk_level=DecisionRiskLevel.LOW,
            governance_outcome=GovernanceOutcome.PROCEED_ADVISORY,
            policy_evaluation_status=PolicyEvaluationStatus.POLICY_NOT_SUPPLIED,
            requires_human_approval=False,
            recommended_action="I recommend replacing the vessel immediately because it looks unsafe.",
            audit_trail_hash="hash123",
        )


def test_forbidden_fields_absence():
    """Verify that forbidden safety/statutory/fitness-for-service fields do not exist on models."""
    forbidden_fields = [
        "fit_for_service",
        "is_safe",
        "statutorily_compliant",
        "statutory_approval",
        "safety_score",
        "authority_score",
        "confidence_score",
    ]
    for field in forbidden_fields:
        assert not hasattr(OperationalDecisionPackage, field), f"Forbidden field '{field}' exists on OperationalDecisionPackage!"
        assert not hasattr(StatutoryDecisionPolicy, field), f"Forbidden field '{field}' exists on StatutoryDecisionPolicy!"
        assert not hasattr(RuleEvaluationResult, field), f"Forbidden field '{field}' exists on RuleEvaluationResult!"
