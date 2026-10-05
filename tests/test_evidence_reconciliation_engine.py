# tests/test_evidence_reconciliation_engine.py
"""
MRPL Sovereign AI Workbench — Phase 3B Test Suite:
Relational Classification & Industrial Evidence Reconciliation Engine.

Validates:
A. Normal degradation (2019=6.0 mm, 2024=4.5 mm, same CML -> TEMPORAL_PROGRESSION, TEMPORALLY_MAPPED, DerivedObservation = 0.30 mm/year)
B. Multi-year sequence (2019=6.0, 2021=5.4, 2023=4.8, 2024=4.5 -> chronological PropertyTimeline)
C. Same location conflict (2024 CML-02=4.5, 2024 CML-02=3.2 -> SIMULTANEOUS_DISCREPANCY, EvidenceConflict, both observations preserved)
D. Different CMLs (CML-01=4.8, CML-02=4.5 -> SPATIALLY_DISTINCT, NO conflict)
E. Corroborating documents (same value/context from independent sources -> CORROBORATING)
F. Thickness increase (2019=4.0, 2024=5.5 -> ANOMALOUS_PROGRESSION_CANDIDATE, NOT ANOMALOUS_PROGRESSION)
G. Missing date -> TEMPORAL_ORDER_UNKNOWN, no derived rate
H. Missing revision -> Safe degradation without assumption
I. Approved vs Draft -> UNAPPROVED_DRAFT
J. Explicit approved MOC supersedence -> SUPERSEDED_REVISION
K. Ambiguous revision lineage -> SUPERSEDENCE_UNCERTAIN
L. Different entities (P-201 vs PSV-201) -> no false relationship
M. Different properties (wall_thickness vs design_pressure) -> no false relationship
N. Authority disagreement (high-tier vs informal) -> AUTHORITY_DISCREPANCY, both preserved
O. Range observation ("4.4 - 4.6 mm") -> no averaging
P. Incompatible units -> no derived calculation
Q. Multi-entity comparison (P-201 + P-101) -> independent timelines
R. Empty observation list -> safe ReconciliationResult, INSUFFICIENT_CONTEXT
S. Duplicate identical observation -> CORROBORATING without deleting source observation
T. Zero numeric consistency or authority scores anywhere in result
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
    ReconciliationResult,
)
from backend.services.evidence.observation_extractor import EvidenceObservationExtractor
from backend.services.evidence.reconciliation_engine import EvidenceReconciliationEngine


class TestEvidenceReconciliationEngine:
    """Comprehensive test matrix A through T for Phase 3B Reconciliation Engine."""

    def test_a_normal_degradation(self):
        """A. Normal degradation: 2019=6.0 mm, 2024=4.5 mm at same CML -> TEMPORAL_PROGRESSION & 0.30 mm/year rate."""
        obs1 = EvidenceObservation(
            observation_id="OBS-P201-2019",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=6.0,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2019-01-01",
            source_document="MRPL-INSP-2019-P201.pdf",
            raw_statement="2019 wall thickness at CML-01: 6.0 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-P201-2024",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-01-01",
            source_document="MRPL-INSP-2024-P201.pdf",
            raw_statement="2024 wall thickness at CML-01: 4.5 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2], entity_scope=["P-201"])
        assert res.consistency_state == ConsistencyState.TEMPORALLY_EXPLAINED
        assert res.reconciliation_status == ReconciliationStatus.TEMPORALLY_MAPPED
        assert len(res.relationships) == 1
        assert res.relationships[0].relationship_type == RelationshipType.TEMPORAL_PROGRESSION

        assert len(res.derived_observations) == 1
        deriv = res.derived_observations[0]
        assert deriv.property_name == "observed_corrosion_rate"
        assert deriv.derived_value == 0.30  # (6.0 - 4.5) / 5.0 years = 0.30 mm/year
        assert deriv.time_interval_years == 5.0

    def test_b_multi_year_sequence(self):
        """B. Multi-year sequence: 2019=6.0, 2021=5.4, 2023=4.8, 2024=4.5 -> Chronological timeline."""
        years_vals = [(2019, 6.0), (2021, 5.4), (2023, 4.8), (2024, 4.5)]
        observations = [
            EvidenceObservation(
                observation_id=f"OBS-P201-{y}",
                entity_tag="P-201",
                property_name="wall_thickness",
                value=v,
                unit="mm",
                measurement_location="CML-02",
                observation_date=f"{y}-06-01",
                source_document=f"INSP-{y}.pdf",
                raw_statement=f"Survey {y}: {v} mm at CML-02",
            )
            for y, v in years_vals
        ]
        # Shuffle inputs to verify deterministic sorting
        res = EvidenceReconciliationEngine.reconcile([observations[2], observations[0], observations[3], observations[1]])
        timeline = res.property_timelines.get("P-201:wall_thickness:CML-02")
        assert timeline is not None
        sorted_dates = [o.observation_date for o in timeline.observations_chronological]
        assert sorted_dates == ["2019-06-01", "2021-06-01", "2023-06-01", "2024-06-01"]
        assert timeline.temporal_trend == "MONOTONIC_DECREASE"
        assert not timeline.has_anomalies

    def test_c_same_location_conflict(self):
        """C. Same location conflict: 2024 CML-02=4.5, 2024 CML-02=3.2 -> SIMULTANEOUS_DISCREPANCY & EvidenceConflict."""
        obs1 = EvidenceObservation(
            observation_id="OBS-A-45",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-02",
            observation_date="2024-06-01",
            source_document="SurveyA.pdf",
            raw_statement="Survey A reports 4.5 mm at CML-02",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-B-32",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=3.2,
            unit="mm",
            measurement_location="CML-02",
            observation_date="2024-06-01",
            source_document="SurveyB.pdf",
            raw_statement="Survey B reports 3.2 mm at CML-02",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.consistency_state == ConsistencyState.CONFLICTING
        assert res.reconciliation_status == ReconciliationStatus.UNRESOLVED_CONFLICT
        assert len(res.active_conflicts) == 1
        assert "OBS-A-45" in res.active_conflicts[0].conflicting_observation_ids
        assert "OBS-B-32" in res.active_conflicts[0].conflicting_observation_ids
        # Invariant: Both observations remain preserved!
        assert len(res.all_observations) == 2

    def test_d_different_cmls_spatially_distinct(self):
        """D. Different CMLs: CML-01=4.8, CML-02=4.5 -> SPATIALLY_DISTINCT, NO conflict."""
        obs1 = EvidenceObservation(
            observation_id="OBS-CML1",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.8,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-06-01",
            source_document="Survey.pdf",
            raw_statement="CML-01 thickness: 4.8 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-CML2",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-02",
            observation_date="2024-06-01",
            source_document="Survey.pdf",
            raw_statement="CML-02 thickness: 4.5 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.consistency_state == ConsistencyState.SPATIALLY_DISTINCT
        assert res.reconciliation_status == ReconciliationStatus.SPATIALLY_MAPPED
        assert len(res.active_conflicts) == 0
        assert len(res.relationships) == 1
        assert res.relationships[0].relationship_type == RelationshipType.SPATIALLY_DISTINCT

    def test_e_corroborating_documents(self):
        """E. Corroborating documents: matching value/context from independent sources -> CORROBORATING."""
        obs1 = EvidenceObservation(
            observation_id="OBS-DOC1",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-02",
            observation_date="2024-06-01",
            source_document="Survey1.pdf",
            raw_statement="Doc 1: 4.5 mm at CML-02",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-DOC2",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-02",
            observation_date="2024-06-01",
            source_document="Survey2.pdf",
            raw_statement="Doc 2: 4.5 mm at CML-02",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.consistency_state == ConsistencyState.CONSISTENT
        assert res.reconciliation_status == ReconciliationStatus.NON_CONFLICTING
        assert len(res.relationships) == 1
        assert res.relationships[0].relationship_type == RelationshipType.CORROBORATING

    def test_f_thickness_increase_anomalous_candidate(self):
        """F. Thickness increase: 2019=4.0, 2024=5.5 -> ANOMALOUS_PROGRESSION_CANDIDATE (NOT ANOMALOUS_PROGRESSION)."""
        obs1 = EvidenceObservation(
            observation_id="OBS-2019",
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
            observation_id="OBS-2024",
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
        assert res.consistency_state == ConsistencyState.ANOMALOUS
        assert res.reconciliation_status == ReconciliationStatus.ANOMALY_DETECTED
        assert len(res.relationships) == 1
        rel = res.relationships[0]
        # Invariant: Must be CANDIDATE because search not yet executed
        assert rel.relationship_type == RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE
        assert rel.relationship_type != RelationshipType.ANOMALOUS_PROGRESSION
        assert rel.evidence_search_status == EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED
        assert rel.is_anomaly is True

    def test_g_missing_date_temporal_order_unknown(self):
        """G. Missing date: TEMPORAL_ORDER_UNKNOWN & no derived rate calculated."""
        obs1 = EvidenceObservation(
            observation_id="OBS-DATED",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-01-01",
            source_document="INSP-2024.pdf",
            raw_statement="2024: 4.5 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-UNDATED",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=3.8,
            unit="mm",
            measurement_location="CML-01",
            observation_date=None,  # Missing date
            source_document="Unknown_Log.pdf",
            raw_statement="Log: 3.8 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.consistency_state == ConsistencyState.UNCERTAIN
        assert len(res.relationships) == 1
        assert res.relationships[0].relationship_type == RelationshipType.TEMPORAL_ORDER_UNKNOWN
        assert len(res.derived_observations) == 0  # No rate computed without dates

    def test_h_missing_revision_safe_degradation(self):
        """H. Missing revision metadata degrades safely without assumptions."""
        obs1 = EvidenceObservation(
            observation_id="OBS-REV-NONE",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            revision_number=None,
            approval_status=ApprovalStatus.UNKNOWN,
            source_document="SpecA.pdf",
            raw_statement="Design pressure: 16.0 bar",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-REV-NONE2",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            revision_number=None,
            approval_status=ApprovalStatus.UNKNOWN,
            source_document="SpecB.pdf",
            raw_statement="Design pressure: 16.0 bar",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.consistency_state == ConsistencyState.CONSISTENT
        assert res.relationships[0].relationship_type == RelationshipType.CORROBORATING

    def test_i_approved_vs_draft_unapproved_draft(self):
        """I. Approved vs Draft -> UNAPPROVED_DRAFT."""
        obs_appr = EvidenceObservation(
            observation_id="OBS-APPR",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            revision_number="Rev 2",
            approval_status=ApprovalStatus.APPROVED,
            source_document="MRPL-DS-P201.pdf",
            raw_statement="Approved datasheet: 16.0 bar",
        )
        obs_draft = EvidenceObservation(
            observation_id="OBS-DRAFT",
            entity_tag="P-201",
            property_name="design_pressure",
            value=18.0,
            unit="bar",
            revision_number="Rev 3-Draft",
            approval_status=ApprovalStatus.DRAFT,
            source_document="MOC_Draft_P201.pdf",
            raw_statement="Proposed revision 3 draft: 18.0 bar",
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs_appr, obs_draft)
        assert rel is not None
        assert rel.relationship_type == RelationshipType.UNAPPROVED_DRAFT

    def test_j_explicit_approved_moc_supersedence(self):
        """J. Explicit approved MOC supersedence -> SUPERSEDED_REVISION."""
        obs_old = EvidenceObservation(
            observation_id="OBS-OLD",
            entity_tag="P-201",
            property_name="design_pressure",
            value=14.0,
            unit="bar",
            revision_number="Rev 0",
            approval_status=ApprovalStatus.SUPERSEDED,
            source_document="Old_DS.pdf",
            raw_statement="Old baseline: 14.0 bar",
        )
        obs_new = EvidenceObservation(
            observation_id="OBS-NEW",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            revision_number="Rev 1",
            approval_status=ApprovalStatus.APPROVED,
            source_document="MOC_Approved_P201.pdf",
            raw_statement="Approved MOC: 16.0 bar",
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs_old, obs_new)
        assert rel is not None
        assert rel.relationship_type == RelationshipType.SUPERSEDED_REVISION

    def test_k_ambiguous_revision_lineage(self):
        """K. Ambiguous revision lineage -> SUPERSEDENCE_UNCERTAIN."""
        obs_a = EvidenceObservation(
            observation_id="OBS-REVA",
            entity_tag="P-201",
            property_name="design_pressure",
            value=15.0,
            unit="bar",
            revision_number="Rev A",
            approval_status=ApprovalStatus.PENDING_MOC,
            source_document="DocA.pdf",
            raw_statement="Rev A: 15.0 bar",
        )
        obs_b = EvidenceObservation(
            observation_id="OBS-REVB",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            revision_number="Rev B",
            approval_status=ApprovalStatus.PENDING_MOC,
            source_document="DocB.pdf",
            raw_statement="Rev B: 16.0 bar",
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs_a, obs_b)
        assert rel is not None
        assert rel.relationship_type == RelationshipType.SUPERSEDENCE_UNCERTAIN

    def test_l_different_entities_no_false_relationship(self):
        """L. Different entities: P-201 vs PSV-201 -> No false relationship."""
        obs1 = EvidenceObservation(
            observation_id="OBS-P201",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            source_document="P201.pdf",
            raw_statement="P-201 design pressure = 16.0 bar",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-PSV201",
            entity_tag="PSV-201",
            property_name="design_pressure",
            value=18.5,
            unit="bar",
            source_document="PSV201.pdf",
            raw_statement="PSV-201 set pressure = 18.5 bar",
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs1, obs2)
        assert rel is None

    def test_m_different_properties_no_false_relationship(self):
        """M. Different properties: wall_thickness vs design_pressure -> No false relationship."""
        obs1 = EvidenceObservation(
            observation_id="OBS-THICK",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            source_document="P201.pdf",
            raw_statement="P-201 wall thickness: 4.5 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-PRESS",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            unit="bar",
            source_document="P201.pdf",
            raw_statement="P-201 design pressure: 16.0 bar",
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs1, obs2)
        assert rel is None

    def test_n_authority_disagreement_both_preserved(self):
        """N. Authority disagreement: high-authority vs informal -> AUTHORITY_DISCREPANCY, both preserved."""
        obs_high = EvidenceObservation(
            observation_id="OBS-STATUTORY",
            entity_tag="P-201",
            property_name="operating_temperature",
            value=150.0,
            unit="°C",
            observation_date="2024-06-01",
            authority_tier=AuthorityTier.APPROVED_AUTHORITATIVE,
            source_document="MRPL-DS-P201.pdf",
            raw_statement="Statutory datasheet: 150 C",
        )
        obs_low = EvidenceObservation(
            observation_id="OBS-INFORMAL",
            entity_tag="P-201",
            property_name="operating_temperature",
            value=175.0,
            unit="°C",
            observation_date="2024-06-01",
            authority_tier=AuthorityTier.INFORMAL,
            source_document="Operator_Scratchpad.txt",
            raw_statement="Operator note: running at 175 C",
        )
        res = EvidenceReconciliationEngine.reconcile([obs_high, obs_low])
        assert res.consistency_state == ConsistencyState.CONFLICTING
        assert len(res.relationships) == 1
        assert res.relationships[0].relationship_type == RelationshipType.AUTHORITY_DISCREPANCY
        # Invariant: Neither observation deleted or declared ground truth
        assert len(res.all_observations) == 2
        obs_ids = [o.observation_id for o in res.all_observations]
        assert "OBS-STATUTORY" in obs_ids
        assert "OBS-INFORMAL" in obs_ids

    def test_o_range_observation_no_averaging(self):
        """O. Range observation string ('4.4 - 4.6 mm') is preserved verbatim without numeric averaging."""
        obs = EvidenceObservation(
            observation_id="OBS-RANGE",
            entity_tag="P-201",
            property_name="wall_thickness",
            value="4.4 - 4.6",
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-06-01",
            source_document="Survey.pdf",
            raw_statement="Survey: 4.4 - 4.6 mm across elbow",
        )
        res = EvidenceReconciliationEngine.reconcile([obs])
        assert res.all_observations[0].value == "4.4 - 4.6"
        assert res.all_observations[0].value != 4.5

    def test_p_incompatible_units_no_derived_calculation(self):
        """P. Incompatible units -> No derived progression calculation."""
        obs1 = EvidenceObservation(
            observation_id="OBS-U1",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2019-01-01",
            source_document="Doc1.pdf",
            raw_statement="4.5 mm",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-U2",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=0.15,
            unit="inches",  # Incompatible unit
            measurement_location="CML-01",
            observation_date="2024-01-01",
            source_document="Doc2.pdf",
            raw_statement="0.15 inches",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert len(res.derived_observations) == 0

    def test_q_multi_entity_independent_timelines(self):
        """Q. Multi-entity comparison: P-201 + P-101 maintain completely independent timelines."""
        obs_p201 = EvidenceObservation(
            observation_id="OBS-P201",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-06-01",
            source_document="P201.pdf",
            raw_statement="P-201: 4.5 mm",
        )
        obs_p101 = EvidenceObservation(
            observation_id="OBS-P101",
            entity_tag="P-101",
            property_name="wall_thickness",
            value=3.8,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-06-01",
            source_document="P101.pdf",
            raw_statement="P-101: 3.8 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs_p201, obs_p101], entity_scope=["P-201", "P-101"])
        assert len(res.property_timelines) == 2
        assert "P-201:wall_thickness:CML-01" in res.property_timelines
        assert "P-101:wall_thickness:CML-01" in res.property_timelines
        # No cross-entity relationship
        assert len(res.relationships) == 0

    def test_r_empty_observation_list_insufficient_context(self):
        """R. Empty observation list returns safe ReconciliationResult with INSUFFICIENT_CONTEXT."""
        res = EvidenceReconciliationEngine.reconcile([])
        assert res.consistency_state == ConsistencyState.INSUFFICIENT_CONTEXT
        assert res.reconciliation_status == ReconciliationStatus.INSUFFICIENT_CONTEXT
        assert len(res.all_observations) == 0
        assert len(res.active_conflicts) == 0

    def test_s_duplicate_identical_observation(self):
        """S. Duplicate identical observation is handled without deleting either instance."""
        obs = EvidenceObservation(
            observation_id="OBS-DUP",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            measurement_location="CML-01",
            observation_date="2024-06-01",
            source_document="Survey.pdf",
            raw_statement="4.5 mm at CML-01",
        )
        res = EvidenceReconciliationEngine.reconcile([obs, obs])
        assert len(res.all_observations) == 2
        assert len(res.relationships) == 1
        assert res.relationships[0].relationship_type == RelationshipType.CORROBORATING

    def test_t_no_numeric_consistency_score_anywhere(self):
        """T. Invariant: Consistency state is strictly categorical without numeric scores."""
        obs = EvidenceObservation(
            observation_id="OBS-TEST",
            entity_tag="P-201",
            property_name="wall_thickness",
            value=4.5,
            unit="mm",
            source_document="Survey.pdf",
            raw_statement="4.5 mm",
        )
        res = EvidenceReconciliationEngine.reconcile([obs])
        # Verify no numeric consistency or authority score fields exist on ReconciliationResult
        assert not hasattr(res, "consistency_score")
        assert not hasattr(res, "confidence_score")
        assert not hasattr(res, "authority_score")
        assert isinstance(res.consistency_state, ConsistencyState)
        assert isinstance(res.reconciliation_status, ReconciliationStatus)
