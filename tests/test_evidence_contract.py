# tests/test_evidence_contract.py
"""
MRPL Sovereign AI Workbench — Evidence Contract Test Suite.
Tests EvidenceRequirementEngine, EvidenceContract models, contract validation,
and REST API endpoints for Phase 1: Evidence Contract.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.models.task_profile import TaskProfile, TaskType, RiskLevel
from backend.services.evidence import (
    EvidenceRequirementEngine,
    EvidenceContractValidator,
    EvidenceContract,
    EvidenceRequirement,
    EvidenceType,
    AuthorityLevel,
    EvidenceModality,
)


@pytest.fixture
def evidence_engine():
    return EvidenceRequirementEngine()


@pytest.fixture
def client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────
# 1. Unit Tests for Contract Generation across Task Types
# ─────────────────────────────────────────────────────────────

def test_generate_calculation_contract(evidence_engine):
    task = TaskProfile(
        task_type=TaskType.ENGINEERING_CALCULATION,
        intent="Calculate corrosion rate and remaining life for P-201",
        risk=RiskLevel.HIGH,
        entity_name="P-201",
    )
    contract = evidence_engine.generate_contract(task_profile=task)

    assert contract is not None
    assert contract.task_type == "engineering_calculation"
    assert contract.risk_level == "high"
    assert "P-201" in contract.required_entities
    assert len(contract.required_evidence) >= 3

    # Check required calculation evidence
    req_types = [r.evidence_type for r in contract.required_evidence]
    assert EvidenceType.REQUIRED_NUMERIC_INPUTS in req_types
    assert EvidenceType.APPLICABLE_STANDARD in req_types
    assert EvidenceType.FORMULA_DEFINITION in req_types
    assert EvidenceType.UNITS_SPECIFICATION in req_types

    # Check optional datasheet evidence
    opt_types = [r.evidence_type for r in contract.optional_evidence]
    assert EvidenceType.EQUIPMENT_DATASHEET in opt_types

    # Check security declaration
    assert "0 tool permissions" in contract.security_notice


def test_generate_approval_contract(evidence_engine):
    task = TaskProfile(
        task_type=TaskType.EQUIPMENT_APPROVAL,
        intent="Prepare statutory approval note for continued operation of P-201",
        risk=RiskLevel.HIGH,
        entity_name="P-201",
    )
    contract = evidence_engine.generate_contract(task_profile=task)

    assert contract.task_type == "equipment_approval"
    assert contract.required_source_authority == AuthorityLevel.AUTHORITATIVE_PSU
    assert "P-201" in contract.required_entities

    req_types = [r.evidence_type for r in contract.required_evidence]
    assert EvidenceType.CURRENT_INSPECTION in req_types
    assert EvidenceType.BASELINE_INSPECTION in req_types
    assert EvidenceType.EQUIPMENT_DATASHEET in req_types
    assert EvidenceType.ACCEPTANCE_CRITERIA in req_types


def test_generate_presentation_contract(evidence_engine):
    task = TaskProfile(
        task_type=TaskType.MEMO_SUMMARIZATION,
        intent="create a presentation on boiler feed water treatment",
        risk=RiskLevel.LOW,
    )
    contract = evidence_engine.generate_contract(
        task_profile=task,
        query="create a presentation on boiler feed water treatment"
    )

    assert contract.task_type == "presentation_generation"
    req_types = [r.evidence_type for r in contract.required_evidence]
    assert EvidenceType.USER_SCOPE in req_types
    assert EvidenceType.FACTUAL_ASSERTIONS in req_types


def test_generate_coding_contract(evidence_engine):
    task = TaskProfile(
        task_type=TaskType.CODE_GENERATION,
        intent="Write a python script to compute API 570 corrosion rates",
        risk=RiskLevel.LOW,
    )
    contract = evidence_engine.generate_contract(task_profile=task)

    assert contract.task_type == "code_generation"
    req_types = [r.evidence_type for r in contract.required_evidence]
    assert EvidenceType.FUNCTIONAL_REQUIREMENTS in req_types
    assert EvidenceType.TEST_CRITERIA in req_types


def test_generate_vision_contract(evidence_engine):
    contract = evidence_engine.generate_contract(
        query="Inspect this P&ID diagram for Crude Feed Booster Pump P-101A",
        files=[{"name": "pid_drawing.png", "type": "image/png", "base64_data": "iVBORw0KGgoAAAANSUhEUgAA"}]
    )

    assert contract.task_type == "vision_p_and_id"
    assert contract.required_source_authority == AuthorityLevel.USER_PROVIDED_ATTACHMENT
    req_types = [r.evidence_type for r in contract.required_evidence]
    assert EvidenceType.P_AND_ID_SCHEMATIC in req_types


def test_generate_general_contract(evidence_engine):
    contract = evidence_engine.generate_contract(
        query="Explain the difference between centrifugal and positive displacement pumps"
    )

    assert contract.task_type == "general_reasoning"
    req_types = [r.evidence_type for r in contract.required_evidence]
    assert EvidenceType.USER_SCOPE in req_types
    assert EvidenceType.GENERAL_KNOWLEDGE_DECLARATION in req_types


# ─────────────────────────────────────────────────────────────
# 2. Tests for Mandatory vs Optional Evidence & Evaluation
# ─────────────────────────────────────────────────────────────

def test_mandatory_vs_optional_evidence_flags(evidence_engine):
    task = TaskProfile(task_type=TaskType.EQUIPMENT_APPROVAL, entity_name="P-201")
    contract = evidence_engine.generate_contract(task_profile=task)

    for req in contract.required_evidence:
        assert req.mandatory is True
        assert req.authority_requirement in (AuthorityLevel.AUTHORITATIVE_PSU, AuthorityLevel.STANDARD_OPERATING_PROCEDURE, AuthorityLevel.VERIFIED_ENGINEERING_RECORD)

    for opt in contract.optional_evidence:
        assert opt.mandatory is False


def test_contract_evaluation_satisfied(evidence_engine):
    task = TaskProfile(task_type=TaskType.ENGINEERING_CALCULATION, entity_name="P-201")
    contract = evidence_engine.generate_contract(task_profile=task)

    # Simulated retrieved chunks containing API 570, thickness, and standard data
    class MockChunk:
        def __init__(self, text, doc):
            self.text = text
            self.source = type('Src', (), {'document': doc, 'document_id': 'DOC-1', 'page': 1, 'section': 'UT', 'document_type': 'Inspection', 'equipment_tag': 'P-201'})()

    mock_chunks = [
        MockChunk("P-201 ultrasonic wall thickness measured 4.5 mm vs baseline 6.0 mm per API 570 standard.", "MRPL-INSP-2024-P201.pdf"),
        MockChunk("API 570 Section 7.1.1 corrosion rate formula calculation.", "API-570-Standard.pdf"),
    ]
    mock_calc = {"status": "SUCCESS", "corrosion_rate": 0.30, "result": 0.30}

    evaluated = EvidenceContractValidator.evaluate_contract(
        contract=contract,
        retrieved_chunks=mock_chunks,
        tool_outputs=mock_calc,
    )

    assert evaluated.is_satisfied is True
    assert evaluated.satisfaction_ratio == 1.0
    assert len(evaluated.blocking_conditions) == 0


def test_contract_evaluation_unsatisfied_blocking(evidence_engine):
    task = TaskProfile(task_type=TaskType.ENGINEERING_CALCULATION, entity_name="P-999")
    contract = evidence_engine.generate_contract(task_profile=task)

    # Evaluated with 0 retrieved evidence chunks
    evaluated = EvidenceContractValidator.evaluate_contract(
        contract=contract,
        retrieved_chunks=[],
        tool_outputs={},
    )

    assert evaluated.is_satisfied is False
    assert evaluated.satisfaction_ratio < 1.0
    assert len(evaluated.blocking_conditions) > 0
    assert any("UNSATISFIED_MANDATORY_EVIDENCE" in b for b in evaluated.blocking_conditions)


# ─────────────────────────────────────────────────────────────
# 3. REST API Endpoint Tests
# ─────────────────────────────────────────────────────────────

def test_api_generate_evidence_contract(client):
    payload = {
        "query": "Perform statutory calculation and evaluate wall thickness for P-201",
        "risk_override": "high",
        "task_type": "engineering_calculation",
        "entity_name": "P-201"
    }
    response = client.post("/api/evidence/contract", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "task_id" in data
    assert data["task_type"] == "engineering_calculation"
    assert "required_evidence" in data
    assert len(data["required_evidence"]) >= 3
    assert "optional_evidence" in data
    assert "security_notice" in data
    assert "UNTRUSTED_DATA_BOUNDARY" in data["security_notice"]


def test_api_route_includes_evidence_contract(client):
    payload = {
        "query": "Evaluate remaining life and corrosion rate for Crude Feed Pump P-201",
        "risk_override": "high"
    }
    response = client.post("/api/route", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "evidence_contract" in data
    contract = data["evidence_contract"]
    assert "required_evidence" in contract
    assert "optional_evidence" in contract
    assert "blocking_conditions" in contract
    assert contract["task_type"] in ("engineering_calculation", "equipment_approval", "general_reasoning")
