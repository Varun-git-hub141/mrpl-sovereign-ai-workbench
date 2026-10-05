# backend/services/evidence/evidence_contract.py
"""
MRPL Sovereign AI Workbench — Evidence Contract Validation & Evaluation.
Validates whether incoming evidence (RAG chunks, tool outputs, user attachments)
fulfills the prerequisites established in the EvidenceContract.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from backend.services.evidence.evidence_models import (
    EvidenceContract,
    EvidenceRequirement,
    AuthorityLevel,
    EvidenceType,
)

logger = logging.getLogger("mrpl.evidence.contract")


class EvidenceContractValidator:
    """
    Evaluates evidence against an EvidenceContract.
    Computes satisfaction score, flags missing mandatory items, and evaluates blocking conditions.
    """

    @classmethod
    def evaluate_contract(
        cls,
        contract: EvidenceContract,
        retrieved_chunks: Optional[List[Any]] = None,
        attached_data: Optional[Dict[str, Any]] = None,
        tool_outputs: Optional[Dict[str, Any]] = None,
        has_images: bool = False,
        is_pre_retrieval: bool = False,
    ) -> EvidenceContract:
        """
        Evaluates current available context against the requirements in the EvidenceContract.
        Returns an updated copy of the contract with satisfied flags populated.
        """
        contract_copy = contract.model_copy(deep=True)
        retrieved_chunks = retrieved_chunks or []
        attached_data = attached_data or {}
        tool_outputs = tool_outputs or {}

        # Aggregate texts and metadata from all available evidence items
        chunk_texts: List[str] = []
        chunk_docs: List[str] = []
        for c in retrieved_chunks:
            t = getattr(c, "text", "") if hasattr(c, "text") else (c.get("text", "") if isinstance(c, dict) else str(c))
            chunk_texts.append((t or "").lower())
            doc_name = ""
            if hasattr(c, "source") and getattr(c, "source", None) is not None:
                doc_name = getattr(c.source, "document", "") or ""
            elif isinstance(c, dict):
                src_val = c.get("source")
                if isinstance(src_val, dict):
                    doc_name = src_val.get("document", "") or ""
                elif hasattr(src_val, "document"):
                    doc_name = getattr(src_val, "document", "") or ""
                if not doc_name:
                    doc_name = c.get("filename", "") or ""
            if doc_name:
                chunk_docs.append(doc_name.lower())

        combined_text = " ".join(chunk_texts)
        combined_docs = " ".join(chunk_docs)

        # Evaluate Mandatory Requirements
        satisfied_mandatory = 0
        total_mandatory = len(contract_copy.required_evidence)

        for req in contract_copy.required_evidence:
            is_satisfied, matched_src = cls._check_requirement(
                req=req,
                combined_text=combined_text,
                combined_docs=combined_docs,
                retrieved_chunks=retrieved_chunks,
                attached_data=attached_data,
                tool_outputs=tool_outputs,
                has_images=has_images,
                is_pre_retrieval=is_pre_retrieval,
            )
            req.satisfied = is_satisfied
            req.matched_source = matched_src
            if is_satisfied:
                satisfied_mandatory += 1

        # Evaluate Optional Requirements
        for req in contract_copy.optional_evidence:
            is_satisfied, matched_src = cls._check_requirement(
                req=req,
                combined_text=combined_text,
                combined_docs=combined_docs,
                retrieved_chunks=retrieved_chunks,
                attached_data=attached_data,
                tool_outputs=tool_outputs,
                has_images=has_images,
                is_pre_retrieval=is_pre_retrieval,
            )
            req.satisfied = is_satisfied
            req.matched_source = matched_src

        # Compute Coverage Ratio
        ratio = (satisfied_mandatory / total_mandatory) if total_mandatory > 0 else 1.0
        contract_copy.satisfaction_ratio = round(ratio, 3)
        contract_copy.is_satisfied = ratio >= contract_copy.minimum_coverage

        # Re-evaluate blocking conditions
        active_blockers: List[str] = []
        if not is_pre_retrieval:
            for req in contract_copy.required_evidence:
                if not req.satisfied:
                    active_blockers.append(f"UNSATISFIED_MANDATORY_EVIDENCE: {req.description} ({req.evidence_type.value})")

            if contract_copy.required_entities:
                for ent in contract_copy.required_entities:
                    if ent.lower() not in combined_text and ent.lower() not in combined_docs and not has_images:
                        active_blockers.append(f"MISSING_ENTITY_AUTHORITATIVE_RECORD: {ent}")

        contract_copy.blocking_conditions = active_blockers
        return contract_copy

    @classmethod
    def _check_requirement(
        cls,
        req: EvidenceRequirement,
        combined_text: str,
        combined_docs: str,
        retrieved_chunks: List[Any],
        attached_data: Dict[str, Any],
        tool_outputs: Dict[str, Any],
        has_images: bool,
        is_pre_retrieval: bool = False,
    ) -> tuple[bool, Optional[str]]:
        ev_type = req.evidence_type

        # 1. User Prompt Context & Scope (Always available at prompt time)
        if ev_type in (
            EvidenceType.USER_SCOPE,
            EvidenceType.FACTUAL_ASSERTIONS,
            EvidenceType.GENERAL_KNOWLEDGE_DECLARATION,
            EvidenceType.FUNCTIONAL_REQUIREMENTS,
            EvidenceType.TEST_CRITERIA,
        ):
            if attached_data.get("query") or combined_text or has_images:
                return True, "User Scope / Prompt Context"
            return True, "User Prompt Context"

        # During PRE-RETRIEVAL, downstream physical document and retrieval requirements are pending
        if is_pre_retrieval:
            return False, "Awaiting RAG Retrieval"

        # Enforce entity scope if explicitly specified on requirement
        if req.entity_scope:
            scope_l = req.entity_scope.lower()
            scope_clean = scope_l.replace("-", "")
            if scope_l not in combined_text and scope_clean not in combined_text and scope_l not in combined_docs and scope_clean not in combined_docs and not has_images:
                return False, None

        # 2. P&ID and Visual Diagrams
        if ev_type == EvidenceType.P_AND_ID_SCHEMATIC:
            if has_images or "pid" in combined_docs or "schematic" in combined_docs or "diagram" in combined_docs:
                return True, "User Uploaded Diagram / Indexed P&ID"
            return False, None

        # 3. Formula Definitions & Calculations
        if ev_type in (EvidenceType.FORMULA_DEFINITION, EvidenceType.REQUIRED_NUMERIC_INPUTS, EvidenceType.UNITS_SPECIFICATION):
            if tool_outputs.get("status") == "SUCCESS" or "corrosion_rate" in tool_outputs or "result" in tool_outputs:
                return True, "Deterministic Calculator Output"
            if any(k in combined_text for k in ["thickness", "corrosion rate", "api 570", "t_min", "baseline"]):
                return True, "Retrieved Technical Specification"
            return False, None

        # 4. Applicable Standards
        if ev_type == EvidenceType.APPLICABLE_STANDARD:
            standards = ["api 570", "api 510", "asme b31.3", "asme section viii", "iso 10816", "oisd-118", "oisd"]
            for std in standards:
                if std in combined_text or std in combined_docs:
                    return True, f"Standard Reference: {std.upper()}"
            return False, None

        # 5. Baseline Inspection
        if ev_type == EvidenceType.BASELINE_INSPECTION:
            if any(k in combined_text or k in combined_docs for k in ["baseline", "2019", "2017", "previous", "initial", "t_prev", "insp-2019", "insp-2017"]):
                return True, "MRPL Baseline Inspection Log"
            return False, None

        # 5b. Current Inspection
        if ev_type == EvidenceType.CURRENT_INSPECTION:
            if any(k in combined_text or k in combined_docs for k in ["current", "2024", "2020", "latest", "turnaround", "grid c", "t_curr", "insp-2024", "insp-2020"]):
                return True, "MRPL Current Inspection Survey"
            return False, None

        # 5c. Ultrasonic Thickness Data
        if ev_type == EvidenceType.ULTRASONIC_THICKNESS_DATA:
            if any(k in combined_text for k in ["ultrasonic", "wall thickness", "grid", "thickness", "mm"]):
                return True, "Ultrasonic Thickness Data"
            return False, None

        # 6. Equipment Datasheet
        if ev_type == EvidenceType.EQUIPMENT_DATASHEET:
            if any(k in combined_text or k in combined_docs for k in ["datasheet", "casing material", "design pressure", "design temperature", "operating service", "pump", "column"]):
                return True, "MRPL Asset Datasheet"
            return False, None

        # 7. Source Documents / Local Documentation
        if ev_type in (EvidenceType.SOURCE_DOCUMENTS, EvidenceType.LOCAL_DOCUMENTATION):
            if len(retrieved_chunks) > 0 or len(combined_docs) > 0 or len(combined_text) > 0:
                return True, "Retrieved MRPL Documentation"
            return False, None

        # 8. Entity Scope Match
        if req.entity_scope:
            if req.entity_scope.lower() in combined_text or req.entity_scope.lower() in combined_docs:
                return True, f"MRPL Asset Record for {req.entity_scope}"
            return False, None

        # Fallback heuristic
        if len(retrieved_chunks) > 0:
            return True, "General Retrieved Evidence"
        return False, None
