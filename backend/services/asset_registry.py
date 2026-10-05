"""
MRPL Sovereign AI Workbench — Dynamic Asset Registry Service
Manages dynamic lifecycle of plant assets, multi-tier hierarchy, component & location trees,
document attachment, observation extraction with strict semantic separation, and audit logging.
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional, Set
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

logger = logging.getLogger("mrpl.asset_registry")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "backend" / "data"
REGISTRY_FILE = DATA_DIR / "asset_registry.json"
AUDIT_FILE = DATA_DIR / "asset_audit_trail.json"
OBSERVATIONS_FILE = DATA_DIR / "asset_observations.json"


class AssetRegistryService:
    """
    Authoritative Dynamic Asset Registry for MRPL.
    Supports runtime asset creation, component/location hierarchy updates,
    document attachment with incremental RAG indexing, and non-destructive audit logging.
    """

    def __init__(self, hybrid_rag: Optional[HybridRAGService] = None, data_dir: Optional[Path] = None):
        self.hybrid_rag = hybrid_rag or HybridRAGService()
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.data_dir / "asset_registry.json"
        self.audit_file = self.data_dir / "asset_audit_trail.json"
        self.observations_file = self.data_dir / "asset_observations.json"

        self.assets: Dict[str, Asset] = {}  # keyed by asset_id and aliased by asset_tag
        self.tag_to_id: Dict[str, str] = {}
        self.audit_log: List[AssetAuditRecord] = []
        self.observations: List[EngineeringObservation] = []
        
        self.load_or_bootstrap()

    def _save(self):
        """Persists registry, audit log, and observations to JSON."""
        try:
            unique_assets = {a.asset_id: a.model_dump() for a in self.assets.values()}
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(unique_assets, f, indent=2, default=str)

            with open(self.audit_file, "w", encoding="utf-8") as f:
                json.dump([a.model_dump() for a in self.audit_log], f, indent=2, default=str)

            with open(self.observations_file, "w", encoding="utf-8") as f:
                json.dump([o.model_dump() for o in self.observations], f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to persist asset registry state: {e}")

    def load_or_bootstrap(self):
        """Loads state from disk or bootstraps from MRPL Knowledge Base."""
        if self.registry_file.exists() and self.audit_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for aid, a_dict in data.items():
                    asset = Asset(**a_dict)
                    self.assets[asset.asset_id] = asset
                    self.assets[asset.asset_tag.upper()] = asset
                    self.tag_to_id[asset.asset_tag.upper()] = asset.asset_id

                if self.audit_file.exists():
                    with open(self.audit_file, "r", encoding="utf-8") as f:
                        a_data = json.load(f)
                    self.audit_log = [AssetAuditRecord(**rec) for rec in a_data]

                if self.observations_file.exists():
                    with open(self.observations_file, "r", encoding="utf-8") as f:
                        o_data = json.load(f)
                    self.observations = [EngineeringObservation(**obs) for obs in o_data]

                logger.info(f"Loaded {len(unique_assets := set(self.tag_to_id.values()))} assets from persistent registry.")
                return
            except Exception as e:
                logger.warning(f"Failed to load existing asset registry cache, bootstrapping: {e}")

        self.bootstrap_from_knowledge_base()

    def bootstrap_from_knowledge_base(self):
        """Initializes canonical asset catalog from the 76-document MRPL Knowledge Base."""
        logger.info("Bootstrapping Dynamic Asset Registry from Knowledge Base...")
        self.assets.clear()
        self.tag_to_id.clear()
        self.audit_log.clear()
        self.observations.clear()

        # Seed initial assets
        baseline_definitions = [
            {
                "tag": "P-201",
                "name": "Crude Distillation Feed Booster Pump",
                "class": AssetClassEnum.PUMP,
                "unit": "CDU-II",
                "service": "Atmospheric Heavy Desalted Crude Oil Feed",
                "design_code": "API 610 12th Edition (Type OH2)",
                "manufacturer": "Sulzer Pumps Ltd",
                "model_number": "OH2-320-75",
                "commissioning_date": "2019-06-01",
                "class_attributes": {
                    "rated_flow_m3h": 320.0,
                    "differential_head_m": 75.0,
                    "design_pressure_barg": 14.5,
                    "operating_pressure_barg": 9.8,
                    "design_temperature_c": 165.0,
                    "driver_power_kw": 110.0,
                    "driver_speed_rpm": 2950,
                    "seal_flush_plan": "API Plan 53B"
                },
                "components": ["Pump Casing", "Impeller", "Shaft", "Mechanical Seal", "Bearing Housing"],
                "locations": ["CML-01 (Suction Nozzle)", "CML-02 (Inboard Belly)", "CML-03 (Volute Throat)", "CML-04 (Discharge Nozzle)"]
            },
            {
                "tag": "P-101",
                "name": "Atmospheric Residue Booster Pump",
                "class": AssetClassEnum.PUMP,
                "unit": "CDU-I",
                "service": "Atmospheric Tower Bottoms Residue (>300 C)",
                "design_code": "API 610 12th Edition (Type BB2)",
                "manufacturer": "Flowserve Corp",
                "model_number": "BB2-280-68",
                "commissioning_date": "2018-05-15",
                "class_attributes": {
                    "rated_flow_m3h": 280.0,
                    "differential_head_m": 68.0,
                    "operating_temperature_c": 340.0,
                    "driver_power_kw": 132.0,
                    "driver_speed_rpm": 2960,
                    "seal_flush_plan": "API Plan 53A (Synthetic PAO)"
                },
                "components": ["Pump Casing", "Impeller", "Wear Rings", "Mechanical Seal", "Driver Motor & Coupling"],
                "locations": ["suction nozzle", "discharge nozzle", "casing inboard", "casing wear region", "bearing housing NDE"]
            },
            {
                "tag": "V-201",
                "name": "High Pressure 3-Phase Separator Vessel",
                "class": AssetClassEnum.PRESSURE_VESSEL,
                "unit": "CDU-II",
                "service": "Light Ends Gas/Oil/Water Separation",
                "design_code": "ASME Section VIII Div 1 Edition 2019",
                "manufacturer": "L&T Heavy Engineering",
                "model_number": "HP-SEP-2200x6800",
                "commissioning_date": "2017-04-25",
                "class_attributes": {
                    "design_pressure_barg": 28.0,
                    "operating_pressure_barg": 22.0,
                    "design_temperature_c": 120.0,
                    "internal_diameter_mm": 2200,
                    "tan_to_tan_length_mm": 6800,
                    "nominal_thickness_mm": 18.0,
                    "corrosion_allowance_mm": 5.5
                },
                "components": ["Vessel Shell", "Top Head", "Bottom Head", "Inlet Nozzle N1", "Demister Pad", "Water Boot"],
                "locations": ["vessel shell course 1", "vessel shell course 2", "top head (2:1 ellipsoidal)", "bottom head (2:1 ellipsoidal)", "inlet nozzle N1 region"]
            },
            {
                "tag": "TK-201",
                "name": "Crude Storage Tank (50,000 m3)",
                "class": AssetClassEnum.STORAGE_TANK,
                "unit": "Tank Farm Area 3",
                "service": "Import Crude Hydrocarbon Storage",
                "design_code": "API Standard 650 13th Edition",
                "manufacturer": "Vijay Tanks & Vessels Ltd",
                "model_number": "EFR-TK-50K",
                "commissioning_date": "2018-09-10",
                "class_attributes": {
                    "working_capacity_m3": 50000.0,
                    "nominal_diameter_m": 60.0,
                    "height_m": 19.5,
                    "max_safe_fill_level_m": 19.0,
                    "roof_type": "External Floating Roof (Double Deck)",
                    "seal_type": "Primary Mechanical Shoe + Secondary Polyurethane Wiper"
                },
                "components": ["Shell Courses 1-5", "Annular Plates", "Floor Plates", "Floating Roof", "Articulated Roof Drain", "ICCP Anode Grid"],
                "locations": ["shell course 1 (bottom course)", "bottom annular plate", "bottom floor plate MFL zone A/B/C", "geodetic settlement benchmark points (BM-01 to BM-16)", "floating roof rim seal"]
            },
            {
                "tag": "PSV-201",
                "name": "Crude Booster Pump Discharge Safety Relief Valve",
                "class": AssetClassEnum.VALVE,
                "unit": "CDU-II",
                "service": "Hydrocarbon Overpressure Relief to Flare",
                "design_code": "API Standard 520 / 526",
                "manufacturer": "Consolidated / Baker Hughes",
                "model_number": "1900 Series Flanged Relief Valve",
                "commissioning_date": "2020-02-18",
                "class_attributes": {
                    "set_pressure_barg": 12.0,
                    "orifice_designation": "1.5J2",
                    "inlet_flange": "2-inch Class 300 RF",
                    "outlet_flange": "3-inch Class 150 RF",
                    "relieving_capacity_kgh": 38500.0
                },
                "components": ["Valve Body", "Nozzle & Disc", "Spring", "Bonnet & Cap"],
                "locations": ["valve seating face", "inlet nozzle neck", "spring chamber"]
            },
            {
                "tag": "XV-203",
                "name": "Crude Pump Suction Emergency Shutdown Valve",
                "class": AssetClassEnum.VALVE,
                "unit": "CDU-II",
                "service": "Emergency Suction Isolation (SIL-3)",
                "design_code": "API 6D / IEC 61508 / IEC 61511",
                "manufacturer": "Fisher / Emerson",
                "model_number": "High Performance Butterfly Valve",
                "commissioning_date": "2020-05-14",
                "class_attributes": {
                    "valve_size_inch": 12,
                    "sil_rating": "SIL-3",
                    "fail_position": "Fail Close (FC)",
                    "stroke_time_sec": 3.2
                },
                "components": ["Valve Body", "Disc & Stem", "Pneumatic Actuator", "Partial Stroke Testing Module"],
                "locations": ["valve body", "stem packing", "actuator cylinder"]
            },
            {
                "tag": "C-101",
                "name": "Atmospheric Distillation Crude Fractionator Column",
                "class": AssetClassEnum.COLUMN,
                "unit": "CDU-I",
                "service": "Crude Oil Fractionation",
                "design_code": "ASME Section VIII Div 1",
                "manufacturer": "L&T Heavy Engineering",
                "model_number": "COL-4200x48000",
                "commissioning_date": "2017-06-12",
                "class_attributes": {
                    "total_height_m": 48.0,
                    "column_diameter_mm": 4200,
                    "tray_count": 48,
                    "tray_type": "Valve Trays (316L SS)"
                },
                "components": ["Shell Sections", "Fractionation Trays", "Flash Zone Internals", "Overhead Vapor Line"],
                "locations": ["bottom flash zone", "feed tray zone", "overhead vapor nozzle"]
            },
            {
                "tag": "E-101",
                "name": "Crude Preheat Shell & Tube Exchanger Train",
                "class": AssetClassEnum.HEAT_EXCHANGER,
                "unit": "CDU-I",
                "service": "Crude Feed vs Residue Heat Transfer",
                "design_code": "TEMA Class R / ASME Section VIII",
                "manufacturer": "Alfa Laval / BHI",
                "model_number": "TEMA Type AES",
                "commissioning_date": "2019-03-25",
                "class_attributes": {
                    "shell_side_fluid": "Atmospheric Residue (340 C)",
                    "tube_side_fluid": "Raw Crude Feed (120 C)",
                    "heat_duty_mw": 18.5,
                    "tube_material": "Duplex Stainless Steel 2205",
                    "tube_count": 840
                },
                "components": ["Exchanger Shell", "Channel Head", "Tube Bundle", "Baffles", "Floating Head"],
                "locations": ["shell inlet nozzle", "tube bundle entrance", "floating head cover"]
            }
        ]

        for defn in baseline_definitions:
            aid = f"ASSET-MRPL-{defn['unit'].replace(' ', '-').upper()}-{defn['tag']}"
            
            components = [
                AssetComponent(
                    component_id=f"COMP-{defn['tag']}-{idx+1:02d}",
                    component_name=cname,
                    criticality="HIGH"
                )
                for idx, cname in enumerate(defn["components"])
            ]

            locations = [
                InspectionLocation(
                    location_id=f"LOC-{defn['tag']}-{idx+1:02d}",
                    location_name=lname,
                    component_name=components[min(idx, len(components)-1)].component_name
                )
                for idx, lname in enumerate(defn["locations"])
            ]

            asset = Asset(
                asset_id=aid,
                asset_tag=defn["tag"],
                asset_name=defn["name"],
                asset_class=defn["class"],
                organization="MRPL",
                refinery="Mangalore Refinery",
                process_unit=defn["unit"],
                service_description=defn["service"],
                design_code=defn.get("design_code"),
                manufacturer=defn.get("manufacturer"),
                model_number=defn.get("model_number"),
                commissioning_date=defn.get("commissioning_date"),
                class_attributes=defn.get("class_attributes", {}),
                components=components,
                inspection_locations=locations,
                status=AssetStatusEnum.IN_SERVICE,
            )

            # Link existing documents from Hybrid RAG
            for doc_id, doc in self.hybrid_rag.documents.items():
                doc_str = json.dumps(doc).upper()
                if defn["tag"].upper() in doc_str or defn["tag"].replace("-", "").upper() in doc_str:
                    asset.documents_manifest.append(doc_id)
                    # Extract observation
                    obs_list = self.extract_observations_from_document(asset, doc)
                    self.observations.extend(obs_list)

            self.assets[asset.asset_id] = asset
            self.assets[asset.asset_tag.upper()] = asset
            self.tag_to_id[asset.asset_tag.upper()] = asset.asset_id

            self.audit_log.append(AssetAuditRecord(
                asset_id=asset.asset_id,
                asset_tag=asset.asset_tag,
                action="ASSET_CREATED",
                performed_by="SYSTEM_BOOTSTRAP",
                details={"source": "MRPL_KNOWLEDGE_BASE", "documents_linked": len(asset.documents_manifest)}
            ))

        self._save()
        logger.info(f"Dynamic Asset Registry bootstrap complete: {len(self.tag_to_id)} assets initialized.")

    def extract_observations_from_document(self, asset: Asset, doc: Dict[str, Any]) -> List[EngineeringObservation]:
        """Extracts structured engineering observations with precise location, measurement type, and provenance."""
        observations: List[EngineeringObservation] = []
        doc_id = doc.get("document_id", "DOC-UNKNOWN")
        doc_type = doc.get("document_type", "Inspection Reports")
        title = doc.get("title", doc_id)
        date = doc.get("date", "2024-01-01")
        section = doc.get("section", "General")
        page = int(doc.get("page_number", 1))
        content = doc.get("content", "")
        meta = doc.get("metadata", {})

        prov = ProvenanceRecord(
            document_id=doc_id,
            document_name=title,
            document_type=doc_type,
            page=page,
            section=section,
            exact_source_span=content[:200],
            date=date,
            revision=doc.get("revision") or meta.get("revision", "Rev 0"),
            authority=doc.get("authority") or meta.get("authority", "Authority Level A"),
            approval_status=doc.get("approval_status") or meta.get("approval_status", "APPROVED_FOR_SERVICE"),
            is_official_mrpl=doc.get("is_official_mrpl", True)
        )

        # 1. Parse from metadata if explicitly present
        if meta.get("inspection_locations"):
            for loc in meta["inspection_locations"]:
                measurements: List[EngineeringMeasurement] = []
                # Wall thickness
                if meta.get("measured_min_thickness") or meta.get("nominal_thickness"):
                    val = float(str(meta.get("measured_min_thickness") or meta.get("nominal_thickness") or "5.0").replace(" mm", "").replace("mm", "").strip())
                    measurements.append(EngineeringMeasurement(
                        measurement_type=MeasurementTypeEnum.WALL_THICKNESS,
                        value=val,
                        unit="mm",
                        nominal_value=float(str(meta.get("nominal_thickness", "5.0")).replace(" mm", "").replace("mm", "").strip()) if meta.get("nominal_thickness") else None,
                        minimum_allowable_limit=float(str(meta.get("retirement_thickness", "3.2")).replace(" mm", "").replace("mm", "").strip()) if meta.get("retirement_thickness") else None,
                        description="Ultrasonic wall thickness measurement"
                    ))
                
                obs = EngineeringObservation(
                    asset_id=asset.asset_id,
                    asset_tag=asset.asset_tag,
                    component_name=meta.get("component", "Asset Component"),
                    inspection_location=loc,
                    observation_type=f"{doc_type} Observation",
                    observation_date=date,
                    measurements=measurements,
                    findings_summary=f"Inspection record for {loc} under {doc_id}",
                    provenance=prov
                )
                observations.append(obs)

        # 2. Text line parsing if no explicit meta locations
        if not observations and content:
            lines = content.split("\n")
            for line in lines:
                l_str = line.strip()
                if any(k in l_str for k in ["Thickness", "thickness", "Clearance", "clearance", "Settlement", "settlement", "Vibration", "vibration", "Pressure", "barg", "mm"]):
                    if len(l_str) > 15:
                        measurements: List[EngineeringMeasurement] = []
                        m_type = MeasurementTypeEnum.GENERIC_MEASUREMENT
                        if "thickness" in l_str.lower(): m_type = MeasurementTypeEnum.WALL_THICKNESS
                        elif "clearance" in l_str.lower(): m_type = MeasurementTypeEnum.CLEARANCE
                        elif "vibration" in l_str.lower(): m_type = MeasurementTypeEnum.VIBRATION_RMS
                        elif "settlement" in l_str.lower(): m_type = MeasurementTypeEnum.SETTLEMENT
                        elif "pressure" in l_str.lower() or "barg" in l_str.lower(): m_type = MeasurementTypeEnum.SET_PRESSURE

                        # Extract first numerical value
                        import re
                        num_match = re.search(r"(\d+(?:\.\d+)?)", l_str)
                        val = float(num_match.group(1)) if num_match else 0.0
                        unit = "mm"
                        if "barg" in l_str: unit = "barg"
                        elif "mm/s" in l_str: unit = "mm/s RMS"
                        elif "deg c" in l_str.lower() or "°c" in l_str.lower(): unit = "°C"
                        elif "m3/h" in l_str.lower(): unit = "m3/h"

                        measurements.append(EngineeringMeasurement(
                            measurement_type=m_type,
                            value=val,
                            unit=unit,
                            description=l_str[:120]
                        ))

                        obs = EngineeringObservation(
                            asset_id=asset.asset_id,
                            asset_tag=asset.asset_tag,
                            component_name=asset.components[0].component_name if asset.components else "Main Body",
                            inspection_location=asset.inspection_locations[0].location_name if asset.inspection_locations else "General Zone",
                            observation_type=f"{doc_type} Observation",
                            observation_date=date,
                            measurements=measurements,
                            findings_summary=l_str,
                            provenance=prov
                        )
                        observations.append(obs)
                        if len(observations) >= 4:
                            break

        return observations

    def get_all_assets(
        self,
        asset_class: Optional[AssetClassEnum] = None,
        process_unit: Optional[str] = None,
        status: Optional[AssetStatusEnum] = None,
        search_query: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[Asset]:
        """Lists registered assets with optional filters."""
        # Use canonical unique assets
        unique_assets = [self.assets[aid] for aid in set(self.tag_to_id.values())]
        filtered = []

        raw_q = query or search_query
        q_lower = raw_q.lower().strip() if raw_q else None

        for a in unique_assets:
            if asset_class and a.asset_class != asset_class:
                continue
            if process_unit and process_unit.lower() not in a.process_unit.lower():
                continue
            if status and a.status != status:
                continue
            if q_lower:
                match = (
                    q_lower in a.asset_tag.lower() or
                    q_lower in a.asset_name.lower() or
                    q_lower in a.service_description.lower() or
                    q_lower in a.process_unit.lower()
                )
                if not match:
                    continue
            filtered.append(a)

        filtered.sort(key=lambda x: (x.process_unit, x.asset_class.value, x.asset_tag))
        return filtered

    def get_asset(self, tag_or_id: str) -> Optional[Asset]:
        """Retrieves asset by tag (e.g. P-201, PSV-301) or full ID."""
        key = tag_or_id.upper().strip()
        if key in self.assets:
            return self.assets[key]
        if key in self.tag_to_id:
            return self.assets[self.tag_to_id[key]]
        return None

    def create_asset(self, req: AssetCreateRequest, performed_by: str = "MRPL_OPERATIONS_USER") -> Asset:
        """
        Dynamically registers a completely new asset without developer/code/schema modifications.
        Immediately assigns a stable internal Asset ID and persists to disk.
        """
        tag = req.asset_tag.upper().strip()
        if tag in self.assets or tag in self.tag_to_id:
            raise ValueError(f"Asset tag '{tag}' already exists in MRPL Registry (Asset ID: {self.tag_to_id.get(tag)}).")

        unit_code = req.process_unit.replace(" ", "-").upper()
        asset_id = f"ASSET-MRPL-{unit_code}-{tag}"

        components = [
            AssetComponent(
                component_id=f"COMP-{tag}-{i+1:02d}",
                component_name=cname.strip(),
                criticality="HIGH"
            )
            for i, cname in enumerate(req.initial_components)
        ]

        locations = [
            InspectionLocation(
                location_id=f"LOC-{tag}-{i+1:02d}",
                location_name=lname.strip(),
                component_name=components[0].component_name if components else "Main Body"
            )
            for i, lname in enumerate(req.initial_inspection_locations)
        ]

        asset = Asset(
            asset_id=asset_id,
            asset_tag=tag,
            asset_name=req.asset_name or req.name or tag,
            asset_class=req.asset_class,
            organization="MRPL",
            refinery=req.refinery or "Mangalore Refinery",
            process_unit=req.process_unit or "CDU-II",
            parent_asset_tag=req.parent_asset_tag,
            service_description=req.service_description or req.service or "Refinery Continuous Service",
            status=req.status or AssetStatusEnum.IN_SERVICE,
            design_code=req.design_code or "API 610 / ASME VIII",
            manufacturer=req.manufacturer,
            model_number=req.model_number,
            commissioning_date=req.commissioning_date or time.strftime("%Y-%m-%d"),
            class_attributes=req.class_attributes or {},
            components=components,
            inspection_locations=locations,
            created_at=time.time(),
            updated_at=time.time(),
            revision=1,
            data_status="DEMONSTRATION / CURATED TEST DATA"
        )

        self.assets[asset.asset_id] = asset
        self.assets[tag] = asset
        self.tag_to_id[tag] = asset.asset_id

        # Audit event
        self.audit_log.append(AssetAuditRecord(
            asset_id=asset.asset_id,
            asset_tag=asset.asset_tag,
            action="ASSET_CREATED",
            performed_by=performed_by,
            details={
                "asset_class": req.asset_class.value,
                "process_unit": req.process_unit,
                "components_count": len(components),
                "locations_count": len(locations),
            }
        ))

        self._save()
        logger.info(f"Created new asset [{asset.asset_id}] ({tag}) in MRPL Asset Registry.")
        return asset

    def add_component(self, tag_or_id: str, comp_or_name: Any, description: Optional[str] = None, material: Optional[str] = None) -> Asset:
        """Adds a component to an existing asset and returns updated Asset."""
        asset = self.get_asset(tag_or_id)
        if not asset:
            raise ValueError(f"Asset '{tag_or_id}' not found.")

        if isinstance(comp_or_name, AssetComponent):
            comp = comp_or_name
            if not comp.component_id:
                comp.component_id = f"COMP-{asset.asset_tag}-{len(asset.components)+1:02d}"
        elif isinstance(comp_or_name, dict):
            comp = AssetComponent(**comp_or_name)
        else:
            comp_id = f"COMP-{asset.asset_tag}-{len(asset.components)+1:02d}"
            comp = AssetComponent(
                component_id=comp_id,
                component_name=str(comp_or_name),
                description=description,
                material_of_construction=material,
                criticality="HIGH"
            )

        asset.components.append(comp)
        asset.updated_at = time.time()
        asset.revision += 1

        self.audit_log.append(AssetAuditRecord(
            asset_id=asset.asset_id,
            asset_tag=asset.asset_tag,
            action="COMPONENT_ADDED",
            performed_by="MRPL_OPERATIONS_USER",
            details={"component_id": comp.component_id, "component_name": comp.component_name}
        ))
        self._save()
        return asset

    def add_inspection_location(self, tag_or_id: str, loc_or_tag: Any, component_name: Optional[str] = None, method: str = "Ultrasonic Thickness (UT)", baseline_value: Optional[float] = None, unit: Optional[str] = None) -> Asset:
        """Adds an inspection location to an existing asset and returns updated Asset."""
        asset = self.get_asset(tag_or_id)
        if not asset:
            raise ValueError(f"Asset '{tag_or_id}' not found.")

        if isinstance(loc_or_tag, InspectionLocation):
            loc = loc_or_tag
            if not loc.location_id:
                loc.location_id = f"LOC-{asset.asset_tag}-{len(asset.inspection_locations)+1:02d}"
        elif isinstance(loc_or_tag, dict):
            loc = InspectionLocation(**loc_or_tag)
        else:
            loc_id = f"LOC-{asset.asset_tag}-{len(asset.inspection_locations)+1:02d}"
            loc = InspectionLocation(
                location_id=loc_id,
                location_name=str(loc_or_tag),
                component_name=component_name or (asset.components[0].component_name if asset.components else "Main Body"),
                inspection_method=method,
                baseline_value=baseline_value,
                unit=unit
            )

        asset.inspection_locations.append(loc)
        asset.updated_at = time.time()
        asset.revision += 1

        self.audit_log.append(AssetAuditRecord(
            asset_id=asset.asset_id,
            asset_tag=asset.asset_tag,
            action="LOCATION_ADDED",
            performed_by="MRPL_OPERATIONS_USER",
            details={"location_id": loc.location_id, "location_name": loc.location_name, "method": loc.inspection_method}
        ))
        self._save()
        return asset

    def add_document_to_asset(
        self,
        tag_or_id: str,
        doc_req: AssetDocumentUploadRequest,
        performed_by: str = "MRPL_OPERATIONS_USER"
    ) -> Dict[str, Any]:
        """
        Attaches a new engineering document to an asset:
        1. Assigns a stable Document ID.
        2. Links to Asset ID.
        3. Extracts structured observations.
        4. Incrementally indexes into Hybrid RAG without rebuilding entire index.
        5. Preserves historical records non-destructively.
        """
        asset = self.get_asset(tag_or_id)
        if not asset:
            raise ValueError(f"Asset '{tag_or_id}' not found.")

        doc_id = doc_req.document_id or f"MRPL-{doc_req.category.split('_')[-1].upper()}-{time.strftime('%Y')}-{asset.asset_tag}-{len(asset.documents_manifest)+1:02d}"
        
        doc_dict = {
            "category": doc_req.category,
            "filename": f"{doc_id}.json",
            "document_id": doc_id,
            "document_type": doc_req.document_type,
            "title": doc_req.title,
            "equipment_tag": asset.asset_tag,
            "asset_id": asset.asset_id,
            "asset_class": asset.asset_class.value,
            "equipment_type": asset.asset_class.value,
            "plant_area": asset.process_unit,
            "date": doc_req.date,
            "revision": doc_req.revision,
            "authority": doc_req.authority,
            "approval_status": doc_req.approval_status,
            "source_type": doc_req.category,
            "source_file": f"{doc_id}.json",
            "page_number": doc_req.page_number,
            "section": doc_req.section,
            "content": doc_req.content,
            "metadata": {
                **doc_req.metadata,
                "data_status": "DEMONSTRATION / CURATED TEST DATA",
                "is_official_mrpl": False,
                "disclaimer": "DEMONSTRATION / CURATED TEST DATA: NOT MRPL OFFICIAL RECORD",
                "component": doc_req.component or (asset.components[0].component_name if asset.components else "Main Body"),
                "inspection_locations": [doc_req.inspection_location] if doc_req.inspection_location else [loc.location_name for loc in asset.inspection_locations],
                "revision": doc_req.revision,
                "authority": doc_req.authority,
                "approval_status": doc_req.approval_status
            }
        }

        # 1. Incrementally Index into Hybrid RAG
        retrieved_chunk = self.hybrid_rag.index_document_incremental(doc_dict)

        # 2. Extract structured observations
        new_obs = self.extract_observations_from_document(asset, doc_dict)
        self.observations.extend(new_obs)

        # 3. Update asset manifest
        if doc_id not in asset.documents_manifest:
            asset.documents_manifest.append(doc_id)
        asset.updated_at = time.time()
        asset.revision += 1

        # 4. Audit trail entry
        audit_rec = AssetAuditRecord(
            asset_id=asset.asset_id,
            asset_tag=asset.asset_tag,
            action="DOCUMENT_ATTACHED",
            performed_by=performed_by,
            details={
                "document_id": doc_id,
                "title": doc_req.title,
                "category": doc_req.category,
                "date": doc_req.date,
                "observations_extracted": len(new_obs)
            }
        )
        self.audit_log.append(audit_rec)
        self._save()

        logger.info(f"Attached document [{doc_id}] to asset [{asset.asset_tag}] with {len(new_obs)} observations extracted.")

        return {
            "status": "SUCCESS",
            "success": True,
            "document_id": doc_id,
            "asset_id": asset.asset_id,
            "asset_tag": asset.asset_tag,
            "observations_count": len(new_obs),
            "chunk_indexed": retrieved_chunk.model_dump(),
            "audit_record": audit_rec.model_dump()
        }

    def get_asset_dossier(self, tag_or_id: str) -> AssetDossier:
        """
        Dynamically aggregates the full engineering dossier for any asset:
        information, datasheets, P&IDs, inspections, calibration, observations, measurements, and audit history.
        """
        asset = self.get_asset(tag_or_id)
        if not asset:
            raise ValueError(f"Asset '{tag_or_id}' not found.")

        # Aggregate documents by category
        docs_by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for doc_id in asset.documents_manifest:
            doc = self.hybrid_rag.documents.get(doc_id)
            if doc:
                cat = doc.get("document_type", doc.get("category", "General"))
                if cat not in docs_by_cat:
                    docs_by_cat[cat] = []
                docs_by_cat[cat].append({
                    "document_id": doc.get("document_id", doc_id),
                    "title": doc.get("title", doc_id),
                    "date": doc.get("date", "N/A"),
                    "revision": doc.get("revision") or doc.get("metadata", {}).get("revision", "Rev 0"),
                    "authority": doc.get("authority") or doc.get("metadata", {}).get("authority", "Authority Level A"),
                    "approval_status": doc.get("approval_status") or doc.get("metadata", {}).get("approval_status", "APPROVED_FOR_SERVICE"),
                    "section": doc.get("section", "General"),
                    "page": doc.get("page_number", 1),
                    "source_file": doc.get("source_file", f"{doc_id}.json")
                })

        # Observations for this asset
        asset_obs = [o for o in self.observations if o.asset_tag.upper() == asset.asset_tag.upper()]
        
        # Flatten recent measurements
        recent_msr: List[EngineeringMeasurement] = []
        for o in asset_obs:
            recent_msr.extend(o.measurements)

        # Audit records
        asset_audits = [a for a in self.audit_log if a.asset_tag.upper() == asset.asset_tag.upper()]
        asset_audits.sort(key=lambda x: x.timestamp, reverse=True)

        hierarchy_path = f"{asset.organization} -> {asset.refinery} -> {asset.process_unit} -> {asset.asset_class.value} -> {asset.asset_tag}"

        return AssetDossier(
            asset=asset,
            hierarchy_path=hierarchy_path,
            total_documents=len(asset.documents_manifest),
            categories_covered=sorted(list(docs_by_cat.keys())),
            documents_by_category=docs_by_cat,
            observations=asset_obs,
            recent_measurements=recent_msr[:20],
            audit_trail=asset_audits,
            summary=f"Dynamic engineering dossier for {asset.asset_tag} ({asset.asset_name}) with {len(asset.documents_manifest)} linked documents across {len(docs_by_cat)} categories and {len(asset_obs)} structured observations."
        )

    def get_hierarchy_tree(self) -> HierarchyNode:
        """
        Builds and returns the full 10-tier dynamic hierarchical tree:
        MRPL (Org) -> Mangalore (Refinery) -> Process Unit -> Asset Class -> Asset
          -> Component -> Inspection Location -> Observation -> Measurement -> Provenance
        """
        root = HierarchyNode(
            id="MRPL-CORP",
            label="Mangalore Refinery & Petrochemicals Ltd (MRPL)",
            node_type="organization",
            children_count=0,
            children=[]
        )

        # Group assets by refinery -> process_unit -> asset_class
        refinery_map: Dict[str, Dict[str, Dict[str, List[Asset]]]] = {}
        unique_assets = [self.assets[aid] for aid in set(self.tag_to_id.values())]

        for a in unique_assets:
            ref = a.refinery or "Mangalore Refinery"
            unit = a.process_unit or "CDU-II"
            aclass = a.asset_class.value

            if ref not in refinery_map:
                refinery_map[ref] = {}
            if unit not in refinery_map[ref]:
                refinery_map[ref][unit] = {}
            if aclass not in refinery_map[ref][unit]:
                refinery_map[ref][unit][aclass] = []
            refinery_map[ref][unit][aclass].append(a)

        for ref_name, units in refinery_map.items():
            ref_node = HierarchyNode(
                id="MRPL-MANGALORE",
                label=ref_name,
                node_type="refinery",
                children_count=0,
                children=[]
            )

            for unit_name, classes in units.items():
                unit_node = HierarchyNode(
                    id=f"UNIT-{unit_name.replace(' ', '-').upper()}",
                    label=unit_name,
                    node_type="process_unit",
                    children_count=0,
                    children=[]
                )

                for class_name, asset_list in classes.items():
                    class_node = HierarchyNode(
                        id=f"CLASS-{unit_name.replace(' ', '-').upper()}-{class_name}",
                        label=f"{class_name.replace('_', ' ').title()}s ({len(asset_list)})",
                        node_type="asset_class",
                        asset_class=class_name,
                        children_count=len(asset_list),
                        children=[]
                    )

                    for a in asset_list:
                        a_node = HierarchyNode(
                            id=a.asset_id,
                            label=f"{a.asset_tag} — {a.asset_name}",
                            node_type="asset",
                            asset_class=a.asset_class.value,
                            asset_tag=a.asset_tag,
                            status=a.status.value,
                            children_count=0,
                            children=[]
                        )

                        # Find observations for this asset
                        asset_obs = [o for o in self.observations if o.asset_tag.upper() == a.asset_tag.upper()]

                        # Map components
                        comp_nodes: Dict[str, HierarchyNode] = {}
                        for comp in a.components:
                            c_node = HierarchyNode(
                                id=comp.component_id,
                                label=f"Component: {comp.component_name} ({comp.criticality})",
                                node_type="component",
                                asset_tag=a.asset_tag,
                                children_count=0,
                                children=[]
                            )
                            comp_nodes[comp.component_name.upper()] = c_node
                            comp_nodes[comp.component_id.upper()] = c_node
                            a_node.children.append(c_node)

                        # Map inspection locations
                        loc_nodes: Dict[str, HierarchyNode] = {}
                        for loc in a.inspection_locations:
                            l_node = HierarchyNode(
                                id=loc.location_id,
                                label=f"Inspection Location: {loc.location_name} ({loc.inspection_method})",
                                node_type="location",
                                asset_tag=a.asset_tag,
                                children_count=0,
                                children=[]
                            )
                            loc_nodes[loc.location_name.upper()] = l_node
                            loc_nodes[loc.location_id.upper()] = l_node

                            # Attach to parent component if present, else asset
                            target_parent = a_node
                            if loc.component_name and loc.component_name.upper() in comp_nodes:
                                target_parent = comp_nodes[loc.component_name.upper()]
                            target_parent.children.append(l_node)

                        # Attach observations
                        for obs in asset_obs:
                            obs_node = HierarchyNode(
                                id=obs.observation_id,
                                label=f"Observation: {obs.findings_summary[:60]} ({obs.observation_date})",
                                node_type="observation",
                                asset_tag=a.asset_tag,
                                children_count=0,
                                children=[]
                            )

                            # Attach measurements
                            for msr in obs.measurements:
                                msr_node = HierarchyNode(
                                    id=msr.measurement_id,
                                    label=f"Measurement: {msr.measurement_type.value} = {msr.value} {msr.unit}",
                                    node_type="measurement",
                                    asset_tag=a.asset_tag,
                                    children_count=0,
                                    children=[]
                                )

                                # Attach Provenance node
                                prov = obs.provenance
                                prov_node = HierarchyNode(
                                    id=f"PROV-{prov.document_id}",
                                    label=f"Provenance: {prov.document_name} ({prov.section} p.{prov.page})",
                                    node_type="provenance",
                                    asset_tag=a.asset_tag,
                                    children_count=0,
                                    children=[]
                                )
                                msr_node.children.append(prov_node)
                                msr_node.children_count += 1
                                obs_node.children.append(msr_node)
                                obs_node.children_count += 1

                            # Place observation under matching location or component or asset
                            target_loc = None
                            if obs.inspection_location and obs.inspection_location.upper() in loc_nodes:
                                target_loc = loc_nodes[obs.inspection_location.upper()]
                            elif obs.component_name and obs.component_name.upper() in comp_nodes:
                                target_loc = comp_nodes[obs.component_name.upper()]
                            else:
                                target_loc = a_node

                            target_loc.children.append(obs_node)
                            target_loc.children_count += 1

                        a_node.children_count = len(a_node.children)
                        class_node.children.append(a_node)

                    unit_node.children.append(class_node)
                    unit_node.children_count += len(asset_list)

                ref_node.children.append(unit_node)
                ref_node.children_count += unit_node.children_count

            root.children.append(ref_node)
            root.children_count += ref_node.children_count

        return root

    def get_audit_trail(self, tag_or_id: Optional[str] = None) -> List[AssetAuditRecord]:
        """Returns audit records for a specific asset or full registry."""
        if tag_or_id:
            asset = self.get_asset(tag_or_id)
            if not asset:
                return []
            return [a for a in self.audit_log if a.asset_tag.upper() == asset.asset_tag.upper()]
        return self.audit_log
