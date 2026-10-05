"""
Phase 4B Unit & Adversarial Safety Tests — Decision & Policy Evaluation Engine
Approved Specification: v1.0.0-FINAL-CLARIFIED-R3

Verifies deterministic governance routing, external policy evaluation,
audit hash generation, provenance preservation, and safety invariants.
"""

import pytest
from datetime import datetime

from backend.services.decision.decision_engine import DecisionEngine
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
from backend.services.evidence.evidence_models import (
    AuthorityLevel,
    EvidenceAssessment,
    EvidenceDebt,
    SufficiencyStatus,
)
from backend.services.evidence.reconciliation_models import (
    ApplicabilityStatus,
    ApplicableObservationContext,
    ApprovalStatus,
    AuthorityTier,
    ConsistencyState,
    EvidenceConflict,
    EvidenceObservation,
    EvidenceSearchStatus,
    ExtractionMethod,
    ReconciliationRelationship,
    ReconciliationResult,
    ReconciliationStatus,
    RelationshipType,
)


@pytest.fixture
def engine():
    return DecisionEngine()


@pytest.fixture
def sample_observation():
    return EvidenceObservation(
        observation_id="OBS-001",
        entity_tag="11-V-101",
        property_name="wall_thickness_mm",
        value=8.5,
        unit="mm",
        authority_tier=AuthorityTier.APPROVED_AUTHORITATIVE,
        approval_status=ApprovalStatus.APPROVED,
        extraction_method=ExtractionMethod.STRUCTURED_JSON,
        source_document="11-V-101_UT_2024.json",
        page_number=1,
        raw_statement="Thickness: 8.5 mm",
    )


# ─────────────────────────────────────────────────────────────
# 1. Phase 2 Precondition Tests (Rule 1)
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", [
    SufficiencyStatus.BLOCKED,
    SufficiencyStatus.INSUFFICIENT,
    SufficiencyStatus.CONTRADICTORY,
])
def test_phase2_blocking_preconditions(engine, status, sample_observation):
    """Verify Phase 2 BLOCKED, INSUFFICIENT, CONTRADICTORY map to GOVERNANCE_GATE_BLOCKED."""
    assessment = EvidenceAssessment(
        task_id="TASK-P2-01",
        task_type="thickness_evaluation",
        overall_status=status,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        evidence_assessment=assessment,
        observations=[sample_observation],
    )
    assert result.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert result.requires_human_approval is True
    assert result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


# ─────────────────────────────────────────────────────────────
# 2. Phase 3 Conflict & Anomaly Search Gate Tests (Rule 2)
# ─────────────────────────────────────────────────────────────

def test_phase3_active_contradiction_blocks(engine, sample_observation):
    """Verify active unaddressed conflict triggers GOVERNANCE_GATE_BLOCKED."""
    conflict = EvidenceConflict(
        conflict_id="CONF-01",
        property_name="wall_thickness_mm",
        entity_tag="11-V-101",
        conflicting_observation_ids=["OBS-001", "OBS-002"],
        conflict_description="Simultaneous discrepancy between NDT logs",
    )
    rec_result = ReconciliationResult(
        task_id="REC-01",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.CONFLICTING,
        reconciliation_status=ReconciliationStatus.UNRESOLVED_CONFLICT,
        all_observations=[sample_observation],
        active_conflicts=[conflict],
        reconciliation_summary="Active conflict detected.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert result.requires_human_approval is True
    assert result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


def test_phase3_anomaly_search_not_performed_blocks(engine, sample_observation):
    """Verify anomaly candidate with search not performed triggers GOVERNANCE_GATE_BLOCKED."""
    rel = ReconciliationRelationship(
        relationship_id="REL-01",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE,
        observation_ids=["OBS-001", "OBS-002"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
        explanation="Unexplained thickness increase",
        is_anomaly=True,
    )
    rec_result = ReconciliationResult(
        task_id="REC-02",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.ANOMALOUS,
        reconciliation_status=ReconciliationStatus.ANOMALY_DETECTED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Anomaly candidate pending search.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert result.requires_human_approval is True
    assert result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


def test_phase3_anomaly_search_in_progress_blocks(engine, sample_observation):
    """Verify anomaly candidate with search in progress triggers GOVERNANCE_GATE_BLOCKED."""
    rel = ReconciliationRelationship(
        relationship_id="REL-02",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.ANOMALOUS_PROGRESSION,
        observation_ids=["OBS-001", "OBS-002"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_IN_PROGRESS,
        explanation="Search in progress",
        is_anomaly=True,
    )
    rec_result = ReconciliationResult(
        task_id="REC-03",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.ANOMALOUS,
        reconciliation_status=ReconciliationStatus.ANOMALY_DETECTED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Search currently in progress.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert result.requires_human_approval is True


# ─────────────────────────────────────────────────────────────
# 3. Policy Breach & Template Propagation (Rule 3)
# ─────────────────────────────────────────────────────────────

def test_external_policy_breach_escalates_and_propagates_template(engine, sample_observation):
    """Verify policy breach escalates to human review and propagates authorized breach template."""
    breach_template = PolicyActionTemplate(
        action_code=TemplateActionCode.ENGINEERING_ASSESSMENT_REQUIRED,
        action_title="Engineering Assessment for Thinning",
        action_description="Conduct engineering assessment under API 579.",
    )
    rule = PolicyRule(
        rule_id="RULE-THK-01",
        rule_name="Minimum Thickness Limit",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=10.0,  # Observed is 8.5 -> Breach
        on_breach_template=breach_template,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-CORR-01",
        policy_name="Corrosion Monitoring Policy",
        policy_version="1.0",
        issuing_authority="MRPL_CORROSION_BOARD",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.MEDIUM,
        rules=[rule],
    )

    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.MEDIUM,
        policy=policy,
        observations=[sample_observation],
    )
    assert result.governance_outcome == GovernanceOutcome.ESCALATE_HUMAN_REVIEW
    assert result.policy_evaluation_status == PolicyEvaluationStatus.CRITERIA_BREACHED
    assert result.requires_human_approval is True
    assert result.recommended_action == "ENGINEERING_ASSESSMENT_REQUIRED"
    assert result.action_template.action_code == TemplateActionCode.ENGINEERING_ASSESSMENT_REQUIRED


# ─────────────────────────────────────────────────────────────
# 4. High / Statutory / Critical Safety (Rule 4)
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("risk", [
    DecisionRiskLevel.HIGH,
    DecisionRiskLevel.STATUTORY,
    DecisionRiskLevel.CRITICAL_SAFETY,
])
def test_high_statutory_critical_requires_mandatory_hitl(engine, risk, sample_observation):
    """Verify high, statutory, and critical safety risk tasks CANNOT bypass human approval."""
    rule = PolicyRule(
        rule_id="RULE-01",
        rule_name="Nominal Check",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=5.0,  # Satisfied (8.5 >= 5.0)
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-STAT-01",
        policy_name="Statutory Baseline Policy",
        policy_version="2.0",
        issuing_authority="PESO",
        effective_date="2024-01-01",
        risk_level=risk,
        rules=[rule],
    )

    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=risk,
        policy=policy,
        observations=[sample_observation],
    )
    assert result.requires_human_approval is True
    assert result.governance_outcome == GovernanceOutcome.ESCALATE_HUMAN_REVIEW


def test_high_risk_with_policy_conditions(engine, sample_observation):
    """Verify high risk with policy satisfied + conditions emits PROCEED_WITH_CONDITIONS + HITL."""
    cond_template = PolicyActionTemplate(
        action_code=TemplateActionCode.SCHEDULE_INSPECTION,
        action_title="Schedule Turnaround Inspection",
        action_description="Re-inspect at next turnaround.",
    )
    rule = PolicyRule(
        rule_id="RULE-01",
        rule_name="Nominal Thickness",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=5.0,
        on_satisfied_template=cond_template,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-01",
        policy_name="P1",
        policy_version="1.0",
        issuing_authority="MRPL",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.HIGH,
        rules=[rule],
    )

    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.HIGH,
        policy=policy,
        observations=[sample_observation],
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_WITH_CONDITIONS
    assert result.requires_human_approval is True
    assert result.recommended_action == "SCHEDULE_INSPECTION"


# ─────────────────────────────────────────────────────────────
# 5. Low / Medium Risk Routing (Rules 5 & 6)
# ─────────────────────────────────────────────────────────────

def test_low_medium_with_policy_conditions(engine, sample_observation):
    """Verify low risk with non-blocking conditions emits PROCEED_WITH_CONDITIONS with HITL=False."""
    cond_template = PolicyActionTemplate(
        action_code=TemplateActionCode.PERFORM_THICKNESS_SURVEY,
        action_title="Routine Survey",
        action_description="Carry out routine UT survey.",
    )
    rule = PolicyRule(
        rule_id="R-01",
        rule_name="Check",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=5.0,
        on_satisfied_template=cond_template,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="P-01",
        policy_name="P1",
        policy_version="1.0",
        issuing_authority="MRPL",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.LOW,
        rules=[rule],
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        policy=policy,
        observations=[sample_observation],
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_WITH_CONDITIONS
    assert result.requires_human_approval is False
    assert result.recommended_action == "PERFORM_THICKNESS_SURVEY"


def test_low_medium_without_policy_emits_proceed_advisory(engine, sample_observation):
    """Verify low risk with POLICY_NOT_SUPPLIED emits PROCEED_ADVISORY with HITL=False."""
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        observations=[sample_observation],
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_ADVISORY
    assert result.policy_evaluation_status == PolicyEvaluationStatus.POLICY_NOT_SUPPLIED
    assert result.requires_human_approval is False
    assert result.recommended_action is None


# ─────────────────────────────────────────────────────────────
# 6. Policy Operators & Data Insufficiency Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("op, thresh, obs_val, expected_sat", [
    (">", 5.0, 8.5, True),
    (">", 8.5, 8.5, False),
    (">=", 8.5, 8.5, True),
    ("<", 10.0, 8.5, True),
    ("<=", 8.5, 8.5, True),
    ("==", 8.5, 8.5, True),
    ("!=", 8.5, 8.5, False),
    ("IN_RANGE", [5.0, 10.0], 8.5, True),
    ("IN_RANGE", [9.0, 12.0], 8.5, False),
])
def test_all_policy_operators(engine, op, thresh, obs_val, expected_sat, sample_observation):
    """Verify deterministic evaluation of all supported policy operators."""
    obs = sample_observation.model_copy(update={"value": obs_val})
    rule = PolicyRule(
        rule_id="R-OP",
        rule_name="Op Test",
        target_property="wall_thickness_mm",
        operator=op,
        threshold_value=thresh,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-OP",
        policy_name="Operator Policy",
        policy_version="1.0",
        issuing_authority="TEST",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.LOW,
        rules=[rule],
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        policy=policy,
        observations=[obs],
    )
    eval_res = result.rule_evaluations[0]
    assert eval_res.satisfied == expected_sat
    if expected_sat:
        assert result.policy_evaluation_status == PolicyEvaluationStatus.CRITERIA_SATISFIED
    else:
        assert result.policy_evaluation_status == PolicyEvaluationStatus.CRITERIA_BREACHED


def test_data_insufficient_for_policy(engine, sample_observation):
    """Verify DATA_INSUFFICIENT_FOR_POLICY when target property is missing."""
    rule = PolicyRule(
        rule_id="R-MISSING",
        rule_name="Corrosion Rate",
        target_property="corrosion_rate_mm_year",
        operator="<",
        threshold_value=0.2,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-MISSING",
        policy_name="Corrosion Policy",
        policy_version="1.0",
        issuing_authority="TEST",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.LOW,
        rules=[rule],
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        policy=policy,
        observations=[sample_observation],  # Has wall_thickness_mm, not corrosion_rate
    )
    assert result.policy_evaluation_status == PolicyEvaluationStatus.DATA_INSUFFICIENT_FOR_POLICY
    assert result.requires_human_approval is True
    assert result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


def test_conflict_prevents_evaluation_when_multiple_unreconciled_observations(engine):
    """Verify CONFLICT_PREVENTS_EVALUATION when multiple unresolved distinct observations exist."""
    obs1 = EvidenceObservation(
        observation_id="OBS-A",
        entity_tag="11-V-101",
        property_name="wall_thickness_mm",
        value=8.5,
        unit="mm",
        authority_tier=AuthorityTier.APPROVED,
        approval_status=ApprovalStatus.APPROVED,
        extraction_method=ExtractionMethod.STRUCTURED_JSON,
        source_document="docA.json",
        raw_statement="thickness 8.5",
    )
    obs2 = EvidenceObservation(
        observation_id="OBS-B",
        entity_tag="11-V-101",
        property_name="wall_thickness_mm",
        value=6.2,  # Conflicting value
        unit="mm",
        authority_tier=AuthorityTier.INTERNAL,
        approval_status=ApprovalStatus.DRAFT,
        extraction_method=ExtractionMethod.STRUCTURED_JSON,
        source_document="docB.json",
        raw_statement="thickness 6.2",
    )
    rule = PolicyRule(
        rule_id="R-THK",
        rule_name="Thickness",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=7.0,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-CONF",
        policy_name="Conf Policy",
        policy_version="1.0",
        issuing_authority="TEST",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.LOW,
        rules=[rule],
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        policy=policy,
        observations=[obs1, obs2],
    )
    assert result.policy_evaluation_status == PolicyEvaluationStatus.CONFLICT_PREVENTS_EVALUATION
    assert result.requires_human_approval is True
    assert result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


# ─────────────────────────────────────────────────────────────
# 7. Determinism & SHA-256 Audit Hash Tests
# ─────────────────────────────────────────────────────────────

def test_deterministic_identical_input_behavior_and_audit_hash(engine, sample_observation):
    """Verify that identical inputs produce identical outcomes and identical SHA-256 audit hashes."""
    rule = PolicyRule(
        rule_id="R-01",
        rule_name="Nominal",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=6.0,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-01",
        policy_name="P1",
        policy_version="1.0",
        issuing_authority="TEST",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.LOW,
        rules=[rule],
    )
    res1 = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        policy=policy,
        observations=[sample_observation],
        package_id="PKG-FIXED-01",
    )
    res2 = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        policy=policy,
        observations=[sample_observation],
        package_id="PKG-FIXED-01",
    )
    assert res1.governance_outcome == res2.governance_outcome
    assert res1.policy_evaluation_status == res2.policy_evaluation_status
    assert res1.audit_trail_hash == res2.audit_trail_hash
    assert len(res1.audit_trail_hash) == 64  # Valid SHA-256 hex string


# ─────────────────────────────────────────────────────────────
# 8. Provenance & Role Safety Tests
# ─────────────────────────────────────────────────────────────

def test_provenance_preservation(engine, sample_observation):
    """Verify complete verbatim source span provenance is preserved in the decision package."""
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        observations=[sample_observation],
    )
    assert len(result.provenance_source_spans) >= 1
    span = result.provenance_source_spans[0]
    assert span["observation_id"] == "OBS-001"
    assert span["verbatim_source_span"] == "Thickness: 8.5 mm"
    assert span["raw_source_document"] == "11-V-101_UT_2024.json"


def test_no_hardcoded_hitl_roles(engine, sample_observation):
    """Verify that required_human_roles defaults to [] when no external roles are provided."""
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.HIGH,
        observations=[sample_observation],
    )
    # Even under HIGH risk requiring human approval, roles must remain [] if not externally supplied
    assert result.requires_human_approval is True
    assert result.required_human_roles == []


# ─────────────────────────────────────────────────────────────
# 9. Adversarial Safety Tests
# ─────────────────────────────────────────────────────────────

def test_adversarial_no_averaging_of_conflicting_observations(engine):
    """Adversarial Test: Engine must NOT average 8.0mm and 4.0mm to create 6.0mm."""
    obs1 = EvidenceObservation(
        observation_id="OBS-1",
        entity_tag="11-V-101",
        property_name="wall_thickness_mm",
        value=8.0,
        unit="mm",
        authority_tier=AuthorityTier.APPROVED,
        approval_status=ApprovalStatus.APPROVED,
        extraction_method=ExtractionMethod.STRUCTURED_JSON,
        source_document="doc1.json",
        raw_statement="thickness 8.0",
    )
    obs2 = EvidenceObservation(
        observation_id="OBS-2",
        entity_tag="11-V-101",
        property_name="wall_thickness_mm",
        value=4.0,
        unit="mm",
        authority_tier=AuthorityTier.INTERNAL,
        approval_status=ApprovalStatus.DRAFT,
        extraction_method=ExtractionMethod.STRUCTURED_JSON,
        source_document="doc2.json",
        raw_statement="thickness 4.0",
    )
    rule = PolicyRule(
        rule_id="R-THK",
        rule_name="Min Thk",
        target_property="wall_thickness_mm",
        operator=">=",
        threshold_value=5.0,
    )
    policy = StatutoryDecisionPolicy(
        policy_id="POL-ADV",
        policy_name="Adv Policy",
        policy_version="1.0",
        issuing_authority="TEST",
        effective_date="2024-01-01",
        risk_level=DecisionRiskLevel.LOW,
        rules=[rule],
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        policy=policy,
        observations=[obs1, obs2],
    )
    # If it had averaged to 6.0, it would have satisfied >= 5.0. It MUST NOT.
    assert result.policy_evaluation_status == PolicyEvaluationStatus.CONFLICT_PREVENTS_EVALUATION
    assert result.governance_outcome == GovernanceOutcome.ESCALATE_HUMAN_REVIEW


def test_adversarial_no_autonomous_clearance_under_policy_not_supplied(engine, sample_observation):
    """Adversarial Test: POLICY_NOT_SUPPLIED must NOT provide clearance or safety approval."""
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.HIGH,
        observations=[sample_observation],
    )
    assert result.policy_evaluation_status == PolicyEvaluationStatus.POLICY_NOT_SUPPLIED
    assert result.governance_outcome == GovernanceOutcome.ESCALATE_HUMAN_REVIEW
    assert result.requires_human_approval is True
    # Absence of policy must NOT make recommended_action say "SAFE" or "CLEAR"
    assert result.recommended_action is None or result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


# ─────────────────────────────────────────────────────────────
# 6. Phase 5.1 Rule 2 Anomaly-Aware Semantic Tests (Tests A–J)
# ─────────────────────────────────────────────────────────────

def test_rule2_test_a_corroborating_with_search_not_performed_does_not_block(engine, sample_observation):
    """TEST A: Ordinary CORROBORATING + EVIDENCE_SEARCH_NOT_PERFORMED does NOT trigger anomaly Rule 2 blocking."""
    rel = ReconciliationRelationship(
        relationship_id="REL-CORR-01",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.CORROBORATING,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
        explanation="Corroborating measurements",
        is_anomaly=False,
    )
    rec_result = ReconciliationResult(
        task_id="REC-A",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.CONSISTENT,
        reconciliation_status=ReconciliationStatus.NON_CONFLICTING,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Corroborating evidence.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_ADVISORY
    assert result.requires_human_approval is False


def test_rule2_test_b_temporal_progression_with_search_not_performed_does_not_block(engine, sample_observation):
    """TEST B: Ordinary TEMPORAL_PROGRESSION + EVIDENCE_SEARCH_NOT_PERFORMED does NOT trigger anomaly Rule 2 blocking."""
    rel = ReconciliationRelationship(
        relationship_id="REL-TEMP-01",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.TEMPORAL_PROGRESSION,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
        explanation="Valid temporal wall thinning",
        is_anomaly=False,
    )
    rec_result = ReconciliationResult(
        task_id="REC-B",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.TEMPORALLY_EXPLAINED,
        reconciliation_status=ReconciliationStatus.TEMPORALLY_MAPPED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Temporal progression mapped.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_ADVISORY
    assert result.requires_human_approval is False


def test_rule2_test_c_spatially_distinct_with_search_not_performed_does_not_block(engine, sample_observation):
    """TEST C: Ordinary SPATIALLY_DISTINCT + EVIDENCE_SEARCH_NOT_PERFORMED does NOT trigger anomaly Rule 2 blocking."""
    rel = ReconciliationRelationship(
        relationship_id="REL-SPAT-01",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.SPATIALLY_DISTINCT,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
        explanation="Distinct spatial CML inspection points",
        is_anomaly=False,
    )
    rec_result = ReconciliationResult(
        task_id="REC-C",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.SPATIALLY_DISTINCT,
        reconciliation_status=ReconciliationStatus.SPATIALLY_MAPPED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Spatially distinct points mapped.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_ADVISORY
    assert result.requires_human_approval is False


def test_rule2_test_d_anomaly_candidate_search_not_performed_blocks(engine, sample_observation):
    """TEST D: ANOMALOUS_PROGRESSION_CANDIDATE + EVIDENCE_SEARCH_NOT_PERFORMED MUST trigger GOVERNANCE_GATE_BLOCKED."""
    rel = ReconciliationRelationship(
        relationship_id="REL-ANOM-CAND",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
        explanation="Unresolved anomaly candidate",
        is_anomaly=True,
    )
    rec_result = ReconciliationResult(
        task_id="REC-D",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.ANOMALOUS,
        reconciliation_status=ReconciliationStatus.ANOMALY_DETECTED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Candidate requires search.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert result.requires_human_approval is True
    assert result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


def test_rule2_test_e_anomaly_candidate_search_in_progress_blocks(engine, sample_observation):
    """TEST E: ANOMALOUS_PROGRESSION_CANDIDATE + EVIDENCE_SEARCH_IN_PROGRESS MUST trigger GOVERNANCE_GATE_BLOCKED."""
    rel = ReconciliationRelationship(
        relationship_id="REL-ANOM-PROG",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.ANOMALOUS_PROGRESSION,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_IN_PROGRESS,
        explanation="Search actively running",
        is_anomaly=True,
    )
    rec_result = ReconciliationResult(
        task_id="REC-E",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.ANOMALOUS,
        reconciliation_status=ReconciliationStatus.ANOMALY_DETECTED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Search running.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert result.requires_human_approval is True


def test_rule2_test_f_supporting_evidence_found_anomaly_behavior(engine, sample_observation):
    """TEST F: Existing supporting-evidence-found anomaly behavior passes Rule 2 search gate."""
    rel = ReconciliationRelationship(
        relationship_id="REL-ANOM-FOUND",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.ANOMALOUS_PROGRESSION,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.SUPPORTING_EVIDENCE_FOUND,
        explanation="Supporting MOC found",
        is_anomaly=True,
    )
    rec_result = ReconciliationResult(
        task_id="REC-F",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.ANOMALOUS,
        reconciliation_status=ReconciliationStatus.ANOMALY_DETECTED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Supporting MOC verified.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_ADVISORY
    assert result.requires_human_approval is False


def test_rule2_test_g_supporting_evidence_not_found_anomaly_behavior(engine, sample_observation):
    """TEST G: Existing supporting-evidence-not-found behavior passes Rule 2 search gate."""
    rel = ReconciliationRelationship(
        relationship_id="REL-ANOM-NOTFOUND",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.ANOMALOUS_PROGRESSION,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH,
        explanation="Search completed, no MOC found",
        is_anomaly=True,
    )
    rec_result = ReconciliationResult(
        task_id="REC-G",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.ANOMALOUS,
        reconciliation_status=ReconciliationStatus.ANOMALY_DETECTED,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Search completed.",
        reconciled_at=1700000000.0,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
    )
    assert result.governance_outcome == GovernanceOutcome.PROCEED_ADVISORY
    assert result.requires_human_approval is False


@pytest.mark.parametrize("status", [
    SufficiencyStatus.BLOCKED,
    SufficiencyStatus.INSUFFICIENT,
    SufficiencyStatus.CONTRADICTORY,
])
def test_rule2_test_h_phase2_gates_remain_unchanged(engine, status, sample_observation):
    """TEST H: Phase 2 BLOCKED/INSUFFICIENT/CONTRADICTORY gates remain unchanged."""
    assessment = EvidenceAssessment(
        task_id="TASK-P2-H",
        task_type="thickness_evaluation",
        overall_status=status,
    )
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        evidence_assessment=assessment,
        observations=[sample_observation],
    )
    assert result.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED
    assert result.requires_human_approval is True
    assert result.recommended_action == "REQUIRES_ENGINEER_DISPOSITION"


@pytest.mark.parametrize("risk", [
    DecisionRiskLevel.HIGH,
    DecisionRiskLevel.STATUTORY,
    DecisionRiskLevel.CRITICAL_SAFETY,
])
def test_rule2_test_i_elevated_risk_hitl_unchanged(engine, risk, sample_observation):
    """TEST I: HIGH / STATUTORY / CRITICAL_SAFETY HITL behavior remains unchanged."""
    result = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=risk,
        observations=[sample_observation],
    )
    assert result.governance_outcome == GovernanceOutcome.ESCALATE_HUMAN_REVIEW
    assert result.requires_human_approval is True


def test_rule2_test_j_determinism_and_hash_invariance(engine, sample_observation):
    """TEST J: Repeated identical evaluation remains deterministic and produces the same audit hash."""
    rel = ReconciliationRelationship(
        relationship_id="REL-CORR-DET",
        property_name="wall_thickness_mm",
        relationship_type=RelationshipType.CORROBORATING,
        observation_ids=["OBS-001"],
        evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
        explanation="Corroborating measurements",
        is_anomaly=False,
    )
    rec_result = ReconciliationResult(
        task_id="REC-DET",
        entity_scope=["11-V-101"],
        consistency_state=ConsistencyState.CONSISTENT,
        reconciliation_status=ReconciliationStatus.NON_CONFLICTING,
        all_observations=[sample_observation],
        relationships=[rel],
        reconciliation_summary="Deterministic check.",
        reconciled_at=1700000000.0,
    )
    res1 = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
        package_id="PKG-DETERMINISM-FIXED",
    )
    res2 = engine.evaluate(
        entity_tag="11-V-101",
        risk_level=DecisionRiskLevel.LOW,
        reconciliation_result=rec_result,
        package_id="PKG-DETERMINISM-FIXED",
    )
    assert res1.governance_outcome == res2.governance_outcome
    assert res1.audit_trail_hash == res2.audit_trail_hash
    assert len(res1.audit_trail_hash) == 64

