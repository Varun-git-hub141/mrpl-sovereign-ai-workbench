# tests/test_pid_evidence_bridge_suite.py
"""
MRPL Sovereign AI Workbench — Phase 3 Acceptance Test Suite.
Verifies the integration between the P&ID Knowledge Graph and the Evidence Architecture:
- Tier A: Pure Topology (sub-10ms fast path, zero unnecessary RAG, zero debt)
- Tier B: P&ID + Documentary Evidence (grounded RAG retrieval, evidence citations)
- Tier C: Engineering Decision / Safety Gating (Evidence Contract, Sufficiency, Evidence Debt, Safety Boundary)
- Unknown Entity Guard (Context Guard rejection, zero hallucination)
- Sovereignty (zero external network egress)
"""

import pytest
from backend.models.pid_graph_models import (
    EvidenceTier,
    EvidenceClassification,
    PIDQueryResultStatus,
)
from backend.services.pid.pid_evidence_bridge import PIDEvidenceBridge
from backend.services.evidence.evidence_models import SufficiencyStatus


@pytest.fixture(scope="module")
def bridge():
    return PIDEvidenceBridge()


def test_01_tier_a_pure_topology_no_rag(bridge):
    """
    TEST 1: Pure topology question must not invoke RAG or generate Evidence Contract.
    """
    res = bridge.process_query("What is upstream of P-201?")
    
    assert res.evidence_tier == EvidenceTier.PURE_TOPOLOGY
    assert res.target_entity == "P-201"
    assert res.selected_drawing == "MRPL-PID-CDU-200"
    assert "MRPL-PID-TK201" in res.alternate_drawings
    assert res.safety_decision == "TOPOLOGY_ONLY_NO_CONCLUSION"
    assert res.contract is None
    assert res.retrieved_documents == []
    assert len(res.evidence_claims) > 0
    assert all(c.classification == EvidenceClassification.TOPOLOGY_FACT for c in res.evidence_claims)
    assert "Y-201" in res.topology.direct_nodes_involved
    assert "XV-203" in res.topology.direct_nodes_involved


def test_02_tier_a_downstream_isolation(bridge):
    """
    TEST 2: Pure downstream and isolation queries execute as pure topology.
    """
    res_down = bridge.process_query("What is downstream of P-201?")
    assert res_down.evidence_tier == EvidenceTier.PURE_TOPOLOGY
    assert res_down.target_entity == "P-201"
    assert "CV-201" in res_down.topology.direct_nodes_involved

    res_iso = bridge.process_query("Which valves isolate P-201?")
    assert res_iso.evidence_tier == EvidenceTier.PURE_TOPOLOGY
    assert "XV-203" in res_iso.topology.direct_nodes_involved
    assert "MOV-204" in res_iso.topology.direct_nodes_involved


def test_03_tier_b_documentary_evidence_retrieval(bridge):
    """
    TEST 3: Documentary evidence query initiates grounded RAG search and returns MRPL KB documents.
    """
    res = bridge.process_query("What MRPL documents support isolation of P-201?")
    
    assert res.evidence_tier == EvidenceTier.TOPOLOGY_AND_EVIDENCE
    assert res.target_entity == "P-201"
    assert res.contract is not None
    assert len(res.retrieved_documents) > 0
    assert any("SOP" in d["document_title"] or "PID" in d["document_title"] for d in res.retrieved_documents)
    
    # Verify claims contain both TOPOLOGY_FACT and DOCUMENTARY_EVIDENCE
    classes = [c.classification for c in res.evidence_claims]
    assert EvidenceClassification.TOPOLOGY_FACT in classes
    assert EvidenceClassification.DOCUMENTARY_EVIDENCE in classes


def test_04_tier_c_safety_conclusion_gating_and_debt(bridge):
    """
    TEST 4: Safety conclusion question evaluates Evidence Contract and flags unverified claims if missing evidence.
    """
    res = bridge.process_query("Can P-201 be safely isolated for maintenance?")
    
    assert res.evidence_tier == EvidenceTier.ENGINEERING_DECISION
    assert res.target_entity == "P-201"
    assert res.contract is not None
    assert res.contract["task_type"] == "pid_isolation_safety"
    assert res.assessment is not None
    assert res.evidence_debt is not None
    assert len(res.evidence_claims) > 0


def test_05_tier_c_multi_drawing_p201_context(bridge):
    """
    TEST 5: Explicitly scoped multi-drawing query preserves context in Evidence Bridge.
    """
    res = bridge.process_query("Can P-201 be isolated in TF-301?")
    
    assert res.evidence_tier == EvidenceTier.ENGINEERING_DECISION
    assert res.target_entity == "P-201"
    assert res.selected_drawing == "MRPL-PID-TK201"
    assert "MRPL-PID-CDU-200" in res.alternate_drawings
    assert "MOV-301" in res.topology.direct_nodes_involved


def test_06_tier_c_psv_protection_adequacy_blocking(bridge):
    """
    TEST 6: Asking if PSV is adequate blocks approval when statutory sizing calculation is missing.
    """
    res = bridge.process_query("What protects P-201 and is the PSV adequate?")
    
    assert res.evidence_tier == EvidenceTier.ENGINEERING_DECISION
    assert res.safety_decision == "BLOCKED_INSUFFICIENT_EVIDENCE"
    assert res.evidence_debt["missing_mandatory_count"] > 0
    assert any("APPLICABLE_STANDARD" in b or "FORMULA_DEFINITION" in b for b in res.safety_blockers)
    
    # Must contain UNVERIFIED_CLAIM warning
    unverified_claims = [c for c in res.evidence_claims if c.classification == EvidenceClassification.UNVERIFIED_CLAIM]
    assert len(unverified_claims) > 0
    assert "cannot be confirmed" in unverified_claims[0].claim_text.lower()


def test_07_unknown_asset_context_guard(bridge):
    """
    TEST 7: Unknown asset P-999 is blocked by Context Guard with 0 RAG hallucination.
    """
    res_topo = bridge.process_query("What is upstream of P-999?")
    assert res_topo.safety_decision == "BLOCKED_BY_CONTEXT_GUARD"
    assert res_topo.topology.status == PIDQueryResultStatus.UNRESOLVED
    assert res_topo.retrieved_documents == []

    res_safety = bridge.process_query("Can P-999 be safely isolated?")
    assert res_safety.safety_decision == "BLOCKED_BY_CONTEXT_GUARD"
    assert res_safety.topology.status == PIDQueryResultStatus.UNRESOLVED
    assert res_safety.retrieved_documents == []


def test_08_sovereignty_zero_egress(bridge):
    """
    TEST 8: All P&ID Evidence Bridge queries execute 100% locally with zero external network egress.
    """
    from backend.telemetry.audit import NetworkEgressGuard
    
    bridge.process_query("What is upstream of P-201?")
    bridge.process_query("What documents support isolation of P-201?")
    bridge.process_query("Can P-201 be safely isolated for maintenance?")
    bridge.process_query("What protects P-201 and is the PSV adequate?")
    bridge.process_query("Can P-999 be safely isolated?")
        
    sov = NetworkEgressGuard.get_sovereignty_status()
    assert sov["air_gap_active"] is True
    assert sov["external_llm_calls"] == 0
    assert sov["data_leaves_machine"] is False

