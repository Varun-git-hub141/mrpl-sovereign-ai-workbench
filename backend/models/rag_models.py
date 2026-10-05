import time
from typing import List, Dict, Any, Optional, Set
from enum import Enum
from pydantic import BaseModel, Field


class AuthorityLevel(str, Enum):
    A = "A"  # Approved MRPL internal document / authoritative
    B = "B"  # Controlled engineering standard (API, ASME, OISD, ISO, ASTM)
    C = "C"  # Technical reference / Manufacturer manual / Datasheet
    D = "D"  # Generated reference knowledge (clearly labeled NOT_MRPL_OFFICIAL)
    E = "E"  # Unverified / draft information


class KnowledgeSourceType(str, Enum):
    APPROVED_MRPL_DOCUMENT = "APPROVED_MRPL_DOCUMENT"
    ENGINEERING_STANDARD = "ENGINEERING_STANDARD"
    EQUIPMENT_MANUAL = "EQUIPMENT_MANUAL"
    INSPECTION_RECORD = "INSPECTION_RECORD"
    MAINTENANCE_RECORD = "MAINTENANCE_RECORD"
    PND_DRAWING = "PND_DRAWING"
    SOP_PROCEDURE = "SOP_PROCEDURE"
    ENGINEERING_DECISION = "ENGINEERING_DECISION"
    TECHNICAL_DATASHEET = "TECHNICAL_DATASHEET"
    GENERATED_REFERENCE = "GENERATED_REFERENCE"
    SYNTHETIC_TEST_DATA = "SYNTHETIC_TEST_DATA"


class KnowledgeObject(BaseModel):
    document_id: str = Field(..., description="Unique knowledge document / chunk identifier")
    source: str = Field(..., description="Original source document or standard reference")
    source_type: KnowledgeSourceType = Field(KnowledgeSourceType.GENERATED_REFERENCE)
    title: str = Field(..., description="Descriptive title of the knowledge artifact")
    revision: str = Field("Rev 0", description="Revision code or standard edition year")
    date: str = Field("2026-03-01", description="Document or survey date")
    discipline: str = Field(..., description="Engineering discipline (e.g. Mechanical, Corrosion, Piping)")
    discipline_code: str = Field("B", description="Discipline code A-AL")
    equipment_class: Optional[str] = Field(None, description="Equipment class (e.g. centrifugal_pump, piping)")
    tag: Optional[str] = Field(None, description="Specific equipment tag (e.g. P-101, P-201, CDU-101-01)")
    unit: str = Field("CDU-101", description="Refinery unit name (e.g. CDU-101, CDU-II, VGO-HDT)")
    plant_area: Optional[str] = Field("Crude Distillation Unit", description="Plant area")
    equipment_type: Optional[str] = Field(None, description="Equipment type")
    document_type: Optional[str] = Field("General", description="Document Category/Type")
    section: str = Field("General", description="Section or chapter heading")
    content: str = Field(..., description="Text content containing engineering rules or facts")
    technical_terms: List[str] = Field(default_factory=list, description="Extracted keywords and technical terms")
    applicability: str = Field("Refinery Continuous Service", description="Applicable operating environment")
    authority_level: AuthorityLevel = Field(AuthorityLevel.D, description="A through E authority hierarchy")
    confidence: float = Field(0.95, ge=0.0, le=1.0, description="Extraction or validation confidence")
    page_number: int = Field(1, description="Source page number for citation")
    source_location: str = Field("Page 1", description="Exact page, table, or figure location")
    related_equipment: List[str] = Field(default_factory=list, description="Associated equipment tags")
    related_formula: Optional[str] = Field(None, description="Associated formula ID (e.g. CORR-001, CR-001)")
    related_standard: Optional[str] = Field(None, description="Standard reference (e.g. API 570, ASME B31.3)")
    revision_status: str = Field("CURRENT_APPROVED", description="CURRENT_APPROVED, SUPERSEDED, DRAFT, GENERATED")
    is_official_mrpl: bool = Field(False, description="True ONLY for actual verified MRPL corporate documents")
    disclaimer: str = Field("GENERATED_REFERENCE: NOT_MRPL_OFFICIAL", description="Clear reference disclaimer")


class IngestionLog(BaseModel):
    document_name: str
    pages_total: int
    pages_successfully_parsed: int
    pages_flagged: int
    status: str  # "COMPLETE", "PARTIAL_EXTRACTION", "FAILED"
    authority_level: AuthorityLevel
    chunks_created: int
    ingested_at: float = Field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════
# PROVENANCE & HYBRID RAG MODELS
# ═══════════════════════════════════════════════════════════════

class ChunkProvenance(BaseModel):
    document: str = Field(..., description="Document filename")
    document_id: str = Field(..., description="Document or chunk ID")
    document_type: str = Field(..., description="Document category (e.g. Inspection Reports)")
    page: int = Field(1, description="Page number")
    section: str = Field("General", description="Section or chapter")
    equipment_tag: Optional[str] = Field(None, description="Linked equipment tag (e.g. P-201)")
    plant_area: Optional[str] = Field(None, description="Plant area")
    equipment_type: Optional[str] = Field(None, description="Equipment type")
    date: Optional[str] = Field(None, description="Document date")
    source_file: Optional[str] = Field(None, description="Source file relative or absolute path")


class RetrievalScoreBreakdown(BaseModel):
    semantic_score: float = Field(0.0, description="Dense vector cosine similarity score")
    keyword_score: float = Field(0.0, description="BM25 lexical retrieval score")
    metadata_score: float = Field(0.0, description="Metadata match relevance score")
    hybrid_score: float = Field(0.0, description="Weighted composite hybrid ranking score")
    retrieval_method: str = Field("hybrid", description="Method: hybrid, bm25, semantic, equipment_link")


class RetrievedChunk(BaseModel):
    text: str = Field(..., description="Extracted content text")
    source: ChunkProvenance = Field(..., description="Granular source provenance")
    retrieval: RetrievalScoreBreakdown = Field(..., description="Retrieval score breakdown")
    authority_level: AuthorityLevel = Field(AuthorityLevel.A, description="A through E authority level")
    confidence: float = Field(0.95, description="Confidence rating")
    is_official_mrpl: bool = Field(True, description="True if official MRPL document")


class ConflictEvidence(BaseModel):
    source_document: str
    document_id: str
    page: int
    property_name: str
    value: Any
    raw_statement: str


class ContradictionReport(BaseModel):
    has_conflict: bool = False
    conflict_type: Optional[str] = None  # e.g., "NUMERIC_THICKNESS_DISCREPANCY"
    status: str = "NO_CONFLICT"  # "NO_CONFLICT", "CONFLICT_DETECTED", "REQUIRES_HUMAN_REVIEW"
    evidence_a: Optional[ConflictEvidence] = None
    evidence_b: Optional[ConflictEvidence] = None
    missing_evidence: List[str] = Field(default_factory=list)
    documents_checked: List[str] = Field(default_factory=list)
    human_review_required: bool = False
    explanation: Optional[str] = None


class EquipmentDossier(BaseModel):
    equipment_tag: str
    plant_area: Optional[str] = None
    equipment_type: Optional[str] = None
    total_documents: int = 0
    categories_covered: List[str] = Field(default_factory=list)
    documents_by_category: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    retrieved_evidence: List[RetrievedChunk] = Field(default_factory=list)
    key_properties: Dict[str, Any] = Field(default_factory=dict)
    contradiction_report: ContradictionReport = Field(default_factory=ContradictionReport)
    summary: Optional[str] = None


class HybridSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(5, description="Number of results to return")
    equipment_tag: Optional[str] = Field(None, description="Equipment / Asset tag filter (e.g. P-201, PSV-301)")
    asset_id: Optional[str] = Field(None, description="Asset ID filter")
    asset_class: Optional[str] = Field(None, description="Asset class filter (e.g. PUMP, VALVE)")
    process_unit: Optional[str] = Field(None, description="Process unit filter (e.g. CDU-II, Tank Farm)")
    plant_area: Optional[str] = Field(None, description="Plant area filter")
    refinery: Optional[str] = Field(None, description="Refinery filter")
    organization: Optional[str] = Field(None, description="Organization filter (e.g. MRPL)")
    component: Optional[str] = Field(None, description="Component filter (e.g. Casing, Impeller)")
    inspection_location: Optional[str] = Field(None, description="Inspection location filter")
    measurement_type: Optional[str] = Field(None, description="Measurement type filter")
    document_type: Optional[str] = Field(None, description="Document type / category filter")
    equipment_type: Optional[str] = Field(None, description="Equipment type filter")
    date: Optional[str] = Field(None, description="Date filter")
    revision: Optional[str] = Field(None, description="Revision filter")
    approval_status: Optional[str] = Field(None, description="Approval status filter")
    source_file: Optional[str] = Field(None, description="Source file filter")
    semantic_weight: float = Field(0.40, description="Weight for semantic dense similarity")
    keyword_weight: float = Field(0.45, description="Weight for BM25 keyword score")
    metadata_weight: float = Field(0.15, description="Weight for metadata matching")
