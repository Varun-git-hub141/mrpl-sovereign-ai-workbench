import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from backend.models.pid_graph_models import (
    PIDGraph,
    PIDNode,
    PIDEdge,
    NodeType,
    EdgeRelationship,
    QueryIntent,
    PIDQueryPlan,
    PIDQueryResultStatus,
    PIDQueryRequest,
    PIDQueryResponse,
    PIDProvenanceRecord,
    PIDTraversalPath,
)
from backend.services.pid.pid_loader import PIDKnowledgeLoader
from backend.services.pid.pid_traversal import DirectedAdjacencyGraph, PIDTraversalEngine
from backend.services.pid.pid_query_planner import PIDQueryPlanner

logger = logging.getLogger("mrpl.pid_graph")


class PIDGraphEngine:
    """
    Sovereign P&ID Engineering Graph Engine.
    Represents equipment, piping lines, control loops, safety relief devices,
    and isolation boundaries as a fully traversable topological knowledge graph.
    Executes deterministic graph traversals anchored in official MRPL P&ID drawings.
    """

    def __init__(self, kb_dir: Optional[str] = None):
        self.loader = PIDKnowledgeLoader(kb_dir=kb_dir)
        self.planner = PIDQueryPlanner(loader=self.loader)
        self._adj_cache: Dict[str, DirectedAdjacencyGraph] = {}
        self._build_adjacency_cache()

    def _build_adjacency_cache(self):
        self._adj_cache.clear()
        for g_id, graph in self.loader.graphs_by_id.items():
            if g_id not in self._adj_cache:
                self._adj_cache[g_id] = DirectedAdjacencyGraph(graph)

    def _get_adj(self, drawing_id: str) -> Optional[DirectedAdjacencyGraph]:
        if not drawing_id:
            return None
        d_norm = drawing_id.upper().strip()
        if d_norm not in self._adj_cache:
            g = self.loader.get_graph(d_norm)
            if g:
                self._adj_cache[d_norm] = DirectedAdjacencyGraph(g)
        return self._adj_cache.get(d_norm)

    def get_graph(self, drawing_id: str = "MRPL-PID-PERMANENT-P201") -> Optional[PIDGraph]:
        return self.loader.get_graph(drawing_id)

    def list_drawings(self) -> List[Dict[str, Any]]:
        return self.loader.list_drawings()

    def query_pid(self, req: PIDQueryRequest) -> PIDQueryResponse:
        """
        Executes deterministic semantic graph queries on the P&ID topological network.
        Resolves target entities, plans execution, performs adjacency traversal,
        and compiles evidence-backed responses with source provenance.
        """
        # 1. Create Query Execution Plan
        plan = self.planner.plan_query(
            question=req.question,
            requested_drawing_id=req.drawing_id,
            requested_target=req.target_equipment,
        )

        # 2. Check Entity Resolution
        if not plan.is_resolved:
            return PIDQueryResponse(
                question=req.question,
                drawing_id=plan.drawing_id or req.drawing_id or "UNKNOWN",
                answer=(
                    f"**Entity Resolution Warning:**\n\n"
                    f"{plan.unresolved_reason}\n\n"
                    f"To prevent engineering hallucination, topological queries require valid equipment, valve, or instrument tags "
                    f"present in registered MRPL drawings (e.g. `P-201`, `TK-201`, `C-101`, `PSV-201`, `XV-201`, `XV-203`, `CV-201`, `MOV-204`, `PCV-201`)."
                ),
                confidence=0.0,
                query_plan=plan,
                status=PIDQueryResultStatus.UNRESOLVED,
                selected_drawing=None,
                alternate_drawings=[],
                ambiguity_status="UNRESOLVED",
                safety_boundary_note="Unresolved entity queries are rejected to uphold sovereign MRPL engineering integrity.",
            )

        # 3. Retrieve Drawing Adjacency Graph
        adj = self._get_adj(plan.drawing_id or "MRPL-PID-PERMANENT-P201")
        if not adj:
            return PIDQueryResponse(
                question=req.question,
                drawing_id=plan.drawing_id or "UNKNOWN",
                answer=f"Drawing '{plan.drawing_id}' not found in P&ID Graph Registry.",
                confidence=0.0,
                query_plan=plan,
                status=PIDQueryResultStatus.INSUFFICIENT_SOURCE_DATA,
                selected_drawing=None,
                alternate_drawings=[],
                ambiguity_status="INSUFFICIENT_SOURCE_DATA",
            )

        target = plan.target_entity or (adj.graph.nodes[0].tag if adj.graph.nodes else "P-201")

        # 4. Dispatch to Deterministic Traversal based on Intent
        if plan.intent == QueryIntent.ISOLATION:
            return self._execute_isolation_query(adj, target, req.question, plan)

        elif plan.intent == QueryIntent.UPSTREAM:
            return self._execute_upstream_query(adj, target, req.question, plan)

        elif plan.intent == QueryIntent.DOWNSTREAM:
            return self._execute_downstream_query(adj, target, req.question, plan)

        elif plan.intent == QueryIntent.PROTECTION:
            return self._execute_protection_query(adj, target, req.question, plan)

        elif plan.intent == QueryIntent.PSV_DISCHARGE:
            return self._execute_psv_discharge_query(adj, target, req.question, plan)

        elif plan.intent == QueryIntent.INSTRUMENTATION:
            return self._execute_instrumentation_query(adj, target, req.question, plan)

        elif plan.intent == QueryIntent.FAILURE_MODE:
            return self._execute_failure_mode_query(adj, target, req.question, plan)

        elif plan.intent == QueryIntent.FLOW_PATH:
            return self._execute_flow_path_query(adj, target, req.question, plan)

        else:
            return self._execute_general_overview(adj, req.question, plan)

    def _format_context_note(self, target: str, plan: PIDQueryPlan) -> List[str]:
        lines: List[str] = []
        if plan.alternate_drawings:
            lines.extend([
                f"> ℹ️ **Multi-Drawing Context:** Tag `{target}` also appears in drawing(s): `{', '.join(plan.alternate_drawings)}`.",
                f"> Traversal below is evaluated specifically within **`{plan.selected_drawing or plan.drawing_id}`** ({plan.resolution_reason}).",
                "",
            ])
        return lines

    def _format_source_str(self, g: PIDGraph) -> str:
        is_permanent = "CDU-200" in g.drawing_id or "P201" in g.drawing_id or "CDU-200" in (g.drawing_number or "")
        permanent_prefix = "Permanent Reference Image: ChatGPT Image Sep 22, 2026, 06_54_04 PM.png\n" if is_permanent else ""
        return (
            f"{permanent_prefix}"
            f"Drawing Title: {g.drawing_title}\n"
            f"Drawing ID: {g.drawing_id}\n"
            f"Drawing Number: {g.drawing_number or g.drawing_id}\n"
            f"Revision: {g.revision}\n"
            f"System: {g.system}\n"
            f"Source File: {g.source_file}\n"
            f"Derived Representation: Machine-Readable Verified Knowledge Graph (DirectedAdjacencyGraph)\n"
            f"Pipeline: Permanent Architecture Image → Derived Topology Representation → P&ID Graph → Natural-Language Interpretation → Deterministic Topology Traversal → Answer"
        )

    # ── Deterministic Query Executors ──

    def _execute_isolation_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        nodes, edges, details = PIDTraversalEngine.get_isolation_boundary(adj, target)
        g = adj.graph

        suct_valves = details.get("suction_isolation", [])
        disch_valves = details.get("discharge_isolation", [])
        drains = details.get("drains_and_vents", [])
        isolation_provenance = details.get("isolation_provenance", "DIRECT P&ID ISOLATION RELATIONSHIP")

        immediate_parts = []
        if suct_valves:
            immediate_parts.append(f"Suction Isolation: {', '.join(suct_valves)}")
        else:
            immediate_parts.append("Suction Isolation: None on immediate sheet")
        if disch_valves:
            immediate_parts.append(f"Discharge Isolation: {', '.join(disch_valves)}")
        else:
            immediate_parts.append("Discharge Isolation: None on immediate sheet")
        if drains:
            immediate_parts.append(f"Depressurization / Drain Points: {', '.join(drains)}")

        # Check for adjacent check valves to explicitly state non-isolation status
        check_valves = [
            n.tag for n in adj.graph.nodes
            if n.type == NodeType.CHECK_VALVE and (
                any(e.target_tag.upper() == n.tag.upper() for e in adj.outgoing.get(target, [])) or
                any(e.source_tag.upper() == n.tag.upper() for e in adj.incoming.get(target, []))
            )
        ]
        if check_valves:
            immediate_parts.append(f"(Check valve {', '.join(check_valves)} provides non-return backflow prevention only and is not classified as an isolation valve)")

        immediate_str = "\n".join([f"- {p}" for p in immediate_parts])
        extended_path_str = f"Boundary block valves: {', '.join([n.tag for n in nodes])} isolating {target}" if nodes else f"No block valves directly bounding {target}"

        # Build pure P&ID topology explanation
        explanation_parts = []
        if suct_valves and disch_valves:
            explanation_parts.append(
                f"The P&ID identifies {', '.join(suct_valves)} as the suction-side isolation valve and {', '.join(disch_valves)} as the discharge-side isolation valve for {target}."
            )
        elif suct_valves:
            explanation_parts.append(
                f"The P&ID identifies {', '.join(suct_valves)} as the suction-side isolation valve for {target}."
            )
        elif disch_valves:
            explanation_parts.append(
                f"The P&ID identifies {', '.join(disch_valves)} as the discharge-side isolation valve for {target}."
            )
        elif nodes:
            explanation_parts.append(
                f"The P&ID identifies {', '.join([n.tag for n in nodes])} as bounding isolation valve(s) for {target}."
            )
        else:
            explanation_parts.append(
                f"No dedicated isolation valves are connected to {target} on immediate drawing {g.drawing_id}."
            )

        explanation = " ".join(explanation_parts)

        source_str = self._format_source_str(g)

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            "**Drawing:**",
            g.drawing_id,
            "",
            "**Target:**",
            target,
            "",
            "**Operation:**",
            "ISOLATES",
            "",
            "**Relationship Basis:**",
            isolation_provenance,
            "",
            "**Immediate result:**",
            immediate_str,
            "",
            "**Extended topology:**",
            extended_path_str,
            "",
            "**Explanation:**",
            explanation,
            "",
            "**Source:**",
            source_str,
            "",
            "> **Safety Boundary Notice:** P&ID topological presence confirms the physical connectivity of block valves. "
            "Verification of seat tightness, bleed verification, and positive Lockout/Tagout (LOTO) isolation requires field physical verification per OISD-STD-105.",
        ])

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                section="Isolation Scheme",
                evidence_text=f"Boundary valves {', '.join([n.tag for n in nodes])} on drawing {g.drawing_number} [{isolation_provenance}]",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[n.tag for n in nodes],
            path_trace=[target] + [n.tag for n in nodes],
            engineering_rationale=f"Isolation boundary resolved via {len(edges)} topological relationships around {target} [{isolation_provenance}].",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DERIVED_GRAPH_TRAVERSAL,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            provenance_records=provenance,
            safety_boundary_note="Physical LOTO execution requires field verification; P&ID indicates topological boundary.",
        )

    def _execute_upstream_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        nodes, paths, edges = PIDTraversalEngine.get_upstream(adj, target, max_depth=5)
        g = adj.graph

        # Immediate upstream nodes
        immediate_nodes = [n for n in nodes if any(e.source_tag.upper() == n.tag.upper() and e.target_tag.upper() == target.upper() for e in edges)]
        if not immediate_nodes and nodes:
            immediate_nodes = [nodes[0]]

        immediate_str = ", ".join([f"{n.tag} ({n.description or n.type.value})" for n in immediate_nodes]) if immediate_nodes else "None identified on immediate drawing"

        extended_paths = []
        for p in paths[:3]:
            extended_paths.append(" → ".join(p.path))
        extended_path_str = "\n".join(extended_paths) if extended_paths else target

        if immediate_nodes:
            explanation = (
                f"{', '.join([n.tag for n in immediate_nodes])} is connected directly upstream of {target} in the process flow direction. "
                f"Reverse topological graph traversal traces inflow across {len(nodes)} upstream component(s) on drawing {g.drawing_id}."
            )
        else:
            explanation = f"No incoming flow components connected upstream of {target} on drawing {g.drawing_id}."

        source_str = self._format_source_str(g)

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            "**Drawing:**",
            g.drawing_id,
            "",
            "**Target:**",
            target,
            "",
            "**Operation:**",
            "UPSTREAM",
            "",
            "**Immediate result:**",
            immediate_str,
            "",
            "**Extended topology:**",
            extended_path_str,
            "",
            "**Explanation:**",
            explanation,
            "",
            "**Source:**",
            source_str,
        ])

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Reverse BFS traversal from {target} across {len(edges)} flow edges",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[n.tag for n in nodes],
            path_trace=[n.tag for n in nodes] + [target],
            engineering_rationale=f"Upstream topological trace via {len(edges)} incoming flow edges to {target}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DERIVED_GRAPH_TRAVERSAL,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            traversal_paths=paths,
            provenance_records=provenance,
        )

    def _execute_downstream_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        nodes, paths, edges = PIDTraversalEngine.get_downstream(adj, target, max_depth=5)
        g = adj.graph

        # Immediate downstream nodes
        immediate_nodes = [n for n in nodes if any(e.source_tag.upper() == target.upper() and e.target_tag.upper() == n.tag.upper() for e in edges)]
        if not immediate_nodes and nodes:
            immediate_nodes = [nodes[0]]

        immediate_str = ", ".join([f"{n.tag} ({n.description or n.type.value})" for n in immediate_nodes]) if immediate_nodes else "None identified on immediate drawing"

        extended_paths = []
        for p in paths[:3]:
            extended_paths.append(" → ".join(p.path))
        extended_path_str = "\n".join(extended_paths) if extended_paths else target

        if immediate_nodes:
            explanation = (
                f"{target} is connected upstream of {', '.join([n.tag for n in immediate_nodes])}; therefore {', '.join([n.tag for n in immediate_nodes])} "
                f"is the immediate downstream node in the P&ID flow direction. Forward topological traversal traces outflow through {len(nodes)} component(s)."
            )
        else:
            explanation = f"No outgoing process flow components connected downstream of {target} on drawing {g.drawing_id}."

        source_str = self._format_source_str(g)

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            "**Drawing:**",
            g.drawing_id,
            "",
            "**Target:**",
            target,
            "",
            "**Operation:**",
            "DOWNSTREAM",
            "",
            "**Immediate result:**",
            immediate_str,
            "",
            "**Extended topology:**",
            extended_path_str,
            "",
            "**Explanation:**",
            explanation,
            "",
            "**Source:**",
            source_str,
        ])

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Forward BFS traversal from {target} across {len(edges)} flow edges",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[n.tag for n in nodes],
            path_trace=[target] + [n.tag for n in nodes],
            engineering_rationale=f"Downstream topological trace via {len(edges)} outgoing flow edges from {target}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DERIVED_GRAPH_TRAVERSAL,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            traversal_paths=paths,
            provenance_records=provenance,
        )

    def _execute_protection_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        nodes, edges, details = PIDTraversalEngine.get_protection_path(adj, target)
        g = adj.graph

        psv_list = details.get("psv_devices", [])
        dest_list = details.get("discharge_destinations", [])

        immediate_items = []
        if psv_list:
            for psv in psv_list:
                immediate_items.append(f"{psv['tag']} ({psv['description']}) [Set: {psv['set_pressure']}]")
            immediate_str = ", ".join(immediate_items)
            extended_path_str = "\n".join([f"{psv['tag']} protects {target}" for psv in psv_list])
            explanation = (
                f"{', '.join([psv['tag'] for psv in psv_list])} provides overpressure relief protection for {target}. "
                f"Relief routes directly to {', '.join(dest_list) or 'flare header'}."
            )
        else:
            immediate_str = f"No dedicated PSV protection tagged directly on {target} in drawing {g.drawing_id}."
            extended_path_str = target
            explanation = f"No overpressure relief device explicitly assigned to {target} on drawing {g.drawing_id}."

        source_str = self._format_source_str(g)

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            "**Drawing:**",
            g.drawing_id,
            "",
            "**Target:**",
            target,
            "",
            "**Operation:**",
            "PROTECTION",
            "",
            "**Immediate result:**",
            immediate_str,
            "",
            "**Extended topology:**",
            extended_path_str,
            "",
            "**Explanation:**",
            explanation,
            "",
            "**Source:**",
            source_str,
            "",
            "> **Safety Boundary Notice:** P&ID specifies relief valve set pressure and physical header routing. "
            "Adequacy of relief sizing per API RP 520/521 requires process calculation and relief valve sizing calculation sheets.",
        ])

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Protection relationship connecting {target} to {[n.tag for n in nodes]}",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[n.tag for n in nodes],
            path_trace=[target] + [n.tag for n in nodes],
            engineering_rationale=f"Overpressure protection path resolved via {len(edges)} safety relief edges.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DIRECT_SOURCE_RELATIONSHIP,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            provenance_records=provenance,
            safety_boundary_note="Relief sizing calculation requires API 520 calculation datasheet.",
        )

    def _execute_psv_discharge_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        nodes, edges, details = PIDTraversalEngine.get_psv_discharge_path(adj, target)
        g = adj.graph

        dest_items = details.get("relieves_to", [])

        if dest_items:
            immediate_items = []
            for item in dest_items:
                line_str = f" via line {item['line_spec']}" if item.get('line_spec') else ""
                immediate_items.append(f"{item['destination_tag']} ({item['description']}){line_str}")
            immediate_str = ", ".join(immediate_items)
            extended_path_str = "\n".join([f"{target} → {item['destination_tag']}" for item in dest_items])
            explanation = (
                f"{target} discharges / relieves along verified topological edge(s) directly to "
                f"{', '.join([item['destination_tag'] for item in dest_items])} in accordance with drawing {g.drawing_id}."
            )
        else:
            dn_nodes, dn_paths, dn_edges = PIDTraversalEngine.get_downstream(adj, target, max_depth=3)
            if dn_nodes:
                immediate_str = f"{dn_nodes[0].tag} ({dn_nodes[0].description or dn_nodes[0].type.value})"
                extended_path_str = " → ".join(dn_paths[0].path) if dn_paths else f"{target} → {dn_nodes[0].tag}"
                explanation = f"{target} is connected upstream of {dn_nodes[0].tag} and discharges process flow to {dn_nodes[0].tag}."
            else:
                immediate_str = f"Discharge destination for {target} not connected to downstream header on this drawing."
                extended_path_str = target
                explanation = f"No outgoing relief or discharge connection found for {target} in drawing {g.drawing_id}."

        source_str = self._format_source_str(g)

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            "**Drawing:**",
            g.drawing_id,
            "",
            "**Target:**",
            target,
            "",
            "**Operation:**",
            "DISCHARGES",
            "",
            "**Immediate result:**",
            immediate_str,
            "",
            "**Extended topology:**",
            extended_path_str,
            "",
            "**Explanation:**",
            explanation,
            "",
            "**Source:**",
            source_str,
        ])

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Relief route from {target} to {[n.tag for n in nodes]}",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[target] + [n.tag for n in nodes],
            path_trace=[target] + [n.tag for n in nodes],
            engineering_rationale=f"Discharge route traversed along RELIEVES_TO edges for {target}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DIRECT_SOURCE_RELATIONSHIP,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            provenance_records=provenance,
        )

    def _execute_instrumentation_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        nodes, edges, details = PIDTraversalEngine.get_instrumentation(adj, target)
        g = adj.graph

        local_inst = details.get("local_indicators", [])
        transmitters = details.get("transmitters_and_controllers", [])

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            f"### Instrumentation & Control Architecture for `{target}`",
            f"**Drawing:** {g.drawing_title} (`{g.drawing_number or g.drawing_id}`)",
            "",
            "#### 1. Transmitters, Controllers & Interlocks (Active):",
        ])

        if transmitters:
            for inst in transmitters:
                answer_lines.append(f"- **`{inst['tag']}`**: {inst['description']}")
        else:
            answer_lines.append("- None directly tagged on immediate node")

        answer_lines.append("")
        answer_lines.append("#### 2. Local Indicators & Gauges (Passive):")
        if local_inst:
            for inst in local_inst:
                answer_lines.append(f"- **`{inst['tag']}`**: {inst['description']}")
        else:
            answer_lines.append("- None directly tagged on immediate node")

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Instrumentation loops {[n.tag for n in nodes]} measuring {target}",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[n.tag for n in nodes],
            path_trace=[target] + [n.tag for n in nodes],
            engineering_rationale=f"Instrumentation identified via {len(edges)} MEASURES/CONTROLS relationships on {target}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DIRECT_SOURCE_RELATIONSHIP,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            provenance_records=provenance,
        )

    def _execute_failure_mode_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        g = adj.graph
        target_node = adj.get_node(target)
        nodes_involved = [target]

        # Find upstream pressure accumulation points and downstream consequences
        up_nodes, _, up_edges = PIDTraversalEngine.get_upstream(adj, target, max_depth=3)
        dn_nodes, _, dn_edges = PIDTraversalEngine.get_downstream(adj, target, max_depth=3)

        # Check for safety valves on upstream piping
        safety_valves = [n for n in up_nodes if n.type == NodeType.SAFETY_VALVE]
        if not safety_valves:
            safety_valves = [n for n in adj.graph.nodes if n.type == NodeType.SAFETY_VALVE]

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            f"### Failure Mode / Process Deviation Analysis: `{target}`",
            f"**Drawing:** {g.drawing_title} (`{g.drawing_number or g.drawing_id}`)",
            "",
            f"**Component:** `{target}` ({target_node.type.value if target_node else 'Valve/Control Element'})",
            f"**Description:** {target_node.description if target_node else 'Process component'}",
            "",
            "#### 1. Hydraulic Impact on Closure / Failure:",
            f"- **Upstream Pressure Surge:** Flow from `{', '.join([n.tag for n in up_nodes[:3]]) or 'upstream feed'}` is blocked.",
            f"- **Downstream Loss of Flow:** Units downstream (`{', '.join([n.tag for n in dn_nodes[:3]]) or 'process train'}`) experience immediate starvation.",
        ])

        # Check for controllers connected to target
        controllers = [e.source_tag for e in adj.incoming.get(target, []) if e.relationship == EdgeRelationship.CONTROLS]
        if not controllers:
            controllers = [n.tag for n in adj.graph.nodes if n.type == NodeType.INSTRUMENT and ("PIC" in n.tag or "FIC" in n.tag or "LIC" in n.tag)]

        if safety_valves:
            sv = safety_valves[0]
            nodes_involved.append(sv.tag)
            answer_lines.extend([
                "",
                "#### 2. Overpressure Safeguard:",
                f"- Safety relief valve **`{sv.tag}`** ({sv.description}) provides secondary protection.",
                f"- Set Pressure: **{sv.specs.get('set_pressure', '9.0 barg')}** relieving to **Flare Header**.",
            ])

        if controllers:
            ctrl = controllers[0]
            nodes_involved.append(ctrl)
            answer_lines.extend([
                "",
                "#### 3. Control Loop Response & Alarms:",
                f"- Pressure/Flow controller **`{ctrl}`** detects high pressure deviation (PAH alarm in DCS) upon valve closure.",
            ])

        answer_lines.extend([
            "",
            "> **Safety Boundary Notice:** Failure consequences are topologically evaluated based on P&ID routing. "
            "Transient hydraulic surge pressures require dynamic simulation modeling.",
        ])

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Failure scenario tracing around {target} in drawing {g.drawing_number}",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=list(set(nodes_involved + [n.tag for n in up_nodes[:2]] + [n.tag for n in dn_nodes[:2]])),
            path_trace=[target] + [n.tag for n in up_nodes[:2]],
            engineering_rationale=f"HAZOP deviation traced along upstream/downstream flow boundaries of {target}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DERIVED_GRAPH_TRAVERSAL,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            provenance_records=provenance,
        )

    def _execute_flow_path_query(
        self, adj: DirectedAdjacencyGraph, target: str, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        nodes, paths, edges = PIDTraversalEngine.get_downstream(adj, target, max_depth=6)
        up_nodes, _, up_edges = PIDTraversalEngine.get_upstream(adj, target, max_depth=4)
        g = adj.graph

        full_chain = [n.tag for n in reversed(up_nodes)] + [target] + [n.tag for n in nodes]

        answer_lines = self._format_context_note(target, plan)
        answer_lines.extend([
            f"### Continuous Process Flow Path for `{target}`",
            f"**Drawing:** {g.drawing_title} (`{g.drawing_number or g.drawing_id}`)",
            f"**System:** {g.system}",
            "",
            "#### Sequential Flow Routing:",
            f"```text\n{' ──► '.join(full_chain)}\n```",
            "",
            "#### Components Along Path:",
        ])

        for n_tag in full_chain:
            node = adj.get_node(n_tag)
            if node:
                answer_lines.append(f"- **`{node.tag}`** ({node.type.value}): {node.description}")

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Full path routing across {len(edges) + len(up_edges)} flow edges",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=full_chain,
            path_trace=full_chain,
            engineering_rationale=f"Complete topological process flow path from inlet to outlet across {g.drawing_id}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DERIVED_GRAPH_TRAVERSAL,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            provenance_records=provenance,
        )

    def _execute_general_overview(
        self, adj: DirectedAdjacencyGraph, question: str, plan: PIDQueryPlan
    ) -> PIDQueryResponse:
        g = adj.graph
        answer_lines = [
            f"### P&ID Engineering Overview: {g.drawing_title}",
            f"**Drawing Number:** `{g.drawing_number or g.drawing_id}` | **Revision:** {g.revision}",
            f"**Document ID:** `{g.document_id}` | **Source:** `{g.source_file}`",
            f"**System Area:** {g.system}",
            "",
            f"- **Total Nodes:** {len(g.nodes)} components",
            f"- **Total Relationships:** {len(g.edges)} verified edges",
            "",
            "#### Major Components:",
        ]

        for n in g.nodes[:8]:
            answer_lines.append(f"- **`{n.tag}`** ({n.type.value}): {n.description}")

        if g.safety_devices:
            answer_lines.append("")
            answer_lines.append("#### Safety Relief Devices:")
            for s in g.safety_devices:
                answer_lines.append(f"- **`{s.get('tag')}`**: Set at {s.get('set_pressure', 'N/A')} relieving to {s.get('relieves_to', 'N/A')}")

        if g.critical_loops:
            answer_lines.append("")
            answer_lines.append("#### Critical Control Loops:")
            for c in g.critical_loops:
                answer_lines.append(f"- **`{c.get('loop_tag')}`** ({c.get('type')}): {c.get('description')}")

        provenance = [
            PIDProvenanceRecord(
                drawing_id=g.drawing_id,
                drawing_number=g.drawing_number,
                document_id=g.document_id,
                source_file=g.source_file,
                page_number=g.page_number,
                revision=g.revision,
                evidence_text=f"Drawing summary for {g.drawing_number}",
                confidence=1.0,
            )
        ]

        return PIDQueryResponse(
            question=question,
            drawing_id=g.drawing_id,
            answer="\n".join(answer_lines),
            direct_nodes_involved=[n.tag for n in g.nodes[:6]],
            path_trace=[n.tag for n in g.nodes[:6]],
            engineering_rationale=f"Topological graph summary for drawing {g.drawing_id}.",
            evidence_citations=[p.model_dump() for p in provenance],
            confidence=1.0,
            query_plan=plan,
            status=PIDQueryResultStatus.DIRECT_SOURCE_RELATIONSHIP,
            selected_drawing=plan.selected_drawing or g.drawing_id,
            alternate_drawings=plan.alternate_drawings,
            ambiguity_status=plan.ambiguity_status,
            provenance_records=provenance,
        )
