from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    EQUIPMENT = "EQUIPMENT"
    SYSTEM = "SYSTEM"
    INSTRUMENT = "INSTRUMENT"
    VALVE = "VALVE"
    VESSEL = "VESSEL"
    TANK = "TANK"
    DOCUMENT = "DOCUMENT"
    PROCEDURE = "PROCEDURE"
    MOC = "MOC"
    STANDARD = "STANDARD"
    UNKNOWN = "UNKNOWN"


class EntityResolutionStatus(str, Enum):
    FOUND_IN_MRPL_KB = "FOUND_IN_MRPL_KB"
    FOUND_IN_ASSET_REGISTRY = "FOUND_IN_ASSET_REGISTRY"
    NOT_FOUND_IN_KB = "NOT_FOUND_IN_KB"
    NOT_FOUND = "NOT_FOUND"
    NO_ENTITY_DETECTED = "NO_ENTITY_DETECTED"


class DomainCategory(str, Enum):
    MRPL_ENGINEERING = "MRPL ENGINEERING"
    GENERAL = "GENERAL"
    SOFTWARE = "SOFTWARE"


class KnowledgeSourceType(str, Enum):
    MRPL_LOCAL_KNOWLEDGE_BASE = "MRPL LOCAL KNOWLEDGE BASE"
    MRPL_ASSET_REGISTRY = "MRPL ASSET REGISTRY"
    UPLOADED_DOCUMENT = "UPLOADED DOCUMENT"
    GENERAL_PRETRAINED_KNOWLEDGE = "GENERAL PRETRAINED KNOWLEDGE"


class MRPLEntityRecord(BaseModel):
    """
    Structured entity record from the local MRPL Knowledge Base.
    Equipment Master documents serve as primary authority.
    """
    canonical_name: str = Field(..., description="Canonical entity tag or name (e.g. P-201)")
    entity_type: EntityType = Field(EntityType.EQUIPMENT, description="Category of entity")
    aliases: List[str] = Field(default_factory=list, description="Known aliases and name variants")
    equipment_tag: Optional[str] = Field(None, description="Primary equipment tag if applicable")
    equipment_type: Optional[str] = Field(None, description="Detailed equipment description")
    plant_area: Optional[str] = Field(None, description="Refinery plant area or unit (e.g. CDU-II)")
    domain: str = Field("MRPL Engineering", description="Operational domain")
    source_document: str = Field(..., description="Primary authoritative document filename")
    document_id: Optional[str] = Field(None, description="Document ID of primary authority")
    page_number: int = Field(1, description="Page number of authoritative definition")
    status: str = Field("KNOWN", description="Knowledge status: KNOWN, DECOMMISSIONED, etc.")
    related_document_ids: List[str] = Field(default_factory=list, description="IDs of all connected documents")
    related_document_types: List[str] = Field(default_factory=list, description="Types of connected documents")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted key technical properties")


class EntityResolutionResult(BaseModel):
    """
    Result of resolving an entity mention from user query against MRPL index and Asset Registry.
    """
    entity: Optional[str] = Field(None, description="Primary entity identifier (e.g. P-201)")
    raw_entity: Optional[str] = Field(None, description="Raw entity mention extracted from query")
    canonical_name: Optional[str] = Field(None, description="Canonical resolved name")
    entity_type: EntityType = Field(EntityType.UNKNOWN, description="Entity type: EQUIPMENT, VALVE, etc.")
    mrpl_kb_status: str = Field("NONE", description="FOUND, NOT_FOUND, or NONE")
    asset_registry_status: str = Field("NOT_CHECKED", description="FOUND, NOT_FOUND, or NOT_CHECKED")
    resolution_status: EntityResolutionStatus = Field(EntityResolutionStatus.NO_ENTITY_DETECTED, description="Resolution status enum")
    confidence: float = Field(0.99, ge=0.0, le=1.0, description="Confidence of entity detection and resolution")
    matched_documents: List[str] = Field(default_factory=list, description="Authoritative MRPL documents matching entity")
    matched_entity: Optional[MRPLEntityRecord] = Field(None, description="Detailed MRPL entity record if found in KB")
    asset_record: Optional[Dict[str, Any]] = Field(None, description="Asset Registry metadata record if found in Asset Registry")
    is_mrpl_entity: bool = Field(False, description="True if verified present in local MRPL Knowledge Base or Asset Registry")
    resolution_message: str = Field("No entity resolution performed", description="Human-readable resolution trace")
    all_extracted_tags: List[str] = Field(default_factory=list, description="All entity tags extracted from query")
    resolved_entities: List[str] = Field(default_factory=list, description="List of verified MRPL entities found")
    unresolved_entities: List[str] = Field(default_factory=list, description="List of unindexed/unknown entities found")
    target_entity: Optional[str] = Field(None, description="Primary target entity of the query")
    is_generic_tag_inquiry: bool = Field(False, description="True if query asks generic nomenclature/tag convention question")


class ContextGuardDecision(BaseModel):
    """
    Context Guard policy decision for routing and evidence handling.
    """
    is_mrpl_entity: bool = Field(False, description="True if query references a verified MRPL entity")
    entity_tag: Optional[str] = Field(None, description="Target equipment or entity tag")
    knowledge_precedence: str = Field("MRPL_AUTHORITATIVE", description="MRPL_AUTHORITATIVE, MRPL_ASSET_REGISTRY, UNKNOWN_ENTITY_BLOCKED, or GENERAL_UNVERIFIED_FALLBACK")
    should_retrieve_rag: bool = Field(True, description="Whether Hybrid RAG retrieval is required")
    unknown_entity_blocked: bool = Field(False, description="True if unknown entity was blocked from hallucinating")
    allow_unverified_fallback: bool = Field(False, description="True if user explicitly requested general LLM fallback")
    guarded_response: Optional[str] = Field(None, description="Deterministic guard response for unknown entities")
    context_directive: str = Field("", description="System prompt directive enforcing local evidence precedence or unverified warning")
    warning_banner: Optional[str] = Field(None, description="Visible disclaimer banner for UI")
    context_guard_status: Optional[str] = Field(None, description="Context Guard status text (e.g. LOCAL ENTITY NOT RESOLVED)")


