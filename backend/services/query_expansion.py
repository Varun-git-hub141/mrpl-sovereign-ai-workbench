# -*- coding: utf-8 -*-
"""
MRPL Sovereign AI Workbench — Automatic Query Expansion Engine
Evidence-driven query expansion for incomplete or insufficient retrieval context.

Executes iterative retrieval rounds (max 3 rounds) using existing Hybrid RAG
(BM25 + Vector + Metadata Filtering + Reranking), merges/deduplicates chunks,
and recalculates Confidence Engine metrics after each round.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel, Field

from backend.models.rag_models import RetrievedChunk, HybridSearchRequest
from backend.models.execution_plan import ExecutionPlan
from backend.services.hybrid_rag import HybridRAGService
from backend.services.confidence_engine import ConfidenceEngine

logger = logging.getLogger("mrpl.query_expansion")


class ExpansionRoundRecord(BaseModel):
    round_number: int
    missing_claims: List[str] = Field(default_factory=list)
    generated_subqueries: List[str] = Field(default_factory=list)
    new_chunks_retrieved: int = 0
    retrieved_documents: List[str] = Field(default_factory=list)
    retrieved_chunks_summary: List[str] = Field(default_factory=list)
    total_accumulated_chunks: int = 0
    retrieval_score: float = 0.0
    evidence_coverage: float = 0.0
    verification_score: float = 0.0
    overall_confidence: float = 0.0
    confidence_delta: float = 0.0
    stop_condition_met: bool = False
    stop_reason: Optional[str] = None


class QueryExpansionResult(BaseModel):
    expansion_executed: bool = False
    original_query: str = ""
    trigger_reason: str = ""
    initial_confidence: float = 0.0
    final_confidence: float = 0.0
    final_status: str = "HIGH"
    stopping_reason: str = ""
    initial_missing_evidence: List[str] = Field(default_factory=list)
    rounds_executed: int = 0
    max_rounds: int = 3
    rounds: List[ExpansionRoundRecord] = Field(default_factory=list)
    missing_evidence_final: List[str] = Field(default_factory=list)
    merged_chunks: List[Any] = Field(default_factory=list)
    is_sufficient: bool = True
    summary: str = ""


class QueryExpansionEngine:
    """
    Automatic Query Expansion Engine.
    Executes targeted, evidence-driven subquery retrieval loops when initial RAG retrieval
    lacks required engineering claims or exhibits low overall confidence.
    """

    MAX_EXPANSION_ROUNDS = 3
    TARGET_CONFIDENCE_THRESHOLD = 0.85

    def __init__(
        self,
        hybrid_rag: Optional[HybridRAGService] = None,
        confidence_engine: Optional[ConfidenceEngine] = None,
    ):
        self.hybrid_rag = hybrid_rag or HybridRAGService()
        self.confidence_engine = confidence_engine or ConfidenceEngine()

    def generate_targeted_subqueries(
        self,
        query: str,
        missing_claims: List[str],
        entity_tag: Optional[str] = None,
    ) -> List[str]:
        """
        Generates evidence-driven targeted search subqueries tailored to missing facts.
        """
        subqueries: List[str] = []
        tag = entity_tag or ""

        # Map missing claim keywords to targeted engineering search terms
        for claim in missing_claims:
            c_lower = claim.lower()
            if "historical corrosion rate" in c_lower or "explicit recorded" in c_lower or "corrosion rate" in c_lower:
                subqueries.append(f"{tag} previous corrosion rate inspection".strip())
                subqueries.append(f"{tag} historical corrosion rate".strip())
                subqueries.append(f"{tag} 2019 inspection corrosion rate".strip())
                subqueries.append(f"{tag} baseline inspection corrosion rate".strip())
                subqueries.append(f"{tag} recorded corrosion rate".strip())
            elif "baseline" in c_lower or "previous" in c_lower or "original thickness" in c_lower:
                subqueries.append(f"{tag} previous wall thickness baseline 2019 inspection".strip())
                subqueries.append(f"{tag} commissioning baseline thickness records".strip())
            elif "current thickness" in c_lower or "casing" in c_lower or "recent thickness" in c_lower:
                subqueries.append(f"{tag} current casing thickness inspection NDT report 2024".strip())
                subqueries.append(f"{tag} ultrasonic thickness measurement survey latest".strip())
            elif "minimum allowable" in c_lower or "tmin" in c_lower or "retirement" in c_lower:
                subqueries.append(f"{tag} minimum allowable retirement thickness tmin design calculation ASME".strip())
                subqueries.append(f"{tag} API 570 minimum allowable casing thickness limit".strip())
            elif "interval" in c_lower or "date" in c_lower or "year" in c_lower:
                subqueries.append(f"{tag} inspection interval timeline baseline to current".strip())
            elif "recommendation" in c_lower or "decision" in c_lower or "operation" in c_lower:
                subqueries.append(f"{tag} engineering recommendation continued operation fitness for service".strip())
                subqueries.append(f"{tag} previous engineering decision MOC approval".strip())
            elif "inspection" in c_lower or "finding" in c_lower or "ndt" in c_lower:
                subqueries.append(f"{tag} ultrasonic thickness inspection findings integrity summary".strip())
            else:
                subqueries.append(f"{tag} {claim}".strip())

        # Fallback default subquery if none mapped
        if not subqueries:
            subqueries.append(f"{tag} asset engineering integrity dossier and inspection log".strip())

        # Deduplicate while preserving order, limit to 5 subqueries per round
        unique_subqueries = list(dict.fromkeys(subqueries))[:5]
        return unique_subqueries

    def run_expansion_loop(
        self,
        plan: ExecutionPlan,
        initial_chunks: List[RetrievedChunk],
        query: str,
        entity_tag: Optional[str] = None,
        deterministic_calc: Optional[Dict[str, Any]] = None,
        task_type: Optional[str] = None,
        target_confidence: float = 0.85,
    ) -> QueryExpansionResult:
        """
        Executes the up-to-3-round query expansion loop:
        1. Identify missing claims
        2. Generate targeted subqueries
        3. Retrieve using existing Hybrid RAG
        4. Merge & deduplicate evidence
        5. Detect contradictions
        6. Recalculate Retrieval Score, Evidence Coverage, Verification Score, Overall Confidence
        7. Stop when confidence threshold met AND critical claims supported AND no contradiction.
        """
        # Step 0: Initial Confidence evaluation
        initial_assessment = self.confidence_engine.evaluate_confidence(
            plan=plan,
            retrieved_chunks=initial_chunks,
            entity_tag=entity_tag,
            deterministic_calc=deterministic_calc,
            task_type=task_type,
        )

        init_conf = initial_assessment["overall_confidence"]
        missing_claims = initial_assessment["missing_evidence"]

        # If initial confidence is already high and no critical claims are missing, return immediately
        if init_conf >= target_confidence and not missing_claims and not initial_assessment["verification_details"]["contradiction_detected"]:
            return QueryExpansionResult(
                expansion_executed=False,
                original_query=query,
                trigger_reason="Initial hybrid retrieval satisfied all required claims with high confidence.",
                initial_confidence=init_conf,
                final_confidence=init_conf,
                final_status="HIGH",
                stopping_reason="Confidence threshold reached on initial retrieval.",
                initial_missing_evidence=[],
                rounds_executed=0,
                max_rounds=self.MAX_EXPANSION_ROUNDS,
                rounds=[],
                missing_evidence_final=[],
                merged_chunks=initial_chunks,
                is_sufficient=True,
                summary="Initial hybrid retrieval satisfied all required claims with high confidence.",
            )

        # Start expansion loop
        accumulated_chunks = list(initial_chunks)
        rounds_records: List[ExpansionRoundRecord] = []
        current_conf = init_conf
        prev_conf = init_conf
        final_missing = list(missing_claims)

        trigger_reason = f"Initial confidence {init_conf:.2f} < threshold {target_confidence:.2f}"
        if missing_claims:
            trigger_reason += f" with missing claims: {', '.join(missing_claims[:2])}"

        for round_idx in range(1, self.MAX_EXPANSION_ROUNDS + 1):
            # 1. Identify missing claims
            current_eval = self.confidence_engine.evaluate_confidence(
                plan=plan,
                retrieved_chunks=accumulated_chunks,
                entity_tag=entity_tag,
                deterministic_calc=deterministic_calc,
                task_type=task_type,
            )
            round_missing = current_eval["missing_evidence"]
            if not round_missing and current_eval["overall_confidence"] >= target_confidence:
                break

            # 2. Generate targeted subqueries
            subqueries = self.generate_targeted_subqueries(
                query=query,
                missing_claims=round_missing if round_missing else [query],
                entity_tag=entity_tag,
            )

            # 3. Retrieve using Hybrid RAG
            new_chunks_count = 0
            round_docs: List[str] = []
            round_chunk_summaries: List[str] = []
            existing_texts = {getattr(c, "text", "").strip() for c in accumulated_chunks}

            for subq in subqueries:
                search_req = HybridSearchRequest(
                    query=subq,
                    equipment_tag=entity_tag,
                    top_k=4,
                )
                try:
                    sub_chunks = self.hybrid_rag.hybrid_search(search_req)
                    for sc in sub_chunks:
                        sc_text = getattr(sc, "text", "").strip()
                        doc_name = getattr(getattr(sc, "source", None), "document", "MRPL KB Document")
                        page_num = getattr(getattr(sc, "source", None), "page", 1)
                        # Deduplicate by content
                        if sc_text and sc_text not in existing_texts:
                            existing_texts.add(sc_text)
                            accumulated_chunks.append(sc)
                            new_chunks_count += 1
                            if doc_name not in round_docs:
                                round_docs.append(doc_name)
                            round_chunk_summaries.append(f"{doc_name} (p.{page_num}): {sc_text[:100]}...")
                except Exception as e:
                    logger.warning(f"Subquery retrieval failed for '{subq}': {e}")

            # 4. Recalculate metrics
            new_eval = self.confidence_engine.evaluate_confidence(
                plan=plan,
                retrieved_chunks=accumulated_chunks,
                entity_tag=entity_tag,
                deterministic_calc=deterministic_calc,
                task_type=task_type,
            )

            new_conf = new_eval["overall_confidence"]
            final_missing = new_eval["missing_evidence"]
            contradiction = new_eval["verification_details"]["contradiction_detected"]
            delta = round(new_conf - prev_conf, 2)

            stop_met = (new_conf >= target_confidence and len(final_missing) == 0 and not contradiction)
            stop_reason = None
            if stop_met:
                stop_reason = f"Confidence threshold reached ({new_conf:.2f} >= {target_confidence:.2f}) with all critical claims supported."
            elif round_idx == self.MAX_EXPANSION_ROUNDS:
                if new_conf >= target_confidence:
                    stop_reason = "Maximum expansion rounds reached (Confidence satisfied)."
                else:
                    stop_reason = "Maximum expansion rounds reached (Evidence remains insufficient for unrecorded claims)."

            rec = ExpansionRoundRecord(
                round_number=round_idx,
                missing_claims=round_missing,
                generated_subqueries=subqueries,
                new_chunks_retrieved=new_chunks_count,
                retrieved_documents=round_docs,
                retrieved_chunks_summary=round_chunk_summaries,
                total_accumulated_chunks=len(accumulated_chunks),
                retrieval_score=new_eval["retrieval_score"],
                evidence_coverage=new_eval["evidence_coverage"],
                verification_score=new_eval["verification_score"],
                overall_confidence=new_conf,
                confidence_delta=delta,
                stop_condition_met=stop_met,
                stop_reason=stop_reason,
            )
            rounds_records.append(rec)
            prev_conf = new_conf
            current_conf = new_conf

            if stop_met:
                break

        if current_conf >= 0.90:
            final_status = "HIGH"
        elif current_conf >= 0.75:
            final_status = "MEDIUM"
        elif current_conf >= 0.60:
            final_status = "LOW"
        else:
            final_status = "INSUFFICIENT"

        last_stop = rounds_records[-1].stop_reason if rounds_records else "Completed"
        is_sufficient = (current_conf >= 0.75) and len(final_missing) == 0

        summary = (
            f"Query Expansion completed {len(rounds_records)} round(s). "
            f"Confidence progressed from {init_conf:.2f} → {current_conf:.2f}. "
            f"Accumulated {len(accumulated_chunks)} evidence chunks. Stopping Reason: {last_stop}"
        )

        return QueryExpansionResult(
            expansion_executed=True,
            original_query=query,
            trigger_reason=trigger_reason,
            initial_confidence=init_conf,
            final_confidence=current_conf,
            final_status=final_status,
            stopping_reason=last_stop,
            initial_missing_evidence=missing_claims,
            rounds_executed=len(rounds_records),
            max_rounds=self.MAX_EXPANSION_ROUNDS,
            rounds=rounds_records,
            missing_evidence_final=final_missing,
            merged_chunks=accumulated_chunks,
            is_sufficient=is_sufficient,
            summary=summary,
        )
