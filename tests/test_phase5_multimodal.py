import os
import base64
import pytest
from backend.services.multimodal_processor import MultimodalFileProcessor
from backend.services.task_analyzer import TaskAnalyzer
from backend.services.context_builder import RequestContextBuilder
from backend.services.router import IntelligentModelRouter
from backend.services.execution_planner import ExecutionPlanner
from backend.services.registry import ModelRegistry
from backend.services.discovery import ModelDiscoveryService
from backend.services.health_manager import ModelHealthManager
from backend.services.verification_engine import VerificationEngine
from backend.models.task_profile import TaskType, RiskLevel, InputModality
from backend.models.verification_result import VerificationStatus, DeterministicStatus
from backend.models.model_profile import (
    ModelProfile,
    CapabilityVector,
    HardwareRequirements,
    PerformanceStats,
)


@pytest.fixture
def test_pdf_bytes():
    pdf_path = os.path.join("samples", "MRPL_Sovereign_Multimodal_Test_Pack.pdf")
    with open(pdf_path, "rb") as f:
        return f.read()


@pytest.fixture
def mock_registry():
    profiles = [
        ModelProfile(
            id="m-coder",
            ollama_name="qwen2.5-coder:3b",
            display_name="Qwen 2.5 Coder 3B",
            family="qwen2",
            capabilities=CapabilityVector.from_dict({"coding": 0.95, "mathematics": 0.85, "reasoning": 0.75, "tool_use": 0.80, "general": 0.60}),
            hardware=HardwareRequirements(estimated_vram_gb=2.0),
            performance=PerformanceStats(latency_score=0.90, benchmark_score=0.85),
        ),
        ModelProfile(
            id="m-reasoning",
            ollama_name="qwen3:4b",
            display_name="Qwen 3 4B",
            family="qwen3",
            capabilities=CapabilityVector.from_dict({"reasoning": 0.95, "document_understanding": 0.92, "general": 0.90, "tool_use": 0.70, "ocr": 0.85}),
            hardware=HardwareRequirements(estimated_vram_gb=2.5),
            performance=PerformanceStats(latency_score=0.80, benchmark_score=0.92),
        ),
        ModelProfile(
            id="m-vision",
            ollama_name="qwen2.5vl:3b",
            display_name="Qwen 2.5 VL 3B",
            family="qwen25vl",
            capabilities=CapabilityVector.from_dict({"vision": 0.98, "ocr": 0.95, "document_understanding": 0.90, "reasoning": 0.75, "general": 0.70}),
            hardware=HardwareRequirements(estimated_vram_gb=3.0),
            performance=PerformanceStats(latency_score=0.75, benchmark_score=0.88),
        ),
    ]

    class MockDiscovery:
        def discover_models(self):
            return profiles

    reg = ModelRegistry(discovery_service=MockDiscovery())
    reg.refresh()
    return reg


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Upload 5-Page PDF -> Reports 5 pages and processes all 5 pages
# ─────────────────────────────────────────────────────────────────────────────
def test_1_five_page_pdf_extraction(test_pdf_bytes):
    processor = MultimodalFileProcessor()
    doc = processor.process_file(
        name="MRPL_Sovereign_Multimodal_Test_Pack.pdf",
        file_bytes=test_pdf_bytes,
        query_context="Extract all pages from the 5-page PDF",
    )

    assert doc.status == "PROCESSED"
    assert doc.doc_type == "PDF"
    assert doc.page_count == 5
    assert doc.pages_processed_count == 5
    assert len(doc.pages) == 5

    # Verify each page's content
    assert doc.pages[0].page_number == 1
    assert "P-101 Transfer Pump" in doc.pages[0].extracted_text
    assert doc.pages[1].page_number == 2
    assert "CDU-101-01" in doc.pages[1].extracted_text
    assert doc.pages[2].page_number == 3
    assert "CDU-101-02" in doc.pages[2].extracted_text
    assert doc.pages[3].page_number == 4
    assert "SOP-MRPL-MNT-2026" in doc.pages[3].extracted_text
    assert doc.pages[4].page_number == 5
    assert "ASTM A106" in doc.pages[4].extracted_text


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Upload Scanned Document -> OCR fallback triggered
# ─────────────────────────────────────────────────────────────────────────────
def test_2_scanned_pdf_ocr_fallback():
    class MockOllamaAdapter:
        def generate(self, model, prompt, images=None, **kwargs):
            return {
                "success": True,
                "response": "Equipment: P-101 Transfer Pump\nCurrent wall thickness = 3.8 mm\nMinimum allowable thickness = 3.2 mm",
            }

    processor = MultimodalFileProcessor(ollama_adapter=MockOllamaAdapter())
    doc = processor.process_file(
        name="scanned_inspection_p101.jpg",
        base64_data="data:image/jpeg;base64,ZmFrZV9pbWFnZV9ieXRlcw==",
        query_context="Read scanned inspection report",
    )

    assert doc.status == "PROCESSED"
    assert doc.pages[0].ocr_text is not None
    assert "3.8 mm" in doc.pages[0].ocr_text
    assert "3.2 mm" in doc.pages[0].ocr_text


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Diagram Pages -> Rendered to image and vision analysis performed
# ─────────────────────────────────────────────────────────────────────────────
def test_3_pid_diagram_vision_extraction(test_pdf_bytes):
    processor = MultimodalFileProcessor()
    doc = processor.process_file(
        name="MRPL_Sovereign_Multimodal_Test_Pack.pdf",
        file_bytes=test_pdf_bytes,
        query_context="Identify all components and flow direction in P&ID",
    )

    # Page 2: Primary P&ID
    page2 = doc.pages[1]
    assert page2.page_number == 2
    assert page2.image_base64 is not None
    assert page2.vision_observations is not None
    assert page2.vision_status == "SUCCESS"
    obs2 = page2.vision_observations
    assert "P-101" in obs2["equipment"]
    assert "T-101" in obs2["equipment"]
    assert "V-101" in obs2["valves"]
    assert "V-102" in obs2["valves"]
    assert "V-103" in obs2["valves"]
    assert obs2["flow_direction"] == "LEFT_TO_RIGHT"

    # Page 3: Auxiliary P&ID
    page3 = doc.pages[2]
    assert page3.page_number == 3
    assert page3.image_base64 is not None
    assert page3.vision_observations is not None
    obs3 = page3.vision_observations
    assert "T-101" in obs3["equipment"]
    assert "PSV-101" in obs3["valves"]
    assert obs3["flow_direction"] == "TOP_TO_BOTTOM"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Wall thickness, Inspection Date, and Process Line with citations
# ─────────────────────────────────────────────────────────────────────────────
def test_4_current_wall_thickness_extraction(test_pdf_bytes):
    processor = MultimodalFileProcessor()
    doc = processor.process_file(
        name="MRPL_Sovereign_Multimodal_Test_Pack.pdf",
        file_bytes=test_pdf_bytes,
        query_context="Extract wall thickness, date, and connected process line",
    )

    # Verify structured fields extracted from Page 1
    page1 = doc.pages[0]
    assert page1.quality == "good"
    assert page1.character_count > 0

    field_names = [f["field"] for f in page1.structured_fields]
    assert "equipment_tag" in field_names
    assert "original_thickness" in field_names
    assert "current_wall_thickness" in field_names
    assert "minimum_allowable_thickness" in field_names
    assert "inspection_interval" in field_names
    assert "inspection_date" in field_names
    assert "connected_process_line" in field_names

    # Verify exact extracted values
    field_map = {f["field"]: f for f in page1.structured_fields}
    assert field_map["original_thickness"]["value"] == 5.0
    assert field_map["current_wall_thickness"]["value"] == 3.8
    assert field_map["minimum_allowable_thickness"]["value"] == 3.2
    assert field_map["inspection_interval"]["value"] == 4.0
    assert field_map["inspection_date"]["value"] == "2026-03-15"
    assert field_map["connected_process_line"]["value"] == "10-CDU-PL-101"

    # Verify evidence envelope contains structured provenance
    envelope = processor.format_evidence_envelope([doc])
    assert "DOCUMENT EVIDENCE" in envelope
    assert "STRUCTURED FIELDS:" in envelope
    assert "current_wall_thickness: 3.8 mm" in envelope
    assert "minimum_allowable_thickness: 3.2 mm" in envelope
    assert "original_thickness: 5.0 mm" in envelope
    assert "inspection_interval: 4.0 years" in envelope
    assert "Inspection Date" in envelope or "inspection_date" in envelope
    assert "Connected Process Line" in envelope or "connected_process_line" in envelope
    assert "Page 1" in envelope
    assert "Current wall thickness = 3.8 mm" in envelope  # Raw text still present
    assert "Minimum allowable thickness = 3.2 mm" in envelope  # Raw text still present


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: P&ID components identification with Page 2 source
# ─────────────────────────────────────────────────────────────────────────────
def test_5_pid_components_identification(test_pdf_bytes):
    processor = MultimodalFileProcessor()
    doc = processor.process_file(
        name="MRPL_Sovereign_Multimodal_Test_Pack.pdf",
        file_bytes=test_pdf_bytes,
        query_context="Identify all components in the P&ID",
    )

    page2_obs = doc.pages[1].vision_observations
    all_components = page2_obs["equipment"] + page2_obs["valves"]
    for expected in ["P-101", "T-101", "V-101", "V-102", "V-103"]:
        assert expected in all_components

    # Verify structured claims tracking
    p2_claims = [c for c in doc.claims if c["source"]["page"] == 2]
    assert len(p2_claims) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Flow Direction Determination across Pages
# ─────────────────────────────────────────────────────────────────────────────
def test_6_flow_direction_extraction(test_pdf_bytes):
    processor = MultimodalFileProcessor()
    doc = processor.process_file(
        name="MRPL_Sovereign_Multimodal_Test_Pack.pdf",
        file_bytes=test_pdf_bytes,
        query_context="What is the flow direction?",
    )

    # Page 2: LEFT_TO_RIGHT
    assert doc.pages[1].vision_observations["flow_direction"] == "LEFT_TO_RIGHT"
    # Page 3: TOP_TO_BOTTOM
    assert doc.pages[2].vision_observations["flow_direction"] == "TOP_TO_BOTTOM"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Engineering Calculation Question -> Deterministic verification
# ─────────────────────────────────────────────────────────────────────────────
def test_7_engineering_calculation_verification():
    verification_engine = VerificationEngine()
    prompt = (
        "=== EXTRACTED EVIDENCE ===\n"
        "[Document: MRPL_Sovereign_Multimodal_Test_Pack.pdf | Page 1]\n"
        "Equipment: P-101 Transfer Pump\n"
        "Original wall thickness = 5.0 mm\n"
        "Current wall thickness = 3.8 mm\n"
        "Inspection interval = 4.0 years\n"
        "User Request: Calculate the corrosion rate using the values in the uploaded report."
    )

    primary_response = (
        "Based on the inspection report (Page 1), original wall thickness is 5.0 mm and current wall thickness is 3.8 mm over 4.0 years.\n"
        "Corrosion Rate = (5.0 - 3.8) / 4.0 = 0.30 mm/year."
    )

    class MockModelRole:
        ollama_name = "qwen2.5-coder:3b"
        model_id = "m-coder"
        display_name = "Coder 3B"

    class MockPlan:
        request_id = "req-calc-multimodal"
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

    report = verification_engine.verify(
        plan=MockPlan(),
        prompt=prompt,
        primary_response=primary_response,
        verifier_response=None,
    )

    assert report.deterministic_status == DeterministicStatus.PASSED
    assert report.deterministic.expected_value == 0.3
    assert report.status == VerificationStatus.SUPPORTED


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Intentional Contradiction -> CONFLICT DETECTED
# ─────────────────────────────────────────────────────────────────────────────
def test_8_intentional_contradiction_conflict_detected():
    verification_engine = VerificationEngine()
    prompt = (
        "=== EXTRACTED EVIDENCE ===\n"
        "[Document: MRPL_Sovereign_Multimodal_Test_Pack.pdf | Page 1]\n"
        "Equipment: P-101 Transfer Pump\n"
        "Current wall thickness = 3.8 mm\n"
        "User Request: Review the uploaded P-101 inspection report and check current thickness."
    )

    primary_response = "Inspection report indicates current wall thickness is 3.8 mm."
    # Verifier hallucinates 4.2 mm, causing an evidence conflict
    verifier_response = "According to survey notes, the current wall thickness is 4.2 mm."

    class MockModelRole:
        ollama_name = "qwen3:4b"
        model_id = "m-reasoning"
        display_name = "Qwen3 4B"

    class MockPlan:
        request_id = "req-conflict-multimodal"
        risk = RiskLevel.HIGH
        primary_model = MockModelRole()
        verifier_model = MockModelRole()
        verification_independence = "HIGHER"
        human_approval_required = True

        class VerificationSpec:
            cross_model_required = True
            deterministic_required = False
            evidence_required = True
            contradiction_check_required = True

        verification_spec = VerificationSpec()

    report = verification_engine.verify(
        plan=MockPlan(),
        prompt=prompt,
        primary_response=primary_response,
        verifier_response=verifier_response,
    )

    assert report.status == VerificationStatus.CONTRADICTED
    assert report.human_review_required is True
    assert len(report.contradictions) > 0
    assert any("Document Evidence Conflict" in c for c in report.contradictions)
