from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    NOT_REQUIRED = "NOT_REQUIRED"


class CrossModelStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_EXECUTED = "NOT_EXECUTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    CONTRADICTED = "CONTRADICTED"
    LIMITED_INDEPENDENCE = "LIMITED_INDEPENDENCE"


class DeterministicStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_EXECUTED = "NOT_EXECUTED"
    PASSED = "PASSED"
    SUPPORTED = "SUPPORTED"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EvidenceStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_EXECUTED = "NOT_EXECUTED"
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INSUFFICIENT = "INSUFFICIENT"
    CONTRADICTED = "CONTRADICTED"


class DeterministicCheckResult(BaseModel):
    tool_used: str = Field(..., description="Deterministic tool invoked (e.g. python_calculator)")
    formula_name: str = Field(..., description="Calculation or engineering code reference")
    expected_output: Any = Field(..., description="Mathematically calculated result")
    model_output: Any = Field(..., description="Value extracted from model response")
    match: bool = Field(True, description="Whether model output matches deterministic calculation")
    expected_value: Optional[float] = Field(None, description="Exact expected numerical value if numeric")
    model_values: List[float] = Field(default_factory=list, description="Extracted numerical values from models")
    discrepancy: Optional[str] = Field(None, description="Detailed discrepancy explanation")
    calculation_result: Optional[Dict[str, Any]] = Field(None, description="Structured calculation result payload")
    extracted_evidence: Optional[Dict[str, Any]] = Field(None, description="Extracted evidence dictionary")
    calculation_conflict: bool = Field(False, description="Whether calculation conflict is detected")
    deterministic_check: str = Field("SUPPORTED", description="SUPPORTED, CONTRADICTED, or INSUFFICIENT_DATA")
    verification_trace: Optional[str] = Field(None, description="Formatted verification trace")


class CrossModelCheckResult(BaseModel):
    primary_model: str = Field(..., description="Primary model tag")
    verifier_model: str = Field(..., description="Verifier model tag")
    agreement_score: float = Field(1.0, ge=0.0, le=1.0, description="Semantic and factual agreement level (0-1)")
    consensus_summary: str = Field("", description="Summary of mutual agreement or points of divergence")
    discrepancies: List[str] = Field(default_factory=list, description="Specific conflicting claims")
    independence_level: str = Field("LIMITED", description="HIGHER, LIMITED, or NOT_APPLICABLE")


class VerificationReport(BaseModel):
    status: VerificationStatus = Field(VerificationStatus.NOT_REQUIRED, description="Composite verification outcome")
    evidence_status: EvidenceStatus = Field(EvidenceStatus.NOT_REQUIRED, description="Evidence grounding status")
    cross_model_status: CrossModelStatus = Field(CrossModelStatus.NOT_REQUIRED, description="Cross-model verification status")
    deterministic_status: DeterministicStatus = Field(DeterministicStatus.NOT_REQUIRED, description="Deterministic verification status")
    contradictions: List[str] = Field(default_factory=list, description="Contradictions detected between models or evidence")
    missing_information: List[str] = Field(default_factory=list, description="Missing required parameters or incomplete context")
    evidence_support: float = Field(1.0, ge=0.0, le=1.0, description="Fraction of assertions grounded in retrieved evidence (0-1)")
    evidence_support_pct: float = Field(100.0, ge=0.0, le=100.0, description="Percentage of claims grounded in retrieved evidence")
    model_agreement: str = Field("NOT_APPLICABLE", description="NOT_APPLICABLE, AGREED, DISAGREED, PARTIALLY_AGREED")
    verification_independence: str = Field("NOT_APPLICABLE", description="NOT_APPLICABLE, HIGHER, LIMITED")
    provenance_valid: bool = Field(True, description="Auditable provenance chain integrity verified")
    human_review_required: bool = Field(False, description="Flag indicating mandatory human sign-off")
    cross_model: Optional[CrossModelCheckResult] = Field(None, description="Dual-model cross-examination result")
    deterministic: Optional[DeterministicCheckResult] = Field(None, description="Deterministic arithmetic / physics check")
    provenance_chain: List[str] = Field(default_factory=list, description="Auditable step-by-step verification provenance")
    notes: str = Field("", description="Verification summary notes")
