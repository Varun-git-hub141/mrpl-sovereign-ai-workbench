# tests/test_evidence_phase3d_integration.py
"""
MRPL Sovereign AI Workbench — Phase 3D Integration & End-to-End Validation Test Suite.

Validates:
A. Normal degradation via API (2019=6.0 mm, 2024=4.5 mm -> TEMPORAL_PROGRESSION, 0.30 mm/yr rate)
B. Apparent growth & anomaly search lifecycle (Candidate -> Search -> Confirmed Anomaly & High-Risk Gate)
C. Same CML / same time / different values (Discrepancy, Unresolved conflict, zero averaging)
D. Different CMLs (SPATIALLY_DISTINCT, no conflict)
E. Approved revision with explicit MOC (SUPERSEDED_REVISION)
F. Draft vs approved (UNAPPROVED_DRAFT, no revision-number authority assumption)
G. Missing date (TEMPORAL_ORDER_UNKNOWN, no derived rate)
H. Missing revision (Safe degradation, no invented hierarchy)
I. Authority disagreement (AUTHORITY_DISCREPANCY, ConflictSeverity=UNCLASSIFIED)
J. Multi-entity input (Independent timelines, zero cross-entity relationships)
K. External applicability policy (NOT_EVALUATED default, policy selection, alternatives preserved)
L. Claim provenance (Complete lineage, is_contested flag on unresolved conflicts)
M. API endpoint POST /api/evidence/reconcile via TestClient
N. API endpoint GET /api/evidence/timeline/{entity_tag} via TestClient
O. Safety boundary validation (Zero operational verdicts, fit/unfit, or safe/unsafe claims)
"""

import pytest
from fastapi.testclient import TestClient
from backend.app import app
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

client = TestClient(app)


class TestEvidencePhase3DIntegration:
    """End-to-End API and Integration test suite for Phase 3D."""

    def test_a_normal_degradation_api_e2e(self):
        """A. Normal degradation: 2019=6.0 mm, 2024=4.5 mm -> TEMPORAL_PROGRESSION & 0.30 mm/year rate."""
        payload = {
            "observations": [
                {
                    "entity_tag": "P-201",
                    "property_name": "wall_thickness",
                    "value": 6.0,
                    "unit": "mm",
                    "measurement_location": "CML-01",
                    "observation_date": "2019-01-01",
                    "source_document": "INSP-2019.pdf",
                    "raw_statement": "2019: 6.0 mm",
                },
                {
                    "entity_tag": "P-201",
                    "property_name": "wall_thickness",
                    "value": 4.5,
                    "unit": "mm",
                    "measurement_location": "CML-01",
                    "observation_date": "2024-01-01",
                    "source_document": "INSP-2024.pdf",
                    "raw_statement": "2024: 4.5 mm",
                },
            ],
            "entity_scope": ["P-201"],
        }
        resp = client.post("/api/evidence/reconcile", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["consistency_state"] == "TEMPORALLY_EXPLAINED"
        assert data["reconciliation_status"] == "TEMPORALLY_MAPPED"
        assert len(data["relationships"]) == 1
        assert data["relationships"][0]["relationship_type"] == "TEMPORAL_PROGRESSION"
        assert len(data["derived_observations"]) == 1
        assert data["derived_observations"][0]["derived_value"] == 0.30

    def test_b_apparent_growth_anomaly_lifecycle_and_high_risk_gate(self):
        """B. Apparent growth candidate -> search executed -> confirmed anomaly & high-risk gate."""
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
        # Initial candidate detection
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2], is_high_risk_task=True)
        rel = res.relationships[0]
        assert rel.relationship_type == RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE
        assert rel.evidence_search_status == EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED

        # After completed search without supporting MOC
        updated = EvidenceReconciliationEngine.execute_anomaly_search(
            result=res,
            relationship_id=rel.relationship_id,
            supporting_evidence=[],
            search_performed=True,
        )
        assert updated.relationships[0].relationship_type == RelationshipType.ANOMALOUS_PROGRESSION
        assert updated.relationships[0].evidence_search_status == EvidenceSearchStatus.SUPPORTING_EVIDENCE_NOT_FOUND_AFTER_SEARCH
        
        # High-risk task flags human investigation
        gated = EvidenceReconciliationEngine.evaluate_high_risk_gate(updated, is_high_risk_task=True)
        assert gated.requires_human_investigation is True

    def test_c_same_cml_same_time_different_values_no_averaging(self):
        """C. Discrepancy at same CML and time: unresolved conflict with zero numeric averaging."""
        payload = {
            "observations": [
                {
                    "entity_tag": "P-201",
                    "property_name": "wall_thickness",
                    "value": 4.5,
                    "unit": "mm",
                    "measurement_location": "CML-01",
                    "observation_date": "2024-06-01",
                    "source_document": "SurveyA.pdf",
                    "raw_statement": "4.5 mm at CML-01",
                },
                {
                    "entity_tag": "P-201",
                    "property_name": "wall_thickness",
                    "value": 3.2,
                    "unit": "mm",
                    "measurement_location": "CML-01",
                    "observation_date": "2024-06-01",
                    "source_document": "SurveyB.pdf",
                    "raw_statement": "3.2 mm at CML-01",
                },
            ]
        }
        resp = client.post("/api/evidence/reconcile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["consistency_state"] == "CONFLICTING"
        assert data["reconciliation_status"] == "UNRESOLVED_CONFLICT"
        assert len(data["active_conflicts"]) == 1
        assert len(data["all_observations"]) == 2
        vals = [o["value"] for o in data["all_observations"]]
        assert 4.5 in vals
        assert 3.2 in vals
        assert 3.85 not in vals

    def test_d_different_cmls_spatially_distinct(self):
        """D. Different CMLs: SPATIALLY_DISTINCT and no conflict."""
        payload = {
            "observations": [
                {"entity_tag": "P-201", "property_name": "wall_thickness", "value": 4.8, "measurement_location": "CML-01", "observation_date": "2024-06-01", "source_document": "A.pdf", "raw_statement": "4.8 mm"},
                {"entity_tag": "P-201", "property_name": "wall_thickness", "value": 4.5, "measurement_location": "CML-02", "observation_date": "2024-06-01", "source_document": "B.pdf", "raw_statement": "4.5 mm"},
            ]
        }
        resp = client.post("/api/evidence/reconcile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["consistency_state"] == "SPATIALLY_DISTINCT"
        assert data["reconciliation_status"] == "SPATIALLY_MAPPED"
        assert len(data["active_conflicts"]) == 0

    def test_e_approved_revision_with_explicit_moc_superseded(self):
        """E. Approved revision retiring older version -> SUPERSEDED_REVISION."""
        obs_old = EvidenceObservation(
            observation_id="OBS-OLD",
            entity_tag="P-201",
            property_name="design_pressure",
            value=14.0,
            revision_number="Rev 0",
            approval_status=ApprovalStatus.SUPERSEDED,
            source_document="Old.pdf",
            raw_statement="Old: 14 bar",
        )
        obs_new = EvidenceObservation(
            observation_id="OBS-NEW",
            entity_tag="P-201",
            property_name="design_pressure",
            value=16.0,
            revision_number="Rev 1",
            approval_status=ApprovalStatus.APPROVED,
            source_document="MOC.pdf",
            raw_statement="MOC: 16 bar",
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs_old, obs_new)
        assert rel.relationship_type == RelationshipType.SUPERSEDED_REVISION

    def test_f_draft_vs_approved_unapproved_draft(self):
        """F. Draft alongside approved -> UNAPPROVED_DRAFT without revision-only authority assumption."""
        obs_appr = EvidenceObservation(
            observation_id="OBS-A", entity_tag="P-201", property_name="pressure", value=15.0, revision_number="Rev 1", approval_status=ApprovalStatus.APPROVED, source_document="DS.pdf", raw_statement="15 bar"
        )
        obs_draft = EvidenceObservation(
            observation_id="OBS-D", entity_tag="P-201", property_name="pressure", value=18.0, revision_number="Rev 2", approval_status=ApprovalStatus.DRAFT, source_document="Draft.pdf", raw_statement="18 bar"
        )
        rel = EvidenceReconciliationEngine.classify_relationship(obs_appr, obs_draft)
        assert rel.relationship_type == RelationshipType.UNAPPROVED_DRAFT

    def test_g_missing_date_temporal_order_unknown(self):
        """G. Missing date: TEMPORAL_ORDER_UNKNOWN and no rate calculated."""
        obs1 = EvidenceObservation(
            observation_id="OBS-1", entity_tag="P-201", property_name="wall_thickness", value=5.0, unit="mm", observation_date=None, source_document="A.pdf", raw_statement="5.0 mm"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-2", entity_tag="P-201", property_name="wall_thickness", value=4.2, unit="mm", observation_date="2024-01-01", source_document="B.pdf", raw_statement="4.2 mm"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.relationships[0].relationship_type == RelationshipType.TEMPORAL_ORDER_UNKNOWN
        assert len(res.derived_observations) == 0

    def test_h_missing_revision_safe_degradation(self):
        """H. Missing revision degrades safely without inventing a hierarchy."""
        obs1 = EvidenceObservation(
            observation_id="OBS-R1", entity_tag="P-201", property_name="vibration", value=4.5, revision_number=None, approval_status=ApprovalStatus.UNKNOWN, source_document="A.pdf", raw_statement="4.5 mm/s"
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-R2", entity_tag="P-201", property_name="vibration", value=4.5, revision_number=None, approval_status=ApprovalStatus.UNKNOWN, source_document="B.pdf", raw_statement="4.5 mm/s"
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.consistency_state == ConsistencyState.CONSISTENT
        assert res.relationships[0].relationship_type == RelationshipType.CORROBORATING

    def test_i_authority_disagreement_unclassified_severity(self):
        """I. Authority disagreement produces AUTHORITY_DISCREPANCY with UNCLASSIFIED severity."""
        obs1 = EvidenceObservation(
            observation_id="OBS-HIGH",
            entity_tag="P-201",
            property_name="temperature",
            value=140.0,
            observation_date="2024-01-01",
            authority_tier=AuthorityTier.APPROVED_AUTHORITATIVE,
            source_document="DS.pdf",
            raw_statement="140 C",
        )
        obs2 = EvidenceObservation(
            observation_id="OBS-LOW",
            entity_tag="P-201",
            property_name="temperature",
            value=165.0,
            observation_date="2024-01-01",
            authority_tier=AuthorityTier.INFORMAL,
            source_document="Notes.txt",
            raw_statement="165 C",
        )
        res = EvidenceReconciliationEngine.reconcile([obs1, obs2])
        assert res.relationships[0].relationship_type == RelationshipType.AUTHORITY_DISCREPANCY
        assert len(res.active_conflicts) == 1
        assert res.active_conflicts[0].severity == ConflictSeverity.UNCLASSIFIED

    def test_j_multi_entity_input_isolated_timelines(self):
        """J. Multi-entity input produces isolated timelines with zero cross-entity relationships."""
        payload = {
            "observations": [
                {"entity_tag": "P-201", "property_name": "wall_thickness", "value": 4.5, "unit": "mm", "source_document": "A.pdf", "raw_statement": "P-201: 4.5 mm"},
                {"entity_tag": "TK-201", "property_name": "wall_thickness", "value": 12.0, "unit": "mm", "source_document": "B.pdf", "raw_statement": "TK-201: 12.0 mm"},
            ],
            "entity_scope": ["P-201", "TK-201"],
        }
        resp = client.post("/api/evidence/reconcile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["relationships"]) == 0
        assert "P-201:wall_thickness:ALL" in data["property_timelines"]
        assert "TK-201:wall_thickness:ALL" in data["property_timelines"]

    def test_k_external_applicability_policy_selection(self):
        """K. External applicability policy selects preferred observation while preserving alternatives."""
        payload = {
            "observations": [
                {
                    "entity_tag": "P-201",
                    "property_name": "design_pressure",
                    "value": 16.0,
                    "unit": "bar",
                    "observation_date": "2024-01-01",
                    "authority_tier": "APPROVED_AUTHORITATIVE",
                    "approval_status": "APPROVED",
                    "source_document": "DS.pdf",
                    "raw_statement": "16.0 bar",
                },
                {
                    "entity_tag": "P-201",
                    "property_name": "design_pressure",
                    "value": 15.0,
                    "unit": "bar",
                    "observation_date": "2024-01-01",
                    "authority_tier": "INTERNAL",
                    "approval_status": "DRAFT",
                    "source_document": "Log.txt",
                    "raw_statement": "15.0 bar",
                },
            ],
            "policy": {
                "policy_identifier": "STATUTORY_PRIORITY_V1",
                "preferred_authority_tiers": ["APPROVED_AUTHORITATIVE", "APPROVED"],
                "preferred_approval_statuses": ["APPROVED"],
                "require_verified_date": True,
            },
        }
        resp = client.post("/api/evidence/reconcile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        ctx = data["applicable_contexts"][0]
        assert ctx["applicability_status"] == "EVALUATED_APPLICABLE"
        assert ctx["policy_identifier"] == "STATUTORY_PRIORITY_V1"
        assert len(ctx["alternative_observation_ids"]) == 1

    def test_l_claim_provenance_integration(self):
        """L. Claim provenance preserves complete source lineage and flags contested state."""
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
            assert item["is_contested"] is True
            assert item["source_document"] in ("A.pdf", "B.pdf")

    def test_m_timeline_api_get_endpoint(self):
        """M. GET /api/evidence/timeline/{entity_tag} returns deterministic property timelines."""
        resp = client.get("/api/evidence/timeline/P-201")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_tag"] == "P-201"
        assert "timelines" in data
        assert isinstance(data["timelines"], dict)

    def test_n_reconcile_api_empty_payload_safe(self):
        """N. POST /api/evidence/reconcile with empty payload degrades safely to INSUFFICIENT_CONTEXT."""
        resp = client.post("/api/evidence/reconcile", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["consistency_state"] == "INSUFFICIENT_CONTEXT"
        assert data["reconciliation_status"] == "INSUFFICIENT_CONTEXT"
        assert len(data["all_observations"]) == 0

    def test_o_security_safety_boundary_no_operational_verdict(self):
        """O. Invariant: Reconciliation output NEVER contains operational verdicts (fit/unfit, safe/unsafe)."""
        payload = {
            "observations": [
                {"entity_tag": "P-201", "property_name": "wall_thickness", "value": 2.1, "unit": "mm", "source_document": "Crit.pdf", "raw_statement": "2.1 mm (Retirement is 3.2 mm)"},
            ]
        }
        resp = client.post("/api/evidence/reconcile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        # Verify prohibited keys
        assert "fit_for_service" not in data
        assert "is_safe" not in data
        assert "statutory_compliance" not in data
        assert "maintenance_action" not in data
        assert "ground_truth" not in data
        assert "consistency_score" not in data
