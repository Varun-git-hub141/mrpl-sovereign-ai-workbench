import time
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ClaimOriginType(str, Enum):
    MRPL_KB_DIRECT = "MRPL_KB_DIRECT"
    CALCULATED_FROM_MRPL_EVIDENCE = "CALCULATED_FROM_MRPL_EVIDENCE"
    DERIVED_FROM_MRPL_EVIDENCE = "DERIVED_FROM_MRPL_EVIDENCE"
    GENERAL_LLM = "GENERAL_LLM"
    UNSUPPORTED = "UNSUPPORTED"
    MULTIMODAL_IMAGE_EVIDENCE = "MULTIMODAL_IMAGE_EVIDENCE"
    
    # Canonical Pipeline Identifiers & Aliases
    DIRECT_MRPL_RECORD = "MRPL_KB_DIRECT"
    CALCULATED_FROM_MRPL = "CALCULATED_FROM_MRPL_EVIDENCE"
    DERIVED_FROM_MRPL = "DERIVED_FROM_MRPL_EVIDENCE"
    LLM_INFERENCE = "GENERAL_LLM"
    MRPL_EVIDENCE = "MRPL_KB_DIRECT"
    MRPL_KB = "MRPL_KB_DIRECT"
    DETERMINISTIC_CALCULATOR = "CALCULATED_FROM_MRPL_EVIDENCE"
    LLM_SYNTHESIS = "MRPL_KB_DIRECT"
    GENERAL_MODEL_KNOWLEDGE = "GENERAL_LLM"


class ClaimStatus(str, Enum):
    SUPPORTED_BY_MRPL = "SUPPORTED BY MRPL KB"
    CALCULATED_BY_DETERMINISTIC = "CALCULATED BY DETERMINISTIC ENGINE"
    LLM_SYNTHESIS = "LLM SYNTHESIS"
    GENERAL_MODEL_KNOWLEDGE = "GENERAL MODEL KNOWLEDGE / INFERENCE — NOT MRPL VERIFIED"
    NOT_SUPPORTED_BY_MRPL = "NOT SUPPORTED BY MRPL EVIDENCE"


class ClaimProvenanceItem(BaseModel):
    claim_id: str = Field(..., description="Unique identifier for the claim (e.g. claim-1)")
    claim: str = Field(..., description="Verbatim or summarized factual statement extracted from response")
    origin: str = Field(ClaimOriginType.MRPL_KB_DIRECT.value, description="MRPL_KB_DIRECT, CALCULATED_FROM_MRPL_EVIDENCE, GENERAL_LLM, UNSUPPORTED, MULTIMODAL_IMAGE_EVIDENCE")
    source_document: Optional[str] = Field(None, description="Source document name or ID")
    source_chunk: Optional[str] = Field(None, description="Granular source chunk ID")
    source_type: str = Field("Inspection Record", description="Document type or reasoning source")
    calculation_status: str = Field("NOT_CALCULATED", description="NOT_CALCULATED or DETERMINISTIC")
    calculation_formula: Optional[str] = Field(None, description="Mathematical formula if calculated")
    formula: Optional[str] = Field(None, description="Mathematical equation used")
    input_sources: List[str] = Field(default_factory=list, description="List of source document IDs used as input")
    verification_status: str = Field("VERIFIED", description="VERIFIED, NOT_MRPL_VERIFIED, or UNSUPPORTED")
    
    # Backward compatibility attributes
    source: str = Field("MRPL Knowledge Base", description="Source document ID or authority reference")
    document_name: str = Field("", description="Document filename")
    document_type: str = Field("General", description="Inspection Report, Equipment History, Datasheet, etc.")
    equipment_tag: Optional[str] = Field(None, description="Associated equipment tag (e.g. P-201)")
    page: int = Field(1, description="Page number of evidence")
    chunk_id: str = Field("", description="Granular chunk identifier")
    evidence: str = Field("", description="Exact extracted snippet from retrieved MRPL chunk")
    status: str = Field(ClaimStatus.SUPPORTED_BY_MRPL.value, description="Claim verification status")
    origin_type: ClaimOriginType = Field(ClaimOriginType.MRPL_KB_DIRECT, description="Origin classification")
    bm25_score: Optional[float] = Field(None, description="BM25 lexical retrieval score")
    vector_score: Optional[float] = Field(None, description="Dense vector similarity score")
    hybrid_score: Optional[float] = Field(None, description="Combined hybrid ranking score")
    formula_trace: Optional[str] = Field(None, description="Deterministic formula if calculated")


class NumericalOriginItem(BaseModel):
    value: str = Field(..., description="Numerical quantity with units or number (e.g. 18.0 mm, 0.2286 mm/year)")
    unit: Optional[str] = Field(None, description="Physical engineering unit (e.g. mm/year, mm, years)")
    quantity_type: Optional[str] = Field(None, description="CORROSION_RATE, THICKNESS, INTERVAL, PRESSURE, etc.")
    origin: str = Field(..., description="Origin source or deterministic formula reference")
    source_doc: str = Field("", description="Document and page citation (e.g. MRPL-INSP-2019-P201, Page 1)")
    is_calculated: bool = Field(False, description="True if produced by deterministic calculator")
    formula: Optional[str] = Field(None, description="Mathematical equation used for calculation")


class SourceCoverageSummary(BaseModel):
    mrpl_supported_claims: int = Field(0, description="Count of claims directly backed by MRPL records")
    calculated_claims: int = Field(0, description="Count of claims verified by deterministic calculator")
    llm_inference_claims: int = Field(0, description="Count of synthesis/summary assertions")
    unsupported_claims: int = Field(0, description="Count of claims lacking MRPL evidence")
    general_knowledge_claims: int = Field(0, description="Count of unverified pretrained model claims")
    total_claims: int = Field(0, description="Total extracted claims evaluated")
    coverage_score: float = Field(1.0, ge=0.0, le=1.0, description="Fraction of supported/calculated claims")


class ClaimProvenanceReport(BaseModel):
    claims: List[ClaimProvenanceItem] = Field(default_factory=list, description="Claim-level provenance trail")
    numerical_origins: List[NumericalOriginItem] = Field(default_factory=list, description="Numerical origin mapping")
    source_coverage: SourceCoverageSummary = Field(default_factory=SourceCoverageSummary, description="Coverage summary")
    calculation_trace: Optional[str] = Field(None, description="Deterministic math trace if calculations occurred")
    is_fully_supported: bool = Field(True, description="True if no unsupported claims were detected")
    timestamp: float = Field(default_factory=time.time)
