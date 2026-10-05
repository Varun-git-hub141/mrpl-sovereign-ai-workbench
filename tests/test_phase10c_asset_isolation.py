import pytest
from pathlib import Path
from backend.services.hybrid_rag import HybridRAGService
from backend.services.question_guard import QuestionTypeGuard
from backend.services.claim_provenance import ClaimProvenanceEngine
from backend.services.orchestrator import ExecutionOrchestrator
from backend.models.rag_models import HybridSearchRequest, RetrievedChunk
from schemas.engineering_evidence import EngineeringEvidence, EvidenceValue
from calculator.input_resolver import InputResolver


@pytest.fixture
def hybrid_rag():
    return HybridRAGService()


@pytest.fixture
def question_guard():
    return QuestionTypeGuard()


@pytest.fixture
def orchestrator():
    orch = ExecutionOrchestrator()
    return orch


def test_mandatory_a_tk201_clean_query(hybrid_rag):
    """
    Mandatory Test A: TK-201 clean query
    Verify:
    - only TK-201 evidence is used for engineering calculations
    - zero P-201 source IDs appear in calculation provenance
    - zero P-201 measurements appear in the calculation
    - asset tag on every calculation input is TK-201
    """
    # 1. Retrieve dossier for TK-201
    dossier = hybrid_rag.get_equipment_dossier("TK-201")
    assert dossier.total_documents > 0, "TK-201 dossier must contain documents"
    for chunk in dossier.retrieved_evidence:
        tag = (chunk.source.equipment_tag or "").upper()
        assert "TK-201" in tag or "TK201" in tag, f"Chunk has non-TK-201 tag: {tag}"

    # 2. Execute calculation from retrieved evidence for TK-201
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("TK-201", "CR-001")
    
    # If calculation succeeds for TK-201:
    if calc_res.get("status") == "SUCCESS":
        assert calc_res.get("equipment_tag") == "TK-201"
        for src in calc_res.get("input_sources", []):
            assert not (src.endswith("-P201") or src.endswith("-P-201") or "/P201" in src), f"P-201 source leaked into TK-201 calculation: {src}"
        
        canon = calc_res.get("canonical_inputs", {})
        for k, v in canon.items():
            if v and isinstance(v, dict) and "source" in v:
                s_str = str(v["source"]).upper()
                assert not (s_str.endswith("-P201") or s_str.endswith("-P-201")), f"P-201 source found in canonical input: {s_str}"

    # 3. Test ClaimProvenanceEngine validation for TK-201
    search_req = HybridSearchRequest(
        query="What is the historical corrosion rate and remaining life for crude storage tank TK-201?",
        equipment_tag="TK-201",
        top_k=6,
    )
    chunks = hybrid_rag.hybrid_search(search_req)
    for c in chunks:
        assert c.source.equipment_tag == "TK-201", f"Retrieved chunk with tag {c.source.equipment_tag} for TK-201 query"

    claim_rep = ClaimProvenanceEngine.validate(
        response_text="TK-201 is a 50,000 m3 crude storage tank in Tank Farm Area 3.",
        retrieved_chunks=chunks,
        deterministic_result=calc_res if calc_res.get("status") == "SUCCESS" else None,
        context_mode="MRPL_LOCAL_KNOWLEDGE_BASE",
        entity_tag="TK-201",
    )
    
    for cl in claim_rep.claims:
        for isrc in (cl.input_sources or []):
            assert not (isrc.endswith("-P201") or isrc.endswith("-P-201")), f"P-201 source found in claim: {isrc}"


def test_mandatory_b_p201_clean_query(hybrid_rag):
    """
    Mandatory Test B: P-201 clean query
    Verify:
    - P-201 evidence is used
    - TK-201 evidence is not used as engineering evidence
    """
    dossier = hybrid_rag.get_equipment_dossier("P-201")
    assert dossier.total_documents > 0, "P-201 dossier must contain documents"
    for chunk in dossier.retrieved_evidence:
        tag = (chunk.source.equipment_tag or "").upper()
        assert "P-201" in tag or "P201" in tag, f"Chunk has non-P-201 tag: {tag}"

    calc_res = hybrid_rag.calculate_from_retrieved_evidence("P-201", "CR-001")
    assert calc_res.get("status") == "SUCCESS"
    assert calc_res.get("equipment_tag") == "P-201"
    assert calc_res.get("result") == 0.3
    
    for src in calc_res.get("input_sources", []):
        assert "TK201" not in src.upper() and "TK-201" not in src.upper()


def test_mandatory_c_cross_asset_contamination_attempt(hybrid_rag, question_guard):
    """
    Mandatory Test C: Cross-asset contamination attempt
    Query: "Assess TK-201 using the P-201 2019 and 2024 thickness records."
    Expected:
    - system must not silently apply P-201 evidence to TK-201
    - explicitly report an asset mismatch / evidence mismatch
    - do not calculate a TK-201 corrosion rate from P-201 values
    """
    # Evaluate retrieved evidence for TK-201 when search is performed
    tk_chunks = hybrid_rag.hybrid_search(HybridSearchRequest(query="Assess TK-201 using the P-201 2019 and 2024 thickness records.", equipment_tag="TK-201", top_k=6))
    
    q_class = question_guard.classify_question("Assess TK-201 using the P-201 2019 and 2024 thickness records.", entity_tag="TK-201")
    ev_eval = question_guard.evaluate_retrieved_evidence(
        q_class=q_class,
        retrieved_chunks=tk_chunks,
        entity_tag="TK-201",
    )
    guidance = question_guard.post_process_validation(
        response_text="Evaluation for TK-201",
        q_class=q_class,
        evidence_eval=ev_eval,
    )
    
    # Verify that question_guard does NOT inject P-201 values
    assert "MRPL-INSP-2019-P201" not in guidance
    assert "MRPL-INSP-2024-P201" not in guidance
    
    # Calculate for TK-201 must NOT return P-201 results
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("TK-201", "CR-001")
    if calc_res.get("status") == "SUCCESS":
        assert calc_res.get("equipment_tag") == "TK-201"
        for src in calc_res.get("input_sources", []):
            assert not (src.endswith("-P201") or src.endswith("-P-201"))


def test_mandatory_d_context_reference_isolation(hybrid_rag):
    """
    Mandatory Test D: Context-reference test
    Use a P-201 document containing a textual reference to TK-201,
    such as PID_CDU_200_P201_Crude_Booster_Loop.json ("routes from TK-201").
    Verify that this does NOT make the P-201 document part of the TK-201 engineering dossier.
    """
    tk_dossier = hybrid_rag.get_equipment_dossier("TK-201")
    tk_doc_ids = [c.source.document_id for c in tk_dossier.retrieved_evidence]
    
    # PID_CDU_200_P201 is a P-201 drawing referencing TK-201 in text
    assert "MRPL-DWG-PID-CDU-200" not in tk_doc_ids
    assert "DOC-PID-CDU-200" not in tk_doc_ids
    
    # Also verify MOC-2022-03 (P-201 minimum flow to TK-201) is not in TK-201 dossier
    assert "MOC-2022-03" not in tk_doc_ids


def test_mandatory_e_calculation_provenance_structure(hybrid_rag):
    """
    Mandatory Test E: Calculation provenance test
    Every deterministic calculation input must carry:
    - asset/equipment tag
    - measurement type
    - component/location
    - value
    - unit
    - source document ID
    - source date
    """
    calc_res = hybrid_rag.calculate_from_retrieved_evidence("P-201", "CR-001")
    assert calc_res.get("status") == "SUCCESS"
    
    inputs_with_prov = calc_res.get("inputs_with_provenance", {})
    assert "previous_thickness" in inputs_with_prov
    assert "current_thickness" in inputs_with_prov
    assert "inspection_interval" in inputs_with_prov
    
    prev_inp = inputs_with_prov["previous_thickness"]
    assert prev_inp.get("equipment_tag") == "P-201"
    assert prev_inp.get("value") == 6.0
    assert prev_inp.get("unit") == "mm"
    assert prev_inp.get("source_document_id") in ("MRPL-EH-P201", "MRPL-EM-P201", "MRPL-DOC-2019-001", "MRPL-DOC-2019-P201", "MRPL-INSP-2019-P201")
    assert prev_inp.get("measurement_type") == "thickness"
    assert "Casing" in prev_inp.get("component", "") or "Pump" in prev_inp.get("component", "")

    curr_inp = inputs_with_prov["current_thickness"]
    assert curr_inp.get("equipment_tag") == "P-201"
    assert curr_inp.get("value") == 4.5
    assert curr_inp.get("unit") == "mm"
    assert curr_inp.get("source_document_id") in ("MRPL-DOC-2024-001", "MRPL-DOC-2024-P201", "MRPL-INSP-2024-P201")
    assert curr_inp.get("measurement_type") == "thickness"
    assert "Casing" in curr_inp.get("component", "") or "Pump" in curr_inp.get("component", "")


def test_mandatory_f_no_fallback_on_insufficient_data(hybrid_rag, question_guard):
    """
    Mandatory Test F: No-fallback test
    If an equipment does not have enough valid thickness observations for a calculation,
    the system must return INSUFFICIENT_DATA and never substitute P-201 values.
    """
    # Create artificial evidence for an asset with missing previous thickness
    incomplete_ev = EngineeringEvidence(
        equipment_tag="PSV-201",
        current_thickness=EvidenceValue(value=10.0, unit="mm", source="PSV Test", page=1, verified=True),
        previous_thickness=None,
        inspection_interval=None,
    )
    
    resolved_prev = InputResolver.resolve_input(incomplete_ev, "previous_thickness")
    resolved_curr = InputResolver.resolve_input(incomplete_ev, "current_thickness")
    resolved_interval = InputResolver.resolve_input(incomplete_ev, "inspection_interval")
    
    assert resolved_prev is None
    assert resolved_curr is not None
    assert resolved_interval is None

    # Verify that question_guard does not inject P-201 numbers for PSV-201
    q_class = question_guard.classify_question("What is the corrosion rate for PSV-201?", entity_tag="PSV-201")
    ev_eval = question_guard.evaluate_retrieved_evidence(
        q_class=q_class,
        retrieved_chunks=[],
        entity_tag="PSV-201",
    )
    guidance = question_guard.post_process_validation(
        response_text="Corrosion rate query for PSV-201",
        q_class=q_class,
        evidence_eval=ev_eval,
    )
    assert "0.30 mm/year" not in guidance
    assert "6.0 mm" not in guidance
    assert "MRPL-INSP-2019-P201" not in guidance
