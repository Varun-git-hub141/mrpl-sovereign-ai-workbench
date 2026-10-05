from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .model_profile import CapabilityVector


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InputModality(str, Enum):
    TEXT = "text"
    VISION = "vision"
    DOCUMENT_PDF = "document_pdf"
    SCANNED_PDF = "scanned_pdf"
    SPREADSHEET = "spreadsheet"
    SOURCE_CODE = "source_code"
    MULTIMODAL = "multimodal"


class TaskType(str, Enum):
    CODING = "coding"
    GENERIC_CODING = "generic_coding"
    ENGINEERING_CODING = "engineering_coding"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    MULTIMODAL_DOCUMENT_ANALYSIS = "multimodal_document_analysis"
    MULTIMODAL_ENGINEERING_ANALYSIS = "multimodal_engineering_analysis"
    DOCUMENT_QA = "document_qa"
    OCR_EXTRACTION = "ocr_extraction"
    VISION_P_AND_ID = "vision_p_and_id"
    ENGINEERING_CALCULATION = "engineering_calculation"
    EQUIPMENT_APPROVAL = "equipment_approval"
    POLICY_COMPLIANCE = "policy_compliance"
    MEMO_SUMMARIZATION = "memo_summarization"
    INTERNAL_CORRESPONDENCE = "internal_correspondence"
    GENERAL_REASONING = "general_reasoning"
    UNKNOWN_MRPL_ENTITY = "unknown_mrpl_entity"
    MRPL_CONTEXT_BLOCKED = "mrpl_context_blocked"


class TaskProfile(BaseModel):
    request_id: Optional[str] = Field(None, description="Unique request trace identifier")
    task_type: TaskType = Field(TaskType.GENERAL_REASONING, description="Classified task domain")
    intent: str = Field("general_query", description="Specific granular intent identified from query")
    risk: RiskLevel = Field(RiskLevel.LOW, description="Determined or overridden operational risk")
    modality: InputModality = Field(InputModality.TEXT, description="Detected input modality")
    complexity: float = Field(0.5, ge=0.0, le=1.0, description="Estimated task complexity level")
    required_capabilities: CapabilityVector = Field(default_factory=CapabilityVector, description="Capability demand vector")
    required_tools: List[str] = Field(default_factory=list, description="List of required tools/sandboxes")
    requires_verification: bool = Field(False, description="Flag indicating independent multi-model verification requirement")
    context_requirement: int = Field(2048, description="Estimated required context window size in tokens")
    extracted_signals: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic signals and matched keywords")
    entity_name: Optional[str] = Field(None, description="Extracted entity identifier (e.g. P-201)")
    entity_type: Optional[str] = Field(None, description="Entity category: EQUIPMENT, SYSTEM, VALVE, etc.")
    entity_resolution_status: str = Field("NO_ENTITY_DETECTED", description="FOUND_IN_MRPL_KB, NOT_FOUND_IN_KB, NO_ENTITY_DETECTED")
    domain: str = Field("GENERAL", description="MRPL ENGINEERING, GENERAL, or SOFTWARE")
    knowledge_source: str = Field("GENERAL PRETRAINED KNOWLEDGE", description="MRPL LOCAL KNOWLEDGE BASE, UPLOADED DOCUMENT, or GENERAL PRETRAINED KNOWLEDGE")
    retrieval_mode: str = Field("NONE", description="HYBRID, KEYWORD, VECTOR, or NONE")
    reasoning_stage: str = Field("DIRECT EXECUTION", description="AFTER RETRIEVAL or DIRECT EXECUTION")

