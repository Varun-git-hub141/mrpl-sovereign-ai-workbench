# tests/test_evidence_phase3c.py
"""
MRPL Sovereign AI Workbench — Phase 3C Test Suite:
Anomaly Evidence Retrieval Lifecycle & External Policy Applicability.

Validates:
1. Anomaly candidate starts with EVIDENCE_SEARCH_NOT_PERFORMED.
2. Search transitions to EVIDENCE_SEARCH_IN_PROGRESS.
3. Completed search with supporting MOC/evidence is represented correctly.
4. Completed search with no supporting evidence produces SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH and confirmed ANOMALOUS_PROGRESSION.
5. No retrieved MOC does NOT equal "MOC does not exist".
6. Supporting evidence preserves source/provenance lineage.
7. Applicability defaults to NOT_EVALUATED without external policy.
8. External policy can explicitly select an observation.
9. Alternative observations remain preserved after applicability selection.
10. Conflicting observations are never averaged or deleted.
11. Approved-vs-draft revision handling remains unchanged.
12. Missing date remains TEMPORAL_ORDER_UNKNOWN and cannot generate a rate.
13. Incompatible units cannot generate a derived rate.
14. High-risk unresolved conflict remains visible and can require human investigation without operational verdict.
15. Multi-entity scopes remain independent.
16. Claim provenance export retains full source lineage and is_contested status.
"""

import pytest
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
    ReconciliationRelationship,
    EvidenceConflict,
    PropertyTimeline,
    ApplicabilityPolicy,
    ApplicableObservationContext,
    ReconciliationResult,
)
from backend.services.evidence.reconciliation_engine import EvidenceReconciliationEngine


class TestEvidencePhase3C:
    """Phase 3C test suite for anomaly lifecycle and external policy applicability."""

    def test_1_anomaly_candidate_starts_with_search_not_performed(self):
        """1. Anomaly candidate initially starts with EVIDENCE_SEARCH_NOT_PERFORMED."""
        obs1 = EvidenceObservation(
            observation_id="OBS-19",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.0,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2019-01-01",
            source_document="INSP-2019.pdf",
            raw_statement="2019 wall thickness: 4.0 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-24",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=5.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-01-01",
            source_document="INSP-2024.pdf",
            raw_statement="2024 wall thickness: 5.5 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert len(res.relationships) == 1
        rel = res.relationships[0]
        assert rel.relationship_type == RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE
        assert rel.evidence_search_status == EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED
        assert rel.is_anomaly is True

    def test_2_search_transitions_to_in_progress(self):
        """2. Search lifecycle correctly transitions to EVIDENCE_SEARCH_IN_PROGRESS."""
        obs1 = EvidenceObservation(
            observation_id="OBS-19",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.0,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2019-01-01",
            source_document="INSP-2019.pdf",
            raw_statement="2019: 4.0 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-24",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=5.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-01-01",
            source_document="INSP-2024.pdf",
            raw_statement="2024: 5.5 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        rel_id = res.relationships[0].relationship_id

        # Execute partial lifecycle with search_performed=False to check IN_PROGRESS state
        updated = EvidenceReconciliationEngine.execute_anomaly_search(
            result=res,
            relationship_id=rel_id,
            supporting_evidence=None,
            search_performed=False,
        )
        assert updated.relationships[0].evidence_search_status == EvidenceSearchStatus.EVIDENCE_SEARCH_IN_PROGRESS

    def test_3_completed_search_with_supporting_moc_evidence(self):
        """3. Completed search with supporting MOC resolves anomaly to explainable progression."""
        obs1 = EvidenceObservation(
            observation_id="OBS-19",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.0,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2019-01-01",
            source_document="INSP-2019.pdf",
            raw_statement="2019: 4.0 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-24",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=5.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-01-01",
            source_document="INSP-2024.pdf",
            raw_statement="2024: 5.5 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        rel_id = res.relationships[0].relationship_id

        # Supporting MOC found during retrieval search
        moc_obs = EvidenceObservation(
            observation_id="OBS-MOC-2022",
            entity_tag="P-201",
            property_name="spool_replacement",
            value="New Spool Schedule 80 Installed",
            observation_date="2022-08-10",
            source_document="MRPL-MOC-2022-P201.pdf",
            document_id="MOC-P201-0822",
            approval_status=ApprovalStatus.APPROVED,
            authority_tier=AuthorityTier.APPROVED_AUTHORITATIVE,
            raw_statement="MOC 2022-0822: Replaced corroded suction spool with new 5.5 mm nominal schedule 80 spool.",
        )

        updated = EvidenceReconciliationEngine.execute_anomaly_search(
            result=res,
            relationship_id=rel_id,
            supporting_evidence=[moc_obs],
            search_performed=True,
        )

        rel = updated.relationships[0]
        assert rel.evidence_search_status == EvidenceSearchStatus.SUPPORTING_EVIDENCE_FOUND
        assert rel.relationship_type == RelationshipType.TEMPORAL_PROGRESSION
        assert rel.is_anomaly is False
        assert "MRPL-MOC-2022-P201.pdf" in rel.explanation
        # Supporting observation non-destructively added to all_observations
        assert "OBS-MOC-2022" in [o.observation_id for o in updated.all_observations]
        assert updated.consistency_state == ConsistencyState.TEMPORALLY_EXPLAINED

    def test_4_completed_search_with_no_supporting_evidence_confirms_anomaly(self):
        """4. Completed search yielding no supporting evidence produces SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH & ANOMALOUS_PROGRESSION."""
        obs1 = EvidenceObservation(
            observation_id="OBS-19",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.0,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2019-01-01",
            source_document="INSP-2019.pdf",
            raw_statement="2019: 4.0 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-24",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=5.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-01-01",
            source_document="INSP-2024.pdf",
            raw_statement="2024: 5.5 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        rel_id = res.relationships[0].relationship_id

        updated = EvidenceReconciliationEngine.execute_anomaly_search(
            result=res,
            relationship_id=rel_id,
            supporting_evidence=[],  # Search completed, nothing found
            search_performed=True,
        )

        rel = updated.relationships[0]
        assert rel.evidence_search_status == EvidenceSearchStatus.SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH
        assert rel.relationship_type == RelationshipType.ANOMALOUS_PROGRESSION
        assert rel.is_anomaly is True
        assert updated.consistency_state == ConsistencyState.ANOMALOUS
        assert updated.reconciliation_status == ReconciliationStatus.ANOMALY_DETECTED

    def test_5_no_retrieved_moc_does_not_equal_moc_does_not_exist(self):
        """5. Initial candidate state preserves distinction: unperformed search does not assert absence of MOC."""
        obs1 = EvidenceObservation(
            observation_id="OBS-1", entity_tag="P-201", property_name="wall_thickness", value=4.0, observation_date="2019-01-01", source_document="D1.pdf", raw_statement="4.0 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-2", entity_tag="P-201", property_name="wall_thickness", value=5.0, observation_date="2024-01-01", source_document="D2.pdf", raw_statement="5.0 mm"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        rel = res.relationships[0]
        # Invariant: Must remain candidate until explicit search execution
        assert rel.relationship_type == RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE
        assert rel.relationship_type != RelationshipType.ANOMALOUS_PROGRESSION
        assert rel.evidence_search_status == EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED

    def test_6_supporting_evidence_preserves_provenance(self):
        """6. Supporting evidence retains complete provenance and document lineage."""
        moc_obs = EvidenceObservation(
            observation_id="OBS-MOC-PROV",
            entity_tag="P-201",
            property_name="moc_approval",
            value="Approved Spool Mod",
            observation_date="2023-05-12",
            source_document="MRPL-MOC-2023.pdf",
            document_id="DOC-MOC-2023",
            document_type="MOC Decisions",
            page_number=4,
            section="Engineering Modification Summary",
            source_span="char:120-250",
            revision_number="Rev 0",
            approval_status=ApprovalStatus.APPROVED,
            authority_tier=AuthorityTier.APPROVED_AUTHORITATIVE,
            extraction_method=ExtractionMethod.STRUCTURED_JSON,
            raw_statement="Verbatim MOC sign-off on 5.5 mm spool replacement.",
        )
        assert moc_obs.document_id == "DOC-MOC-2023"
        assert moc_obs.page_number == 4
        assert moc_obs.source_span == "char:120-250"
        assert moc_obs.authority_tier == AuthorityTier.APPROVED_AUTHORITATIVE

    def test_7_applicability_defaults_to_not_evaluated_without_policy(self):
        """7. Applicability defaults strictly to NOT_EVALUATED when no external policy is supplied."""
        obs1 = EvidenceObservation(
            observation_id="OBS-DS", entity_tag="P-201", property_name="design_pressure", value=16.0, unit="bar", source_document="DS.pdf", raw_statement="16.0 bar"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-MANUAL", entity_tag="P-201", property_name="design_pressure", value=15.5, unit="bar", source_document="Manual.pdf", raw_statement="15.5 bar"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert len(res.applicable_contexts) == 1
        ctx = res.applicable_contexts[0]
        assert ctx.applicability_status == ApplicabilityStatus.NOT_EVALUATED
        assert ctx.selected_observation_id is None
        assert set(ctx.alternative_observation_ids) == {"OBS-DS", "OBS-MANUAL"}

    def test_8_external_policy_explicitly_selects_observation(self):
        """8. External policy can explicitly resolve an applicable observation based on policy rules."""
        obs_statutory = EvidenceObservation(
            observation_id="OBS-STATUTORY",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            observation_date="2024-01-01",
            authority_tier=AuthorityTier.APPROVED_AUTHORITATIVE,
            approval_status=ApprovalStatus.APPROVED,
            source_document="MRPL-DS-P201.pdf",
            raw_statement="Statutory baseline: 16.0 bar",
        )
        obs_internal = EvidenceObservation(
            observation_id="OBS-INTERNAL",
            entity_tag="P-201",
            property_name="design_pressure",
            value=15.0,
            unit="bar",
            observation_date="2024-01-01",
            authority_tier=AuthorityTier.INTERNAL,
            approval_status=ApprovalStatus.DRAFT,
            source_document="Internal_Log.txt",
            raw_statement="Log: 15.0 bar",
        )

        policy = ApplicabilityPolicy(
            policy_identifier="STATUTORY_MANDATORY_BASELINE_V1",
            description="Prioritize APPROVED_AUTHORITATIVE and APPROVED records",
            preferred_authority_tiers=[AuthorityTier.APPROVED_AUTHORITATIVE, AuthorityTier.APPROVED],
            preferred_approval_statuses=[ApprovalStatus.APPROVED],
            require_verified_date=True,
        )

        res = EvidenceReconciliationEngine.reconcile([obs_statutory, obs_internal], policy=policy)
        assert len(res.applicable_contexts) == 1
        ctx = res.applicable_contexts[0]
        assert ctx.applicability_status == ApplicabilityStatus.EVALUATED_APPLICABLE
        assert ctx.selected_observation_id == "OBS-STATUTORY"
        assert ctx.policy_identifier == "STATUTORY_MANDATORY_BASELINE_V1"

    def test_9_alternative_observations_remain_preserved_after_applicability_selection(self):
        """9. Alternative non-selected observations remain completely preserved in context and all_observations."""
        obs1 = EvidenceObservation(
            observation_id="OBS-A", entity_tag="P-201", property_name="wall_thickness", value=4.5, authority_tier=AuthorityTier.APPROVED, source_document="A.pdf", raw_statement="4.5 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-B", entity_tag="P-201", property_name="wall_thickness", value=4.1, authority_tier=AuthorityTier.INTERNAL, source_document="B.pdf", raw_statement="4.1 mm"
        )
        policy = ApplicabilityPolicy(
            policy_identifier="TIER_PREFERENCE_POLICY",
            preferred_authority_tiers=[AuthorityTier.APPROVED, AuthorityTier.INTERNAL],
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2], policy=policy)
        ctx = res.applicable_contexts[0]
        assert ctx.selected_observation_id == "OBS-A"
        assert "OBS-B" in ctx.alternative_observation_ids
        # Invariant: Neither observation deleted
        assert len(res.all_observations) == 2

    def test_10_conflicting_observations_never_averaged_or_deleted(self):
        """10. Conflicting observations are never averaged, merged, or deleted."""
        obs1 = EvidenceObservation(
            observation_id="OBS-C1", entity_tag="P-201", property_name="wall_thickness", value=4.5, unit="mm", observation_date="2024-06-01", measurement_location="CML-01", source_document="Doc1.pdf", raw_statement="4.5 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-C2", entity_tag="P-201", property_name="wall_thickness", value=3.2, unit="mm", observation_date="2024-06-01", measurement_location="CML-01", source_document="Doc2.pdf", raw_statement="3.2 mm"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        values = [o.value for o in res.all_observations]
        assert 4.5 in values
        assert 3.2 in values
        assert 3.85 not in values  # No numeric average!

    def test_11_approved_vs_draft_revision_handling_preserved(self):
        """11. Approved vs Draft revision relationship correctly produces UNAPPROVED_DRAFT."""
        obs1 = EvidenceObservation(
            observation_id="OBS-APPR", entity_tag="P-201", property_name="pressure", value=10.0, revision_number="Rev 1", approval_status=ApprovalStatus.APPROVED, source_document="Appr.pdf", raw_statement="10 bar"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-DRAFT", entity_tag="P-201", property_name="pressure", value=12.0, revision_number="Rev 2", approval_status=ApprovalStatus.DRAFT, source_document="Draft.pdf", raw_statement="12 bar"
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs1, obs2)
        assert rel.relationship_type == RelationshipType.UNAPPROVED_DRAFT

    def test_12_missing_date_remains_temporal_order_unknown_no_rate(self):
        """12. Missing date produces TEMPORAL_ORDER_UNKNOWN and inhibits rate calculation."""
        obs1 = EvidenceObservation(
            observation_id="OBS-1", entity_tag="P-201", property_name="wall_thickness", value=5.0, unit="mm", observation_date=None, source_document="A.pdf", raw_statement="5.0 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-2", entity_tag="P-201", property_name="wall_thickness", value=4.0, unit="mm", observation_date=None, source_document="B.pdf", raw_statement="4.0 mm"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert len(res.derived_observations) == 0
        assert res.relationships[0].relationship_type == RelationshipType.TEMPORAL_ORDER_UNKNOWN

    def test_13_incompatible_units_cannot_generate_derived_rate(self):
        """13. Incompatible units prevent rate calculation without silent conversion."""
        obs1 = EvidenceObservation(
            observation_id="OBS-U1", entity_tag="P-201", property_name="wall_thickness", value=5.0, unit="mm", observation_date="2020-01-01", source_document="A.pdf", raw_statement="5.0 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-U2", entity_tag="P-201", property_name="wall_thickness", value=0.15, unit="inches", observation_date="2024-01-01", source_document="B.pdf", raw_statement="0.15 in"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert len(res.derived_observations) == 0

    def test_14_high_risk_unresolved_conflict_requires_human_investigation_without_verdict(self):
        """14. High-risk task with unresolved conflict sets requires_human_investigation without operational verdicts."""
        obs1 = EvidenceObservation(
            observation_id="OBS-1", entity_tag="P-201", property_name="wall_thickness", value=4.5, unit="mm", observation_date="2024-06-01", measurement_location="CML-01", source_document="A.pdf", raw_statement="4.5 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-2", entity_tag="P-201", property_name="wall_thickness", value=3.1, unit="mm", observation_date="2024-06-01", measurement_location="CML-01", source_document="B.pdf", raw_statement="3.1 mm"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2], is_high_risk_task=True)
        assert res.requires_human_investigation is True
        # Invariant: No statutory verdict or fit/unfit claim injected
        assert not hasattr(res, "fit_for_service")
        assert not hasattr(res, "is_safe")

    def test_15_multi_entity_scopes_remain_independent(self):
        """15. Observations across multiple entities remain strictly isolated."""
        obs1 = EvidenceObservation(
            observation_id="OBS-P201", entity_tag="P-201", property_name="wall_thickness", value=4.5, unit="mm", source_document="A.pdf", raw_statement="P-201: 4.5 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-P101", entity_tag="P-101", property_name="wall_thickness", value=3.9, unit="mm", source_document="B.pdf", raw_statement="P-101: 3.9 mm"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2], entity_scope=["P-201", "P-101"])
        assert len(res.relationships) == 0
        assert len(res.property_timelines) == 2

    def test_16_claim_provenance_export(self):
        """16. Claim provenance export retains full source lineage and flags contested status."""
        obs1 = EvidenceObservation(
            observation_id="OBS-1", entity_tag="P-201", property_name="wall_thickness", value=4.5, unit="mm", observation_date="2024-06-01", measurement_location="CML-01", source_document="A.pdf", raw_statement="4.5 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-2", entity_tag="P-201", property_name="wall_thickness", value=3.1, unit="mm", observation_date="2024-06-01", measurement_location="CML-01", source_document="B.pdf", raw_statement="3.1 mm"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        exported = EvidenceReconciliationEngine.export_to_claim_provenance(res)
        assert len(exported) == 2
        for item in exported:
            assert "observation_id" in item
            assert "source_document" in item
            assert "raw_statement" in item
            assert item["is_contested"] is True
