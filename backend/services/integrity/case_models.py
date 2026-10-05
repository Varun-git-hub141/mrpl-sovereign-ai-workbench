# backend/services/integrity/case_models.py
"""
MRPL Sovereign AI Workbench — Phase 9: Industrial Integrity Investigation Models.
Defines data models for case workspaces, evidence references, workflow stages,
disposition tracking, and end-to-end audit trace trees.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from backend.services.evidence.reconciliation_models import (
    EvidenceObservation,
    ReconciliationResult,
    AuthorityTier,
    ApprovalStatus,
)
from backend.services.evidence.evidence_models import (
    EvidenceAssessment,
    SufficiencyStatus,
)
from backend.services.decision.decision_models import (
    DecisionRiskLevel,
    GovernanceOutcome,
    PolicyEvaluationStatus,
    OperationalDecisionPackage,
    StatutoryDecisionPolicy,
)
from backend.services.decision.decision_hitl import (
    DecisionApprovalDeliverable,
    HumanApprovalState,
)


class InvestigationWorkflowStage(str, Enum):
    EVIDENCE_RECEIVED = "EVIDENCE_RECEIVED"
    OBSERVATIONS_EXTRACTED = "OBSERVATIONS_EXTRACTED"
    EVIDENCE_ASSESSED = "EVIDENCE_ASSESSED"
    RECONCILED = "RECONCILED"
    DECISION_EVALUATED = "DECISION_EVALUATED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class EvidenceDocumentReference(BaseModel):
    document_id: str
    filename: str
    document_type: str = "INSPECTION_REPORT"  # INSPECTION_REPORT, DATASHEET, CALIBRATION_CERT, MOC_RECORD
    revision: str = "Rev 0"
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    authority_tier: AuthorityTier = AuthorityTier.APPROVED_AUTHORITATIVE
    extraction_status: str = "PENDING"  # PENDING, EXTRACTED, FAILED
    source_path: Optional[str] = None
    uploaded_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    raw_content: Optional[Dict[str, Any]] = None


class AuditTraceNode(BaseModel):
    node_id: str
    node_type: str  # DECISION, RULE, RECONCILIATION, RELATIONSHIP, ASSESSMENT, OBSERVATION, DOCUMENT, SPAN
    title: str
    status: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    children: List["AuditTraceNode"] = Field(default_factory=list)


class IntegrityCase(BaseModel):
    case_id: str
    entity_tag: str
    case_title: str
    description: str
    risk_level: DecisionRiskLevel = DecisionRiskLevel.LOW
    workflow_stage: InvestigationWorkflowStage = InvestigationWorkflowStage.EVIDENCE_RECEIVED
    created_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    evidence_documents: List[EvidenceDocumentReference] = Field(default_factory=list)
    extracted_observations: List[EvidenceObservation] = Field(default_factory=list)
    evidence_assessment: Optional[EvidenceAssessment] = None
    reconciliation_result: Optional[ReconciliationResult] = None
    applied_policy: Optional[StatutoryDecisionPolicy] = None
    decision_package: Optional[OperationalDecisionPackage] = None
    approval_deliverable: Optional[DecisionApprovalDeliverable] = None
    audit_trail_hash: Optional[str] = None
    assigned_roles: List[str] = Field(default_factory=list)
    is_blocked: bool = False
    blocking_reason: Optional[str] = None
    human_approval_state: HumanApprovalState = HumanApprovalState.NOT_REQUIRED
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[float] = None


class CreateCaseRequest(BaseModel):
    entity_tag: str
    case_title: str
    description: Optional[str] = ""
    risk_level: DecisionRiskLevel = DecisionRiskLevel.LOW
    assigned_roles: Optional[List[str]] = None
    initial_documents: Optional[List[Dict[str, Any]]] = None


class AddEvidenceRequest(BaseModel):
    document_id: Optional[str] = None
    filename: str
    document_type: Optional[str] = "INSPECTION_REPORT"
    revision: Optional[str] = "Rev 0"
    approval_status: Optional[ApprovalStatus] = ApprovalStatus.APPROVED
    authority_tier: Optional[AuthorityTier] = AuthorityTier.APPROVED_AUTHORITATIVE
    raw_content: Optional[Dict[str, Any]] = None


class CaseDispositionRequest(BaseModel):
    action: str  # APPROVE, REJECT, REQUEST_REVISION
    reviewer_name: str
    reviewer_role: Optional[str] = None
    notes: Optional[str] = None
