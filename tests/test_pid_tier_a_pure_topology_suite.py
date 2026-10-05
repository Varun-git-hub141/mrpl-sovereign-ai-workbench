import pytest
from backend.services.pid_graph_engine import PIDGraphEngine
from backend.services.pid.pid_evidence_bridge import PIDEvidenceBridge
from backend.models.pid_graph_models import (
    PIDQueryRequest,
    PIDQueryResultStatus,
    QueryIntent,
    EvidenceTier,
)
from backend.telemetry.audit import get_live_sovereignty_telemetry


@pytest.fixture
def pid_engine():
    return PIDGraphEngine()


@pytest.fixture
def evidence_bridge(pid_engine):
    return PIDEvidenceBridge(pid_engine=pid_engine)


# ═══════════════════════════════════════════════════════════════
# EXACT 8 LIVE QUESTIONS TEST MATRIX
# ═══════════════════════════════════════════════════════════════

def test_tier_a_01_upstream_p201(pid_engine):
    """1. What is upstream of P-201? -> UPSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is upstream of P-201?"))
    assert res.query_plan.intent == QueryIntent.UPSTREAM
    assert res.query_plan.target_entity == "P-201"
    assert "**Drawing:**\nMRPL-PID-CDU-200" in res.answer or "**Drawing:**" in res.answer
    assert "**Target:**\nP-201" in res.answer
    assert "**Operation:**\nUPSTREAM" in res.answer
    assert "**Immediate result:**" in res.answer
    assert "**Extended topology:**" in res.answer
    assert "**Explanation:**" in res.answer
    assert "**Source:**" in res.answer
    assert "Y-201" in res.direct_nodes_involved or "XV-203" in res.direct_nodes_involved


def test_tier_a_02_downstream_p201(pid_engine):
    """2. What is downstream of P-201? -> DOWNSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of P-201?"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "P-201"
    assert "**Target:**\nP-201" in res.answer
    assert "**Operation:**\nDOWNSTREAM" in res.answer
    assert "CV-201" in res.direct_nodes_involved or "MOV-204" in res.direct_nodes_involved


def test_tier_a_03_isolates_p201(pid_engine):
    """3. Which valves isolate P-201? -> ISOLATES"""
    res = pid_engine.query_pid(PIDQueryRequest(question="Which valves isolate P-201?"))
    assert res.query_plan.intent == QueryIntent.ISOLATION
    assert res.query_plan.target_entity == "P-201"
    assert "**Target:**\nP-201" in res.answer
    assert "**Operation:**\nISOLATES" in res.answer
    assert "DIRECT P&ID ISOLATION RELATIONSHIP" in res.answer or "DERIVED TOPOLOGY INTERPRETATION" in res.answer
    assert "XV-203" in res.direct_nodes_involved  # Suction block
    assert "MOV-204" in res.direct_nodes_involved  # Discharge block
    assert "CV-201" not in res.direct_nodes_involved  # Check valve excluded


def test_tier_a_04_discharges_psv201(pid_engine):
    """4. Where does PSV-201 discharge? -> DISCHARGES (Safety Valve)"""
    res = pid_engine.query_pid(PIDQueryRequest(question="Where does PSV-201 discharge?"))
    assert res.query_plan.intent == QueryIntent.PSV_DISCHARGE
    assert res.query_plan.target_entity == "PSV-201"
    assert "**Target:**\nPSV-201" in res.answer
    assert "**Operation:**\nDISCHARGES" in res.answer
    assert "FLARE_HEADER" in res.direct_nodes_involved


def test_tier_a_05_upstream_xv201(pid_engine):
    """5. What is upstream of XV-201? -> UPSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is upstream of XV-201?"))
    assert res.query_plan.intent == QueryIntent.UPSTREAM
    assert res.query_plan.target_entity == "XV-201"
    assert "**Target:**\nXV-201" in res.answer
    assert "**Operation:**\nUPSTREAM" in res.answer
    assert "TK-201" in res.direct_nodes_involved


def test_tier_a_06_downstream_xv201(pid_engine):
    """6. What is downstream of XV-201? -> DOWNSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of XV-201?"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "XV-201"
    assert "**Target:**\nXV-201" in res.answer
    assert "**Operation:**\nDOWNSTREAM" in res.answer
    assert "Y-101" in res.direct_nodes_involved or "Y-201" in res.direct_nodes_involved


def test_tier_a_07_downstream_xv203(pid_engine):
    """7. What is downstream of XV-203? -> DOWNSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of XV-203?"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "XV-203"
    assert "**Target:**\nXV-203" in res.answer
    assert "**Operation:**\nDOWNSTREAM" in res.answer


def test_tier_a_08_discharges_xv201(pid_engine):
    """8. Where does XV-201 discharge? -> DOWNSTREAM (Process Valve, not PSV)"""
    res = pid_engine.query_pid(PIDQueryRequest(question="Where does XV-201 discharge?"))
    # Process valve discharge MUST resolve to DOWNSTREAM, NOT PSV_DISCHARGE
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "XV-201"
    assert "**Target:**\nXV-201" in res.answer
    assert "**Operation:**\nDOWNSTREAM" in res.answer
    assert "Y-101" in res.direct_nodes_involved or "Y-201" in res.direct_nodes_involved


# ═══════════════════════════════════════════════════════════════
# NATURAL-LANGUAGE VARIATIONS
# ═══════════════════════════════════════════════════════════════

def test_variation_01_what_feeds_p201(pid_engine):
    """'What feeds P-201?' -> UPSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What feeds P-201?"))
    assert res.query_plan.intent == QueryIntent.UPSTREAM
    assert res.query_plan.target_entity == "P-201"
    assert "**Operation:**\nUPSTREAM" in res.answer


def test_variation_02_what_comes_before_p201(pid_engine):
    """'What comes before P-201?' -> UPSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What comes before P-201?"))
    assert res.query_plan.intent == QueryIntent.UPSTREAM
    assert res.query_plan.target_entity == "P-201"
    assert "**Operation:**\nUPSTREAM" in res.answer


def test_variation_03_whats_after_p201(pid_engine):
    """'What's after P-201?' -> DOWNSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What's after P-201?"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "P-201"
    assert "**Operation:**\nDOWNSTREAM" in res.answer


def test_variation_04_what_does_p201_feed(pid_engine):
    """'What does P-201 feed?' -> DOWNSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What does P-201 feed?"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "P-201"
    assert "**Operation:**\nDOWNSTREAM" in res.answer


def test_variation_05_where_does_xv201_send_flow(pid_engine):
    """'Where does XV-201 send flow?' -> DOWNSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="Where does XV-201 send flow?"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "XV-201"
    assert "**Operation:**\nDOWNSTREAM" in res.answer


def test_variation_06_what_is_connected_downstream_of_xv203(pid_engine):
    """'What is connected downstream of XV-203?' -> DOWNSTREAM"""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is connected downstream of XV-203?"))
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert res.query_plan.target_entity == "XV-203"
    assert "**Operation:**\nDOWNSTREAM" in res.answer


# ═══════════════════════════════════════════════════════════════
# CRITICAL NEGATIVE TESTS
# ═══════════════════════════════════════════════════════════════

def test_negative_01_p201_downstream_not_p101(pid_engine):
    """1. 'What is downstream of P-201?' cannot return P-101 topology."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of P-201?"))
    assert res.query_plan.target_entity == "P-201"
    assert "P-101" not in res.direct_nodes_involved
    assert "CV-101" not in res.direct_nodes_involved
    assert "XV-204" not in res.direct_nodes_involved


def test_negative_02_xv201_discharges_not_psv(pid_engine):
    """2. 'Where does XV-201 discharge?' cannot enter PSV discharge logic."""
    res = pid_engine.query_pid(PIDQueryRequest(question="Where does XV-201 discharge?"))
    assert res.query_plan.intent != QueryIntent.PSV_DISCHARGE
    assert res.query_plan.intent == QueryIntent.DOWNSTREAM
    assert "**Operation:**\nDOWNSTREAM" in res.answer


def test_negative_03_cv201_not_credited_as_isolation_valve(pid_engine):
    """3. 'Which valves isolate P-201?' cannot credit CV-201 as an isolation valve."""
    res = pid_engine.query_pid(PIDQueryRequest(question="Which valves isolate P-201?"))
    assert "CV-201" not in res.direct_nodes_involved
    assert "Check valve" in res.answer or "non-return" in res.answer
    assert "is not classified as an isolation valve" in res.answer


def test_negative_04_unknown_entity_guard(pid_engine, evidence_bridge):
    """4. Unknown entity 'P-999' must NOT invent answers."""
    res = pid_engine.query_pid(PIDQueryRequest(question="What is downstream of P-999?"))
    assert res.status == PIDQueryResultStatus.UNRESOLVED
    assert "is not present in any registered MRPL P&ID drawing" in res.answer

    bridge_res = evidence_bridge.process_query("What is downstream of P-999?")
    assert bridge_res.safety_decision == "BLOCKED_BY_CONTEXT_GUARD"


def test_sovereignty_zero_egress(evidence_bridge):
    """Verifies that all topology operations run with 0 external network egress."""
    res1 = evidence_bridge.process_query("What is upstream of P-201?")
    res2 = evidence_bridge.process_query("What is downstream of P-201?")
    res3 = evidence_bridge.process_query("Which valves isolate P-201?")
    res4 = evidence_bridge.process_query("Where does PSV-201 discharge?")

    assert res1.evidence_tier == EvidenceTier.PURE_TOPOLOGY
    assert res2.evidence_tier == EvidenceTier.PURE_TOPOLOGY
    assert res3.evidence_tier == EvidenceTier.PURE_TOPOLOGY
    assert res4.evidence_tier == EvidenceTier.PURE_TOPOLOGY

    telemetry = get_live_sovereignty_telemetry()
    assert telemetry["data_egress_bytes"] == 0
    assert telemetry["external_calls"] == 0
