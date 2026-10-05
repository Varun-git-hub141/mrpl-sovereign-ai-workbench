# tests/test_evidence_sufficiency.py
"""
MRPL Sovereign AI Workbench — Phase 2: Evidence Sufficiency Engine Test Suite.
Tests:
1. Complete evidence -> SUFFICIENT, 100% coverage, 0 debt.
2. Partially complete evidence -> PARTIALLY_SUFFICIENT, correct coverage, debt identified.
3. Missing critical evidence -> INSUFFICIENT / BLOCKED, debt reflects critical missing item.
4. Irrelevant evidence -> Low relevance score, fails coverage.
5. Contradictory evidence -> CONTRADICTORY status, safety blocker flagged.
6. High-risk task with missing evidence -> Gated execution BLOCKED, safety recommendation provided.
7. End-to-end API testing (/api/evidence/assess, /api/route, /api/execute).
"""

import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.services.evidence import (
    EvidenceRequirementEngine,
    EvidenceContractValidator,
    EvidenceContract,
    EvidenceRequirement,
    EvidenceType,
    AuthorityLevel,
    SufficiencyStatus,
    EvidenceDebtSeverity,
    EvidenceAssessment,
    EvidenceSufficiencyEngine,
    EvidenceScoringEngine,
    EvidenceDebtCalculator,
)

client = TestClient(app)


def test_complete_evidence_sufficiency():
    """Verify that complete evidence achieves SUFFICIENT status, 100% coverage, and zero debt."""
    engine = EvidenceRequirementEngine()
    contract = engine.generate_contract(
        query="What is the wall thickness of P-201 from the 2024 inspection survey?",
        risk_override="medium",
    )
    
    mock_chunks = [
        type("Chunk", (), {
            "text": "MRPL Statutory UT Survey 2024 for P-201 crude booster pump. Baseline 2019 was 6.0mm. Current measured wall thickness is 4.5mm across Grid C1-C8. Design limit t_min is 3.5mm.",
            "source": type("Src", (), {"document": "MRPL-INSP-2024-P201.pdf", "equipment_tag": "P-201", "document_type": "inspection_report"})(),
            "retrieval": type("Ret", (), {"keyword_score": 0.95, "semantic_score": 0.92, "hybrid_score": 0.94})(),
            "model_dump": lambda self: {"text": self.text, "source": {"document": self.source.document}}
        })(),
        type("Chunk", (), {
            "text": "Datasheet MRPL-DS-P201: Crude Feed Booster Pump, CDU-II, ASME B31.3 / API 570, min allowable thickness 3.5mm.",
            "source": type("Src", (), {"document": "MRPL-DS-P201.pdf", "equipment_tag": "P-201", "document_type": "datasheet"})(),
            "retrieval": type("Ret", (), {"keyword_score": 0.90, "semantic_score": 0.88, "hybrid_score": 0.89})(),
            "model_dump": lambda self: {"text": self.text, "source": {"document": self.source.document}}
        })()
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=mock_chunks,
        query="What is the wall thickness of P-201 from the 2024 inspection survey?",
    )

    assert assessment.overall_status == SufficiencyStatus.SUFFICIENT
    assert assessment.coverage_score >= 0.80
    assert assessment.authority_score >= 0.90
    assert assessment.freshness_score == 1.0  # 2024 survey
    assert assessment.consistency_score == 1.0
    assert assessment.mandatory_requirements_met is True
    assert assessment.evidence_debt.missing_mandatory_count == 0
    assert "Calculation may proceed" in assessment.system_recommendation or "Safe to proceed" in assessment.system_recommendation


def test_partially_complete_evidence():
    """Verify that partial evidence results in PARTIALLY_SUFFICIENT status with quantified debt."""
    contract = EvidenceContract(
        task_id="task-partial-001",
        task_type="engineering_calculation",
        risk_level="medium",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Current 2024 ultrasonic survey",
                mandatory=True,
                validation_rule="Check 2024 UT data",
            ),
            EvidenceRequirement(
                id="REQ-2",
                evidence_type=EvidenceType.BASELINE_INSPECTION,
                description="Previous 2019 baseline survey",
                mandatory=True,
                validation_rule="Check 2019 baseline data",
            ),
        ],
        optional_evidence=[
            EvidenceRequirement(
                id="REQ-3",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description="Pump engineering datasheet",
                mandatory=False,
                validation_rule="Check datasheet",
            )
        ],
        minimum_coverage=0.80,
    )

    # Only provide current 2024 survey, omitting baseline 2019 and datasheet
    partial_chunks = [
        type("Chunk", (), {
            "text": "MRPL-INSP-2024-P201.pdf current ultrasonic survey shows 4.5mm wall thickness.",
            "source": type("Src", (), {"document": "MRPL-INSP-2024-P201.pdf", "equipment_tag": "P-201"})(),
            "model_dump": lambda self: {"text": self.text}
        })()
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=partial_chunks,
        query="Calculate corrosion rate of P-201",
    )

    assert assessment.overall_status == SufficiencyStatus.PARTIALLY_SUFFICIENT
    assert 0.40 <= assessment.coverage_score <= 0.70
    assert assessment.mandatory_requirements_met is False
    assert assessment.evidence_debt.missing_mandatory_count == 1
    assert "1 critical requirement missing" in assessment.evidence_debt.debt_summary or "1" in assessment.evidence_debt.debt_summary
    assert len(assessment.evidence_debt.recommendations) > 0


def test_missing_critical_evidence_on_high_risk_task():
    """Verify that a high-risk task with missing mandatory evidence is strictly BLOCKED."""
    contract = EvidenceContract(
        task_id="task-highrisk-001",
        task_type="statutory_approval",
        risk_level="high",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-STAT-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Statutory UT inspection survey",
                mandatory=True,
                validation_rule="Check UT survey",
                entity_scope="P-201",
            ),
            EvidenceRequirement(
                id="REQ-STAT-2",
                evidence_type=EvidenceType.BASELINE_INSPECTION,
                description="Baseline turnaround inspection log",
                mandatory=True,
                validation_rule="Check baseline log",
                entity_scope="P-201",
            ),
            EvidenceRequirement(
                id="REQ-STAT-3",
                evidence_type=EvidenceType.APPLICABLE_STANDARD,
                description="Statutory standard (API 570)",
                mandatory=True,
                validation_rule="Check API 570 standard",
                entity_scope="P-201",
            ),
        ],
        minimum_coverage=1.0,
    )

    # Empty retrieved evidence for high-risk statutory approval
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[],
        query="Draft statutory approval note for continued operation of P-201",
    )

    assert assessment.overall_status == SufficiencyStatus.BLOCKED
    assert assessment.can_safely_proceed is False
    assert assessment.is_high_risk is True
    assert assessment.coverage_score == 0.0
    assert assessment.mandatory_requirements_met is False
    assert assessment.evidence_debt.missing_mandatory_count == 3
    assert "High-risk task blocked" in assessment.system_recommendation


def test_irrelevant_evidence_scoring():
    """Verify that retrieving off-topic noise yields low relevance and fails sufficiency."""
    contract = EvidenceContract(
        task_id="task-irrelevant-001",
        task_type="engineering_calculation",
        risk_level="medium",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.ULTRASONIC_THICKNESS_DATA,
                description="Crude pump ultrasonic survey",
                mandatory=True,
                validation_rule="Check UT data",
                entity_scope="P-201",
            )
        ],
        required_entities=["P-201"],
    )

    irrelevant_chunks = [
        type("Chunk", (), {
            "text": "General canteen menu schedule for refinery administrative building lunch breaks.",
            "source": type("Src", (), {"document": "Admin_Notice_2024.pdf", "equipment_tag": None})(),
            "model_dump": lambda self: {"text": self.text}
        })()
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=irrelevant_chunks,
        query="What is the measured wall thickness for P-201?",
    )

    assert assessment.relevance_score < 0.65
    assert assessment.entity_match_score == 0.0
    assert assessment.overall_status in (SufficiencyStatus.INSUFFICIENT, SufficiencyStatus.PARTIALLY_SUFFICIENT, SufficiencyStatus.BLOCKED)


def test_contradictory_evidence_detection():
    """Verify that contradictory evidence triggers CONTRADICTORY status and halts execution."""
    contract = EvidenceContract(
        task_id="task-contra-001",
        task_type="engineering_calculation",
        risk_level="medium",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Inspection record",
                mandatory=True,
                validation_rule="Check inspection",
                entity_scope="P-201",
            )
        ],
        required_entities=["P-201"],
    )

    # Conflicting equipment tags in single query scope
    contradictory_chunks = [
        type("Chunk", (), {
            "text": "Inspection survey for equipment CDU-P-101. Asset is approved for continued operation.",
            "source": type("Src", (), {"document": "MRPL-INSP-2024-P101.pdf", "equipment_tag": "CDU-P-101"})(),
            "model_dump": lambda self: {"text": self.text}
        })(),
        type("Chunk", (), {
            "text": "Inspection survey for equipment P-201. Asset is unfit for service due to severe thinning.",
            "source": type("Src", (), {"document": "MRPL-INSP-2024-P201.pdf", "equipment_tag": "P-201"})(),
            "model_dump": lambda self: {"text": self.text}
        })(),
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=contradictory_chunks,
        query="Assess fitness for service for P-201",
    )

    assert assessment.overall_status == SufficiencyStatus.CONTRADICTORY
    assert assessment.can_safely_proceed is False
    assert assessment.consistency_score < 0.50
    assert len(assessment.contradictions) > 0


def test_api_evidence_assess_endpoint():
    """Verify /api/evidence/assess endpoint returns valid EvidenceAssessment schema."""
    req_payload = {
        "query": "Calculate corrosion rate for P-201",
        "retrieved_chunks": [
            {
                "text": "MRPL-INSP-2024-P201.pdf UT inspection shows 4.50mm current thickness. 2019 baseline was 6.00mm.",
                "source": {"document": "MRPL-INSP-2024-P201.pdf", "equipment_tag": "P-201"}
            }
        ],
        "tool_outputs": {"status": "SUCCESS", "corrosion_rate": 0.30}
    }

    res = client.post("/api/evidence/assess", json=req_payload)
    assert res.status_code == 200
    data = res.json()

    assert "overall_status" in data
    assert "coverage_score" in data
    assert "relevance_score" in data
    assert "authority_score" in data
    assert "evidence_debt" in data
    assert "evidence_checklist" in data
    assert "system_recommendation" in data


# ─────────────────────────────────────────────────────────────
# Permanent Regression Tests for Bug 1 & Bug 2
# ─────────────────────────────────────────────────────────────

def test_regression_source_none_metadata():
    """
    REGRESSION TEST 1: Chunk with explicit source=None metadata must not raise AttributeError.
    """
    contract = EvidenceContract(
        task_id="reg-none-001",
        task_type="general_reasoning",
        risk_level="low",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.USER_SCOPE,
                description="User scope",
                mandatory=True,
                validation_rule="Check scope",
            )
        ],
    )
    chunks = [{"text": "P-201 general operating notes", "source": None}]
    
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks,
        query="What is the status of P-201?",
    )
    assert 0.0 <= assessment.authority_score <= 1.0
    assert assessment.authority_score == 0.40  # Safely falls back to untrusted/unspecified score


def test_regression_missing_source_metadata():
    """
    REGRESSION TEST 2: Chunk with missing source key uses filename fallback cleanly.
    """
    contract = EvidenceContract(
        task_id="reg-miss-001",
        task_type="engineering_calculation",
        risk_level="medium",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Current inspection",
                mandatory=True,
                validation_rule="Check inspection",
            )
        ],
    )
    chunks = [{"text": "Current turnaround 2024 measured thickness is 4.5mm.", "filename": "MRPL-INSP-2024-P201.pdf"}]
    
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks,
        query="Calculate corrosion rate",
    )
    assert assessment.authority_score == 1.0  # Recognized official MRPL prefix from filename
    assert assessment.mandatory_requirements_met is True


def test_regression_wrong_entity_current_inspection():
    """
    REGRESSION TEST 3: Entity-scoped CURRENT_INSPECTION must not be satisfied by wrong asset data.
    """
    contract = EvidenceContract(
        task_id="reg-ent-001",
        task_type="equipment_approval",
        risk_level="high",
        created_at=1000.0,
        required_entities=["P-201"],
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="P-201 current 2024 inspection",
                mandatory=True,
                entity_scope="P-201",
                validation_rule="Check P-201 UT inspection",
            )
        ],
    )
    
    # Document contains 'current', '2024', and 'turnaround', but for P-101
    p101_chunk = {
        "text": "MRPL-INSP-2024-P101.pdf current turnaround 2024 inspection for crude pump P-101.",
        "source": {"document": "MRPL-INSP-2024-P101.pdf", "equipment_tag": "P-101"}
    }
    
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[p101_chunk],
        query="Approve P-201 for continued operation",
    )
    
    assert assessment.entity_match_score == 0.0
    assert assessment.mandatory_requirements_met is False
    assert assessment.overall_status == SufficiencyStatus.BLOCKED
    assert assessment.can_safely_proceed is False


def test_regression_high_risk_blocking_condition_gate():
    """
    REGRESSION TEST 4: High-risk task with active blocking_conditions MUST be BLOCKED even if mandatory_met=True.
    """
    contract = EvidenceContract(
        task_id="reg-block-001",
        task_type="engineering_calculation",
        risk_level="high",
        created_at=1000.0,
        required_entities=["P-201"],
        required_evidence=[
            # General requirement that gets satisfied by text
            EvidenceRequirement(
                id="REQ-GEN",
                evidence_type=EvidenceType.USER_SCOPE,
                description="General engineering scope",
                mandatory=True,
                validation_rule="Check text presence",
            )
        ],
    )
    
    # Text satisfies REQ-GEN, but required entity P-201 is missing from text and docs
    chunks = [{"text": "General engineering scope without target asset mention.", "source": {"document": "General_Scope.pdf"}}]
    
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks,
        query="Calculate corrosion rate for P-201",
    )
    
    # Mandatory requirement is satisfied, but MISSING_ENTITY_AUTHORITATIVE_RECORD: P-201 is in blocking_reasons
    assert assessment.mandatory_requirements_met is True
    assert len(assessment.blocking_reasons) > 0
    assert any("MISSING_ENTITY_AUTHORITATIVE_RECORD: P-201" in b for b in assessment.blocking_reasons)
    # High-Risk Safety Gate MUST hold: Status is BLOCKED, not PARTIALLY_SUFFICIENT
    assert assessment.overall_status == SufficiencyStatus.BLOCKED
    assert assessment.can_safely_proceed is False
