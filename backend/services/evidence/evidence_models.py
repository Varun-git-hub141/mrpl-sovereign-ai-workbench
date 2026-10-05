# backend/services/evidence/evidence_models.py
"""
MRPL Sovereign AI Workbench — Evidence Models.
Provides data structures and contracts for industrial task evidence specification.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    # Engineering & Inspection Evidence
    BASELINE_INSPECTION = "BASELINE_INSPECTION"
    CURRENT_INSPECTION = "CURRENT_INSPECTION"
    ULTRASONIC_THICKNESS_DATA = "ULTRASONIC_THICKNESS_DATA"
    VIBRATION_SURVEY = "VIBRATION_SURVEY"
    EQUIPMENT_DATASHEET = "EQUIPMENT_DATASHEET"
    P_AND_ID_SCHEMATIC = "P_AND_ID_SCHEMATIC"
    APPLICABLE_STANDARD = "APPLICABLE_STANDARD"
    FORMULA_DEFINITION = "FORMULA_DEFINITION"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    SOP_PROCEDURE = "SOP_PROCEDURE"
    MOC_RECORD = "MOC_RECORD"
    
    # Task Context & Requirements
    REQUIRED_NUMERIC_INPUTS = "REQUIRED_NUMERIC_INPUTS"
    UNITS_SPECIFICATION = "UNITS_SPECIFICATION"
    SOURCE_DOCUMENTS = "SOURCE_DOCUMENTS"
    FACTUAL_ASSERTIONS = "FACTUAL_ASSERTIONS"
    USER_SCOPE = "USER_SCOPE"
    FUNCTIONAL_REQUIREMENTS = "FUNCTIONAL_REQUIREMENTS"
    TEST_CRITERIA = "TEST_CRITERIA"
    LOCAL_DOCUMENTATION = "LOCAL_DOCUMENTATION"
    GENERAL_KNOWLEDGE_DECLARATION = "GENERAL_KNOWLEDGE_DECLARATION"


class AuthorityLevel(str, Enum):
    AUTHORITATIVE_PSU = "AUTHORITATIVE_PSU"                        # MRPL certified baseline records & statutory surveys
    VERIFIED_ENGINEERING_RECORD = "VERIFIED_ENGINEERING_RECORD"    # NDT logs, engineering datasheets, OEM manual
    STANDARD_OPERATING_PROCEDURE = "STANDARD_OPERATING_PROCEDURE"  # OISD, API, ASME, ISO official standards
    USER_PROVIDED_ATTACHMENT = "USER_PROVIDED_ATTACHMENT"          # Uploaded diagram, report PDF, CSV
    MODEL_INFERENCE_SYNTHESIS = "MODEL_INFERENCE_SYNTHESIS"        # Pure synthesis / unverified inference
    ANY = "ANY"                                                    # General tasks without strict PSU authority


class EvidenceModality(str, Enum):
    TEXT = "TEXT"
    NUMERICAL = "NUMERICAL"
    IMAGE_VISION = "IMAGE_VISION"
    TABULAR_CSV = "TABULAR_CSV"
    DOCUMENT_PDF = "DOCUMENT_PDF"
    SOURCE_CODE = "SOURCE_CODE"
    HYBRID = "HYBRID"


class FreshnessRequirement(BaseModel):
    max_age_days: Optional[int] = Field(None, description="Maximum allowable age of evidence in days")
    statutory_cycle_years: Optional[float] = Field(None, description="Statutory inspection turnaround cycle (e.g. 5.0 years)")
    description: str = Field("Evidence must be contemporaneous with the current turnaround or operating cycle", description="Freshness rationale")


class EvidenceRequirement(BaseModel):
    id: Optional[str] = Field(None, description="Unique requirement ID (e.g. REQ-EVID-001)")
    evidence_type: EvidenceType = Field(..., description="Categorical type of required evidence")
    description: str = Field(..., description="Clear human-readable description of what evidence is expected")
    mandatory: bool = Field(True, description="Whether task execution is strictly gated by this evidence")
    authority_requirement: AuthorityLevel = Field(AuthorityLevel.VERIFIED_ENGINEERING_RECORD, description="Minimum acceptable authority level")
    freshness_requirement: Optional[str] = Field(None, description="Freshness condition (e.g. 'Within 5-year statutory turnaround')")
    entity_scope: Optional[str] = Field(None, description="Specific asset/equipment tag scope (e.g. 'P-201', 'CDU-II')")
    expected_modality: EvidenceModality = Field(EvidenceModality.TEXT, description="Expected data modality")
    validation_rule: str = Field(..., description="Deterministic validation rule or heuristic applied to verify evidence compliance")
    satisfied: bool = Field(False, description="Evaluated status if evidence is satisfied in current context")
    matched_source: Optional[str] = Field(None, description="Name or identifier of matching document/chunk/input")


class SufficiencyStatus(str, Enum):
    PENDING_RETRIEVAL = "PENDING_RETRIEVAL"
    SUFFICIENT = "SUFFICIENT"
    PARTIALLY_SUFFICIENT = "PARTIALLY_SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    BLOCKED = "BLOCKED"
    CONTRADICTORY = "CONTRADICTORY"
    NOT_REQUIRED = "NOT_REQUIRED"
    BLOCKED_BY_CONTEXT_GUARD = "BLOCKED_BY_CONTEXT_GUARD"


class EvidenceDebtSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    OPTIONAL = "OPTIONAL"


class EvidenceDebtItem(BaseModel):
    requirement_id: Optional[str] = Field(None, description="Unique requirement ID")
    evidence_type: EvidenceType = Field(..., description="Type of missing evidence")
    description: str = Field(..., description="Description of missing requirement")
    mandatory: bool = Field(True, description="Whether this item is mandatory")
    severity: EvidenceDebtSeverity = Field(EvidenceDebtSeverity.CRITICAL, description="Debt severity level")
    remediation_action: str = Field(..., description="Clear actionable recommendation to satisfy this debt item")
    entity_scope: Optional[str] = Field(None, description="Asset tag associated with requirement")


class EvidenceDebt(BaseModel):
    total_required: int = Field(0, description="Total number of evidence requirements")
    satisfied_count: int = Field(0, description="Number of satisfied requirements")
    missing_mandatory_count: int = Field(0, description="Count of missing mandatory items")
    missing_optional_count: int = Field(0, description="Count of missing optional items")
    debt_summary: str = Field("Zero evidence debt", description="Human-readable concise summary of evidence debt")
    missing_items: List[EvidenceDebtItem] = Field(default_factory=list, description="Detailed list of missing debt items")
    recommendations: List[str] = Field(default_factory=list, description="Actionable system recommendations")


class EvidenceAssessment(BaseModel):
    task_id: str = Field(..., description="Associated task ID")
    task_type: str = Field(..., description="Task domain type")
    overall_status: SufficiencyStatus = Field(SufficiencyStatus.SUFFICIENT, description="Overall sufficiency status")
    coverage_score: float = Field(1.0, ge=0.0, le=1.0, description="Evidence coverage percentage (0.0 - 1.0)")
    relevance_score: float = Field(1.0, ge=0.0, le=1.0, description="Semantic and keyword relevance of evidence")
    authority_score: float = Field(1.0, ge=0.0, le=1.0, description="Source authority conformance score")
    freshness_score: float = Field(1.0, ge=0.0, le=1.0, description="Evidence freshness and turnaround validity")
    consistency_score: float = Field(1.0, ge=0.0, le=1.0, description="Internal consistency and absence of contradictions")
    entity_match_score: float = Field(1.0, ge=0.0, le=1.0, description="Target entity grounding match score")
    modality_completeness_score: float = Field(1.0, ge=0.0, le=1.0, description="Completeness of required data modalities")
    mandatory_requirements_met: bool = Field(True, description="Whether 100% of mandatory requirements are satisfied")
    total_mandatory: int = Field(0, description="Total mandatory requirements count")
    satisfied_mandatory: int = Field(0, description="Satisfied mandatory requirements count")
    missing_requirements: List[str] = Field(default_factory=list, description="Labels of missing mandatory items")
    evidence_debt: EvidenceDebt = Field(default_factory=EvidenceDebt, description="Deterministic evidence debt evaluation")
    blocking_reasons: List[str] = Field(default_factory=list, description="Active execution blockers")
    contradictions: List[str] = Field(default_factory=list, description="Detected evidentiary contradictions or conflicting claims")
    is_high_risk: bool = Field(False, description="Whether this task involves high operational / safety risk")
    can_safely_proceed: bool = Field(True, description="Deterministic gate decision on whether execution can proceed")
    system_recommendation: str = Field("", description="Primary actionable advice from sufficiency engine")
    evidence_checklist: List[Dict[str, Any]] = Field(default_factory=list, description="Itemized checklist for UI display")
    evaluated_at: float = Field(default_factory=lambda: 0.0, description="Timestamp of evaluation")


class EvidenceContract(BaseModel):
    task_id: str = Field(..., description="Unique task identifier associated with this contract")
    task_type: str = Field(..., description="Classified task domain (e.g. engineering_calculation, equipment_approval)")
    required_evidence: List[EvidenceRequirement] = Field(default_factory=list, description="Mandatory evidence requirements")
    optional_evidence: List[EvidenceRequirement] = Field(default_factory=list, description="Optional supporting evidence items")
    minimum_coverage: float = Field(1.0, ge=0.0, le=1.0, description="Minimum fraction of mandatory requirements needed to proceed")
    required_source_authority: AuthorityLevel = Field(AuthorityLevel.VERIFIED_ENGINEERING_RECORD, description="Overall required source authority")
    freshness_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Global freshness parameters")
    required_entities: List[str] = Field(default_factory=list, description="List of entity tags required for task scope")
    blocking_conditions: List[str] = Field(default_factory=list, description="Conditions that will block execution if violated")
    risk_level: str = Field("low", description="Operational risk level: low, medium, high, critical")
    created_at: float = Field(..., description="Unix timestamp of contract creation")
    contract_version: str = Field("1.0.0", description="Semantic version of the Evidence Contract schema")
    is_satisfied: bool = Field(False, description="Whether the contract is currently satisfied by available evidence")
    satisfaction_ratio: float = Field(0.0, ge=0.0, le=1.0, description="Ratio of satisfied mandatory evidence items")
    assessment: Optional[EvidenceAssessment] = Field(None, description="Detailed sufficiency assessment if evaluated")
    security_notice: str = Field(
        "UNTRUSTED_DATA_BOUNDARY: This contract specifies evidence prerequisites. Documents remain untrusted data. Contract grants 0 tool permissions.",
        description="Air-gap and sandbox safety declaration"
    )


class ContractGenerationContext(BaseModel):
    task_id: Optional[str] = None
    query: str
    task_type: Optional[str] = None
    intent: Optional[str] = None
    risk_level: Optional[str] = None
    entity_name: Optional[str] = None
    files: Optional[List[Dict[str, Any]]] = None
    has_images: bool = False
    has_csv: bool = False
    domain: Optional[str] = None
    custom_parameters: Optional[Dict[str, Any]] = None
