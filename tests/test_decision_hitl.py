"""
Phase 4C Unit & Adversarial Safety Tests — Decision HITL & Deliverable Packaging
Approved Specification: v1.0.0-FINAL-CLARIFIED-R3

Verifies HumanApprovalManager integration, role resolution precedence,
approval state transitions, provenance preservation, and safety invariants.
"""

import pytest
from datetime import datetime

from backend.services.decision.decision_engine import DecisionEngine
from backend.services.decision.decision_hitl import (
    DecisionApprovalDeliverable,
    DecisionHITLManager,
)
from backend.services.decision.decision_models import (
    DecisionRiskLevel,
    GovernanceOutcome,
    OperationalDecisionPackage,
    PolicyActionTemplate,
    PolicyEvaluationStatus,
    PolicyRule,
    RuleEvaluationResult,
    StatutoryDecisionPolicy,
    TemplateActionCode,
)
from backend.services.human_approval import (
    ApprovalItem,
    HumanApprovalManager,
    HumanApprovalState,
)


@pytest.fixture
def approval_manager():
    return HumanApprovalManager()


@pytest.fixture
def hitl_manager(approval_manager):
    return DecisionHITLManager(approval_manager=approval_manager)


@pytest.fixture
def sample_decision_package():
    return OperationalDecisionPackage(
        package_id="PKG-HITL-001",
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.HIGH,
        governance_outcome=GovernanceOutcome.ESCALATE_HUMAN_REVIEW,
        policy_evaluation_status=PolicyEvaluationStatus.CRITERIA_BREACHED,
        applied_policy_id="POL-OISD-142",
        applied_policy_version="2024.1",
        rule_evaluations=[
            RuleEvaluationResult(
                rule_id="R-01",
                target_property="wall_thickness_mm",
                observed_value=5.2,
                threshold_value=6.0,
                operator=">=",
                satisfied=False,
                evaluation_notes="Measured 5.2mm is below minimum required 6.0mm.",
            )
        ],
        recommended_action="ENGINEERING_ASSESSMENT_REQUIRED",
        requires_human_approval=True,
        required_human_roles=["Statutory_Inspector_Level_III"],
        evidence_assessment_id="EA-TASK-100",
        reconciliation_report_id="REC-TASK-200",
        provenance_source_spans=[
            {
                "observation_id": "OBS-001",
                "raw_source_document": "11-V-101_UT.json",
                "verbatim_source_span": "Thickness 5.2mm",
            }
        ],
        audit_trail_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )


# ─────────────────────────────────────────────────────────────
# 1. HITL Registration & State Management Tests
# ─────────────────────────────────────────────────────────────

def test_escalate_human_review_creates_hitl_ticket(hitl_manager, sample_decision_package):
    """Verify ESCALATE_HUMAN_REVIEW registers item in HumanApprovalManager with PENDING_REVIEW."""
    deliverable = hitl_manager.create_approval_package(sample_decision_package)

    assert deliverable.requires_human_approval is True
    assert deliverable.approval_state == HumanApprovalState.PENDING_REVIEW
    assert deliverable.approval_ticket_id is not None

    # Confirm item in HumanApprovalManager
    registered_item = hitl_manager.approval_manager.get_item(deliverable.approval_ticket_id)
    assert registered_item is not None
    assert registered_item.state == HumanApprovalState.PENDING_REVIEW
    assert registered_item.risk == DecisionRiskLevel.HIGH.value


def test_governance_gate_blocked_creates_human_review_workflow(hitl_manager, sample_decision_package):
    """Verify GOVERNANCE_GATE_BLOCKED creates human review workflow and flags contested evidence."""
    blocked_pkg = sample_decision_package.model_copy(
        update={
            "governance_outcome": GovernanceOutcome.GOVERNANCE_GATE_BLOCKED,
            "policy_evaluation_status": PolicyEvaluationStatus.CONFLICT_PREVENTS_EVALUATION,
            "recommended_action": "REQUIRES_ENGINEER_DISPOSITION",
        }
    )
    deliverable = hitl_manager.create_approval_package(blocked_pkg)

    assert deliverable.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert deliverable.requires_human_approval is True
    assert deliverable.approval_state == HumanApprovalState.PENDING_REVIEW
    assert deliverable.has_contested_evidence is True
    assert len(deliverable.contested_evidence_details) > 0


def test_low_risk_proceed_advisory_does_not_create_mandatory_hitl(hitl_manager, sample_decision_package):
    """Verify LOW risk PROCEED_ADVISORY sets approval_state to NOT_REQUIRED."""
    advisory_pkg = sample_decision_package.model_copy(
        update={
            "risk_level": DecisionRiskLevel.LOW,
            "governance_outcome": GovernanceOutcome.PROCEED_ADVISORY,
            "policy_evaluation_status": PolicyEvaluationStatus.POLICY_NOT_SUPPLIED,
            "requires_human_approval": False,
            "recommended_action": None,
        }
    )
    deliverable = hitl_manager.create_approval_package(advisory_pkg)

    assert deliverable.requires_human_approval is False
    assert deliverable.approval_state == HumanApprovalState.NOT_REQUIRED


def test_proceed_with_conditions_semantics(hitl_manager, sample_decision_package):
    """Verify PROCEED_WITH_CONDITIONS preserves HITL requirement when risk is HIGH."""
    cond_pkg = sample_decision_package.model_copy(
        update={
            "risk_level": DecisionRiskLevel.HIGH,
            "governance_outcome": GovernanceOutcome.PROCEED_WITH_CONDITIONS,
            "policy_evaluation_status": PolicyEvaluationStatus.CRITERIA_SATISFIED,
            "requires_human_approval": True,
            "recommended_action": "PERFORM_THICKNESS_SURVEY",
        }
    )
    deliverable = hitl_manager.create_approval_package(cond_pkg)

    assert deliverable.governance_outcome == GovernanceOutcome.PROCEED_WITH_CONDITIONS
    assert deliverable.requires_human_approval is True
    assert deliverable.approval_state == HumanApprovalState.PENDING_REVIEW


# ─────────────────────────────────────────────────────────────
# 2. Role Resolution Precedence Tests
# ─────────────────────────────────────────────────────────────

def test_role_resolution_tier1_policy_roles_preferred(hitl_manager, sample_decision_package):
    """Verify Tier 1: package/policy roles take precedence over external configs."""
    ext_config = {DecisionRiskLevel.HIGH.value: ["External_Config_Role"]}
    mgr_config = ["Manager_Config_Role"]

    deliverable = hitl_manager.create_approval_package(
        sample_decision_package,
        external_role_config=ext_config,
        manager_role_config=mgr_config,
    )
    # Must use package role: Statutory_Inspector_Level_III
    assert deliverable.required_human_roles == ["Statutory_Inspector_Level_III"]


def test_role_resolution_tier2_external_config_used_if_no_package_roles(hitl_manager, sample_decision_package):
    """Verify Tier 2: external HITL config used when package has empty roles."""
    pkg_no_roles = sample_decision_package.model_copy(update={"required_human_roles": []})
    ext_config = {DecisionRiskLevel.HIGH.value: ["External_Corrosion_Lead"]}

    deliverable = hitl_manager.create_approval_package(
        pkg_no_roles,
        external_role_config=ext_config,
    )
    assert deliverable.required_human_roles == ["External_Corrosion_Lead"]


def test_role_resolution_tier3_manager_config_used(hitl_manager, sample_decision_package):
    """Verify Tier 3: manager config used when Tier 1 & 2 are empty."""
    pkg_no_roles = sample_decision_package.model_copy(update={"required_human_roles": []})
    mgr_config = ["Manager_Default_Role"]

    deliverable = hitl_manager.create_approval_package(
        pkg_no_roles,
        manager_role_config=mgr_config,
    )
    assert deliverable.required_human_roles == ["Manager_Default_Role"]


def test_role_resolution_fallback_to_empty_and_no_invented_roles(hitl_manager, sample_decision_package):
    """Verify Tier 4: falls back to [] when no roles supplied, never inventing roles."""
    pkg_no_roles = sample_decision_package.model_copy(update={"required_human_roles": []})

    deliverable = hitl_manager.create_approval_package(pkg_no_roles)
    assert deliverable.required_human_roles == []
    # HITL must still remain required
    assert deliverable.requires_human_approval is True
    assert deliverable.approval_state == HumanApprovalState.PENDING_REVIEW


# ─────────────────────────────────────────────────────────────
# 3. Human Workflow Disposition & Deliverable Provenance Tests
# ─────────────────────────────────────────────────────────────

def test_human_disposition_state_transitions(hitl_manager, sample_decision_package):
    """Verify human reviewer approval/rejection transitions using existing HumanApprovalManager."""
    deliverable = hitl_manager.create_approval_package(sample_decision_package)
    assert deliverable.approval_state == HumanApprovalState.PENDING_REVIEW

    # Approve
    approved = hitl_manager.submit_human_disposition(
        deliverable=deliverable,
        action="approve",
        reviewer_name="Inspector Dave",
        reviewer_notes="Reviewed and approved per statutory schedule.",
    )
    assert approved.approval_state == HumanApprovalState.APPROVED
    assert approved.reviewed_by == "Inspector Dave"
    assert approved.reviewer_notes == "Reviewed and approved per statutory schedule."
    assert isinstance(approved.reviewed_at, float)

    # Reject
    rejected = hitl_manager.submit_human_disposition(
        deliverable=deliverable,
        action="reject",
        reviewer_name="Inspector Dave",
        reviewer_notes="Rejecting due to insufficient survey coverage.",
    )
    assert rejected.approval_state == HumanApprovalState.REJECTED


def test_deliverable_preserves_provenance_and_audit_hash(hitl_manager, sample_decision_package):
    """Verify deliverable retains complete provenance, audit hash, and decision IDs."""
    deliverable = hitl_manager.create_approval_package(sample_decision_package)

    assert deliverable.audit_trail_hash == sample_decision_package.audit_trail_hash
    assert deliverable.applied_policy_id == "POL-OISD-142"
    assert deliverable.applied_policy_version == "2024.1"
    assert deliverable.evidence_assessment_id == "EA-TASK-100"
    assert deliverable.reconciliation_report_id == "REC-TASK-200"
    assert len(deliverable.provenance_source_spans) == 1
    assert deliverable.provenance_source_spans[0]["observation_id"] == "OBS-001"
    assert "0123456789abcdef" in deliverable.deliverable_summary


# ─────────────────────────────────────────────────────────────
# 4. Adversarial Safety Tests
# ─────────────────────────────────────────────────────────────

def test_adversarial_approval_does_not_create_fit_for_service_or_safety(hitl_manager, sample_decision_package):
    """Adversarial Test: Human approval must NOT inject fit_for_service, is_safe, or statutory_approval."""
    deliverable = hitl_manager.create_approval_package(sample_decision_package)
    approved = hitl_manager.submit_human_disposition(
        deliverable=deliverable,
        action="approve",
        reviewer_name="Senior Engineer",
    )
    # Check that model has no forbidden fields
    forbidden_fields = [
        "fit_for_service",
        "is_safe",
        "statutorily_compliant",
        "statutory_approval",
        "safety_score",
        "authority_score",
    ]
    for field in forbidden_fields:
        assert not hasattr(approved, field), f"Forbidden field '{field}' exists on DecisionApprovalDeliverable!"

    # Governance outcome must remain ESCALATE_HUMAN_REVIEW (unchanged by human approval)
    assert approved.governance_outcome == GovernanceOutcome.ESCALATE_HUMAN_REVIEW


def test_adversarial_cannot_bypass_governance_gate_blocked(hitl_manager, sample_decision_package):
    """Adversarial Test: GOVERNANCE_GATE_BLOCKED remains blocked and cannot be silently cleared."""
    blocked_pkg = sample_decision_package.model_copy(
        update={"governance_outcome": GovernanceOutcome.GOVERNANCE_GATE_BLOCKED}
    )
    deliverable = hitl_manager.create_approval_package(blocked_pkg)
    assert deliverable.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert deliverable.requires_human_approval is True
    # Human approval only records disposition; deliverable governance_outcome stays GOVERNANCE_GATE_BLOCKED
    approved = hitl_manager.submit_human_disposition(
        deliverable=deliverable,
        action="approve",
        reviewer_name="Lead Engineer",
    )
    assert approved.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
