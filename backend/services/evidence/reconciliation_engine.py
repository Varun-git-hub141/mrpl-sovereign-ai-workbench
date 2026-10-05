# backend/services/evidence/reconciliation_engine.py
"""
MRPL Sovereign AI Workbench — Phase 3: Industrial Evidence Reconciliation Engine.
Determines deterministic relationships, temporal timelines, conflict structures,
anomaly evidence search lifecycles, and external policy applicability boundaries.

Key Invariants:
- Absolute Non-Destructive Retention: Raw observations are never deleted, overwritten, or averaged.
- Categorical Consistency: Zero numeric consistency or authority scores.
- Spatial Disambiguation: Distinct CML points are recognized as non-conflicting.
- Anomaly Lifecycle: Anomaly candidates start with EVIDENCE_SEARCH_NOT_PERFORMED and transition through search lifecycle.
- External Policy Decoupling: Applicability status defaults to NOT_EVALUATED and requires external policy for resolution.
- Human Investigation Gating: High-risk conflicts flag requires_human_investigation without assigning operational verdicts.
"""

import re
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple, Set, Union, Callable
from datetime import datetime

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
    DerivedObservation,
    ReconciliationRelationship,
    EvidenceConflict,
    PropertyTimeline,
    ApplicabilityPolicy,
    ApplicableObservationContext,
    ReconciliationResult,
)

logger = logging.getLogger("mrpl.evidence.reconciliation_engine")


class EvidenceReconciliationEngine:
    """
    Deterministic Relational Classification & Reconciliation Engine.
    Operates on extracted EvidenceObservation collections to establish relational
    graphs, chronological progression timelines, conflict containers, anomaly search
    lifecycles, and external policy applicability contexts.
    """

    MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }

    @classmethod
    def parse_observation_date(cls, date_str: Optional[str]) -> Optional[float]:
        """
        Parses an ISO, year, or text date into a continuous decimal year value.
        Returns None if date_str is missing or unparseable.
        Example: '2024-06-15' -> 2024.45, '2019' -> 2019.0, '15-Feb-2022' -> 2022.12
        """
        if not date_str or not isinstance(date_str, str):
            return None

        clean = date_str.strip()
        if not clean:
            return None

        # 1. Pure 4-digit Year
        if re.match(r"^(19|20)\d{2}$", clean):
            return float(clean)

        # 2. ISO Format: YYYY-MM-DD
        m_iso = re.match(r"^(19|20)\d{2}-(\d{1,2})-(\d{1,2})", clean)
        if m_iso:
            year = int(m_iso.group(1) + clean[2:4])
            month = int(m_iso.group(2))
            day = int(m_iso.group(3))
            return round(year + (max(1, min(12, month)) - 1) / 12.0 + (max(1, min(31, day)) - 1) / 365.25, 4)

        # 3. Text format: DD-Mon-YYYY or DD/Mon/YYYY or DD Mon YYYY
        m_txt = re.match(r"^(\d{1,2})[\s\-\/]([A-Za-z]{3,9})[\s\-\/]((?:19|20)\d{2})$", clean)
        if m_txt:
            day = int(m_txt.group(1))
            month_str = m_txt.group(2).lower()[:3]
            year = int(m_txt.group(3))
            month = cls.MONTH_MAP.get(month_str, 1)
            return round(year + (month - 1) / 12.0 + (day - 1) / 365.25, 4)

        # 4. Standard Date Parser Fallback
        for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(clean, fmt)
                return round(dt.year + (dt.month - 1) / 12.0 + (dt.day - 1) / 365.25, 4)
            except ValueError:
                continue

        # Extract embedded 4-digit year if present
        m_embed = re.search(r"\b(19\d{2}|20\d{2})\b", clean)
        if m_embed:
            return float(m_embed.group(1))

        return None

    @classmethod
    def reconcile(
        cls,
        observations: List[EvidenceObservation],
        entity_scope: Optional[List[str]] = None,
        task_id: Optional[str] = None,
        policy: Optional[ApplicabilityPolicy] = None,
        is_high_risk_task: bool = False,
    ) -> ReconciliationResult:
        """
        Executes full Phase 3 reconciliation on the provided observations.
        Produces complete ReconciliationResult with timelines, relationships, conflicts,
        and policy applicability contexts.
        """
        task_id = task_id or f"TASK-RECON-{int(time.time())}"
        
        # 1. Handle empty observation case
        if not observations:
            return ReconciliationResult(
                task_id=task_id,
                entity_scope=entity_scope or [],
                consistency_state=ConsistencyState.INSUFFICIENT_CONTEXT,
                reconciliation_status=ReconciliationStatus.INSUFFICIENT_CONTEXT,
                all_observations=[],
                relationships=[],
                property_timelines={},
                derived_observations=[],
                active_conflicts=[],
                unresolved_conflicts=[],
                applicable_contexts=[],
                requires_human_investigation=False,
                reconciliation_summary="No observations provided for reconciliation.",
                reconciled_at=time.time(),
            )

        # 2. Filter by entity scope if specified
        target_entities = set(e.upper().strip() for e in entity_scope) if entity_scope else None
        filtered_obs = [
            o for o in observations
            if target_entities is None or o.entity_tag.upper().strip() in target_entities
        ]

        if not filtered_obs:
            return ReconciliationResult(
                task_id=task_id,
                entity_scope=entity_scope or [],
                consistency_state=ConsistencyState.INSUFFICIENT_CONTEXT,
                reconciliation_status=ReconciliationStatus.INSUFFICIENT_CONTEXT,
                all_observations=[],
                relationships=[],
                property_timelines={},
                derived_observations=[],
                active_conflicts=[],
                unresolved_conflicts=[],
                applicable_contexts=[],
                requires_human_investigation=False,
                reconciliation_summary="No matching observations found within specified entity scope.",
                reconciled_at=time.time(),
            )

        # 3. Classify pairwise relationships
        relationships: List[ReconciliationRelationship] = []
        n_obs = len(filtered_obs)
        for i in range(n_obs):
            for j in range(i + 1, n_obs):
                rel = cls.classify_relationship(filtered_obs[i], filtered_obs[j])
                if rel:
                    relationships.append(rel)

        # 4. Build Property Timelines and compute derived progressions
        timelines = cls.build_timelines(filtered_obs)

        # Collect all derived observations across timelines
        all_derived: List[DerivedObservation] = []
        for t in timelines.values():
            all_derived.extend(t.derived_progressions)

        # 5. Detect and assemble conflicts
        conflicts = cls.detect_conflicts(filtered_obs, relationships)

        # 6. Determine overall ConsistencyState (Categorical only)
        has_conflict = len(conflicts) > 0
        has_anomaly = any(r.is_anomaly for r in relationships) or any(t.has_anomalies for t in timelines.values())
        has_uncertain = any(r.relationship_type in (RelationshipType.TEMPORAL_ORDER_UNKNOWN, RelationshipType.SUPERSEDENCE_UNCERTAIN) for r in relationships)
        has_temporal = any(r.relationship_type == RelationshipType.TEMPORAL_PROGRESSION for r in relationships)
        has_spatial = any(r.relationship_type == RelationshipType.SPATIALLY_DISTINCT for r in relationships)

        if has_conflict:
            consistency_state = ConsistencyState.CONFLICTING
        elif has_anomaly:
            consistency_state = ConsistencyState.ANOMALOUS
        elif has_uncertain:
            consistency_state = ConsistencyState.UNCERTAIN
        elif has_temporal:
            consistency_state = ConsistencyState.TEMPORALLY_EXPLAINED
        elif has_spatial:
            consistency_state = ConsistencyState.SPATIALLY_DISTINCT
        elif len(filtered_obs) >= 1:
            consistency_state = ConsistencyState.CONSISTENT
        else:
            consistency_state = ConsistencyState.INSUFFICIENT_CONTEXT

        # 7. Determine overall ReconciliationStatus
        if has_conflict:
            reconciliation_status = ReconciliationStatus.UNRESOLVED_CONFLICT
        elif has_anomaly:
            reconciliation_status = ReconciliationStatus.ANOMALY_DETECTED
        elif any(r.relationship_type == RelationshipType.SUPERSEDENCE_UNCERTAIN for r in relationships):
            reconciliation_status = ReconciliationStatus.SUPERSEDENCE_UNCERTAIN
        elif has_temporal:
            reconciliation_status = ReconciliationStatus.TEMPORALLY_MAPPED
        elif has_spatial:
            reconciliation_status = ReconciliationStatus.SPATIALLY_MAPPED
        elif len(filtered_obs) >= 1:
            reconciliation_status = ReconciliationStatus.NON_CONFLICTING
        else:
            reconciliation_status = ReconciliationStatus.INSUFFICIENT_CONTEXT

        # 8. Generate Applicable Contexts (Defaults to NOT_EVALUATED)
        applicable_contexts = cls._generate_applicable_contexts(filtered_obs)

        # 9. Build comprehensive summary
        summary_parts = [
            f"Reconciliation completed for {len(filtered_obs)} observations across {len(set(o.entity_tag for o in filtered_obs))} entities.",
            f"Consistency State: {consistency_state.value}.",
            f"Reconciliation Status: {reconciliation_status.value}.",
            f"Classified Relationships: {len(relationships)}.",
            f"Active Conflicts: {len(conflicts)}.",
            f"Derived Historical Progressions: {len(all_derived)}.",
        ]
        if has_anomaly:
            summary_parts.append("ATTENTION: Anomalous progression candidate detected without verified MOC documentation.")

        result = ReconciliationResult(
            task_id=task_id,
            entity_scope=list(set(o.entity_tag for o in filtered_obs)),
            consistency_state=consistency_state,
            reconciliation_status=reconciliation_status,
            all_observations=filtered_obs,
            relationships=relationships,
            property_timelines=timelines,
            derived_observations=all_derived,
            active_conflicts=conflicts,
            unresolved_conflicts=conflicts,
            applicable_contexts=applicable_contexts,
            requires_human_investigation=False,  # Gated by downstream policy
            reconciliation_summary=" ".join(summary_parts),
            reconciled_at=time.time(),
        )

        # Apply external policy if supplied
        if policy:
            result = cls.evaluate_applicability(result, policy)

        # Apply high risk gate if requested
        if is_high_risk_task:
            result = cls.evaluate_high_risk_gate(result, is_high_risk_task=True)

        return result

    @classmethod
    def classify_relationship(
        cls,
        observation_a: EvidenceObservation,
        observation_b: EvidenceObservation,
    ) -> Optional[ReconciliationRelationship]:
        """
        Classifies the relationship between two observations strictly by provenance,
        spatial location, revision lifecycle, authority tier, and temporal coordinates.
        """
        tag_a = observation_a.entity_tag.upper().strip()
        tag_b = observation_b.entity_tag.upper().strip()
        
        # Invariant: Different entities -> No inter-entity relationship
        if tag_a != tag_b:
            return None

        prop_a = observation_a.property_name.lower().strip()
        prop_b = observation_b.property_name.lower().strip()

        # Invariant: Different properties -> No inter-property relationship
        if prop_a != prop_b:
            return None

        rel_id = f"REL-{tag_a}-{prop_a[:8].upper()}-{observation_a.observation_id[:6]}-{observation_b.observation_id[:6]}"

        # Check duplicate identical observation
        if observation_a.observation_id == observation_b.observation_id:
            return ReconciliationRelationship(
                relationship_id=rel_id,
                property_name=observation_a.property_name,
                relationship_type=RelationshipType.CORROBORATING,
                observation_ids=[observation_a.observation_id, observation_b.observation_id],
                explanation=f"Identical observation instance {observation_a.observation_id} corroborated.",
            )

        # 1. Spatial Disambiguation
        loc_a = (observation_a.measurement_location or "").strip()
        loc_b = (observation_b.measurement_location or "").strip()
        if loc_a and loc_b and loc_a.lower() != loc_b.lower():
            return ReconciliationRelationship(
                relationship_id=rel_id,
                property_name=observation_a.property_name,
                relationship_type=RelationshipType.SPATIALLY_DISTINCT,
                observation_ids=[observation_a.observation_id, observation_b.observation_id],
                explanation=f"Observations represent physically distinct locations ({loc_a} vs {loc_b}) on {tag_a}.",
            )

        # 2. Revision Lifecycle Classification
        appr_a = observation_a.approval_status
        appr_b = observation_b.approval_status

        # Superseded Revision
        if (appr_a == ApprovalStatus.SUPERSEDED and appr_b == ApprovalStatus.APPROVED) or \
           (appr_b == ApprovalStatus.SUPERSEDED and appr_a == ApprovalStatus.APPROVED):
            sup_obs = observation_a if appr_a == ApprovalStatus.SUPERSEDED else observation_b
            appr_obs = observation_b if appr_a == ApprovalStatus.SUPERSEDED else observation_a
            return ReconciliationRelationship(
                relationship_id=rel_id,
                property_name=observation_a.property_name,
                relationship_type=RelationshipType.SUPERSEDED_REVISION,
                observation_ids=[observation_a.observation_id, observation_b.observation_id],
                explanation=f"Observation in revision {sup_obs.revision_number or 'older'} is superseded by approved revision {appr_obs.revision_number or 'current'}.",
            )

        # Unapproved Draft alongside Approved
        if (appr_a == ApprovalStatus.DRAFT and appr_b == ApprovalStatus.APPROVED) or \
           (appr_b == ApprovalStatus.DRAFT and appr_a == ApprovalStatus.APPROVED):
            return ReconciliationRelationship(
                relationship_id=rel_id,
                property_name=observation_a.property_name,
                relationship_type=RelationshipType.UNAPPROVED_DRAFT,
                observation_ids=[observation_a.observation_id, observation_b.observation_id],
                explanation="Unapproved draft observation exists alongside approved engineering baseline.",
            )

        # Ambiguous Revision Lineage
        rev_a = observation_a.revision_number
        rev_b = observation_b.revision_number
        if (appr_a == ApprovalStatus.PENDING_MOC or appr_b == ApprovalStatus.PENDING_MOC) or \
           (rev_a and rev_b and rev_a != rev_b and appr_a == ApprovalStatus.UNKNOWN and appr_b == ApprovalStatus.UNKNOWN):
            return ReconciliationRelationship(
                relationship_id=rel_id,
                property_name=observation_a.property_name,
                relationship_type=RelationshipType.SUPERSEDENCE_UNCERTAIN,
                observation_ids=[observation_a.observation_id, observation_b.observation_id],
                explanation="Ambiguous revision lineage: multiple revisions exist without verified MOC supersedence.",
            )

        # 3. Value Matching & Corroboration
        val_match = cls._are_values_matching(observation_a.value, observation_b.value, observation_a.unit, observation_b.unit)

        # 4. Temporal Analysis
        t_a = cls.parse_observation_date(observation_a.observation_date)
        t_b = cls.parse_observation_date(observation_b.observation_date)

        # Missing Timestamps
        if t_a is None or t_b is None:
            if val_match:
                return ReconciliationRelationship(
                    relationship_id=rel_id,
                    property_name=observation_a.property_name,
                    relationship_type=RelationshipType.CORROBORATING,
                    observation_ids=[observation_a.observation_id, observation_b.observation_id],
                    explanation=f"Independent records report matching value {observation_a.value} {observation_a.unit or ''}.",
                )
            
            # Values differ and timestamp is missing
            if observation_a.authority_tier != observation_b.authority_tier and \
               observation_a.authority_tier != AuthorityTier.UNKNOWN and observation_b.authority_tier != AuthorityTier.UNKNOWN:
                return ReconciliationRelationship(
                    relationship_id=rel_id,
                    property_name=observation_a.property_name,
                    relationship_type=RelationshipType.AUTHORITY_DISCREPANCY,
                    observation_ids=[observation_a.observation_id, observation_b.observation_id],
                    explanation=f"Authority discrepancy: {observation_a.authority_tier.value} reports {observation_a.value} while {observation_b.authority_tier.value} reports {observation_b.value}.",
                )

            return ReconciliationRelationship(
                relationship_id=rel_id,
                property_name=observation_a.property_name,
                relationship_type=RelationshipType.TEMPORAL_ORDER_UNKNOWN,
                observation_ids=[observation_a.observation_id, observation_b.observation_id],
                explanation=f"Missing observation timestamp prevents chronological sequencing between {observation_a.observation_id} and {observation_b.observation_id}.",
            )

        # Simultaneous / Overlapping Timestamps (within ~30 days / 0.08 years)
        if abs(t_a - t_b) < 0.08:
            if val_match:
                return ReconciliationRelationship(
                    relationship_id=rel_id,
                    property_name=observation_a.property_name,
                    relationship_type=RelationshipType.CORROBORATING,
                    observation_ids=[observation_a.observation_id, observation_b.observation_id],
                    explanation=f"Independent records corroborate value {observation_a.value} {observation_a.unit or ''} for {tag_a} at timestamp {observation_a.observation_date}.",
                )

            # Different values at same timestamp
            if observation_a.authority_tier != observation_b.authority_tier and \
               observation_a.authority_tier != AuthorityTier.UNKNOWN and observation_b.authority_tier != AuthorityTier.UNKNOWN:
                return ReconciliationRelationship(
                    relationship_id=rel_id,
                    property_name=observation_a.property_name,
                    relationship_type=RelationshipType.AUTHORITY_DISCREPANCY,
                    observation_ids=[observation_a.observation_id, observation_b.observation_id],
                    explanation=f"Discrepancy across authority tiers at timestamp {observation_a.observation_date}: {observation_a.authority_tier.value} ({observation_a.value}) vs {observation_b.authority_tier.value} ({observation_b.value}).",
                )

            return ReconciliationRelationship(
                relationship_id=rel_id,
                property_name=observation_a.property_name,
                relationship_type=RelationshipType.SIMULTANEOUS_DISCREPANCY,
                observation_ids=[observation_a.observation_id, observation_b.observation_id],
                explanation=f"Simultaneous discrepancy: conflicting values ({observation_a.value} vs {observation_b.value}) reported for same location at timestamp {observation_a.observation_date}.",
            )

        # Chronologically Distinct Timestamps (t_a != t_b)
        earlier_obs, later_obs = (observation_a, observation_b) if t_a < t_b else (observation_b, observation_a)
        
        # Check physical thickness anomaly candidate (apparent growth without replacement)
        if "thickness" in prop_a:
            v_early = cls._to_float(earlier_obs.value)
            v_late = cls._to_float(later_obs.value)
            if v_early is not None and v_late is not None and v_late > v_early:
                return ReconciliationRelationship(
                    relationship_id=rel_id,
                    property_name=observation_a.property_name,
                    relationship_type=RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE,
                    observation_ids=[earlier_obs.observation_id, later_obs.observation_id],
                    evidence_search_status=EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
                    explanation=f"Apparent thickness increase from {v_early} mm ({earlier_obs.observation_date}) to {v_late} mm ({later_obs.observation_date}) without verified MOC replacement record in current evidence context.",
                    is_anomaly=True,
                )

        return ReconciliationRelationship(
            relationship_id=rel_id,
            property_name=observation_a.property_name,
            relationship_type=RelationshipType.TEMPORAL_PROGRESSION,
            observation_ids=[earlier_obs.observation_id, later_obs.observation_id],
            explanation=f"Chronological temporal progression from {earlier_obs.observation_date} ({earlier_obs.value}) to {later_obs.observation_date} ({later_obs.value}).",
        )

    @classmethod
    def execute_anomaly_search(
        cls,
        result: ReconciliationResult,
        relationship_id: str,
        supporting_evidence: Optional[List[EvidenceObservation]] = None,
        search_performed: bool = True,
    ) -> ReconciliationResult:
        """
        Executes the Phase 3C Anomaly Evidence Search Lifecycle.
        Progression:
        EVIDENCE_SEARCH_NOT_PERFORMED
            -> EVIDENCE_SEARCH_IN_PROGRESS
            -> EVIDENCE_SEARCH_COMPLETED
            -> SUPPORTING_EVIDENCE_FOUND (if MOC/replacement found)
            OR
            -> SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH (if no MOC found -> ANOMALOUS_PROGRESSION)
        """
        target_rel = None
        for rel in result.relationships:
            if rel.relationship_id == relationship_id:
                target_rel = rel
                break

        if not target_rel:
            return result

        # Transition 1: IN_PROGRESS
        target_rel.evidence_search_status = EvidenceSearchStatus.EVIDENCE_SEARCH_IN_PROGRESS

        if not search_performed:
            return result

        # Transition 2: COMPLETED
        target_rel.evidence_search_status = EvidenceSearchStatus.EVIDENCE_SEARCH_COMPLETED

        if supporting_evidence:
            # Supporting MOC/replacement records found
            target_rel.evidence_search_status = EvidenceSearchStatus.SUPPORTING_EVIDENCE_FOUND
            target_rel.relationship_type = RelationshipType.TEMPORAL_PROGRESSION
            target_rel.is_anomaly = False
            src_doc_info = ", ".join(set(o.source_document for o in supporting_evidence))
            target_rel.explanation += f" Supporting MOC/replacement documentation verified in {src_doc_info}."
            
            # Non-destructive: add supporting evidence observations to all_observations
            existing_ids = set(o.observation_id for o in result.all_observations)
            for s_obs in supporting_evidence:
                if s_obs.observation_id not in existing_ids:
                    result.all_observations.append(s_obs)
                    existing_ids.add(s_obs.observation_id)
        else:
            # Search completed but no supporting evidence found
            target_rel.evidence_search_status = EvidenceSearchStatus.SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH
            target_rel.relationship_type = RelationshipType.ANOMALOUS_PROGRESSION
            target_rel.is_anomaly = True
            target_rel.explanation += " Search completed: no supporting MOC or replacement record exists in repository to explain thickness increase."

        # Re-evaluate consistency state and status
        has_conflict = len(result.active_conflicts) > 0
        has_anomaly = any(r.is_anomaly for r in result.relationships)
        has_uncertain = any(r.relationship_type in (RelationshipType.TEMPORAL_ORDER_UNKNOWN, RelationshipType.SUPERSEDENCE_UNCERTAIN) for r in result.relationships)
        has_temporal = any(r.relationship_type == RelationshipType.TEMPORAL_PROGRESSION for r in result.relationships)
        has_spatial = any(r.relationship_type == RelationshipType.SPATIALLY_DISTINCT for r in result.relationships)

        if has_conflict:
            result.consistency_state = ConsistencyState.CONFLICTING
            result.reconciliation_status = ReconciliationStatus.UNRESOLVED_CONFLICT
        elif has_anomaly:
            result.consistency_state = ConsistencyState.ANOMALOUS
            result.reconciliation_status = ReconciliationStatus.ANOMALY_DETECTED
        elif has_uncertain:
            result.consistency_state = ConsistencyState.UNCERTAIN
            result.reconciliation_status = ReconciliationStatus.SUPERSEDENCE_UNCERTAIN
        elif has_temporal:
            result.consistency_state = ConsistencyState.TEMPORALLY_EXPLAINED
            result.reconciliation_status = ReconciliationStatus.TEMPORALLY_MAPPED
        elif has_spatial:
            result.consistency_state = ConsistencyState.SPATIALLY_DISTINCT
            result.reconciliation_status = ReconciliationStatus.SPATIALLY_MAPPED
        else:
            result.consistency_state = ConsistencyState.CONSISTENT
            result.reconciliation_status = ReconciliationStatus.NON_CONFLICTING

        return result

    @classmethod
    def evaluate_applicability(
        cls,
        result: ReconciliationResult,
        policy: Optional[ApplicabilityPolicy] = None,
    ) -> ReconciliationResult:
        """
        Applies an external policy to evaluate which candidate observation is operationally applicable.
        Preserves all candidate and alternative observations non-destructively.
        """
        if not policy:
            for ctx in result.applicable_contexts:
                ctx.applicability_status = ApplicabilityStatus.NOT_EVALUATED
                ctx.selected_observation_id = None
                ctx.selection_basis = None
                ctx.policy_identifier = None
                ctx.applicability_rationale = "No external applicability policy supplied; all candidate observations preserved."
            return result

        tier_rank = {
            AuthorityTier.APPROVED_AUTHORITATIVE: 4,
            AuthorityTier.APPROVED: 3,
            AuthorityTier.INTERNAL: 2,
            AuthorityTier.INFORMAL: 1,
            AuthorityTier.UNKNOWN: 0,
        }
        status_rank = {
            ApprovalStatus.APPROVED: 4,
            ApprovalStatus.PENDING_MOC: 3,
            ApprovalStatus.DRAFT: 2,
            ApprovalStatus.SUPERSEDED: 1,
            ApprovalStatus.UNKNOWN: 0,
        }

        # Override with custom policy preferences if provided
        if policy.preferred_authority_tiers:
            tier_rank = {t: len(policy.preferred_authority_tiers) - i for i, t in enumerate(policy.preferred_authority_tiers)}
        if policy.preferred_approval_statuses:
            status_rank = {s: len(policy.preferred_approval_statuses) - i for i, s in enumerate(policy.preferred_approval_statuses)}

        for ctx in result.applicable_contexts:
            # Check property filter
            if policy.target_properties and ctx.property_name not in policy.target_properties:
                continue

            candidates = [
                o for o in result.all_observations
                if o.entity_tag.upper().strip() == ctx.entity_tag.upper().strip() and
                   o.property_name.lower().strip() == ctx.property_name.lower().strip()
            ]

            if not candidates:
                ctx.applicability_status = ApplicabilityStatus.NOT_EVALUATED
                continue

            # Date filter if required by policy
            if policy.require_verified_date:
                candidates = [c for c in candidates if c.observation_date is not None]

            if not candidates:
                ctx.applicability_status = ApplicabilityStatus.UNRESOLVED
                ctx.policy_identifier = policy.policy_identifier
                ctx.applicability_rationale = "No candidate observations met policy requirement for verified observation dates."
                continue

            # Sort candidates by (Tier Rank, Approval Rank, Date if select_latest_dated)
            def score_candidate(cand: EvidenceObservation):
                t_score = tier_rank.get(cand.authority_tier, 0)
                s_score = status_rank.get(cand.approval_status, 0)
                d_score = cls.parse_observation_date(cand.observation_date) or 0.0 if policy.select_latest_dated else 0.0
                return (t_score, s_score, d_score)

            candidates.sort(key=score_candidate, reverse=True)
            top_candidate = candidates[0]
            top_score = score_candidate(top_candidate)

            # Check for tie among top candidates (unless select_latest_dated disambiguated)
            tied = [c for c in candidates if score_candidate(c) == top_score]
            if len(tied) > 1 and not (policy.select_latest_dated and len(set(c.observation_date for c in tied)) > 1):
                # Multiple candidates tied and cannot resolve single applicable observation
                ctx.applicability_status = ApplicabilityStatus.UNRESOLVED
                ctx.selected_observation_id = None
                ctx.policy_identifier = policy.policy_identifier
                ctx.selection_basis = f"Policy {policy.policy_identifier} yielded {len(tied)} tied candidate observations."
                ctx.applicability_rationale = "Ambiguous applicability: multiple observations share equal ranking under supplied policy."
                ctx.alternative_observation_ids = [c.observation_id for c in candidates]
            else:
                ctx.applicability_status = ApplicabilityStatus.EVALUATED_APPLICABLE
                ctx.selected_observation_id = top_candidate.observation_id
                ctx.policy_identifier = policy.policy_identifier
                ctx.selection_basis = f"Selected by policy {policy.policy_identifier} (Tier: {top_candidate.authority_tier.value}, Approval: {top_candidate.approval_status.value})"
                ctx.applicability_rationale = f"Observation {top_candidate.observation_id} from {top_candidate.source_document} resolved as applicable."
                ctx.alternative_observation_ids = [c.observation_id for c in candidates if c.observation_id != top_candidate.observation_id]

        return result

    @classmethod
    def evaluate_high_risk_gate(
        cls,
        result: ReconciliationResult,
        is_high_risk_task: bool = False,
    ) -> ReconciliationResult:
        """
        Flags requires_human_investigation when high-risk tasks have unresolved conflicts or anomalies.
        Does not emit operational safety conclusions or statutory pass/fail verdicts.
        """
        if is_high_risk_task:
            if len(result.active_conflicts) > 0 or result.consistency_state in (ConsistencyState.CONFLICTING, ConsistencyState.ANOMALOUS):
                result.requires_human_investigation = True
        return result

    @classmethod
    def export_to_claim_provenance(
        cls,
        result: ReconciliationResult,
    ) -> List[Dict[str, Any]]:
        """
        Exports reconciled observations with complete source lineage and contested state flags
        for seamless consumption by Phase 2 / Claim Provenance layers.
        """
        contested_ids = set()
        for conf in result.active_conflicts:
            contested_ids.update(conf.conflicting_observation_ids)

        exported: List[Dict[str, Any]] = []
        for obs in result.all_observations:
            exported.append({
                "observation_id": obs.observation_id,
                "entity_tag": obs.entity_tag,
                "property_name": obs.property_name,
                "value": obs.value,
                "unit": obs.unit,
                "measurement_location": obs.measurement_location,
                "measurement_method": obs.measurement_method,
                "observation_date": obs.observation_date,
                "source_document": obs.source_document,
                "document_id": obs.document_id,
                "document_type": obs.document_type,
                "page_number": obs.page_number,
                "section": obs.section,
                "source_span": obs.source_span,
                "revision_number": obs.revision_number,
                "approval_status": obs.approval_status.value,
                "authority_tier": obs.authority_tier.value,
                "extraction_method": obs.extraction_method.value,
                "raw_statement": obs.raw_statement,
                "is_contested": obs.observation_id in contested_ids,
            })
        return exported

    @classmethod
    def build_timelines(
        cls,
        observations: List[EvidenceObservation],
    ) -> Dict[str, PropertyTimeline]:
        """
        Groups observations by (entity, property, location) and builds chronological timelines
        with calculated observed historical rates.
        """
        grouped: Dict[str, List[EvidenceObservation]] = {}
        for obs in observations:
            loc = (obs.measurement_location or "ALL").strip()
            key = f"{obs.entity_tag}:{obs.property_name}:{loc}"
            grouped.setdefault(key, []).append(obs)

        timelines: Dict[str, PropertyTimeline] = {}

        for key, obs_list in grouped.items():
            entity_tag = obs_list[0].entity_tag
            property_name = obs_list[0].property_name

            # Partition into dated and undated
            dated: List[Tuple[float, EvidenceObservation]] = []
            undated: List[EvidenceObservation] = []

            for obs in obs_list:
                t = cls.parse_observation_date(obs.observation_date)
                if t is not None:
                    dated.append((t, obs))
                else:
                    undated.append(obs)

            # Sort dated chronologically
            dated.sort(key=lambda x: x[0])
            sorted_obs = [o for _, o in dated] + undated

            derived_progressions: List[DerivedObservation] = []
            anomalies: List[str] = []
            has_anomalies = False

            # Compute observed historical progression rates across dated pairs
            if len(dated) >= 2:
                for idx in range(len(dated) - 1):
                    t1, obs1 = dated[idx]
                    t2, obs2 = dated[idx + 1]
                    delta_t = round(t2 - t1, 4)

                    if delta_t > 0:
                        v1 = cls._to_float(obs1.value)
                        v2 = cls._to_float(obs2.value)

                        # Check unit compatibility
                        units_compatible = (obs1.unit or "").lower() == (obs2.unit or "").lower()

                        if v1 is not None and v2 is not None and units_compatible:
                            if "thickness" in property_name.lower():
                                # Metal loss progression
                                thickness_loss = round(v1 - v2, 4)
                                rate = round(thickness_loss / delta_t, 4)
                                
                                if v2 > v1:
                                    has_anomalies = True
                                    anomalies.append(
                                        f"Physical growth candidate: {obs1.value} mm ({obs1.observation_date}) -> {obs2.value} mm ({obs2.observation_date})"
                                    )

                                deriv = DerivedObservation(
                                    derived_id=f"DERIV-RATE-{obs1.observation_id[:6]}-{obs2.observation_id[:6]}",
                                    property_name=f"observed_corrosion_rate",
                                    derived_value=rate,
                                    unit=f"{obs1.unit or 'mm'}/year",
                                    derivation_status=DerivationStatus.CALCULATED,
                                    source_observation_ids=[obs1.observation_id, obs2.observation_id],
                                    derivation_method="Observed Historical Progression Rate",
                                    input_parameters={
                                        "initial_value": v1,
                                        "final_value": v2,
                                        "initial_date": obs1.observation_date,
                                        "final_date": obs2.observation_date,
                                        "time_interval_years": delta_t,
                                        "unit": obs1.unit,
                                    },
                                    time_interval_years=delta_t,
                                    source_verified_assumptions=["Observed historical rate derived strictly from source observation timestamps."],
                                )
                                derived_progressions.append(deriv)
                            else:
                                # Generic progression rate
                                rate = round((v2 - v1) / delta_t, 4)
                                deriv = DerivedObservation(
                                    derived_id=f"DERIV-RATE-{obs1.observation_id[:6]}-{obs2.observation_id[:6]}",
                                    property_name=f"observed_{property_name}_rate",
                                    derived_value=rate,
                                    unit=f"{obs1.unit or 'units'}/year",
                                    derivation_status=DerivationStatus.CALCULATED,
                                    source_observation_ids=[obs1.observation_id, obs2.observation_id],
                                    derivation_method="Observed Historical Progression Rate",
                                    input_parameters={
                                        "initial_value": v1,
                                        "final_value": v2,
                                        "time_interval_years": delta_t,
                                        "unit": obs1.unit,
                                    },
                                    time_interval_years=delta_t,
                                    source_verified_assumptions=["Observed historical rate derived strictly from source observation timestamps."],
                                )
                                derived_progressions.append(deriv)

            # Determine temporal trend
            temporal_trend = cls._determine_temporal_trend(dated, property_name)

            timelines[key] = PropertyTimeline(
                property_name=property_name,
                entity_tag=entity_tag,
                observations_chronological=sorted_obs,
                derived_progressions=derived_progressions,
                temporal_trend=temporal_trend,
                has_anomalies=has_anomalies,
                anomaly_descriptions=anomalies,
            )

        return timelines

    @classmethod
    def detect_conflicts(
        cls,
        observations: List[EvidenceObservation],
        relationships: List[ReconciliationRelationship],
    ) -> List[EvidenceConflict]:
        """
        Extracts formal EvidenceConflict containers from classified discrepancies.
        """
        conflicts: List[EvidenceConflict] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        for rel in relationships:
            if rel.relationship_type in (RelationshipType.SIMULTANEOUS_DISCREPANCY, RelationshipType.AUTHORITY_DISCREPANCY):
                if len(rel.observation_ids) >= 2:
                    pair_key = (rel.observation_ids[0], rel.observation_ids[1])
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Find target entity
                    matching_obs = [o for o in observations if o.observation_id in rel.observation_ids]
                    entity_tag = matching_obs[0].entity_tag if matching_obs else "UNKNOWN"

                    conf = EvidenceConflict(
                        conflict_id=f"CONF-{entity_tag}-{rel.property_name[:8].upper()}-{rel.relationship_id[:8]}",
                        property_name=rel.property_name,
                        entity_tag=entity_tag,
                        severity=ConflictSeverity.UNCLASSIFIED,  # Decoupled from Phase 3B/3C
                        conflicting_observation_ids=rel.observation_ids,
                        conflict_description=rel.explanation,
                        required_resolution_evidence=[
                            "Verify inspection calibration logs and survey methodology",
                            "Review original NDT technician sign-off sheet",
                        ],
                    )
                    conflicts.append(conf)

        return conflicts

    @classmethod
    def _generate_applicable_contexts(
        cls,
        observations: List[EvidenceObservation],
    ) -> List[ApplicableObservationContext]:
        """
        Creates ApplicableObservationContext records for distinct (entity, property) scopes.
        Defaults to NOT_EVALUATED to maintain decoupling from unsupplied external policies.
        """
        contexts: List[ApplicableObservationContext] = []
        seen: Set[Tuple[str, str]] = set()

        for obs in observations:
            pair = (obs.entity_tag, obs.property_name)
            if pair in seen:
                continue
            seen.add(pair)

            all_matching_ids = [o.observation_id for o in observations if o.entity_tag == obs.entity_tag and o.property_name == obs.property_name]

            ctx = ApplicableObservationContext(
                entity_tag=obs.entity_tag,
                property_name=obs.property_name,
                applicability_status=ApplicabilityStatus.NOT_EVALUATED,
                selected_observation_id=None,
                selection_basis=None,
                policy_identifier=None,
                applicability_rationale="No external applicability policy supplied; all candidate observations preserved.",
                alternative_observation_ids=all_matching_ids,
            )
            contexts.append(ctx)

        return contexts

    @classmethod
    def _determine_temporal_trend(
        cls,
        dated_obs: List[Tuple[float, EvidenceObservation]],
        property_name: str,
    ) -> Optional[str]:
        """
        Calculates monotonic or fluctuating trend across dated numerical observations.
        """
        if len(dated_obs) < 2:
            return "UNKNOWN"

        values = [cls._to_float(obs.value) for _, obs in dated_obs]
        if any(v is None for v in values):
            return "UNKNOWN"

        diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]  # type: ignore

        if all(abs(d) < 1e-4 for d in diffs):
            return "STABLE"
        if all(d <= 1e-4 for d in diffs):
            return "MONOTONIC_DECREASE"
        if all(d >= -1e-4 for d in diffs):
            return "MONOTONIC_INCREASE"
        
        return "FLUCTUATING"

    @classmethod
    def _are_values_matching(
        cls,
        v1: Any,
        v2: Any,
        u1: Optional[str],
        u2: Optional[str],
    ) -> bool:
        """
        Checks if two values and their units represent an identical observation.
        """
        # Unit check
        if (u1 or "").strip().lower() != (u2 or "").strip().lower():
            return False

        # Numeric check
        f1 = cls._to_float(v1)
        f2 = cls._to_float(v2)
        if f1 is not None and f2 is not None:
            return abs(f1 - f2) < 1e-4

        # String / exact check (e.g. range strings '4.4 - 4.6')
        return str(v1).strip().lower() == str(v2).strip().lower()

    @classmethod
    def _to_float(cls, val: Any) -> Optional[float]:
        """
        Safely converts a value to float if possible. Returns None for ranges or non-numeric strings.
        """
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            clean = val.strip()
            # If string contains range indicator, it is NOT a single float
            if "-" in clean or " to " in clean.lower():
                return None
            try:
                return float(clean)
            except ValueError:
                return None
        return None
