# backend/services/evidence/__init__.py
"""
MRPL Sovereign AI Workbench — Evidence Contract & Requirement Framework.
Defines formal evidence contracts, requirement models, and deterministic requirement engines.
"""

from backend.services.evidence.evidence_models import (
    EvidenceType,
    AuthorityLevel,
    EvidenceModality,
    EvidenceRequirement,
    EvidenceContract,
    ContractGenerationContext,
    SufficiencyStatus,
    EvidenceDebtSeverity,
    EvidenceDebtItem,
    EvidenceDebt,
    EvidenceAssessment,
)
from backend.services.evidence.evidence_contract import EvidenceContractValidator
from backend.services.evidence.evidence_requirement_engine import EvidenceRequirementEngine
from backend.services.evidence.evidence_scoring import EvidenceScoringEngine
from backend.services.evidence.evidence_debt import EvidenceDebtCalculator
from backend.services.evidence.evidence_sufficiency import EvidenceSufficiencyEngine

# Phase 3 Reconciliation Models & Extractor
from backend.services.evidence.reconciliation_models import (
    AuthorityTier,
    ApprovalStatus,
    ExtractionMethod,
    EvidenceSearchStatus,
    DerivationStatus,
    RelationshipType,
    ConsistencyState,
    ReconciliationStatus,
    ConflictSeverity,
    ApplicabilityStatus,
    EvidenceObservation,
    MalformedObservationRecord,
    ObservationExtractionResult,
    DerivedObservation,
    ReconciliationRelationship,
    EvidenceConflict,
    PropertyTimeline,
    ApplicabilityPolicy,
    ApplicableObservationContext,
    ReconciliationResult,
)
from backend.services.evidence.observation_extractor import EvidenceObservationExtractor
from backend.services.evidence.reconciliation_engine import EvidenceReconciliationEngine

__all__ = [
    "EvidenceType",
    "AuthorityLevel",
    "EvidenceModality",
    "EvidenceRequirement",
    "EvidenceContract",
    "ContractGenerationContext",
    "EvidenceContractValidator",
    "EvidenceRequirementEngine",
    "SufficiencyStatus",
    "EvidenceDebtSeverity",
    "EvidenceDebtItem",
    "EvidenceDebt",
    "EvidenceAssessment",
    "EvidenceScoringEngine",
    "EvidenceDebtCalculator",
    "EvidenceSufficiencyEngine",
    # Phase 3 Exports
    "AuthorityTier",
    "ApprovalStatus",
    "ExtractionMethod",
    "EvidenceSearchStatus",
    "DerivationStatus",
    "RelationshipType",
    "ConsistencyState",
    "ReconciliationStatus",
    "ConflictSeverity",
    "ApplicabilityStatus",
    "EvidenceObservation",
    "MalformedObservationRecord",
    "ObservationExtractionResult",
    "DerivedObservation",
    "ReconciliationRelationship",
    "EvidenceConflict",
    "PropertyTimeline",
    "ApplicabilityPolicy",
    "ApplicableObservationContext",
    "ReconciliationResult",
    "EvidenceObservationExtractor",
    "EvidenceReconciliationEngine",
]



