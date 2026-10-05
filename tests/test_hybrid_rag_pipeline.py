"""
MRPL Sovereign Workbench — Hybrid RAG Knowledge Base & Query Pipeline Tests
Validates all requirements of user specification:
1. Exact equipment search
2. Semantic search
3. BM25 search
4. Hybrid search
5. Metadata filtering
6. Cross-document P-201 retrieval
7. Provenance preservation
8. Missing evidence detection
9. Contradiction conflict detection
10. Deterministic calculation integration
11. No hallucinated values / offline grounding
12. Local / air-gapped sovereign operation
13. Minimum test queries Q1 - Q8
"""

import pytest
from backend.services.hybrid_rag import HybridRAGService, BM25Ranker, DenseSemanticVectorizer
from backend.services.rag_engine import EngineeringRAGEngine
from backend.models.rag_models import (
    HybridSearchRequest,
    RetrievedChunk,
    ChunkProvenance,
    RetrievalScoreBreakdown,
    AuthorityLevel,
)
from schemas.engineering_evidence import EngineeringEvidence, EvidenceValue
from calculator.input_resolver import InputResolver
from backend.services.deterministic_calculator import DeterministicCalculator
from backend.telemetry.audit import NetworkEgressGuard


@pytest.fixture
def hybrid_service():
    return HybridRAGService()


@pytest.fixture
def rag_engine():
    return EngineeringRAGEngine()


# ==============================================================================
# TEST 1: Knowledge Base 57-Document Ingestion & Categorization
# ==============================================================================
def test_1_knowledge_base_57_documents_indexed(hybrid_service):
    stats = hybrid_service.get_stats()
    assert stats["total_documents"] >= 57, f"Expected at least 57 documents, found {stats['total_documents']}"
    assert stats["total_chunks"] >= 57

    expected_categories = [
        "Equipment Master",
        "Equipment History",
        "Inspection Reports",
        "Maintenance Records",
        "P&IDs / Engineering Drawings",
        "SOPs",
        "Engineering Manuals",
        "Previous Engineering Decisions",
        "Technical Datasheets",
    ]
    for cat in expected_categories:
        assert cat in stats["document_categories"], f"Missing category {cat}"


# ==============================================================================
# TEST 2: Exact Equipment Tag Search (P-201, V-201, PSV-201)
# ==============================================================================
def test_2_exact_equipment_search(hybrid_service):
    req = HybridSearchRequest(query="P-201", top_k=5)
    results = hybrid_service.hybrid_search(req)
    assert len(results) > 0
    top_result = results[0]
    assert "P-201" in top_result.text or top_result.source.equipment_tag == "P-201"
    assert top_result.retrieval.keyword_score > 0.0


# ==============================================================================
# TEST 3: Semantic Dense Vector Search
# ==============================================================================
def test_3_semantic_dense_search(hybrid_service):
    vectorizer = hybrid_service.vectorizer
    scores = vectorizer.search("casing wall thickness ultrasonic corrosion degradation")
    assert len(scores) > 0
    top_chunk_id = max(scores, key=scores.get)
    assert scores[top_chunk_id] > 0.0
    # Top semantic result should be related to inspection, history, or thickness
    chunk = hybrid_service.chunks[top_chunk_id]
    assert any(w in chunk["content"].lower() for w in ["thickness", "corrosion", "ultrasonic", "casing", "inspection"])


# ==============================================================================
# TEST 4: BM25 Lexical Keyword Search with Exact Identifiers
# ==============================================================================
def test_4_bm25_lexical_search(hybrid_service):
    # Test work order identifier
    bm25 = hybrid_service.bm25
    scores = bm25.score("WO-9021 mechanical seal overhaul")
    assert len(scores) > 0
    top_chunk_id = max(scores, key=scores.get)
    assert scores[top_chunk_id] > 0.0
    assert "WO-9021" in hybrid_service.chunks[top_chunk_id]["content"]


# ==============================================================================
# TEST 5: Configurable Hybrid Search Ranking
# ==============================================================================
def test_5_hybrid_search_ranking(hybrid_service):
    req = HybridSearchRequest(
        query="P-201 Sulzer centrifugal feed pump",
        semantic_weight=0.50,
        keyword_weight=0.35,
        metadata_weight=0.15,
        top_k=5,
    )
    results = hybrid_service.hybrid_search(req)
    assert len(results) > 0
    for r in results:
        assert 0.0 <= r.retrieval.hybrid_score <= 1.0
        assert r.retrieval.semantic_score >= 0.0
        assert r.retrieval.keyword_score >= 0.0
        assert r.retrieval.metadata_score >= 0.0


# ==============================================================================
# TEST 6: Multi-field Metadata Filtering
# ==============================================================================
def test_6_metadata_filtering(hybrid_service):
    # Query for P-201 restricted strictly to "Maintenance Records"
    req = HybridSearchRequest(
        query="mechanical seal replacement and bearing overhaul",
        equipment_tag="P-201",
        document_type="Maintenance Records",
        top_k=5,
    )
    results = hybrid_service.hybrid_search(req)
    assert len(results) > 0
    for r in results:
        assert r.source.equipment_tag == "P-201"
        assert r.source.document_type == "Maintenance Records"


# ==============================================================================
# TEST 7: Cross-Document P-201 Retrieval (Equipment Dossier)
# ==============================================================================
def test_7_cross_document_p201_retrieval(hybrid_service):
    dossier = hybrid_service.get_equipment_dossier("P-201")
    assert dossier.equipment_tag == "P-201"
    assert dossier.total_documents >= 8, f"Expected multiple records across categories, got {dossier.total_documents}"

    # Verify P-201 appears across categories
    categories = dossier.categories_covered
    assert any("Equipment Master" in c for c in categories)
    assert any("Equipment History" in c for c in categories)
    assert any("Inspection Reports" in c for c in categories)
    assert any("Maintenance Records" in c for c in categories)
    assert any("P&IDs" in c for c in categories)
    assert any("SOPs" in c for c in categories)
    assert any("Decisions" in c for c in categories)
    assert any("Datasheets" in c for c in categories)


# ==============================================================================
# TEST 8: Full Provenance Preservation on Retrieved Chunks
# ==============================================================================
def test_8_provenance_preservation(hybrid_service):
    req = HybridSearchRequest(query="P-201 ultrasonic survey 2024", top_k=3)
    results = hybrid_service.hybrid_search(req)
    assert len(results) > 0
    chunk = results[0]

    # Verify all mandatory provenance attributes
    assert chunk.source.document.endswith(".json")
    assert chunk.source.document_id is not None
    assert chunk.source.page >= 1
    assert chunk.source.section is not None
    assert chunk.source.document_type is not None
    assert chunk.retrieval.hybrid_score > 0.0
    assert chunk.retrieval.retrieval_method in ["hybrid", "equipment_link"]


# ==============================================================================
# TEST 9: Missing Evidence Detection
# ==============================================================================
def test_9_missing_evidence_detection(hybrid_service):
    # Dummy chunk with missing baseline and interval
    dummy_prov = ChunkProvenance(
        document="dummy.json",
        document_id="DUMMY-01",
        document_type="Inspection Reports",
        page=1,
        section="General",
        equipment_tag="P-999",
    )
    dummy_chunk = RetrievedChunk(
        text="Pump P-999 is located in Area 5. No thickness data available.",
        source=dummy_prov,
        retrieval=RetrievalScoreBreakdown(),
        authority_level=AuthorityLevel.B,
        confidence=0.9,
    )
    report = hybrid_service.detect_contradictions([dummy_chunk], equipment_tag="P-999")
    assert len(report.missing_evidence) > 0
    assert "Baseline / Initial Wall Thickness" in report.missing_evidence
    assert "Current Measured Wall Thickness" in report.missing_evidence


# ==============================================================================
# TEST 10: Contradiction & Conflict Detection (Human Review Gate)
# ==============================================================================
def test_10_contradiction_conflict_detection(hybrid_service):
    # Construct two conflicting inspection records (4.5 mm vs 4.1 mm)
    chunk_a = RetrievedChunk(
        text="Inspection Report 2024: P-201 casing current wall thickness measured at 4.5 mm.",
        source=ChunkProvenance(
            document="INSP_2024_P201.json",
            document_id="INSP-01",
            document_type="Inspection Reports",
            page=1,
            section="UT Survey",
            equipment_tag="P-201",
        ),
        retrieval=RetrievalScoreBreakdown(),
        authority_level=AuthorityLevel.A,
    )
    chunk_b = RetrievedChunk(
        text="Contractor NDT Audit: P-201 casing measured wall thickness at 4.1 mm.",
        source=ChunkProvenance(
            document="AUDIT_NDT_2024.json",
            document_id="AUDIT-02",
            document_type="Inspection Reports",
            page=2,
            section="Audit Section",
            equipment_tag="P-201",
        ),
        retrieval=RetrievalScoreBreakdown(),
        authority_level=AuthorityLevel.A,
    )

    report = hybrid_service.detect_contradictions([chunk_a, chunk_b], equipment_tag="P-201")
    assert report.has_conflict is True
    assert report.status == "CONFLICT_DETECTED"
    assert report.human_review_required is True
    assert report.evidence_a.value == 4.5
    assert report.evidence_b.value == 4.1
    assert "CONFLICT DETECTED" in report.explanation
    assert "REQUIRES HUMAN REVIEW" in report.explanation


# ==============================================================================
# TEST 11: Deterministic Calculation Integration from Retrieved RAG Evidence
# ==============================================================================
def test_11_deterministic_calculation_integration(hybrid_service):
    # Retrieve P-201 facts and calculate corrosion rate using pure-Python calculator
    calc_result = hybrid_service.calculate_from_retrieved_evidence("P-201", formula_id="CR-001")
    assert calc_result["status"] == "SUCCESS"
    assert calc_result["equipment_tag"] == "P-201"
    assert calc_result["result"] == 0.30  # (6.0 - 4.5) / 5.0 = 0.30 mm/year
    assert calc_result["result_unit"] == "mm/year"
    assert calc_result["independent_verification"]["verified"] is True
    assert calc_result["canonical_inputs"]["previous_thickness"]["value"] == 6.0
    assert calc_result["canonical_inputs"]["current_thickness"]["value"] == 4.5
    assert calc_result["canonical_inputs"]["inspection_interval"]["value"] == 5.0


# ==============================================================================
# TEST 12: Sovereign Local Operation (No Cloud Egress)
# ==============================================================================
def test_12_sovereign_local_operation(hybrid_service):
    status = NetworkEgressGuard.get_sovereignty_status()
    assert status["air_gap_active"] is True
    assert status["external_llm_calls"] == 0
    assert status["data_leaves_machine"] is False
    assert status["status"] == "SOVEREIGN_AIR_GAPPED"


# ==============================================================================
# TEST 13: Minimum User Queries (TEST 1 through TEST 8 from Section 10)
# ==============================================================================
def test_user_query_1_what_do_we_know_about_p201(hybrid_service):
    res = hybrid_service.query_pipeline("What do we know about P-201?")
    assert res["detected_equipment"] == "P-201"
    assert len(res["retrieved_evidence"]) >= 3
    assert "P-201" in res["final_answer"]
    assert len(res["sources_and_pages"]) >= 3


def test_user_query_2_previous_wall_thickness(hybrid_service):
    res = hybrid_service.query_pipeline("What was the previous wall thickness of P-201?")
    assert res["detected_equipment"] == "P-201"
    assert len(res["retrieved_evidence"]) > 0
    combined_evidence = " ".join([c["text"] for c in res["retrieved_evidence"]])
    assert "6.0 mm" in combined_evidence or "6.0" in combined_evidence


def test_user_query_3_maintenance_performed(hybrid_service):
    res = hybrid_service.query_pipeline("What maintenance was performed on P-201?")
    assert res["detected_equipment"] == "P-201"
    combined_evidence = " ".join([c["text"] for c in res["retrieved_evidence"]])
    assert any(k in combined_evidence.lower() for k in ["seal", "bearing", "overhaul", "wo-9021", "wo-9045"])


def test_user_query_4_relevant_sops(hybrid_service):
    res = hybrid_service.query_pipeline("What SOPs are relevant to P-201?")
    assert res["detected_equipment"] == "P-201"
    combined_evidence = " ".join([c["text"] for c in res["retrieved_evidence"]])
    assert "SOP" in combined_evidence or "startup" in combined_evidence.lower()


def test_user_query_5_previous_engineering_decisions(hybrid_service):
    res = hybrid_service.query_pipeline("What previous engineering decisions exist for P-201?")
    assert res["detected_equipment"] == "P-201"
    combined_evidence = " ".join([c["text"] for c in res["retrieved_evidence"]])
    assert "MOC" in combined_evidence or "decision" in combined_evidence.lower() or "impeller" in combined_evidence.lower()


def test_user_query_6_process_relationship(hybrid_service):
    res = hybrid_service.query_pipeline("What is the process relationship of P-201 with other equipment?")
    assert res["detected_equipment"] == "P-201"
    combined_evidence = " ".join([c["text"] for c in res["retrieved_evidence"]])
    assert any(eq in combined_evidence for eq in ["TK-201", "PSV-201", "XV-203", "E-101", "C-101", "P&ID"])


def test_user_query_7_calculate_corrosion_rate(hybrid_service):
    res = hybrid_service.query_pipeline("Calculate the corrosion rate of P-201.")
    assert res["detected_equipment"] == "P-201"
    assert res["calculation_path"] is not None
    assert res["calculation_path"]["status"] == "SUCCESS"
    assert res["calculation_path"]["result"] == 0.30
    assert "0.30 mm/year" in res["final_answer"] or "0.3" in res["final_answer"]


def test_user_query_8_find_contradictory_information(hybrid_service):
    # Query for contradictory records
    chunk_a = RetrievedChunk(
        text="Inspection Report: P-201 casing thickness measured at 4.5 mm.",
        source=ChunkProvenance(document="INSP_A.json", document_id="I1", document_type="Inspection Reports", page=1, equipment_tag="P-201"),
        retrieval=RetrievalScoreBreakdown(),
    )
    chunk_b = RetrievedChunk(
        text="Alternative Log: P-201 casing thickness measured at 4.1 mm.",
        source=ChunkProvenance(document="INSP_B.json", document_id="I2", document_type="Inspection Reports", page=1, equipment_tag="P-201"),
        retrieval=RetrievalScoreBreakdown(),
    )
    report = hybrid_service.detect_contradictions([chunk_a, chunk_b], equipment_tag="P-201")
    assert report.has_conflict is True
    assert report.status == "CONFLICT_DETECTED"
    assert report.human_review_required is True


# ==============================================================================
# TEST 14: REST API Endpoints (/rag/*)
# ==============================================================================
def test_rag_api_endpoints():
    from fastapi.testclient import TestClient
    from backend.app import app
    client = TestClient(app)

    # 1. GET /rag/status
    res = client.get("/rag/status")
    assert res.status_code == 200
    data = res.json()
    assert data["total_documents"] >= 57

    # 2. POST /rag/search with filters
    res = client.post("/rag/search", json={
        "query": "P-201 mechanical seal",
        "top_k": 3,
        "filters": {"equipment_tag": "P-201"}
    })
    assert res.status_code == 200
    search_data = res.json()
    assert len(search_data["results"]) > 0
    assert search_data["retrieval_mode"] == "hybrid"

    # 3. POST /rag/debug-query
    res = client.post("/rag/debug-query", json={
        "query": "Tell me everything relevant about P-201.",
        "top_k": 4
    })
    assert res.status_code == 200
    dbg = res.json()
    assert dbg["detected_equipment"] == "P-201"
    assert "bm25_top_scores" in dbg
    assert "semantic_top_scores" in dbg
    assert "hybrid_ranking" in dbg
    assert "final_context_sent_to_llm" in dbg

