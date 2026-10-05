import logging
from typing import Dict, Any, Optional, List
from backend.models.entity_models import (
    EntityResolutionResult,
    EntityResolutionStatus,
    ContextGuardDecision,
)
from backend.models.rag_models import RetrievedChunk

logger = logging.getLogger("mrpl.context_guard")


class MRPLContextGuard:
    """
    MRPL Context Guard:
    Enforces strict sovereignty, entity precedence, and unknown entity protection.

    Rules:
    1. For organization-specific entities, LOCAL MRPL KNOWLEDGE MUST TAKE PRECEDENCE OVER GENERAL/PRETRAINED MODEL KNOWLEDGE.
    2. Unknown Entity Protection: If an entity (e.g. P-999) is NOT in the MRPL Knowledge Base, return a strict refusal without hallucination.
    3. General Queries: General queries without MRPL entities flow to general reasoning models.
    """

    def __init__(self):
        pass

    @staticmethod
    def evaluate(
        entity_res: EntityResolutionResult,
        query: str,
        allow_unverified_fallback: bool = False,
    ) -> ContextGuardDecision:
        """
        Evaluates query and entity resolution result against Context Guard policies.
        Enforces local knowledge boundary and user-controlled general LLM fallback.
        """
        # Case A: Unknown equipment-like entity requested (Neither in KB nor in Asset Registry)
        if entity_res.resolution_status in [EntityResolutionStatus.NOT_FOUND_IN_KB, EntityResolutionStatus.NOT_FOUND]:
            raw = entity_res.raw_entity or entity_res.entity or "Target entity"

            # Check if user explicitly activated user-controlled fallback
            if allow_unverified_fallback:
                logger.info(f"ContextGuard ALLOWING explicit user-requested general LLM fallback for {raw}")
                directive = (
                    "You are operating in GENERAL KNOWLEDGE MODE.\n\n"
                    f"The requested entity ({raw}) could not be found in the MRPL Local Knowledge Base or the MRPL Asset Registry.\n\n"
                    "You may answer using your pretrained/general knowledge.\n\n"
                    "IMPORTANT:\n"
                    "- Do not claim that any information is MRPL-specific.\n"
                    "- Do not invent MRPL records or equipment specifications.\n"
                    "- Do not present general knowledge as verified organizational knowledge.\n"
                    "- Clearly state that the response is UNVERIFIED GENERAL KNOWLEDGE — NOT MRPL-VERIFIED.\n"
                    "- This response is NOT MRPL evidence and cannot satisfy Evidence Contract requirements.\n"
                    "- If the entity is ambiguous, explain the ambiguity.\n"
                    "- Prefer saying that you do not know rather than fabricating facts."
                )
                warning_banner = "UNVERIFIED GENERAL KNOWLEDGE — NOT MRPL-VERIFIED"
                return ContextGuardDecision(
                    is_mrpl_entity=False,
                    entity_tag=raw,
                    knowledge_precedence="GENERAL_UNVERIFIED_FALLBACK",
                    should_retrieve_rag=False,
                    unknown_entity_blocked=False,
                    allow_unverified_fallback=True,
                    guarded_response=None,
                    context_directive=directive,
                    warning_banner=warning_banner,
                    context_guard_status="GENERAL_UNVERIFIED_FALLBACK",
                )

            # Strict Boundary Guard: Block general LLM automatically
            refusal_msg = (
                f"Entity: {raw}\n\n"
                "MRPL Knowledge Base Status:\n"
                "NOT FOUND\n\n"
                "Asset Registry Status:\n"
                "NOT FOUND\n\n"
                "Context Guard:\n"
                "LOCAL ENTITY NOT RESOLVED\n\n"
                "Answer:\n"
                f"\"{raw} could not be found in the MRPL Local Knowledge Base or the MRPL Asset Registry. "
                "No authoritative organization-specific information is available for this equipment.\n\n"
                "The system will not use pretrained/general knowledge to make MRPL-specific claims about this equipment.\""
            )
            logger.info(f"ContextGuard BLOCKED unknown entity: {raw}")
            return ContextGuardDecision(
                is_mrpl_entity=False,
                entity_tag=raw,
                knowledge_precedence="UNKNOWN_ENTITY_BLOCKED",
                should_retrieve_rag=False,
                unknown_entity_blocked=True,
                allow_unverified_fallback=False,
                guarded_response=refusal_msg,
                context_directive="UNKNOWN_ENTITY: Return strict local knowledge absence statement.",
                warning_banner="LOCAL MRPL KNOWLEDGE NOT FOUND — GENERAL LLM BLOCKED",
                context_guard_status="LOCAL ENTITY NOT RESOLVED",
            )

        # Case B: Entity found in Dynamic Asset Registry only (Identity established, but standalone KB absent)
        if entity_res.resolution_status == EntityResolutionStatus.FOUND_IN_ASSET_REGISTRY:
            tag = entity_res.canonical_name or entity_res.raw_entity
            asset_rec = entity_res.asset_record or {}
            unit_str = asset_rec.get("process_unit", "Refinery Unit")
            name_str = asset_rec.get("asset_name", "Registered Asset")
            class_str = asset_rec.get("asset_class", "EQUIPMENT")
            
            directive = (
                f"LOCAL MRPL ASSET REGISTRY CONTEXT for entity {tag}.\n"
                f"Asset {tag} is registered in the MRPL Asset Registry ({name_str}, Unit: {unit_str}, Class: {class_str}).\n"
                "IMPORTANT KNOWLEDGE BOUNDARIES:\n"
                "- Asset Registry metadata establishes equipment identity, components, and inspection locations, but does NOT establish standalone inspection measurements or historical engineering facts without supporting engineering evidence.\n"
                "- Use only verified attached evidence documents and observations.\n"
                "- If no supporting engineering evidence is attached or found in RAG, clearly state: 'Asset exists in Asset Registry, but supporting engineering evidence was not found.'\n"
                "- Do not invent engineering facts or measurements from registry metadata."
            )
            return ContextGuardDecision(
                is_mrpl_entity=True,
                entity_tag=tag,
                knowledge_precedence="MRPL_ASSET_REGISTRY",
                should_retrieve_rag=True,
                unknown_entity_blocked=False,
                guarded_response=None,
                context_directive=directive,
                context_guard_status="ASSET_REGISTRY_IDENTIFIED",
            )

        # Case C: Verified MRPL Entity Found in KB (e.g. P-201, P-101, V-201)
        if entity_res.resolution_status == EntityResolutionStatus.FOUND_IN_MRPL_KB:
            tag = entity_res.canonical_name or entity_res.raw_entity
            directive = (
                f"AUTHORITATIVE LOCAL MRPL CONTEXT ENFORCED for entity {tag}. "
                "You are an on-premise refinery engineering assistant for Mangalore Refinery and Petrochemicals Limited (MRPL). "
                f"You MUST use ONLY the verified MRPL retrieved evidence below to answer questions about {tag}. "
                "DO NOT use unrelated pretrained knowledge or invent external specifications. "
                "Cite the source document and page number for all factual claims."
            )
            return ContextGuardDecision(
                is_mrpl_entity=True,
                entity_tag=tag,
                knowledge_precedence="MRPL_AUTHORITATIVE",
                should_retrieve_rag=True,
                unknown_entity_blocked=False,
                guarded_response=None,
                context_directive=directive,
                context_guard_status="KB_AUTHORITATIVE_ENFORCED",
            )

        # Case C: No entity detected (General Query or Code)
        return ContextGuardDecision(
            is_mrpl_entity=False,
            entity_tag=None,
            knowledge_precedence="GENERAL_FALLBACK",
            should_retrieve_rag=False,
            unknown_entity_blocked=False,
            guarded_response=None,
            context_directive="Standard reasoning context.",
        )

    @staticmethod
    def build_grounded_system_prompt(
        guard_decision: ContextGuardDecision,
        retrieved_chunks: List[RetrievedChunk],
        base_system_prompt: Optional[str] = None,
        question_guidance: Optional[str] = None,
    ) -> str:
        """
        Constructs a strict provenance-grounded system prompt embedding retrieved evidence
        and explicitly labeled provenance categories.
        """
        if not guard_decision.is_mrpl_entity or not retrieved_chunks:
            return base_system_prompt or "You are a helpful, sovereign industrial AI engineering assistant."

        evidence_blocks = []
        for idx, chunk in enumerate(retrieved_chunks, 1):
            src = chunk.source
            score = chunk.retrieval.hybrid_score if chunk.retrieval else 1.0
            evidence_blocks.append(
                f"[EVIDENCE ITEM {idx}]\n"
                f"- Origin: MRPL LOCAL KNOWLEDGE BASE\n"
                f"- Category: DIRECT MRPL RECORD\n"
                f"- Document: {src.document} (ID: {src.document_id})\n"
                f"- Document Type: {src.document_type} | Page: {src.page} | Section: {src.section}\n"
                f"- Equipment Tag: {src.equipment_tag or guard_decision.entity_tag} | Date: {src.date}\n"
                f"- Hybrid Score: {score} | Authority: {chunk.authority_level.value}\n"
                f"- Content:\n{chunk.text.strip()}\n"
            )

        evidence_text = "\n".join(evidence_blocks)

        guidance_section = ""
        if question_guidance:
            guidance_section = (
                "\n═══════════════════════════════════════════════════════════════\n"
                "QUESTION TYPE & CLAIM PROVENANCE DIRECTIVE:\n"
                f"{question_guidance}\n"
                "═══════════════════════════════════════════════════════════════\n"
            )

        prompt = (
            "═══════════════════════════════════════════════════════════════\n"
            "MANGALORE REFINERY AND PETROCHEMICALS LIMITED (MRPL)\n"
            "SOVEREIGN ON-PREMISE HYBRID RAG CONTEXT GUARD (AUTHORITATIVE)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            f"TARGET ENTITY: {guard_decision.entity_tag}\n"
            "POLICY DIRECTIVES:\n"
            "- Local MRPL Knowledge takes absolute precedence over pretrained model memory.\n"
            f"- Answer the user's query regarding {guard_decision.entity_tag} using ONLY the verified evidence items below.\n"
            "- LLM ROLE: EVIDENCE SYNTHESIS / REASONING ONLY. The LLM is NOT the source of MRPL facts.\n"
            "- STRICT ASSET ISOLATION: Use ONLY evidence belonging directly to the target equipment.\n"
            f"- Never apply measurements, thickness records, or provenance from another asset (such as P-201) to {guard_decision.entity_tag}.\n"
            f"- If the query requests evaluating {guard_decision.entity_tag} using another asset's records (e.g., P-201 records), explicitly report the ASSET MISMATCH / EVIDENCE MISMATCH and do not calculate {guard_decision.entity_tag} values from another equipment's data.\n"
            "- Never convert CALCULATED_FROM_MRPL_EVIDENCE into EXPLICITLY_RECORDED.\n"
            "- If an explicitly recorded value does not exist, clearly state that no recorded value was found.\n"
            "- If providing a calculated value, explicitly state that it is a deterministic calculation derived from MRPL data.\n"
            "- Every factual claim MUST cite its source document and page number (e.g. [Source: EQ_MASTER_P201.json, Page 1]).\n"
            f"{guidance_section}\n"
            "AUTHORITATIVE RETRIEVED EVIDENCE:\n"
            f"{evidence_text}\n"
            "═══════════════════════════════════════════════════════════════"
        )
        return prompt
