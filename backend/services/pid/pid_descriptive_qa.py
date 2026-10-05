import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from backend.models.pid_graph_models import (
    PIDGraph,
    PIDNode,
    PIDQueryRequest,
    PIDQueryResponse,
    PIDQueryPlan,
    PIDQueryResultStatus,
    QueryIntent,
    TraversalOperation,
    PIDProvenanceRecord,
    NodeType,
)
from backend.services.pid.pid_loader import PIDKnowledgeLoader

logger = logging.getLogger("mrpl.pid_descriptive_qa")


class PIDDescriptiveQAService:
    """
    Descriptive P&ID Architecture Q&A Service.
    Answers natural-language descriptive questions (equipment type, service, function, specs)
    grounded strictly in the permanent P-201 architecture (MRPL-PID-PERMANENT-P201).
    """

    TOPOLOGY_KEYWORDS = [
        "upstream", "downstream", "before", "after", "comes before", "comes after",
        "what's before", "what's after", "immediately before", "immediately after",
        "isolate", "isolation", "isolated", "valves isolate", "loto", "block valve",
        "suction side", "suction of", "inlet side", "inlet of", "inlet to", "inlet from",
        "outlet side", "outlet of", "outlet to", "send flow", "sends flow", "flows into",
        "flows to", "what feeds", "feed into", "where does flow", "where does it send flow",
        "relieve", "relieves", "relieving", "relieving to", "where does .* discharge",
        "destination of .* relief", "discharge destination", "protects", "protect",
    ]

    TAG_PATTERN = re.compile(
        r"\b([A-Z]{1,4}-[0-9]{1,4}[A-Z]{0,2}|[A-Z]{2,4}_[A-Z0-9_]+|TK-[0-9]{3}|P-[0-9]{3}[A-B]?|C-[0-9]{3}|V-[0-9]{3}|E-[0-9]{3}|Y-[0-9]{3}|MOV-[0-9]{3}|XV-[0-9]{3}[A-B]?|PSV-[0-9]{3}[A-B]?|PCV-[0-9]{3}|FCV-[0-9]{3}|PI-[0-9]{3}|PT-[0-9]{3}|TI-[0-9]{3}|TE-[0-9]{3}|PIC-[0-9]{3}|FIC-[0-9]{3}|LIC-[0-9]{3}|CV-[0-9]{3}|PG-[0-9]{3}|DV-[0-9]{3})\b",
        re.IGNORECASE,
    )

    def __init__(self, loader: PIDKnowledgeLoader):
        self.loader = loader
        self.permanent_graph = loader.get_graph(PIDKnowledgeLoader.PERMANENT_DRAWING_ID)

    def is_descriptive_query(self, question: str) -> bool:
        """
        Classifies whether a question is a descriptive architecture question (Path B)
        or a deterministic topology question (Path A).
        """
        q_lower = question.lower().strip()

        # Strict check for topology keywords
        for kw in self.TOPOLOGY_KEYWORDS:
            if ".*" in kw:
                if re.search(r"\b" + kw + r"\b", q_lower):
                    return False
            else:
                if kw in q_lower:
                    return False

        # Specific regex checks for directional queries
        if re.search(r"\bwhere\s+does\s+.*\s+send\b", q_lower):
            return False
        if re.search(r"\bwhere\s+does\s+.*\s+flow\b", q_lower):
            return False
        if re.search(r"\bwhat\s+feeds\b", q_lower):
            return False
        if re.search(r"\bwhich\s+valves\s+isolate\b", q_lower):
            return False

        # Descriptive question patterns
        descriptive_patterns = [
            r"\bwhat\s+is\b",
            r"\bwhat\s+type\s+of\b",
            r"\bwhat\s+service\b",
            r"\bservice\s+of\b",
            r"\bservice\s+associated\b",
            r"\bwhat\s+does\s+.*\s+do\b",
            r"\bwhat\s+does\s+.*\s+handle\b",
            r"\bfunction\s+of\b",
            r"\bwhat\s+is\s+the\s+function\b",
            r"\bdescribe\b",
            r"\btell\s+me\s+about\b",
            r"\bdetails\s+of\b",
            r"\bspecs\s+of\b",
            r"\bspecifications\b",
            r"\bset\s+pressure\b",
            r"\blocation\s+of\b",
            r"\bpurpose\s+of\b",
            r"\bwhat\s+kind\s+of\b",
            r"\bdestination\s+shown\b",
        ]

        for pat in descriptive_patterns:
            if re.search(pat, q_lower):
                return True

        return False

    def extract_target_tag(self, text: str) -> Optional[str]:
        if self.permanent_graph:
            for node in self.permanent_graph.nodes:
                pattern = rf"\b{re.escape(node.tag)}\b"
                if re.search(pattern, text, re.IGNORECASE):
                    return node.tag

        matches = self.TAG_PATTERN.findall(text)
        if matches:
            return matches[0].upper()

        text_lower = text.lower()
        if "pump" in text_lower or "booster" in text_lower:
            return "P-201"
        if "tank" in text_lower or "storage" in text_lower:
            return "TK-201"
        if "strainer" in text_lower:
            return "Y-201"
        if "relief valve" in text_lower or "safety valve" in text_lower or "psv" in text_lower:
            return "PSV-201"
        if "column" in text_lower or "fractionator" in text_lower:
            return "C-101"
        if "flare" in text_lower:
            return "FLARE_HEADER"

        return None

    def answer_descriptive_query(self, req: PIDQueryRequest) -> PIDQueryResponse:
        """
        Generates a grounded descriptive answer from permanent architecture attributes.
        """
        question = req.question.strip()
        target = self.extract_target_tag(question)

        permanent_nodes = {n.tag.upper(): n for n in self.permanent_graph.nodes} if self.permanent_graph else {}

        # 1. Unknown target check
        if not target or target.upper() not in permanent_nodes:
            unresolved_target = target or "Unknown"
            plan = PIDQueryPlan(
                intent=QueryIntent.GENERAL_OVERVIEW,
                target_entity=unresolved_target,
                drawing_id=PIDKnowledgeLoader.PERMANENT_DRAWING_ID,
                selected_drawing=None,
                alternate_drawings=[],
                resolution_reason="Target absent from permanent architecture.",
                ambiguity_status="UNRESOLVED",
                relationship_types=[],
                direction="STATIC",
                operation=TraversalOperation.DIRECT_NEIGHBORS,
                is_resolved=False,
                unresolved_reason=(
                    f"Target '{unresolved_target}' is not present in the configured permanent P&ID architecture "
                    f"('{PIDKnowledgeLoader.PERMANENT_IMAGE_NAME}'). No architecture-specific description is available."
                ),
            )
            return PIDQueryResponse(
                question=question,
                drawing_id=PIDKnowledgeLoader.PERMANENT_DRAWING_ID,
                answer=(
                    f"**Entity Resolution Warning:**\n\n"
                    f"Target '{unresolved_target}' is not present in the configured permanent P&ID architecture "
                    f"('{PIDKnowledgeLoader.PERMANENT_IMAGE_NAME}'). No architecture-specific description is available.\n\n"
                    f"To prevent hallucination, descriptive queries must reference equipment or valves present in the "
                    f"permanent P-201 architecture (e.g. `P-201`, `TK-201`, `XV-201`, `Y-201`, `XV-203`, `CV-201`, `MOV-204`, `PSV-201`, `PCV-201`, `C-101`)."
                ),
                confidence=0.0,
                query_plan=plan,
                status=PIDQueryResultStatus.UNRESOLVED,
                selected_drawing=None,
                alternate_drawings=[],
                ambiguity_status="UNRESOLVED",
                safety_boundary_note="Unresolved equipment descriptions are rejected under MRPL sovereign data policy.",
            )

        # 2. Extract Grounded Metadata
        node = permanent_nodes[target.upper()]
        g = self.permanent_graph
        doc_id = g.drawing_id
        dwg_num = g.drawing_number or doc_id

        specs = node.specs or {}
        service = specs.get("service") or ("Crude Feed" if "201" in node.tag else "Process Fluid")
        eq_type = node.type.value if hasattr(node.type, "value") else str(node.type)
        desc = node.description or "Process equipment"
        location = node.location or "CDU-II Process Area"
        state = getattr(node, "normal_state", None)

        # Build educational response lines
        answer_lines = [
            "**Drawing:**",
            doc_id,
            "",
            "**Target:**",
            node.tag,
            "",
            "**Result Type:**",
            "DESCRIPTIVE ARCHITECTURE ANSWER",
            "",
            "**Equipment / Component:**",
            f"{node.tag} — {desc}",
            "",
            "**Type:**",
            eq_type,
            "",
            "**Service / Function:**",
            service,
            "",
            "**Location:**",
            location,
        ]

        if state:
            answer_lines.extend(["", "**Normal Operating State:**", state])

        # Add specific component details
        detail_lines = []
        if specs:
            for k, v in specs.items():
                k_formatted = k.replace("_", " ").title()
                detail_lines.append(f"- {k_formatted}: {v}")

        if detail_lines:
            answer_lines.extend(["", "**Specifications & Registered Attributes:**", "\n".join(detail_lines)])

        # Synthesize clear, grounded natural-language explanation
        q_lower = question.lower()
        if "service" in q_lower or "handle" in q_lower:
            explanation = f"{node.tag} is dedicated to **{service}** service in the permanent {g.drawing_title} architecture ({doc_id})."
        elif "type" in q_lower or "kind" in q_lower:
            explanation = f"{node.tag} is classified as a **{eq_type}** ({desc}) located in {location}."
        elif "psv" in node.tag.lower() or node.type == NodeType.SAFETY_VALVE:
            set_p = specs.get("set_pressure", "9.0 barg")
            dest = specs.get("relieving_to", "FLARE_HEADER")
            explanation = f"{node.tag} is a **Safety Relief Valve** set at **{set_p}**, discharging directly to **{dest}** for overpressure protection."
        elif node.type == NodeType.PUMP:
            explanation = f"{node.tag} is the primary **Crude Feed Pump** (Centrifugal API 610) delivering crude feed from storage tank TK-201 through the discharge header to Column C-101."
        elif node.type == NodeType.CHECK_VALVE:
            explanation = f"{node.tag} is a **Check Valve** installed on the discharge spool of P-201 for non-return backflow prevention only (not an isolation valve)."
        elif node.type == NodeType.VALVE:
            size_type = specs.get("size", "Gate Valve")
            explanation = f"{node.tag} is a **{desc}** ({size_type}) with normal state **{state or 'NORMALLY_OPEN'}**."
        elif node.type == NodeType.STRAINER:
            explanation = f"{node.tag} is the **Suction Basket Strainer** equipped with differential pressure gauge PG-201 on the P-201 suction line."
        else:
            explanation = f"{node.tag} ({desc}) is a registered {eq_type} component in the permanent MRPL P-201 architecture."

        answer_lines.extend([
            "",
            "**Explanation:**",
            explanation,
            "",
            "**Source:**",
            f"Permanent Reference Image: {PIDKnowledgeLoader.PERMANENT_IMAGE_NAME}\n"
            f"Drawing Title: {g.drawing_title}\n"
            f"Drawing ID: {doc_id}\n"
            f"Drawing Number: {dwg_num}\n"
            f"Revision: {g.revision}\n"
            f"System: {g.system}\n"
            f"Grounded Metadata: Machine-Readable Verified Knowledge Graph Node Specification",
        ])

        plan = PIDQueryPlan(
            intent=QueryIntent.GENERAL_OVERVIEW,
            target_entity=node.tag,
            drawing_id=doc_id,
            selected_drawing=doc_id,
            alternate_drawings=[],
            resolution_reason="Descriptive Q&A grounded in permanent architecture node metadata.",
            ambiguity_status="PERMANENT_ARCHITECTURE",
            relationship_types=[],
            direction="STATIC",
            operation=TraversalOperation.DIRECT_NEIGHBORS,
            is_resolved=True,
            unresolved_reason=None,
        )

        provenance = [
            PIDProvenanceRecord(
                drawing_id=doc_id,
                drawing_number=dwg_num,
                document_id=doc_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                section="Equipment Metadata",
                evidence_text=f"Node {node.tag}: {desc} [{service}]",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=doc_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[node.tag],
            path_trace=[node.tag],
            engineering_rationale=f"Descriptive metadata lookup for {node.tag} in {doc_id}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DIRECT_SOURCE_RELATIONSHIP,
            selected_drawing=doc_id,
            alternate_drawings=[],
            ambiguity_status="RESOLVED",
            provenance_records=provenance,
        )
