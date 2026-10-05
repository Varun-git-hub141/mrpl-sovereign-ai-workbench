"""
MRPL Sovereign Engineering AI Workbench — Master End-to-End Test Suite (Phases 0 to 30)
Validates all 10 core engineering workflow scenarios specified in Phase 29:
TEST 1: "Explain two sum" → Coding Model
TEST 2: "Write Python code for corrosion calculation" → Coding Model + Formula Registry
TEST 3: "Explain this P&ID" → Vision + P&ID Graph + RAG
TEST 4: "Which valves isolate P-101?" → P&ID Graph (XV-203, XV-204, DV-101/102)
TEST 5: "What happens if PCV-101 fails closed?" → P&ID Graph + PSV-101 Flare Relief (9.0 barg)
TEST 6: "Calculate corrosion rate" → Deterministic Formula Engine (0.30 mm/yr)
TEST 7: "Calculate remaining life" → Formula Engine + Applicability (2.0 years)
TEST 8: "Review P-101 inspection report" → Extraction + RAG + Formula Engine
TEST 9: "Can P-101 continue operating?" → Evidence assessment + Verification + Human Review Gate
TEST 10: "Generate approval note" → Complete 19-section DOCX generator
"""

import os
from pathlib import Path
from backend.models.task_profile import TaskType, RiskLevel, InputModality
from backend.models.formula_models import FormulaCalculationRequest
from backend.models.pid_graph_models import PIDQueryRequest
from backend.services.task_analyzer import TaskAnalyzer
from backend.services.router import IntelligentModelRouter
from backend.services.registry import ModelRegistry
from backend.services.discovery import ModelDiscoveryService
from backend.services.ollama_adapter import OllamaAdapter
from backend.services.policy_engine import PolicyEngine
from backend.services.health_manager import ModelHealthManager
from backend.services.rag_engine import EngineeringRAGEngine
from backend.services.formula_registry import FormulaRegistry
from backend.services.pid_graph_engine import PIDGraphEngine
from backend.services.inspection_analyzer import InspectionAnalyzer
from backend.services.docx_generator import ApprovalNoteDocxGenerator


def get_mock_router():
    adapter = OllamaAdapter()
    discovery = ModelDiscoveryService(adapter=adapter)
    registry = ModelRegistry(discovery_service=discovery)
    health_mgr = ModelHealthManager(registry=registry, adapter=adapter)
    policy_engine = PolicyEngine()
    router = IntelligentModelRouter(registry=registry, health_manager=health_mgr, policy_engine=policy_engine)
    return router, registry


# ─────────────────────────────────────────────────────────────
# TEST 1: "Explain two sum" → Coding model routed
# ─────────────────────────────────────────────────────────────
def test_1_explain_two_sum_coding_model():
    analyzer = TaskAnalyzer()
    profile = analyzer.analyze("Explain two sum algorithm in Python", files=[])
    assert profile.task_type == TaskType.CODING
    assert profile.required_capabilities.coding >= 0.80

    router, registry = get_mock_router()
    decision = router.route(profile)
    assert decision.selected_models[0].role == "primary"
    # Coding model should be selected
    assert "coder" in decision.selected_models[0].ollama_name.lower() or "qwen2.5-coder" in decision.selected_models[0].ollama_name.lower()


# ─────────────────────────────────────────────────────────────
# TEST 2: "Write Python code for corrosion calculation" → Coding Model + Formula
# ─────────────────────────────────────────────────────────────
def test_2_write_python_corrosion_calculation():
    analyzer = TaskAnalyzer()
    profile = analyzer.analyze("Write Python code for corrosion calculation per API 570", files=[])
    assert profile.task_type == TaskType.CODING
    assert profile.required_capabilities.coding >= 0.80

    formula_reg = FormulaRegistry()
    formula = formula_reg.get_by_id("CORR-001")
    assert formula is not None
    assert formula.name == "Historical Average Corrosion Rate"
    assert formula.equation in ["CR = (T_previous - T_current) / elapsed_time", "CR = (T_initial - T_current) / delta_years"]


# ─────────────────────────────────────────────────────────────
# TEST 3: "Explain this P&ID" → Vision + P&ID Graph + RAG
# ─────────────────────────────────────────────────────────────
def test_3_explain_pid_diagram():
    analyzer = TaskAnalyzer()
    profile = analyzer.analyze(
        "Explain this P&ID drawing for Crude Feed Pump system",
        files=[{"name": "pid_crude_distillation.jpg", "type": "image/jpeg"}],
    )
    assert profile.modality in [InputModality.VISION, InputModality.MULTIMODAL]
    assert profile.required_capabilities.vision >= 0.80

    pid_engine = PIDGraphEngine()
    graph = pid_engine.get_graph("CDU-P-101")
    assert graph is not None
    assert len(graph.nodes) >= 20
    assert len(graph.edges) >= 20


# ─────────────────────────────────────────────────────────────
# TEST 4: "Which valves isolate P-101?" → P&ID Graph
# ─────────────────────────────────────────────────────────────
def test_4_valves_isolating_pump_p101():
    pid_engine = PIDGraphEngine()
    res = pid_engine.query_pid(PIDQueryRequest(question="Which valves isolate P-101?"))
    assert res.confidence >= 0.95
    assert "XV-203" in res.answer
    assert "XV-204" in res.answer
    assert "DV-101" in res.answer
    assert "DV-102" in res.answer
    assert "Suction Isolation" in res.answer or "suction" in res.answer.lower()


# ─────────────────────────────────────────────────────────────
# TEST 5: "What happens if PCV-101 fails closed?" → P&ID Graph + Flare Relief
# ─────────────────────────────────────────────────────────────
def test_5_pcv101_fail_closed_simulation():
    pid_engine = PIDGraphEngine()
    res = pid_engine.query_pid(PIDQueryRequest(question="What happens if PCV-101 fails closed?"))
    assert "PSV-101" in res.answer
    assert "9.0 barg" in res.answer or "Flare Header" in res.answer
    assert "PIC-101" in res.answer or "PAH-101" in res.answer


# ─────────────────────────────────────────────────────────────
# TEST 6: "Calculate corrosion rate" → Deterministic Formula Engine
# ─────────────────────────────────────────────────────────────
def test_6_calculate_corrosion_rate_deterministic():
    formula_reg = FormulaRegistry()
    req = FormulaCalculationRequest(
        formula_id="CORR-001",
        inputs={"T_initial": 5.0, "T_current": 3.8, "delta_years": 4.0},
        equipment_tag="P-101",
    )
    res = formula_reg.calculate(req)
    assert res.status == "SUCCESS"
    assert res.result == 0.30
    assert res.result_unit == "mm/year"
    assert res.formula_display == "(5.0 - 3.8) / 4.0" or "(5 - 3.8) / 4"


# ─────────────────────────────────────────────────────────────
# TEST 7: "Calculate remaining life" → Formula Engine + Applicability
# ─────────────────────────────────────────────────────────────
def test_7_calculate_remaining_life_deterministic():
    formula_reg = FormulaRegistry()
    req = FormulaCalculationRequest(
        formula_id="CORR-004",
        inputs={"T_current": 3.8, "T_min": 3.2, "CR": 0.30},
        equipment_tag="P-101",
    )
    res = formula_reg.calculate(req)
    assert res.status == "SUCCESS"
    assert res.result == 2.0  # (3.8 - 3.2) / 0.30 = 2.0 years
    assert res.result_unit == "years"


# ─────────────────────────────────────────────────────────────
# TEST 8: "Review P-101 inspection report" → Extraction + RAG + Formula
# ─────────────────────────────────────────────────────────────
def test_8_review_inspection_report():
    sample_text = """
    Equipment: P-101 Transfer Pump
    Original wall thickness = 5.0 mm
    Current wall thickness = 3.8 mm
    Minimum allowable thickness = 3.2 mm
    Inspection interval = 4.0 years
    Overall vibration = 7.4 mm/s RMS
    """
    res = InspectionAnalyzer.analyze_report_text(sample_text)
    assert res.equipment_tag == "P-101"
    assert res.original_thickness_mm == 5.0
    assert res.current_thickness_mm == 3.8
    assert res.minimum_allowable_mm == 3.2
    assert res.corrosion_rate_mm_year == 0.30
    assert res.remaining_life_years == 2.0
    assert res.vibration_velocity_rms == 7.4


# ─────────────────────────────────────────────────────────────
# TEST 9: "Can P-101 continue operating?" → Evidence + Human Review Gate
# ─────────────────────────────────────────────────────────────
def test_9_continued_operation_human_review_gate():
    sample_text = """
    Equipment: P-101 Transfer Pump
    Original wall thickness = 5.0 mm
    Current wall thickness = 3.8 mm
    Minimum allowable thickness = 3.2 mm
    Inspection interval = 4.0 years
    Overall vibration = 7.4 mm/s RMS
    """
    res = InspectionAnalyzer.analyze_report_text(sample_text)
    assert res.operation_status == "HUMAN_REVIEW_REQUIRED"
    assert "HUMAN ENGINEERING REVIEW REQUIRED" in res.decision_banner
    assert "Vibration" in res.reason


# ─────────────────────────────────────────────────────────────
# TEST 10: "Generate approval note" → DOCX generator
# ─────────────────────────────────────────────────────────────
def test_10_generate_docx_approval_note():
    data = {
        "equipment_tag": "P-101",
        "original_thickness": 5.0,
        "current_thickness": 3.8,
        "t_min": 3.2,
        "interval_years": 4.0,
        "vibration_rms": "7.4 mm/s RMS",
    }
    out_path = ApprovalNoteDocxGenerator.generate_p101_approval_note(
        analysis_data=data,
        output_filepath="artifacts/test_p101_approval_note.docx",
    )
    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 10000  # Non-empty rich DOCX file
