# backend/services/pid/pid_evidence_bridge.py
"""
MRPL Sovereign AI Workbench — P&ID Evidence Bridge.
Integrates the approved P&ID Engineering Knowledge Graph with the existing MRPL Evidence Architecture:
- EvidenceRequirementEngine (synthesizes formal EvidenceContracts)
- EngineeringRAGEngine (authoritative local document retrieval)
- EvidenceSufficiencyEngine (multi-dimensional evidence assessment)
- EvidenceDebtCalculator (quantifies missing mandatory prerequisites)
- MRPLEntityResolver (authoritative asset identity & context guard)

Enforces strict boundary between:
1. WHAT THE P&ID DRAWING SHOWS (TOPOLOGY_FACT)
2. WHAT MRPL DOCUMENTARY EVIDENCE SUPPORTS (DOCUMENTARY_EVIDENCE)
3. WHAT CAN BE DETERMINISTICALLY CALCULATED (CALCULATED_RESULT)
4. WHAT REMAINS UNKNOWN / UNVERIFIED (UNVERIFIED_CLAIM / BLOCKED)
"""

import time
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from backend.models.pid_graph_models import (
    PIDQueryRequest,
    PIDQueryResponse,
    PIDQueryResultStatus,
    PIDEnhancedEvidenceResponse,
    EvidenceTier,
    EvidenceClassification,
    EvidenceClaimItem,
)
from backend.services.evidence.evidence_models import (
    EvidenceContract,
    EvidenceAssessment,
    EvidenceDebt,
    SufficiencyStatus,
    ContractGenerationContext,
)
from backend.services.evidence.evidence_requirement_engine import EvidenceRequirementEngine
from backend.services.evidence.evidence_sufficiency import EvidenceSufficiencyEngine
from backend.services.rag_engine import EngineeringRAGEngine
from backend.models.rag_models import HybridSearchRequest

logger = logging.getLogger("mrpl.pid_evidence_bridge")


class PIDEvidenceBridge:
    """
    Controlled Evidence Bridge connecting P&ID Graph Topology to MRPL Evidence Architecture.
    """

    def __init__(
        self,
        pid_engine: Optional[Any] = None,
        rag_engine: Optional[EngineeringRAGEngine] = None,
        evidence_req_engine: Optional[EvidenceRequirementEngine] = None,
    ):
        if pid_engine is None:
            from backend.services.pid_graph_engine import PIDGraphEngine
            self.pid_engine = PIDGraphEngine()
        else:
            self.pid_engine = pid_engine
        self.rag_engine = rag_engine or EngineeringRAGEngine()
        self.evidence_req_engine = evidence_req_engine or EvidenceRequirementEngine()

    def process_query(
        self,
        question: str,
        drawing_id: Optional[str] = None,
        target_equipment: Optional[str] = None,
    ) -> PIDEnhancedEvidenceResponse:
        """
        Main query pipeline bridging P&ID Topology and Evidence Architecture.
        """
        q_clean = question.strip()
        
        # 1. Classify Task Tier (Tier A: Pure Topology, Tier B: Doc Evidence, Tier C: Safety/Decision)
        tier = self._classify_query_tier(q_clean)
        
        # 2. Execute Deterministic P&ID Graph Traversal
        req = PIDQueryRequest(
            question=q_clean,
            drawing_id=drawing_id,
            target_equipment=target_equipment,
        )
        topo_res = self.pid_engine.query_pid(req)

        # 3. Handle Unknown Entity Guard
        if topo_res.status == PIDQueryResultStatus.UNRESOLVED:
            return self._build_unknown_entity_response(q_clean, topo_res, tier)

        # 4. Tier A: Pure P&ID Topology (Fast path, zero RAG, zero debt)
        if tier == EvidenceTier.PURE_TOPOLOGY:
            return self._build_pure_topology_response(q_clean, topo_res)

        # 5. Tier B: P&ID + Documentary Evidence
        elif tier == EvidenceTier.TOPOLOGY_AND_EVIDENCE:
            return self._build_documentary_evidence_response(q_clean, topo_res)

        # 6. Tier C: Engineering Decision / Safety Question Gated by Evidence Contract
        else:
            return self._build_engineering_decision_response(q_clean, topo_res)

    # ─────────────────────────────────────────────────────────────
    # Tier Classification Logic
    # ─────────────────────────────────────────────────────────────

    def _classify_query_tier(self, question: str) -> EvidenceTier:
        q_lower = question.lower()

        # Engineering Decision / Safety Gating patterns (Tier C)
        decision_patterns = [
            r"\bcan\b.*\bisolat",
            r"\bcan\b.*\bsafely\b",
            r"\bis\b.*\bsafe\b",
            r"\bis\b.*\badequate\b",
            r"\bcan\b.*\bcontinue\b.*operat",
            r"\bis\b.*\bsufficient\b.*loto",
            r"\bis\b.*\bfit\b.*service",
            r"\bauthorization\b",
            r"\bpermit\b.*to\b.*work\b",
            r"\bsafe\b.*for\b.*maintenance\b",
            r"\badequate\b.*psv\b",
            r"\bpsv\b.*adequate\b",
            r"\bis\b.*\bprotection\b.*adequate\b",
        ]
        for pat in decision_patterns:
            if re.search(pat, q_lower):
                return EvidenceTier.ENGINEERING_DECISION

        # Documentary Evidence patterns (Tier B)
        document_patterns = [
            r"\bdocument(s)?\b.*support",
            r"\bmrpl\b.*document",
            r"\bsop\b",
            r"\bprocedure\b",
            r"\bmaintenance\b.*record",
            r"\bmanual\b",
            r"\bstandard\b.*support",
            r"\bevidence\b.*support",
            r"\bwhat\b.*evidence\b",
        ]
        for pat in document_patterns:
            if re.search(pat, q_lower):
                return EvidenceTier.TOPOLOGY_AND_EVIDENCE

        # Pure P&ID Topology (Tier A)
        return EvidenceTier.PURE_TOPOLOGY

    # ─────────────────────────────────────────────────────────────
    # Response Builders
    # ─────────────────────────────────────────────────────────────

    def _build_pure_topology_response(
        self, question: str, topo_res: PIDQueryResponse
    ) -> PIDEnhancedEvidenceResponse:
        """
        Builds Tier A response: pure graph facts with zero unnecessary RAG or debt.
        """
        claims: List[EvidenceClaimItem] = []
        target = topo_res.query_plan.target_entity if topo_res.query_plan else "Equipment"

        for node_tag in topo_res.direct_nodes_involved:
            claims.append(
                EvidenceClaimItem(
                    claim_text=f"Node `{node_tag}` is topologically connected to `{target}` in drawing `{topo_res.selected_drawing or topo_res.drawing_id}`.",
                    classification=EvidenceClassification.TOPOLOGY_FACT,
                    source_citation=f"Drawing {topo_res.selected_drawing or topo_res.drawing_id} ({topo_res.provenance_records[0].source_file if topo_res.provenance_records else 'P&ID Source'})",
                    document_id=topo_res.selected_drawing or topo_res.drawing_id,
                    verified=True,
                )
            )

        return PIDEnhancedEvidenceResponse(
            question=question,
            target_entity=target,
            selected_drawing=topo_res.selected_drawing,
            alternate_drawings=topo_res.alternate_drawings,
            evidence_tier=EvidenceTier.PURE_TOPOLOGY,
            topology=topo_res,
            contract=None,
            assessment=None,
            evidence_debt=None,
            retrieved_documents=[],
            evidence_claims=claims,
            safety_decision="TOPOLOGY_ONLY_NO_CONCLUSION",
            safety_blockers=[],
            recommendations=["For formal maintenance authorization, execute an Engineering Decision inquiry to evaluate MRPL LOTO and isolation SOPs."],
            final_synthesis=topo_res.answer,
        )

    def _build_documentary_evidence_response(
        self, question: str, topo_res: PIDQueryResponse
    ) -> PIDEnhancedEvidenceResponse:
        """
        Builds Tier B response: P&ID topology grounded with MRPL Knowledge Base RAG retrieval.
        """
        target = topo_res.query_plan.target_entity if topo_res.query_plan else "Equipment"
        drawing = topo_res.selected_drawing or topo_res.drawing_id

        # 1. Generate Evidence Contract
        ctx = ContractGenerationContext(
            query=question,
            task_type="pid_documentary_support",
            entity_name=target,
            domain="REFINERY",
            risk_level="medium",
        )
        contract = self.evidence_req_engine.generate_contract(context=ctx)

        # 2. Perform Grounded Hybrid RAG Search
        search_query = f"{target} {drawing} isolation maintenance SOP procedure manual drawing"
        rag_chunks = []
        try:
            rag_chunks = self.rag_engine.hybrid_service.hybrid_search(
                HybridSearchRequest(
                    query=search_query,
                    top_k=4,
                    entity_filter=target,
                )
            )
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)

        # 3. Assess Evidence Sufficiency & Debt
        assessment = EvidenceSufficiencyEngine.assess_evidence(
            contract=contract,
            retrieved_chunks=rag_chunks,
            query=question,
            is_pre_retrieval=False,
        )

        # 4. Formulate Evidence Claims
        claims: List[EvidenceClaimItem] = []
        # Topology facts
        for node_tag in topo_res.direct_nodes_involved:
            claims.append(
                EvidenceClaimItem(
                    claim_text=f"Topology relationship: `{node_tag}` connected to `{target}` in `{drawing}`.",
                    classification=EvidenceClassification.TOPOLOGY_FACT,
                    source_citation=f"Drawing {drawing}",
                    document_id=drawing,
                    verified=True,
                )
            )

        # Documentary evidence claims
        docs_summary: List[Dict[str, Any]] = []
        for chk in rag_chunks:
            doc_title = chk.source.document if hasattr(chk, "source") and hasattr(chk.source, "document") else str(getattr(chk, "title", "MRPL Document"))
            doc_id = getattr(chk, "id", doc_title)
            snippet = (chk.text[:180] + "...") if hasattr(chk, "text") else str(chk)[:180]
            claims.append(
                EvidenceClaimItem(
                    claim_text=f"Documentary reference ({doc_title}): {snippet}",
                    classification=EvidenceClassification.DOCUMENTARY_EVIDENCE,
                    source_citation=doc_title,
                    document_id=doc_id,
                    verified=True,
                )
            )
            docs_summary.append({
                "document_title": doc_title,
                "document_id": doc_id,
                "snippet": snippet,
                "score": round(getattr(chk, "score", 0.9), 3),
            })

        # Multi-drawing notice
        multi_context_note = ""
        if topo_res.alternate_drawings:
            multi_context_note = f"\n\n> ℹ️ **Multi-Drawing Context:** Tag `{target}` also appears in alternate drawing(s): `{', '.join(topo_res.alternate_drawings)}`. Retrieval scoped to primary context `{drawing}`."

        synthesis = (
            f"### P&ID Grounded Documentary Evidence for `{target}`\n\n"
            f"{topo_res.answer}\n\n"
            f"---\n\n"
            f"### Supporting MRPL Documentary Evidence\n"
            f"- **Evidence Contract:** `{contract.task_type}` (Coverage: {assessment.coverage_score * 100:.0f}%)\n"
            f"- **Sufficiency Status:** `{assessment.overall_status.value}`\n"
            f"- **Retrieved Knowledge Sources:** {len(docs_summary)} documents\n\n"
        )
        for d in docs_summary:
            synthesis += f"- **{d['document_title']}**: {d['snippet']}\n"
        synthesis += multi_context_note

        return PIDEnhancedEvidenceResponse(
            question=question,
            target_entity=target,
            selected_drawing=topo_res.selected_drawing,
            alternate_drawings=topo_res.alternate_drawings,
            evidence_tier=EvidenceTier.TOPOLOGY_AND_EVIDENCE,
            topology=topo_res,
            contract=contract.model_dump(),
            assessment=assessment.model_dump(),
            evidence_debt=assessment.evidence_debt.model_dump(),
            retrieved_documents=docs_summary,
            evidence_claims=claims,
            safety_decision="APPROVED_WITH_EVIDENCE" if assessment.overall_status == SufficiencyStatus.SUFFICIENT else "INSUFFICIENT_DOCUMENTARY_EVIDENCE",
            safety_blockers=assessment.blocking_reasons,
            recommendations=assessment.evidence_debt.recommendations,
            final_synthesis=synthesis,
        )

    def _build_engineering_decision_response(
        self, question: str, topo_res: PIDQueryResponse
    ) -> PIDEnhancedEvidenceResponse:
        """
        Builds Tier C response: strict engineering decision gating preventing unverified 'safe' claims.
        """
        target = topo_res.query_plan.target_entity if topo_res.query_plan else "Equipment"
        drawing = topo_res.selected_drawing or topo_res.drawing_id
        q_lower = question.lower()

        # 1. Determine specific decision domain & synthesize Evidence Contract
        task_type = "pid_isolation_safety"
        if "psv" in q_lower or "adequate" in q_lower or "relief" in q_lower:
            task_type = "pid_protection_adequacy"

        ctx = ContractGenerationContext(
            query=question,
            task_type=task_type,
            entity_name=target,
            domain="REFINERY",
            risk_level="high" if task_type == "pid_isolation_safety" else "critical",
        )
        contract = self.evidence_req_engine.generate_contract(context=ctx)

        # 2. Grounded RAG Search for mandatory SOP / standard / datasheet
        search_query = f"{target} {drawing} LOTO isolation procedure depressurization drainage SOP PSV datasheet capacity"
        rag_chunks = []
        try:
            rag_chunks = self.rag_engine.hybrid_service.hybrid_search(
                HybridSearchRequest(
                    query=search_query,
                    top_k=4,
                    entity_filter=target,
                )
            )
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)

        # 3. Assess Sufficiency and calculate Evidence Debt
        # Note: If mandatory LOTO SOP / capacity calculation is missing, SufficiencyEngine blocks the task.
        assessment = EvidenceSufficiencyEngine.assess_evidence(
            contract=contract,
            retrieved_chunks=rag_chunks,
            query=question,
            is_pre_retrieval=False,
        )

        # 4. Formulate Claims distinguishing Topology vs Document vs Unverified Claim
        claims: List[EvidenceClaimItem] = []
        # Topology facts
        for node_tag in topo_res.direct_nodes_involved:
            claims.append(
                EvidenceClaimItem(
                    claim_text=f"Physical topology confirmed: `{node_tag}` is adjacent/isolating `{target}` in `{drawing}`.",
                    classification=EvidenceClassification.TOPOLOGY_FACT,
                    source_citation=f"Drawing {drawing}",
                    document_id=drawing,
                    verified=True,
                )
            )

        # Documentary evidence from RAG
        docs_summary: List[Dict[str, Any]] = []
        for chk in rag_chunks:
            doc_title = chk.source.document if hasattr(chk, "source") and hasattr(chk.source, "document") else str(getattr(chk, "title", "MRPL Document"))
            doc_id = getattr(chk, "id", doc_title)
            snippet = (chk.text[:180] + "...") if hasattr(chk, "text") else str(chk)[:180]
            claims.append(
                EvidenceClaimItem(
                    claim_text=f"Retrieved document ({doc_title}): {snippet}",
                    classification=EvidenceClassification.DOCUMENTARY_EVIDENCE,
                    source_citation=doc_title,
                    document_id=doc_id,
                    verified=True,
                )
            )
            docs_summary.append({
                "document_title": doc_title,
                "document_id": doc_id,
                "snippet": snippet,
                "score": round(getattr(chk, "score", 0.9), 3),
            })

        # 5. Safety Boundary Enforcement & Gating
        is_blocked = (assessment.overall_status != SufficiencyStatus.SUFFICIENT) or (len(assessment.evidence_debt.missing_items) > 0)
        safety_decision = "BLOCKED_INSUFFICIENT_EVIDENCE" if is_blocked else "APPROVED_WITH_EVIDENCE"

        if is_blocked:
            unverified_claim_text = (
                f"Field isolation / operational safety authorization for `{target}` cannot be established from P&ID schematic alone without verified MRPL LOTO SOP, positive depressurization verification, and active permit-to-work."
                if task_type == "pid_isolation_safety"
                else f"Overpressure protection adequacy for `{target}` cannot be confirmed from P&ID schematic alone without relief capacity sizing calculations and certified PSV manufacturer datasheet."
            )
            claims.append(
                EvidenceClaimItem(
                    claim_text=unverified_claim_text,
                    classification=EvidenceClassification.UNVERIFIED_CLAIM,
                    source_citation="Safety Gating Policy: Topology != Operational Authorization",
                    verified=False,
                    notes="Blocked by Evidence Debt. Field work must not proceed without mandatory engineering documentation.",
                )
            )

        # 6. Synthesize Multi-Layer Explanation
        multi_context_note = ""
        if topo_res.alternate_drawings:
            multi_context_note = f"\n> ℹ️ **Multi-Drawing Context:** Tag `{target}` also appears in alternate drawing(s): `{', '.join(topo_res.alternate_drawings)}`. Evaluated in primary context `{drawing}`."

        synthesis = (
            f"## Engineering Decision Evaluation for `{target}`\n\n"
            f"### Layer 1: P&ID Graph Topology\n"
            f"- **Target Equipment:** `{target}`\n"
            f"- **Selected Drawing:** `{drawing}`\n"
            f"- **Identified Boundary / Connected Elements:** {', '.join(f'`{n}`' for n in topo_res.direct_nodes_involved)}\n"
            f"- **Topology Traversal Status:** `{topo_res.status.value}`\n\n"
            f"{topo_res.answer}\n\n"
            f"{multi_context_note}\n\n"
            f"---\n\n"
            f"### Layer 2: Engineering Evidence & Sufficiency Contract\n"
            f"- **Contract Schema:** `{contract.task_type}` (Risk Level: `{contract.risk_level.upper()}`)\n"
            f"- **Sufficiency Status:** `{assessment.overall_status.value}`\n"
            f"- **Coverage Ratio:** {assessment.coverage_score * 100:.0f}%\n"
            f"- **Evidence Debt State:** **{assessment.evidence_debt.debt_summary}** ({assessment.evidence_debt.missing_mandatory_count} mandatory missing)\n\n"
        )

        if assessment.evidence_debt.missing_items:
            synthesis += "#### Outstanding Evidence Debt (Blockers):\n"
            for item in assessment.evidence_debt.missing_items:
                synthesis += f"- ❌ **[{item.severity.value}] {item.evidence_type.value}:** {item.description}\n  *Action:* {item.remediation_action}\n"
            synthesis += "\n"

        synthesis += (
            f"---\n\n"
            f"### Layer 3: Final Engineering Conclusion & Safety Gating\n"
            f"**Decision Status:** "
        )

        if is_blocked:
            synthesis += (
                f"🛑 **BLOCKED — INSUFFICIENT EVIDENCE**\n\n"
                f"> ⚠️ **SAFETY MANDATE:** Physical P&ID connectivity establishes valve presence but does **NOT** authorize field maintenance, confirm zero-energy isolation, or validate PSV capacity adequacy.\n\n"
                f"**Mandatory Actions before Proceeding:**\n"
            )
            for rec in assessment.evidence_debt.recommendations:
                synthesis += f"1. {rec}\n"
        else:
            synthesis += (
                f"✅ **APPROVED WITH VERIFIED EVIDENCE**\n\n"
                f"All mandatory P&ID topology boundaries and MRPL operating procedures have been verified."
            )

        return PIDEnhancedEvidenceResponse(
            question=question,
            target_entity=target,
            selected_drawing=topo_res.selected_drawing,
            alternate_drawings=topo_res.alternate_drawings,
            evidence_tier=EvidenceTier.ENGINEERING_DECISION,
            topology=topo_res,
            contract=contract.model_dump(),
            assessment=assessment.model_dump(),
            evidence_debt=assessment.evidence_debt.model_dump(),
            retrieved_documents=docs_summary,
            evidence_claims=claims,
            safety_decision=safety_decision,
            safety_blockers=assessment.blocking_reasons,
            recommendations=assessment.evidence_debt.recommendations,
            final_synthesis=synthesis,
        )

    def _build_unknown_entity_response(
        self, question: str, topo_res: PIDQueryResponse, tier: EvidenceTier
    ) -> PIDEnhancedEvidenceResponse:
        """
        Handles unknown MRPL assets: blocks immediately with Context Guard without RAG hallucination.
        """
        target = topo_res.query_plan.target_entity if topo_res.query_plan else "UNKNOWN"
        
        ctx = ContractGenerationContext(
            query=question,
            task_type="unknown_mrpl_entity",
            entity_name=target,
            domain="REFINERY",
            risk_level="high",
        )
        contract = self.evidence_req_engine.generate_contract(context=ctx)
        assessment = EvidenceSufficiencyEngine.assess_evidence(
            contract=contract,
            retrieved_chunks=[],
            query=question,
            is_pre_retrieval=False,
        )

        claims = [
            EvidenceClaimItem(
                claim_text=f"Asset tag '{target}' is not registered in MRPL P&ID drawing registry or Knowledge Base.",
                classification=EvidenceClassification.UNVERIFIED_CLAIM,
                source_citation="MRPL Context Guard",
                verified=False,
                notes="Blocked to prevent AI hallucination on non-existent refinery equipment.",
            )
        ]

        synthesis = (
            f"🛑 **Context Guard Rejection — Unknown MRPL Asset**\n\n"
            f"The specified equipment tag **`{target}`** does not exist in any registered MRPL P&ID drawing or Equipment Master record.\n\n"
            f"- **P&ID Resolution:** `UNRESOLVED` (0.0 confidence)\n"
            f"- **Sufficiency Status:** `BLOCKED_BY_CONTEXT_GUARD`\n"
            f"- **Evidence Retrieval:** Halted (zero hallucination policy)\n\n"
            f"*Please verify the equipment tag against official MRPL plant documentation (e.g. `P-101`, `P-201`, `TK-201`, `C-101`, `V-201`).*"
        )

        return PIDEnhancedEvidenceResponse(
            question=question,
            target_entity=target,
            selected_drawing=None,
            alternate_drawings=[],
            evidence_tier=tier,
            topology=topo_res,
            contract=contract.model_dump(),
            assessment=assessment.model_dump(),
            evidence_debt=assessment.evidence_debt.model_dump(),
            retrieved_documents=[],
            evidence_claims=claims,
            safety_decision="BLOCKED_BY_CONTEXT_GUARD",
            safety_blockers=[f"UNKNOWN_MRPL_ENTITY: {target}"],
            recommendations=[f"Verify the equipment tag '{target}' against registered MRPL plant drawings."],
            final_synthesis=synthesis,
        )
