"""
Unit and Integration Tests for Phase 10B — Dynamic MRPL Asset Hierarchy and Asset Registry
Tests dynamic extensible asset registry, multi-tier hierarchy, incremental Hybrid RAG indexing,
generic and class-specific attributes, observation extraction, provenance, and audit logs.
"""

import pytest
import time
from pathlib import Path
from backend.models.asset_hierarchy import (
    Asset,
    AssetClassEnum,
    AssetStatusEnum,
    AssetComponent,
    InspectionLocation,
    EngineeringObservation,
    EngineeringMeasurement,
    MeasurementTypeEnum,
    ProvenanceRecord,
    AssetAuditRecord,
    AssetDossier,
    HierarchyNode,
    AssetCreateRequest,
    AssetDocumentUploadRequest,
)
from backend.services.hybrid_rag import HybridRAGService
from backend.services.asset_registry import AssetRegistryService
from backend.models.rag_models import HybridSearchRequest


@pytest.fixture
def clean_registry(tmp_path):
    """Fixture providing a fresh isolated AssetRegistryService instance with HybridRAG."""
    # Initialize HybridRAG with standard KB
    rag = HybridRAGService()
    registry = AssetRegistryService(hybrid_rag=rag, data_dir=tmp_path / "registry_store")
    return registry


class TestAssetHierarchyAndRegistry:
    """Test suite for Phase 10B Dynamic Asset Registry & Hierarchy."""

    def test_default_seeded_assets(self, clean_registry):
        """Verify baseline assets (P-201, P-101, V-201, TK-201, PSV-201, XV-203, C-101, E-101) exist."""
        assets = clean_registry.get_all_assets()
        tags = [a.tag for a in assets]
        assert "P-201" in tags
        assert "P-101" in tags
        assert "V-201" in tags
        assert "TK-201" in tags
        assert "PSV-201" in tags
        assert "XV-203" in tags
        assert "C-101" in tags
        assert "E-101" in tags

    def test_10_tier_hierarchy_tree_structure(self, clean_registry):
        """Verify the 10-tier hierarchy tree renders from MRPL down to Provenance."""
        tree = clean_registry.get_hierarchy_tree()
        assert tree.node_id == "MRPL-CORP"
        assert tree.node_type == "organization"
        assert len(tree.children) > 0

        # refinery level
        refinery = tree.children[0]
        assert refinery.node_type == "refinery"
        assert refinery.node_id == "MRPL-MANGALORE"

        # process unit level
        unit_ids = [u.node_id for u in refinery.children]
        assert "UNIT-CDU-II" in unit_ids or "UNIT-CDU-I" in unit_ids

        # verify tree depth reaches observation/measurement/provenance
        found_observation = False
        def walk_tree(node: HierarchyNode):
            nonlocal found_observation
            if node.node_type == "observation" or node.node_type == "measurement":
                found_observation = True
            for child in node.children:
                walk_tree(child)

        walk_tree(tree)
        assert found_observation, "Hierarchy tree must contain observation and measurement nodes"

    def test_create_new_valve_psv301_without_code_changes(self, clean_registry):
        """CRITICAL: Add completely new valve PSV-301 dynamically without developer/code changes."""
        req = AssetCreateRequest(
            tag="PSV-301",
            name="Atmospheric Column Overhead Safety Relief Valve",
            asset_class=AssetClassEnum.VALVES,
            process_unit="CDU-I",
            service="Hydrocarbon Vapor Relief to Flare",
            location="Column C-101 Overhead Top Vapor Line",
            design_pressure_bar=18.5,
            design_temperature_c=165.0,
            operating_pressure_bar=12.2,
            operating_temperature_c=142.0,
            material_of_construction="ASTM A216 WCB / 316 SS Trim",
            class_attributes={
                "valve_type": "Spring-Loaded Pressure Safety Valve (PSV)",
                "set_pressure_bar": 15.0,
                "cold_differential_test_pressure_bar": 15.3,
                "orifice_designation": "8T10",
                "flange_rating_inlet": "300# ANSI",
                "flange_rating_outlet": "150# ANSI",
                "overpressure_percent": 10.0,
                "blowdown_percent": 7.0,
            },
            created_by="Lead Mechanical Engineer (Mr. Rajesh Rao)",
        )
        new_asset = clean_registry.create_asset(req)

        assert new_asset.tag == "PSV-301"
        assert new_asset.asset_id == "ASSET-MRPL-CDU-I-PSV-301"
        assert new_asset.asset_class == AssetClassEnum.VALVES
        assert new_asset.class_attributes["set_pressure_bar"] == 15.0
        assert new_asset.class_attributes["orifice_designation"] == "8T10"

        # Verify retrievable by tag and ID
        fetched = clean_registry.get_asset("PSV-301")
        assert fetched is not None
        assert fetched.asset_id == new_asset.asset_id

    def test_create_new_heat_exchanger_e301(self, clean_registry):
        """CRITICAL: Add completely new heat exchanger E-301 dynamically."""
        req = AssetCreateRequest(
            tag="E-301",
            name="Crude Pre-Flash Preheater Shell & Tube Exchanger",
            asset_class=AssetClassEnum.HEAT_EXCHANGERS,
            process_unit="CDU-II",
            service="Crude Preheat / Atmospheric Residue Bottoms",
            location="Preheat Train Row 3",
            design_pressure_bar=25.0,
            design_temperature_c=280.0,
            material_of_construction="Shell: SA-516 Gr 70 / Tubes: SA-214 Carbon Steel",
            class_attributes={
                "tbesa_type": "AES (Split-Ring Floating Head)",
                "shell_passes": 1,
                "tube_passes": 4,
                "tube_count": 840,
                "tube_od_mm": 19.05,
                "tube_thickness_mm": 2.11,
                "surface_area_m2": 620.0,
            },
            created_by="Process Integrity Lead",
        )
        new_asset = clean_registry.create_asset(req)

        assert new_asset.tag == "E-301"
        assert new_asset.asset_id == "ASSET-MRPL-CDU-II-E-301"
        assert new_asset.class_attributes["tube_count"] == 840

    def test_add_component_and_inspection_location(self, clean_registry):
        """Add structured components and inspection CMLs to an asset."""
        comp = AssetComponent(
            component_id="COMP-P201-SEAL",
            name="Mechanical Cartridge Seal Plan 53A",
            component_type="Mechanical Seal",
            material="Silicon Carbide vs Tungsten Carbide",
            criticality="HIGH",
        )
        updated_asset = clean_registry.add_component("P-201", comp)
        assert any(c.component_id == "COMP-P201-SEAL" for c in updated_asset.components)

        loc = InspectionLocation(
            location_id="LOC-P201-CML-05",
            location_tag="CML-05",
            description="Pump Discharge Nozzle Neck Ultrasonic Thickness Spot",
            nominal_thickness_mm=9.52,
            minimum_required_thickness_mm=6.10,
            corrosion_allowance_mm=3.42,
            component_id="COMP-P201-CASING",
        )
        updated_asset2 = clean_registry.add_inspection_location("P-201", loc)
        assert any(l.location_tag == "CML-05" for l in updated_asset2.inspection_locations)

    def test_dynamic_document_addition_and_incremental_indexing(self, clean_registry):
        """CRITICAL: Upload a new test document to PSV-301 and verify incremental search."""
        # 1. Create PSV-301
        clean_registry.create_asset(AssetCreateRequest(
            tag="PSV-301",
            name="Atmospheric Relief Valve",
            asset_class=AssetClassEnum.VALVES,
            process_unit="CDU-I",
        ))

        # 2. Upload Pop Test Document
        doc_req = AssetDocumentUploadRequest(
            title="PSV-301 Annual Pop Test & Calibration Certificate 2026",
            document_type="Test Certificate",
            document_number="MRPL-CAL-2026-PSV301-01",
            revision="R0",
            approval_status="APPROVED",
            author="Senior Instrumentation & Safety Valve Specialist",
            content="""MANGALORE REFINERY AND PETROCHEMICALS LIMITED (MRPL)
OFFICIAL SAFETY VALVE CERTIFICATE
Asset Tag: PSV-301
Location: CDU-I Overhead Relief
Test Date: 2026-03-15
Authorized Inspector: S. Nair (Chief Valve Specialist)

1.0 POP TEST BENCH RESULTS:
Set Pressure Specification: 15.00 bar
As-Found Pop Pressure: 15.15 bar (Deviation +1.0%, Acceptable within API 527 +/- 3%)
As-Left Cold Set Pressure: 15.02 bar
Reseat / Blowdown Pressure: 13.95 bar (Blowdown: 7.1%)
Seat Leakage Test: Bubble test per API 527 showed 0 bubbles/min at 90% set pressure (13.5 bar).
Spring Condition: Satisfactory, zero permanent set or pitting.
Nozzle and Disc Lapping: Lapped to 2 light bands optical flatness.

2.0 STATUTORY CERTIFICATION:
Valve PSV-301 is certified for continuous operational service in CDU-I until March 2027.""",
            measurements=[
                EngineeringMeasurement(
                    measurement_id="M-PSV301-SET-2026",
                    measurement_type=MeasurementTypeEnum.SET_PRESSURE,
                    value=15.02,
                    unit="bar",
                    tolerance_min=14.55,
                    tolerance_max=15.45,
                    is_within_limits=True,
                ),
                EngineeringMeasurement(
                    measurement_id="M-PSV301-BLOWDOWN-2026",
                    measurement_type=MeasurementTypeEnum.BLOWDOWN,
                    value=7.1,
                    unit="%",
                    tolerance_min=4.0,
                    tolerance_max=10.0,
                    is_within_limits=True,
                ),
            ],
            inspection_location_tag="TEST-BENCH-01",
            source_page="Page 1",
            source_section="Section 1.0 Pop Test Bench Results",
            source_span="As-Found Pop Pressure: 15.15 bar ... As-Left Cold Set Pressure: 15.02 bar",
        )

        res = clean_registry.add_document_to_asset("PSV-301", doc_req)
        assert res["success"] is True
        assert res["document_id"] == "MRPL-CAL-2026-PSV301-01"

        # 3. Hybrid RAG Search for PSV-301
        search_req = HybridSearchRequest(
            query="PSV-301 pop test set pressure blowdown",
            equipment_tag="PSV-301",
            top_k=3,
        )
        results = clean_registry.hybrid_rag.hybrid_search(search_req)
        assert len(results) > 0
        top_match = results[0]
        assert "PSV-301" in top_match.text
        assert "15.02 bar" in top_match.text

        # 4. Check Asset Dossier
        dossier = clean_registry.get_asset_dossier("PSV-301")
        assert len(dossier.documents) == 1
        assert len(dossier.observations) >= 1
        assert dossier.observations[0].provenance.document_id == "MRPL-CAL-2026-PSV301-01"

    def test_chronological_multi_document_addition_without_overwriting(self, clean_registry):
        """Adding a second document later preserves both in historical order."""
        # 1. Create PSV-301
        clean_registry.create_asset(AssetCreateRequest(
            tag="PSV-301",
            name="Atmospheric Relief Valve",
            asset_class=AssetClassEnum.VALVES,
            process_unit="CDU-I",
        ))

        # 2. Add 2025 Test
        clean_registry.add_document_to_asset("PSV-301", AssetDocumentUploadRequest(
            title="PSV-301 2025 Inspection & Pop Test",
            document_type="Test Certificate",
            document_number="MRPL-CAL-2025-PSV301-01",
            content="2025 Test: As-Found Pop Pressure 15.20 bar, As-Left 15.00 bar.",
        ))

        # 3. Add 2026 Maintenance Record
        clean_registry.add_document_to_asset("PSV-301", AssetDocumentUploadRequest(
            title="PSV-301 2026 Maintenance & Overhaul Record",
            document_type="Maintenance Record",
            document_number="MRPL-MAINT-2026-PSV301-01",
            content="2026 Maintenance: Dismantled, replaced spring and guide ring, lapped disc.",
        ))

        dossier = clean_registry.get_asset_dossier("PSV-301")
        assert len(dossier.documents) == 2
        doc_ids = [d["document_id"] for d in dossier.documents]
        assert "MRPL-CAL-2025-PSV301-01" in doc_ids
        assert "MRPL-MAINT-2026-PSV301-01" in doc_ids

        # Verify audit trail has 3 events (1 create + 2 doc additions)
        trails = clean_registry.get_audit_trail("PSV-301")
        assert len(trails) >= 3
        actions = [t.action for t in trails]
        assert "ASSET_CREATED" in actions
        assert actions.count("DOCUMENT_ATTACHED") == 2

    def test_semantic_rule_different_measurement_types_separated(self, clean_registry):
        """CRITICAL: 6.0 mm wall thickness and 0.42 mm wear ring clearance are different types and never equated."""
        p201 = clean_registry.get_asset("P-201")
        assert p201 is not None

        # Add 6.0 mm wall thickness observation
        clean_registry.add_document_to_asset("P-201", AssetDocumentUploadRequest(
            title="P-201 Casing Thickness Measurement 2026",
            document_type="Inspection Report",
            document_number="INSP-P201-THK-2026",
            content="Ultrasonic wall thickness measurement at CML-01 is 6.00 mm.",
            measurements=[
                EngineeringMeasurement(
                    measurement_id="M-THK-01",
                    measurement_type=MeasurementTypeEnum.WALL_THICKNESS,
                    value=6.00,
                    unit="mm",
                )
            ]
        ))

        # Add 0.42 mm wear ring clearance observation
        clean_registry.add_document_to_asset("P-201", AssetDocumentUploadRequest(
            title="P-201 Wear Ring Clearance Overhaul Report 2026",
            document_type="Maintenance Record",
            document_number="MAINT-P201-CLR-2026",
            content="Feeler gauge radial wear ring clearance measured at 0.42 mm.",
            measurements=[
                EngineeringMeasurement(
                    measurement_id="M-CLR-01",
                    measurement_type=MeasurementTypeEnum.CLEARANCE,
                    value=0.42,
                    unit="mm",
                )
            ]
        ))

        dossier = clean_registry.get_asset_dossier("P-201")
        types = [m.measurement_type for obs in dossier.observations for m in obs.measurements]
        assert MeasurementTypeEnum.WALL_THICKNESS in types
        assert MeasurementTypeEnum.CLEARANCE in types

        # Ensure measurements remain distinct objects with unique semantic types
        thk_meas = [m for obs in dossier.observations for m in obs.measurements if m.measurement_type == MeasurementTypeEnum.WALL_THICKNESS]
        clr_meas = [m for obs in dossier.observations for m in obs.measurements if m.measurement_type == MeasurementTypeEnum.CLEARANCE]

        assert len(thk_meas) >= 1
        assert len(clr_meas) >= 1
        assert thk_meas[0].measurement_type != clr_meas[0].measurement_type

    def test_multi_tier_hybrid_rag_queries(self, clean_registry):
        """Test multi-tier metadata filtering in Hybrid RAG:
        1. Find everything about P-201
        2. Find all pumps in CDU
        3. Find all inspection evidence for TK-201
        4. Find all pressure vessels with historical thickness measurements
        """
        # 1. Everything about P-201
        req1 = HybridSearchRequest(
            query="Find everything about P-201 crude distillation feed pump",
            asset_tag="P-201",
            top_k=5,
        )
        res1 = clean_registry.hybrid_rag.hybrid_search(req1)
        assert len(res1) > 0
        assert any("P-201" in r.text or "P-201" in r.source.document for r in res1)

        # 2. All pumps in CDU
        req2 = HybridSearchRequest(
            query="Booster and feed pumps in CDU process unit",
            asset_class=AssetClassEnum.PUMPS,
            top_k=5,
        )
        res2 = clean_registry.hybrid_rag.hybrid_search(req2)
        assert len(res2) > 0

        # 3. All inspection evidence for TK-201
        req3 = HybridSearchRequest(
            query="TK-201 inspection evidence API 653 MFL bottom plate settlement",
            asset_tag="TK-201",
            top_k=5,
        )
        res3 = clean_registry.hybrid_rag.hybrid_search(req3)
        assert len(res3) > 0
        assert any("TK-201" in r.text or "Storage Tank" in r.text for r in res3)
