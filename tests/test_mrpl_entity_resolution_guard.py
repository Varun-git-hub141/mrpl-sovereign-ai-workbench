"""
MRPL Entity Resolution & Context Guard Automated Test Suite
============================================================
Verifies:
1. Automatic MRPL entity discovery and resolution from local knowledge base.
2. Context Guard precedence (Local MRPL knowledge takes absolute precedence).
3. Unknown entity protection (strict refusal without hallucination for P-999).
4. Two-stage routing (Knowledge/Tool Routing BEFORE Model Routing).
5. Grounded prompt synthesis with exact provenance.
6. Deterministic engineering calculation separation.
7. General query bypass for non-MRPL topics (photosynthesis, etc.).
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.entity_resolver import MRPLEntityResolver
from backend.services.context_guard import MRPLContextGuard
from backend.services.task_analyzer import TaskAnalyzer
from backend.services.router import IntelligentModelRouter
from backend.services.execution_planner import ExecutionPlanner
from backend.services.orchestrator import ExecutionOrchestrator
from backend.services.hybrid_rag import HybridRAGService
from backend.models.entity_models import EntityResolutionStatus, EntityType
from backend.models.rag_models import HybridSearchRequest
from backend.models.task_profile import TaskType


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def entity_resolver():
    return MRPLEntityResolver()


@pytest.fixture(scope="module")
def hybrid_rag():
    return HybridRAGService()


@pytest.fixture(scope="module")
def task_analyzer():
    return TaskAnalyzer()


# ==============================================================================
# TEST 1: "What do we know about P-201?"
# ==============================================================================
def test_case_1_what_do_we_know_about_p201(entity_resolver, task_analyzer, hybrid_rag):
    query = "What do we know about P-201?"

    # 1. Entity Resolution
    entity_res = entity_resolver.resolve(query)
    assert entity_res.resolution_status == EntityResolutionStatus.FOUND_IN_MRPL_KB
    assert entity_res.canonical_name == "P-201"
    assert entity_res.entity_type == EntityType.EQUIPMENT
    assert entity_res.is_mrpl_entity is True
    assert entity_res.matched_entity is not None
    assert "EM_P201" in entity_res.matched_entity.source_document

    # 2. Query Analyzer & Tool Routing
    task = task_analyzer.analyze(query)
    assert task.domain == "MRPL ENGINEERING"
    assert task.knowledge_source == "MRPL LOCAL KNOWLEDGE BASE"
    assert "ENGINEERING RAG" in task.required_tools
    assert task.retrieval_mode == "HYBRID"
    assert task.reasoning_stage == "AFTER RETRIEVAL"

    # 3. Hybrid RAG Retrieval
    req = HybridSearchRequest(query=query, equipment_tag="P-201", top_k=5)
    results = hybrid_rag.hybrid_search(req)
    assert len(results) > 0
    top_result = results[0]
    assert top_result.source.equipment_tag == "P-201"

    # 4. Context Guard Directive
    guard = MRPLContextGuard.evaluate(entity_res, query)
    assert guard.knowledge_precedence == "MRPL_AUTHORITATIVE"
    assert guard.should_retrieve_rag is True
    assert guard.unknown_entity_blocked is False

    grounded_prompt = MRPLContextGuard.build_grounded_system_prompt(guard, results)
    assert "MANGALORE REFINERY AND PETROCHEMICALS LIMITED" in grounded_prompt
    assert "P-201" in grounded_prompt
    assert "EM_P201" in grounded_prompt or "Page" in grounded_prompt


# ==============================================================================
# TEST 2: "What was the previous wall thickness of P-201?"
# ==============================================================================
def test_case_2_previous_wall_thickness(entity_resolver, hybrid_rag):
    query = "What was the previous wall thickness of P-201?"
    entity_res = entity_resolver.resolve(query)
    assert entity_res.is_mrpl_entity is True

    req = HybridSearchRequest(query=query, equipment_tag="P-201", top_k=5)
    results = hybrid_rag.hybrid_search(req)
    assert len(results) > 0

    # Ensure baseline / previous thickness of 6.0 mm or 4.5 mm inspection is retrieved with provenance
    found_thickness = False
    for chunk in results:
        if "6.0" in chunk.text or "4.5" in chunk.text or "thickness" in chunk.text.lower():
            found_thickness = True
            assert chunk.source.document is not None
            assert chunk.source.page is not None
    assert found_thickness is True


# ==============================================================================
# TEST 3: "What maintenance was performed on P-201?"
# ==============================================================================
def test_case_3_maintenance_performed(entity_resolver, hybrid_rag):
    query = "What maintenance was performed on P-201?"
    entity_res = entity_resolver.resolve(query)
    assert entity_res.is_mrpl_entity is True

    req = HybridSearchRequest(query=query, equipment_tag="P-201", top_k=5)
    results = hybrid_rag.hybrid_search(req)
    assert len(results) > 0

    # Maintenance records should rank prominently
    maint_found = any("Maintenance" in c.source.document_type or "WO-" in c.text or "overhaul" in c.text.lower() for c in results)
    assert maint_found is True


# ==============================================================================
# TEST 4: "What does the P&ID show about P-201?"
# ==============================================================================
def test_case_4_pid_process_relationship(entity_resolver, hybrid_rag):
    query = "What does the P&ID show about P-201?"
    entity_res = entity_resolver.resolve(query)
    assert entity_res.is_mrpl_entity is True

    req = HybridSearchRequest(query=query, equipment_tag="P-201", top_k=5)
    results = hybrid_rag.hybrid_search(req)
    assert len(results) > 0

    # P&ID records / process relationships
    pid_found = any("P&ID" in c.source.document_type or "drawing" in c.text.lower() or "suction" in c.text.lower() for c in results)
    assert pid_found is True


# ==============================================================================
# TEST 5: "Calculate corrosion rate for P-201."
# ==============================================================================
def test_case_5_deterministic_calculation_separation(entity_resolver, task_analyzer, hybrid_rag):
    query = "Calculate corrosion rate for P-201."

    # 1. Analyzer classifies as Engineering Calculation with RAG tool
    task = task_analyzer.analyze(query)
    assert task.task_type == TaskType.ENGINEERING_CALCULATION
    assert "ENGINEERING RAG" in task.required_tools
    assert "engineering_calculator" in task.required_tools or "python_calculator" in task.required_tools

    # 2. Deterministic calculation executed via formula registry CR-001
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("P-201", "CR-001")
    assert calc_res["status"] == "SUCCESS"
    assert calc_res["formula_id"] == "CR-001"
    # CR = (6.0 - 4.5) / 5.0 = 0.30 mm/year
    assert pytest.approx(calc_res["result"], rel=1e-3) == 0.30
    assert calc_res["result_unit"] == "mm/year"
    assert calc_res["independent_verification"]["verified"] is True
    assert "Deterministic Python Calculator" in calc_res["independent_verification"]["engine"]


# ==============================================================================
# TEST 6: "Explain photosynthesis."
# ==============================================================================
def test_case_6_general_query_no_mrpl_entity(entity_resolver, task_analyzer):
    query = "Explain photosynthesis."

    # 1. Entity Resolver should detect NO MRPL entity
    entity_res = entity_resolver.resolve(query)
    assert entity_res.resolution_status == EntityResolutionStatus.NO_ENTITY_DETECTED
    assert entity_res.is_mrpl_entity is False

    # 2. Context Guard allows general fallback
    guard = MRPLContextGuard.evaluate(entity_res, query)
    assert guard.knowledge_precedence == "GENERAL_FALLBACK"
    assert guard.should_retrieve_rag is False
    assert guard.unknown_entity_blocked is False

    # 3. Task Analyzer routes as General Knowledge
    task = task_analyzer.analyze(query)
    assert task.domain == "GENERAL"
    assert task.knowledge_source == "GENERAL PRETRAINED KNOWLEDGE"
    assert "ENGINEERING RAG" not in task.required_tools


# ==============================================================================
# TEST 7: "What do we know about P-999?"
# ==============================================================================
def test_case_7_unknown_entity_protection(entity_resolver, task_analyzer, client):
    query = "What do we know about P-999?"

    # 1. Entity Resolver identifies P-999 as NOT FOUND in MRPL KB or Asset Registry
    entity_res = entity_resolver.resolve(query)
    assert entity_res.resolution_status in [EntityResolutionStatus.NOT_FOUND, EntityResolutionStatus.NOT_FOUND_IN_KB]
    assert entity_res.mrpl_kb_status == "NOT_FOUND"
    assert entity_res.asset_registry_status == "NOT_FOUND"
    assert entity_res.canonical_name == "P-999"
    assert entity_res.is_mrpl_entity is False

    # 2. Context Guard blocks unknown entity from hallucination
    guard = MRPLContextGuard.evaluate(entity_res, query)
    assert guard.unknown_entity_blocked is True
    assert "P-999 could not be found in the MRPL Local Knowledge Base or the MRPL Asset Registry" in guard.guarded_response
    assert "The system will not use pretrained/general knowledge to make MRPL-specific claims" in guard.guarded_response

    # 3. Test via API route
    res = client.post("/api/route", json={"query": query})
    assert res.status_code == 200
    route_data = res.json()
    task_p = route_data["task_profile"]
    assert task_p["entity_name"] == "P-999"
    assert task_p["entity_resolution_status"] in ["NOT_FOUND", "NOT_FOUND_IN_KB"]

    # 4. Test via Entity Resolve API
    res_ent = client.post("/api/entities/resolve", json={"query": query})
    assert res_ent.status_code == 200
    ent_data = res_ent.json()
    assert ent_data["entity_resolution"]["resolution_status"] in ["NOT_FOUND", "NOT_FOUND_IN_KB"]
    assert ent_data["entity_resolution"]["mrpl_kb_status"] == "NOT_FOUND"
    assert ent_data["entity_resolution"]["asset_registry_status"] == "NOT_FOUND"
    assert ent_data["context_guard"]["unknown_entity_blocked"] is True

    # 5. Test guarded execution when allow_unverified_fallback is False (Default)
    plan_data = route_data["execution_plan"]
    assert plan_data["primary_model"]["ollama_name"] == "NONE"
    assert "MRPL_CONTEXT_GUARD" in plan_data["required_tools"]
    exec_res = client.post("/api/execute", json={
        "execution_plan": plan_data,
        "query": query,
        "allow_unverified_fallback": False
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["deliverable_type"] == "guarded_entity_resolution_refusal"
    assert "P-999 could not be found in the MRPL Local Knowledge Base or the MRPL Asset Registry" in exec_data["primary_execution"]["response"]
    assert exec_data["allow_general_fallback_available"] is True

    # 6. Test explicit user fallback when allow_unverified_fallback is True
    guard_fallback = MRPLContextGuard.evaluate(entity_res, query, allow_unverified_fallback=True)
    assert guard_fallback.unknown_entity_blocked is False
    assert guard_fallback.allow_unverified_fallback is True
    assert "UNVERIFIED GENERAL KNOWLEDGE — NOT MRPL-VERIFIED" in guard_fallback.warning_banner


# ==============================================================================
# TEST 8: Two-Stage Routing Verification (Knowledge/Tool vs Model Routing)
# ==============================================================================
def test_two_stage_routing_decision(client):
    # Query A: MRPL Equipment Query
    res_a = client.post("/api/route", json={"query": "What do we know about P-201?"})
    assert res_a.status_code == 200
    data_a = res_a.json()
    task_a = data_a["task_profile"]
    plan_a = data_a["execution_plan"]

    # Stage A: Knowledge/Tool Routing
    assert task_a["domain"] == "MRPL ENGINEERING"
    assert task_a["knowledge_source"] == "MRPL LOCAL KNOWLEDGE BASE"
    assert "ENGINEERING RAG" in plan_a["required_tools"]
    assert "None" not in str(plan_a["required_tools"])

    # Stage B: Model Routing (Primary Model assigned)
    assert plan_a["primary_model"]["ollama_name"] is not None

    # Query B: Code Generation Task
    res_b = client.post("/api/route", json={"query": "Write a Python script to parse refinery telemetry logs"})
    assert res_b.status_code == 200
    data_b = res_b.json()
    task_b = data_b["task_profile"]
    plan_b = data_b["execution_plan"]

    assert task_b["domain"] == "SOFTWARE"
    assert "python_sandbox" in plan_b["required_tools"]
    assert "qwen2.5-coder:3b" in [c["ollama_name"] for c in data_b["candidate_evaluations"]]


# ==============================================================================
# TEST 9: Final Acceptance 3-Step Demonstration Flow
# ==============================================================================
def test_three_step_demonstration_flow(client):
    # STEP 1: "What do we know about P-201?"
    res1_route = client.post("/api/route", json={"query": "What do we know about P-201?"})
    assert res1_route.status_code == 200
    r1 = res1_route.json()
    assert r1["task_profile"]["entity_resolution_status"] == "FOUND_IN_MRPL_KB"
    assert "ENGINEERING RAG" in r1["execution_plan"]["required_tools"]
    assert r1["execution_plan"]["primary_model"]["ollama_name"] != "NONE"

    # STEP 2: "What do we know about P-999?" (Initial query)
    res2_route = client.post("/api/route", json={"query": "What do we know about P-999?"})
    assert res2_route.status_code == 200
    r2 = res2_route.json()
    assert r2["task_profile"]["entity_resolution_status"] in ["NOT_FOUND", "NOT_FOUND_IN_KB"]
    assert r2["execution_plan"]["primary_model"]["ollama_name"] == "NONE"
    assert "MRPL_CONTEXT_GUARD" in r2["execution_plan"]["required_tools"]

    # Execute Step 2 without fallback
    res2_exec = client.post("/api/execute", json={
        "query": "What do we know about P-999?",
        "execution_plan": r2["execution_plan"],
        "allow_unverified_fallback": False
    })
    assert res2_exec.status_code == 200
    e2 = res2_exec.json()
    assert e2["deliverable_type"] == "guarded_entity_resolution_refusal"
    assert e2["allow_general_fallback_available"] is True
    assert e2["model_actually_executed"] == "MRPL_CONTEXT_GUARD"
    assert "P-999 could not be found in the MRPL Local Knowledge Base or the MRPL Asset Registry" in e2["primary_execution"]["response"]

    # STEP 3: User clicks [ Ask General LLM Anyway ]
    res3_exec = client.post("/api/execute", json={
        "query": "What do we know about P-999?",
        "execution_plan": r2["execution_plan"],
        "allow_unverified_fallback": True
    })
    assert res3_exec.status_code == 200
    e3 = res3_exec.json()
    assert e3["context_mode"] == "GENERAL_KNOWLEDGE"
    assert e3["mrpl_verified"] is False
    assert e3["knowledge_source_used"] == "General Model Knowledge"
    assert "UNVERIFIED GENERAL KNOWLEDGE — NOT MRPL-VERIFIED" in e3["primary_execution"]["response"]
    assert e3["model_actually_executed"] != "MRPL_CONTEXT_GUARD"

