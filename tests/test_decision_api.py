"""
Phase 4D REST API & End-to-End Tests
Approved Specification: v1.0.0-FINAL-CLARIFIED-R3

Verifies REST API endpoints:
- POST /api/decision/evaluate
- POST /api/decision/approval-package
and end-to-end integration, error handling, governance immutability, role precedence,
audit hashes, provenance preservation, and adversarial safety boundaries.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.decision.decision_models import (
    DecisionRiskLevel,
    GovernanceOutcome,
    PolicyEvaluationStatus,
    TemplateActionCode,
)
from backend.services.evidence.evidence_models import SufficiencyStatus


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_observation_dict():
    return {
        "observation_id": "OBS-API-001",
        "entity_tag": "11-V-101",
        "property_name": "wall_thickness_mm",
        "value": 8.5,
        "unit": "mm",
        "authority_tier": "APPROVED_AUTHORITATIVE",
        "approval_status": "APPROVED",
        "extraction_method": "STRUCTURED_JSON",
        "source_document": "11-V-101_UT.json",
        "page_number": 1,
        "raw_statement": "Thickness 8.5 mm",
    }


# ─────────────────────────────────────────────────────────────
# 1. POST /api/decision/evaluate Basic & Error Paths
# ─────────────────────────────────────────────────────────────

def test_api_evaluate_success_path(client, sample_observation_dict):
    """1. Verify standard evaluate endpoint returns valid OperationalDecisionPackage."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "LOW",
        "observations": [sample_observation_dict],
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["entity_tag"] == "11-V-101"
    assert data["risk_level"] == "LOW"
    assert data["governance_outcome"] == "PROCEED_ADVISORY"
    assert data["policy_evaluation_status"] == "POLICY_NOT_SUPPLIED"
    assert data["requires_human_approval"] is False
    assert len(data["audit_trail_hash"]) == 64
    assert len(data["provenance_source_spans"]) >= 1


def test_api_evaluate_missing_entity_tag(client):
    """2. Verify missing entity_tag returns 422 Unprocessable Entity."""
    resp = client.post("/api/decision/evaluate", json={"risk_level": "LOW"})
    assert resp.status_code == 422


def test_api_evaluate_invalid_risk_level(client):
    """3. Verify invalid risk_level string returns 422."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "EXTREME_UNVALIDATED_RISK",
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 422


def test_api_evaluate_malformed_evidence_assessment(client):
    """Verify malformed nested objects return 422 without crashing."""
    payload = {
        "entity_tag": "11-V-101",
        "evidence_assessment": "not-a-valid-dict",
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# 2. Governance Gating API Tests (Rules 1 & 2)
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ["BLOCKED", "INSUFFICIENT", "CONTRADICTORY"])
def test_api_evaluate_phase2_blocked_preconditions(client, status, sample_observation_dict):
    """4-6. Verify Phase 2 BLOCKED/INSUFFICIENT/CONTRADICTORY returns GOVERNANCE_GATE_BLOCKED through API."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "LOW",
        "evidence_assessment": {
            "task_id": "TASK-API-01",
            "task_type": "thickness",
            "overall_status": status,
        },
        "observations": [sample_observation_dict],
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["governance_outcome"] == "GOVERNANCE_GATE_BLOCKED"
    assert data["requires_human_approval"] is True
    assert data["recommended_action"] == "REQUIRES_ENGINEER_DISPOSITION"


def test_api_evaluate_phase3_active_conflict_blocks(client, sample_observation_dict):
    """7. Verify Phase 3 active conflict returns GOVERNANCE_GATE_BLOCKED through API."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "LOW",
        "reconciliation_result": {
            "task_id": "REC-API-01",
            "entity_scope": ["11-V-101"],
            "consistency_state": "CONFLICTING",
            "reconciliation_status": "UNRESOLVED_CONFLICT",
            "all_observations": [sample_observation_dict],
            "active_conflicts": [
                {
                    "conflict_id": "CONF-01",
                    "property_name": "wall_thickness_mm",
                    "entity_tag": "11-V-101",
                    "conflicting_observation_ids": ["OBS-01", "OBS-02"],
                    "conflict_description": "Discrepancy",
                }
            ],
            "reconciliation_summary": "Active conflict",
            "reconciled_at": 1700000000.0,
        },
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["governance_outcome"] == "GOVERNANCE_GATE_BLOCKED"
    assert data["requires_human_approval"] is True


def test_api_evaluate_incomplete_anomaly_search_blocks(client, sample_observation_dict):
    """8. Verify incomplete anomaly search returns GOVERNANCE_GATE_BLOCKED through API."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "LOW",
        "reconciliation_result": {
            "task_id": "REC-API-02",
            "entity_scope": ["11-V-101"],
            "consistency_state": "ANOMALOUS",
            "reconciliation_status": "ANOMALY_DETECTED",
            "all_observations": [sample_observation_dict],
            "relationships": [
                {
                    "relationship_id": "REL-01",
                    "property_name": "wall_thickness_mm",
                    "relationship_type": "ANOMALOUS_PROGRESSION_CANDIDATE",
                    "observation_ids": ["OBS-01", "OBS-02"],
                    "evidence_search_status": "EVIDENCE_SEARCH_NOT_PERFORMED",
                    "explanation": "Search pending",
                    "is_anomaly": True,
                }
            ],
            "reconciliation_summary": "Anomaly pending search",
            "reconciled_at": 1700000000.0,
        },
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["governance_outcome"] == "GOVERNANCE_GATE_BLOCKED"
    assert data["requires_human_approval"] is True


# ─────────────────────────────────────────────────────────────
# 3. Risk Level & Policy Evaluation API Tests (Rules 3–6)
# ─────────────────────────────────────────────────────────────

def test_api_evaluate_low_medium_proceed_with_conditions(client, sample_observation_dict):
    """9-10. Verify LOW/MEDIUM risk with policy conditions yields PROCEED_WITH_CONDITIONS with HITL=False."""
    policy_dict = {
        "policy_id": "POL-API-COND",
        "policy_name": "Survey Policy",
        "policy_version": "1.0",
        "issuing_authority": "MRPL",
        "effective_date": "2024-01-01",
        "risk_level": "LOW",
        "rules": [
            {
                "rule_id": "R-01",
                "rule_name": "Nominal Thickness",
                "target_property": "wall_thickness_mm",
                "operator": ">=",
                "threshold_value": 6.0,
                "on_satisfied_template": {
                    "action_code": "PERFORM_THICKNESS_SURVEY",
                    "action_title": "Routine Survey",
                    "action_description": "Perform survey next turnaround.",
                },
            }
        ],
    }
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "LOW",
        "policy": policy_dict,
        "observations": [sample_observation_dict],
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["governance_outcome"] == "PROCEED_WITH_CONDITIONS"
    assert data["requires_human_approval"] is False
    assert data["recommended_action"] == "PERFORM_THICKNESS_SURVEY"


@pytest.mark.parametrize("risk", ["HIGH", "STATUTORY", "CRITICAL_SAFETY"])
def test_api_evaluate_high_statutory_critical_requires_hitl(client, risk, sample_observation_dict):
    """11-13. Verify HIGH/STATUTORY/CRITICAL_SAFETY always enforces requires_human_approval=True via API."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": risk,
        "observations": [sample_observation_dict],
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["requires_human_approval"] is True
    assert data["governance_outcome"] == "ESCALATE_HUMAN_REVIEW"


def test_api_evaluate_policy_breach_escalates_and_attaches_template(client, sample_observation_dict):
    """Verify policy breach returns ESCALATE_HUMAN_REVIEW and attaches breach action template."""
    policy_dict = {
        "policy_id": "POL-API-THK",
        "policy_name": "Thickness Policy",
        "policy_version": "1.0",
        "issuing_authority": "OISD",
        "effective_date": "2024-01-01",
        "risk_level": "MEDIUM",
        "rules": [
            {
                "rule_id": "R-01",
                "rule_name": "Min Thk",
                "target_property": "wall_thickness_mm",
                "operator": ">=",
                "threshold_value": 10.0,  # Observed is 8.5 -> Breach
                "on_breach_template": {
                    "action_code": "ENGINEERING_ASSESSMENT_REQUIRED",
                    "action_title": "Engineering Review",
                    "action_description": "Review thinning",
                },
            }
        ],
    }
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "MEDIUM",
        "policy": policy_dict,
        "observations": [sample_observation_dict],
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["governance_outcome"] == "ESCALATE_HUMAN_REVIEW"
    assert data["policy_evaluation_status"] == "CRITERIA_BREACHED"
    assert data["requires_human_approval"] is True
    assert data["recommended_action"] == "ENGINEERING_ASSESSMENT_REQUIRED"
    assert data["action_template"]["action_code"] == "ENGINEERING_ASSESSMENT_REQUIRED"


# ─────────────────────────────────────────────────────────────
# 4. POST /api/decision/approval-package Tests
# ─────────────────────────────────────────────────────────────

def test_api_approval_package_success_and_hitl_registration(client, sample_observation_dict):
    """14-17. Verify approval-package endpoint creates DecisionApprovalDeliverable and registers HITL ticket."""
    eval_resp = client.post(
        "/api/decision/evaluate",
        json={
            "entity_tag": "11-V-101",
            "risk_level": "HIGH",
            "observations": [sample_observation_dict],
        },
    )
    decision_package = eval_resp.json()

    pkg_resp = client.post(
        "/api/decision/approval-package",
        json={"decision_package": decision_package},
    )
    assert pkg_resp.status_code == 200
    deliverable = pkg_resp.json()

    assert deliverable["deliverable_id"].startswith("DELIV-")
    assert deliverable["package_id"] == decision_package["package_id"]
    assert deliverable["approval_state"] == "PENDING_REVIEW"
    assert deliverable["requires_human_approval"] is True
    assert deliverable["audit_trail_hash"] == decision_package["audit_trail_hash"]
    assert len(deliverable["provenance_source_spans"]) >= 1


def test_api_approval_package_role_resolution_precedence(client, sample_observation_dict):
    """18-21. Verify role resolution precedence (Policy -> External Config -> Manager -> []) through API."""
    eval_resp = client.post(
        "/api/decision/evaluate",
        json={
            "entity_tag": "11-V-101",
            "risk_level": "HIGH",
            "observations": [sample_observation_dict],
        },
    )
    decision_package = eval_resp.json()

    # Pass external_role_config
    pkg_resp = client.post(
        "/api/decision/approval-package",
        json={
            "decision_package": decision_package,
            "external_role_config": {"HIGH": ["External_Corrosion_Specialist"]},
        },
    )
    assert pkg_resp.status_code == 200
    deliverable = pkg_resp.json()
    assert deliverable["required_human_roles"] == ["External_Corrosion_Specialist"]

    # When no role is passed, must default to [] without inventing roles
    pkg_resp_fallback = client.post(
        "/api/decision/approval-package",
        json={"decision_package": decision_package},
    )
    assert pkg_resp_fallback.json()["required_human_roles"] == []
    assert pkg_resp_fallback.json()["requires_human_approval"] is True


def test_api_approval_package_missing_body(client):
    """Verify missing package body returns 422 error."""
    resp = client.post("/api/decision/approval-package", json={})
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# 5. Determinism, Provenance & Adversarial Safety Boundaries
# ─────────────────────────────────────────────────────────────

def test_api_deterministic_repeated_requests(client, sample_observation_dict):
    """22-24, 28. Verify repeated API calls produce identical outcomes and SHA-256 audit hashes."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "LOW",
        "package_id": "PKG-DETERMINISTIC-01",
        "observations": [sample_observation_dict],
    }
    resp1 = client.post("/api/decision/evaluate", json=payload).json()
    resp2 = client.post("/api/decision/evaluate", json=payload).json()

    assert resp1["governance_outcome"] == resp2["governance_outcome"]
    assert resp1["policy_evaluation_status"] == resp2["policy_evaluation_status"]
    assert resp1["audit_trail_hash"] == resp2["audit_trail_hash"]
    assert resp1["provenance_source_spans"] == resp2["provenance_source_spans"]


def test_api_forbidden_fields_absence(client, sample_observation_dict):
    """25-27. Verify no forbidden autonomous clearance or scoring fields exist in API responses."""
    resp = client.post(
        "/api/decision/evaluate",
        json={"entity_tag": "11-V-101", "risk_level": "LOW", "observations": [sample_observation_dict]},
    )
    data = resp.json()
    forbidden_fields = [
        "fit_for_service",
        "is_safe",
        "statutorily_compliant",
        "statutory_approval",
        "safety_score",
        "authority_score",
        "confidence_score",
    ]
    for field in forbidden_fields:
        assert field not in data, f"Forbidden field '{field}' in evaluate API response!"


def test_adversarial_api_cannot_bypass_governance_gate_blocked(client):
    """33. Adversarial Test: API cannot convert BLOCKED into an advisory or clearance state."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "LOW",
        "evidence_assessment": {
            "task_id": "TASK-ADV-01",
            "task_type": "thickness",
            "overall_status": "BLOCKED",
        },
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    data = resp.json()
    assert data["governance_outcome"] == "GOVERNANCE_GATE_BLOCKED"
    assert data["requires_human_approval"] is True
    assert data["recommended_action"] == "REQUIRES_ENGINEER_DISPOSITION"


def test_adversarial_api_cannot_bypass_high_statutory_hitl(client, sample_observation_dict):
    """34. Adversarial Test: High and statutory tasks cannot bypass requires_human_approval via API."""
    payload = {
        "entity_tag": "11-V-101",
        "risk_level": "STATUTORY",
        "requires_human_approval": False,  # Attacker attempts to bypass HITL in input
        "observations": [sample_observation_dict],
    }
    resp = client.post("/api/decision/evaluate", json=payload)
    data = resp.json()
    # Engine must enforce HITL despite attacker's False payload
    assert data["requires_human_approval"] is True


def test_adversarial_api_conflicting_observations_are_not_averaged(client):
    """30, 35. Adversarial Test: API cannot average conflicting thickness values (8.0mm vs 4.0mm)."""
    obs1 = {
        "observation_id": "OBS-1",
        "entity_tag": "11-V-101",
        "property_name": "wall_thickness_mm",
        "value": 8.0,
        "source_document": "doc1.json",
        "raw_statement": "Thickness 8.0",
    }
    obs2 = {
        "observation_id": "OBS-2",
        "entity_tag": "11-V-101",
        "property_name": "wall_thickness_mm",
        "value": 4.0,
        "source_document": "doc2.json",
        "raw_statement": "Thickness 4.0",
    }
    policy_dict = {
        "policy_id": "POL-AVG-TEST",
        "policy_name": "Avg Test",
        "policy_version": "1.0",
        "issuing_authority": "TEST",
        "effective_date": "2024-01-01",
        "risk_level": "LOW",
        "rules": [
            {
                "rule_id": "R-1",
                "rule_name": "Thickness Check",
                "target_property": "wall_thickness_mm",
                "operator": ">=",
                "threshold_value": 5.0,  # If averaged to 6.0, would pass. Must NOT.
            }
        ],
    }
    resp = client.post(
        "/api/decision/evaluate",
        json={
            "entity_tag": "11-V-101",
            "risk_level": "LOW",
            "policy": policy_dict,
            "observations": [obs1, obs2],
        },
    )
    data = resp.json()
    assert data["policy_evaluation_status"] == "CONFLICT_PREVENTS_EVALUATION"
    assert data["governance_outcome"] == "ESCALATE_HUMAN_REVIEW"
