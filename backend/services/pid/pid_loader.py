import os
import json
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from backend.models.pid_graph_models import (
    PIDGraph,
    PIDNode,
    PIDEdge,
    NodeType,
    EdgeRelationship,
)

logger = logging.getLogger("mrpl.pid_loader")


class PIDKnowledgeLoader:
    """
    Clean, Sovereign P&ID Loader for the Permanent Reference Architecture.
    Represents the P-201 Crude Feed Pump System (ChatGPT Image Sep 22, 2026, 06_54_04 PM.png)
    as a deterministic, machine-readable topological knowledge graph.
    """

    PERMANENT_DRAWING_ID = "MRPL-PID-PERMANENT-P201"
    PERMANENT_IMAGE_NAME = "ChatGPT Image Sep 22, 2026, 06_54_04 PM.png"

    def __init__(self, kb_dir: Optional[str] = None):
        self.graphs_by_id: Dict[str, PIDGraph] = {}
        self.tag_to_drawings: Dict[str, Set[str]] = {}
        self._load_permanent_architecture()

    def _load_permanent_architecture(self):
        """Constructs the permanent P-201 reference graph with verified topological facts."""
        doc_id = self.PERMANENT_DRAWING_ID
        drawing_num = "MRPL-DWG-PID-P201-REV1"
        source_file = "PID_CDU_200_P201_Crude_Booster_Loop.json"
        revision = "Rev 1 (As-Built Permanent Reference)"
        plant_area = "Crude Distillation Unit (CDU-II)"

        nodes: List[PIDNode] = [
            PIDNode(
                node_id="N-TK201",
                tag="TK-201",
                type=NodeType.TANK,
                description="Atmospheric Storage Tank (Crude Source)",
                location="Tank Farm Area 3",
                specs={"service": "Crude Feed", "header": "12-CDU-SUCT-201"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-XV201",
                tag="XV-201",
                type=NodeType.VALVE,
                description="Suction Header Isolation Valve",
                location="P-201 Suction Header",
                normal_state="NORMALLY_OPEN",
                specs={"type": "Suction Block Valve", "size": "12-inch Gate"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-Y201",
                tag="Y-201",
                type=NodeType.STRAINER,
                description="Suction Basket Strainer (with PG-201)",
                location="P-201 Suction Line",
                specs={"size": "12-inch duplex", "dp_alarm": "0.5 bar"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-PG201",
                tag="PG-201",
                type=NodeType.INSTRUMENT,
                description="Differential Pressure Gauge across Y-201 Strainer",
                location="Across Y-201 Strainer",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-XV203",
                tag="XV-203",
                type=NodeType.VALVE,
                description="Suction Isolation Valve",
                location="P-201 Suction Nozzle",
                normal_state="NORMALLY_OPEN",
                specs={"type": "Suction Block Valve", "size": "12-inch Gate"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-PI201",
                tag="PI-201",
                type=NodeType.INSTRUMENT,
                description="Suction Pressure Indicator (1.8 barg)",
                location="P-201 Suction Flange",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-TI201",
                tag="TI-201",
                type=NodeType.INSTRUMENT,
                description="Pump Casing Temperature Indicator (42°C)",
                location="P-201 Pump Casing",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-DV201",
                tag="DV-201",
                type=NodeType.DRAIN_VALVE,
                description="Suction Low-Point Drain Valve",
                location="P-201 Suction Low Point",
                normal_state="NORMALLY_CLOSED",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-P201",
                tag="P-201",
                type=NodeType.PUMP,
                description="Crude Feed Pump (Centrifugal API 610)",
                location="Pump Bay CDU-II",
                specs={
                    "service": "Crude Feed",
                    "type": "Centrifugal Pump",
                    "normal_suction_pressure": "1.8 barg",
                    "normal_discharge_pressure": "7.2 barg",
                    "flow_rate": "280 m3/hr",
                    "temperature": "42°C",
                    "suction_flange": "12-inch",
                    "discharge_flange": "10-inch",
                },
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-DV202",
                tag="DV-202",
                type=NodeType.DRAIN_VALVE,
                description="Discharge / Casing Drain Valve",
                location="P-201 Casing / Discharge Low Point",
                normal_state="NORMALLY_CLOSED",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-CV201",
                tag="CV-201",
                type=NodeType.CHECK_VALVE,
                description="Check Valve (Prevents Backflow — Non-Return Only)",
                location="P-201 Discharge Spool",
                specs={"size": "10-inch Class 300# CS"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-PI202",
                tag="PI-202",
                type=NodeType.INSTRUMENT,
                description="Discharge Pressure Indicator (7.2 barg)",
                location="P-201 Discharge Spool",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-MOV204",
                tag="MOV-204",
                type=NodeType.VALVE,
                description="Discharge Isolation Valve (Class 300 Gate)",
                location="P-201 Discharge Header",
                normal_state="NORMALLY_OPEN",
                specs={"size": "10-inch Class 300# Motor Operated Gate"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-PSV201",
                tag="PSV-201",
                type=NodeType.SAFETY_VALVE,
                description="Safety Relief Valve (Overpressure Protection)",
                location="P-201 Discharge Header (Relief Line)",
                specs={"set_pressure": "9.0 barg", "relieving_to": "FLARE_HEADER"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-PIC201",
                tag="PIC-201",
                type=NodeType.INSTRUMENT,
                description="Pressure Indicating Controller",
                location="CCR DCS Controller",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-PCV201",
                tag="PCV-201",
                type=NodeType.CONTROL_VALVE,
                description="Pressure Control Valve (Modulates Discharge Pressure)",
                location="CDU Feed Header",
                specs={"controller": "PIC-201"},
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-C101",
                tag="C-101",
                type=NodeType.COLUMN,
                description="CDU Pre-Heat Train & Column C-101 (Downstream Process)",
                location="CDU Process Area",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
            PIDNode(
                node_id="N-FLARE",
                tag="FLARE_HEADER",
                type=NodeType.HEADER,
                description="Refinery Flare Header (9.0 barg Relief Destination)",
                location="Refinery Flare Network",
                document_id=doc_id,
                drawing_number=drawing_num,
                source_file=source_file,
                revision=revision,
            ),
        ]

        edges: List[PIDEdge] = [
            PIDEdge(source_tag="TK-201", target_tag="XV-201", relationship=EdgeRelationship.FEEDS, line_spec="12-CDU-SUCT-201", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="XV-201", target_tag="P-201", relationship=EdgeRelationship.ISOLATES, notes="Suction isolation valve", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="XV-201", target_tag="Y-201", relationship=EdgeRelationship.FEEDS, line_spec="12-CDU-SUCT-201", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="Y-201", target_tag="PG-201", relationship=EdgeRelationship.MEASURES, line_spec="Impulse Line", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="Y-201", target_tag="XV-203", relationship=EdgeRelationship.FEEDS, line_spec="12-CDU-SUCT-201", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="XV-203", target_tag="P-201", relationship=EdgeRelationship.ISOLATES, notes="Suction isolation valve", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="XV-203", target_tag="P-201", relationship=EdgeRelationship.FEEDS, line_spec="12-CDU-SUCT-201", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="P-201", target_tag="PI-201", relationship=EdgeRelationship.MEASURES, notes="Suction pressure 1.8 barg", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="P-201", target_tag="TI-201", relationship=EdgeRelationship.MEASURES, notes="Casing temperature 42°C", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="P-201", target_tag="DV-201", relationship=EdgeRelationship.CONNECTED_TO, notes="Suction drain", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="P-201", target_tag="DV-202", relationship=EdgeRelationship.CONNECTED_TO, notes="Discharge drain", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="P-201", target_tag="CV-201", relationship=EdgeRelationship.FEEDS, line_spec="10-CDU-DISCH-201", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="CV-201", target_tag="PI-202", relationship=EdgeRelationship.MEASURES, notes="Discharge pressure 7.2 barg", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="CV-201", target_tag="MOV-204", relationship=EdgeRelationship.FEEDS, line_spec="10-CDU-DISCH-201", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="MOV-204", target_tag="P-201", relationship=EdgeRelationship.ISOLATES, notes="Discharge isolation valve", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="MOV-204", target_tag="PCV-201", relationship=EdgeRelationship.FEEDS, line_spec="10-CDU-DISCH-201", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="PIC-201", target_tag="PCV-201", relationship=EdgeRelationship.CONTROLS, line_spec="Pressure Controller Signal", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="PCV-201", target_tag="C-101", relationship=EdgeRelationship.FEEDS, line_spec="To CDU Pre-Heat Train & Column C-101", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="CV-201", target_tag="PSV-201", relationship=EdgeRelationship.CONNECTED_TO, line_spec="Relief Line", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="PSV-201", target_tag="P-201", relationship=EdgeRelationship.PROTECTS, notes="Overpressure protection (9.0 barg)", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
            PIDEdge(source_tag="PSV-201", target_tag="FLARE_HEADER", relationship=EdgeRelationship.RELIEVES_TO, line_spec="To Flare Header (9.0 barg)", document_id=doc_id, drawing_number=drawing_num, source_file=source_file),
        ]

        graph = PIDGraph(
            drawing_id=doc_id,
            drawing_title="P-201 Crude Feed Pump System",
            system="Crude Distillation Unit (CDU-II)",
            document_id=doc_id,
            drawing_number=drawing_num,
            revision=revision,
            plant_area=plant_area,
            source_file=source_file,
            page_number=1,
            nodes=nodes,
            edges=edges,
            critical_loops=[
                {"loop_tag": "PIC-201 / PCV-201", "type": "Pressure Control", "description": "Modulates discharge pressure downstream of MOV-204 to Column C-101"}
            ],
            safety_devices=[
                {"tag": "PSV-201", "type": "Safety Relief Valve", "set_pressure": "9.0 barg", "relieves_to": "FLARE_HEADER"}
            ],
            metadata={"reference_image": self.PERMANENT_IMAGE_NAME},
        )

        aliases = [
            doc_id,
            "MRPL-PID-PERMANENT-P201",
            "MRPL-PID-CDU-200",
            "CDU-200",
            "P201",
            "P-201",
            drawing_num,
        ]

        for alias in aliases:
            self.graphs_by_id[alias.upper().strip()] = graph

        for node in nodes:
            tag_u = node.tag.upper().strip()
            if tag_u not in self.tag_to_drawings:
                self.tag_to_drawings[tag_u] = set()
            self.tag_to_drawings[tag_u].add(doc_id)

        logger.info("Loaded permanent architecture %s with %d nodes and %d edges.", doc_id, len(nodes), len(edges))

    def get_graph(self, drawing_id: Optional[str] = None) -> Optional[PIDGraph]:
        if not drawing_id:
            return self.graphs_by_id.get(self.PERMANENT_DRAWING_ID)
        return self.graphs_by_id.get(drawing_id.upper().strip(), self.graphs_by_id.get(self.PERMANENT_DRAWING_ID))

    def list_drawings(self) -> List[Dict[str, Any]]:
        g = self.get_graph()
        if not g:
            return []
        return [{
            "drawing_id": g.drawing_id,
            "drawing_title": g.drawing_title,
            "drawing_number": g.drawing_number,
            "node_count": len(g.nodes),
            "edge_count": len(g.edges),
            "reference_image": self.PERMANENT_IMAGE_NAME,
        }]
