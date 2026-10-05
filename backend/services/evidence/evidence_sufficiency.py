# backend/services/evidence/evidence_sufficiency.py
"""
MRPL Sovereign AI Workbench — Evidence Sufficiency Engine.
Determines whether retrieved evidence satisfies the EvidenceContract prerequisites for safe execution.
Integrates:
- Multi-dimensional scoring (Relevance, Coverage, Authority, Freshness, Consistency, Entity Match, Modality)
- Deterministic Evidence Debt evaluation
- Contradiction & conflict detection
- High-risk safety gating (Abstain/Block when critical evidence is missing)
"""

import time
import logging
from typing import Dict, Any, List, Optional
from backend.services.evidence.evidence_models import (
    EvidenceContract,
    EvidenceRequirement,
    EvidenceAssessment,
    SufficiencyStatus,
    EvidenceDebt,
    AuthorityLevel,
)
from backend.services.evidence.evidence_contract import EvidenceContractValidator
from backend.services.evidence.evidence_scoring import EvidenceScoringEngine
from backend.services.evidence.evidence_debt import EvidenceDebtCalculator

logger = logging.getLogger("mrpl.evidence.sufficiency")


class EvidenceSufficiencyEngine:
    """
    Evaluates evidence sufficiency for MRPL industrial operations.
    Guarantees that high-risk engineering calculations and approval notes are never executed
    on insufficient or contradictory evidence without explicit safeguards.
    """

    @classmethod
    def assess_evidence(
        cls,
        contract: EvidenceContract,
        retrieved_chunks: Optional[List[Any]] = None,
        attached_data: Optional[Dict[str, Any]] = None,
        tool_outputs: Optional[Dict[str, Any]] = None,
        has_images: bool = False,
        query: str = "",
        is_pre_retrieval: bool = False,
    ) -> EvidenceAssessment:
        """
        Executes a comprehensive sufficiency assessment on the EvidenceContract.
        Distinguishes:
        - PENDING_RETRIEVAL: Pre-retrieval planning stage (prerequisites defined, awaiting retrieval)
        - NOT_REQUIRED: General knowledge queries where MRPL evidence does not apply
        - SUFFICIENT / INSUFFICIENT / BLOCKED: Post-retrieval evaluation against actual retrieved evidence
        - BLOCKED_BY_CONTEXT_GUARD: Unknown MRPL entities blocked by context guard
        """
        t0 = time.time()
        retrieved_chunks = retrieved_chunks or []
        attached_data = attached_data or {}
        tool_outputs = tool_outputs or {}

        # 1. Evaluate Contract Requirements
        evaluated_contract = EvidenceContractValidator.evaluate_contract(
            contract=contract,
            retrieved_chunks=retrieved_chunks,
            attached_data=attached_data,
            tool_outputs=tool_outputs,
            has_images=has_images,
            is_pre_retrieval=is_pre_retrieval,
        )

        is_high_risk = (contract.risk_level in ("high", "critical")) or (contract.task_type == "statutory_approval")

        # 2. Multi-Dimensional Scoring
        relevance_score = EvidenceScoringEngine.compute_relevance_score(
            query=query or attached_data.get("query", ""),
            retrieved_chunks=retrieved_chunks,
            contract=evaluated_contract,
            has_images=has_images,
        )
        coverage_score = EvidenceScoringEngine.compute_coverage_score(contract=evaluated_contract)
        authority_score = EvidenceScoringEngine.compute_authority_score(
            retrieved_chunks=retrieved_chunks,
            required_authority=evaluated_contract.required_source_authority,
            has_images=has_images,
        )
        freshness_score = EvidenceScoringEngine.compute_freshness_score(
            retrieved_chunks=retrieved_chunks,
            freshness_requirements=evaluated_contract.freshness_requirements,
        )
        consistency_score, contradictions = EvidenceScoringEngine.compute_consistency_score(
            retrieved_chunks=retrieved_chunks,
            required_entities=evaluated_contract.required_entities,
        )
        entity_match_score = EvidenceScoringEngine.compute_entity_match_score(
            retrieved_chunks=retrieved_chunks,
            required_entities=evaluated_contract.required_entities,
            has_images=has_images,
        )
        modality_score = EvidenceScoringEngine.compute_modality_completeness_score(
            contract=evaluated_contract,
            has_images=has_images,
            attached_data=attached_data,
            tool_outputs=tool_outputs,
        )

        # 3. Deterministic Evidence Debt
        debt = EvidenceDebtCalculator.calculate_debt(
            contract=evaluated_contract,
            is_high_risk=is_high_risk,
            is_pre_retrieval=is_pre_retrieval,
        )

        total_mandatory = len(evaluated_contract.required_evidence)
        satisfied_mandatory = sum(1 for r in evaluated_contract.required_evidence if r.satisfied)
        mandatory_met = (debt.missing_mandatory_count == 0)
        missing_req_labels = [r.description for r in evaluated_contract.required_evidence if not r.satisfied]

        # Mode A: GENERAL KNOWLEDGE & GENERIC CODING (Plant RAG not required)
        is_pure_general = (contract.task_type in ("general_reasoning", "general", "generic_coding")) and not contract.required_entities

        if is_pure_general and not is_high_risk:
            overall_status = SufficiencyStatus.NOT_REQUIRED
            can_safely_proceed = True
            debt = EvidenceDebt(
                total_required=0,
                satisfied_count=0,
                missing_mandatory_count=0,
                missing_optional_count=0,
                debt_summary="None",
                missing_items=[],
                recommendations=[],
            )
            system_recommendation = "Generic programming or general knowledge mode — MRPL engineering evidence retrieval is not applicable."
            relevance_score = 1.0
            coverage_score = 1.0
            authority_score = 1.0
            freshness_score = 1.0
            consistency_score = 1.0
            entity_match_score = 1.0
            modality_score = 1.0

        # Mode B: PRE-RETRIEVAL PLANNING STAGE
        elif is_pre_retrieval:
            overall_status = SufficiencyStatus.PENDING_RETRIEVAL
            can_safely_proceed = True
            system_recommendation = "Prerequisites defined. Execute RAG retrieval to gather required evidence."
            # Do not assert missing entity blockers before retrieval
            evaluated_contract.blocking_conditions = []

        # Mode C: UNKNOWN MRPL ENTITY (Context Guard Refusal)
        elif contract.task_type in ("unknown_mrpl_entity", "guarded_entity_resolution_refusal", "mrpl_context_blocked") or getattr(contract, "deliverable_type", None) == "guarded_entity_resolution_refusal":
            overall_status = SufficiencyStatus.BLOCKED_BY_CONTEXT_GUARD
            can_safely_proceed = False
            ent = contract.required_entities[0] if contract.required_entities else "Target Entity"
            debt = EvidenceDebt(
                total_required=1,
                satisfied_count=0,
                missing_mandatory_count=1,
                missing_optional_count=0,
                debt_summary=f"Missing authoritative MRPL record for {ent}",
                missing_items=[],
                recommendations=["Register asset in MRPL Knowledge Base / Asset Registry before requesting MRPL claims."],
            )
            system_recommendation = "No authoritative MRPL record was found for this entity. General pretrained knowledge cannot be used to make an MRPL-specific claim."
            relevance_score = 0.0
            coverage_score = 0.0
            authority_score = 0.0
            freshness_score = 0.0
            consistency_score = 0.0
            entity_match_score = 0.0
            modality_score = 0.0

        # Mode D: POST-RETRIEVAL INDUSTRIAL WORKFLOW EVALUATION
        else:
            if len(contradictions) > 0:
                overall_status = SufficiencyStatus.CONTRADICTORY
                can_safely_proceed = False
            elif is_high_risk and (not mandatory_met or len(evaluated_contract.blocking_conditions) > 0):
                overall_status = SufficiencyStatus.BLOCKED
                can_safely_proceed = False
            elif mandatory_met and coverage_score >= evaluated_contract.minimum_coverage and not evaluated_contract.blocking_conditions:
                overall_status = SufficiencyStatus.SUFFICIENT
                can_safely_proceed = True
            elif coverage_score >= 0.40 or satisfied_mandatory > 0:
                overall_status = SufficiencyStatus.PARTIALLY_SUFFICIENT
                can_safely_proceed = not is_high_risk
            else:
                overall_status = SufficiencyStatus.INSUFFICIENT
                can_safely_proceed = False

            # Formulate Primary System Recommendation
            if overall_status == SufficiencyStatus.SUFFICIENT:
                system_recommendation = "Required evidence is verified. Execution may proceed; this does not constitute an engineering fitness-for-service decision."
            elif overall_status == SufficiencyStatus.CONTRADICTORY:
                system_recommendation = f"Contradiction detected: {contradictions[0]}. Human resolution required before execution."
            elif overall_status == SufficiencyStatus.BLOCKED:
                first_rec = debt.recommendations[0] if debt.recommendations else "Retrieve missing statutory records."
                system_recommendation = f"High-risk task blocked: {debt.debt_summary}. {first_rec}"
            elif overall_status == SufficiencyStatus.PARTIALLY_SUFFICIENT:
                first_rec = debt.recommendations[0] if debt.recommendations else "Expand search query for missing requirements."
                system_recommendation = f"Partial evidence ({round(coverage_score * 100)}% coverage). {first_rec}"
            else:
                first_rec = debt.recommendations[0] if debt.recommendations else "Provide supporting documentation."
                system_recommendation = f"Insufficient evidence ({round(coverage_score * 100)}% coverage). {first_rec}"

        # 6. Build UI Evidence Checklist
        checklist: List[Dict[str, Any]] = []
        for req in evaluated_contract.required_evidence:
            checklist.append({
                "id": req.id,
                "name": req.description,
                "evidence_type": req.evidence_type.value,
                "mandatory": True,
                "satisfied": req.satisfied,
                "matched_source": req.matched_source or "Not Found",
                "authority": req.authority_requirement.value,
            })
        for req in evaluated_contract.optional_evidence:
            checklist.append({
                "id": req.id,
                "name": req.description,
                "evidence_type": req.evidence_type.value,
                "mandatory": False,
                "satisfied": req.satisfied,
                "matched_source": req.matched_source or "Optional (Omitted)",
                "authority": req.authority_requirement.value,
            })

        assessment = EvidenceAssessment(
            task_id=evaluated_contract.task_id,
            task_type=evaluated_contract.task_type,
            overall_status=overall_status,
            coverage_score=coverage_score,
            relevance_score=relevance_score,
            authority_score=authority_score,
            freshness_score=freshness_score,
            consistency_score=consistency_score,
            entity_match_score=entity_match_score,
            modality_completeness_score=modality_score,
            mandatory_requirements_met=mandatory_met,
            total_mandatory=total_mandatory,
            satisfied_mandatory=satisfied_mandatory,
            missing_requirements=missing_req_labels,
            evidence_debt=debt,
            blocking_reasons=evaluated_contract.blocking_conditions,
            contradictions=contradictions,
            is_high_risk=is_high_risk,
            can_safely_proceed=can_safely_proceed,
            system_recommendation=system_recommendation,
            evidence_checklist=checklist,
            evaluated_at=round(time.time(), 3),
        )

        evaluated_contract.assessment = assessment
        return assessment
