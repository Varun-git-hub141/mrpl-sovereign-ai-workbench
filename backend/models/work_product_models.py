# backend/models/work_product_models.py
"""
MRPL Sovereign AI Workbench — Work Product Data Models.
Defines structured schemas for industrial work products, observations, calculations,
claim lineages, and post-generation deliverable verification receipts.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DeliverableStatus(str, Enum):
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    VERIFYING = "VERIFYING"
    VERIFIED_DELIVERABLE = "VERIFIED_DELIVERABLE"
    DELIVERABLE_VERIFICATION_FAILED = "DELIVERABLE_VERIFICATION_FAILED"


class ClaimLineageType(str, Enum):
    OBSERVED = "OBSERVED"
    SOURCE_STATED = "SOURCE_STATED"
    CALCULATED_FROM_MRPL_EVIDENCE = "CALCULATED_FROM_MRPL_EVIDENCE"
    SYSTEM_GENERATED = "SYSTEM_GENERATED"


class WorkProductObservation(BaseModel):
    parameter: str = Field(..., description="Name of observed engineering parameter")
    value: float = Field(..., description="Numerical value")
    unit: str = Field(..., description="Engineering unit (e.g. mm, barg, °C)")
    date: str = Field(..., description="Observation date (e.g. '2017-03-15')")
    location: str = Field(..., description="Component / inspection location (e.g. 'Shell Course 1 (CML 1)')")
    source_document: str = Field(..., description="Authoritative MRPL source document name")
    lineage_type: ClaimLineageType = Field(ClaimLineageType.OBSERVED, description="Lineage type")
    notes: Optional[str] = Field(None, description="Additional context or inspection notes")


class WorkProductCalculation(BaseModel):
    calculation_id: str = Field(..., description="Unique calculation identifier (e.g. 'CALC-V201-CR')")
    formula_name: str = Field(..., description="Standard engineering formula name (e.g. 'API 570 Short-Term / Long-Term Corrosion Rate')")
    formula_expression: str = Field(..., description="Mathematical formula expression (e.g. '(t_prev - t_curr) / delta_years')")
    inputs: Dict[str, Any] = Field(..., description="Input parameters and their values with units")
    interval_years: float = Field(..., description="Exact inspection interval in years")
    metal_loss_mm: float = Field(..., description="Calculated metal loss in mm")
    result_value: float = Field(..., description="Deterministic calculation result value")
    result_unit: str = Field("mm/year", description="Result engineering unit")
    calculator_identity: str = Field("MRPL Deterministic Formula Engine (Float64)", description="Calculator engine used")
    verification_status: str = Field("VERIFIED_DETERMINISTIC", description="Verification status of the arithmetic")


class WorkProductClaim(BaseModel):
    claim_id: str = Field(..., description="Unique claim identifier")
    text: str = Field(..., description="Exact substantive claim statement")
    lineage_type: ClaimLineageType = Field(..., description="Lineage classification")
    source_reference: str = Field(..., description="Specific document, section, or calculation ID")
    is_verified: bool = Field(True, description="Whether claim is backed by authoritative evidence")


class WorkProductSourceRef(BaseModel):
    document_name: str = Field(..., description="Filename or document title")
    document_id: str = Field(..., description="Authoritative document identifier")
    document_type: str = Field(..., description="Category (e.g. 'UT Inspection Report', 'Equipment Datasheet')")
    page: Optional[int] = Field(None, description="Page number")
    section: Optional[str] = Field(None, description="Document section or table")
    authority_level: str = Field("VERIFIED_ENGINEERING_RECORD", description="Source authority level")


class DeliverableVerificationCheck(BaseModel):
    check_name: str = Field(..., description="Identifier for verification check")
    description: str = Field(..., description="Human-readable description of what was verified")
    status: str = Field(..., description="'PASS' or 'FAIL'")
    expected: Optional[Any] = Field(None, description="Expected value or condition")
    actual: Optional[Any] = Field(None, description="Actual parsed value from the generated DOCX")
    details: Optional[str] = Field(None, description="Diagnostic notes if mismatch occurs")


class DeliverableVerificationReceipt(BaseModel):
    receipt_id: str = Field(..., description="Unique receipt ID")
    work_product_id: str = Field(..., description="Associated work product ID")
    artifact_path: str = Field(..., description="File path of the generated DOCX artifact")
    file_size_bytes: int = Field(0, description="Size of generated DOCX in bytes")
    status: DeliverableStatus = Field(..., description="Deliverable verification outcome")
    verified_at: float = Field(..., description="Unix timestamp of verification")
    asset_id: str = Field(..., description="Verified asset identifier")
    equipment_tag: str = Field(..., description="Verified equipment tag")
    checks_total: int = Field(0, description="Total checks executed")
    checks_passed: int = Field(0, description="Total checks passed")
    checks_failed: int = Field(0, description="Total checks failed")
    checks: List[DeliverableVerificationCheck] = Field(default_factory=list, description="Itemized verification checks")
    evidence_refs: List[str] = Field(default_factory=list, description="Referenced evidence documents")
    calculator_refs: List[str] = Field(default_factory=list, description="Referenced deterministic calculations")
    provenance_refs: List[str] = Field(default_factory=list, description="Referenced claim IDs")
    sovereignty_proof: Dict[str, Any] = Field(default_factory=dict, description="Air-gap and local execution telemetry")


class WorkProduct(BaseModel):
    work_product_id: str = Field(..., description="Unique work product identifier")
    work_product_type: str = Field("INSPECTION_REVIEW_NOTE", description="Type of engineering deliverable")
    title: str = Field(..., description="Document title")
    asset_id: str = Field(..., description="Unique asset ID")
    equipment_tag: str = Field(..., description="Equipment tag (e.g. 'V-201')")
    equipment_name: str = Field(..., description="Full equipment name (e.g. 'Crude Column Overhead Separator')")
    unit: str = Field(..., description="Refinery unit / area (e.g. 'CDU-II / Area 100')")
    request: str = Field(..., description="Original user prompt or engineering review scope request")
    scope: str = Field(..., description="Scope of review (e.g. 'Corrosion rate evaluation of Shell Course 1 per API 570')")
    evidence_status: str = Field("SUFFICIENT", description="Evidence sufficiency status")
    evidence_debt: str = Field("NONE", description="Evidence debt summary")
    observations: List[WorkProductObservation] = Field(default_factory=list, description="Inspection observations")
    calculations: List[WorkProductCalculation] = Field(default_factory=list, description="Deterministic calculations")
    claims: List[WorkProductClaim] = Field(default_factory=list, description="Substantive claims with lineage")
    limitations: List[str] = Field(default_factory=list, description="Evidence limitations and evaluation boundaries")
    source_references: List[WorkProductSourceRef] = Field(default_factory=list, description="Authoritative source references")
    safety_language: str = Field(
        "ENGINEERING DISCLAIMER: This work product is generated by the MRPL Sovereign AI Workbench as a verified decision-support document. It does not authorize mechanical modifications, plant operations changes, or bypass statutory inspection sign-offs.",
        description="Mandatory engineering disclaimer"
    )
    verification_requirements: List[str] = Field(default_factory=list, description="Pre-conditions for deliverable verification")
    demo_data_status: str = Field("CURATED_PLANT_DATA", description="Indicates whether plant records are real, curated, or demo")
    created_at: float = Field(..., description="Creation timestamp")
    docx_artifact_path: Optional[str] = Field(None, description="Path to generated DOCX file")
    verification_receipt: Optional[DeliverableVerificationReceipt] = Field(None, description="Receipt generated upon DOCX re-read")
