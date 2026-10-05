import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.models.claim_provenance import (
    ClaimOriginType,
    ClaimStatus,
)
from backend.services.claim_provenance import ClaimProvenanceEngine
from backend.services.hybrid_rag import HybridRAGService
from backend.models.rag_models import HybridSearchRequest


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# TEST 1: "What do we know about P-201?" — Hybrid RAG & Claim-Level Citations
# ==============================================================================
def test_1_p201_claim_level_provenance(client):
    query = "What do we know about P-201?"
    
    # 1. Route Plan
    route_res = client.post("/api/route", json={"query": query})
    assert route_res.status_code == 200
    route_data = route_res.json()
    assert route_data["task_profile"]["entity_resolution_status"] == "FOUND_IN_MRPL_KB"
    assert "ENGINEERING RAG" in route_data["execution_plan"]["required_tools"]
    assert route_data["execution_plan"]["primary_model"]["ollama_name"] != "NONE"

    # 2. Execution
    exec_res = client.post("/api/execute", json={
        "query": query,
        "execution_plan": route_data["execution_plan"],
        "allow_unverified_fallback": False,
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()

    assert exec_data["mrpl_verified"] is True
    assert exec_data["context_mode"] == "MRPL_AUTHORITATIVE"

    # Check RAG Trace & Chunk Attributes (Requirement 1)
    rag_trace = exec_data["rag_trace"]
    assert rag_trace is not None
    assert rag_trace["entity"] == "P-201"
    assert rag_trace["mrpl_entity_resolution"] == "FOUND"
    assert rag_trace["mrpl_kb_status"] == "FOUND"
    assert rag_trace["retrieval_executed"] == "HYBRID RAG EXECUTED"
    assert rag_trace["retrieved_chunks_count"] > 0

    first_chunk = rag_trace["evidence_items"][0]
    assert "document_id" in first_chunk
    assert "filename" in first_chunk or "document" in first_chunk
    assert "document_type" in first_chunk
    assert "page" in first_chunk
    assert "chunk_id" in first_chunk
    assert "source_text" in first_chunk or "text" in first_chunk
    assert "bm25_score" in first_chunk
    assert "vector_score" in first_chunk
    assert "hybrid_score" in first_chunk

    # Check Claim-Level Provenance (Requirement 2 & 3)
    claim_prov = exec_data.get("claim_provenance")
    assert claim_prov is not None
    assert claim_prov["source_coverage"]["mrpl_supported_claims"] >= 1
    assert isinstance(claim_prov["source_coverage"]["unsupported_claims"], int)

    # Check 15-Field Audit Record (Requirement 12)
    audit = exec_data.get("audit_record")
    assert audit is not None
    assert audit["query"] == query
    assert audit["entity"] == "P-201"
    assert audit["entity_resolution_status"] in ["FOUND", "FOUND_IN_MRPL_KB"]
    assert audit["retrieval_mode"] == "HYBRID"
    assert len(audit["retrieved_documents"]) > 0
    assert len(audit["retrieved_chunks"]) > 0
    assert "scores" in audit
    assert audit["llm_invoked"] is True
    assert len(audit["claims"]) > 0
    assert len(audit["claim_sources"]) > 0
    assert "verification_status" in audit
    assert audit["unsupported_claims"] == 0
    assert "timestamp" in audit


# ==============================================================================
# TEST 2: "What is the baseline thickness of P-201?" — Direct Inspection Evidence
# ==============================================================================
def test_2_p201_baseline_thickness_origin(client):
    query = "What is the baseline thickness of P-201?"
    
    route_res = client.post("/api/route", json={"query": query})
    assert route_res.status_code == 200
    route_data = route_res.json()

    exec_res = client.post("/api/execute", json={
        "query": query,
        "execution_plan": route_data["execution_plan"],
        "allow_unverified_fallback": False,
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()

    assert exec_data["mrpl_verified"] is True
    claim_prov = exec_data["claim_provenance"]
    assert len(claim_prov["claims"]) > 0

    # Numerical origins must trace 6.0 mm to MRPL inspection report
    num_origins = claim_prov.get("numerical_origins", [])
    has_6mm = any("6.0" in n["value"] and "inspection" in n["origin"].lower() for n in num_origins)
    assert has_6mm, f"6.0 mm origin not found in numerical origins: {num_origins}"


# ==============================================================================
# TEST 3: "What is the corrosion rate of P-201?" — Deterministic Math Trace
# ==============================================================================
def test_3_p201_corrosion_rate_deterministic_trace(client):
    query = "What is the corrosion rate of P-201?"
    
    route_res = client.post("/api/route", json={"query": query})
    assert route_res.status_code == 200
    route_data = route_res.json()

    exec_res = client.post("/api/execute", json={
        "query": query,
        "execution_plan": route_data["execution_plan"],
        "allow_unverified_fallback": False,
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()

    claim_prov = exec_data["claim_provenance"]
    assert claim_prov is not None

    # Check deterministic calculation in numerical origins
    num_origins = claim_prov.get("numerical_origins", [])
    has_corr_rate = any("0.30" in n["value"] and n["is_calculated"] for n in num_origins)
    assert has_corr_rate, f"0.30 mm/year calculation not found in: {num_origins}"

    # Check claims status contains CALCULATED BY DETERMINISTIC ENGINE or SUPPORTED BY MRPL KB
    calc_claims = [c for c in claim_prov["claims"] if c["status"] == ClaimStatus.CALCULATED_BY_DETERMINISTIC.value]
    assert len(calc_claims) >= 1 or claim_prov["source_coverage"]["calculated_claims"] >= 1


# ==============================================================================
# TEST 4: "What do we know about P-999?" — Context Guard Refusal (No LLM)
# ==============================================================================
def test_4_p999_context_guard_no_llm(client):
    query = "What do we know about P-999?"
    
    route_res = client.post("/api/route", json={"query": query})
    assert route_res.status_code == 200
    route_data = route_res.json()

    assert route_data["task_profile"]["entity_resolution_status"] == "NOT_FOUND_IN_KB"
    assert route_data["execution_plan"]["primary_model"]["ollama_name"] == "NONE"

    exec_res = client.post("/api/execute", json={
        "query": query,
        "execution_plan": route_data["execution_plan"],
        "allow_unverified_fallback": False,
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()

    assert exec_data["deliverable_type"] == "guarded_entity_resolution_refusal"
    assert exec_data["model_actually_executed"] == "MRPL_CONTEXT_GUARD"
    assert exec_data["routed_model"] == "NONE"
    assert exec_data["allow_general_fallback_available"] is True
    assert "NOT FOUND" in exec_data["primary_execution"]["response"]
    assert "P-999" in exec_data["primary_execution"]["response"]

    # Audit record check for refusal
    audit = exec_data.get("audit_record")
    assert audit is not None
    assert audit["llm_invoked"] is False
    assert audit["llm_model"] == "NONE"
    assert audit["entity_resolution_status"] in ["NOT_FOUND", "NOT_FOUND_IN_KB"]


# ==============================================================================
# TEST 5: "What does P-999 mean?" — Initial Refusal & Explicit User Fallback
# ==============================================================================
def test_5_p999_explicit_user_fallback(client):
    query = "What does P-999 mean?"
    
    # 1. Initial attempt without fallback
    res_initial = client.post("/api/route", json={"query": query})
    assert res_initial.status_code == 200
    r_init = res_initial.json()

    exec_init = client.post("/api/execute", json={
        "query": query,
        "execution_plan": r_init["execution_plan"],
        "allow_unverified_fallback": False,
    })
    assert exec_init.status_code == 200
    e_init = exec_init.json()
    assert e_init["deliverable_type"] == "guarded_entity_resolution_refusal"
    assert e_init["allow_general_fallback_available"] is True

    # 2. User explicitly clicks [ Ask General LLM Anyway ]
    exec_fallback = client.post("/api/execute", json={
        "query": query,
        "execution_plan": r_init["execution_plan"],
        "allow_unverified_fallback": True,
    })
    assert exec_fallback.status_code == 200
    e_fb = exec_fallback.json()

    assert e_fb["context_mode"] == "GENERAL_KNOWLEDGE"
    assert e_fb["mrpl_verified"] is False
    assert e_fb["knowledge_source_used"] == "General Model Knowledge"
    assert "UNVERIFIED GENERAL KNOWLEDGE" in e_fb["primary_execution"]["response"] or "GENERAL MODEL RESPONSE" in e_fb["primary_execution"]["response"]
    assert "NOT MRPL-VERIFIED" in e_fb["primary_execution"]["response"] or "NOT MRPL VERIFIED" in e_fb["primary_execution"]["response"]
    assert e_fb["model_actually_executed"] != "MRPL_CONTEXT_GUARD"

    # Claim provenance for general knowledge fallback
    claim_prov = e_fb.get("claim_provenance")
    assert claim_prov is not None
    assert claim_prov["source_coverage"]["general_knowledge_claims"] >= 1
    for cl in claim_prov["claims"]:
        assert cl["status"] == ClaimStatus.GENERAL_MODEL_KNOWLEDGE.value
