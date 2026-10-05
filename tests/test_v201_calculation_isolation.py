import pytest
from backend.services.deterministic_calculator import DeterministicCalculator
from backend.services.hybrid_rag import HybridRAGService
from backend.services.orchestrator import ExecutionOrchestrator


@pytest.fixture
def calculator():
    return DeterministicCalculator()


@pytest.fixture
def hybrid_rag():
    return HybridRAGService()


def test_a_v201_shell_course_1_calculation(hybrid_rag):
    """Test A: V-201 Shell Course 1 deterministic calculation isolation."""
    query = "Calculate the corrosion rate for V-201 Shell Course 1."
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query=query)

    assert calc_res["status"] == "SUCCESS"
    assert calc_res["equipment_tag"] == "V-201"
    assert "course 1" in calc_res["inspection_location"].lower() or "shell course 1" in calc_res["component"].lower()

    prev = calc_res["canonical_inputs"]["previous_thickness"]["value"]
    curr = calc_res["canonical_inputs"]["current_thickness"]["value"]
    interval = calc_res["canonical_inputs"]["inspection_interval"]["value"]
    result = calc_res["result"]

    assert prev == 18.0
    assert curr == 17.2
    assert interval == 3.5
    assert pytest.approx(result, rel=1e-3) == (18.0 - 17.2) / 3.5  # 0.228571...

    # Negative assertions
    assert interval != 2.0
    assert result != 0.4
    assert calc_res["equipment_tag"] != "P-201"


def test_b_v201_generic_shell_query_insufficient_data(hybrid_rag):
    """Test B: V-201 generic query without unique CML returns INSUFFICIENT_DATA."""
    query = "Calculate the corrosion rate for V-201 shell."
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query=query)

    # If evidence contains multiple distinct locations (Course 1 vs Course 2) and none is specified,
    # the system must return INSUFFICIENT_DATA and not arbitrarily pick one.
    assert calc_res["status"] == "INSUFFICIENT_DATA"


def test_c_hydrotest_regression_hours_rejected(calculator):
    """Test C: Evidence containing 'zero pressure drop over 2 hours' must not produce interval = 2 years."""
    evidence = (
        "During baseline hydrostatic testing of V-201 in 2017, the vessel showed zero pressure drop over 2 hours at 24.5 bar. "
        "Baseline thickness for Shell Course 1 was 18.0 mm. Current thickness in 2020 is 17.2 mm."
    )
    canonical = calculator.extract_canonical_inputs("CR-001", evidence)

    # inspection_interval must NOT be 2.0 (since 2 was for 2 hours)
    int_obj = canonical.get("inspection_interval")
    assert int_obj is None or (isinstance(int_obj, dict) and int_obj.get("value") != 2.0)


def test_d_p201_calculation_independence(hybrid_rag):
    """Test D: P-201 calculation using its own evidence remains P-201-specific."""
    query = "Calculate corrosion rate for P-201."
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("P-201", "CR-001", query=query)

    assert calc_res["status"] == "SUCCESS"
    assert calc_res["equipment_tag"] == "P-201"
    prev = calc_res["canonical_inputs"]["previous_thickness"]["value"]
    curr = calc_res["canonical_inputs"]["current_thickness"]["value"]
    interval = calc_res["canonical_inputs"]["inspection_interval"]["value"]

    assert prev == 6.0
    assert curr == 4.5
    assert interval == 5.0
    assert pytest.approx(calc_res["result"], rel=1e-3) == 0.30


def test_e_interleaved_isolation(hybrid_rag):
    """Test E: V-201 -> P-201 -> V-201 sequence preserves strict asset isolation."""
    res_v201_1 = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query="Calculate corrosion rate for V-201 Shell Course 1")
    assert res_v201_1["status"] == "SUCCESS"
    assert res_v201_1["equipment_tag"] == "V-201"
    assert pytest.approx(res_v201_1["result"], rel=1e-3) == (18.0 - 17.2) / 3.5

    res_p201 = hybrid_rag.calculate_from_retrieved_evidence("P-201", "CR-001", query="Calculate corrosion rate for P-201")
    assert res_p201["status"] == "SUCCESS"
    assert res_p201["equipment_tag"] == "P-201"
    assert pytest.approx(res_p201["result"], rel=1e-3) == 0.30

    res_v201_2 = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query="Calculate corrosion rate for V-201 Shell Course 1")
    assert res_v201_2["status"] == "SUCCESS"
    assert res_v201_2["equipment_tag"] == "V-201"
    assert pytest.approx(res_v201_2["result"], rel=1e-3) == (18.0 - 17.2) / 3.5


def test_f_missing_equipment_tag_no_fallback(calculator):
    """Test F: When equipment tag is missing, calculator does not fall back to P-201 or any other real asset tag."""
    evidence = "Wall thickness measurement: previous = 18.0 mm, current = 17.2 mm over 3.5 years."
    canonical = calculator.extract_canonical_inputs("CR-001", evidence)
    eq_tag = canonical.get("equipment_tag")

    assert eq_tag is None or eq_tag == "UNKNOWN_EQUIPMENT"
    assert eq_tag != "P-201"
    assert eq_tag != "V-201"


def test_g_provenance_integrity(hybrid_rag):
    """Test G: Calculation result contains complete provenance for all inputs and verified status."""
    query = "Calculate the corrosion rate for V-201 Shell Course 1."
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query=query)

    assert calc_res["status"] == "SUCCESS"
    assert calc_res["equipment_tag"] == "V-201"
    assert "course 1" in calc_res["inspection_location"].lower()

    inputs = calc_res["canonical_inputs"]
    assert "source_doc" in inputs["previous_thickness"]
    assert "source_doc" in inputs["current_thickness"]
    assert "source_doc" in inputs["inspection_interval"]

    # Strict source document attribution
    assert "2017" in inputs["previous_thickness"]["source_doc"] or "BASE" in inputs["previous_thickness"]["source_doc"]
    assert "2020" in inputs["current_thickness"]["source_doc"]
    assert "2017" in inputs["inspection_interval"]["source_doc"] and "2020" in inputs["inspection_interval"]["source_doc"]

    assert calc_res["independent_verification"]["status"] == "VERIFIED"
    assert calc_res["independent_verification"]["discrepancy"] == 0.0


def test_h_claim_provenance_classification(hybrid_rag):
    """Test H: Claim classification distinguishes direct evidence from calculated/system-generated metadata."""
    from backend.services.claim_provenance import ClaimProvenanceEngine
    from backend.models.claim_provenance import ClaimOriginType

    query = "Calculate the corrosion rate for V-201 Shell Course 1."
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query=query)
    dossier = hybrid_rag.get_equipment_dossier("V-201")
    chunk_dicts = [
        {
            "document_id": c.source.document_id,
            "document_name": c.source.document,
            "document_type": c.source.document_type,
            "equipment_tag": c.source.equipment_tag,
            "page": c.source.page,
            "chunk_id": f"{c.source.document_id}_c1",
            "text": c.text,
            "bm25_score": 0.95,
            "vector_score": 0.85,
            "hybrid_score": 0.90,
        }
        for c in dossier.retrieved_evidence
    ]

    answer = (
        "Baseline thickness in 2017 was 18.0 mm for Shell Course 1. "
        "Measured thickness in 2020 was 17.2 mm. "
        "Metal loss is 0.8 mm over the 3.5 year interval. "
        "The calculated corrosion rate is 0.2286 mm/year. "
        "Status: VERIFIED by deterministic calculator."
    )

    report = ClaimProvenanceEngine.validate(
        response_text=answer,
        retrieved_chunks=dossier.retrieved_evidence,
        deterministic_result=calc_res,
        entity_tag="V-201",
    )

    # Metal loss, corrosion rate, and Status: VERIFIED must be CALCULATED_FROM_MRPL_EVIDENCE
    calc_claims = [c for c in report.claims if c.origin == ClaimOriginType.CALCULATED_FROM_MRPL_EVIDENCE.value]
    direct_claims = [c for c in report.claims if c.origin == ClaimOriginType.MRPL_KB_DIRECT.value]

    assert len(calc_claims) >= 2
    assert any("corrosion rate" in c.claim.lower() for c in calc_claims)
    assert any("status: verified" in c.claim.lower() for c in calc_claims)
    # Verification status must NOT be classified as DIRECT_MRPL_RECORD
    assert not any("status: verified" in c.claim.lower() for c in direct_claims)


def test_provenance_precision_requirements_a_through_i(hybrid_rag, calculator):
    """
    Final Provenance Precision Fix Regression Suite (Criteria A-I):
    A. 17.2 mm primary source = MRPL-INSP-2020-V201
    B. 18.0 mm primary source = MRPL-INSP-2017-V201
    C. 3.5 years = DERIVED_FROM_MRPL_EVIDENCE from the two inspection dates
    D. 2023 inspection is not a causal input to the 2017->2020 calculation
    E. Equipment History is corroborating evidence, not the primary source for 17.2 mm
    F. No UNKNOWN_EQUIPMENT calculation trace is exposed as VERIFIED
    G. "Safe to proceed" is calculation-scoped, not an engineering approval
    H. Result remains exactly 0.2286 mm/year
    I. No P-201, 0.40 mm/year, or 2.0-year contamination
    """
    from backend.services.claim_provenance import ClaimProvenanceEngine
    from backend.models.claim_provenance import ClaimOriginType
    from backend.services.evidence.evidence_sufficiency import EvidenceSufficiencyEngine, SufficiencyStatus
    from backend.services.evidence.evidence_models import EvidenceContract, EvidenceRequirement, EvidenceType, AuthorityLevel

    query = "Calculate the corrosion rate for V-201 Shell Course 1 between 2017 and 2020."
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query=query)
    dossier = hybrid_rag.get_equipment_dossier("V-201")

    # --- Criterion H: Result remains exactly 0.2286 mm/year ---
    assert calc_res["status"] == "SUCCESS"
    assert calc_res["result"] == 0.2286
    assert pytest.approx(calc_res["result"], rel=1e-3) == (18.0 - 17.2) / 3.5

    # --- Criterion I: No P-201, 0.40 mm/year, or 2.0-year contamination ---
    assert calc_res["equipment_tag"] == "V-201"
    assert calc_res["equipment_tag"] != "P-201"
    assert calc_res["canonical_inputs"]["inspection_interval"]["value"] == 3.5
    assert calc_res["canonical_inputs"]["inspection_interval"]["value"] != 2.0
    assert calc_res["result"] != 0.40

    # --- Criterion D: 2023 inspection is not a causal input to the 2017->2020 calculation ---
    input_sources = calc_res.get("input_sources", [])
    assert not any("2023" in s for s in input_sources)
    assert not any("EH-" in s or "EM-" in s for s in input_sources)

    # Validate response text with claim provenance engine
    response_text = (
        "Baseline Thickness (2017): 18.0 mm (Source: MRPL-INSP-2017-V201)\n"
        "Current Thickness (2020): 17.2 mm (Source: MRPL-INSP-2020-V201)\n"
        "Elapsed Interval: 3.5 years derived from 2017-04-25 to 2020-10-14\n"
        "Corrosion Rate: 0.2286 mm/year calculated using API 570 Formula CR-001\n"
        "Status: VERIFIED by deterministic calculator."
    )

    report = ClaimProvenanceEngine.validate(
        response_text=response_text,
        retrieved_chunks=dossier.retrieved_evidence,
        deterministic_result=calc_res,
        entity_tag="V-201",
    )

    # --- Criterion A & E: 17.2 mm primary source = MRPL-INSP-2020-V201, EH is not primary ---
    num_17_2 = next((n for n in report.numerical_origins if "17.2" in n.value), None)
    assert num_17_2 is not None
    assert "MRPL-INSP-2020-V201" in num_17_2.source_doc
    assert "EH" not in num_17_2.source_doc

    claim_17_2 = next((c for c in report.claims if "17.2" in c.claim and "current" in c.claim.lower()), None)
    if claim_17_2 and claim_17_2.source_document:
        assert "MRPL-INSP-2020-V201" in claim_17_2.source_document
        assert "EH" not in claim_17_2.source_document

    # --- Criterion B: 18.0 mm primary source = MRPL-INSP-2017-V201 ---
    num_18_0 = next((n for n in report.numerical_origins if "18.0" in n.value or "18" in n.value), None)
    assert num_18_0 is not None
    assert "MRPL-INSP-2017-V201" in num_18_0.source_doc

    claim_18_0 = next((c for c in report.claims if "18.0" in c.claim and "baseline" in c.claim.lower()), None)
    if claim_18_0 and claim_18_0.source_document:
        assert "MRPL-INSP-2017-V201" in claim_18_0.source_document

    # --- Criterion C: 3.5 years = DERIVED_FROM_MRPL_EVIDENCE from the two inspection dates ---
    num_3_5 = next((n for n in report.numerical_origins if "3.5" in n.value), None)
    assert num_3_5 is not None
    assert num_3_5.origin == "DERIVED_FROM_MRPL_EVIDENCE"
    assert "MRPL-INSP-2017-V201" in num_3_5.source_doc
    assert "MRPL-INSP-2020-V201" in num_3_5.source_doc

    # --- Criterion F: No UNKNOWN_EQUIPMENT calculation trace is exposed as VERIFIED ---
    unscoped_calc = hybrid_rag.calculate_from_retrieved_evidence("UNKNOWN_EQUIPMENT", "CR-001")
    assert unscoped_calc["status"] == "INSUFFICIENT_DATA"
    assert unscoped_calc["independent_verification"]["verified"] is False
    assert unscoped_calc["result"] is None

    # --- Criterion G: "Safe to proceed" is calculation-scoped, not an engineering approval ---
    contract = EvidenceContract(
        task_id="task-calc-v201",
        task_type="engineering_calculation",
        risk_level="medium",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Current UT Survey",
                mandatory=True,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                validation_rule="Check 2020 UT survey",
            ),
            EvidenceRequirement(
                id="REQ-2",
                evidence_type=EvidenceType.BASELINE_INSPECTION,
                description="Baseline UT Survey",
                mandatory=True,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                validation_rule="Check 2017 baseline survey",
            ),
        ],
    )
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=dossier.retrieved_evidence,
        query=query,
    )
    assert assessment.overall_status == SufficiencyStatus.SUFFICIENT
    assert "Required evidence is verified" in assessment.system_recommendation
    assert "does not constitute an engineering fitness-for-service decision" in assessment.system_recommendation


def test_v201_provenance_presentation_microfixes(hybrid_rag, calculator):
    """
    Micro-Fix Presentation & Unit Typing Regression Suite:
    D. 'Resolved Inputs:' is not marked as UNSUPPORTED engineering claim
    E. No '0.2286 mm' lineage entry exists
    F. Result 0.2286 is strictly typed as CORROSION_RATE with unit mm/year
    """
    from backend.services.claim_provenance import ClaimProvenanceEngine
    from backend.models.claim_provenance import ClaimOriginType

    query = "Calculate the corrosion rate for V-201 Shell Course 1 between 2017 and 2020."
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("V-201", "CR-001", query=query)
    dossier = hybrid_rag.get_equipment_dossier("V-201")

    # Complete response text mimicking actual orchestrator output
    response_text = (
        "The corrosion rate for V-201 Shell Course 1 between 2017 and 2020 can be calculated as follows:\n\n"
        "1. Baseline thickness in 2017: 18.0 mm\n"
        "2. Measured thickness in 2020: 17.2 mm\n"
        "3. Interval between inspections: 2020 - 2017 = 3.5 years\n\n"
        "Corrosion rate = (Baseline thickness - Measured thickness) / Interval\n"
        "Corrosion rate = (18.0 mm - 17.2 mm) / 3.5 years\n"
        "Corrosion rate = 0.8 mm / 3.5 years\n"
        "Corrosion rate ≈ 0.228 mm/year\n\n"
        "Therefore, the corrosion rate for V-201 Shell Course 1 between 2017 and 2020 is approximately 0.228 mm/year.\n\n"
        "═══════════════════════════════════════════════════════════════\n"
        "DETERMINISTIC REFINERY CALCULATION (LEVEL 2 ARITHMETIC AUTHORITY)\n"
        "═══════════════════════════════════════════════════════════════\n"
        "Equipment Tag: V-201\n"
        "Component: Vessel Shell\n"
        "Inspection Location / CML: vessel shell course 1\n"
        "Formula: CR-001 — Historical Average Corrosion Rate\n"
        "Equation: (18.0 - 17.2) / 3.5\n"
        "Resolved Inputs:\n"
        "  • Previous Thickness: 18.0 mm (Source: MRPL-INSP-2017-V201)\n"
        "  • Current Thickness:  17.2 mm (Source: MRPL-INSP-2020-V201)\n"
        "  • Elapsed Interval:   3.5 years (Source: derived from documented 2017-04-25 -> 2020-10-14 inspection dates (MRPL-INSP-2020-V201 / MRPL-DEC-2020-08))\n"
        "Computed Result: 0.2286 mm/year\n"
        "Status: VERIFIED (Engine: Deterministic Python Calculator)\n"
        "═══════════════════════════════════════════════════════════════\n"
    )

    report = ClaimProvenanceEngine.validate(
        response_text=response_text,
        retrieved_chunks=dossier.retrieved_evidence,
        deterministic_result=calc_res,
        entity_tag="V-201",
    )

    # --- Requirement D: 'Resolved Inputs:' is NOT marked as UNSUPPORTED ---
    unsupported_claims = [c for c in report.claims if c.origin == ClaimOriginType.UNSUPPORTED.value]
    assert len(unsupported_claims) == 0, f"Found unexpected unsupported claims: {[c.claim for c in unsupported_claims]}"
    assert not any("Resolved Inputs" in c.claim for c in report.claims)
    assert report.source_coverage.unsupported_claims == 0
    assert report.is_fully_supported is True

    # --- Requirement E: No '0.2286 mm' lineage entry exists ---
    for num in report.numerical_origins:
        if "0.2286" in num.value or "0.228" in num.value:
            assert num.unit != "mm", f"Lineage entry {num.value} incorrectly typed with unit mm!"
            assert num.quantity_type != "THICKNESS", f"Lineage entry {num.value} incorrectly typed as THICKNESS!"

    # --- Requirement F: 0.2286 is typed as CORROSION_RATE with unit mm/year ---
    res_num = next((n for n in report.numerical_origins if "0.2286" in n.value or "0.228" in n.value), None)
    assert res_num is not None
    assert res_num.unit == "mm/year"
    assert res_num.quantity_type == "CORROSION_RATE"
    assert res_num.origin in ["DETERMINISTIC_CALCULATOR", "DETERMINISTIC CALCULATOR"]
    assert res_num.is_calculated is True

    # Check that thickness values are cleanly typed
    num_18 = next((n for n in report.numerical_origins if "18.0" in n.value or "18" in n.value), None)
    assert num_18 is not None
    assert num_18.unit == "mm"
    assert num_18.quantity_type == "THICKNESS"

    num_17_2 = next((n for n in report.numerical_origins if "17.2" in n.value), None)
    assert num_17_2 is not None
    assert num_17_2.unit == "mm"
    assert num_17_2.quantity_type == "THICKNESS"

    num_3_5 = next((n for n in report.numerical_origins if "3.5" in n.value), None)
    assert num_3_5 is not None
    assert num_3_5.unit == "years"
    assert num_3_5.quantity_type == "INTERVAL"


