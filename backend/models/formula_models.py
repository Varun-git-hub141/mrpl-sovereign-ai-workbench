from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field


class FormulaDefinition(BaseModel):
    formula_id: str = Field(..., description="Unique alphanumeric identifier (e.g. CORR-001, HYD-004)")
    name: str = Field(..., description="Standard engineering formula title")
    category: str = Field(..., description="Category: Corrosion, Pressure Vessels, Piping, Rotating Equipment, Heat Transfer, Thermodynamics, General Engineering")
    description: str = Field(..., description="Technical engineering definition and scope")
    equation: str = Field(..., description="Mathematical representation string")
    equation_display: str = Field(..., description="Human-readable formula string for display")
    variables: Dict[str, str] = Field(default_factory=dict, description="Variable symbol to descriptive name mapping")
    units: Dict[str, str] = Field(default_factory=dict, description="Standard units for variables and output")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="Expected inputs with types and default units")
    output: Dict[str, str] = Field(default_factory=dict, description="Output variable and unit")
    applicable_equipment: List[str] = Field(default_factory=list, description="List of compatible equipment types")
    applicable_service: List[str] = Field(default_factory=list, description="Compatible process fluids/services")
    applicable_conditions: str = Field("Standard refinery operating envelope", description="Applicable operating range")
    limitations: List[str] = Field(default_factory=list, description="Engineering constraints and invalid scenarios")
    assumptions: List[str] = Field(default_factory=list, description="Underlying physics/engineering assumptions")
    required_data: List[str] = Field(default_factory=list, description="Mandatory input parameters")
    optional_data: List[str] = Field(default_factory=list, description="Optional parameters")
    standard_reference: str = Field("API 570 / ASME B31.3", description="Governing engineering standard code")
    source_type: str = Field("GOVERNING_STANDARD", description="GOVERNING_STANDARD, RECOGNIZED_PRINCIPLE, or REQUIRES_ENGINEERING_VALIDATION")
    validation_rules: List[str] = Field(default_factory=list, description="Validation constraints (e.g. input > 0, t_curr <= t_orig)")
    unit_conversion_rules: Dict[str, str] = Field(default_factory=dict, description="Unit normalization instructions")
    risk_level: str = Field("medium", description="Operational risk level (low, medium, high)")
    engineering_review_required: bool = Field(False, description="Flag for mandatory Chief Engineer review")
    confidence: float = Field(0.99, ge=0.0, le=1.0, description="Formula deterministic confidence")
    status: str = Field("VALIDATED", description="VALIDATED, EXPERIMENTAL, or REQUIRES_VALIDATION")


class FormulaCalculationRequest(BaseModel):
    formula_id: str
    inputs: Dict[str, float]
    input_units: Optional[Dict[str, str]] = None
    equipment_tag: Optional[str] = None
    equipment_type: Optional[str] = None


class FormulaCalculationResult(BaseModel):
    formula_id: str
    name: str
    category: str
    status: str  # "SUCCESS", "INSUFFICIENT_DATA", "INCOMPATIBLE_UNITS", "INVALID_INPUT"
    result: Optional[float] = None
    result_unit: Optional[str] = None
    formula_display: str = ""
    inputs_applied: Dict[str, Any] = Field(default_factory=dict)
    missing_inputs: List[str] = Field(default_factory=list)
    units_applied: Dict[str, str] = Field(default_factory=dict)
    standard_reference: str = ""
    engineering_notes: str = ""
    source: str = "deterministic_formula_engine"
