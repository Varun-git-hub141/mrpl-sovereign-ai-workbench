# tests/test_integrity_investigation_workflow.py
"""
Phase 9 Automated Verification Suite — Industrial Integrity Investigation Workflow.
Tests the full 8-stage integrity investigation lifecycle:
Source Evidence -> Observation Extraction -> Provenance -> Sufficiency ->
Reconciliation -> Decision Gates -> Human Review -> Complete Audit Trace.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.integrity.investigation_service import IntegrityInvestigationService
from backend.services.integrity.case_models import (
    InvestigationWorkflowStage,
    CreateCaseRequest,
    AddEvidenceRequest,
    CaseDispositionRequest,
)
from backend.services.decision.decision_models import DecisionRiskLevel, GovernanceOutcome
from backend.services.decision.decision_hitl import HumanApprovalState
from backend.services.evidence.evidence_models import SufficiencyStatus


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def service():
    return IntegrityInvestigationService()


# ─────────────────────────────────────────────────────────────
# 1. Case Workspace Creation & Management (Phase 9A)
# ─────────────────────────────────────────────────────────────

def test_1_create_integrity_case(client):
    """Test 1: Create an industrial integrity investigation case workspace."""
    payload = {
        "entity_tag": "E-801",
        "case_title": "E-801 Shell Thinning Investigation",
        "description": "Turnaround inspection survey review",
        "risk_level": "LOW",
    }
    resp = client.post("/api/integrity/cases", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"].startswith("CASE-")
    assert data["entity_tag"] == "E-801"
    assert data["workflow_stage"] == "EVIDENCE_RECEIVED"
    assert data["risk_level"] == "LOW"


def test_2_add_evidence_documents(client):
    """Test 2: Add industrial evidence documents to a case."""
    create_resp = client.post("/api/integrity/cases", json={
        "entity_tag": "E-801",
        "case_title": "E-801 Document Test",
    })
    case_id = create_resp.json()["case_id"]

    ev_payload = {
        "document_id": "DOC-E801-2019",
        "filename": "E801_UT_2019.json",
        "document_type": "INSPECTION_REPORT",
        "revision": "Rev 0",
        "approval_status": "APPROVED",
        "authority_tier": "APPROVED_AUTHORITATIVE",
        "raw_content": {
            "equipment_tag": "E-801",
            "property_name": "shell_thickness_mm",
            "value": 12.4,
            "unit": "mm",
            "observation_date": "2019-04-10",
            "source_statement": "Base scan: 12.4 mm",
        },
    }
    resp = client.post(f"/api/integrity/cases/{case_id}/evidence", json=ev_payload)
    assert resp.status_code == 200
    case_data = resp.json()
    assert len(case_data["evidence_documents"]) == 1
    assert case_data["evidence_documents"][0]["filename"] == "E801_UT_2019.json"


# ─────────────────────────────────────────────────────────────
# 2. Discrete Observation Extraction & Provenance (Phase 9B & 9C)
# ─────────────────────────────────────────────────────────────

def test_3_extract_observations_and_provenance(client):
    """Test 3 & 4: Extract discrete observations and preserve complete provenance."""
    create_resp = client.post("/api/integrity/cases", json={
        "entity_tag": "E-801",
        "case_title": "Extraction Test",
        "initial_documents": [
            {
                "document_id": "DOC-1",
                "filename": "doc1.json",
                "raw_content": {
                    "equipment_tag": "E-801",
                    "property_name": "shell_thickness_mm",
                    "value": 12.4,
                    "unit": "mm",
                    "observation_date": "2019-04-10",
                    "source_statement": "Base scan: 12.4 mm",
                }
            },
            {
                "document_id": "DOC-2",
                "filename": "doc2.json",
                "raw_content": {
                    "equipment_tag": "E-801",
                    "property_name": "shell_thickness_mm",
                    "value": 11.8,
                    "unit": "mm",
                    "observation_date": "2022-04-15",
                    "source_statement": "Intermediate scan: 11.8 mm",
                }
            }
        ]
    })
    case_id = create_resp.json()["case_id"]

    extract_resp = client.post(f"/api/integrity/cases/{case_id}/extract")
    assert extract_resp.status_code == 200
    data = extract_resp.json()
    assert data["total_extracted"] == 2
    assert data["workflow_stage"] == "OBSERVATIONS_EXTRACTED"

    # Verify provenance on observations
    obs_list = data["observations"]
    assert obs_list[0]["value"] == 12.4
    assert obs_list[0]["source_document"] == "doc1.json"
    assert obs_list[1]["value"] == 11.8
    assert obs_list[1]["source_document"] == "doc2.json"


def test_5_multiple_observations_preserved_without_merging(client):
    """Test 5: Verify multiple observations are NOT averaged, overwritten, or merged."""
    create_resp = client.post("/api/integrity/cases", json={
        "entity_tag": "COL-301",
        "case_title": "Spatial Nozzles Test",
        "initial_documents": [
            {
                "document_id": "DOC-N",
                "filename": "north.json",
                "raw_content": {
                    "equipment_tag": "COL-301",
                    "property_name": "nozzle_thickness_mm",
                    "value": 14.0,
                    "unit": "mm",
                    "source_statement": "North nozzle: 14.0 mm",
                }
            },
            {
                "document_id": "DOC-S",
                "filename": "south.json",
                "raw_content": {
                    "equipment_tag": "COL-301",
                    "property_name": "nozzle_thickness_mm",
                    "value": 11.5,
                    "unit": "mm",
                    "source_statement": "South nozzle: 11.5 mm",
                }
            }
        ]
    })
    case_id = create_resp.json()["case_id"]
    client.post(f"/api/integrity/cases/{case_id}/extract")

    obs_resp = client.get(f"/api/integrity/cases/{case_id}/observations")
    assert obs_resp.status_code == 200
    obs_data = obs_resp.json()
    assert obs_data["total_observations"] == 2
    values = [o["value"] for o in obs_data["observations"]]
    assert 14.0 in values
    assert 11.5 in values
    # Must NOT contain averaged 12.75
    assert 12.75 not in values


# ─────────────────────────────────────────────────────────────
# 3. Evidence Sufficiency & Reconciliation (Phase 9D & 9E)
# ─────────────────────────────────────────────────────────────

def test_6_sufficiency_result_exposed(client):
    """Test 6: Evaluate and expose Phase 2 Evidence Sufficiency."""
    demo_resp = client.post("/api/integrity/demonstration", json={"scenario": "E-801"})
    case_id = demo_resp.json()["case"]["case_id"]

    resp = client.post(f"/api/integrity/cases/{case_id}/assess")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evidence_assessment"] is not None
    assert data["evidence_assessment"]["overall_status"] == "SUFFICIENT"


def test_7_reconciliation_result_exposed(client):
    """Test 7: Reconcile observations through Phase 3 Reconciliation Engine."""
    demo_resp = client.post("/api/integrity/demonstration", json={"scenario": "E-801"})
    case_id = demo_resp.json()["case"]["case_id"]

    resp = client.post(f"/api/integrity/cases/{case_id}/reconcile")
    assert resp.status_code == 200
    data = resp.json()
    rec = data["reconciliation_result"]
    assert rec is not None
    assert rec["consistency_state"] in ["CONSISTENT", "TEMPORALLY_EXPLAINED"]
    assert len(rec["relationships"]) >= 1


def test_8_conflict_visibility(client):
    """Test 8: Verify active contradictions are captured and remain visible in reconciliation."""
    create_resp = client.post("/api/integrity/cases", json={
        "entity_tag": "XV-501",
        "case_title": "Conflict Visibility Test",
        "initial_documents": [
            {
                "document_id": "DOC-A",
                "filename": "ds.json",
                "raw_content": {
                    "equipment_tag": "XV-501",
                    "property_name": "fail_action",
                    "value": "FAIL_OPEN",
                    "observation_date": "2024-01-01",
                    "source_statement": "Action: FAIL_OPEN",
                }
            },
            {
                "document_id": "DOC-B",
                "filename": "cal.json",
                "raw_content": {
                    "equipment_tag": "XV-501",
                    "property_name": "fail_action",
                    "value": "FAIL_CLOSE",
                    "observation_date": "2024-01-01",
                    "source_statement": "Action: FAIL_CLOSE",
                }
            }
        ]
    })
    case_id = create_resp.json()["case_id"]
    client.post(f"/api/integrity/cases/{case_id}/extract")
    rec_resp = client.post(f"/api/integrity/cases/{case_id}/reconcile")
    data = rec_resp.json()
    rec = data["reconciliation_result"]
    assert rec["consistency_state"] == "CONFLICTING"
    assert rec["reconciliation_status"] == "UNRESOLVED_CONFLICT"
    assert len(rec["active_conflicts"]) == 1


# ─────────────────────────────────────────────────────────────
# 4. Decision Evaluation & Human Review (Phase 9F & 9G)
# ─────────────────────────────────────────────────────────────

def test_9_decision_engine_integration(client):
    """Test 9: Evaluate decision package through DecisionEngine."""
    demo_resp = client.post("/api/integrity/demonstration", json={"scenario": "E-801"})
    case_id = demo_resp.json()["case"]["case_id"]

    eval_resp = client.post(f"/api/integrity/cases/{case_id}/evaluate")
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert data["governance_outcome"] == "PROCEED_ADVISORY"
    assert data["decision_package"]["audit_trail_hash"] is not None


def test_10_human_approval_package_generation_and_disposition(client):
    """Test 10: Generate HITL approval package and submit human review disposition."""
    demo_resp = client.post("/api/integrity/demonstration", json={"scenario": "PSV-201"})
    case_id = demo_resp.json()["case"]["case_id"]

    # Generate approval package
    pkg_resp = client.post(f"/api/integrity/cases/{case_id}/approval-package")
    assert pkg_resp.status_code == 200
    deliv = pkg_resp.json()["approval_deliverable"]
    assert deliv is not None
    assert deliv["requires_human_approval"] is True
    assert "CHIEF_INSPECTION_ENGINEER" in deliv["required_human_roles"]

    # Submit human disposition
    disp_resp = client.post(f"/api/integrity/cases/{case_id}/disposition", json={
        "action": "APPROVE",
        "reviewer_name": "Senior Statutory Inspector",
        "notes": "Verified against IBR compliance standards.",
    })
    assert disp_resp.status_code == 200
    disp_data = disp_resp.json()
    assert disp_data["human_approval_state"] == "APPROVED"
    assert disp_data["workflow_stage"] == "COMPLETED"


# ─────────────────────────────────────────────────────────────
# 5. End-to-End Audit Trace & Lineage (Phase 9H)
# ─────────────────────────────────────────────────────────────

def test_11_audit_trace_connects_decision_to_source(client):
    """Test 11: Verify 7-tier clickable hierarchical audit tree from Decision to Source Span."""
    demo_resp = client.post("/api/integrity/demonstration", json={"scenario": "E-801"})
    case_id = demo_resp.json()["case"]["case_id"]

    trace_resp = client.get(f"/api/integrity/cases/{case_id}/audit-trace")
    assert trace_resp.status_code == 200
    tree = trace_resp.json()
    assert tree["node_type"] == "FINAL_DECISION"
    assert len(tree["children"]) >= 3  # Decision rules, Reconciliation, Observations

    # Find observation collection and leaf document spans
    child_types = [c["node_type"] for c in tree["children"]]
    assert "DECISION_RULES" in child_types
    assert "RECONCILIATION_RESULT" in child_types
    assert "OBSERVATION_COLLECTION" in child_types

    obs_node = next(c for c in tree["children"] if c["node_type"] == "OBSERVATION_COLLECTION")
    assert len(obs_node["children"]) == 3  # 3 discrete measurements (2019, 2022, 2025)
    leaf_doc = obs_node["children"][0]["children"][0]
    assert leaf_doc["node_type"] == "SOURCE_DOCUMENT_SPAN"
    assert "12.4 mm" in leaf_doc["details"]["verbatim_raw_statement"]


# ─────────────────────────────────────────────────────────────
# 6. Safety Invariants & Missing Metadata (Phase 9L)
# ─────────────────────────────────────────────────────────────

def test_12_missing_metadata_is_not_fabricated(client):
    """Test 12: Missing metadata fields must remain None/UNKNOWN, never synthesized."""
    create_resp = client.post("/api/integrity/cases", json={
        "entity_tag": "P-101",
        "case_title": "Missing Meta Test",
        "initial_documents": [
            {
                "document_id": "DOC-RAW",
                "filename": "raw.json",
                "raw_content": {
                    "equipment_tag": "P-101",
                    "property_name": "vibration_mms",
                    "value": 4.5,
                    # No date, no revision, no unit
                    "source_statement": "Vibration recorded 4.5",
                }
            }
        ]
    })
    case_id = create_resp.json()["case_id"]
    client.post(f"/api/integrity/cases/{case_id}/extract")

    obs_resp = client.get(f"/api/integrity/cases/{case_id}/observations")
    obs = obs_resp.json()["observations"][0]
    assert obs["observation_date"] is None
    assert obs["unit"] is None


def test_13_no_physical_control_endpoints(client):
    """Test 13: Verify absence of any DCS/SCADA/PLC actuation endpoints."""
    # Attempting physical write/actuation should return 404
    resp1 = client.post("/api/control/actuate", json={"valve_id": "XV-501", "action": "CLOSE"})
    assert resp1.status_code == 404

    resp2 = client.post("/api/dcs/write", json={"tag": "PSV-201", "setpoint": 15.0})
    assert resp2.status_code == 404


def test_14_demonstration_scenario_end_to_end(client):
    """Test 14: End-to-end verification of preloaded demonstration scenario."""
    resp = client.post("/api/integrity/demonstration", json={"scenario": "E-801"})
    assert resp.status_code == 200
    case = resp.json()["case"]
    assert case["entity_tag"] == "E-801"
    assert len(case["extracted_observations"]) == 3
    assert case["reconciliation_result"] is not None
    assert case["decision_package"] is not None
    assert case["approval_deliverable"] is not None
    assert case["audit_trail_hash"] is not None
