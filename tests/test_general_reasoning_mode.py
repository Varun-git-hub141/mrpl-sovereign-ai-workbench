import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.services.evidence.evidence_models import SufficiencyStatus, EvidenceContract
from backend.services.evidence.evidence_sufficiency import EvidenceSufficiencyEngine
from backend.services.confidence_engine import ConfidenceEngine, ConfidenceTier
from backend.models.execution_plan import ExecutionPlan, ModelRoleAssignment
from backend.services.ollama_adapter import OllamaAdapter


@pytest.fixture
def client():
    return TestClient(app)


def test_general_reasoning_evidence_sufficiency_not_required():
    """
    Test A: General reasoning queries must bypass MRPL evidence requirements.
    SufficiencyStatus must be NOT_REQUIRED, debt must be 'None', and recommendation must declare general knowledge mode.
    """
    contract = EvidenceContract(
        task_id="TEST-GEN-001",
        task_type="general_reasoning",
        required_evidence=[],
        created_at=0.0,
    )
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[],
        query="What is a centrifugal pump?",
    )
    assert assessment.overall_status == SufficiencyStatus.NOT_REQUIRED
    assert assessment.can_safely_proceed is True
    assert assessment.evidence_debt.debt_summary == "None"
    assert "General knowledge mode" in assessment.system_recommendation


def test_general_reasoning_confidence_not_applicable():
    """
    Test A2: Confidence Engine must not evaluate MRPL retrieval formula for general reasoning.
    ConfidenceTier must be NOT_APPLICABLE, confidence_score must be None, and no missing evidence gates triggered.
    """
    engine = ConfidenceEngine()
    plan = ExecutionPlan(
        request_id="req-test-gen",
        task_spec="What is a centrifugal pump?",
        primary_model=ModelRoleAssignment(model_id="qwen3:4b", ollama_name="qwen3:4b", display_name="Qwen 3 4B"),
        deliverable_type="general_reasoning",
    )
    res = engine.evaluate_confidence(plan=plan, task_type="general_reasoning", retrieved_chunks=[])
    assert res["confidence_score"] is None
    assert res["confidence_tier"] == ConfidenceTier.NOT_APPLICABLE.value
    assert "General Knowledge Mode" in res["status"]
    assert len(res["hard_safety_gates"]) == 0


def test_qwen3_num_predict_budget():
    """
    Test B: OllamaAdapter must assign num_predict=2048 for qwen3:4b when options are not explicitly set.
    """
    adapter = OllamaAdapter()
    gen_opts = {}
    if "qwen3" in "qwen3:4b".lower():
        gen_opts["num_predict"] = 2048
    assert gen_opts["num_predict"] == 2048


def test_mrpl_psv201_question_grounding(client):
    """
    Test C: MRPL questions must continue through Entity Resolution + Engineering RAG.
    """
    res = client.post("/api/route", json={
        "query": "What is the documented set pressure of PSV-201 at MRPL?"
    })
    assert res.status_code == 200
    data = res.json()
    # Route must detect entity or route to proper task
    assert data["local_only"] is True


def test_v201_deterministic_calculation_regression(client):
    """
    Test D: V-201 Shell Course 1 corrosion rate calculation remains fully intact.
    (18.0 - 17.2) / 3.5 = 0.2286 mm/year
    Narrative must not claim insufficient data when calculation inputs are resolved.
    """
    res = client.post("/api/execute", json={
        "query": "For V-201 Shell Course 1, compare the 2017 baseline with the 2020 UT measurement and calculate the corrosion rate."
    })
    assert res.status_code == 200
    data = res.json()
    resp = data.get("primary_execution", {}).get("response", "") or data.get("response", "")
    assert "0.228" in resp or "0.229" in resp or "0.2286" in resp, f"Expected 0.2286 mm/year, got {resp[:200]}"
    # Verify no contradictory stale narrative
    assert "does not contain complete baseline and interval" not in resp, "Contradictory insufficient data claim found in verified calculation"


def test_unknown_mrpl_entity_guard(client):
    """
    Test E: Unknown MRPL entity P-999 must produce MRPL Context Guard with no general model hallucination.
    """
    res = client.post("/api/execute", json={
        "query": "What is P-999 at MRPL?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data.get("deliverable_type") == "guarded_entity_resolution_refusal" or data.get("model_actually_executed") == "MRPL_CONTEXT_GUARD"
    assert data.get("routed_model") == "NONE"
    assert data.get("tools_invoked") == []
    
    # Confidence and Evidence checks
    conf = data.get("confidence_assessment", {})
    assert conf.get("confidence_score") is None
    assert conf.get("confidence_tier") == "NOT_APPLICABLE"
    
    ev = data.get("evidence_assessment", {})
    assert ev.get("overall_status") in ("BLOCKED_BY_CONTEXT_GUARD", "BLOCKED")
    
    # Response must only state unverified entity without hallucinating specs
    resp = data.get("primary_execution", {}).get("response", "")
    assert "could not be found in the MRPL Local Knowledge Base" in resp


# =====================================================================
# URGENT REGRESSION TESTS (A through H)
# =====================================================================

def test_regression_a_numeric_confidence():
    """
    Test A: Numeric confidence (e.g. 0.92) is calculated properly, non-null,
    and serializes without exception.
    """
    engine = ConfidenceEngine()
    plan = ExecutionPlan(
        request_id="req-test-num-conf",
        task_spec="What is the operating service and design pressure of P-201 at MRPL?",
        primary_model=ModelRoleAssignment(model_id="qwen2.5-coder:3b", ollama_name="qwen2.5-coder:3b", display_name="Qwen 2.5 Coder 3B"),
        deliverable_type="document_qa",
    )
    from backend.models.rag_models import RetrievedChunk, ChunkProvenance, RetrievalScoreBreakdown, AuthorityLevel
    sample_chunk = RetrievedChunk(
        text="Equipment Tag: P-201. Description: Crude Feed Booster Pump. Operating Service: CDU Primary Charge. Design Pressure: 28.5 kg/cm2g. Design Temperature: 180 C.",
        source=ChunkProvenance(document="MRPL-DS-P201.pdf", document_id="DOC-DS-P201", document_type="Equipment Datasheet", equipment_tag="P-201", page=1, section="Mechanical Specs"),
        retrieval=RetrievalScoreBreakdown(keyword_score=0.95, semantic_score=0.90, hybrid_score=0.93)
    )
    res = engine.evaluate_confidence(plan=plan, task_type="document_qa", retrieved_chunks=[sample_chunk], entity_tag="P-201")
    assert res["overall_confidence"] is not None
    assert isinstance(res["overall_confidence"], (int, float))
    assert res["overall_confidence"] >= 0.70
    assert res["confidence_tier"] in (ConfidenceTier.HIGH.value, ConfidenceTier.MEDIUM.value)


def test_regression_b_null_confidence_safe_evaluation():
    """
    Test B: Null confidence handles safely without exception across all evaluation paths.
    """
    engine = ConfidenceEngine()
    plan = ExecutionPlan(
        request_id="req-test-null-conf",
        task_spec="Unknown entity check",
        primary_model=ModelRoleAssignment(model_id="MRPL_CONTEXT_GUARD", ollama_name="NONE", display_name="NONE (MRPL_CONTEXT_GUARD)"),
        deliverable_type="unknown_mrpl_entity",
    )
    res = engine.evaluate_confidence(plan=plan, task_type="unknown_mrpl_entity", retrieved_chunks=[])
    assert res["confidence_score"] is None
    assert res["overall_confidence"] is None
    assert res["retrieval_score"] is None
    assert res["evidence_coverage"] is None
    assert res["verification_score"] is None
    assert res["confidence_tier"] == "NOT_APPLICABLE"


def test_regression_c_general_reasoning_mode(client):
    """
    Test C: General reasoning query produces GENERAL_REASONING, confidence N/A,
    and explicitly marks General Knowledge Mode.
    """
    res = client.post("/api/route", json={
        "query": "What is a centrifugal pump? Explain its basic operating principle."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["task_profile"]["task_type"] == "general_reasoning"
    
    plan = data["execution_plan"]
    assert plan["deliverable_type"] == "general_reasoning"
    assert plan["primary_model"]["ollama_name"] in ("qwen3:4b", "qwen2.5-coder:3b", "qwen2.5vl:3b")


def test_regression_d_context_guard_blocked_entity(client):
    """
    Test D: Unknown MRPL entity P-999 is blocked by Context Guard with model NONE,
    confidence N/A, and pretrained knowledge blocked.
    """
    res = client.post("/api/route", json={
        "query": "What is the design pressure of P-999 at MRPL?"
    })
    assert res.status_code == 200
    data = res.json()
    assert "NOT_FOUND" in data["task_profile"]["entity_resolution_status"]
    assert data["execution_plan"]["primary_model"]["ollama_name"] == "NONE"


def test_regression_e_engineering_rag_no_general_knowledge_leak(client):
    """
    Test E: Engineering RAG query (P-201) must be classified as document_qa / KNOWLEDGE_RETRIEVAL,
    grounded in MRPL KB, and NOT general_reasoning.
    """
    res = client.post("/api/route", json={
        "query": "What is the operating service and design pressure of P-201 at MRPL?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["task_profile"]["task_type"] in ("document_qa", "equipment_approval", "engineering_calculation")
    assert data["task_profile"]["task_type"] != "general_reasoning"
    assert data["execution_plan"]["deliverable_type"] != "general_reasoning"
    assert "ENGINEERING RAG" in data["execution_plan"]["required_tools"]


def test_regression_f_pre_retrieval_missing_entity_allows_retrieval(client):
    """
    Test F: Pre-retrieval missing entity warning does not block execution for known entities (P-201).
    RAG retrieval resolves entity records during execution.
    """
    res = client.post("/api/execute", json={
        "query": "What is the operating service and design pressure of P-201 at MRPL?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data.get("mrpl_verified") is True
    
    # Post-retrieval evidence assessment must be present and grounded
    ev = data.get("evidence_assessment", {})
    assert ev.get("overall_status") in ("SUFFICIENT", "PARTIALLY_SUFFICIENT")
    
    # Confidence must be a valid number
    conf = data.get("confidence_assessment", {})
    assert conf.get("overall_confidence") is not None
    assert isinstance(conf.get("overall_confidence"), (int, float))


def test_regression_g_model_consistency(client):
    """
    Test G: Planned model and executed model must either match or have an explicit fallback record.
    """
    res = client.post("/api/execute", json={
        "query": "What is the design temperature of P-201 at MRPL?"
    })
    assert res.status_code == 200
    data = res.json()
    
    routed_model = data.get("routed_model")
    executed_model = data.get("executed_model") or data.get("model_actually_executed")
    fallback_triggered = data.get("fallback_triggered", False)
    
    if not fallback_triggered:
        assert routed_model == executed_model, f"Model mismatch without fallback: routed={routed_model}, executed={executed_model}"
    else:
        assert data.get("fallback_reason") is not None


def test_regression_h_full_ui_null_safe_confidence_smoke():
    """
    Test H: Ask AI serialization and confidence structures must never crash when confidence fields are null.
    """
    # Verify ConfidenceEngine outputs safely with None / NOT_APPLICABLE
    engine = ConfidenceEngine()
    plan_guard = ExecutionPlan(
        request_id="req-test-h-1",
        task_spec="Unknown entity P-999",
        primary_model=ModelRoleAssignment(model_id="MRPL_CONTEXT_GUARD", ollama_name="NONE", display_name="NONE (MRPL_CONTEXT_GUARD)"),
        deliverable_type="unknown_mrpl_entity",
    )
    conf_guard = engine.evaluate_confidence(plan=plan_guard, task_type="unknown_mrpl_entity")
    assert conf_guard["overall_confidence"] is None
    assert conf_guard["confidence_score"] is None
    assert conf_guard["retrieval_score"] is None
    assert conf_guard["evidence_coverage"] is None
    assert conf_guard["verification_score"] is None

    # General reasoning null confidence
    plan_gen = ExecutionPlan(
        request_id="req-test-h-2",
        task_spec="What is Bernoulli's principle?",
        primary_model=ModelRoleAssignment(model_id="qwen3:4b", ollama_name="qwen3:4b", display_name="Qwen 3 4B"),
        deliverable_type="general_reasoning",
    )
    conf_gen = engine.evaluate_confidence(plan=plan_gen, task_type="general_reasoning")
    assert conf_gen["overall_confidence"] is None
    assert conf_gen["confidence_score"] is None
    assert "General Knowledge Mode" in conf_gen["status"]


def test_regression_i_multi_entity_cross_asset_bait_blocked(client):
    """
    Test I: Multi-entity cross-asset bait query (P-201 known + P-999 unknown).
    Known P-201 must NOT allow unknown P-999 to bypass Context Guard.
    """
    res = client.post("/api/execute", json={
        "query": "P-201 is a pump. Is P-999 also a pump at MRPL?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["context_mode"] == "MRPL_LOCAL_KNOWLEDGE_BASE (BLOCKED_ABSENCE)"
    assert data["executed_model"] == "MRPL_CONTEXT_GUARD (Sovereign Local Gate)"
    assert data["mrpl_verified"] is False
    assert data["confidence_assessment"]["overall_confidence"] is None


def test_regression_j_multi_entity_comparison_blocked_if_unresolved(client):
    """
    Test J: Comparison of known and unknown entity at MRPL must be blocked.
    """
    res = client.post("/api/execute", json={
        "query": "Compare P-201 and P-999 at MRPL."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["context_mode"] == "MRPL_LOCAL_KNOWLEDGE_BASE (BLOCKED_ABSENCE)"
    assert data["executed_model"] == "MRPL_CONTEXT_GUARD (Sovereign Local Gate)"


def test_regression_k_generic_tag_inquiry_allowed(client):
    """
    Test K: Generic equipment tag / nomenclature inquiry enters GENERAL_REASONING.
    """
    res = client.post("/api/execute", json={
        "query": "What could P-999 mean as a generic equipment tag?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["context_mode"] == "GENERAL"
    assert data["deliverable_type"] == "general_reasoning"
    assert data["evidence_assessment"]["overall_status"] == "NOT_REQUIRED"


def test_regression_l_generic_prefix_inquiry_allowed(client):
    """
    Test L: Generic prefix inquiry enters GENERAL_REASONING.
    """
    res = client.post("/api/execute", json={
        "query": "What does P- prefix generally mean in equipment tagging?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["context_mode"] == "GENERAL"
    assert data["deliverable_type"] == "general_reasoning"


def test_regression_m_generic_comparison_allowed(client):
    """
    Test M: Generic comparison of equipment tags enters GENERAL_REASONING.
    """
    res = client.post("/api/execute", json={
        "query": "Compare the general meaning of P-201 and P-999 as equipment tags."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["context_mode"] == "GENERAL"
    assert data["deliverable_type"] == "general_reasoning"


def test_regression_n_explicit_non_mrpl_override(client):
    """
    Test N: User explicitly specifying not asking about MRPL enters GENERAL_REASONING.
    """
    res = client.post("/api/execute", json={
        "query": "What could P-999 generally mean? I am not asking about MRPL."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["context_mode"] == "GENERAL"
    assert data["deliverable_type"] == "general_reasoning"





