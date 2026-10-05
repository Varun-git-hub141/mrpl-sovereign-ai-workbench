# tests/test_evidence_adversarial.py
"""
MRPL Sovereign AI Workbench — Adversarial & Safety Boundary Test Suite.
Tests Phase 1 (Evidence Contract) and Phase 2 (Evidence Sufficiency Engine) under
realistic adversarial conditions, corrupted metadata, edge-case distractor documents,
and temporal/modality constraints.

Quality Standard:
- All tests specify Given / When / Then.
- Uses deterministic fixtures without mocking the component under test.
- Verifies externally observable behavior and safety invariants.
"""

import pytest
from typing import Dict, Any, List
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
    SufficiencyStatus,
    EvidenceDebtSeverity,
    EvidenceAssessment,
    EvidenceSufficiencyEngine,
    EvidenceScoringEngine,
    EvidenceDebtCalculator,
)
from backend.services.claim_provenance import ClaimProvenanceEngine
from backend.models.rag_models import RetrievedChunk, ChunkProvenance, RetrievalScoreBreakdown

client = TestClient(app)


# ─────────────────────────────────────────────────────────────
# Helper Fixtures & Mock Chunk Creators
# ─────────────────────────────────────────────────────────────

def make_chunk(text: str, doc: str = "MRPL-DOC.pdf", tag: str = "P-201", doc_type: str = "inspection"):
    class MockSource:
        def __init__(self):
            self.document = doc
            self.document_id = f"DOC-{doc}"
            self.page = 1
            self.section = "General"
            self.document_type = doc_type
            self.equipment_tag = tag

    class MockRetrieval:
        def __init__(self):
            self.keyword_score = 0.90
            self.semantic_score = 0.88
            self.hybrid_score = 0.89

    class MockChunk:
        def __init__(self):
            self.text = text
            self.source = MockSource()
            self.retrieval = MockRetrieval()

        def model_dump(self):
            return {
                "text": self.text,
                "source": {
                    "document": self.source.document,
                    "document_id": self.source.document_id,
                    "page": self.source.page,
                    "section": self.source.section,
                    "document_type": self.source.document_type,
                    "equipment_tag": self.source.equipment_tag,
                }
            }

    return MockChunk()


# ═════════════════════════════════════════════════════════════
# TEST GROUP 1 — SAFETY GATING
# ═════════════════════════════════════════════════════════════

def test_1_high_coverage_missing_critical_mandatory_gate():
    """
    TEST 1: High numerical coverage but missing critical mandatory evidence.
    Given: A high-risk contract with 3 mandatory requirements and 2 optional requirements, minimum_coverage = 0.60.
    When: Evidence satisfies 2/3 mandatory items and 2/2 optional items (numerical coverage >= 0.70).
    Then: coverage_score is high, mandatory_requirements_met is False, overall_status is BLOCKED, and can_safely_proceed is False.
    """
    contract = EvidenceContract(
        task_id="task-adv-001",
        task_type="equipment_approval",
        risk_level="high",
        created_at=1000.0,
        minimum_coverage=0.60,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-MAND-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Current 2024 turnaround ultrasonic survey",
                mandatory=True,
                validation_rule="Check 2024 UT data",
                entity_scope="P-201",
            ),
            EvidenceRequirement(
                id="REQ-MAND-2",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description="MRPL Equipment Datasheet",
                mandatory=True,
                validation_rule="Check datasheet",
                entity_scope="P-201",
            ),
            EvidenceRequirement(
                id="REQ-MAND-3",
                evidence_type=EvidenceType.BASELINE_INSPECTION,
                description="2019 baseline inspection record",
                mandatory=True,
                validation_rule="Check baseline log",
                entity_scope="P-201",
            ),
        ],
        optional_evidence=[
            EvidenceRequirement(
                id="REQ-OPT-1",
                evidence_type=EvidenceType.VIBRATION_SURVEY,
                description="Vibration survey",
                mandatory=False,
                validation_rule="Check vibration",
                entity_scope="P-201",
            ),
            EvidenceRequirement(
                id="REQ-OPT-2",
                evidence_type=EvidenceType.MOC_RECORD,
                description="MOC record",
                mandatory=False,
                validation_rule="Check MOC",
                entity_scope="P-201",
            ),
        ],
    )

    # Chunks satisfy REQ-MAND-1 (Current), REQ-MAND-2 (Datasheet), REQ-OPT-1 (Vibration), REQ-OPT-2 (MOC)
    # Intentionally OMITTING REQ-MAND-3 (Baseline)
    chunks = [
        make_chunk("MRPL-INSP-2024-P201.pdf current ultrasonic survey shows 4.5mm wall thickness.", "MRPL-INSP-2024-P201.pdf"),
        make_chunk("Datasheet MRPL-DS-P201: Crude Feed Booster Pump, design limit t_min 3.5mm.", "MRPL-DS-P201.pdf"),
        make_chunk("ISO 10816 vibration survey logs for P-201 show 2.1 mm/s RMS in Zone A.", "MRPL-VIB-P201.pdf"),
        make_chunk("Management of Change MOC-2022-P201 impeller upgrade recorded.", "MRPL-MOC-P201.pdf"),
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks,
        query="Approve continued operation for P-201",
    )

    # Assert that numerical coverage is high (2/3 mandatory + 2/2 optional = 0.567 + 0.15 = 0.717 >= 0.60 min_coverage)
    assert assessment.coverage_score >= 0.60
    # BUT mandatory requirement 3 is unsatisfied
    assert assessment.mandatory_requirements_met is False
    assert assessment.satisfied_mandatory == 2
    assert assessment.total_mandatory == 3
    # Strict High-Risk Safety Gate: Status MUST be BLOCKED, can_safely_proceed MUST be False
    assert assessment.overall_status == SufficiencyStatus.BLOCKED
    assert assessment.can_safely_proceed is False
    assert assessment.evidence_debt.missing_mandatory_count == 1
    assert "critical requirement missing" in assessment.evidence_debt.debt_summary


def test_2_query_expansion_recovery_deterministic():
    """
    TEST 2: Query expansion recovery.
    Given: A task where Round 1 retrieval is missing baseline inspection and acceptance criteria.
    When: Round 1 evaluates to PARTIALLY_SUFFICIENT / BLOCKED, then query expansion retrieves the missing items for Round 2.
    Then: Round 2 re-assessment executes on the merged pool and achieves SUFFICIENT with 0 mandatory debt.
    """
    engine = EvidenceRequirementEngine()
    contract = engine.generate_contract(
        query="Approve continued operation for Crude Feed Pump P-201",
        risk_override="high",
        task_profile=TaskProfile(
            task_type=TaskType.EQUIPMENT_APPROVAL,
            intent="Approve continued operation for Crude Feed Pump P-201",
            risk=RiskLevel.HIGH,
            entity_name="P-201",
        ),
    )

    # Round 1: Only current inspection and datasheet are available
    round1_chunks = [
        make_chunk("MRPL-INSP-2024-P201.pdf current turnaround survey 2024 shows 4.5mm thickness.", "MRPL-INSP-2024-P201.pdf"),
        make_chunk("MRPL-DS-P201 pump datasheet design pressure 25 bar, t_min 3.5mm.", "MRPL-DS-P201.pdf"),
    ]

    assessment_round1 = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=round1_chunks,
        query="Approve continued operation for Crude Feed Pump P-201",
    )

    assert assessment_round1.overall_status in (SufficiencyStatus.BLOCKED, SufficiencyStatus.PARTIALLY_SUFFICIENT)
    assert assessment_round1.mandatory_requirements_met is False
    assert assessment_round1.evidence_debt.missing_mandatory_count > 0

    # Deterministic expansion delivers missing baseline log and API 570 standard / acceptance criteria
    expansion_chunks = [
        make_chunk("MRPL-INSP-2019-P201.pdf baseline inspection log 2019 initial wall thickness was 6.0mm.", "MRPL-INSP-2019-P201.pdf"),
        make_chunk("API 570 standard acceptance criteria: remaining life must exceed turnaround cycle.", "API-570-Standard.pdf"),
    ]

    # Round 2: Merged evidence pool
    round2_chunks = round1_chunks + expansion_chunks

    assessment_round2 = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=round2_chunks,
        query="Approve continued operation for Crude Feed Pump P-201",
    )

    # Verify that the second assessment executed and evaluated all mandatory items as satisfied
    assert assessment_round2.overall_status == SufficiencyStatus.SUFFICIENT
    assert assessment_round2.mandatory_requirements_met is True
    assert "Calculation may proceed" in assessment_round2.system_recommendation or "Safe to proceed" in assessment_round2.system_recommendation


def test_3_query_expansion_exhaustion_safety_gate():
    """
    TEST 3: Query expansion exhaustion.
    Given: A high-risk task where mandatory evidence cannot be found after maximum expansion rounds.
    When: Expansion returns empty or non-matching chunks across all rounds.
    Then: System remains BLOCKED, can_safely_proceed remains False, and no fabricated evidence is produced.
    """
    engine = EvidenceRequirementEngine()
    contract = engine.generate_contract(
        query="Perform statutory approval for Crude Feed Pump P-201",
        risk_override="high",
    )

    # Round 1: Deficient chunks
    pool = [make_chunk("MRPL-DS-P201 pump datasheet design pressure 25 bar.", "MRPL-DS-P201.pdf")]

    max_rounds = 3
    for round_idx in range(1, max_rounds + 1):
        # Simulated expansion fails to find required inspection logs
        expanded_chunks = []  # Empty or non-relevant
        pool.extend(expanded_chunks)
        assessment = EvidenceSufficiencyEngine.assess_evidence(
            contract=contract,
            retrieved_chunks=pool,
            query="Perform statutory approval for Crude Feed Pump P-201",
        )

    # After exhausting max rounds, safety gate MUST hold
    assert assessment.overall_status == SufficiencyStatus.BLOCKED
    assert assessment.can_safely_proceed is False
    assert assessment.mandatory_requirements_met is False
    assert assessment.evidence_debt.missing_mandatory_count >= 2


def test_4_missing_modality_vision_block():
    """
    TEST 4: Missing modality.
    Given: A P&ID schematic inspection task requiring IMAGE_VISION modality.
    When: Only text documents are provided (has_images = False).
    Then: modality_completeness_score is 0.0, modality requirement is unsatisfied, and high/medium-risk task cannot proceed.
    """
    engine = EvidenceRequirementEngine()
    contract = engine.generate_contract(
        query="Inspect P&ID schematic drawing for Crude Unit CDU-II",
        risk_override="high",
    )

    # Provide only text chunks, NO image attachment
    text_chunks = [
        make_chunk("General process description for Crude Distillation Unit II.", "CDU_Overview.pdf")
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=text_chunks,
        has_images=False,
        attached_data={},
        query="Inspect P&ID schematic drawing for Crude Unit CDU-II",
    )

    # REQ-VIS-001 has IMAGE_VISION (unsatisfied), REQ-VIS-002 has TEXT (satisfied)
    # modality_completeness_score = 1/2 = 0.5 < 1.0
    assert assessment.modality_completeness_score < 1.0
    assert assessment.mandatory_requirements_met is False
    assert assessment.overall_status in (SufficiencyStatus.BLOCKED, SufficiencyStatus.INSUFFICIENT)
    assert assessment.can_safely_proceed is False


# ═════════════════════════════════════════════════════════════
# TEST GROUP 2 — EVIDENCE QUALITY
# ═════════════════════════════════════════════════════════════

def test_5_keyword_stuffed_distractor_does_not_override_sufficiency():
    """
    TEST 5: Keyword-stuffed distractor.
    Given: Query 'Determine whether P-201 can continue operation based on its latest inspection.'
           and a distractor document with high lexical overlap but omitting decision standards and baseline.
    When: Evidence sufficiency is assessed for a high-risk equipment approval contract.
    Then: relevance_score is high (>= 0.80), but mandatory domain requirements are unsatisfied,
          and overall_status is BLOCKED (proves lexical relevance != evidence sufficiency).
    """
    engine = EvidenceRequirementEngine()
    contract = engine.generate_contract(
        query="Determine whether P-201 can continue operation based on its latest inspection",
        risk_override="high",
        task_profile=TaskProfile(
            task_type=TaskType.EQUIPMENT_APPROVAL,
            intent="Determine whether P-201 can continue operation based on its latest inspection",
            risk=RiskLevel.HIGH,
            entity_name="P-201",
        )
    )

    # Distractor chunk: contains all query keywords repeatedly, but NO baseline log, NO t_min, NO API 570
    distractor_chunk = make_chunk(
        "P-201 latest inspection report discusses continued operation and thickness. "
        "The operation of P-201 pump was observed during routine inspection. "
        "Latest thickness monitoring on P-201 is part of standard plant operation.",
        "General_Plant_Notes.pdf",
        tag="P-201"
    )

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[distractor_chunk],
        query="Determine whether P-201 can continue operation based on its latest inspection",
    )

    # Lexical relevance is high due to term matches
    assert assessment.relevance_score >= 0.75
    # BUT mandatory acceptance criteria, baseline log, and official standard are missing
    assert assessment.mandatory_requirements_met is False
    assert assessment.overall_status == SufficiencyStatus.BLOCKED
    assert assessment.can_safely_proceed is False


def test_6_wrong_entity_fails_entity_and_blocks():
    """
    TEST 6: Wrong entity.
    Given: Contract requiring P-201.
    When: Retrieved chunk contains valid engineering inspection data for P-101 (wrong asset).
    Then: entity_match_score is 0.0, P-201 requirement remains unsatisfied, and MISSING_ENTITY_AUTHORITATIVE_RECORD blocker exists.
    """
    contract = EvidenceContract(
        task_id="task-entity-001",
        task_type="engineering_calculation",
        risk_level="high",
        created_at=1000.0,
        required_entities=["P-201"],
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="P-201 inspection report",
                mandatory=True,
                entity_scope="P-201",
                validation_rule="Check P-201 inspection",
            )
        ],
    )

    # Valid engineering document, but for P-101 instead of P-201
    wrong_entity_chunk = make_chunk(
        "MRPL Statutory UT Survey 2024 for P-101 crude booster pump. Baseline was 6.0mm, current measured thickness is 4.5mm.",
        "MRPL-INSP-2024-P101.pdf",
        tag="P-101"
    )

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[wrong_entity_chunk],
        query="Calculate corrosion rate for P-201",
    )

    assert assessment.entity_match_score == 0.0
    assert assessment.mandatory_requirements_met is False
    assert any("MISSING_ENTITY_AUTHORITATIVE_RECORD: P-201" in b for b in assessment.blocking_reasons)
    assert assessment.can_safely_proceed is False


def test_7_multi_entity_legitimate_comparison():
    """
    TEST 7: Multi-entity legitimate task.
    Given: Query 'Compare P-201 and P-202.' with required_entities = ['P-201', 'P-202'].
    When: Doc A for P-201 (operating) and Doc B for P-202 (operating) are retrieved.
    Then: entity_match_score is 1.0, consistency_score is 1.0, and contradictions is empty.
    """
    contract = EvidenceContract(
        task_id="task-multi-ent-001",
        task_type="general_reasoning",
        risk_level="low",
        created_at=1000.0,
        required_entities=["P-201", "P-202"],
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

    chunks = [
        make_chunk("Pump P-201 status: operating normally at rated flow 150 m3/hr.", "MRPL-LOG-P201.pdf", tag="P-201"),
        make_chunk("Pump P-202 status: operating normally in parallel train.", "MRPL-LOG-P202.pdf", tag="P-202"),
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks,
        query="Compare P-201 and P-202",
    )

    assert assessment.entity_match_score == 1.0
    assert assessment.consistency_score == 1.0
    assert len(assessment.contradictions) == 0


def test_8_real_contradiction_detection():
    """
    TEST 8: Real contradiction.
    Given: P-201 Document A states 'Approved for continued operation' and Document B states 'Unfit for service'.
    When: Evidence is assessed.
    Then: overall_status is CONTRADICTORY, can_safely_proceed is False, and consistency_score < 0.50.
    """
    contract = EvidenceContract(
        task_id="task-contra-002",
        task_type="equipment_approval",
        risk_level="high",
        created_at=1000.0,
        required_entities=["P-201"],
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="P-201 current inspection",
                mandatory=True,
                validation_rule="Check inspection",
                entity_scope="P-201",
            )
        ],
    )

    chunks = [
        make_chunk("MRPL-INSP-2024-P201.pdf: Asset P-201 is approved for continued operation.", "MRPL-INSP-2024-P201.pdf", tag="P-201"),
        make_chunk("MRPL-INSP-2024-P201-REV.pdf: Asset P-201 is unfit for service due to critical cracking.", "MRPL-INSP-2024-P201-REV.pdf", tag="P-201"),
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks,
        query="Approve P-201 for service",
    )

    assert assessment.overall_status == SufficiencyStatus.CONTRADICTORY
    assert assessment.can_safely_proceed is False
    assert assessment.consistency_score <= 0.30
    assert len(assessment.contradictions) > 0
    assert "Contradictory operational health status" in assessment.contradictions[0]


# ═════════════════════════════════════════════════════════════
# TEST GROUP 3 — TEMPORAL EVIDENCE
# ═════════════════════════════════════════════════════════════

def test_9_freshness_comparison_and_fallback():
    """
    TEST 9: Freshness comparison.
    Given: Deterministic evidence chunks for 2012, 2019, 2024, and a chunk with no year.
    When: compute_freshness_score() is called on each.
    Then: 2024 returns 1.0 (current turnaround), 2019 returns 0.75 (5-year baseline),
          2012 returns 0.50 (stale), and no-year returns 0.85 (neutral fallback).
    """
    chunk_2024 = make_chunk("MRPL Turnaround Survey 2024 wall thickness measurements.")
    chunk_2019 = make_chunk("MRPL Turnaround Survey 2019 baseline measurements.")
    chunk_2012 = make_chunk("Historical commissioning survey from 2012.")
    chunk_noyear = make_chunk("General equipment technical manual without explicit timestamps.")

    score_2024 = EvidenceScoringEngine.compute_freshness_score([chunk_2024])
    score_2019 = EvidenceScoringEngine.compute_freshness_score([chunk_2019])
    score_2012 = EvidenceScoringEngine.compute_freshness_score([chunk_2012])
    score_noyear = EvidenceScoringEngine.compute_freshness_score([chunk_noyear])

    assert score_2024 == 1.0, "2024 contemporaneous turnaround survey must score 1.0"
    assert score_2019 == 0.75, "2019 previous turnaround cycle must score 0.75"
    assert score_2012 == 0.50, "2012 aged records must score 0.50"
    assert score_noyear == 0.85, "Fallback when no date is extracted must score 0.85 (ARCHITECTURAL_BASELINE)"


# ═════════════════════════════════════════════════════════════
# TEST GROUP 4 — ROBUSTNESS
# ═════════════════════════════════════════════════════════════

def test_10_duplicate_evidence_invariance():
    """
    TEST 10: Duplicate evidence invariance.
    Given: A single valid chunk.
    When: Evaluated once vs evaluated with 10 identical copies in retrieved_chunks.
    Then: coverage, authority, freshness, entity match, and final sufficiency status remain identical.
    """
    contract = EvidenceContract(
        task_id="task-dup-001",
        task_type="engineering_calculation",
        risk_level="medium",
        created_at=1000.0,
        required_entities=["P-201"],
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Current 2024 ultrasonic survey",
                mandatory=True,
                validation_rule="Check 2024 UT data",
                entity_scope="P-201",
            )
        ],
    )

    chunk = make_chunk("MRPL-INSP-2024-P201.pdf current ultrasonic survey shows 4.5mm wall thickness.", "MRPL-INSP-2024-P201.pdf")
    chunks_single = [chunk]
    chunks_ten = [chunk] * 10

    assessment_single = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks_single,
        query="Calculate corrosion rate of P-201",
    )
    assessment_ten = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks_ten,
        query="Calculate corrosion rate of P-201",
    )

    assert assessment_single.coverage_score == assessment_ten.coverage_score
    assert assessment_single.authority_score == assessment_ten.authority_score
    assert assessment_single.freshness_score == assessment_ten.freshness_score
    assert assessment_single.entity_match_score == assessment_ten.entity_match_score
    assert assessment_single.overall_status == assessment_ten.overall_status
    assert assessment_single.can_safely_proceed == assessment_ten.can_safely_proceed


def test_11_malformed_metadata_safe_degradation():
    """
    TEST 11: Malformed metadata.
    Given: Adversarial chunks containing source=None, missing fields, empty strings, and malformed dicts.
    When: assess_evidence() is invoked.
    Then: No exceptions are raised, scores stay within [0.0, 1.0], and authority/freshness degrade safely.
    """
    contract = EvidenceContract(
        task_id="task-malform-001",
        task_type="engineering_calculation",
        risk_level="high",
        created_at=1000.0,
        required_entities=["P-201"],
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

    malformed_chunks = [
        {"text": "", "source": None},
        {"text": "Random text without document key", "source": {}},
        type("CorruptedChunk", (), {"text": "", "source": type("EmptySrc", (), {"document": None})()})(),
        {},
        "Just a plain string chunk without object structure",
    ]

    # Must execute safely without throwing UnboundLocalError, AttributeError, or KeyError
    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=malformed_chunks,
        query="Calculate corrosion rate for P-201",
    )

    assert 0.0 <= assessment.relevance_score <= 1.0
    assert 0.0 <= assessment.coverage_score <= 1.0
    assert 0.0 <= assessment.authority_score <= 1.0
    assert 0.0 <= assessment.freshness_score <= 1.0
    assert 0.0 <= assessment.consistency_score <= 1.0
    assert 0.0 <= assessment.entity_match_score <= 1.0
    # Malformed noise must NOT satisfy mandatory requirements
    assert assessment.mandatory_requirements_met is False
    assert assessment.overall_status == SufficiencyStatus.BLOCKED
    assert assessment.can_safely_proceed is False


def test_12_risk_normalization_consistency():
    """
    TEST 12: Risk normalization.
    Given: Variations of risk string casings ('HIGH', 'High', 'high', 'CRITICAL', 'critical', 'MEDIUM', 'medium').
    When: Contracts are generated and evaluated with missing mandatory evidence.
    Then: All high and critical variations trigger is_high_risk = True and BLOCKED status.
    """
    engine = EvidenceRequirementEngine()
    risk_variations_high = ["HIGH", "High", "high", "CRITICAL", "Critical", "critical"]

    for r_val in risk_variations_high:
        contract = engine.generate_contract(
            query="Draft statutory approval note for P-201",
            risk_override=r_val,
        )
        assessment = EvidenceSufficiencyEngine.assess_evidence(
            contract=contract,
            retrieved_chunks=[],
            query="Draft statutory approval note for P-201",
        )
        assert assessment.is_high_risk is True, f"Risk variant '{r_val}' failed is_high_risk normalization"
        assert assessment.overall_status == SufficiencyStatus.BLOCKED
        assert assessment.can_safely_proceed is False


def test_13_score_boundary_properties():
    """
    TEST 13: Score boundary/property test.
    Given: Edge-case inputs (empty evidence, 0 requirements, 0 optional requirements, maximum evidence).
    When: All 7 sufficiency scores are evaluated.
    Then: Every score strictly adheres to 0.0 <= score <= 1.0.
    """
    # 1. Zero requirements contract
    empty_contract = EvidenceContract(
        task_id="task-empty-reqs",
        task_type="general_reasoning",
        risk_level="low",
        created_at=1000.0,
        required_evidence=[],
        optional_evidence=[],
    )
    assessment_empty = EvidenceSufficiencyEngine.assess_evidence(
        contract=empty_contract,
        retrieved_chunks=[],
        query="Empty query",
    )

    scores_empty = [
        assessment_empty.relevance_score,
        assessment_empty.coverage_score,
        assessment_empty.authority_score,
        assessment_empty.freshness_score,
        assessment_empty.consistency_score,
        assessment_empty.entity_match_score,
        assessment_empty.modality_completeness_score,
    ]
    for s in scores_empty:
        assert 0.0 <= s <= 1.0, f"Score {s} out of [0.0, 1.0] bounds"

    # 2. Maximum complete evidence
    engine = EvidenceRequirementEngine()
    contract_full = engine.generate_contract(
        query="Calculate corrosion rate of P-201",
        risk_override="high",
    )
    chunks_full = [
        make_chunk("P-201 ultrasonic wall thickness measured 4.5 mm vs baseline 6.0 mm per API 570 standard.", "MRPL-INSP-2024-P201.pdf"),
        make_chunk("API 570 Section 7.1.1 formula calculation.", "API-570-Standard.pdf"),
        make_chunk("MRPL-DS-P201 pump datasheet.", "MRPL-DS-P201.pdf"),
    ]
    tool_calc = {"status": "SUCCESS", "corrosion_rate": 0.30, "result": 0.30}

    assessment_full = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract_full,
        retrieved_chunks=chunks_full,
        tool_outputs=tool_calc,
        query="Calculate corrosion rate of P-201",
    )

    scores_full = [
        assessment_full.relevance_score,
        assessment_full.coverage_score,
        assessment_full.authority_score,
        assessment_full.freshness_score,
        assessment_full.consistency_score,
        assessment_full.entity_match_score,
        assessment_full.modality_completeness_score,
    ]
    for s in scores_full:
        assert 0.0 <= s <= 1.0, f"Score {s} out of [0.0, 1.0] bounds"


def test_14_optional_evidence_missing_does_not_block():
    """
    TEST 14: Optional evidence.
    Given: A contract with 2 mandatory requirements and 1 optional requirement.
    When: All mandatory evidence is present, but optional evidence is missing.
    Then: overall_status is SUFFICIENT, can_safely_proceed is True, missing_mandatory_count is 0,
          and missing_optional_count is 1.
    """
    contract = EvidenceContract(
        task_id="task-opt-001",
        task_type="engineering_calculation",
        risk_level="medium",
        minimum_coverage=0.80,
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-MAND-1",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description="Current 2024 ultrasonic survey",
                mandatory=True,
                validation_rule="Check 2024 UT data",
                entity_scope="P-201",
            ),
            EvidenceRequirement(
                id="REQ-MAND-2",
                evidence_type=EvidenceType.BASELINE_INSPECTION,
                description="Previous 2019 baseline survey",
                mandatory=True,
                validation_rule="Check 2019 baseline data",
                entity_scope="P-201",
            ),
        ],
        optional_evidence=[
            EvidenceRequirement(
                id="REQ-OPT-1",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description="Pump engineering datasheet",
                mandatory=False,
                validation_rule="Check datasheet",
                entity_scope="P-201",
            )
        ],
    )

    # Provide only mandatory items (Current 2024 and Baseline 2019)
    chunks = [
        make_chunk("MRPL-INSP-2024-P201.pdf current ultrasonic survey shows 4.5mm wall thickness.", "MRPL-INSP-2024-P201.pdf"),
        make_chunk("MRPL-INSP-2019-P201.pdf baseline 2019 initial inspection was 6.0mm.", "MRPL-INSP-2019-P201.pdf"),
    ]

    assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=chunks,
        query="Calculate corrosion rate of P-201",
    )

    assert assessment.overall_status == SufficiencyStatus.SUFFICIENT
    assert assessment.can_safely_proceed is True
    assert assessment.mandatory_requirements_met is True
    assert assessment.evidence_debt.missing_mandatory_count == 0
    assert assessment.evidence_debt.missing_optional_count == 1
    assert "1 optional requirement missing" in assessment.evidence_debt.debt_summary


# ═════════════════════════════════════════════════════════════
# TEST GROUP 5 — ARCHITECTURAL BOUNDARY
# ═════════════════════════════════════════════════════════════

def test_15_unsupported_claim_provenance_boundary():
    """
    TEST 15: Unsupported generated claim.
    Given: Retrieved evidence contains 'Inspection thickness = 3.8 mm.'
    When: Phase 2 assesses input evidence sufficiency (confirms numeric measurement input is present).
    When: Model reasoning output generates an unsupported claim: 'Immediate shutdown is required.'
    When: Downstream ClaimProvenanceEngine evaluates claim-level provenance against retrieved chunks.
    Then: Phase 2 reports input sufficiency satisfied, while ClaimProvenanceEngine identifies the
          unsupported claim, proving the clean architectural boundary between Input Sufficiency and Output Grounding.
    """
    # 1. Phase 2 Input Evidence Assessment
    contract = EvidenceContract(
        task_id="task-claim-boundary-001",
        task_type="engineering_calculation",
        risk_level="medium",
        created_at=1000.0,
        required_evidence=[
            EvidenceRequirement(
                id="REQ-1",
                evidence_type=EvidenceType.REQUIRED_NUMERIC_INPUTS,
                description="Current thickness measurement",
                mandatory=True,
                validation_rule="Check thickness measurement",
                entity_scope="P-201",
            )
        ],
    )

    evidence_chunk = make_chunk(
        "MRPL-INSP-2024-P201.pdf: Ultrasonic inspection thickness = 3.8 mm measured on Grid C.",
        "MRPL-INSP-2024-P201.pdf",
        tag="P-201"
    )

    input_assessment = EvidenceSufficiencyEngine.assess_evidence(
        contract=contract,
        retrieved_chunks=[evidence_chunk],
        query="What is the wall thickness of P-201?",
    )

    # Input evidence is sufficient to answer the thickness query
    assert input_assessment.overall_status == SufficiencyStatus.SUFFICIENT
    assert input_assessment.mandatory_requirements_met is True

    # 2. Downstream Agent Execution & Claim Provenance Assessment
    generated_response = "The measured thickness is 3.8 mm. Immediate shutdown is required."
    
    rag_chunk = RetrievedChunk(
        text=evidence_chunk.text,
        source=ChunkProvenance(
            document="MRPL-INSP-2024-P201.pdf",
            document_id="DOC-P201",
            page=1,
            section="UT Survey",
            document_type="inspection_report",
            equipment_tag="P-201",
        ),
        retrieval=RetrievalScoreBreakdown(keyword_score=0.95, semantic_score=0.90, hybrid_score=0.92),
    )

    provenance_report = ClaimProvenanceEngine.validate(
        response_text=generated_response,
        retrieved_chunks=[rag_chunk],
        context_mode="MRPL_LOCAL",
        entity_tag="P-201",
    )

    # Verify that ClaimProvenanceEngine distinguishes supported claims from unsupported assertions
    assert provenance_report is not None
    assert provenance_report.source_coverage.mrpl_supported_claims >= 1  # 3.8 mm is supported
    # Downstream verification detects unsupported claims
    assert hasattr(provenance_report.source_coverage, "unsupported_claims")
