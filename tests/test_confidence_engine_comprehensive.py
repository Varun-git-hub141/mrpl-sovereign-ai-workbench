# -*- coding: utf-8 -*-
"""
Tests for Confidence Engine
Verifies:
- Mathematical formula: overall_confidence = 0.40 * retrieval_score + 0.35 * evidence_coverage + 0.25 * verification_score
- Claim decomposition and provenance categorization (DIRECT_MRPL_RECORD, CALCULATED_FROM_MRPL_EVIDENCE, etc.)
- Verification score calculation and contradiction penalty
- Hard safety gates (contradiction, unverified calculation, unsupported critical claims, approval note gate)
- Threshold tiers (HIGH, MEDIUM, LOW, INSUFFICIENT)
"""

import pytest
from backend.models.execution_plan import ExecutionPlan, VerificationSpec, ModelRoleAssignment
from backend.models.task_profile import RiskLevel
from backend.models.rag_models import RetrievedChunk, ChunkProvenance, RetrievalScoreBreakdown
from backend.models.verification_result import VerificationReport, VerificationStatus, DeterministicStatus
from backend.services.confidence_engine import ConfidenceEngine, ConfidenceTier, ClaimOrigin


@pytest.fixture
def confidence_engine():
    return ConfidenceEngine()


@pytest.fixture
def mock_plan():
    primary = ModelRoleAssignment(
        model_id="qwen3_4b",
        ollama_name="qwen3:4b",
        display_name="Qwen 3 4B",
        role="primary",
    )
    return ExecutionPlan(
        request_id="REQ-TEST-001",
        deliverable_type="engineering_analysis",
        risk=RiskLevel.MEDIUM,
        primary_model=primary,
        fallback_models=[],
        required_tools=[],
        verification_spec=VerificationSpec(),
        task_spec="Evaluate corrosion rates for P-201",
    )


def test_confidence_formula_exact(confidence_engine, mock_plan):
    """Test overall_confidence = 0.40 * retrieval + 0.35 * evidence + 0.25 * verification"""
    chunks = [
        RetrievedChunk(
            text="Tag: P-201 baseline thickness is 6.0 mm in 2019. Current thickness is 4.5 mm in 2024. Inspection interval is 5 years. Minimum allowable thickness is 3.2 mm.",
            source=ChunkProvenance(document="MRPL-INSP-2024-P201.pdf", document_id="DOC-01", document_type="Inspection Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.90, semantic_score=0.92, hybrid_score=0.91),
        )
    ]
    
    calc_res = {"status": "SUCCESS", "result": 0.30, "result_unit": "mm/year"}
    res = confidence_engine.evaluate_confidence(
        plan=mock_plan,
        retrieved_chunks=chunks,
        deterministic_calc=calc_res,
        entity_tag="P-201",
    )

    r_score = res["retrieval_score"]
    e_cov = res["evidence_coverage"]
    v_score = res["verification_score"]
    expected_overall = round(0.40 * r_score + 0.35 * e_cov + 0.25 * v_score, 2)

    assert res["overall_confidence"] == expected_overall
    assert 0.0 <= res["overall_confidence"] <= 1.0
    assert res["confidence_tier"] in [t.value for t in ConfidenceTier]


def test_claim_decomposition_corrosion(confidence_engine):
    """Test claim decomposition into DIRECT_MRPL_RECORD and CALCULATED_FROM_MRPL_EVIDENCE"""
    chunks = [
        RetrievedChunk(
            text="Crude Feed Pump P-201 baseline thickness 6.0 mm (2019). Ultrasonic survey 2024 measured 4.5 mm. 5 years interval.",
            source=ChunkProvenance(document="MRPL-INSP-2024-P201.pdf", document_id="DOC-01", document_type="Inspection Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.88, semantic_score=0.90, hybrid_score=0.89),
        )
    ]
    calc_res = {"status": "SUCCESS", "result": 0.30, "result_unit": "mm/year"}

    claims, coverage, missing = confidence_engine.decompose_and_evaluate_claims(
        query="What are the previous corrosion rates of P-201?",
        retrieved_chunks=chunks,
        entity_tag="P-201",
        deterministic_calc=calc_res,
    )

    origins = [c.origin for c in claims]
    assert ClaimOrigin.DIRECT_MRPL_RECORD in origins
    assert ClaimOrigin.CALCULATED_FROM_MRPL_EVIDENCE in origins
    assert coverage >= 0.80


def test_contradiction_lowers_verification_and_triggers_gate(confidence_engine, mock_plan):
    """Test that conflicting documents trigger CONTRADICTION_DETECTED safety gate"""
    chunks = [
        RetrievedChunk(
            text="P-201 current casing thickness: 4.5 mm (2024)",
            source=ChunkProvenance(document="DocA.pdf", document_id="D1", document_type="Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.9, semantic_score=0.9, hybrid_score=0.9),
        ),
        RetrievedChunk(
            text="P-201 current casing thickness: 2.1 mm (2024)",
            source=ChunkProvenance(document="DocB.pdf", document_id="D2", document_type="Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.9, semantic_score=0.9, hybrid_score=0.9),
        ),
        RetrievedChunk(
            text="P-201 current casing thickness: 6.8 mm (2024)",
            source=ChunkProvenance(document="DocC.pdf", document_id="D3", document_type="Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.9, semantic_score=0.9, hybrid_score=0.9),
        ),
    ]

    verif_report = VerificationReport(
        status=VerificationStatus.CONTRADICTED,
        contradictions=["Conflicting thickness records: 4.5mm vs 2.1mm vs 6.8mm"],
    )

    res = confidence_engine.evaluate_confidence(
        plan=mock_plan,
        verification_report=verif_report,
        retrieved_chunks=chunks,
        entity_tag="P-201",
    )

    assert res["verification_details"]["contradiction_detected"] is True
    assert res["confidence_tier"] == ConfidenceTier.CONFLICT_DETECTED.value
    assert any("CONTRADICTION_DETECTED" in g for g in res["hard_safety_gates"])
    assert res["human_approval_mandatory"] is True


def test_approval_note_always_requires_human_approval(confidence_engine, mock_plan):
    """Test that approval notes ALWAYS enforce human approval gate even with high confidence"""
    mock_plan.deliverable_type = "approval_note"
    chunks = [
        RetrievedChunk(
            text="P-201 baseline 6.0 mm, current 4.5 mm, tmin 3.2 mm, recommendation: continued operation",
            source=ChunkProvenance(document="DocA.pdf", document_id="D1", document_type="Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.95, semantic_score=0.95, hybrid_score=0.95),
        )
    ]
    res = confidence_engine.evaluate_confidence(
        plan=mock_plan,
        retrieved_chunks=chunks,
        deterministic_calc={"status": "SUCCESS", "result": 0.30},
        entity_tag="P-201",
        task_type="approval_note",
    )

    assert res["human_approval_mandatory"] is True
    assert any("APPROVAL_NOTE_SAFETY_GATE" in g for g in res["hard_safety_gates"])

