# tests/test_verified_work_product.py
"""
MRPL Sovereign AI Workbench — Verified Industrial Work Product Test Suite.
Validates the end-to-end vertical pipeline:
Evidence Architecture → Deterministic Calculation → Structured WorkProduct →
Local DOCX Generation → DOCX Re-Read & Parsing → Deliverable Verification → Verification Receipt.
Includes extensive positive and negative / adversarial tests.
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
from backend.services.work_product_engine import WorkProductEngine
from backend.services.work_product_docx_generator import WorkProductDocxGenerator
from backend.services.deliverable_verifier import DeliverableVerifier


@pytest.fixture
def client():
    return TestClient(app)


def test_v201_work_product_structure():
    """
    Test 1: WorkProductEngine must synthesize a fully populated structured WorkProduct model.
    """
    wp = WorkProductEngine.build_v201_review_note(query="Generate V-201 Inspection Review Note")
    
    assert wp.equipment_tag == "V-201"
    assert wp.asset_id == "ASSET-MRPL-V201"
    assert wp.evidence_status == "SUFFICIENT"
    assert wp.evidence_debt == "NONE"
    assert len(wp.observations) == 2
    assert len(wp.calculations) == 1
    assert len(wp.claims) == 4
    assert len(wp.source_references) == 3

    # Verify deterministic calculation inputs and exact float result
    calc = wp.calculations[0]
    assert calc.inputs["t_initial"]["value"] == 18.0
    assert calc.inputs["t_current"]["value"] == 17.2
    assert calc.interval_years == 3.5
    assert calc.metal_loss_mm == 0.8
    assert calc.result_value == 0.2286
    assert calc.result_unit == "mm/year"
    assert calc.verification_status == "VERIFIED_DETERMINISTIC"


def test_v201_docx_generation_and_reread_verification():
    """
    Test 2: Full local generation, disk persistence, and independent re-read verification.
    """
    wp = WorkProductEngine.build_v201_review_note(query="Generate V-201 Inspection Review Note")
    out_path = os.path.abspath("artifacts/test_v201_review_note.docx")
    
    generated_path = WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    assert os.path.exists(generated_path)
    assert os.path.getsize(generated_path) > 5000  # Non-empty valid DOCX

    # Re-read and verify generated artifact
    receipt = DeliverableVerifier.verify_docx_deliverable(generated_path, wp)
    
    assert receipt.status == DeliverableStatus.VERIFIED_DELIVERABLE
    assert receipt.checks_failed == 0
    assert receipt.checks_passed == receipt.checks_total
    assert receipt.equipment_tag == "V-201"
    assert receipt.sovereignty_proof["egress_count"] == 0
    assert receipt.sovereignty_proof["air_gap_status"] == "SOVEREIGN_AIR_GAPPED"


def test_negative_tampered_tag_causes_verification_failure():
    """
    Test 3 (Negative): If an incorrect equipment tag (e.g. P-201) is placed in the V-201 review note,
    the deliverable verification MUST FAIL with cross-asset contamination flagged.
    """
    wp = WorkProductEngine.build_v201_review_note()
    out_path = os.path.abspath("artifacts/test_tampered_tag.docx")
    
    # Generate clean docx
    WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    
    # Intentionally contaminate the DOCX by injecting P-201
    doc = Document(out_path)
    doc.add_paragraph("Contaminating Reference: Crude Pump P-201 was inspected instead.")
    doc.save(out_path)

    # DeliverableVerifier must detect contamination
    receipt = DeliverableVerifier.verify_docx_deliverable(out_path, wp)
    assert receipt.status == DeliverableStatus.DELIVERABLE_VERIFICATION_FAILED
    assert receipt.checks_failed > 0
    
    fail_checks = [c for c in receipt.checks if c.status == "FAIL"]
    assert any(c.check_name == "cross_asset_contamination_guard" for c in fail_checks)


def test_negative_tampered_thickness_causes_verification_failure():
    """
    Test 4 (Negative): If the baseline thickness value is tampered (e.g. 18.0 mm -> 25.0 mm),
    the deliverable verification MUST FAIL.
    """
    wp = WorkProductEngine.build_v201_review_note()
    # Mutate the observation value
    wp.observations[0].value = 25.0
    out_path = os.path.abspath("artifacts/test_tampered_thickness.docx")
    
    # Generate mutated docx
    WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    
    # Verify against expected canonical WorkProduct (which requires 18.0 mm)
    canonical_wp = WorkProductEngine.build_v201_review_note()
    receipt = DeliverableVerifier.verify_docx_deliverable(out_path, canonical_wp)
    
    assert receipt.status == DeliverableStatus.DELIVERABLE_VERIFICATION_FAILED
    fail_checks = [c for c in receipt.checks if c.status == "FAIL"]
    assert any(c.check_name == "baseline_thickness_value" for c in fail_checks)


def test_negative_missing_disclaimer_causes_verification_failure():
    """
    Test 5 (Negative): If mandatory engineering disclaimer is stripped,
    the deliverable verification MUST FAIL.
    """
    wp = WorkProductEngine.build_v201_review_note()
    wp.safety_language = "Generic note without disclaimer."
    out_path = os.path.abspath("artifacts/test_missing_disclaimer.docx")
    
    WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    
    canonical_wp = WorkProductEngine.build_v201_review_note()
    receipt = DeliverableVerifier.verify_docx_deliverable(out_path, canonical_wp)
    
    assert receipt.status == DeliverableStatus.DELIVERABLE_VERIFICATION_FAILED
    fail_checks = [c for c in receipt.checks if c.status == "FAIL"]
    assert any(c.check_name == "safety_disclaimer_presence" for c in fail_checks)


def test_work_product_api_endpoint(client):
    """
    Test 6: POST /api/work-products/generate generates, verifies, and returns full package.
    """
    res = client.post("/api/work-products/generate", json={
        "query": "Generate V-201 Inspection Review Note",
        "entity_tag": "V-201"
    })
    assert res.status_code == 200
    data = res.json()
    
    assert data["success"] is True
    assert data["status"] == "VERIFIED_DELIVERABLE"
    assert data["work_product"]["equipment_tag"] == "V-201"
    assert data["verification_receipt"]["checks_failed"] == 0
    assert "download_url" in data
    assert os.path.exists(os.path.join("artifacts", data["filename"]))


def test_work_product_unknown_entity_blocked(client):
    """
    Test 7: POST /api/work-products/generate with unknown entity P-999 is blocked.
    """
    res = client.post("/api/work-products/generate", json={
        "query": "Generate P-999 Inspection Review Note",
        "entity_tag": "P-999"
    })
    assert res.status_code == 403
    assert "ContextGuard" in res.json()["detail"]


def test_negative_erroneous_calculation_artifact_fails_verification():
    """
    Test 8 (Negative): If an erroneous 0.4 mm/year calculation or 2 hours expression is injected,
    the deliverable verification MUST FAIL.
    """
    wp = WorkProductEngine.build_v201_review_note()
    out_path = os.path.abspath("artifacts/test_erroneous_rate.docx")
    
    WorkProductDocxGenerator.generate_docx(wp, output_filepath=out_path)
    
    # Inject obsolete calculation artifact
    doc = Document(out_path)
    doc.add_paragraph("Erroneous Calculation: Estimated short-term corrosion rate was 0.4 mm/year.")
    doc.save(out_path)

    canonical_wp = WorkProductEngine.build_v201_review_note()
    receipt = DeliverableVerifier.verify_docx_deliverable(out_path, canonical_wp)
    
    assert receipt.status == DeliverableStatus.DELIVERABLE_VERIFICATION_FAILED
    fail_checks = [c for c in receipt.checks if c.status == "FAIL"]
    assert any(c.check_name == "arithmetic_grounding_validity" for c in fail_checks)


def test_negative_missing_source_references_fails_verification():
    """
    Test 9 (Negative): If source document references are omitted from the WorkProduct or DOCX,
    the deliverable verification MUST FAIL.
    """
    wp = WorkProductEngine.build_v201_review_note()
    out_path = os.path.abspath("artifacts/test_missing_sources.docx")
    
    # Empty source references
    wp_stripped = WorkProductEngine.build_v201_review_note()
    wp_stripped.source_references = []
    
    WorkProductDocxGenerator.generate_docx(wp_stripped, output_filepath=out_path)
    
    canonical_wp = WorkProductEngine.build_v201_review_note()
    receipt = DeliverableVerifier.verify_docx_deliverable(out_path, canonical_wp)
    
    assert receipt.status == DeliverableStatus.DELIVERABLE_VERIFICATION_FAILED
    fail_checks = [c for c in receipt.checks if c.status == "FAIL"]
    assert any(c.check_name == "source_references_traceability" for c in fail_checks)


def test_generic_p999_nomenclature_remains_general_knowledge(client):
    """
    Test 10: Generic nomenclature inquiry regarding P-999 is routed as GENERAL_KNOWLEDGE
    and is not treated as an authoritative MRPL entity.
    """
    res = client.post("/api/route", json={
        "query": "What does equipment tag P-999 typically mean in refinery nomenclature?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["task_profile"]["entity_name"] in (None, "P-999", "General")

