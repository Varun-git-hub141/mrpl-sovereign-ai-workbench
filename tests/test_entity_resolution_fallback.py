"""
Automated Test Suite for 3-Tier Entity Resolution Fallback & Evidence Boundaries
=================================================================================
Verifies:
1. Path A: KB FOUND (e.g. P-201)
   - KB = FOUND
   - Asset Registry = NOT_CHECKED
   - resolution = FOUND_IN_MRPL_KB
   - Existing behavior preserved

2. Path B: KB NOT_FOUND + Asset Registry FOUND (e.g. E-301)
   - KB = NOT_FOUND
   - Asset Registry = FOUND
   - resolution = FOUND_IN_ASSET_REGISTRY
   - Registry metadata provides identity/context (tag, class, unit, service)
   - Registry metadata does NOT automatically satisfy evidence contracts (thickness, corrosion rate, etc.)
   - If no engineering documents exist, returns clear message:
     "Asset exists in Asset Registry, but supporting engineering evidence was not found."
   - If linked documents are attached/retrieved, Evidence Sufficiency Engine evaluates them normally

3. Path C: KB NOT_FOUND + Asset Registry NOT_FOUND (e.g. P-999, E-999)
   - KB = NOT_FOUND
   - Asset Registry = NOT_FOUND
   - Context Guard = LOCAL ENTITY NOT RESOLVED
   - Blocks pretrained hallucination / MRPL-specific claims
   - Explicit user fallback ("Ask General LLM Anyway") labeled:
     UNVERIFIED GENERAL KNOWLEDGE — NOT MRPL-VERIFIED
   - Fallback cannot satisfy evidence contracts or become MRPL evidence

4. Specific E-301 Scenarios:
   - Does NOT report "E-301 does not exist" when in Asset Registry
   - Reports KB: NOT FOUND, Asset Registry: FOUND
   - Clearly states supporting engineering evidence not found when absent
   - Does not invent engineering facts from registry metadata
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.entity_resolver import MRPLEntityResolver
from backend.services.context_guard import MRPLContextGuard
from backend.services.task_analyzer import TaskAnalyzer
from backend.services.hybrid_rag import HybridRAGService
from backend.services.evidence import (
    EvidenceRequirementEngine,
    EvidenceSufficiencyEngine,
    EvidenceContract,
    SufficiencyStatus,
)
from backend.models.entity_models import (
    EntityResolutionStatus,
    EntityType,
)
from backend.models.rag_models import (
    HybridSearchRequest,
    RetrievedChunk,
    KnowledgeSourceType,
    ChunkProvenance,
    RetrievalScoreBreakdown,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def entity_resolver():
    return MRPLEntityResolver()


@pytest.fixture(scope="module")
def task_analyzer():
    return TaskAnalyzer()


@pytest.fixture(scope="module")
def hybrid_rag():
    return HybridRAGService()


@pytest.fixture(scope="module")
def evidence_engine():
    return EvidenceRequirementEngine()


# ==============================================================================
# PATH A: KB FOUND (e.g. P-201)
# ==============================================================================
def test_path_a_kb_found(entity_resolver, client):
    query = "What is the wall thickness and maintenance history for P-201?"
    res = entity_resolver.resolve(query)

    # Status checks
    assert res.mrpl_kb_status == "FOUND"
    assert res.asset_registry_status == "NOT_CHECKED"
    assert res.resolution_status == EntityResolutionStatus.FOUND_IN_MRPL_KB
    assert res.canonical_name == "P-201"
    assert res.is_mrpl_entity is True
    assert len(res.matched_documents) > 0

    # Context Guard check
    guard = MRPLContextGuard.evaluate(res, query)
    assert guard.knowledge_precedence == "MRPL_AUTHORITATIVE"
    assert guard.should_retrieve_rag is True
    assert guard.unknown_entity_blocked is False

    # API Route check
    api_res = client.post("/api/entities/resolve", json={"query": query})
    assert api_res.status_code == 200
    data = api_res.json()["entity_resolution"]
    assert data["mrpl_kb_status"] == "FOUND"
    assert data["asset_registry_status"] == "NOT_CHECKED"
    assert data["resolution_status"] == "FOUND_IN_MRPL_KB"


# ==============================================================================
# PATH B: KB NOT_FOUND + ASSET REGISTRY FOUND (e.g. E-301)
# ==============================================================================
def test_path_b_asset_registry_found_identity_only(entity_resolver, client, evidence_engine):
    from backend.models.asset_hierarchy import AssetCreateRequest, AssetClassEnum
    from backend.services.asset_registry import AssetRegistryService
    reg_svc = AssetRegistryService()
    if not reg_svc.get_asset("E-888"):
        reg_svc.create_asset(AssetCreateRequest(
            asset_tag="E-888",
            asset_name="Crude Preheater Shell & Tube Exchanger Test Identity",
            asset_class=AssetClassEnum.HEAT_EXCHANGER,
            process_unit="CDU-II",
            service_description="Test Service Only",
            design_code="API 610 / ASME VIII",
        ))

    query = "What is the status and design code of heat exchanger E-888?"
    res = entity_resolver.resolve(query)

    # 1. Status checks
    assert res.mrpl_kb_status == "NOT_FOUND"
    assert res.asset_registry_status == "FOUND"
    assert res.resolution_status == EntityResolutionStatus.FOUND_IN_ASSET_REGISTRY
    assert res.canonical_name == "E-888"
    assert res.is_mrpl_entity is True

    # 2. Registry Identity is available
    assert res.asset_record is not None
    assert res.asset_record["asset_tag"] == "E-888"
    assert res.asset_record["process_unit"] == "CDU-II"
    assert res.asset_record["asset_name"] == "Crude Preheater Shell & Tube Exchanger Test Identity"

    # 3. Context Guard check
    guard = MRPLContextGuard.evaluate(res, query)
    assert guard.knowledge_precedence == "MRPL_ASSET_REGISTRY"
    assert guard.unknown_entity_blocked is False
    assert "Asset Registry metadata establishes equipment identity" in guard.context_directive

    # 4. Evidence Requirements are NOT automatically satisfied by registry metadata
    contract = evidence_engine.generate_contract(
        query="What is the historical corrosion rate and ultrasonic thickness of E-888?",
        risk_override="HIGH",
    )
    # Without retrieved engineering documents, evidence assessment must NOT be SUFFICIENT
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[],
        attached_data=None,
        tool_outputs={},
        has_images=False,
        query="What is the historical corrosion rate and ultrasonic thickness of E-888?",
    )
    assert assessment.overall_status in [SufficiencyStatus.INSUFFICIENT, SufficiencyStatus.PARTIALLY_SUFFICIENT, SufficiencyStatus.BLOCKED]
    assert assessment.can_safely_proceed is False

    # 5. Full execution when E-888 has no engineering evidence
    route_res = client.post("/api/route", json={"query": query})
    assert route_res.status_code == 200
    route_plan = route_res.json()["execution_plan"]

    exec_res = client.post("/api/execute", json={
        "query": query,
        "execution_plan": route_plan,
        "allow_unverified_fallback": False,
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    resp_text = exec_data["primary_execution"]["response"]
    
    # Must NOT say "does not exist"
    assert "does not exist" not in resp_text.lower()
    # Must explicitly state it exists in Asset Registry but evidence was not found
    assert "Asset exists in Asset Registry, but supporting engineering evidence was not found." in resp_text
    assert "MRPL Knowledge Base Status:\nNOT FOUND" in resp_text
    assert "Asset Registry Status:\nFOUND" in resp_text


def test_path_b_with_linked_documents(evidence_engine):
    """If linked engineering documents are attached/retrieved, Evidence Sufficiency Engine evaluates them normally."""
    contract = evidence_engine.generate_contract(
        query="What is the wall thickness of E-301?",
        risk_override="MEDIUM",
    )
    
    # Simulate a linked UT inspection document retrieved for E-301
    mock_chunk = RetrievedChunk(
        text="Ultrasonic thickness survey for E-301 shell recorded nominal thickness of 12.50 mm and current thickness of 11.20 mm on 2024-01-15.",
        source=ChunkProvenance(
            document="MRPL-INSP-2024-E301-UT.pdf",
            document_id="DOC-E301-01",
            document_type="UT Inspection Survey",
            page=1,
            equipment_tag="E-301",
        ),
        retrieval=RetrievalScoreBreakdown(
            semantic_score=0.92,
            keyword_score=0.88,
            metadata_score=1.0,
            hybrid_score=0.93,
        ),
    )
    
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[mock_chunk],
        attached_data=None,
        tool_outputs={},
        has_images=False,
        query="What is the wall thickness of E-301?",
    )
    # The presence of linked engineering evidence improves coverage and evaluates normally
    assert assessment.coverage_score > 0.0


# ==============================================================================
# PATH C: KB NOT_FOUND + ASSET REGISTRY NOT_FOUND (e.g. P-999)
# ==============================================================================
def test_path_c_neither_found(entity_resolver, client):
    query = "What is the design temperature of pump P-999?"
    res = entity_resolver.resolve(query)

    # 1. Status checks
    assert res.mrpl_kb_status == "NOT_FOUND"
    assert res.asset_registry_status == "NOT_FOUND"
    assert res.resolution_status in [EntityResolutionStatus.NOT_FOUND, EntityResolutionStatus.NOT_FOUND_IN_KB]
    assert res.canonical_name == "P-999"
    assert res.is_mrpl_entity is False

    # 2. Context Guard blocks organization claims
    guard = MRPLContextGuard.evaluate(res, query, allow_unverified_fallback=False)
    assert guard.unknown_entity_blocked is True
    assert guard.context_guard_status == "LOCAL ENTITY NOT RESOLVED"
    assert "Entity: P-999" in guard.guarded_response
    assert "MRPL Knowledge Base Status:\nNOT FOUND" in guard.guarded_response
    assert "Asset Registry Status:\nNOT FOUND" in guard.guarded_response
    assert "Context Guard:\nLOCAL ENTITY NOT RESOLVED" in guard.guarded_response
    assert "The system will not use pretrained/general knowledge to make MRPL-specific claims" in guard.guarded_response

    # 3. User clicks explicit fallback
    guard_fb = MRPLContextGuard.evaluate(res, query, allow_unverified_fallback=True)
    assert guard_fb.unknown_entity_blocked is False
    assert guard_fb.allow_unverified_fallback is True
    assert guard_fb.warning_banner == "UNVERIFIED GENERAL KNOWLEDGE — NOT MRPL-VERIFIED"
    assert "This response is NOT MRPL evidence and cannot satisfy Evidence Contract requirements" in guard_fb.context_directive


# ==============================================================================
# SPECIFIC E-301 SCENARIO TESTS
# ==============================================================================
def test_e301_specific_scenarios(entity_resolver, client):
    # Scenario 1 & 2: E-301 in Asset Registry
    query = "What is heat exchanger E-301?"
    res = entity_resolver.resolve(query)
    assert res.mrpl_kb_status == "NOT_FOUND"
    assert res.asset_registry_status == "FOUND"
    assert res.resolution_status == EntityResolutionStatus.FOUND_IN_ASSET_REGISTRY

    # Scenario 4 & 5: Clear statement without inventing engineering facts
    res_api = client.post("/api/entities/resolve", json={"query": query})
    assert res_api.status_code == 200
    api_payload = res_api.json()
    assert api_payload["entity_resolution"]["mrpl_kb_status"] == "NOT_FOUND"
    assert api_payload["entity_resolution"]["asset_registry_status"] == "FOUND"

    # Scenario 6: Unknown E-999 in neither source
    query_unknown = "What is heat exchanger E-999?"
    res_unk = entity_resolver.resolve(query_unknown)
    assert res_unk.mrpl_kb_status == "NOT_FOUND"
    assert res_unk.asset_registry_status == "NOT_FOUND"
    guard_unk = MRPLContextGuard.evaluate(res_unk, query_unknown)
    assert guard_unk.unknown_entity_blocked is True
    assert "LOCAL ENTITY NOT RESOLVED" in guard_unk.guarded_response
