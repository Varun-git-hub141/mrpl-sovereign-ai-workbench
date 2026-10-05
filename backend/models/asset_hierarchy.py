"""
MRPL Sovereign AI Workbench — Dynamic Asset Hierarchy and Registry Models
Implements the full 10-level hierarchy:
MRPL -> Refinery -> Process Unit -> Asset Class -> Asset -> Component -> Inspection Location -> Observation -> Measurement -> Provenance
"""

import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AssetClassEnum(str, Enum):
    PUMP = "PUMP"
    PRESSURE_VESSEL = "PRESSURE_VESSEL"
    STORAGE_TANK = "STORAGE_TANK"
    VALVE = "VALVE"
    HEAT_EXCHANGER = "HEAT_EXCHANGER"
    COMPRESSOR = "COMPRESSOR"
    COLUMN = "COLUMN"
    REACTOR = "REACTOR"
    FIRED_HEATER = "FIRED_HEATER"
    PIPING = "PIPING"
    INSTRUMENT = "INSTRUMENT"
    ELECTRICAL = "ELECTRICAL"
    OTHER = "OTHER"

    # Common aliases
    PUMPS = "PUMP"
    PRESSURE_VESSELS = "PRESSURE_VESSEL"
    STORAGE_TANKS = "STORAGE_TANK"
    VALVES = "VALVE"
    HEAT_EXCHANGERS = "HEAT_EXCHANGER"
    COMPRESSORS = "COMPRESSOR"
    COLUMNS = "COLUMN"
    REACTORS = "REACTOR"
    FIRED_HEATERS = "FIRED_HEATER"
    INSTRUMENTS = "INSTRUMENT"


class AssetStatusEnum(str, Enum):
    IN_SERVICE = "IN_SERVICE"
    STANDBY = "STANDBY"
    MAINTENANCE_OUTAGE = "MAINTENANCE_OUTAGE"
    RETIRED = "RETIRED"
    COMMISSIONING = "COMMISSIONING"


class MeasurementTypeEnum(str, Enum):
    WALL_THICKNESS = "WALL_THICKNESS"
    CLEARANCE = "CLEARANCE"
    VIBRATION_RMS = "VIBRATION_RMS"
    SET_PRESSURE = "SET_PRESSURE"
    BLOWDOWN = "BLOWDOWN"
    POP_PRESSURE = "POP_PRESSURE"
    TEMPERATURE = "TEMPERATURE"
    FLOW_RATE = "FLOW_RATE"
    DIFFERENTIAL_PRESSURE = "DIFFERENTIAL_PRESSURE"
    SETTLEMENT = "SETTLEMENT"
    CORROSION_RATE = "CORROSION_RATE"
    VOLTAGE = "VOLTAGE"
    CURRENT = "CURRENT"
    ACOUSTIC_EMISSION = "ACOUSTIC_EMISSION"
    GENERIC_MEASUREMENT = "GENERIC_MEASUREMENT"


class ProvenanceRecord(BaseModel):
    document_id: str
    document_name: str
    document_type: str = "Inspection Reports"
    page: int = 1
    section: str = "General"
    exact_source_span: Optional[str] = None
    date: Optional[str] = None
    revision: Optional[str] = None
    authority: str = "Authority Level A"
    approval_status: str = "APPROVED_FOR_SERVICE"
    is_official_mrpl: bool = False
    disclaimer: str = "DEMONSTRATION / CURATED TEST DATA: NOT MRPL OFFICIAL RECORD"


class EngineeringMeasurement(BaseModel):
    measurement_id: str = Field(default_factory=lambda: f"MSR-{int(time.time()*1000)%1000000:06d}")
    measurement_type: MeasurementTypeEnum
    value: float
    unit: str
    nominal_value: Optional[float] = None
    minimum_allowable_limit: Optional[float] = None
    maximum_allowable_limit: Optional[float] = None
    available_margin: Optional[float] = None
    tolerance_min: Optional[float] = None
    tolerance_max: Optional[float] = None
    is_within_limits: bool = True
    alert_level: str = "NORMAL"  # NORMAL, WARNING, CRITICAL_ALERT
    description: Optional[str] = None


class InspectionLocation(BaseModel):
    location_id: str
    location_name: Optional[str] = None
    location_tag: Optional[str] = None
    component_id: Optional[str] = None
    component_name: Optional[str] = None
    inspection_method: str = "Ultrasonic Thickness (UT)"
    description: Optional[str] = None
    coordinates_or_description: Optional[str] = None
    baseline_value: Optional[float] = None
    nominal_thickness_mm: Optional[float] = None
    minimum_required_thickness_mm: Optional[float] = None
    corrosion_allowance_mm: Optional[float] = None
    unit: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.location_name and self.location_tag:
            self.location_name = self.location_tag
        if not self.location_tag and self.location_name:
            self.location_tag = self.location_name
        if not self.coordinates_or_description and self.description:
            self.coordinates_or_description = self.description


class EngineeringObservation(BaseModel):
    observation_id: str = Field(default_factory=lambda: f"OBS-{int(time.time()*1000)%1000000:06d}")
    asset_id: str
    asset_tag: str
    component_name: str
    inspection_location: str
    observation_type: str
    observation_date: str
    measurements: List[EngineeringMeasurement] = Field(default_factory=list)
    findings_summary: str
    provenance: ProvenanceRecord
    created_at: float = Field(default_factory=time.time)


class AssetComponent(BaseModel):
    component_id: str
    component_name: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    component_type: Optional[str] = None
    material: Optional[str] = None
    material_of_construction: Optional[str] = None
    criticality: str = "HIGH"  # HIGH, MEDIUM, LOW
    inspection_locations: List[InspectionLocation] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.component_name and self.name:
            self.component_name = self.name
        if not self.name and self.component_name:
            self.name = self.component_name
        if not self.material_of_construction and self.material:
            self.material_of_construction = self.material


class Asset(BaseModel):
    asset_id: str
    asset_tag: str
    asset_name: str
    asset_class: AssetClassEnum
    organization: str = "MRPL"
    refinery: str = "Mangalore Refinery"
    process_unit: str = "CDU-II"
    parent_asset_tag: Optional[str] = None
    service_description: str = "General Hydrocarbon Service"
    status: AssetStatusEnum = AssetStatusEnum.IN_SERVICE
    design_code: Optional[str] = "API 610 / ASME VIII"
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    commissioning_date: Optional[str] = "2020-01-01"
    class_attributes: Dict[str, Any] = Field(default_factory=dict)
    components: List[AssetComponent] = Field(default_factory=list)
    inspection_locations: List[InspectionLocation] = Field(default_factory=list)
    documents_manifest: List[str] = Field(default_factory=list)  # list of doc_ids
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    revision: int = 1
    data_status: str = "DEMONSTRATION / CURATED TEST DATA"

    @property
    def tag(self) -> str:
        return self.asset_tag

    @property
    def name(self) -> str:
        return self.asset_name


class AssetCreateRequest(BaseModel):
    asset_tag: Optional[str] = None
    tag: Optional[str] = None
    asset_name: Optional[str] = None
    name: Optional[str] = None
    asset_class: AssetClassEnum
    process_unit: str = "CDU-II"
    refinery: str = "Mangalore Refinery"
    parent_asset_tag: Optional[str] = None
    service_description: Optional[str] = None
    service: Optional[str] = None
    location: Optional[str] = None
    status: AssetStatusEnum = AssetStatusEnum.IN_SERVICE
    design_code: Optional[str] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    commissioning_date: Optional[str] = None
    design_pressure_bar: Optional[float] = None
    design_temperature_c: Optional[float] = None
    operating_pressure_bar: Optional[float] = None
    operating_temperature_c: Optional[float] = None
    material_of_construction: Optional[str] = None
    class_attributes: Dict[str, Any] = Field(default_factory=dict)
    initial_components: List[str] = Field(default_factory=list)
    initial_inspection_locations: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.asset_tag and self.tag:
            self.asset_tag = self.tag
        if not self.tag and self.asset_tag:
            self.tag = self.asset_tag
        if not self.asset_name and self.name:
            self.asset_name = self.name
        if not self.name and self.asset_name:
            self.name = self.asset_name
        if not self.service_description and self.service:
            self.service_description = self.service


class AssetDocumentUploadRequest(BaseModel):
    document_id: Optional[str] = None
    document_number: Optional[str] = None
    title: str
    category: str = "03_Inspection_Reports"
    document_type: str = "Inspection Reports"
    date: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d"))
    revision: str = "Rev 0"
    section: str = "3.0 In-Service Inspection Findings"
    source_section: Optional[str] = None
    page_number: int = 1
    source_page: Optional[Any] = None
    source_span: Optional[str] = None
    content: str
    authority: str = "Authority Level A"
    approval_status: str = "APPROVED_FOR_SERVICE"
    author: Optional[str] = None
    measurements: List[EngineeringMeasurement] = Field(default_factory=list)
    extracted_measurements: List[Dict[str, Any]] = Field(default_factory=list)
    component: Optional[str] = None
    inspection_location: Optional[str] = None
    inspection_location_tag: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.document_id and self.document_number:
            self.document_id = self.document_number
        if not self.section and self.source_section:
            self.section = self.source_section
        if not self.inspection_location and self.inspection_location_tag:
            self.inspection_location = self.inspection_location_tag


class HierarchyNode(BaseModel):
    id: str
    label: str
    node_type: str  # ORG, REFINERY, PROCESS_UNIT, ASSET_CLASS, ASSET, COMPONENT, LOCATION, OBSERVATION, MEASUREMENT, PROVENANCE
    asset_class: Optional[str] = None
    asset_tag: Optional[str] = None
    status: Optional[str] = None
    children_count: int = 0
    children: List["HierarchyNode"] = Field(default_factory=list)

    @property
    def node_id(self) -> str:
        return self.id


class AssetAuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"AUD-{int(time.time()*1000)%1000000:06d}")
    asset_id: str
    asset_tag: str
    action: str  # ASSET_CREATED, DOCUMENT_ATTACHED, COMPONENT_ADDED, LOCATION_ADDED, METADATA_UPDATED
    performed_by: str = "MRPL_OPERATIONS_USER"
    timestamp: float = Field(default_factory=time.time)
    details: Dict[str, Any] = Field(default_factory=dict)


class AssetDossier(BaseModel):
    asset: Asset
    hierarchy_path: str  # MRPL -> Mangalore Refinery -> CDU-II -> PUMP -> P-201
    total_documents: int = 0
    categories_covered: List[str] = Field(default_factory=list)
    documents_by_category: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    observations: List[EngineeringObservation] = Field(default_factory=list)
    recent_measurements: List[EngineeringMeasurement] = Field(default_factory=list)
    audit_trail: List[AssetAuditRecord] = Field(default_factory=list)
    summary: str

    @property
    def documents(self) -> List[Dict[str, Any]]:
        flat: List[Dict[str, Any]] = []
        for dlist in self.documents_by_category.values():
            flat.extend(dlist)
        return flat
