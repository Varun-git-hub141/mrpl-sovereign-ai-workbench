import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import deque
from backend.models.pid_graph_models import (
    PIDGraph,
    PIDNode,
    PIDEdge,
    NodeType,
    EdgeRelationship,
    PIDTraversalPath,
    PIDProvenanceRecord,
)

logger = logging.getLogger("mrpl.pid_traversal")


class DirectedAdjacencyGraph:
    """
    Indexed Directed Adjacency Graph for a P&ID.
    Maintains fast forward and backward edge maps, node registries, and path tracing.
    """

    def __init__(self, graph: PIDGraph):
        self.graph = graph
        self.nodes_by_tag: Dict[str, PIDNode] = {n.tag.upper(): n for n in graph.nodes}
        self.outgoing: Dict[str, List[PIDEdge]] = {}
        self.incoming: Dict[str, List[PIDEdge]] = {}
        self._build_indexes()

    def _build_indexes(self):
        for n in self.graph.nodes:
            tag_u = n.tag.upper()
            self.outgoing[tag_u] = []
            self.incoming[tag_u] = []

        for e in self.graph.edges:
            s_u = e.source_tag.upper()
            t_u = e.target_tag.upper()
            if s_u not in self.outgoing:
                self.outgoing[s_u] = []
            if t_u not in self.incoming:
                self.incoming[t_u] = []
            self.outgoing[s_u].append(e)
            self.incoming[t_u].append(e)

    def get_node(self, tag: str) -> Optional[PIDNode]:
        return self.nodes_by_tag.get(tag.upper().strip())


class PIDTraversalEngine:
    """
    Deterministic Graph Traversal Engine.
    Executes algorithmic BFS/DFS traversals over P&ID topological relationships.
    """

    FLOW_RELATIONSHIPS = {
        EdgeRelationship.FEEDS,
        EdgeRelationship.DISCHARGES_TO,
        EdgeRelationship.CONNECTED_TO,
        EdgeRelationship.TO,
        EdgeRelationship.FROM,
    }

    ISOLATION_VALVE_TYPES = {
        NodeType.VALVE,
        NodeType.CONTROL_VALVE,
    }

    @classmethod
    def get_upstream(
        cls, adj: DirectedAdjacencyGraph, target_tag: str, max_depth: int = 5
    ) -> Tuple[List[PIDNode], List[PIDTraversalPath], List[PIDEdge]]:
        """
        Executes reverse BFS along incoming flow edges to find all upstream components.
        """
        target_norm = target_tag.upper().strip()
        if target_norm not in adj.nodes_by_tag:
            return [], [], []

        visited: Set[str] = {target_norm}
        queue: deque = deque([(target_norm, [target_norm], [], 0)])
        matched_nodes: List[PIDNode] = []
        paths: List[PIDTraversalPath] = []
        all_edges: List[PIDEdge] = []

        while queue:
            curr_tag, curr_path, curr_edges, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # Look at incoming edges (source -> curr_tag)
            incoming_edges = adj.incoming.get(curr_tag, [])
            for edge in incoming_edges:
                if edge.relationship in cls.FLOW_RELATIONSHIPS:
                    prev_tag = edge.source_tag.upper()
                    if prev_tag not in visited:
                        visited.add(prev_tag)
                        new_path = [prev_tag] + curr_path
                        new_edges = [edge] + curr_edges
                        all_edges.append(edge)

                        prev_node = adj.nodes_by_tag.get(prev_tag)
                        if prev_node:
                            matched_nodes.append(prev_node)

                        paths.append(
                            PIDTraversalPath(
                                source_tag=prev_tag,
                                target_tag=target_norm,
                                path=new_path,
                                edges=new_edges,
                                relationship_chain=[e.relationship.value for e in new_edges],
                                distance=depth + 1,
                            )
                        )
                        queue.append((prev_tag, new_path, new_edges, depth + 1))

        return matched_nodes, paths, all_edges

    @classmethod
    def get_downstream(
        cls, adj: DirectedAdjacencyGraph, target_tag: str, max_depth: int = 5
    ) -> Tuple[List[PIDNode], List[PIDTraversalPath], List[PIDEdge]]:
        """
        Executes forward BFS along outgoing flow edges to find all downstream components.
        """
        target_norm = target_tag.upper().strip()
        if target_norm not in adj.nodes_by_tag:
            return [], [], []

        visited: Set[str] = {target_norm}
        queue: deque = deque([(target_norm, [target_norm], [], 0)])
        matched_nodes: List[PIDNode] = []
        paths: List[PIDTraversalPath] = []
        all_edges: List[PIDEdge] = []

        while queue:
            curr_tag, curr_path, curr_edges, depth = queue.popleft()
            if depth >= max_depth:
                continue

            outgoing_edges = adj.outgoing.get(curr_tag, [])
            for edge in outgoing_edges:
                if edge.relationship in cls.FLOW_RELATIONSHIPS:
                    next_tag = edge.target_tag.upper()
                    if next_tag not in visited:
                        visited.add(next_tag)
                        new_path = curr_path + [next_tag]
                        new_edges = curr_edges + [edge]
                        all_edges.append(edge)

                        next_node = adj.nodes_by_tag.get(next_tag)
                        if next_node:
                            matched_nodes.append(next_node)

                        paths.append(
                            PIDTraversalPath(
                                source_tag=target_norm,
                                target_tag=next_tag,
                                path=new_path,
                                edges=new_edges,
                                relationship_chain=[e.relationship.value for e in new_edges],
                                distance=depth + 1,
                            )
                        )
                        queue.append((next_tag, new_path, new_edges, depth + 1))

        return matched_nodes, paths, all_edges

    @classmethod
    def get_isolation_boundary(
        cls, adj: DirectedAdjacencyGraph, target_tag: str
    ) -> Tuple[List[PIDNode], List[PIDEdge], Dict[str, Any]]:
        """
        Determines the physical isolation boundary for an asset by identifying
        explicit ISOLATES edges as well as the nearest isolating valves on suction/discharge.
        """
        target_norm = target_tag.upper().strip()
        if target_norm not in adj.nodes_by_tag:
            return [], [], {}

        isolation_nodes: List[PIDNode] = []
        isolation_edges: List[PIDEdge] = []
        drain_nodes: List[PIDNode] = []
        details = {
            "suction_isolation": [],
            "discharge_isolation": [],
            "drains_and_vents": [],
            "positive_isolation_notes": [],
        }

        # 1. Check direct ISOLATES edges
        direct_isolates_count = 0
        for edge in adj.graph.edges:
            if edge.relationship == EdgeRelationship.ISOLATES:
                if edge.target_tag.upper() == target_norm:
                    v_node = adj.nodes_by_tag.get(edge.source_tag.upper())
                    if v_node and v_node not in isolation_nodes:
                        isolation_nodes.append(v_node)
                        isolation_edges.append(edge)
                        direct_isolates_count += 1
                        if "suction" in (edge.notes or "").lower() or "suction" in v_node.location.lower() or "inlet" in v_node.description.lower():
                            details["suction_isolation"].append(v_node.tag)
                        else:
                            details["discharge_isolation"].append(v_node.tag)

        if direct_isolates_count > 0:
            details["isolation_provenance"] = "DIRECT P&ID ISOLATION RELATIONSHIP"
        else:
            details["isolation_provenance"] = "DERIVED TOPOLOGY INTERPRETATION"

        # 2. If direct ISOLATES edges weren't explicitly tagged, search nearest block valves
        if not isolation_nodes:
            # Search upstream
            up_nodes, _, up_edges = cls.get_upstream(adj, target_norm, max_depth=3)
            for n in up_nodes:
                if n.type in cls.ISOLATION_VALVE_TYPES:
                    isolation_nodes.append(n)
                    details["suction_isolation"].append(n.tag)
                    break

            # Search downstream
            dn_nodes, _, dn_edges = cls.get_downstream(adj, target_norm, max_depth=3)
            for n in dn_nodes:
                if n.type in cls.ISOLATION_VALVE_TYPES and n.type != NodeType.CHECK_VALVE:
                    isolation_nodes.append(n)
                    details["discharge_isolation"].append(n.tag)
                    break

        # 3. Find connected drains / vents on the target equipment
        for edge in adj.outgoing.get(target_norm, []):
            tgt_node = adj.nodes_by_tag.get(edge.target_tag.upper())
            if tgt_node and tgt_node.type == NodeType.DRAIN_VALVE:
                drain_nodes.append(tgt_node)
                isolation_edges.append(edge)
                details["drains_and_vents"].append(tgt_node.tag)

        for d in drain_nodes:
            if d not in isolation_nodes:
                isolation_nodes.append(d)

        return isolation_nodes, isolation_edges, details

    @classmethod
    def get_protection_path(
        cls, adj: DirectedAdjacencyGraph, target_tag: str
    ) -> Tuple[List[PIDNode], List[PIDEdge], Dict[str, Any]]:
        """
        Finds overpressure protection devices (PSVs, SDVs) protecting the target asset.
        """
        target_norm = target_tag.upper().strip()
        protected_by: List[PIDNode] = []
        protection_edges: List[PIDEdge] = []
        details: Dict[str, Any] = {"psv_devices": [], "discharge_destinations": []}

        # 1. Direct PROTECTS edges
        for edge in adj.graph.edges:
            if edge.relationship == EdgeRelationship.PROTECTS and (
                edge.target_tag.upper() == target_norm or target_norm in edge.target_tag.upper()
            ):
                psv_node = adj.nodes_by_tag.get(edge.source_tag.upper())
                if psv_node and psv_node not in protected_by:
                    protected_by.append(psv_node)
                    protection_edges.append(edge)
                    details["psv_devices"].append({
                        "tag": psv_node.tag,
                        "set_pressure": psv_node.specs.get("set_pressure", "Unknown"),
                        "description": psv_node.description,
                    })

        # 2. Check downstream discharge line tap for PSVs
        dn_nodes, _, dn_edges = cls.get_downstream(adj, target_norm, max_depth=2)
        for n in dn_nodes:
            if n.type == NodeType.SAFETY_VALVE and n not in protected_by:
                protected_by.append(n)
                details["psv_devices"].append({
                    "tag": n.tag,
                    "set_pressure": n.specs.get("set_pressure", "Unknown"),
                    "description": n.description,
                })

        # 3. For each found PSV, find its relief destination
        for psv in protected_by:
            for out_edge in adj.outgoing.get(psv.tag.upper(), []):
                if out_edge.relationship == EdgeRelationship.RELIEVES_TO:
                    protection_edges.append(out_edge)
                    hdr_node = adj.nodes_by_tag.get(out_edge.target_tag.upper())
                    if hdr_node:
                        details["discharge_destinations"].append(hdr_node.tag)

        return protected_by, protection_edges, details

    @classmethod
    def get_psv_discharge_path(
        cls, adj: DirectedAdjacencyGraph, psv_tag: str
    ) -> Tuple[List[PIDNode], List[PIDEdge], Dict[str, Any]]:
        """
        Traverses outgoing relief edges from a PSV or discharge edges from any component.
        """
        psv_norm = psv_tag.upper().strip()
        dest_nodes: List[PIDNode] = []
        dest_edges: List[PIDEdge] = []
        details: Dict[str, Any] = {"psv_tag": psv_norm, "relieves_to": []}

        outgoing = adj.outgoing.get(psv_norm, [])
        for edge in outgoing:
            if edge.relationship in [EdgeRelationship.RELIEVES_TO, EdgeRelationship.DISCHARGES_TO, EdgeRelationship.FEEDS, EdgeRelationship.CONNECTED_TO]:
                target_node = adj.nodes_by_tag.get(edge.target_tag.upper())
                if target_node:
                    dest_nodes.append(target_node)
                    dest_edges.append(edge)
                    details["relieves_to"].append({
                        "destination_tag": target_node.tag,
                        "description": target_node.description,
                        "line_spec": edge.line_spec,
                        "relationship": edge.relationship.value,
                    })

        return dest_nodes, dest_edges, details

    @classmethod
    def get_instrumentation(
        cls, adj: DirectedAdjacencyGraph, target_tag: str
    ) -> Tuple[List[PIDNode], List[PIDEdge], Dict[str, Any]]:
        """
        Finds all instruments (PI, PT, TI, TE, PDI, FIC, PIC, LIC) measuring or controlling the asset.
        """
        target_norm = target_tag.upper().strip()
        instruments: List[PIDNode] = []
        inst_edges: List[PIDEdge] = []
        details: Dict[str, Any] = {"local_indicators": [], "transmitters_and_controllers": []}

        # 1. Direct MEASURES / CONTROLS edges on target
        for edge in adj.graph.edges:
            if edge.relationship in [EdgeRelationship.MEASURES, EdgeRelationship.CONTROLS]:
                if edge.target_tag.upper() == target_norm or edge.source_tag.upper() == target_norm:
                    inst_tag = edge.target_tag.upper() if edge.source_tag.upper() == target_norm else edge.source_tag.upper()
                    node = adj.nodes_by_tag.get(inst_tag)
                    if node and node.type == NodeType.INSTRUMENT and node not in instruments:
                        instruments.append(node)
                        inst_edges.append(edge)

        # 2. Instruments on immediate suction and discharge line segments (1-hop upstream/downstream)
        immediate_nodes = set()
        for e in adj.incoming.get(target_norm, []):
            immediate_nodes.add(e.source_tag.upper())
        for e in adj.outgoing.get(target_norm, []):
            immediate_nodes.add(e.target_tag.upper())

        for neighbor in immediate_nodes:
            for e in adj.outgoing.get(neighbor, []) + adj.incoming.get(neighbor, []):
                if e.relationship == EdgeRelationship.MEASURES:
                    inst_tag = e.target_tag.upper() if e.source_tag.upper() == neighbor else e.source_tag.upper()
                    node = adj.nodes_by_tag.get(inst_tag)
                    if node and node.type == NodeType.INSTRUMENT and node not in instruments:
                        instruments.append(node)
                        inst_edges.append(e)

        # Classify local vs transmitter
        for inst in instruments:
            desc = inst.description.lower()
            tag = inst.tag.upper()
            if any(k in tag for k in ["PT", "TT", "FT", "LT", "PDI", "TE", "PIC", "FIC", "LIC"]):
                details["transmitters_and_controllers"].append({"tag": inst.tag, "description": inst.description})
            else:
                details["local_indicators"].append({"tag": inst.tag, "description": inst.description})

        return instruments, inst_edges, details

    @classmethod
    def get_flow_path(
        cls, adj: DirectedAdjacencyGraph, source_tag: Optional[str] = None, target_tag: Optional[str] = None
    ) -> Tuple[List[PIDNode], List[PIDTraversalPath], List[PIDEdge]]:
        """
        Traces continuous multi-hop flow path between components.
        """
        if not source_tag and not target_tag:
            # Return all forward path edges in drawing
            all_nodes = [n for n in adj.graph.nodes if n.type in [NodeType.PUMP, NodeType.TANK, NodeType.COLUMN, NodeType.VESSEL, NodeType.HEAT_EXCHANGER]]
            return all_nodes, [], adj.graph.edges

        if source_tag and target_tag:
            # Find shortest path from source to target
            s_norm = source_tag.upper().strip()
            t_norm = target_tag.upper().strip()
            queue = deque([(s_norm, [s_norm], [])])
            visited = {s_norm}

            while queue:
                curr, path, edges = queue.popleft()
                if curr == t_norm:
                    matched = [adj.nodes_by_tag[tag] for tag in path if tag in adj.nodes_by_tag]
                    t_path = PIDTraversalPath(
                        source_tag=s_norm,
                        target_tag=t_norm,
                        path=path,
                        edges=edges,
                        relationship_chain=[e.relationship.value for e in edges],
                        distance=len(edges),
                    )
                    return matched, [t_path], edges

                for edge in adj.outgoing.get(curr, []):
                    if edge.relationship in cls.FLOW_RELATIONSHIPS:
                        nxt = edge.target_tag.upper()
                        if nxt not in visited:
                            visited.add(nxt)
                            queue.append((nxt, path + [nxt], edges + [edge]))

            return [], [], []

        if source_tag:
            return cls.get_downstream(adj, source_tag, max_depth=6)
        else:
            return cls.get_upstream(adj, target_tag, max_depth=6)
