from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    EQUIPMENT = "EQUIPMENT"
    VALVE = "VALVE"
    CONTROL_VALVE = "CONTROL_VALVE"
    SAFETY_VALVE = "SAFETY_VALVE"
    DRAIN_VALVE = "DRAIN_VALVE"
    CHECK_VALVE = "CHECK_VALVE"
    INSTRUMENT = "INSTRUMENT"
    TANK = "TANK"
    STRAINER = "STRAINER"
    LINE_SEGMENT = "LINE_SEGMENT"
    HEADER = "HEADER"
    VESSEL = "VESSEL"
    COLUMN = "COLUMN"
    HEAT_EXCHANGER = "HEAT_EXCHANGER"
    PUMP = "PUMP"


class EdgeRelationship(str, Enum):
    FROM = "FROM"
    TO = "TO"
    CONNECTED_TO = "CONNECTED_TO"
    CONTROLS = "CONTROLS"
    PROTECTS = "PROTECTS"
    ISOLATES = "ISOLATES"
    MEASURES = "MEASURES"
    RELIEVES_TO = "RELIEVES_TO"
    FEEDS = "FEEDS"
    DISCHARGES_TO = "DISCHARGES_TO"
    BYPASSES = "BYPASSES"


class QueryIntent(str, Enum):
    ISOLATION = "ISOLATION"
    UPSTREAM = "UPSTREAM"
    DOWNSTREAM = "DOWNSTREAM"
    PROTECTION = "PROTECTION"
    INSTRUMENTATION = "INSTRUMENTATION"
    PSV_DISCHARGE = "PSV_DISCHARGE"
    CONNECTED_EQUIPMENT = "CONNECTED_EQUIPMENT"
    FLOW_PATH = "FLOW_PATH"
    FAILURE_MODE = "FAILURE_MODE"
    GENERAL_OVERVIEW = "GENERAL_OVERVIEW"


class TraversalOperation(str, Enum):
    TRAVERSE_INCOMING = "TRAVERSE_INCOMING"
    TRAVERSE_OUTGOING = "TRAVERSE_OUTGOING"
    BOUNDARY_SEARCH = "BOUNDARY_SEARCH"
    RELATIONSHIP_SEARCH = "RELATIONSHIP_SEARCH"
    SHORTEST_PATH = "SHORTEST_PATH"
    DIRECT_NEIGHBORS = "DIRECT_NEIGHBORS"


class PIDProvenanceRecord(BaseModel):
    drawing_id: str
    drawing_number: Optional[str] = None
    document_id: Optional[str] = None
    source_file: Optional[str] = None
    page_number: int = 1
    revision: Optional[str] = None
    section: Optional[str] = None
    evidence_text: Optional[str] = None
    confidence: float = 1.0


class PIDNode(BaseModel):
    node_id: str = Field(..., description="Unique node identifier")
    tag: str = Field(..., description="Standard tag (e.g. P-101, PCV-101, PSV-101, TI-101)")
    type: NodeType = Field(NodeType.EQUIPMENT, description="Component classification")
    description: str = Field(..., description="Engineering component description")
    location: str = Field("CDU-101", description="Physical unit or area")
    source_page: int = Field(1, description="P&ID source page number")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Visual/OCR extraction confidence")
    specs: Dict[str, Any] = Field(default_factory=dict, description="Design specifications, set points, sizes")
    normal_state: str = Field("OPERATIONAL", description="Normally Open, Closed, Energized, Running")
    document_id: Optional[str] = Field(None, description="Source document ID")
    drawing_number: Optional[str] = Field(None, description="Official drawing number")
    source_file: Optional[str] = Field(None, description="Source JSON/PDF filename")
    revision: Optional[str] = Field(None, description="Drawing revision")


class PIDEdge(BaseModel):
    source_tag: str = Field(..., description="Origin node tag")
    target_tag: str = Field(..., description="Destination node tag")
    relationship: EdgeRelationship = Field(EdgeRelationship.CONNECTED_TO, description="Semantic relationship")
    line_spec: Optional[str] = Field("10-CDU-PL-101", description="Line number and piping class")
    flow_direction: str = Field("FORWARD", description="FORWARD, BIDIRECTIONAL, RELIEF")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence")
    notes: Optional[str] = None
    document_id: Optional[str] = Field(None, description="Source document ID")
    drawing_number: Optional[str] = Field(None, description="Official drawing number")
    source_file: Optional[str] = Field(None, description="Source JSON/PDF filename")


class PIDGraph(BaseModel):
    drawing_id: str = Field("CDU-P-101", description="P&ID drawing number / ID")
    drawing_title: str = Field("Crude Feed Pump P-101 System", description="Title block description")
    system: str = Field("Crude Distillation Unit (CDU-101)", description="Process system name")
    document_id: Optional[str] = Field(None, description="Knowledge base document ID")
    drawing_number: Optional[str] = Field(None, description="Official drawing number (e.g. MRPL-DWG-PID-CDU-100-REV4)")
    revision: Optional[str] = Field("Rev 1", description="Drawing revision")
    plant_area: Optional[str] = Field("CDU", description="Plant area")
    source_file: Optional[str] = Field(None, description="Source file in knowledge base")
    page_number: int = Field(1, description="Drawing sheet / page number")
    nodes: List[PIDNode] = Field(default_factory=list)
    edges: List[PIDEdge] = Field(default_factory=list)
    critical_loops: List[Dict[str, Any]] = Field(default_factory=list)
    safety_devices: List[Dict[str, Any]] = Field(default_factory=list)
    general_notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PIDQueryPlan(BaseModel):
    intent: QueryIntent
    target_entity: Optional[str] = None
    drawing_id: Optional[str] = None
    selected_drawing: Optional[str] = None
    alternate_drawings: List[str] = Field(default_factory=list)
    resolution_reason: Optional[str] = None
    ambiguity_status: str = "UNAMBIGUOUS"  # UNAMBIGUOUS, RESOLVED_PRIMARY_CONTEXT, EXPLICIT_USER_SPECIFIED, AMBIGUOUS_MULTI_DRAWING
    relationship_types: List[EdgeRelationship] = Field(default_factory=list)
    direction: str = "OUTGOING"  # INCOMING, OUTGOING, BOTH
    max_depth: int = 5
    filters: Dict[str, Any] = Field(default_factory=dict)
    operation: TraversalOperation = TraversalOperation.DIRECT_NEIGHBORS
    is_resolved: bool = True
    unresolved_reason: Optional[str] = None


class PIDTraversalPath(BaseModel):
    source_tag: str
    target_tag: str
    path: List[str] = Field(default_factory=list)
    edges: List[PIDEdge] = Field(default_factory=list)
    relationship_chain: List[str] = Field(default_factory=list)
    distance: int = 0


class PIDQueryResultStatus(str, Enum):
    DIRECT_SOURCE_RELATIONSHIP = "DIRECT_SOURCE_RELATIONSHIP"
    DERIVED_GRAPH_TRAVERSAL = "DERIVED_GRAPH_TRAVERSAL"
    AMBIGUOUS_MULTI_DRAWING = "AMBIGUOUS_MULTI_DRAWING"
    UNRESOLVED = "UNRESOLVED"
    INSUFFICIENT_SOURCE_DATA = "INSUFFICIENT_SOURCE_DATA"


class PIDQueryRequest(BaseModel):
    question: str
    drawing_id: Optional[str] = None
    target_equipment: Optional[str] = None


class PIDQueryResponse(BaseModel):
    question: str
    drawing_id: str
    answer: str
    direct_nodes_involved: List[str] = Field(default_factory=list)
    path_trace: List[str] = Field(default_factory=list)
    engineering_rationale: str = ""
    evidence_citations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0
    # Extended Phase 2 Knowledge Graph Fields
    query_plan: Optional[PIDQueryPlan] = None
    status: PIDQueryResultStatus = PIDQueryResultStatus.DIRECT_SOURCE_RELATIONSHIP
    selected_drawing: Optional[str] = None
    alternate_drawings: List[str] = Field(default_factory=list)
    ambiguity_status: Optional[str] = None
    traversal_paths: List[PIDTraversalPath] = Field(default_factory=list)
    matched_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    provenance_records: List[PIDProvenanceRecord] = Field(default_factory=list)
    safety_boundary_note: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# PHASE 3 — EVIDENCE ARCHITECTURE INTEGRATION MODELS
# ═══════════════════════════════════════════════════════════════

class EvidenceClassification(str, Enum):
    TOPOLOGY_FACT = "TOPOLOGY_FACT"
    DOCUMENTARY_EVIDENCE = "DOCUMENTARY_EVIDENCE"
    CALCULATED_RESULT = "CALCULATED_RESULT"
    ENGINEERING_CONCLUSION = "ENGINEERING_CONCLUSION"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"


class EvidenceTier(str, Enum):
    PURE_TOPOLOGY = "PURE_TOPOLOGY"                          # Tier A: Graph only, no RAG / contract needed
    TOPOLOGY_AND_EVIDENCE = "TOPOLOGY_AND_EVIDENCE"          # Tier B: Topology + Documentary RAG evidence
    ENGINEERING_DECISION = "ENGINEERING_DECISION"            # Tier C: Safety/LOTO/adequacy gated by Evidence Contract & Sufficiency


class EvidenceClaimItem(BaseModel):
    claim_text: str
    classification: EvidenceClassification
    source_citation: Optional[str] = None
    document_id: Optional[str] = None
    verified: bool = True
    notes: Optional[str] = None


class PIDEnhancedEvidenceResponse(BaseModel):
    question: str
    target_entity: Optional[str] = None
    selected_drawing: Optional[str] = None
    alternate_drawings: List[str] = Field(default_factory=list)
    evidence_tier: EvidenceTier = EvidenceTier.PURE_TOPOLOGY
    
    # Layer 1: P&ID Topology
    topology: PIDQueryResponse
    
    # Layer 2: Engineering Evidence & Debt (Evaluated for Tier B & C)
    contract: Optional[Dict[str, Any]] = None
    assessment: Optional[Dict[str, Any]] = None
    evidence_debt: Optional[Dict[str, Any]] = None
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Itemized Evidence Claims (Topology vs Documentary vs Conclusion vs Unverified)
    evidence_claims: List[EvidenceClaimItem] = Field(default_factory=list)
    
    # Layer 3: Engineering Decision & Safety Gating
    safety_decision: str = "TOPOLOGY_ONLY_NO_CONCLUSION"  # APPROVED_WITH_EVIDENCE, BLOCKED_INSUFFICIENT_EVIDENCE, TOPOLOGY_ONLY_NO_CONCLUSION, BLOCKED_BY_CONTEXT_GUARD
    safety_blockers: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    final_synthesis: str = ""

