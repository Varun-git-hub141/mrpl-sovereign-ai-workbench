import re
import logging
from typing import Optional, List, Tuple, Set, Dict, Any
from backend.models.pid_graph_models import (
    QueryIntent,
    TraversalOperation,
    PIDQueryPlan,
    EdgeRelationship,
    NodeType,
)
from backend.services.pid.pid_loader import PIDKnowledgeLoader

logger = logging.getLogger("mrpl.pid_query_planner")


class PIDQueryPlanner:
    """
    Clean Semantic Query Planner for the Permanent P&ID Architecture (MRPL-PID-PERMANENT-P201).
    Interprets natural language engineering questions into deterministic topology operations:
    - UPSTREAM
    - DOWNSTREAM
    - ISOLATES
    - DISCHARGES
    """

    TAG_PATTERN = re.compile(
        r"\b([A-Z]{1,4}-[0-9]{1,4}[A-Z]{0,2}|[A-Z]{2,4}_[A-Z0-9_]+|TK-[0-9]{3}|P-[0-9]{3}[A-B]?|C-[0-9]{3}|V-[0-9]{3}|E-[0-9]{3}|Y-[0-9]{3}|MOV-[0-9]{3}|XV-[0-9]{3}[A-B]?|PSV-[0-9]{3}[A-B]?|PCV-[0-9]{3}|FCV-[0-9]{3}|PI-[0-9]{3}|PT-[0-9]{3}|TI-[0-9]{3}|TE-[0-9]{3}|PIC-[0-9]{3}|FIC-[0-9]{3}|LIC-[0-9]{3}|CV-[0-9]{3}|PG-[0-9]{3}|DV-[0-9]{3})\b",
        re.IGNORECASE,
    )

    def __init__(self, loader: PIDKnowledgeLoader):
        self.loader = loader
        self.permanent_graph = loader.get_graph(PIDKnowledgeLoader.PERMANENT_DRAWING_ID)

    def plan_query(self, question: str, requested_drawing_id: Optional[str] = None, requested_target: Optional[str] = None) -> PIDQueryPlan:
        q_raw = question.strip()
        q_lower = q_raw.lower()

        # Target Entity Resolution
        target_tag = requested_target
        if not target_tag:
            target_tag = self._extract_target_tag(q_raw)

        is_resolved = True
        unresolved_reason = None
        drawing_id = PIDKnowledgeLoader.PERMANENT_DRAWING_ID
        selected_drawing = drawing_id
        alternate_drawings: List[str] = []
        resolution_reason = "Single permanent built-in architecture context (ChatGPT Image Sep 22, 2026, 06_54_04 PM.png)."
        ambiguity_status = "PERMANENT_ARCHITECTURE"

        permanent_tags = {n.tag.upper() for n in self.permanent_graph.nodes} if self.permanent_graph else set()

        if target_tag:
            tag_u = target_tag.upper().strip()
            if tag_u not in permanent_tags:
                is_resolved = False
                unresolved_reason = (
                    f"Target '{target_tag}' is not present in the currently configured permanent P&ID architecture "
                    f"('{PIDKnowledgeLoader.PERMANENT_IMAGE_NAME}'). No topology relationship can be established."
                )
        else:
            # Default to primary asset P-201
            target_tag = "P-201"

        # Classify the Four Semantic Operations
        intent, operation, direction, rel_types = self._classify_intent(q_lower, target_tag)

        return PIDQueryPlan(
            intent=intent,
            target_entity=target_tag,
            drawing_id=drawing_id,
            selected_drawing=selected_drawing,
            alternate_drawings=alternate_drawings,
            resolution_reason=resolution_reason,
            ambiguity_status=ambiguity_status,
            relationship_types=rel_types,
            direction=direction,
            max_depth=5,
            operation=operation,
            is_resolved=is_resolved,
            unresolved_reason=unresolved_reason,
        )

    def _extract_target_tag(self, text: str) -> Optional[str]:
        # Priority 1: Direct matches against known tags in permanent architecture
        if self.permanent_graph:
            for node in self.permanent_graph.nodes:
                pattern = rf"\b{re.escape(node.tag)}\b"
                if re.search(pattern, text, re.IGNORECASE):
                    return node.tag

        # Priority 2: Standard engineering tag pattern (e.g., P-101, PSV-101, XYZ-999)
        matches = self.TAG_PATTERN.findall(text)
        if matches:
            return matches[0].upper()

        # Priority 3: Natural language equipment aliases
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

    def _is_safety_device_target(self, target_tag: Optional[str]) -> bool:
        if not target_tag:
            return False
        tag_u = target_tag.upper().strip()
        if any(tag_u.startswith(prefix) for prefix in ["PSV-", "PRV-", "RV-", "RD-", "TSV-", "PSV", "PRV", "RV"]):
            return True
        if self.permanent_graph:
            for node in self.permanent_graph.nodes:
                if node.tag.upper() == tag_u and node.type == NodeType.SAFETY_VALVE:
                    return True
        return False

    def _classify_intent(
        self, q: str, target_tag: Optional[str]
    ) -> Tuple[QueryIntent, TraversalOperation, str, List[EdgeRelationship]]:
        is_safety_target = self._is_safety_device_target(target_tag)
        has_relief_keyword = any(w in q for w in ["relieve", "relieves", "relieving", "relief", "flare routing", "safety valve"])

        # 1. ISOLATES (Isolation boundary / block valves)
        if any(w in q for w in ["isolate", "isolation", "isolated", "loto", "block valve", "double block", "dbb", "boundary"]):
            return (
                QueryIntent.ISOLATION,
                TraversalOperation.BOUNDARY_SEARCH,
                "BOTH",
                [EdgeRelationship.ISOLATES, EdgeRelationship.FEEDS, EdgeRelationship.CONNECTED_TO],
            )

        # 2. DISCHARGES (Only for relief / safety device discharge destination)
        if (is_safety_target or has_relief_keyword) and any(w in q for w in ["discharge", "discharges", "relieve", "relieves", "relief", "destination", "relief routing", "relieving to", "vent destination"]):
            return (
                QueryIntent.PSV_DISCHARGE,
                TraversalOperation.TRAVERSE_OUTGOING,
                "OUTGOING",
                [EdgeRelationship.RELIEVES_TO, EdgeRelationship.DISCHARGES_TO, EdgeRelationship.FEEDS, EdgeRelationship.CONNECTED_TO],
            )

        # 3. UPSTREAM (Process inflow before target)
        if (
            "upstream" in q
            or "before" in q
            or "what's before" in q
            or "comes before" in q
            or "what comes before" in q
            or "immediately before" in q
            or "suction side" in q
            or "suction of" in q
            or "suction" in q
            or "inlet side" in q
            or "inlet of" in q
            or "inlet to" in q
            or "inlet from" in q
            or "inlet" in q
            or "suction source" in q
            or "supplied from" in q
            or "feed line" in q
            or "feeds into" in q
            or "line feeds" in q
            or "feed from" in q
            or re.search(r"\bwhat\s+feeds\b", q)
            or re.search(r"\bwhich\s+equipment\s+is\s+before\b", q)
            or re.search(r"\bwhat\s+is\s+before\b", q)
            or re.search(r"\bwhat\s+is\s+on\s+the\s+suction\b", q)
        ):
            return (
                QueryIntent.UPSTREAM,
                TraversalOperation.TRAVERSE_INCOMING,
                "INCOMING",
                [EdgeRelationship.FEEDS, EdgeRelationship.DISCHARGES_TO, EdgeRelationship.CONNECTED_TO],
            )

        # 4. DOWNSTREAM (Process outflow after target, including equipment/valve process discharge)
        if (
            "downstream" in q
            or "after" in q
            or "what's after" in q
            or "comes after" in q
            or "what comes after" in q
            or "immediately after" in q
            or "outlet side" in q
            or "outlet of" in q
            or "outlet to" in q
            or "outlet" in q
            or "discharge side" in q
            or "send flow" in q
            or "sends flow" in q
            or "receives flow" in q
            or "delivery header" in q
            or "flows into" in q
            or "flows to" in q
            or "connected downstream" in q
            or "receives" in q
            or "discharge" in q
            or "discharges" in q
            or re.search(r"\bwhat\s+(does|do)\s+.*\s+feed\b", q)
            or re.search(r"\bwhere\s+does\s+.*\s+flow\b", q)
            or re.search(r"\bwhere\s+does\s+.*\s+send\b", q)
            or re.search(r"\bwhat\s+is\s+connected\s+downstream\b", q)
            or re.search(r"\bwhere\s+does\s+.*\s+send\s+flow\b", q)
            or "feed" in q
            or "feeds" in q
        ):
            return (
                QueryIntent.DOWNSTREAM,
                TraversalOperation.TRAVERSE_OUTGOING,
                "OUTGOING",
                [EdgeRelationship.FEEDS, EdgeRelationship.DISCHARGES_TO, EdgeRelationship.CONNECTED_TO],
            )

        # Default fallback to DOWNSTREAM traversal
        return (
            QueryIntent.DOWNSTREAM,
            TraversalOperation.TRAVERSE_OUTGOING,
            "OUTGOING",
            [EdgeRelationship.FEEDS, EdgeRelationship.CONNECTED_TO],
        )

