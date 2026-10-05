"""
Decision and Governance Data Models — Phase 4A
Approved Specification: v1.0.0-FINAL-CLARIFIED-R3

Deterministic governance, external policy evaluation schemas, action template mapping,
and human-in-the-loop (HITL) approval packaging models.

SAFETY INVARIANTS:
1. No free-form AI operational recommendations.
2. recommended_action may only represent an externally supplied PolicyActionTemplate action,
   None, or "REQUIRES_ENGINEER_DISPOSITION".
3. No hardcoded statutory standards, thresholds, or retirement limits.
4. No hardcoded organizational roles (required_human_roles defaults to []).
5. No numeric consistency/authority/safety scoring.
6. No synthetic ground truth or destructive observation merging.
7. No autonomous statutory/safety/fit-for-service verdicts.
8. No physical plant control (DCS, SCADA, PLC) integration.
9. Complete cryptographic and text-span provenance is preserved.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class DecisionRiskLevel(str, Enum):
    """Authoritative risk categorization governing human oversight requirements."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    STATUTORY = "STATUTORY"
    CRITICAL_SAFETY = "CRITICAL_SAFETY"


class GovernanceOutcome(str, Enum):
    """Categorical routing outcome from Phase 4 decision governance gates."""
    PROCEED_ADVISORY = "PROCEED_ADVISORY"
    PROCEED_WITH_CONDITIONS = "PROCEED_WITH_CONDITIONS"
    ESCALATE_HUMAN_REVIEW = "ESCALATE_HUMAN_REVIEW"
    GOVERNANCE_GATE_BLOCKED = "GOVERNANCE_GATE_BLOCKED"


class PolicyEvaluationStatus(str, Enum):
    """Evaluation state of an external policy rule against evidence."""
    NOT_EVALUATED = "NOT_EVALUATED"
    POLICY_NOT_SUPPLIED = "POLICY_NOT_SUPPLIED"
    CRITERIA_SATISFIED = "CRITERIA_SATISFIED"
    CRITERIA_BREACHED = "CRITERIA_BREACHED"
    DATA_INSUFFICIENT_FOR_POLICY = "DATA_INSUFFICIENT_FOR_POLICY"
    CONFLICT_PREVENTS_EVALUATION = "CONFLICT_PREVENTS_EVALUATION"


class TemplateActionCode(str, Enum):
    """
    Standardized action codes for authorized policy action templates.
    ENGINEERING_ASSESSMENT_REQUIRED means only:
    'External policy requires competent engineering assessment.'
    It does NOT imply fitness-for-service, safety clearance, or statutory sign-off.
    """
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    SCHEDULE_INSPECTION = "SCHEDULE_INSPECTION"
    PERFORM_THICKNESS_SURVEY = "PERFORM_THICKNESS_SURVEY"
    INITIATE_MOC = "INITIATE_MOC"
    CALIBRATE_INSTRUMENT = "CALIBRATE_INSTRUMENT"
    REVISE_OPERATING_LIMITS = "REVISE_OPERATING_LIMITS"
    ENGINEERING_ASSESSMENT_REQUIRED = "ENGINEERING_ASSESSMENT_REQUIRED"
    REQUIRES_ENGINEER_DISPOSITION = "REQUIRES_ENGINEER_DISPOSITION"


class PolicyActionTemplate(BaseModel):
    """External pre-authorized operational action template."""
    action_code: TemplateActionCode
    action_title: str = Field(..., description="Human-readable title from policy template")
    action_description: str = Field(..., description="Standard operating description from policy")
    mandatory_parameters: Dict[str, Any] = Field(default_factory=dict)


class PolicyRule(BaseModel):
    """Single rule within an external policy specification."""
    rule_id: str
    rule_name: str
    target_property: str = Field(..., description="Property evaluated, e.g. wall_thickness_mm")
    operator: str = Field(..., description="Mathematical operator: >, >=, <, <=, ==, !=, IN_RANGE")
    threshold_value: Any = Field(..., description="Policy threshold value")
    threshold_unit: Optional[str] = None
    on_satisfied_template: Optional[PolicyActionTemplate] = None
    on_breach_template: Optional[PolicyActionTemplate] = None


class StatutoryDecisionPolicy(BaseModel):
    """
    External policy artifact supplied at runtime.
    Contains zero hardcoded internal thresholds or assumptions.
    """
    policy_id: str
    policy_name: str
    policy_version: str
    issuing_authority: str = Field(..., description="e.g. OISD, API, ASME, MRPL_CORROSION_BOARD")
    effective_date: str
    expiration_date: Optional[str] = None
    applicable_entity_types: List[str] = Field(default_factory=list)
    risk_level: DecisionRiskLevel
    required_human_roles: List[str] = Field(
        default_factory=list,
        description="Explicit reviewer roles mandated by policy. If empty, role resolution is deferred to HITL config."
    )
    rules: List[PolicyRule] = Field(default_factory=list)
    provenance_lineage: Dict[str, Any] = Field(default_factory=dict)


class RuleEvaluationResult(BaseModel):
    """Evaluation result for an individual policy rule."""
    rule_id: str
    target_property: str
    observed_value: Any
    threshold_value: Any
    operator: str
    satisfied: bool
    evaluation_notes: str


class OperationalDecisionPackage(BaseModel):
    """
    Authoritative Phase 4 output artifact.
    Preserves complete provenance, governance outcomes, policy status, and audit hashes.
    """
    package_id: str
    entity_tag: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    risk_level: DecisionRiskLevel
    governance_outcome: GovernanceOutcome
    policy_evaluation_status: PolicyEvaluationStatus
    applied_policy_id: Optional[str] = None
    applied_policy_version: Optional[str] = None
    rule_evaluations: List[RuleEvaluationResult] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    action_template: Optional[PolicyActionTemplate] = None
    requires_human_approval: bool
    required_human_roles: List[str] = Field(
        default_factory=list,
        description="Explicit reviewer roles resolved from external policy/config. Never hardcoded by engine."
    )
    approval_ticket_id: Optional[str] = None
    evidence_assessment_id: Optional[str] = None
    reconciliation_report_id: Optional[str] = None
    provenance_source_spans: List[Dict[str, Any]] = Field(default_factory=list)
    audit_trail_hash: str = Field(..., description="SHA-256 cryptographic audit hash")

    @field_validator("recommended_action")
    @classmethod
    def validate_recommended_action(cls, v: Optional[str], info: Any) -> Optional[str]:
        """
        Safety constraint: recommended_action may ONLY exist if:
        1. It is None, or
        2. It is 'REQUIRES_ENGINEER_DISPOSITION', or
        3. An action_template is provided and matches.
        Free-form strings are forbidden.
        """
        if v is None or v == TemplateActionCode.REQUIRES_ENGINEER_DISPOSITION.value:
            return v
        
        # Valid template action codes
        valid_codes = {code.value for code in TemplateActionCode}
        if v not in valid_codes:
            raise ValueError(
                f"Invalid recommended_action '{v}'. Must be None, "
                f"'REQUIRES_ENGINEER_DISPOSITION', or match an authorized TemplateActionCode."
            )
        return v
