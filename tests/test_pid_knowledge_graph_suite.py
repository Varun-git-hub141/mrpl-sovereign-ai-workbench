import pytest
from backend.services.pid_graph_engine import PIDGraphEngine
from backend.models.pid_graph_models import (
    PIDQueryRequest,
    PIDQueryResponse,
    QueryIntent,
    PIDQueryResultStatus,
)
from backend.telemetry.audit import NetworkEgressGuard


@pytest.fixture
def pid_engine():
    return PIDGraphEngine()


def test_00_multi_drawing_loader(pid_engine):
    """Verifies that all 5 KB drawings plus detailed CDU-P-101 are loaded."""
    drawings = pid_engine.list_drawings()
    drawing_ids = [d["drawing_id"] for d in drawings]

    assert len(drawings) >= 5
    assert "MRPL-PID-CDU-200" in drawing_ids or "CDU-200" in drawing_ids
    assert "MRPL-PID-CDU-100" in drawing_ids or "CDU-100" in drawing_ids
    assert "MRPL-PID-C101" in drawing_ids or "C-101" in drawing_ids
    assert "MRPL-PID-TK201" in drawing_ids or "TK-201" in drawing_ids
    assert "MRPL-PID-V201" in drawing_ids or "V-201" in drawing_ids
    assert "CDU-P-101" in drawing_ids


def test_01_isolation_boundary_p101(pid_engine):
    """TEST 1: 'Which valves isolate P-101?' must traverse isolation relationships."""
    res = pid_engine.query_pid(PIDQueryRequest(question="Which valves isolate P-101?", drawing_id="CDU-P-101"))
    assert res.status in [PIDQueryResultStatus.DERIVED_GRAPH_TRAVERSAL, PIDQueryResultStatus.DIRECT_SOURCE_RELATIONSHIP]
    assert res.query_plan.intent == QueryIntent.ISOLATION
    assert "XV-203" in res.direct_nodes_involved
    assert "XV-204" in res.direct_nodes_involved
    assert res.confidence >= 0.95
    assert res.provenance_records is not None
    assert len(res.provenance_records) > 0


def test_02_upstream_traversal_p101(pid_engine):
    """TEST 2: 'What is upstream of P-101?' must traverse upstream relationships."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is upstream of P-101?", drawing_id="CDU-P-101"))
    assert res.query_plan.intent == QueryIntent.UPSTREAM
    assert res.query_plan.direction == "INCOMING"
    assert "XV-203" in res.direct_nodes_involved
    assert "Y-101" in res.direct_nodes_involved
    assert "TK-201" in res.direct_nodes_involved
    # Must NOT include downstream check valve CV-101 or PCV-101
    assert "CV-101" not in res.direct_nodes_involved
    assert "PCV-101" not in res.direct_nodes_involved


def test_03_downstream_traversal_p101(pid_engine):
    """TEST 3: 'What is downstream of P-101?' must traverse downstream relationships."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of P-101?", drawing_id="CDU-P-101"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.direction == "OUTGOING"
    assert "CV-101" in res.direct_nodes_involved
    assert "XV-204" in res.direct_nodes_involved
    assert "PCV-101" in res.direct_nodes_involved
    # Must NOT include upstream tank TK-201 or strainer Y-101
    assert "TK-201" not in res.direct_nodes_involved
    assert "Y-101" not in res.direct_nodes_involved


def test_04_protection_path_p101(pid_engine):
    """TEST 4: 'What protects P-101?' must traverse protection relationships."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What protects P-101?", drawing_id="CDU-P-101"))
    assert res.query_plan.intent == QueryIntent.PROTECTION
    assert "PSV-101" in res.direct_nodes_involved
    assert "9.0 barg" in res.answer or "PSV-101" in res.answer


def test_05_psv_discharge_path(pid_engine):
    """TEST 5: 'Where does PSV-101 discharge?' must traverse discharge relationships."""
    res = pid_engine.query_pid(PIDQueryRequest(question="Where does PSV-101 discharge?", drawing_id="CDU-P-101"))
    assert res.query_plan.intent == QueryIntent.PSV_DISCHARGE
    assert "FLARE_HEADER" in res.direct_nodes_involved
    assert "FLARE_HEADER" in res.answer or "Flare" in res.answer


def test_06_instrumentation_query(pid_engine):
    """TEST 6: 'What instruments monitor P-101?' must traverse measurement relationships."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What instruments monitor P-101?", drawing_id="CDU-P-101"))
    assert res.query_plan.intent == QueryIntent.INSTRUMENTATION
    assert any(inst in res.direct_nodes_involved for inst in ["PI-101", "PI-102", "TI-101", "TE-101"])


def test_07_upstream_vs_downstream_differentiation(pid_engine):
    """TEST 7: Upstream and downstream produce materially different traversal plans and nodes."""
    res_up = pid_engine.query_pid(PIDQueryRequest(question="What is upstream of P-201?"))
    res_dn = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of P-201?"))

    assert res_up.query_plan.intent != res_dn.query_plan.intent
    assert res_up.query_plan.direction == "INCOMING"
    assert res_dn.query_plan.direction == "OUTGOING"

    # Set of returned nodes must be distinct
    up_nodes = set(res_up.direct_nodes_involved)
    dn_nodes = set(res_dn.direct_nodes_involved)
    assert up_nodes != dn_nodes
    assert "TK-201" in up_nodes and "TK-201" not in dn_nodes
    assert "PCV-201" in dn_nodes and "PCV-201" not in up_nodes


def test_08_multidrawing_p201(pid_engine):
    """TEST 8: Querying P-201 automatically resolves and traverses CDU-200 drawing."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is upstream of P-201?"))
    assert res.drawing_id in ["MRPL-PID-CDU-200", "CDU-200"]
    assert "Y-201" in res.direct_nodes_involved
    assert "XV-203" in res.direct_nodes_involved
    assert "TK-201" in res.direct_nodes_involved
    assert res.confidence >= 0.95

    # Check isolation for P-201
    res_iso = pid_engine.query_pid(PIDQueryRequest(question="Which valves isolate P-201?"))
    assert "XV-203" in res_iso.direct_nodes_involved
    assert "MOV-204" in res_iso.direct_nodes_involved

    # Check protection for P-201
    res_prot = pid_engine.query_pid(PIDQueryRequest(question="What protects P-201?"))
    assert "PSV-201" in res_prot.direct_nodes_involved


def test_09_unknown_tag_guard(pid_engine):
    """TEST 9: Unknown MRPL tag must be explicitly unresolved/blocked without hallucination."""
    res = pid_engine.query_pid(PIDQueryRequest(question="Which valves isolate XYZ-999?"))
    assert res.status == PIDQueryResultStatus.UNRESOLVED
    assert res.confidence == 0.0
    assert "not present in any registered MRPL" in res.answer
    assert "XYZ-999" in res.answer


def test_10_provenance_linkage(pid_engine):
    """TEST 10: Every graph-derived claim preserves drawing number, document ID, and revision."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What line feeds P-201?"))
    assert res.provenance_records is not None
    assert len(res.provenance_records) > 0
    prov = res.provenance_records[0]
    assert prov.document_id in ["MRPL-PID-CDU-200", "CDU-200"]
    assert prov.source_file == "PID_CDU_200_P201_Crude_Booster_Loop.json"


def test_11_sovereignty_zero_egress(pid_engine):
    """TEST 11: Sovereign execution check - zero external calls."""
    res1 = pid_engine.query_pid(PIDQueryRequest(question="What is upstream of P-201?"))
    res2 = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of P-201?"))
    res3 = pid_engine.query_pid(PIDQueryRequest(question="What protects V-201 in CDU-250?"))

    assert res1.confidence > 0.9
    assert res2.confidence > 0.9
    assert res3.confidence > 0.9

    sov = NetworkEgressGuard.get_sovereignty_status()
    assert sov["air_gap_active"] is True
    assert sov["external_llm_calls"] == 0
    assert sov["data_leaves_machine"] is False

