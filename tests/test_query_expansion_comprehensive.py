# -*- coding: utf-8 -*-
"""
Tests for Automatic Query Expansion Engine
Verifies:
- Evidence-driven missing claims detection
- Targeted subquery generation
- Multi-round iterative expansion loop (max 3 rounds)
- Deduplication and chunk merging
- Recalculation of retrieval, evidence coverage, verification, and confidence scores
- Clean stop condition when confidence target is reached
"""

import pytest
from backend.models.execution_plan import ExecutionPlan, VerificationSpec, ModelRoleAssignment
from backend.models.task_profile import RiskLevel
from backend.models.rag_models import RetrievedChunk, ChunkProvenance, RetrievalScoreBreakdown
from backend.services.confidence_engine import ConfidenceEngine
from backend.services.query_expansion import QueryExpansionEngine, QueryExpansionResult


@pytest.fixture
def query_expansion_engine():
    return QueryExpansionEngine()


@pytest.fixture
def mock_plan():
    primary = ModelRoleAssignment(
        model_id="qwen3_4b",
        ollama_name="qwen3:4b",
        display_name="Qwen 3 4B",
        role="primary",
    )
    return ExecutionPlan(
        request_id="REQ-EXP-001",
        deliverable_type="approval_note",
        risk=RiskLevel.HIGH,
        primary_model=primary,
        fallback_models=[],
        required_tools=[],
        verification_spec=VerificationSpec(),
        task_spec="Prepare approval note for P-201",
    )


def test_targeted_subquery_generation(query_expansion_engine):
    """Test that subqueries are generated based on specific missing claims"""
    missing = [
        "Current casing wall thickness for P-201",
        "Minimum allowable retirement thickness (t_min) for P-201",
        "Engineering integrity recommendation and continued operation plan for P-201",
    ]
    subqs = query_expansion_engine.generate_targeted_subqueries(
        query="Prepare approval note for P-201",
        missing_claims=missing,
        entity_tag="P-201",
    )

    assert len(subqs) > 0
    assert any("current casing thickness" in q.lower() or "thickness" in q.lower() for q in subqs)
    assert any("minimum allowable" in q.lower() or "tmin" in q.lower() for q in subqs)
    assert any("recommendation" in q.lower() or "operation" in q.lower() for q in subqs)


def test_expansion_loop_execution_and_progression(query_expansion_engine, mock_plan):
    """Test multi-round expansion loop progressing confidence and merging chunks"""
    initial_chunks = [
        RetrievedChunk(
            text="Tag: P-201 is Crude Feed Booster Pump.",
            source=ChunkProvenance(document="DocA.pdf", document_id="D1", document_type="Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.7, semantic_score=0.7, hybrid_score=0.7),
        )
    ]

    res: QueryExpansionResult = query_expansion_engine.run_expansion_loop(
        plan=mock_plan,
        initial_chunks=initial_chunks,
        query="Prepare approval note for P-201",
        entity_tag="P-201",
        task_type="approval_note",
        target_confidence=0.85,
    )

    assert res.expansion_executed is True
    assert res.rounds_executed >= 1
    assert res.rounds_executed <= 3
    assert len(res.merged_chunks) >= len(initial_chunks)
    assert res.final_confidence >= res.initial_confidence
    assert len(res.rounds) == res.rounds_executed


def test_visible_query_expansion_trace_fields(query_expansion_engine, mock_plan):
    """Test that all visible audit trace fields required by the UI are populated."""
    initial_chunks = [
        RetrievedChunk(
            text="P-201 baseline 2019 inspection.",
            source=ChunkProvenance(document="MRPL-INSP-2019.pdf", document_id="D19", document_type="Report", page=1, equipment_tag="P-201"),
            retrieval=RetrievalScoreBreakdown(keyword_score=0.6, semantic_score=0.6, hybrid_score=0.6),
        )
    ]

    res = query_expansion_engine.run_expansion_loop(
        plan=mock_plan,
        initial_chunks=initial_chunks,
        query="What are the previous corrosion rates of P-201?",
        entity_tag="P-201",
        task_type="corrosion_query",
        target_confidence=0.85,
    )

    assert res.original_query == "What are the previous corrosion rates of P-201?"
    assert res.trigger_reason != ""
    assert res.final_status in ["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
    assert res.stopping_reason != ""
    assert len(res.rounds) > 0

    first_round = res.rounds[0]
    assert first_round.round_number == 1
    assert len(first_round.generated_subqueries) > 0
    assert first_round.overall_confidence > 0.0
    assert isinstance(first_round.retrieved_documents, list)
    assert isinstance(first_round.retrieved_chunks_summary, list)


