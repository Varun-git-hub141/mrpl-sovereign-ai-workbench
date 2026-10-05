"""
Automated Test Suite for Deterministic Engineering Calculation Pipeline (P-201 Test Case)

Pipeline under test:
PDF / Text / OCR extraction
→ Structured Engineering Input Extraction (Canonical Object)
→ Formula File Search (knowledge/engineering_formulas/)
→ Formula Selection (CR-001, CR-005)
→ Input Mapping (T_previous, T_current, elapsed_time)
→ Unit Normalization (mm, years -> mm/year)
→ Deterministic Calculator (Pure Python, Zero LLM Arithmetic)
→ Result (CR = 0.30 mm/year, RL = 3.33 years)
→ Verification & Trace
"""

import pytest
from pathlib import Path
from backend.services.deterministic_calculator import DeterministicCalculator
from backend.services.formula_registry import FormulaRegistry
from backend.models.formula_models import FormulaCalculationRequest


P201_REPORT_TEXT = """
Equipment:
P-201

Previous Wall Thickness:
6.0 mm

Current Wall Thickness:
4.5 mm

Minimum Allowable Thickness:
3.5 mm

Inspection Interval:
5 years
"""


def test_step1_extraction_canonical_object():
    canonical = DeterministicCalculator.extract_canonical_inputs(P201_REPORT_TEXT)

    assert canonical["equipment_tag"] == "P-201"
    
    assert canonical["previous_thickness"] is not None
    assert canonical["previous_thickness"]["value"] == 6.0
    assert canonical["previous_thickness"]["unit"] == "mm"
    assert canonical["previous_thickness"]["source"] == "Page 1"
    assert canonical["previous_thickness"]["verified"] is True

    assert canonical["current_thickness"] is not None
    assert canonical["current_thickness"]["value"] == 4.5
    assert canonical["current_thickness"]["unit"] == "mm"
    assert canonical["current_thickness"]["source"] == "Page 1"
    assert canonical["current_thickness"]["verified"] is True

    assert canonical["minimum_allowable_thickness"] is not None
    assert canonical["minimum_allowable_thickness"]["value"] == 3.5
    assert canonical["minimum_allowable_thickness"]["unit"] == "mm"
    assert canonical["minimum_allowable_thickness"]["source"] == "Page 1"
    assert canonical["minimum_allowable_thickness"]["verified"] is True

    assert canonical["inspection_interval"] is not None
    assert canonical["inspection_interval"]["value"] == 5.0
    assert canonical["inspection_interval"]["unit"] == "years"
    assert canonical["inspection_interval"]["source"] == "Page 1"
    assert canonical["inspection_interval"]["verified"] is True


def test_step2_search_formula_files():
    formula_file = DeterministicCalculator.search_formula_file("CR-001")
    assert formula_file is not None
    assert formula_file["formula_id"] == "CR-001"
    assert any(k in formula_file.get("required_inputs", []) or k in formula_file.get("inputs", []) for k in ["original_thickness", "previous_thickness", "T_previous"])
    assert "output_unit" in formula_file or "output_units" in formula_file
    assert "source_reference" in formula_file or "source" in formula_file


def test_step3_input_mapping():
    canonical = DeterministicCalculator.extract_canonical_inputs(P201_REPORT_TEXT)
    cr_formula_file = DeterministicCalculator.search_formula_file("CR-001")
    mapped_inputs, mapping_text = DeterministicCalculator.map_inputs(canonical, cr_formula_file)

    assert mapped_inputs["T_previous"]["value"] == 6.0
    assert mapped_inputs["T_previous"]["unit"] == "mm"
    assert mapped_inputs["T_previous"]["source"] == "Page 1"

    assert mapped_inputs["T_current"]["value"] == 4.5
    assert mapped_inputs["T_current"]["unit"] == "mm"
    assert mapped_inputs["T_current"]["source"] == "Page 1"

    assert mapped_inputs["elapsed_time"]["value"] == 5.0
    assert mapped_inputs["elapsed_time"]["unit"] == "years"
    assert mapped_inputs["elapsed_time"]["source"] == "Page 1"

    assert "FORMULA INPUT MAPPING" in mapping_text
    assert "T_previous = 6 mm" in mapping_text or "T_previous = 6.0 mm" in mapping_text
    assert "T_current = 4.5 mm" in mapping_text
    assert "elapsed_time = 5 years" in mapping_text or "elapsed_time = 5.0 years" in mapping_text
    assert "Source = Page 1" in mapping_text


def test_step4_deterministic_calculation_cr():
    pipeline_res = DeterministicCalculator.execute_pipeline(P201_REPORT_TEXT)
    assert pipeline_res["status"] == "SUCCESS"
    cr_info = pipeline_res["corrosion_rate"]
    assert cr_info["result"] == 0.30
    assert cr_info["unit"] == "mm/year"
    assert "6" in cr_info["formula_display"] and "4.5" in cr_info["formula_display"]


def test_step5_remaining_life_calculation_rl():
    pipeline_res = DeterministicCalculator.execute_pipeline(P201_REPORT_TEXT)
    assert pipeline_res["status"] == "SUCCESS"
    rl_info = pipeline_res["remaining_life"]
    assert rl_info is not None
    assert rl_info["applicable"] is True
    assert rl_info["result"] == 3.33
    assert rl_info["unit"] == "years"


def test_step5_remaining_life_applicability_rejection():
    # When current thickness is below or equal to minimum allowable thickness
    unfit_report = """
    Equipment: P-201
    Previous Wall Thickness: 6.0 mm
    Current Wall Thickness: 3.2 mm
    Minimum Allowable Thickness: 3.5 mm
    Inspection Interval: 5 years
    """
    pipeline_res = DeterministicCalculator.execute_pipeline(unfit_report)
    assert pipeline_res["status"] == "SUCCESS"
    rl_info = pipeline_res["remaining_life"]
    assert rl_info["applicable"] is False
    assert "retirement condition reached" in rl_info["reason"] or "Current thickness" in rl_info["reason"]


def test_step6_zero_llm_arithmetic():
    # Values originate directly from deterministic Python formula execution
    canonical = DeterministicCalculator.extract_canonical_inputs(P201_REPORT_TEXT)
    cr = (canonical["previous_thickness"]["value"] - canonical["current_thickness"]["value"]) / canonical["inspection_interval"]["value"]
    rl = (canonical["current_thickness"]["value"] - canonical["minimum_allowable_thickness"]["value"]) / cr

    assert round(cr, 2) == 0.30
    assert round(rl, 2) == 3.33


def test_step7_exact_trace_format():
    pipeline_res = DeterministicCalculator.execute_pipeline(P201_REPORT_TEXT)
    trace = pipeline_res["trace"]

    assert "ENGINEERING CALCULATION TRACE" in trace
    assert "[1] DOCUMENT EXTRACTION" in trace
    assert "✓ P-201 identified" in trace
    assert "✓ Previous thickness = 6 mm" in trace or "✓ Previous thickness = 6.0 mm" in trace
    assert "✓ Current thickness = 4.5 mm" in trace
    assert "✓ Minimum allowable = 3.5 mm" in trace
    assert "✓ Inspection interval = 5 years" in trace or "✓ Inspection interval = 5.0 years" in trace

    assert "[2] FORMULA FILE SEARCH" in trace
    assert "✓ Formula found" in trace
    assert "✓ Formula ID = CR-001" in trace

    assert "[3] INPUT MAPPING" in trace
    assert "✓ T_previous = 6 mm" in trace or "✓ T_previous = 6.0 mm" in trace
    assert "✓ T_current = 4.5 mm" in trace
    assert "✓ elapsed_time = 5 years" in trace or "✓ elapsed_time = 5.0 years" in trace

    assert "[4] UNIT VALIDATION" in trace
    assert "✓ mm" in trace
    assert "✓ years" in trace
    assert "✓ output = mm/year" in trace

    assert "[5] DETERMINISTIC CALCULATION" in trace
    assert "(6 - 4.5) / 5" in trace or "(6.0 - 4.5) / 5" in trace

    assert "[6] RESULT" in trace
    assert "Corrosion Rate = 0.30 mm/year" in trace

    assert "[7] REMAINING LIFE" in trace
    assert "(4.5 - 3.5) / 0.30" in trace
    assert "Remaining Life = 3.33 years" in trace

    assert "[8] VERIFICATION" in trace
    assert "✓ Deterministic calculation completed" in trace
    assert "✓ No LLM arithmetic used" in trace


def test_regression_no_null_values_in_formula_engine():
    # Verify that the formula registry and calculator receive non-null values
    canonical = DeterministicCalculator.extract_canonical_inputs(P201_REPORT_TEXT)
    reg = FormulaRegistry()

    # Request via FormulaRegistry using extracted canonical inputs
    req = FormulaCalculationRequest(
        formula_id="CR-001",
        inputs={
            "T_previous": canonical["previous_thickness"]["value"],
            "T_current": canonical["current_thickness"]["value"],
            "elapsed_time": canonical["inspection_interval"]["value"],
        }
    )
    result = reg.calculate(req)
    assert result.status == "SUCCESS"
    assert result.result == 0.30
    assert result.missing_inputs == []


# ═════════════════════════════════════════════════════════════════════════════
# SPECIFIED REGRESSION TESTS (TEST 1 - TEST 6)
# ═════════════════════════════════════════════════════════════════════════════

def test_user_test1_full_calculation():
    """TEST 1: 6.0, 4.5, 5 years -> Expected: CR = 0.30 mm/year, Status = SUCCESS / CALCULATED"""
    res = DeterministicCalculator.execute_pipeline(P201_REPORT_TEXT)
    assert res["status"] == "SUCCESS"
    assert res["corrosion_rate"]["result"] == 0.30
    assert res["corrosion_rate"]["unit"] == "mm/year"


def test_user_test2_previous_thickness_missing():
    """TEST 2: previous thickness missing -> Expected: INPUT_MAPPING_ERROR / INSUFFICIENT_DATA"""
    incomplete_text = """
    Equipment: P-201
    Current Wall Thickness: 4.5 mm
    Minimum Allowable Thickness: 3.5 mm
    Inspection Interval: 5 years
    """
    res = DeterministicCalculator.execute_pipeline(incomplete_text)
    assert res["status"] in ["INPUT_MAPPING_ERROR", "INSUFFICIENT_DATA"]
    assert "previous_thickness" in res["missing_inputs"] or "T_previous" in res["missing_inputs"]


def test_user_test3_current_thickness_missing():
    """TEST 3: current thickness missing -> Expected: INPUT_MAPPING_ERROR / INSUFFICIENT_DATA"""
    incomplete_text = """
    Equipment: P-201
    Previous Wall Thickness: 6.0 mm
    Minimum Allowable Thickness: 3.5 mm
    Inspection Interval: 5 years
    """
    res = DeterministicCalculator.execute_pipeline(incomplete_text)
    assert res["status"] in ["INPUT_MAPPING_ERROR", "INSUFFICIENT_DATA"]
    assert "current_thickness" in res["missing_inputs"] or "T_current" in res["missing_inputs"]


def test_user_test4_inspection_interval_missing():
    """TEST 4: inspection interval missing -> Expected: INPUT_MAPPING_ERROR / INSUFFICIENT_DATA"""
    incomplete_text = """
    Equipment: P-201
    Previous Wall Thickness: 6.0 mm
    Current Wall Thickness: 4.5 mm
    Minimum Allowable Thickness: 3.5 mm
    """
    res = DeterministicCalculator.execute_pipeline(incomplete_text)
    assert res["status"] in ["INPUT_MAPPING_ERROR", "INSUFFICIENT_DATA"]
    assert "inspection_interval" in res["missing_inputs"] or "elapsed_time" in res["missing_inputs"]


def test_user_test5_verified_extraction_no_missing_claims_in_report():
    """
    TEST 5: verified extraction contains all values ->
    Expected: Final report MUST NOT say those values are missing.
    Contradiction checker must flag and sanitize any false missing claims.
    """
    res = DeterministicCalculator.execute_pipeline(P201_REPORT_TEXT)
    final_report = res["final_report"]

    assert "Historical thickness measurements are missing" not in final_report
    assert "Previous thickness is missing" not in final_report
    assert "Current thickness: 4.5 mm — verified from Page 1." in final_report
    assert "Previous thickness: 6 mm — verified from Page 1." in final_report or "Previous thickness: 6.0 mm — verified from Page 1." in final_report

    # Test contradiction checker catches and sanitizes a contradictory LLM draft
    flawed_llm_draft = "Based on our analysis, historical thickness measurements for 6.0 mm and 4.5 mm are missing. Therefore evaluation is incomplete."
    canonical = DeterministicCalculator.extract_canonical_inputs(P201_REPORT_TEXT)
    sanitized, contradictions = DeterministicCalculator.check_and_correct_report(flawed_llm_draft, canonical)

    assert len(contradictions) >= 1
    assert "Contradiction Detected" in contradictions[0]
    assert "Historical thickness measurements for 6.0 mm and 4.5 mm are missing" not in sanitized
    assert "Previous and current thickness values required for this calculation are present" in sanitized


def test_user_test6_corrosion_rate_must_never_be_directly_compared_with_min_thickness():
    """
    TEST 6: corrosion rate (0.30 mm/year) must never be directly compared numerically
    with minimum allowable thickness (3.5 mm).
    """
    canonical = DeterministicCalculator.extract_canonical_inputs(P201_REPORT_TEXT)
    flawed_llm_statement = "The thickness change of 0.30 mm/year is within the allowable limit of 3.5 mm."
    
    sanitized, contradictions = DeterministicCalculator.check_and_correct_report(flawed_llm_statement, canonical)
    
    assert len(contradictions) >= 1
    assert "Dimensional Mismatch" in contradictions[0]
    assert "is within the allowable limit" not in sanitized
    assert "Current thickness (4.5 mm) exceeds minimum allowable thickness (3.5 mm) with a thickness margin of 1.0 mm" in sanitized


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 12 EXPLICIT AUTOMATED TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_section12_test1_exact_values():
    """
    TEST 1:
    previous_thickness = 6.0
    current_thickness = 4.5
    inspection_interval = 5.0
    Expected: 0.30 mm/year
    """
    doc = {
        "previous_thickness": {"value": 6.0, "unit": "mm", "source": "Page 1", "verified": True},
        "current_thickness": {"value": 4.5, "unit": "mm", "source": "Page 1", "verified": True},
        "inspection_interval": {"value": 5.0, "unit": "years", "source": "Page 1", "verified": True},
    }
    res = DeterministicCalculator.execute_pipeline(doc)
    assert res["status"] == "SUCCESS"
    assert res["corrosion_rate"]["result"] == 0.30
    assert res["corrosion_rate"]["unit"] == "mm/year"


def test_section12_test2_inspection_interval_missing():
    """
    TEST 2:
    previous_thickness = 6.0
    current_thickness = 4.5
    inspection_interval missing
    Expected: INPUT_MAPPING_ERROR / INSUFFICIENT_DATA
    """
    doc = {
        "previous_thickness": {"value": 6.0, "unit": "mm", "source": "Page 1", "verified": True},
        "current_thickness": {"value": 4.5, "unit": "mm", "source": "Page 1", "verified": True},
    }
    res = DeterministicCalculator.execute_pipeline(doc)
    assert res["status"] in ["INPUT_MAPPING_ERROR", "INSUFFICIENT_DATA"]
    assert "elapsed_time" in res["missing_inputs"] or "inspection_interval" in res["missing_inputs"]
    assert "Available canonical fields" in res["error_message"] or "Missing" in res["error_message"]


def test_section12_test3_units_valid():
    """
    TEST 3:
    previous_thickness = 6.0
    current_thickness = 4.5
    inspection_interval = 5.0
    units valid
    Expected: SUCCESS
    """
    doc = {
        "previous_thickness": {"value": 6.0, "unit": "mm", "source": "Page 1", "verified": True},
        "current_thickness": {"value": 4.5, "unit": "mm", "source": "Page 1", "verified": True},
        "inspection_interval": {"value": 5.0, "unit": "years", "source": "Page 1", "verified": True},
    }
    res = DeterministicCalculator.execute_pipeline(doc)
    assert res["status"] == "SUCCESS"
    assert res["deterministic_status"] == "DETERMINISTIC_SUCCESS"
    assert res["corrosion_rate"]["result"] == 0.30


def test_section12_test4_negative_input_invalid():
    """
    TEST 4:
    previous_thickness = 6.0
    current_thickness = -4.5
    Expected: INVALID_INPUT
    """
    doc = {
        "previous_thickness": {"value": 6.0, "unit": "mm", "source": "Page 1", "verified": True},
        "current_thickness": {"value": -4.5, "unit": "mm", "source": "Page 1", "verified": True},
        "inspection_interval": {"value": 5.0, "unit": "years", "source": "Page 1", "verified": True},
    }
    res = DeterministicCalculator.execute_pipeline(doc)
    assert res["status"] == "INVALID_INPUT"
    assert "Negative value" in res.get("error_message", "") or "Negative value" in res.get("message", "")


def test_section12_test5_llm_contradicted_deterministic_wins():
    """
    TEST 5:
    LLM says 0.27 mm/year
    Deterministic calculator says 0.30 mm/year
    Expected: CONTRADICTED (Deterministic result wins, discrepancy reported)
    """
    from backend.services.verification_engine import VerificationEngine
    from backend.models.execution_plan import ExecutionPlan, ModelRoleAssignment, VerificationSpec, RiskLevel

    engine = VerificationEngine()
    plan = ExecutionPlan(
        request_id="test-calc-conflict-sec12",
        task_id="task-12",
        risk=RiskLevel.MEDIUM,
        primary_model=ModelRoleAssignment(model_id="m1", ollama_name="qwen2.5-coder:3b", role="primary"),
        verification_spec=VerificationSpec(deterministic_required=True),
    )

    prompt = "Calculate corrosion rate when previous thickness is 6.0 mm, current thickness is 4.5 mm, and interval is 5.0 years."
    primary_bad_response = "The calculated corrosion rate is 0.27 mm/year."

    report = engine.verify(plan=plan, prompt=prompt, primary_response=primary_bad_response)
    assert report.deterministic_status.value == "CONFLICT" or report.status.value == "CONTRADICTED"
    assert "0.30" in str(report.deterministic.expected_output) or "0.3" in str(report.deterministic.expected_output)
    assert "0.27" in str(report.deterministic.model_output)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 10 TEST CASES (P-101 & P-201 DUAL VALIDATION)
# ═════════════════════════════════════════════════════════════════════════════

def test_section10_test1_p101_canonical_calculation():
    """
    TEST 1:
    canonical:
    previous_thickness = 5.0
    current_thickness = 3.8
    inspection_interval = 4.0
    formula variables: T_previous, T_current, elapsed_time
    Expected: 0.30 mm/year
    """
    p101_doc = {
        "equipment_tag": "P-101",
        "previous_thickness": {"value": 5.0, "unit": "mm", "source": "Page 1", "verified": True},
        "current_thickness": {"value": 3.8, "unit": "mm", "source": "Page 1", "verified": True},
        "minimum_allowable_thickness": {"value": 3.2, "unit": "mm", "source": "Page 1", "verified": True},
        "inspection_interval": {"value": 4.0, "unit": "years", "source": "Page 1", "verified": True},
    }
    res = DeterministicCalculator.execute_pipeline(p101_doc)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30
    assert res["corrosion_rate"]["result"] == 0.30
    assert res["corrosion_rate"]["unit"] == "mm/year"


def test_section10_test2_p201_canonical_calculation():
    """
    TEST 2:
    canonical:
    previous_thickness = 6.0
    current_thickness = 4.5
    inspection_interval = 5.0
    Expected: 0.30 mm/year
    """
    p201_doc = {
        "equipment_tag": "P-201",
        "previous_thickness": {"value": 6.0, "unit": "mm", "source": "Page 1", "verified": True},
        "current_thickness": {"value": 4.5, "unit": "mm", "source": "Page 1", "verified": True},
        "minimum_allowable_thickness": {"value": 3.5, "unit": "mm", "source": "Page 1", "verified": True},
        "inspection_interval": {"value": 5.0, "unit": "years", "source": "Page 1", "verified": True},
    }
    res = DeterministicCalculator.execute_pipeline(p201_doc)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30
    assert res["corrosion_rate"]["result"] == 0.30


def test_section10_test3_alias_resolution_original_and_current_wall():
    """
    TEST 3:
    Use: original_thickness, current_wall_thickness, inspection_interval
    Expected: same deterministic result (0.30 mm/year)
    """
    alias_doc = {
        "equipment_tag": "P-101",
        "original_thickness": {"value": 5.0, "unit": "mm", "source": "Page 1", "verified": True},
        "current_wall_thickness": {"value": 3.8, "unit": "mm", "source": "Page 1", "verified": True},
        "inspection_interval": {"value": 4.0, "unit": "years", "source": "Page 1", "verified": True},
    }
    res = DeterministicCalculator.execute_pipeline(alias_doc)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30


def test_section10_test4_bidirectional_resolver():
    """
    TEST 4:
    Formula asks: T_previous, T_current, elapsed_time
    Evidence provides: previous_thickness, current_thickness, inspection_interval
    Expected: all three resolve successfully without nulls
    """
    canonical = {
        "previous_thickness": {"value": 5.0, "unit": "mm", "source": "Page 1"},
        "current_thickness": {"value": 3.8, "unit": "mm", "source": "Page 1"},
        "inspection_interval": {"value": 4.0, "unit": "years", "source": "Page 1"},
    }
    formula_def = {
        "formula_id": "API570-CR-001",
        "required_inputs": ["T_previous", "T_current", "elapsed_time"],
        "input_mapping": {"T_previous": "previous_thickness", "T_current": "current_thickness", "elapsed_time": "inspection_interval"},
    }
    res = DeterministicCalculator.resolve_formula_inputs(formula_def, canonical)
    assert res["status"] == "SUCCESS"
    assert res["resolved_inputs"]["T_previous"] == 5.0
    assert res["resolved_inputs"]["T_current"] == 3.8
    assert res["resolved_inputs"]["elapsed_time"] == 4.0


def test_section10_test5_missing_input_explicit_insufficient_data():
    """
    TEST 5:
    If a genuinely required input is absent, return:
    {"status": "INSUFFICIENT_DATA", "missing_inputs": [...]}
    Do NOT return N/A from the LLM.
    """
    incomplete_canonical = {
        "current_thickness": {"value": 3.8, "unit": "mm", "source": "Page 1"},
        "inspection_interval": {"value": 4.0, "unit": "years", "source": "Page 1"},
    }
    formula_def = {
        "formula_id": "API570-CR-001",
        "required_inputs": ["T_previous", "T_current", "elapsed_time"],
        "input_mapping": {"T_previous": "previous_thickness", "T_current": "current_thickness", "elapsed_time": "inspection_interval"},
    }
    res = DeterministicCalculator.resolve_formula_inputs(formula_def, incomplete_canonical)
    assert res["status"] == "INSUFFICIENT_DATA"
    assert "T_previous" in res["missing_inputs"]
    assert "previous_thickness" in res["expected_canonical_fields"]


def test_section10_thickness_margin_separate_calculation():
    """
    Separate thickness margin calculation:
    P-101: 3.8 - 3.2 = 0.6 mm
    P-201: 4.5 - 3.5 = 1.0 mm
    """
    p101_doc = {
        "previous_thickness": {"value": 5.0, "unit": "mm"},
        "current_thickness": {"value": 3.8, "unit": "mm"},
        "minimum_allowable_thickness": {"value": 3.2, "unit": "mm"},
        "inspection_interval": {"value": 4.0, "unit": "years"},
    }
    p101_res = DeterministicCalculator.execute_pipeline(p101_doc)
    assert p101_res["thickness_margin"]["result"] == 0.6

    p201_doc = {
        "previous_thickness": {"value": 6.0, "unit": "mm"},
        "current_thickness": {"value": 4.5, "unit": "mm"},
        "minimum_allowable_thickness": {"value": 3.5, "unit": "mm"},
        "inspection_interval": {"value": 5.0, "unit": "years"},
    }
    p201_res = DeterministicCalculator.execute_pipeline(p201_doc)
    assert p201_res["thickness_margin"]["result"] == 1.0


# ═════════════════════════════════════════════════════════════════════════════
# PROMPT SECTION 10 & 11 EXPLICIT REGRESSION SUITE
# ═════════════════════════════════════════════════════════════════════════════

def test_prompt_test1_canonical_names():
    """
    TEST 1:
    {
      original_thickness: 5.0,
      current_thickness: 3.8,
      inspection_interval: 4.0
    }
    Expected: 0.30 mm/year
    """
    data = {
        "original_thickness": 5.0,
        "current_thickness": 3.8,
        "inspection_interval": 4.0,
    }
    res = DeterministicCalculator.execute_pipeline(data)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30
    assert res["thickness_loss_mm"] == 1.2
    assert "INPUT RESOLUTION:" in res["sec7_trace"]


def test_prompt_test2_previous_currentwall_elapsed():
    """
    TEST 2:
    {
      previous_thickness: 5.0,
      current_wall_thickness: 3.8,
      elapsed_time: 4.0
    }
    Expected: 0.30 mm/year
    """
    data = {
        "previous_thickness": 5.0,
        "current_wall_thickness": 3.8,
        "elapsed_time": 4.0,
    }
    res = DeterministicCalculator.execute_pipeline(data)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30


def test_prompt_test3_tprevious_tcurrent_deltayears():
    """
    TEST 3:
    {
      T_previous: 5.0,
      T_current: 3.8,
      delta_years: 4.0
    }
    Expected: 0.30 mm/year
    """
    data = {
        "T_previous": 5.0,
        "T_current": 3.8,
        "delta_years": 4.0,
    }
    res = DeterministicCalculator.execute_pipeline(data)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30


def test_prompt_test4_missing_current_thickness():
    """
    TEST 4:
    missing current thickness
    Expected: INSUFFICIENT_DATA
    """
    data = {
        "original_thickness": 5.0,
        "inspection_interval": 4.0,
    }
    res = DeterministicCalculator.execute_pipeline(data)
    assert res["status"] == "INSUFFICIENT_DATA"
    assert "current_thickness" in res["missing_inputs"]


def test_prompt_test5_missing_inspection_interval():
    """
    TEST 5:
    missing inspection interval
    Expected: INSUFFICIENT_DATA
    """
    data = {
        "original_thickness": 5.0,
        "current_thickness": 3.8,
    }
    res = DeterministicCalculator.execute_pipeline(data)
    assert res["status"] == "INSUFFICIENT_DATA"
    assert "inspection_interval" in res["missing_inputs"]


def test_prompt_test6_zero_inspection_interval():
    """
    TEST 6:
    zero inspection interval
    Expected: INVALID_INPUT, never divide by zero
    """
    data = {
        "original_thickness": 5.0,
        "current_thickness": 3.8,
        "inspection_interval": 0.0,
    }
    res = DeterministicCalculator.execute_pipeline(data)
    assert res["status"] == "INVALID_INPUT"
    assert "greater than zero" in res.get("error_message", "") or "divide by zero" in res.get("error_message", "")


def test_prompt_test7_multimodal_test_pack_regression():
    """
    TEST 7 (Regression):
    MRPL_Sovereign_Multimodal_Test_Pack(1).pdf
    P-101
    original thickness = 5.0 mm
    current thickness = 3.8 mm
    minimum allowable = 3.2 mm
    inspection interval = 4.0 years
    Expected calculation: (5.0 - 3.8) / 4.0 = 0.30 mm/year
    """
    report_text = """
    PUMP INSPECTION REPORT
    Equipment Tag: P-101
    Original Thickness: 5.0 mm
    Current Wall Thickness: 3.8 mm
    Minimum Allowable Thickness: 3.2 mm
    Inspection Interval: 4.0 years
    """
    res = DeterministicCalculator.execute_pipeline(report_text)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30
    assert res["thickness_loss_mm"] == 1.2
    assert res["thickness_margin"]["result"] == 0.6
    assert res["remaining_life"]["result"] == 2.0


# ==============================================================================
# Comprehensive Rebuilt Pipeline Test Suite (Tests A through U)
# ==============================================================================

from calculator.input_resolver import InputResolver, resolve_required_inputs
from schemas.engineering_evidence import EngineeringEvidence, EvidenceValue


def test_suite_a_canonical_extraction():
    text = "Equipment: P-101\nPrevious Thickness: 5.0 mm\nCurrent Thickness: 3.8 mm\nMinimum Allowable Thickness: 3.2 mm\nInspection Interval: 4.0 years"
    ev = DeterministicCalculator.extract_canonical_inputs(text)
    assert ev["previous_thickness"]["value"] == 5.0
    assert ev["current_thickness"]["value"] == 3.8
    assert ev["minimum_allowable_thickness"]["value"] == 3.2
    assert ev["inspection_interval"]["value"] == 4.0


def test_suite_b_c_d_previous_thickness_aliases():
    for alias_line, expected_val in [
        ("Original Thickness: 5.0 mm", 5.0),
        ("Previous Wall Thickness: 5.0 mm", 5.0),
        ("T_previous: 5.0 mm", 5.0),
    ]:
        ev = DeterministicCalculator.extract_canonical_inputs(f"Equipment: P-101\n{alias_line}\nCurrent Thickness: 3.8 mm\nInspection Interval: 4.0 years")
        assert ev["previous_thickness"]["value"] == expected_val


def test_suite_e_f_current_thickness_aliases():
    for alias_line, expected_val in [
        ("Current Wall Thickness: 3.8 mm", 3.8),
        ("T_current: 3.8 mm", 3.8),
    ]:
        ev = DeterministicCalculator.extract_canonical_inputs(f"Equipment: P-101\nPrevious Thickness: 5.0 mm\n{alias_line}\nInspection Interval: 4.0 years")
        assert ev["current_thickness"]["value"] == expected_val


def test_suite_g_h_interval_aliases():
    for alias_line, expected_val in [
        ("Elapsed Time: 4.0 years", 4.0),
        ("Inspection Interval: 4.0 years", 4.0),
    ]:
        ev = DeterministicCalculator.extract_canonical_inputs(f"Equipment: P-101\nPrevious Thickness: 5.0 mm\nCurrent Thickness: 3.8 mm\n{alias_line}")
        assert ev["inspection_interval"]["value"] == expected_val


def test_suite_i_j_k_l_formatting_variations():
    formats = [
        "Previous Wall Thickness: 6.0 mm\nCurrent Wall Thickness: 4.5 mm\nInspection Interval: 5.0 years",
        "Previous Wall Thickness = 6.0 mm\nCurrent Wall Thickness = 4.5 mm\nInspection Interval = 5.0 years",
        "Previous Wall Thickness\n6.0 mm\nCurrent Wall Thickness\n4.5 mm\nInspection Interval\n5.0 years",
        "Previous Wall Thickness is 6.0 mm\nCurrent Wall Thickness is 4.5 mm\nInspection Interval is 5.0 years",
    ]
    for fmt_text in formats:
        ev = DeterministicCalculator.extract_canonical_inputs(fmt_text)
        assert ev["previous_thickness"]["value"] == 6.0
        assert ev["current_thickness"]["value"] == 4.5
        assert ev["inspection_interval"]["value"] == 5.0


def test_suite_m_units_conversion():
    # cm to mm conversion in InputResolver
    data = {
        "previous_thickness": EvidenceValue(value=0.5, unit="cm"),
        "current_thickness": EvidenceValue(value=0.38, unit="cm"),
        "inspection_interval": EvidenceValue(value=4.0, unit="years"),
    }
    res = InputResolver.resolve_required_inputs(data, ["previous_thickness", "current_thickness", "inspection_interval"])
    assert res["complete"] is True
    assert res["resolved_numeric"]["previous_thickness"] == 5.0
    assert res["resolved_numeric"]["current_thickness"] == 3.8


def test_suite_n_missing_fields_structured():
    data = {"previous_thickness": 5.0, "current_thickness": 3.8}
    res = InputResolver.resolve_required_inputs(data, ["previous_thickness", "current_thickness", "inspection_interval"])
    assert res["complete"] is False
    assert res["status"] == "INSUFFICIENT_DATA"
    assert "inspection_interval" in res["missing_inputs"]


def test_suite_o_p_q_invalid_values():
    # Negative thickness
    neg_data = {"previous_thickness": -5.0, "current_thickness": 3.8, "inspection_interval": 4.0}
    res_neg = InputResolver.resolve_required_inputs(neg_data, ["previous_thickness", "current_thickness", "inspection_interval"])
    assert res_neg["status"] == "INVALID_INPUT"

    # Zero interval
    zero_data = {"previous_thickness": 5.0, "current_thickness": 3.8, "inspection_interval": 0.0}
    res_zero = InputResolver.resolve_required_inputs(zero_data, ["previous_thickness", "current_thickness", "inspection_interval"])
    assert res_zero["status"] == "INVALID_INPUT"

    # Negative interval
    neg_int_data = {"previous_thickness": 5.0, "current_thickness": 3.8, "inspection_interval": -2.0}
    res_neg_int = InputResolver.resolve_required_inputs(neg_int_data, ["previous_thickness", "current_thickness", "inspection_interval"])
    assert res_neg_int["status"] == "INVALID_INPUT"


def test_suite_r_previous_less_than_current_warning():
    data = {"previous_thickness": 3.8, "current_thickness": 5.0, "inspection_interval": 4.0}
    res = InputResolver.resolve_required_inputs(data, ["previous_thickness", "current_thickness", "inspection_interval"])
    assert len(res["warnings"]) > 0
    assert "exceeds previous thickness" in res["warnings"][0]


def test_suite_s_t_u_complete_p101_end_to_end():
    p101_text = """
    PUMP INSPECTION REPORT
    Equipment Tag: P-101
    Inspection Date: 2026-08-15
    Report ID: RPT-P101-2026
    Previous Wall Thickness: 5.0 mm
    Current Wall Thickness: 3.8 mm
    Minimum Allowable Thickness: 3.2 mm
    Inspection Interval: 4.0 years
    """
    res = DeterministicCalculator.execute_pipeline(p101_text)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 0.30
    assert res["expression"] == "(5 - 3.8) / 4"
    assert res["structured_inputs"]["previous_thickness"]["value"] == 5.0
    assert res["structured_inputs"]["current_thickness"]["value"] == 3.8
    assert res["structured_inputs"]["inspection_interval"]["value"] == 4.0

    # Verification Engine check
    from backend.services.verification_engine import VerificationEngine
    from backend.models.execution_plan import ExecutionPlan, ModelRoleAssignment, VerificationSpec, ExecutionStrategy
    from backend.models.task_profile import RiskLevel

    ve = VerificationEngine()
    plan = ExecutionPlan(
        request_id="test-p101-ver",
        task_id="task-p101",
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
            role="verifier",
        ),
        verification_spec=VerificationSpec(cross_model="REQUIRED", deterministic="REQUIRED"),
    )
    vr = ve.verify(
        plan=plan,
        primary_response="The calculated corrosion rate for P-101 is 0.30 mm/year.",
        verifier_response="Agreed. Corrosion rate is 0.30 mm/year.",
        prompt="Calculate corrosion rate for P-101 with previous thickness 5.0 mm, current thickness 3.8 mm, inspection interval 4.0 years",
        attached_data={"extracted_data": res["canonical_inputs"]},
    )
    assert vr.deterministic_status.value in ["PASSED", "MATCH"]
    assert vr.status.value in ["SUPPORTED", "PASSED"]




