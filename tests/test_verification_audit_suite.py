import pytest
import time
import uuid
from backend.models.model_profile import (
    ModelProfile,
    CapabilityVector,
    HardwareRequirements,
    PerformanceStats,
    ModelHealthStatus,
)
from backend.models.task_profile import TaskProfile, TaskType, RiskLevel, InputModality
from backend.models.routing_decision import (
    RoutingDecision,
    CandidateEvaluation,
    CandidateSubscores,
    SelectedModelRole,
)
from backend.models.execution_plan import ExecutionPlan, ModelRoleAssignment, VerificationSpec
from backend.models.verification_result import (
    VerificationReport,
    VerificationStatus,
    CrossModelStatus,
    DeterministicStatus,
    EvidenceStatus,
)
from backend.services.router import IntelligentModelRouter
from backend.services.execution_planner import ExecutionPlanner
from backend.services.verification_engine import VerificationEngine
from backend.services.confidence_engine import ConfidenceEngine
from backend.services.orchestrator import ExecutionOrchestrator
from backend.services.fallback_manager import FallbackManager
from backend.services.registry import ModelRegistry
from backend.services.discovery import ModelDiscoveryService
from backend.telemetry.audit import AuditTrail, NetworkEgressGuard


class MockOllamaAdapter:
    def __init__(self, host="http://127.0.0.1:11434"):
        self.host = host
        self.calls = []
        self.tags = [
            {"name": "qwen2.5-coder:3b", "size": 3 * 1024**3, "details": {"family": "qwen2"}},
            {"name": "qwen3:4b", "size": 4 * 1024**3, "details": {"family": "qwen3"}},
            {"name": "qwen2.5vl:3b", "size": 4 * 1024**3, "details": {"family": "qwen25vl"}},
        ]

    def check_health(self):
        return {"reachable": True, "status": "healthy"}

    def list_tags(self):
        return self.tags

    def show_model(self, name):
        return {"details": {"family": "qwen2" if "coder" in name else "qwen3" if "qwen3" in name else "qwen25vl"}}

    def generate(self, model, prompt, system=None, images=None, options=None):
        self.calls.append({"model": model, "prompt": prompt, "images": bool(images)})
        if "fail" in model:
            return {"success": False, "error": "Model simulated failure", "latency_ms": 50.0}
        
        # Simulated responses
        if "corrosion" in prompt.lower() and "calculate" in prompt.lower():
            resp = "The calculated corrosion rate is 0.30 mm/year with 15.0 years remaining life."
        elif "p-101" in prompt.lower() and "7.4" in prompt:
            resp = "Operation cannot be approved unconditionally. Non-drive end vibration exceeds ISO 10816 Zone D trip limits."
        elif "pid" in prompt.lower() or images:
            resp = "Identified equipment: Crude Feed Pump P-101A, E-101 Preheat Exchanger, and C-101 Column. Control loops: FV-101, PT-102, FIC-101."
        else:
            resp = "Technical summary: maintenance turnaround schedule and isolation protocols verified."

        return {
            "success": True,
            "model": model,
            "response": resp,
            "latency_ms": 120.0,
            "eval_count": 50,
        }


def get_mock_registry():
    adapter = MockOllamaAdapter()
    discovery = ModelDiscoveryService(adapter=adapter)
    return ModelRegistry(discovery_service=discovery)


# ─────────────────────────────────────────────────────────────
# Test A: LOW-risk text query
# ─────────────────────────────────────────────────────────────
def test_a_low_risk_query():
    registry = get_mock_registry()
    planner = ExecutionPlanner(registry=registry)
    task = TaskProfile(
        task_type=TaskType.MEMO_SUMMARIZATION,
        intent="summarize_memo",
        risk=RiskLevel.LOW,
        modality=InputModality.TEXT,
    )
    decision = RoutingDecision(
        request_id="req-low-1",
        task=task,
        selected_models=[
            SelectedModelRole(model_id="model-1", ollama_name="qwen2.5-coder:3b", role="primary", display_name="Coder")
        ],
        verification_required=False,
        candidates=[
            CandidateEvaluation(model_id="model-1", ollama_name="qwen2.5-coder:3b", score=0.88, eligible=True, subscores=CandidateSubscores())
        ],
    )
    plan = planner.create_execution_plan(task, decision)
    assert plan.risk == RiskLevel.LOW
    assert plan.verifier_model is None
    assert plan.verification_spec.cross_model == "NOT_REQUIRED"
    assert plan.verification_spec.deterministic == "NOT_REQUIRED"
    assert plan.verification_independence == "NOT_APPLICABLE"

    engine = VerificationEngine()
    report = engine.verify(plan, "Summarize the memo", "Executive brief: unit turnaround scheduled for 10 days.")
    assert report.status == VerificationStatus.NOT_REQUIRED
    assert report.cross_model_status == CrossModelStatus.NOT_REQUIRED
    assert report.deterministic_status == DeterministicStatus.NOT_REQUIRED
    assert report.model_agreement == "NOT_APPLICABLE"
    assert "not required" in report.notes.lower()


# ─────────────────────────────────────────────────────────────
# Test B: MEDIUM-risk engineering calculation
# ─────────────────────────────────────────────────────────────
def test_b_medium_risk_calculation():
    registry = get_mock_registry()
    planner = ExecutionPlanner(registry=registry)
    task = TaskProfile(
        task_type=TaskType.ENGINEERING_CALCULATION,
        intent="calculate_corrosion",
        risk=RiskLevel.MEDIUM,
        modality=InputModality.TEXT,
        required_capabilities=CapabilityVector(mathematics=0.95),
    )
    decision = RoutingDecision(
        request_id="req-med-1",
        task=task,
        selected_models=[
            SelectedModelRole(model_id="model-1", ollama_name="qwen2.5-coder:3b", role="primary", display_name="Coder")
        ],
        verification_required=False,
        candidates=[
            CandidateEvaluation(model_id="model-1", ollama_name="qwen2.5-coder:3b", score=0.91, eligible=True, subscores=CandidateSubscores())
        ],
    )
    plan = planner.create_execution_plan(task, decision)
    assert plan.verification_spec.deterministic_required is True
    assert plan.verification_spec.cross_model_required is False

    engine = VerificationEngine()
    confidence_engine = ConfidenceEngine()
    prompt = "Calculate corrosion rate for wall thickness from 12.7 mm down to 11.2 mm over 5.0 years."
    primary_response = "Calculated corrosion rate is 0.30 mm/year per API 570."

    report = engine.verify(plan, prompt, primary_response)
    assert report.deterministic_status == DeterministicStatus.PASSED
    assert report.cross_model_status == CrossModelStatus.NOT_REQUIRED
    assert report.deterministic.match is True
    assert report.status == VerificationStatus.SUPPORTED

    conf = confidence_engine.evaluate_confidence(plan, report, primary_response)
    assert conf["deterministic_pass"] is True
    assert conf["deterministic_status"] == "PASSED"
    assert conf["cross_model_status"] == "NOT_REQUIRED"


# ─────────────────────────────────────────────────────────────
# Test C: HIGH-risk approval with dual-model & human review
# ─────────────────────────────────────────────────────────────
def test_c_high_risk_approval():
    registry = get_mock_registry()
    planner = ExecutionPlanner(registry=registry)
    task = TaskProfile(
        task_type=TaskType.EQUIPMENT_APPROVAL,
        intent="pump_approval",
        risk=RiskLevel.HIGH,
        requires_verification=True,
    )
    decision = RoutingDecision(
        request_id="req-high-1",
        task=task,
        selected_models=[
            SelectedModelRole(model_id="model-reasoner", ollama_name="qwen3:4b", role="primary", display_name="Reasoner"),
            SelectedModelRole(model_id="model-coder", ollama_name="qwen2.5-coder:3b", role="independent_verifier", display_name="Coder"),
        ],
        verification_required=True,
        candidates=[
            CandidateEvaluation(model_id="model-reasoner", ollama_name="qwen3:4b", score=0.94, eligible=True, subscores=CandidateSubscores()),
            CandidateEvaluation(model_id="model-coder", ollama_name="qwen2.5-coder:3b", score=0.86, eligible=True, subscores=CandidateSubscores()),
        ],
    )
    plan = planner.create_execution_plan(task, decision)
    assert plan.risk == RiskLevel.HIGH
    assert plan.verifier_model is not None
    assert plan.verification_spec.cross_model_required is True
    assert plan.human_approval_required is True

    adapter = MockOllamaAdapter()
    orchestrator = ExecutionOrchestrator(adapter=adapter, fallback_manager=FallbackManager(adapter, registry))
    result = orchestrator.execute_plan(plan, "Critical Equipment Approval for Pump P-101 with 7.4 mm/s vibration.")

    assert result["success"] is True
    assert result["verifier_execution"] is not None
    assert result["verification_report"]["cross_model_status"] == "PASSED"
    assert result["human_approval"]["required"] is True
    assert len(result["ollama_calls"]) == 2


# ─────────────────────────────────────────────────────────────
# Test D: Vision query with image
# ─────────────────────────────────────────────────────────────
def test_d_vision_query_routing():
    adapter = MockOllamaAdapter()
    discovery = ModelDiscoveryService(adapter=adapter)
    registry = ModelRegistry(discovery_service=discovery)
    
    class MockHealth:
        adapter = MockOllamaAdapter()
        def evaluate_model_eligibility(self, m, hw, ollama):
            return (ModelHealthStatus.HEALTHY, True, "Healthy")

    router = IntelligentModelRouter(registry=registry, health_manager=MockHealth())
    task = TaskProfile(
        task_type=TaskType.MULTIMODAL_DOCUMENT_ANALYSIS,
        intent="analyze_pid",
        risk=RiskLevel.MEDIUM,
        modality=InputModality.VISION,
        required_capabilities=CapabilityVector(vision=0.95, ocr=0.90, document_understanding=0.90),
    )

    decision = router.route(task)
    primary = decision.selected_models[0]
    assert primary.ollama_name == "qwen2.5vl:3b"

    planner = ExecutionPlanner(registry=registry)
    plan = planner.create_execution_plan(task, decision)
    assert plan.vision_required is True
    assert "vision_multimodal_extractor" in plan.required_tools


# ─────────────────────────────────────────────────────────────
# Test E: Model unavailable -> candidate rejected
# ─────────────────────────────────────────────────────────────
def test_e_model_unavailable_evaluated():
    class MockHealthDegraded:
        adapter = MockOllamaAdapter()
        def evaluate_model_eligibility(self, m, hw, ollama):
            if "coder" in m.ollama_name:
                return (ModelHealthStatus.UNAVAILABLE, False, "Model OOM / Process Crashed")
            return (ModelHealthStatus.HEALTHY, True, "Healthy")

    registry = get_mock_registry()
    router = IntelligentModelRouter(registry=registry, health_manager=MockHealthDegraded())

    task = TaskProfile(
        task_type=TaskType.CODING,
        intent="write_code",
        risk=RiskLevel.LOW,
        modality=InputModality.SOURCE_CODE,
        required_capabilities=CapabilityVector(coding=0.95),
    )
    decision = router.route(task)
    coder_cand = next(c for c in decision.candidates if "coder" in c.ollama_name)
    assert coder_cand.eligible is False
    assert "Crashed" in coder_cand.rejection_reason
    assert decision.selected_models[0].ollama_name != "qwen2.5-coder:3b"


# ─────────────────────────────────────────────────────────────
# Test F: Primary model failure fallback
# ─────────────────────────────────────────────────────────────
def test_f_primary_model_failure_fallback():
    class FailAdapter(MockOllamaAdapter):
        def generate(self, model, prompt, system=None, images=None, options=None):
            self.calls.append({"model": model})
            if model == "fail-primary:3b":
                return {"success": False, "error": "CUDA OOM", "latency_ms": 10.0}
            return {"success": True, "model": model, "response": "Fallback execution success.", "latency_ms": 80.0}

    adapter = FailAdapter()
    registry = get_mock_registry()
    fallback_mgr = FallbackManager(adapter=adapter, registry=registry)

    class MockDecision:
        selected_models = [SelectedModelRole(model_id="m1", ollama_name="fail-primary:3b", role="primary", display_name="Fail Model")]
        task = type('T', (), {'task_type': type('TT', (), {'value': 'coding'})()})()
        candidates = [
            type('C', (), {'eligible': True, 'ollama_name': 'qwen2.5-coder:3b', 'score': 0.85})(),
        ]

    res = fallback_mgr.execute_with_fallback(MockDecision(), "Write python code")
    assert res["success"] is True
    assert res["model_used"] == "qwen2.5-coder:3b"
    assert res["is_fallback"] is True
    assert res["fallback_from"] == "fail-primary:3b"


# ─────────────────────────────────────────────────────────────
# Test G: No independent verifier available -> LIMITED independence
# ─────────────────────────────────────────────────────────────
def test_g_limited_independence():
    registry = get_mock_registry()
    planner = ExecutionPlanner(registry=registry)

    task = TaskProfile(
        task_type=TaskType.EQUIPMENT_APPROVAL,
        intent="approval",
        risk=RiskLevel.HIGH,
    )
    # Both models from same family (e.g. qwen2 and qwen2)
    decision = RoutingDecision(
        request_id="req-same-fam",
        task=task,
        selected_models=[
            SelectedModelRole(model_id="model-1", ollama_name="qwen2.5-coder:3b", role="primary", display_name="Coder 1"),
            SelectedModelRole(model_id="model-2", ollama_name="qwen2.5-coder:3b", role="independent_verifier", display_name="Coder 2"),
        ],
        verification_required=True,
    )
    plan = planner.create_execution_plan(task, decision)
    assert plan.verification_independence == "LIMITED"


# ─────────────────────────────────────────────────────────────
# Test H: Deterministic disagreement -> CONFLICT DETECTED
# ─────────────────────────────────────────────────────────────
def test_h_deterministic_conflict():
    engine = VerificationEngine()
    confidence_engine = ConfidenceEngine()

    plan = ExecutionPlan(
        request_id="req-conflict-h",
        risk=RiskLevel.MEDIUM,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen2.5-coder:3b", role="primary", architecture="qwen2"),
        verification_spec=VerificationSpec(deterministic="REQUIRED"),
    )

    prompt = "Calculate corrosion rate for 12.7 mm reduced to 11.2 mm over 5.0 years."
    # Expected is 0.30 mm/year; Primary model hallucinated 0.85 mm/year
    primary_bad_response = "The corrosion rate is 0.85 mm/year."

    report = engine.verify(plan, prompt, primary_bad_response)
    assert report.deterministic_status == DeterministicStatus.CONFLICT
    assert report.deterministic.match is False
    assert report.deterministic.expected_value == 0.30
    assert report.status == VerificationStatus.CONTRADICTED

    conf = confidence_engine.evaluate_confidence(plan, report, primary_bad_response)
    assert conf["confidence_tier"] == "CONFLICT_DETECTED"
    assert conf["deterministic_pass"] is False


# ─────────────────────────────────────────────────────────────
# Test I: External network attempt -> REJECTED
# ─────────────────────────────────────────────────────────────
def test_i_external_network_rejected():
    assert NetworkEgressGuard.validate_url("http://127.0.0.1:11434") is True
    assert NetworkEgressGuard.validate_url("http://localhost:8000") is True

    # Cloud LLMs must be rejected immediately
    assert NetworkEgressGuard.validate_url("https://api.openai.com/v1/chat/completions") is False
    assert NetworkEgressGuard.validate_url("https://api.anthropic.com") is False

    with pytest.raises(PermissionError, match="Sovereignty policy violation"):
        NetworkEgressGuard.enforce_local_url("https://api.openai.com")


# ─────────────────────────────────────────────────────────────
# Test J: Registry refresh dynamically discovers new models
# ─────────────────────────────────────────────────────────────
def test_j_dynamic_discovery_refresh():
    adapter = MockOllamaAdapter()
    discovery = ModelDiscoveryService(adapter=adapter)
    registry = ModelRegistry(discovery_service=discovery)

    initial_count = len(registry.get_all())
    assert initial_count == 3

    # Simulate newly installed model in Ollama daemon
    adapter.tags.append({
        "name": "deepseek-r1:7b",
        "size": 7 * 1024**3,
        "details": {"family": "deepseek"},
    })

    refreshed = registry.refresh_discovery()
    assert len(refreshed) == 4
    assert any(m.ollama_name == "deepseek-r1:7b" for m in refreshed)


# ─────────────────────────────────────────────────────────────
# Test K: Manual override survives registry refresh
# ─────────────────────────────────────────────────────────────
def test_k_override_survives_refresh():
    adapter = MockOllamaAdapter()
    discovery = ModelDiscoveryService(adapter=adapter)
    registry = ModelRegistry(discovery_service=discovery)

    registry.update_capability_override("qwen2.5-coder:3b", {"coding": 0.99, "mathematics": 0.97})
    m = registry.get_by_name("qwen2.5-coder:3b")
    assert m.capabilities.coding == 0.99

    # Re-scan Ollama
    registry.refresh_discovery()
    m2 = registry.get_by_name("qwen2.5-coder:3b")
    assert m2.capabilities.coding == 0.99
    assert m2.capabilities.mathematics == 0.97


# ─────────────────────────────────────────────────────────────
# Test L: Stable model IDs remain deterministic
# ─────────────────────────────────────────────────────────────
def test_l_stable_model_ids():
    adapter = MockOllamaAdapter()
    discovery1 = ModelDiscoveryService(adapter=adapter)
    reg1 = ModelRegistry(discovery_service=discovery1)
    id1 = reg1.get_by_name("qwen2.5-coder:3b").id

    discovery2 = ModelDiscoveryService(adapter=adapter)
    reg2 = ModelRegistry(discovery_service=discovery2)
    id2 = reg2.get_by_name("qwen2.5-coder:3b").id

    assert id1 == id2
    assert id1.startswith("model-")


# ─────────────────────────────────────────────────────────────
# Test M: Audit correctness - never false claims
# ─────────────────────────────────────────────────────────────
def test_m_audit_correctness_and_no_fabrication():
    adapter = MockOllamaAdapter()
    discovery = ModelDiscoveryService(adapter=adapter)
    registry = ModelRegistry(discovery_service=discovery)
    orchestrator = ExecutionOrchestrator(adapter=adapter, fallback_manager=FallbackManager(adapter, registry))

    # Single-pass visual task (medium risk)
    plan = ExecutionPlan(
        request_id="req-audit-test",
        risk=RiskLevel.MEDIUM,
        primary_model=ModelRoleAssignment(
            model_id="m-vl",
            ollama_name="qwen2.5vl:3b",
            role="primary",
            architecture="qwen25vl",
        ),
        verifier_model=None,
        verification_spec=VerificationSpec(
            cross_model="NOT_REQUIRED",
            evidence="REQUIRED",
            deterministic="NOT_REQUIRED",
            contradiction_check="REQUIRED",
        ),
        vision_required=True,
    )

    result = orchestrator.execute_plan(plan, "Inspect P&ID blueprint", images=["base64_img_data"])

    # 1. Verification Report integrity
    verif = result["verification_report"]
    assert verif["cross_model_status"] == "NOT_REQUIRED"
    assert verif["deterministic_status"] == "NOT_REQUIRED"
    assert verif["evidence_status"] == "SUPPORTED"
    assert verif["model_agreement"] == "NOT_APPLICABLE"
    assert verif["verification_independence"] == "NOT_APPLICABLE"
    assert "cross-model and deterministic verification were not required" in verif["notes"].lower()

    # 2. Confidence Assessment integrity
    conf = result["confidence_assessment"]
    assert conf["deterministic_pass"] is None
    assert conf["model_agreement"] == "NOT_APPLICABLE"
    assert conf["confidence_score"] > 0.70

    # 3. Ollama call accounting vs tool invocations
    assert len(result["ollama_calls"]) == 1
    assert result["ollama_calls"][0]["model"] == "qwen2.5vl:3b"
    assert result["ollama_calls"][0]["role"] == "primary"
    assert "vision_multimodal_extractor" in result["tools_invoked"]

    # 4. Sanitized Audit Trail record check
    trace = orchestrator.audit_trail.get_trace_by_id("req-audit-test")
    assert trace is not None
    assert "base64_img_data" not in str(trace)  # No raw image payload persisted
    assert "Inspect P&ID blueprint" not in str(trace["primary_execution"])  # Prompt sanitized
    assert trace["sovereignty"]["air_gap_active"] is True
    assert trace["sovereignty"]["internet_dependency"] == "NONE"
    assert trace["sovereignty"]["data_leaves_machine"] is False
