import pytest
import time
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
from backend.models.execution_plan import (
    ExecutionPlan,
    ModelRoleAssignment,
    VerificationSpec,
    ExecutionStrategy,
)
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
from backend.telemetry.audit import AuditTrail


class MockOllamaAdapter:
    def __init__(self, host="http://127.0.0.1:11434"):
        self.host = host
        self.calls = []
        self.tags = [
            {"name": "qwen2.5-coder:3b", "size": 3 * 1024**3, "details": {"family": "qwen2"}},
            {"name": "qwen3:4b", "size": 4 * 1024**3, "details": {"family": "qwen3"}},
            {"name": "qwen2.5vl:3b", "size": 4 * 1024**3, "details": {"family": "qwen25vl"}},
        ]
        self.fail_models = set()
        self.responses = {}

    def check_health(self):
        return {"reachable": True, "status": "healthy"}

    def list_tags(self):
        return self.tags

    def show_model(self, name):
        return {"details": {"family": "qwen2" if "coder" in name else "qwen3" if "qwen3" in name else "qwen25vl"}}

    def generate(self, model, prompt, system=None, images=None, options=None):
        self.calls.append({"model": model, "prompt": prompt, "images": bool(images)})
        if model in self.fail_models or "fail" in model:
            return {"success": False, "error": f"Model {model} simulated failure", "latency_ms": 50.0}

        if model in self.responses:
            resp = self.responses[model]
        elif "corrosion" in prompt.lower() and "calculate" in prompt.lower():
            resp = "The calculated corrosion rate is 0.30 mm/year with 15.0 years remaining life."
        elif "p-101" in prompt.lower() and "v-101" in prompt.lower():
            resp = "P-101 is connected to Valve V-101 on the discharge line."
        else:
            resp = "Technical analysis completed with verified parameters."

        return {
            "success": True,
            "model": model,
            "response": resp,
            "latency_ms": 110.0,
        }


def build_test_orchestrator(adapter=None):
    adp = adapter or MockOllamaAdapter()
    discovery = ModelDiscoveryService(adapter=adp)
    registry = ModelRegistry(discovery_service=discovery)
    fallback = FallbackManager(adapter=adp, registry=registry)
    verification = VerificationEngine()
    confidence = ConfidenceEngine()
    audit = AuditTrail()
    return ExecutionOrchestrator(
        adapter=adp,
        fallback_manager=fallback,
        verification_engine=verification,
        confidence_engine=confidence,
        audit_trail=audit,
    ), adp, registry


# ─────────────────────────────────────────────────────────────
# TEST 1: LOW risk → exactly one model execution
# ─────────────────────────────────────────────────────────────
def test_1_low_risk_single_model_execution():
    orchestrator, adapter, registry = build_test_orchestrator()
    plan = ExecutionPlan(
        request_id="test-req-low",
        task_id="task-1",
        risk=RiskLevel.LOW,
        strategy=ExecutionStrategy.SINGLE_PASS_DIRECT,
        primary_model=ModelRoleAssignment(
            model_id="model-qwen3",
            ollama_name="qwen3:4b",
            display_name="Qwen 3 4B",
            role="primary",
        ),
        verifier_model=None,
        verification_spec=VerificationSpec(cross_model="NOT_REQUIRED", deterministic="NOT_REQUIRED"),
    )

    result = orchestrator.execute_plan(plan, prompt="Summarize this turnaround safety memo.")

    assert result["success"] is True
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["model"] == "qwen3:4b"
    assert result["verification_report"]["cross_model_status"] == "NOT_REQUIRED"
    assert result["verification_report"]["status"] == "NOT_REQUIRED"


# ─────────────────────────────────────────────────────────────
# TEST 2: HIGH risk → two model executions (Primary + Verifier)
# ─────────────────────────────────────────────────────────────
def test_2_high_risk_dual_model_execution():
    orchestrator, adapter, registry = build_test_orchestrator()
    plan = ExecutionPlan(
        request_id="test-req-high",
        task_id="task-2",
        risk=RiskLevel.HIGH,
        strategy=ExecutionStrategy.MULTI_MODEL_CROSS_VERIFICATION,
        primary_model=ModelRoleAssignment(
            model_id="model-qwen3",
            ollama_name="qwen3:4b",
            display_name="Qwen 3 4B",
            role="primary",
        ),
        verifier_model=ModelRoleAssignment(
            model_id="model-coder",
            ollama_name="qwen2.5-coder:3b",
            display_name="Qwen 2.5 Coder 3B",
            role="independent_verifier",
        ),
        verification_independence="HIGHER",
        verification_spec=VerificationSpec(cross_model="REQUIRED", deterministic="NOT_REQUIRED"),
        human_approval_required=True,
    )

    result = orchestrator.execute_plan(plan, prompt="Evaluate continued pump operation.")

    assert result["success"] is True
    assert len(adapter.calls) == 2
    executed_models = [c["model"] for c in adapter.calls]
    assert "qwen3:4b" in executed_models
    assert "qwen2.5-coder:3b" in executed_models
    assert result["verifier_execution"] is not None
    assert result["verifier_execution"]["verifier_model"] == "qwen2.5-coder:3b"


# ─────────────────────────────────────────────────────────────
# TEST 3: HIGH risk + different model family → verification_independence = different_family / HIGHER
# ─────────────────────────────────────────────────────────────
def test_3_high_risk_different_family_independence():
    _, _, registry = build_test_orchestrator()
    planner = ExecutionPlanner(registry=registry)
    task = TaskProfile(
        task_type=TaskType.EQUIPMENT_APPROVAL,
        intent="pump_approval",
        risk=RiskLevel.HIGH,
        requires_verification=True,
    )
    decision = RoutingDecision(
        request_id="req-indep-1",
        task=task,
        selected_models=[
            SelectedModelRole(model_id="m1", ollama_name="qwen3:4b", role="primary", display_name="Reasoner"),
            SelectedModelRole(model_id="m2", ollama_name="qwen2.5-coder:3b", role="independent_verifier", display_name="Coder"),
        ],
        verification_required=True,
        candidates=[
            CandidateEvaluation(model_id="m1", ollama_name="qwen3:4b", score=0.95, eligible=True, subscores=CandidateSubscores()),
            CandidateEvaluation(model_id="m2", ollama_name="qwen2.5-coder:3b", score=0.88, eligible=True, subscores=CandidateSubscores()),
        ],
    )
    plan = planner.create_execution_plan(task, decision)

    assert plan.verification_independence == "HIGHER"
    assert plan.verifier_model.ollama_name == "qwen2.5-coder:3b"


# ─────────────────────────────────────────────────────────────
# TEST 4: HIGH risk + no different family → verification_independence = limited
# ─────────────────────────────────────────────────────────────
def test_4_high_risk_same_family_limited_independence():
    _, _, registry = build_test_orchestrator()
    planner = ExecutionPlanner(registry=registry)
    task = TaskProfile(
        task_type=TaskType.EQUIPMENT_APPROVAL,
        intent="pump_approval",
        risk=RiskLevel.HIGH,
        requires_verification=True,
    )
    # Primary and verifier from same family (e.g. qwen2 / qwen2)
    decision = RoutingDecision(
        request_id="req-indep-2",
        task=task,
        selected_models=[
            SelectedModelRole(model_id="m1", ollama_name="qwen2.5-coder:3b", role="primary", display_name="Coder"),
            SelectedModelRole(model_id="m2", ollama_name="qwen2.5-coder:3b", role="independent_verifier", display_name="Coder 2"),
        ],
        verification_required=True,
        candidates=[
            CandidateEvaluation(model_id="m1", ollama_name="qwen2.5-coder:3b", score=0.92, eligible=True, subscores=CandidateSubscores()),
        ],
    )
    plan = planner.create_execution_plan(task, decision)

    assert plan.verification_independence == "LIMITED"


# ─────────────────────────────────────────────────────────────
# TEST 5: Primary and verifier agree → SUPPORTED
# ─────────────────────────────────────────────────────────────
def test_5_primary_and_verifier_agree_supported():
    orchestrator, adapter, _ = build_test_orchestrator()
    adapter.responses = {
        "qwen3:4b": "P-101 connects to Valve V-101 on the crude feed line. Both isolation valves are operational.",
        "qwen2.5-coder:3b": "P-101 connects to Valve V-101 on the crude feed line. Isolation valves verified.",
    }
    plan = ExecutionPlan(
        request_id="test-agree",
        task_id="task-5",
        risk=RiskLevel.HIGH,
        strategy=ExecutionStrategy.MULTI_MODEL_CROSS_VERIFICATION,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen3:4b", role="primary"),
        verifier_model=ModelRoleAssignment(model_id="m2", ollama_name="qwen2.5-coder:3b", role="independent_verifier"),
        verification_independence="HIGHER",
        verification_spec=VerificationSpec(cross_model="REQUIRED"),
    )

    result = orchestrator.execute_plan(plan, prompt="Identify connections for P-101.")

    verif = result["verification_report"]
    assert verif["status"] == "SUPPORTED"
    assert verif["cross_model_status"] == "PASSED"
    assert verif["model_agreement"] == "AGREED"
    assert len(verif["contradictions"]) == 0


# ─────────────────────────────────────────────────────────────
# TEST 6: Primary and verifier disagree → CONFLICT / CONTRADICTED
# ─────────────────────────────────────────────────────────────
def test_6_primary_and_verifier_disagree_conflict():
    orchestrator, adapter, _ = build_test_orchestrator()
    adapter.responses = {
        "qwen3:4b": "Pump P-101 vibration is 7.4 mm/s RMS. Safe to approve for continued operation.",
        "qwen2.5-coder:3b": "Pump P-101 vibration exceeds 7.1 mm/s ISO limit. Cannot be approved for operation.",
    }
    plan = ExecutionPlan(
        request_id="test-conflict",
        task_id="task-6",
        risk=RiskLevel.HIGH,
        strategy=ExecutionStrategy.MULTI_MODEL_CROSS_VERIFICATION,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen3:4b", role="primary"),
        verifier_model=ModelRoleAssignment(model_id="m2", ollama_name="qwen2.5-coder:3b", role="independent_verifier"),
        verification_independence="HIGHER",
        verification_spec=VerificationSpec(cross_model="REQUIRED"),
        human_approval_required=True,
    )

    result = orchestrator.execute_plan(plan, prompt="Should P-101 be approved for continued operation with 7.4 mm/s vibration?")

    verif = result["verification_report"]
    assert verif["status"] == "CONTRADICTED"
    assert verif["human_review_required"] is True
    assert len(verif["contradictions"]) > 0


# ─────────────────────────────────────────────────────────────
# TEST 7: Primary fails → fallback to next eligible model
# ─────────────────────────────────────────────────────────────
def test_7_primary_fails_fallback():
    orchestrator, adapter, _ = build_test_orchestrator()
    adapter.fail_models.add("qwen3:4b")
    plan = ExecutionPlan(
        request_id="test-fallback",
        task_id="task-7",
        risk=RiskLevel.LOW,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen3:4b", role="primary"),
        fallback_models=["qwen2.5-coder:3b"],
        verification_spec=VerificationSpec(cross_model="NOT_REQUIRED", deterministic="NOT_REQUIRED"),
    )

    result = orchestrator.execute_plan(plan, prompt="Write Python helper.")

    assert result["success"] is True
    assert result["primary_execution"]["is_fallback"] is True
    assert result["primary_execution"]["model"] == "qwen2.5-coder:3b"


# ─────────────────────────────────────────────────────────────
# TEST 8: Verifier fails → verification status = VERIFICATION_FAILED
# ─────────────────────────────────────────────────────────────
def test_8_verifier_fails_verification_failed():
    orchestrator, adapter, _ = build_test_orchestrator()
    adapter.fail_models.add("qwen2.5-coder:3b")
    plan = ExecutionPlan(
        request_id="test-vfail",
        task_id="task-8",
        risk=RiskLevel.HIGH,
        strategy=ExecutionStrategy.MULTI_MODEL_CROSS_VERIFICATION,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen3:4b", role="primary"),
        verifier_model=ModelRoleAssignment(model_id="m2", ollama_name="qwen2.5-coder:3b", role="independent_verifier"),
        verification_independence="HIGHER",
        verification_spec=VerificationSpec(cross_model="REQUIRED"),
        human_approval_required=True,
    )

    result = orchestrator.execute_plan(plan, prompt="Review pump maintenance log.")

    verif = result["verification_report"]
    assert verif["status"] == "VERIFICATION_FAILED"
    assert verif["cross_model_status"] == "FAILED"
    assert "failed" in verif["notes"].lower()


# ─────────────────────────────────────────────────────────────
# TEST 9: P&ID conflicting extracted relationships → CONFLICT
# ─────────────────────────────────────────────────────────────
def test_9_pid_conflicting_flow_paths_conflict():
    orchestrator, adapter, _ = build_test_orchestrator()
    adapter.responses = {
        "qwen2.5vl:3b": "P-101 -> V-101 -> Tank T-101. Valve V-101 is open.",
        "qwen3:4b": "P-101 -> V-102 -> Tank T-101. Valve V-101 is closed.",
    }
    plan = ExecutionPlan(
        request_id="test-pid-conflict",
        task_id="task-9",
        risk=RiskLevel.HIGH,
        strategy=ExecutionStrategy.MULTI_MODEL_CROSS_VERIFICATION,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen2.5vl:3b", role="primary"),
        verifier_model=ModelRoleAssignment(model_id="m2", ollama_name="qwen3:4b", role="independent_verifier"),
        verification_independence="HIGHER",
        verification_spec=VerificationSpec(cross_model="REQUIRED"),
        vision_required=True,
    )

    result = orchestrator.execute_plan(plan, prompt="Analyze this P&ID and trace flow path from P-101.", images=["fakebase64"])

    verif = result["verification_report"]
    assert verif["status"] == "CONTRADICTED"
    assert verif["human_review_required"] is True
    assert any("flow path" in c.lower() or "v-101" in c.lower() for c in verif["contradictions"])


# ─────────────────────────────────────────────────────────────
# TEST 10: Calculation disagreement with deterministic calculator → CONFLICT
# ─────────────────────────────────────────────────────────────
def test_10_calculation_disagreement_with_deterministic_tool():
    orchestrator, adapter, _ = build_test_orchestrator()
    # Prompt has initial 5.0 mm, final 3.8 mm, interval 4 years -> Expected = (5.0 - 3.8)/4 = 0.30 mm/year
    # Model hallucinated 0.27 mm/year
    adapter.responses = {
        "qwen2.5-coder:3b": "The calculated corrosion rate is 0.27 mm/year based on ultrasonic thickness survey.",
    }
    plan = ExecutionPlan(
        request_id="test-calc-conflict",
        task_id="task-10",
        risk=RiskLevel.MEDIUM,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen2.5-coder:3b", role="primary"),
        verification_spec=VerificationSpec(deterministic_required=True),
    )

    prompt = "Calculate corrosion rate when original thickness is 5.0 mm, current thickness is 3.8 mm, and interval is 4.0 years."
    result = orchestrator.execute_plan(plan, prompt=prompt)

    verif = result["verification_report"]
    assert verif["status"] == "CONTRADICTED"
    assert verif["deterministic_status"] == "CONFLICT"
    assert verif["deterministic"]["match"] is False
    assert "Expected 0.3 mm/year" in verif["deterministic"]["discrepancy"]
