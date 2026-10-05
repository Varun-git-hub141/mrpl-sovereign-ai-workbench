# tests/test_pid_work_product_pipeline_suite.py
"""
MRPL Sovereign AI Workbench — Phase 4 Acceptance Test Suite.
Validates the complete end-to-end pipeline:
USER REQUEST
     ↓
ENTITY RESOLUTION
     ↓
P&ID QUERY / GRAPH
     ↓
TOPOLOGY EVIDENCE
     ↓
P&ID EVIDENCE BRIDGE
     ↓
MRPL EVIDENCE CONTRACT
     ↓
LOCAL RAG
     ↓
EVIDENCE SUFFICIENCY
     ↓
EVIDENCE DEBT
     ↓
DETERMINISTIC CALCULATION IF REQUIRED
     ↓
WORK PRODUCT ASSEMBLY
     ↓
LOCAL DOCX GENERATION
     ↓
DISK RE-READ
     ↓
ARTIFACT VERIFICATION
     ↓
VERIFICATION RECEIPT
     ↓
VERIFIED_DELIVERABLE
"""

import os
import pytest
from fastapi.testclient import TestClient
from docx import Document

from backend.app import app
from backend.models.work_product_models import (
    WorkProduct,
    DeliverableStatus,
    DeliverableVerificationReceipt,
    ClaimLineageType,
)
from backend.services.pid.pid_evidence_bridge import PIDEvidenceBridge
from backend.services.work_product_engine import WorkProductEngine
from backend.services.work_product_docx_generator import WorkProductDocxGenerator
from backend.services.deliverable_verifier import DeliverableVerifier


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def bridge():
    return PIDEvidenceBridge()


def test_01_p201_full_pipeline_to_verified_deliverable(bridge):
    """
    Test 1: Full end-to-end pipeline for P-201 isolation review:
    P&ID Query -> Bridge -> WorkProductEngine -> Local DOCX -> Disk Re-Read -> Verification Receipt.
    """
    evidence_resp = bridge.process_query(
        question="Which valves isolate P-201?",
        target_equipment="P-201"
    )
    assert evidence_resp.target_entity == "P-201"
    assert len(evidence_resp.topology.direct_nodes_involved) > 0

    # 1. Work Product Assembly
    wp = WorkProductEngine.build_pid_work_product(
        evidence_response=evidence_resp,
        query="Which valves isolate P-201?"
    )
    assert wp.equipment_tag == "P-201"
    assert wp.asset_id == "ASSET-MRPL-P201"
    assert wp.work_product_type == "PID_ISOLATION_REVIEW_NOTE"
    assert len(wp.observations) > 0
    assert len(wp.claims) > 0
    assert len(wp.source_references) > 0

    # 2. Local DOCX Generation
    out_path = os.path.abspath("artifacts/test_p201_isolation_review_note.docx")
    docx_path = WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    assert os.path.exists(docx_path)
    assert os.path.getsize(docx_path) > 5000

    # 3. Disk Re-Read & Artifact Verification
    receipt = DeliverableVerifier.verify_docx_deliverable(docx_path, wp)
    assert receipt.status == DeliverableStatus.VERIFIED_DELIVERABLE
    assert receipt.checks_failed == 0
    assert receipt.checks_passed >= 6
    assert receipt.equipment_tag == "P-201"
    assert receipt.sovereignty_proof["egress_count"] == 0
    assert receipt.sovereignty_proof["air_gap_status"] == "SOVEREIGN_AIR_GAPPED"


def test_02_p101_downstream_work_product_pipeline(bridge):
    """
    Test 2: Full pipeline for P-101 Atmospheric Residue Pump.
    """
    evidence_resp = bridge.process_query(
        question="What is downstream of P-101?",
        target_equipment="P-101"
    )
    assert evidence_resp.target_entity == "P-101"

    wp = WorkProductEngine.build_pid_work_product(
        evidence_response=evidence_resp,
        query="What is downstream of P-101?"
    )
    assert wp.equipment_tag == "P-101"
    assert wp.asset_id == "ASSET-MRPL-P101"

    out_path = os.path.abspath("artifacts/test_p101_downstream_review_note.docx")
    docx_path = WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    assert os.path.exists(docx_path)

    receipt = DeliverableVerifier.verify_docx_deliverable(docx_path, wp)
    assert receipt.status == DeliverableStatus.VERIFIED_DELIVERABLE
    assert receipt.checks_failed == 0
    assert receipt.equipment_tag == "P-101"


def test_03_disambiguated_tk201_work_product_pipeline(bridge):
    """
    Test 3: Multi-drawing P-201 specified in Tank Farm (PID_TK201).
    """
    evidence_resp = bridge.process_query(
        question="What is upstream of P-201 in PID_TK201?",
        drawing_id="PID_TK201",
        target_equipment="P-201"
    )
    assert evidence_resp.selected_drawing == "MRPL-PID-TK201"

    wp = WorkProductEngine.build_pid_work_product(
        evidence_response=evidence_resp,
        query="What is upstream of P-201 in PID_TK201?"
    )
    out_path = os.path.abspath("artifacts/test_p201_tk201_review_note.docx")
    docx_path = WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    receipt = DeliverableVerifier.verify_docx_deliverable(docx_path, wp)

    assert receipt.status == DeliverableStatus.VERIFIED_DELIVERABLE
    assert receipt.checks_failed == 0


def test_04_api_endpoint_generate_p201_work_product(client):
    """
    Test 4: POST /api/work-products/generate generates and returns verified P-201 deliverable.
    """
    resp = client.post(
        "/api/work-products/generate",
        json={
            "entity_tag": "P-201",
            "query": "Generate P-201 Isolation Review Note",
            "drawing_id": "PID_CDU_200",
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "VERIFIED_DELIVERABLE"
    assert "download_url" in data
    assert "filename" in data
    assert data["work_product"]["equipment_tag"] == "P-201"
    assert data["verification_receipt"]["checks_failed"] == 0


def test_05_api_endpoint_v201_regression(client):
    """
    Test 5: POST /api/work-products/generate regression test for V-201 benchmark review note.
    """
    resp = client.post(
        "/api/work-products/generate",
        json={
            "entity_tag": "V-201",
            "query": "Generate V-201 Inspection Review Note",
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "VERIFIED_DELIVERABLE"
    assert data["work_product"]["equipment_tag"] == "V-201"
    assert data["work_product"]["calculations"][0]["result_value"] == 0.2286


def test_06_context_guard_blocks_unknown_entity(client):
    """
    Test 6: Unknown entities like P-999 or XYZ-999 are blocked by Context Guard with 403.
    """
    resp = client.post(
        "/api/work-products/generate",
        json={
            "entity_tag": "P-999",
            "query": "Generate isolation review for P-999",
        }
    )
    assert resp.status_code == 403
    assert "ContextGuard" in resp.json()["detail"]


def test_07_tampered_pid_docx_fails_verification(bridge):
    """
    Test 7 (Negative): Tampering with generated P&ID deliverable triggers verification failure.
    """
    evidence_resp = bridge.process_query(
        question="Which valves isolate P-201?",
        target_equipment="P-201"
    )
    wp = WorkProductEngine.build_pid_work_product(evidence_resp)
    out_path = os.path.abspath("artifacts/test_tampered_pid_note.docx")
    WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)

    # Intentionally contaminate by adding bad interval / arithmetic hallucination
    doc = Document(out_path)
    doc.add_paragraph("Corrosion was measured over 2 hours at 0.4 mm/year.")
    doc.save(out_path)

    # Verifier must detect arithmetic hallucination / contamination
    receipt = DeliverableVerifier.verify_docx_deliverable(out_path, wp)
    assert receipt.status == DeliverableStatus.DELIVERABLE_VERIFICATION_FAILED
    assert receipt.checks_failed > 0


def test_08_sovereignty_zero_egress(client):
    """
    Test 8: Ensure all work product generation and verification occurs with 0 network egress.
    """
    resp = client.post(
        "/api/work-products/generate",
        json={
            "entity_tag": "P-201",
            "query": "P-201 Sovereign Deliverable Verification",
        }
    )
    assert resp.status_code == 200
    rcpt = resp.json()["verification_receipt"]
    assert rcpt["sovereignty_proof"]["egress_count"] == 0
    assert rcpt["sovereignty_proof"]["air_gap_status"] == "SOVEREIGN_AIR_GAPPED"
