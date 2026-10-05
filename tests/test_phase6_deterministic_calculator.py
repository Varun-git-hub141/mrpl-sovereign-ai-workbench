"""
Phase 6 — Deterministic Calculation Integration Tests
Verifies:
1. Connecting extracted evidence to local deterministic Python calculation tool
2. Strict non-LLM local deterministic arithmetic execution
3. Structured calculation result payload with inputs, units, formula, result
4. Comparison of primary model output against deterministic calculation (SUPPORTED vs CONTRADICTED)
5. Unit handling, validation, and conversion (mm, cm, m)
6. Missing data handling (INSUFFICIENT_DATA status)
7. Distinguishing calculation types: historical wall-loss rate vs remaining life
8. Auditable verification trace generation
9. Preserving high-risk human engineering review gate
"""

import base64
from pathlib import Path
from backend.models.task_profile import RiskLevel
from backend.models.verification_result import (
    DeterministicStatus,
    VerificationStatus,
    DeterministicCheckResult,
)
from backend.services.deterministic_calculator import DeterministicCalculator
from backend.services.verification_engine import VerificationEngine
from backend.services.context_builder import RequestContextBuilder
from backend.services.multimodal_processor import MultimodalFileProcessor
from backend.services.human_approval import HumanApprovalManager, HumanApprovalState


def test_1_deterministic_calculation_from_pdf_evidence():
    evidence = {
        "equipment": "P-101 Transfer Pump",
        "original_thickness": {"value": 5.0, "value_mm": 5.0, "unit": "mm"},
        "current_thickness": {"value": 3.8, "value_mm": 3.8, "unit": "mm"},
        "minimum_allowable_thickness": {"value": 3.2, "value_mm": 3.2, "unit": "mm"},
        "inspection_interval": {"value": 4.0, "value_years": 4.0, "unit": "years"},
    }

    calc_res = DeterministicCalculator.calculate_historical_wall_loss_rate(evidence)

    assert calc_res["status"] == "SUCCESS"
    assert calc_res["calculation_type"] == "historical_wall_loss_rate"
    assert calc_res["formula"] == "(original_thickness - current_thickness) / inspection_interval"
    assert calc_res["inputs"]["original_thickness"] == 5.0
    assert calc_res["inputs"]["current_thickness"] == 3.8
    assert calc_res["inputs"]["inspection_interval"] == 4.0
    assert calc_res["units"]["result"] == "mm/year"
    assert calc_res["result"] == 0.30
    assert calc_res["source"] == "deterministic_calculator"


def test_2_model_comparison_supported_vs_contradicted():
    evidence = {
        "original_thickness": {"value": 5.0, "value_mm": 5.0, "unit": "mm"},
        "current_thickness": {"value": 3.8, "value_mm": 3.8, "unit": "mm"},
        "inspection_interval": {"value": 4.0, "value_years": 4.0, "unit": "years"},
    }
    calc_res = DeterministicCalculator.calculate_historical_wall_loss_rate(evidence)
    assert calc_res["result"] == 0.30

    # Scenario A: Model says 0.30 mm/year -> SUPPORTED
    primary_supported = "The calculated corrosion rate for pump casing is 0.30 mm/year."
    det_check, conflict, rate, vals, discrepancy = DeterministicCalculator.compare_with_model_output(
        calc_result=calc_res,
        primary_response=primary_supported,
    )
    assert det_check == "SUPPORTED"
    assert conflict is False
    assert rate == 0.30
    assert discrepancy is None

    # Scenario B: Model says 0.27 mm/year -> CONTRADICTED + conflict
    primary_contradicted = "The calculated corrosion rate for pump casing is 0.27 mm/year."
    det_check, conflict, rate, vals, discrepancy = DeterministicCalculator.compare_with_model_output(
        calc_result=calc_res,
        primary_response=primary_contradicted,
    )
    assert det_check == "CONTRADICTED"
    assert conflict is True
    assert rate == 0.27
    assert "Expected 0.3 mm/year" in discrepancy or "Expected 0.30 mm/year" in discrepancy
    assert "primary model stated 0.27 mm/year" in discrepancy


def test_3_unit_validation_and_conversion():
    # 1. Centimeters conversion to mm
    ev_cm = {
        "original_thickness": {"value": 0.5, "value_mm": 5.0, "unit": "cm"},
        "current_thickness": {"value": 0.38, "value_mm": 3.8, "unit": "cm"},
        "inspection_interval": {"value": 4.0, "value_years": 4.0, "unit": "years"},
    }
    calc_cm = DeterministicCalculator.calculate_historical_wall_loss_rate(ev_cm)
    assert calc_cm["status"] == "SUCCESS"
    assert calc_cm["result"] == 0.30

    # 2. Incompatible unit rejection
    ev_bad = {
        "original_thickness": {"value": 5.0, "value_mm": 5.0, "unit": "bar"},
        "current_thickness": {"value": 3.8, "value_mm": 3.8, "unit": "bar"},
        "inspection_interval": {"value": 4.0, "value_years": 4.0, "unit": "years"},
    }
    calc_bad = DeterministicCalculator.calculate_historical_wall_loss_rate(ev_bad)
    assert calc_bad["status"] == "INCOMPATIBLE_UNITS"


def test_4_missing_data_insufficient_data():
    ev_missing = {
        "original_thickness": {"value": 5.0, "value_mm": 5.0, "unit": "mm"},
        "current_thickness": {"value": 3.8, "value_mm": 3.8, "unit": "mm"},
        "inspection_interval": None,
    }
    calc_missing = DeterministicCalculator.calculate_historical_wall_loss_rate(ev_missing)
    assert calc_missing["status"] == "INSUFFICIENT_DATA"
    assert "inspection_interval" in calc_missing["missing_inputs"]


def test_5_distinguish_wall_loss_vs_remaining_life():
    ev = {
        "original_thickness": {"value": 5.0, "value_mm": 5.0, "unit": "mm"},
        "current_thickness": {"value": 3.8, "value_mm": 3.8, "unit": "mm"},
        "minimum_allowable_thickness": {"value": 3.2, "value_mm": 3.2, "unit": "mm"},
        "inspection_interval": {"value": 4.0, "value_years": 4.0, "unit": "years"},
    }
    # 1. Historical wall loss rate
    rate_res = DeterministicCalculator.calculate_historical_wall_loss_rate(ev)
    assert rate_res["calculation_type"] == "historical_wall_loss_rate"
    assert rate_res["result"] == 0.30

    # 2. Remaining life calculation
    life_res = DeterministicCalculator.calculate_remaining_life(ev, corrosion_rate=rate_res["result"])
    assert life_res["calculation_type"] == "remaining_life"
    assert life_res["inputs"]["minimum_allowable_thickness"] == 3.2
    assert life_res["result"] == 2.0  # (3.8 - 3.2) / 0.30 = 2.0 years


def test_6_verification_trace_output():
    evidence = {
        "original_thickness": {"value": 5.0, "value_mm": 5.0, "unit": "mm"},
        "current_thickness": {"value": 3.8, "value_mm": 3.8, "unit": "mm"},
        "inspection_interval": {"value": 4.0, "value_years": 4.0, "unit": "years"},
    }
    calc_res = DeterministicCalculator.calculate_historical_wall_loss_rate(evidence)
    trace = DeterministicCalculator.generate_verification_trace(
        evidence=evidence,
        calc_result=calc_res,
        primary_rate=0.30,
        deterministic_check="SUPPORTED",
        primary_response="Calculated corrosion rate is 0.30 mm/year.",
    )
    assert "EXTRACTED EVIDENCE" in trace
    assert "Original thickness: 5.0 mm" in trace
    assert "Current thickness: 3.8 mm" in trace
    assert "Inspection interval: 4.0 years" in trace
    assert "DETERMINISTIC CALCULATION" in trace
    assert "Result:\n0.30 mm/year" in trace or "Result:\n0.3 mm/year" in trace
    assert "PRIMARY MODEL:\n0.30 mm/year" in trace
    assert "DETERMINISTIC CHECK:\nSUPPORTED" in trace


def test_7_real_pdf_extraction_and_deterministic_verification():
    pdf_path = Path("samples/MRPL_Sovereign_Multimodal_Test_Pack.pdf")
    if not pdf_path.exists():
        return

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    processor = MultimodalFileProcessor()
    doc = processor.process_file(
        name="MRPL_Sovereign_Multimodal_Test_Pack.pdf",
        file_bytes=pdf_bytes,
        query_context="Calculate corrosion rate for P-101",
    )

    p1 = doc.pages[0]
    extracted = DeterministicCalculator.extract_evidence(
        text=p1.extracted_text,
        structured_fields=p1.structured_fields,
    )

    assert extracted["original_thickness"]["value"] == 5.0
    assert extracted["current_thickness"]["value"] == 3.8
    assert extracted["inspection_interval"]["value"] == 4.0

    calc_res = DeterministicCalculator.calculate_historical_wall_loss_rate(extracted)
    assert calc_res["status"] == "SUCCESS"
    assert calc_res["result"] == 0.30

    engine = VerificationEngine()
    class MockModelRole:
        ollama_name = "qwen2.5-coder:3b"
        model_id = "m-coder"
        display_name = "Coder 3B"

    class MockPlan:
        request_id = "req-phase6-test"
        risk = RiskLevel.MEDIUM
        primary_model = MockModelRole()
        verifier_model = None
        verification_independence = "NOT_APPLICABLE"
        human_approval_required = False

        class VerificationSpec:
            cross_model_required = False
            deterministic_required = True
            evidence_required = True
            contradiction_check_required = True

        verification_spec = VerificationSpec()

    # Model reports 0.30 mm/year -> PASSED / SUPPORTED
    report = engine.verify(
        plan=MockPlan(),
        prompt=f"=== EXTRACTED EVIDENCE ===\n{p1.extracted_text}",
        primary_response="The calculated annual corrosion rate is 0.30 mm/year.",
        attached_data={"documents": [doc]},
    )
    assert report.deterministic_status == DeterministicStatus.PASSED
    assert report.deterministic.match is True
    assert report.deterministic.expected_value == 0.30
    assert report.deterministic.deterministic_check == "SUPPORTED"
    assert "EXTRACTED EVIDENCE" in report.deterministic.verification_trace


def test_8_human_review_gate_maintained_for_high_risk():
    approval_mgr = HumanApprovalManager()
    item = approval_mgr.register_for_review(
        request_id="req-risk-001",
        task_type="equipment_approval",
        risk="high",
        summary="Pump P-101 vibration 7.4 mm/s RMS with calculated corrosion rate 0.30 mm/year.",
    )
    assert item.state == HumanApprovalState.PENDING_REVIEW
    assert approval_mgr.get_item("req-risk-001") is not None
    assert approval_mgr.get_item("req-risk-001").state == HumanApprovalState.PENDING_REVIEW
