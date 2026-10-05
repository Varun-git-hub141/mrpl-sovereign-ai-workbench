# backend/services/evidence/evidence_debt.py
"""
MRPL Sovereign AI Workbench — Evidence Debt Calculator.
Deterministically calculates outstanding evidence prerequisites without probabilistic guessing.
Quantifies missing mandatory items, missing optional items, and generates actionable remediation guidance.
"""

import logging
from typing import List, Dict, Any, Optional
from backend.services.evidence.evidence_models import (
    EvidenceContract,
    EvidenceRequirement,
    EvidenceDebt,
    EvidenceDebtItem,
    EvidenceDebtSeverity,
    EvidenceType,
)

logger = logging.getLogger("mrpl.evidence.debt")


class EvidenceDebtCalculator:
    """
    Computes deterministic evidence debt for industrial workflows.
    """

    @classmethod
    def calculate_debt(
        cls,
        contract: EvidenceContract,
        is_high_risk: bool = False,
        is_pre_retrieval: bool = False,
    ) -> EvidenceDebt:
        """
        Calculates exact evidence debt from an evaluated EvidenceContract.
        """
        missing_items: List[EvidenceDebtItem] = []
        recommendations: List[str] = []

        total_reqs = len(contract.required_evidence) + len(contract.optional_evidence)
        satisfied_count = (
            sum(1 for r in contract.required_evidence if r.satisfied) +
            sum(1 for r in contract.optional_evidence if r.satisfied)
        )

        missing_mandatory_count = 0
        missing_optional_count = 0

        # Evaluate Mandatory Requirements
        for req in contract.required_evidence:
            if not req.satisfied:
                missing_mandatory_count += 1
                severity = EvidenceDebtSeverity.CRITICAL if (is_high_risk or contract.risk_level in ("high", "critical")) else EvidenceDebtSeverity.HIGH
                remediation = cls._get_remediation_action(req)
                missing_items.append(
                    EvidenceDebtItem(
                        requirement_id=req.id or f"REQ-MAND-{missing_mandatory_count}",
                        evidence_type=req.evidence_type,
                        description=req.description,
                        mandatory=True,
                        severity=severity,
                        remediation_action=remediation,
                        entity_scope=req.entity_scope,
                    )
                )
                recommendations.append(remediation)

        # Evaluate Optional Requirements
        for req in contract.optional_evidence:
            if not req.satisfied:
                missing_optional_count += 1
                remediation = cls._get_remediation_action(req)
                missing_items.append(
                    EvidenceDebtItem(
                        requirement_id=req.id or f"REQ-OPT-{missing_optional_count}",
                        evidence_type=req.evidence_type,
                        description=req.description,
                        mandatory=False,
                        severity=EvidenceDebtSeverity.OPTIONAL,
                        remediation_action=remediation,
                        entity_scope=req.entity_scope,
                    )
                )

        # Formulate Human-Readable Debt Summary
        if is_pre_retrieval:
            debt_summary = "Prerequisites defined — awaiting RAG retrieval"
            recommendations = ["Execute RAG retrieval to acquire required engineering documentation."]
        elif missing_mandatory_count > 0:
            debt_summary = f"{missing_mandatory_count} critical requirement{'s' if missing_mandatory_count > 1 else ''} missing"
        elif missing_optional_count > 0:
            debt_summary = f"{missing_optional_count} optional requirement{'s' if missing_optional_count > 1 else ''} missing"
        else:
            debt_summary = "Zero evidence debt — complete"

        return EvidenceDebt(
            total_required=total_reqs,
            satisfied_count=satisfied_count,
            missing_mandatory_count=missing_mandatory_count,
            missing_optional_count=missing_optional_count,
            debt_summary=debt_summary,
            missing_items=missing_items,
            recommendations=recommendations,
        )

    @classmethod
    def _get_remediation_action(cls, req: EvidenceRequirement) -> str:
        tag = req.entity_scope or "target asset"
        clean_tag = tag.replace("-", "")
        ev_type = req.evidence_type

        if ev_type == EvidenceType.BASELINE_INSPECTION:
            return f"Retrieve previous statutory inspection log (e.g. MRPL-INSP-2019-{clean_tag}.pdf) to establish baseline wall thickness."
        elif ev_type in (EvidenceType.CURRENT_INSPECTION, EvidenceType.ULTRASONIC_THICKNESS_DATA):
            return f"Retrieve current statutory turnaround survey (e.g. MRPL-INSP-2024-{clean_tag}.pdf) for active UT measurements."
        elif ev_type == EvidenceType.EQUIPMENT_DATASHEET:
            return f"Retrieve equipment engineering datasheet (e.g. MRPL-DS-{clean_tag}.pdf) to verify design limits and t_min."
        elif ev_type == EvidenceType.P_AND_ID_SCHEMATIC:
            return "Attach or upload P&ID engineering drawing / schematic diagram."
        elif ev_type == EvidenceType.APPLICABLE_STANDARD:
            return "Reference governing statutory standard (e.g. API 570 Section 7.1.1 / ASME B31.3 / OISD-118)."
        elif ev_type == EvidenceType.FORMULA_DEFINITION:
            return "Invoke deterministic calculator engine to resolve formula."
        elif ev_type == EvidenceType.REQUIRED_NUMERIC_INPUTS:
            return f"Provide required numerical measurements (e.g. wall thickness, interval) for {tag}."
        elif ev_type == EvidenceType.VIBRATION_SURVEY:
            return f"Retrieve ISO 10816 vibration survey logs for {tag}."
        elif ev_type == EvidenceType.MOC_RECORD:
            return f"Retrieve Management of Change (MOC) records for {tag}."
        elif ev_type == EvidenceType.SOP_PROCEDURE:
            return f"Retrieve standard operating procedure (SOP) documentation for {tag}."
        else:
            return f"Retrieve authoritative local evidence for: {req.description}."
