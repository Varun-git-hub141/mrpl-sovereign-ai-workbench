# backend/services/evidence/reconciliation_models.py
"""
MRPL Sovereign AI Workbench — Phase 3: Industrial Evidence Reconciliation Models.
Defines formal data structures for multi-observation extraction, provenance,
relational classification, conflict representation, and external policy applicability.

Key Invariants:
- Separation of Observation, Reconciliation, and Decision.
- Zero invented numeric consistency or authority scores (categorical representations only).
- Non-destructive observation retention (raw observations are never deleted or averaged).
- Zero hardcoded organizational applicability policies.
- Derived values require explicit source observation lineage and verified assumptions.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# 1. Enums & Categorical States
# ─────────────────────────────────────────────────────────────

class AuthorityTier(str, Enum):
    APPROVED_AUTHORITATIVE = "APPROVED_AUTHORITATIVE" # Statutory baseline, certified NDT Level III survey
    APPROVED = "APPROVED"                             # Verified engineering datasheet, signed MOC record
    INTERNAL = "INTERNAL"                             # Internal operational logs, maintenance shift reports
    INFORMAL = "INFORMAL"                             # Scratchpad notes, unverified conversational notes
    UNKNOWN = "UNKNOWN"                               # Missing or unparseable authority tier


class ApprovalStatus(str, Enum):
    APPROVED = "APPROVED"                             # Formally signed off / implemented
    DRAFT = "DRAFT"                                   # Unapproved draft / proposed modification
    SUPERSEDED = "SUPERSEDED"                         # Officially retired by an active MOC
    PENDING_MOC = "PENDING_MOC"                       # In change-control review
    UNKNOWN = "UNKNOWN"                               # Unstated approval status


class ExtractionMethod(str, Enum):
    STRUCTURED_JSON = "STRUCTURED_JSON"               # Direct key extraction from local KB JSON
    REGEX_PARSER = "REGEX_PARSER"                     # Deterministic regex pattern match
    TABLE_EXTRACTOR = "TABLE_EXTRACTOR"               # Tabular grid parser
    LLM_EXTRACTION = "LLM_EXTRACTION"                 # Source-grounded parser (Zero synthesis)


class EvidenceSearchStatus(str, Enum):
    EVIDENCE_SEARCH_NOT_PERFORMED = "EVIDENCE_SEARCH_NOT_PERFORMED"
    EVIDENCE_SEARCH_IN_PROGRESS = "EVIDENCE_SEARCH_IN_PROGRESS"
    EVIDENCE_SEARCH_COMPLETED = "EVIDENCE_SEARCH_COMPLETED"
    SUPPORTING_EVIDENCE_FOUND = "SUPPORTING_EVIDENCE_FOUND"
    SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH = "SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH"


class DerivationStatus(str, Enum):
    CALCULATED = "CALCULATED"
    INSUFFICIENT_INPUT = "INSUFFICIENT_INPUT"
    ASSUMPTIONS_MISSING = "ASSUMPTIONS_MISSING"
    FORMULA_NOT_APPLICABLE = "FORMULA_NOT_APPLICABLE"


class RelationshipType(str, Enum):
    TEMPORAL_PROGRESSION = "TEMPORAL_PROGRESSION"                   # Sequential degradation at same CML over time
    SPATIALLY_DISTINCT = "SPATIALLY_DISTINCT"                       # Different inspection points (CML-01 vs CML-02)
    CORROBORATING = "CORROBORATING"                                 # Independent sources reporting matching values
    SUPERSEDED_REVISION = "SUPERSEDED_REVISION"                     # Approved MOC supersedes older approved revision
    UNAPPROVED_DRAFT = "UNAPPROVED_DRAFT"                           # Draft revision exists alongside approved revision
    SIMULTANEOUS_DISCREPANCY = "SIMULTANEOUS_DISCREPANCY"           # Conflicting values in overlapping context
    ANOMALOUS_PROGRESSION_CANDIDATE = "ANOMALOUS_PROGRESSION_CANDIDATE" # Apparent growth; search incomplete/unperformed
    ANOMALOUS_PROGRESSION = "ANOMALOUS_PROGRESSION"                 # Search completed; unexplained physical growth confirmed
    AUTHORITY_DISCREPANCY = "AUTHORITY_DISCREPANCY"                 # Disagreement across different authority tiers
    TEMPORAL_ORDER_UNKNOWN = "TEMPORAL_ORDER_UNKNOWN"               # Missing timestamp prevents sequencing
    REVISION_UNKNOWN = "REVISION_UNKNOWN"                           # Missing revision prevents version hierarchy
    SUPERSEDENCE_UNCERTAIN = "SUPERSEDENCE_UNCERTAIN"               # Ambiguous MOC / version lineage


class ConsistencyState(str, Enum):
    CONSISTENT = "CONSISTENT"                                       # All observations align or corroborate
    TEMPORALLY_EXPLAINED = "TEMPORALLY_EXPLAINED"                   # Differences explained by valid chronological degradation
    SPATIALLY_DISTINCT = "SPATIALLY_DISTINCT"                       # Differences explained by distinct CML points
    CONFLICTING = "CONFLICTING"                                     # Mutually exclusive simultaneous observations
    ANOMALOUS = "ANOMALOUS"                                         # Confirmed physical anomaly after search
    UNCERTAIN = "UNCERTAIN"                                         # Missing metadata creates ambiguity
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"                   # Inadequate observations to evaluate


class ReconciliationStatus(str, Enum):
    TEMPORALLY_MAPPED = "TEMPORALLY_MAPPED"                         # Clean chronological degradation trend mapped
    SPATIALLY_MAPPED = "SPATIALLY_MAPPED"                           # Distinct physical locations mapped
    NON_CONFLICTING = "NON_CONFLICTING"                             # Distinct entities or corroborating values
    UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"                     # Active disagreement between observations
    ANOMALY_DETECTED = "ANOMALY_DETECTED"                           # Unexplained physical growth or anomaly
    SUPERSEDENCE_UNCERTAIN = "SUPERSEDENCE_UNCERTAIN"               # Unclear revision supersedence
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"                   # Insufficient data points
    REQUIRES_HUMAN_INVESTIGATION = "REQUIRES_HUMAN_INVESTIGATION"   # Flagged when downstream policy gates on conflict


class ConflictSeverity(str, Enum):
    CRITICAL_SAFETY = "CRITICAL_SAFETY"                             # Classified by downstream policy for safety parameters
    OPERATIONAL_DRIFT = "OPERATIONAL_DRIFT"                         # Variance in operating parameters (flow, pressure)
    INFORMATIONAL_MISMATCH = "INFORMATIONAL_MISMATCH"               # Variance in non-critical metadata (color, vendor)
    UNCLASSIFIED = "UNCLASSIFIED"                                   # Default state before downstream policy evaluation


class ApplicabilityStatus(str, Enum):
    EVALUATED_APPLICABLE = "EVALUATED_APPLICABLE"                   # Policy selected active candidate observation
    UNRESOLVED = "UNRESOLVED"                                       # Policy could not resolve single candidate
    NOT_EVALUATED = "NOT_EVALUATED"                                 # No external applicability policy provided


# ─────────────────────────────────────────────────────────────
# 2. Core Observation Models
# ─────────────────────────────────────────────────────────────

class EvidenceObservation(BaseModel):
    """
    Exact, source-grounded observation extracted from a single document.
    Captures what the source reports without probabilistic guessing or averaging.
    """
    observation_id: str = Field(..., description="Deterministic unique identifier (e.g. OBS-P201-THICK-001)")
    entity_tag: str = Field(..., description="Target equipment or component tag (e.g. P-201, PSV-201)")
    property_name: str = Field(..., description="Canonical property key (e.g. wall_thickness, design_pressure, operating_status)")
    value: Any = Field(..., description="Raw observed value (e.g. 4.5, '4.4 - 4.6', 'Fit for service', 'Duplex 2205')")
    unit: Optional[str] = Field(None, description="Physical engineering unit (e.g. mm, bar, mm/s, mm/year)")
    
    # Spatial & Methodological Parameters
    measurement_location: Optional[str] = Field(None, description="CML/TML point (e.g. CML-01 Suction, CML-02 Volute)")
    measurement_method: Optional[str] = Field(None, description="Inspection method (e.g. UT Pulse-Echo, Radiography, IRIS)")
    
    # Temporal & Document Provenance
    observation_date: Optional[str] = Field(None, description="ISO 8601 date string (e.g. 2024-06-01)")
    source_document: str = Field(..., description="Source document filename or URI")
    document_id: Optional[str] = Field(None, description="Tracking ID (e.g. MRPL-INSP-2024-P201)")
    document_type: str = Field("General", description="Category: Inspection Reports, Equipment Master, MOC Decisions")
    page_number: int = Field(1, description="Source page number")
    section: str = Field("General", description="Section or chapter title")
    source_span: Optional[str] = Field(None, description="Exact character span or table cell reference")
    
    # Revision & Authority Parameters
    revision_number: Optional[str] = Field(None, description="Revision identifier (e.g. Rev 0, Rev 2, Draft B)")
    approval_status: ApprovalStatus = Field(ApprovalStatus.UNKNOWN, description="Approval classification")
    authority_tier: AuthorityTier = Field(AuthorityTier.UNKNOWN, description="Categorical authority tier")
    extraction_method: ExtractionMethod = Field(ExtractionMethod.STRUCTURED_JSON, description="Extraction mechanism")
    raw_statement: str = Field(..., description="Verbatim textual excerpt containing this observation")


class MalformedObservationRecord(BaseModel):
    """
    Captures input data that failed validation without crashing the extraction pipeline.
    """
    raw_input: Any = Field(..., description="Original raw data that caused validation failure")
    error_reason: str = Field(..., description="Description of the validation failure")
    source_document: Optional[str] = Field(None, description="Source document if identified")
    entity_tag: Optional[str] = Field(None, description="Target entity if identified")


class ObservationExtractionResult(BaseModel):
    """
    Result container for the observation extraction layer.
    """
    observations: List[EvidenceObservation] = Field(default_factory=list, description="Validated observations")
    malformed_records: List[MalformedObservationRecord] = Field(default_factory=list, description="Rejected records")
    warnings: List[str] = Field(default_factory=list, description="Extraction warnings and anomalies")
    total_extracted: int = Field(0, description="Count of successfully extracted observations")


class DerivedObservation(BaseModel):
    """
    Encapsulates a derived value computed from raw observations with complete derivation lineage.
    Never replaces or modifies raw observations.
    """
    derived_id: str = Field(..., description="Unique derived observation identifier (e.g. DERIV-CR-P201-001)")
    property_name: str = Field(..., description="Derived property name (e.g. corrosion_rate, remaining_life)")
    derived_value: Optional[float] = Field(None, description="Computed numerical result (None if derivation blocked)")
    unit: str = Field(..., description="Engineering unit (e.g. mm/year, years)")
    derivation_status: DerivationStatus = Field(DerivationStatus.CALCULATED, description="Status of mathematical calculation")
    source_observation_ids: List[str] = Field(..., description="List of raw EvidenceObservation IDs consumed")
    derivation_method: str = Field(..., description="Explicit formula identifier (e.g. API 570 Long-Term Metal Loss)")
    input_parameters: Dict[str, Any] = Field(..., description="Exact numerical inputs and units consumed")
    time_interval_years: Optional[float] = Field(None, description="Elapsed time interval in years")
    source_verified_assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions verified directly from source evidence or caller specification (No AI inventions)"
    )


class ReconciliationRelationship(BaseModel):
    """
    Evaluated relationship between two or more observations.
    """
    relationship_id: str = Field(..., description="Unique relationship identifier")
    property_name: str = Field(..., description="Associated engineering property")
    relationship_type: RelationshipType = Field(..., description="Classified inter-observation relationship")
    observation_ids: List[str] = Field(..., description="Observation IDs participating in this relationship")
    evidence_search_status: EvidenceSearchStatus = Field(
        EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
        description="Lifecycle state of supporting evidence retrieval"
    )
    explanation: str = Field(..., description="Technical rationale for classification")
    is_anomaly: bool = Field(False, description="Whether this relationship represents an engineering anomaly")


class EvidenceConflict(BaseModel):
    """
    Represents an unresolved discrepancy between observations.
    Separates conflict existence from downstream task safety classification.
    """
    conflict_id: str = Field(..., description="Unique conflict identifier")
    property_name: str = Field(..., description="Contested engineering property")
    entity_tag: str = Field(..., description="Contested asset tag")
    severity: ConflictSeverity = Field(ConflictSeverity.UNCLASSIFIED, description="Assigned by downstream task policy")
    conflicting_observation_ids: List[str] = Field(..., description="IDs of all mutually conflicting observations")
    conflict_description: str = Field(..., description="Detailed description of the discrepancy")
    required_resolution_evidence: List[str] = Field(
        default_factory=list,
        description="Evidence items needed to reconcile conflict (e.g. 'Verify original NDT calibration log')"
    )


class PropertyTimeline(BaseModel):
    """
    Chronological series of observations for a single property on a single entity.
    """
    property_name: str
    entity_tag: str
    observations_chronological: List[EvidenceObservation] = Field(default_factory=list)
    derived_progressions: List[DerivedObservation] = Field(default_factory=list)
    temporal_trend: Optional[str] = Field(None, description="MONOTONIC_DECREASE, STABLE, FLUCTUATING, UNKNOWN")
    has_anomalies: bool = False
    anomaly_descriptions: List[str] = Field(default_factory=list)


class ApplicabilityPolicy(BaseModel):
    """
    Formal specification for an external task applicability policy.
    Phase 3 remains policy-driven and does not hardcode internal organizational rules.
    """
    policy_identifier: str = Field(..., description="Unique policy identifier (e.g. STATUTORY_MANDATORY_BASELINE_V1)")
    description: Optional[str] = Field(None, description="Policy description")
    target_properties: Optional[List[str]] = Field(None, description="Properties evaluated by this policy (None for all)")
    preferred_authority_tiers: Optional[List[AuthorityTier]] = Field(None, description="Ranked preference of authority tiers")
    preferred_approval_statuses: Optional[List[ApprovalStatus]] = Field(None, description="Ranked preference of approval statuses")
    require_verified_date: bool = Field(False, description="Whether valid date is required for selection")
    select_latest_dated: bool = Field(False, description="When multiple candidates tie, select latest valid observation date")


class ApplicableObservationContext(BaseModel):
    """
    Preserves candidate applicability determinations driven by external task policy.
    Does not imply unselected observations are false.
    """
    entity_tag: str
    property_name: str
    applicability_status: ApplicabilityStatus = Field(ApplicabilityStatus.NOT_EVALUATED, description="Policy evaluation status")
    selected_observation_id: Optional[str] = Field(None, description="Selected observation ID (None if NOT_EVALUATED)")
    selection_basis: Optional[str] = Field(None, description="External policy rule applied")
    policy_identifier: Optional[str] = Field(None, description="External policy identifier (None if not provided)")
    applicability_rationale: Optional[str] = Field(None, description="Policy justification")
    alternative_observation_ids: List[str] = Field(default_factory=list, description="All other valid preserved observations")



class ReconciliationResult(BaseModel):
    """
    Complete output of Phase 3 Industrial Evidence Reconciliation.
    """
    task_id: str
    entity_scope: List[str] = Field(default_factory=list)
    consistency_state: ConsistencyState = Field(..., description="Categorical consistency state (No numeric score)")
    reconciliation_status: ReconciliationStatus = Field(..., description="Overall reconciliation classification")
    
    # Observations & Relationships
    all_observations: List[EvidenceObservation] = Field(default_factory=list)
    relationships: List[ReconciliationRelationship] = Field(default_factory=list)
    property_timelines: Dict[str, PropertyTimeline] = Field(default_factory=dict)
    derived_observations: List[DerivedObservation] = Field(default_factory=list)
    
    # Conflict Management
    active_conflicts: List[EvidenceConflict] = Field(default_factory=list)
    unresolved_conflicts: List[EvidenceConflict] = Field(default_factory=list)
    
    # Policy-Driven Applicability Context
    applicable_contexts: List[ApplicableObservationContext] = Field(default_factory=list)
    
    requires_human_investigation: bool = Field(False, description="Flagged when downstream policy gates on conflict")
    reconciliation_summary: str = Field(..., description="Technical summary of reconciliation findings")
    reconciled_at: float = Field(..., description="Unix evaluation timestamp")
