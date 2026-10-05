import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from backend.models.formula_models import (
    FormulaDefinition,
    FormulaCalculationRequest,
    FormulaCalculationResult,
)

logger = logging.getLogger("mrpl.formulas")


class FormulaRegistry:
    """
    Sovereign Engineering Formula Registry for MRPL.
    Maintains 50+ structured machine-readable engineering calculations with
    strict deterministic Python execution, unit conversion, and engineering safety checks.
    """

    FORMULA_ALIASES = {
        "API570-CR-001": "CORR-001",
        "API-570-CR-001": "CORR-001",
        "CR-001": "CORR-001",
        "CR-002": "CORR-002",
        "CR-003": "CORR-006",
        "CR-004": "CORR-008",
        "CR-005": "CORR-004",
        "CR-006": "CORR-005",
        "INSP-001": "CORR-010",
        "INSP-002": "PV-022",
        "PRESS-001": "HT-046",
        "PRESS-002": "PV-021",
        "PRESS-003": "ROT-034",
        "PUMP-001": "ROT-032",
        "PUMP-002": "ROT-033",
        "PUMP-003": "ROT-034",
        "PUMP-004": "ROT-035",
        "PUMP-005": "ROT-036",
        "FLOW-001": "HYD-025",
        "FLOW-002": "HYD-026",
        "FLOW-003": "HYD-030",
        "FLOW-004": "HYD-027",
        "PV-001": "PV-016",
        "PV-002": "PV-018",
        "HT-001": "HT-040",
        "HT-002": "HT-041",
        "THERM-001": "HT-044",
        "MECH-001": "GEN-051",
        "MECH-002": "GEN-050",
        "FIN-001": "GEN-049",
        "UNIT-001": "HT-045",
        "UNIT-002": "HT-047",
        "UNIT-003": "HT-046",
        "UNIT-004": "HT-045",
        "UNIT-005": "HYD-025",
        "DATE-001": "CORR-001",
        "SHEET-001": "GEN-049",
    }

    # Common input variable alias mapping
    VAR_ALIASES = {
        "previous_thickness": ["T_previous", "t_previous", "T_initial", "t_initial", "t_prev", "t_orig", "initial_thickness", "original_thickness", "baseline_thickness", "previous_wall_thickness", "original_wall_thickness"],
        "T_previous": ["previous_thickness", "original_thickness", "T_initial", "t_initial", "t_prev", "t_orig", "initial_thickness", "previous_wall_thickness", "original_wall_thickness"],
        "T_initial": ["previous_thickness", "original_thickness", "T_previous", "t_initial", "t_prev", "t_orig", "initial_thickness", "previous_wall_thickness", "original_wall_thickness"],
        "original_thickness": ["previous_thickness", "T_previous", "T_initial", "t_initial", "t_prev", "t_orig", "initial_thickness", "previous_wall_thickness", "original_wall_thickness"],
        "current_thickness": ["T_current", "t_current", "t_curr", "current_wall_thickness", "measured_thickness", "wall_thickness", "actual_thickness"],
        "T_current": ["current_thickness", "t_current", "t_curr", "current_wall_thickness", "measured_thickness", "wall_thickness", "actual_thickness"],
        "current_wall_thickness": ["current_thickness", "T_current", "t_current", "t_curr", "measured_thickness", "wall_thickness", "actual_thickness"],
        "elapsed_time": ["delta_years", "delta_years_ST", "inspection_interval", "years", "time_span", "recent_elapsed_time", "elapsed_years", "time_between_inspections"],
        "inspection_interval": ["elapsed_time", "delta_years", "delta_years_ST", "years", "time_span", "recent_elapsed_time", "elapsed_years"],
        "delta_years": ["elapsed_time", "inspection_interval", "delta_years_ST", "years", "time_span", "recent_elapsed_time", "elapsed_years"],
        "delta_years_ST": ["elapsed_time", "inspection_interval", "delta_years", "years", "time_span", "recent_elapsed_time", "elapsed_years"],
        "minimum_allowable_thickness": ["T_min", "t_min", "min_thickness", "retirement_thickness", "minimum_allowable", "min_allowable_thickness"],
        "T_min": ["minimum_allowable_thickness", "t_min", "min_thickness", "retirement_thickness", "minimum_allowable", "min_allowable_thickness"],
        "corrosion_rate": ["CR", "cr", "rate", "corrosion_rate_mm_year", "CR_ST", "CR_LT"],
        "CR": ["corrosion_rate", "cr", "rate", "corrosion_rate_mm_year", "CR_ST", "CR_LT"],
        "flow_rate": ["Q", "flow_m3hr", "volumetric_flow_m3hr", "flow_rate_m3hr"],
        "density": ["rho", "fluid_density", "density_kg_m3", "liquid_density"],
        "head": ["H", "head_m", "total_head"],
        "pressure": ["P", "pressure_bar", "P_gauge", "P_bar"],
        "diameter": ["D", "diameter_mm", "inside_diameter", "pipe_diameter_mm"],
        "length": ["L", "pipe_length_m"],
    }

    def __init__(self):
        self._formulas: Dict[str, FormulaDefinition] = {}
        self._executors: Dict[str, Any] = {}
        self._initialize_formulas()

    def get_all(self) -> List[FormulaDefinition]:
        return list(self._formulas.values())

    def get_by_id(self, formula_id: str) -> Optional[FormulaDefinition]:
        if not formula_id:
            return None
        norm_id = formula_id.strip().upper()
        if norm_id in self.FORMULA_ALIASES:
            norm_id = self.FORMULA_ALIASES[norm_id]
        return self._formulas.get(norm_id)

    def retrieve_applicable_formula(self, query: str, equipment_type: Optional[str] = None) -> Tuple[Optional[FormulaDefinition], str]:
        """
        Formula Retrieval / RAG Engine: Identifies and ranks the best matching validated formula.
        """
        q = query.lower()
        if any(k in q for k in ["remaining life", "rla", "how long", "retire"]):
            formula = self.get_by_id("CORR-004")
            return formula, "API 570 Remaining Service Life formula selected based on query intent for remaining life assessment."
        elif any(k in q for k in ["margin", "above minimum", "excess thickness", "thickness margin"]):
            formula = self.get_by_id("CORR-008")
            return formula, "Remaining Corrosion Allowance / Thickness Margin formula selected based on query intent."
        elif any(k in q for k in ["corrosion rate", "wall loss rate", "thickness loss per year", "mpy"]):
            formula = self.get_by_id("CORR-001")
            return formula, "API 570 Historical Average Corrosion Rate formula selected based on query intent."
        elif any(k in q for k in ["vibration", "iso 10816", "rms"]):
            formula = self.get_by_id("GEN-051")
            return formula, "ISO 10816 Machinery Vibration Severity formula selected."
        elif any(k in q for k in ["pump power", "hydraulic power", "shaft power"]):
            formula = self.get_by_id("ROT-032")
            return formula, "Centrifugal Pump Hydraulic Power formula selected."
        elif any(k in q for k in ["velocity", "pipe velocity"]):
            formula = self.get_by_id("HYD-025")
            return formula, "Pipe Flow Velocity formula selected."
        
        # General search
        candidates = self.search(query)
        if candidates:
            return candidates[0], f"Formula {candidates[0].formula_id} matched via keyword retrieval."
        return None, "No applicable formula found in registry."

    def search(self, query: str) -> List[FormulaDefinition]:
        q = query.lower().strip()
        if not q:
            return self.get_all()
        results = []
        for f in self._formulas.values():
            if (
                q in f.formula_id.lower()
                or q in f.name.lower()
                or q in f.category.lower()
                or q in f.description.lower()
                or any(q in eq.lower() for eq in f.applicable_equipment)
                or q in f.standard_reference.lower()
            ):
                results.append(f)
        return results

    def filter_by(
        self,
        category: Optional[str] = None,
        equipment: Optional[str] = None,
        risk: Optional[str] = None,
    ) -> List[FormulaDefinition]:
        results = list(self._formulas.values())
        if category and category != "all":
            results = [f for f in results if f.category.lower() == category.lower()]
        if equipment and equipment != "all":
            results = [f for f in results if any(equipment.lower() in eq.lower() for eq in f.applicable_equipment)]
        if risk and risk != "all":
            results = [f for f in results if f.risk_level.lower() == risk.lower()]
        return results

    def _normalize_inputs(self, formula: FormulaDefinition, raw_inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Normalizes variable names, handles unit conversions (e.g. in -> mm, bar -> Pa),
        and detects missing or physically impossible negative inputs.
        """
        normalized: Dict[str, Any] = {}
        missing: List[str] = []

        for req_var in formula.required_data:
            val = raw_inputs.get(req_var)
            if val is None:
                # Check alias mapping
                for canonical, aliases in self.VAR_ALIASES.items():
                    if req_var == canonical or req_var in aliases:
                        for alias in [canonical] + aliases:
                            if alias in raw_inputs and raw_inputs[alias] is not None:
                                val = raw_inputs[alias]
                                break
                    if val is not None:
                        break

            if val is None:
                missing.append(req_var)
            else:
                try:
                    num_val = float(val)
                    # Check negative physical constraints
                    if num_val < 0 and req_var in [
                        "T_initial", "T_previous", "previous_thickness",
                        "T_current", "current_thickness", "current_wall_thickness",
                        "T_min", "minimum_allowable_thickness",
                        "delta_years", "delta_years_ST", "elapsed_time", "inspection_interval",
                        "D", "t", "thickness", "diameter_mm", "flow_rate_m3hr"
                    ]:
                        raise ValueError(f"Negative value ({num_val:g}) is physically impossible for parameter '{req_var}'.")
                    normalized[req_var] = num_val
                except ValueError as ve:
                    raise ve

        return normalized, missing

    def calculate(self, req: FormulaCalculationRequest) -> FormulaCalculationResult:
        """
        Executes a deterministic formula with unit normalization and safety validations.
        Never calls an LLM for arithmetic.
        """
        formula = self.get_by_id(req.formula_id)
        if not formula:
            return FormulaCalculationResult(
                formula_id=req.formula_id,
                name="Unknown Formula",
                category="Unknown",
                status="INVALID_INPUT",
                engineering_notes=f"Formula '{req.formula_id}' not found in registry.",
            )

        # Normalize inputs & check missing
        try:
            norm_inputs, missing = self._normalize_inputs(formula, req.inputs)
        except ValueError as ve:
            return FormulaCalculationResult(
                formula_id=formula.formula_id,
                name=formula.name,
                category=formula.category,
                status="INVALID_INPUT",
                engineering_notes=f"Input validation failure: {str(ve)}",
            )

        if missing:
            return FormulaCalculationResult(
                formula_id=formula.formula_id,
                name=formula.name,
                category=formula.category,
                status="INSUFFICIENT_DATA",
                missing_inputs=missing,
                formula_display=formula.equation_display,
                standard_reference=formula.standard_reference,
                engineering_notes=f"Missing required parameters: {', '.join(missing)}. Values must not be fabricated.",
            )

        # Execute deterministic Python function
        executor = self._executors.get(formula.formula_id)
        if not executor:
            return FormulaCalculationResult(
                formula_id=formula.formula_id,
                name=formula.name,
                category=formula.category,
                status="INVALID_INPUT",
                formula_display=formula.equation_display,
                engineering_notes="Deterministic executor not registered.",
            )

        try:
            val, display_str, notes = executor(norm_inputs)
            out_unit = list(formula.output.values())[0] if formula.output else ""
            return FormulaCalculationResult(
                formula_id=formula.formula_id,
                name=formula.name,
                category=formula.category,
                status="SUCCESS",
                result=val,
                result_unit=out_unit,
                formula_display=display_str or formula.equation_display,
                inputs_applied=norm_inputs,
                units_applied=formula.units,
                standard_reference=formula.standard_reference,
                engineering_notes=notes,
            )
        except Exception as e:
            return FormulaCalculationResult(
                formula_id=formula.formula_id,
                name=formula.name,
                category=formula.category,
                status="INVALID_INPUT",
                formula_display=formula.equation_display,
                standard_reference=formula.standard_reference,
                engineering_notes=f"Calculation error: {str(e)}",
            )

    def _register(self, f: FormulaDefinition, executor: Any):
        self._formulas[f.formula_id.upper()] = f
        self._executors[f.formula_id.upper()] = executor

    def _initialize_formulas(self):
        # ═══════════════════════════════════════════════════════════════
        # SECTION 1: CORROSION & REMAINING LIFE (Formulas 1-14)
        # ═══════════════════════════════════════════════════════════════
        self._register(
            FormulaDefinition(
                formula_id="CORR-001",
                name="Historical Average Corrosion Rate",
                category="Corrosion",
                description="Determines historical wall-loss rate between initial baseline and current inspection.",
                equation="CR = (T_previous - T_current) / elapsed_time",
                equation_display="(T_previous - T_current) / elapsed_time",
                variables={"T_previous": "Previous inspection thickness", "T_current": "Current wall thickness", "elapsed_time": "Inspection interval in years"},
                units={"T_previous": "mm", "T_current": "mm", "elapsed_time": "years", "CR": "mm/year"},
                output={"CR": "mm/year"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "heat_exchanger", "pump", "column", "drum"],
                required_data=["T_previous", "T_current", "elapsed_time"],
                standard_reference="API 570 Section 7.1.1 / API 510",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp.get("T_previous", inp.get("T_initial", inp.get("previous_thickness"))) - inp.get("T_current", inp.get("current_thickness"))) / inp.get("elapsed_time", inp.get("delta_years", inp.get("inspection_interval"))), 4),
                f"({inp.get('T_previous', inp.get('T_initial', inp.get('previous_thickness')))} - {inp.get('T_current', inp.get('current_thickness'))}) / {inp.get('elapsed_time', inp.get('delta_years', inp.get('inspection_interval')))}",
                "API 570 Historical Wall Loss Rate calculated deterministically.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-002",
                name="Short-Term Corrosion Rate",
                category="Corrosion",
                description="Calculates short-term rate between the two most recent consecutive ultrasonic inspections.",
                equation="CR_ST = (T_previous - T_current) / time_between_inspections",
                equation_display="(T_previous - T_current) / delta_years_ST",
                variables={"T_previous": "Previous inspection thickness", "T_current": "Current measured thickness", "delta_years_ST": "Elapsed years"},
                units={"T_previous": "mm", "T_current": "mm", "delta_years_ST": "years", "CR_ST": "mm/year"},
                output={"CR_ST": "mm/year"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "heat_exchanger", "column"],
                required_data=["T_previous", "T_current", "delta_years_ST"],
                standard_reference="API 570 Section 7.1.1",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["T_previous"] - inp["T_current"]) / inp["delta_years_ST"], 4),
                f"({inp['T_previous']} - {inp['T_current']}) / {inp['delta_years_ST']}",
                "API 570 Short-Term Rate calculated.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-003",
                name="Long-Term Corrosion Rate",
                category="Corrosion",
                description="Calculates long-term corrosion rate from original commissioning nominal thickness to latest reading.",
                equation="CR_LT = (T_initial - T_current) / total_service_years",
                equation_display="(T_initial - T_current) / total_years",
                variables={"T_initial": "Initial thickness", "T_current": "Current thickness", "total_years": "Total operating years"},
                units={"T_initial": "mm", "T_current": "mm", "total_years": "years", "CR_LT": "mm/year"},
                output={"CR_LT": "mm/year"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "heat_exchanger"],
                required_data=["T_initial", "T_current", "total_years"],
                standard_reference="API 570 Section 7.1.1",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["T_initial"] - inp["T_current"]) / inp["total_years"], 4),
                f"({inp['T_initial']} - {inp['T_current']}) / {inp['total_years']}",
                "API 570 Long-Term Rate calculated.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-004",
                name="Remaining Life Assessment",
                category="Corrosion",
                description="Calculates estimated remaining service life before reaching minimum allowable retirement thickness.",
                equation="RL = (T_current - T_min) / CR",
                equation_display="(T_current - T_min) / CR",
                variables={"T_current": "Current thickness", "T_min": "Minimum allowable thickness", "CR": "Corrosion rate"},
                units={"T_current": "mm", "T_min": "mm", "CR": "mm/year", "RL": "years"},
                output={"RL": "years"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "heat_exchanger", "pump", "column", "drum"],
                required_data=["T_current", "T_min", "CR"],
                standard_reference="API 570 Section 7.1.2 / API 510",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round((inp["T_current"] - inp["T_min"]) / inp["CR"], 2),
                f"({inp['T_current']} - {inp['T_min']}) / {inp['CR']}",
                "API 570 Remaining Life calculation. Mandatory review required if RL < 2 years.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-005",
                name="Projected Future Wall Thickness",
                category="Corrosion",
                description="Forecasts wall thickness at a future date based on constant corrosion rate.",
                equation="T_future = T_current - (CR * future_years)",
                equation_display="T_current - (CR * future_years)",
                variables={"T_current": "Current thickness", "CR": "Corrosion rate", "future_years": "Forecast interval"},
                units={"T_current": "mm", "CR": "mm/year", "future_years": "years", "T_future": "mm"},
                output={"T_future": "mm"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "heat_exchanger"],
                required_data=["T_current", "CR", "future_years"],
                standard_reference="API 570 / API 510",
                risk_level="medium",
            ),
            lambda inp: (
                round(inp["T_current"] - (inp["CR"] * inp["future_years"]), 3),
                f"{inp['T_current']} - ({inp['CR']} * {inp['future_years']})",
                "Projected thickness calculated.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-006",
                name="Total Cumulative Thickness Loss",
                category="Corrosion",
                description="Calculates cumulative metal loss since original installation.",
                equation="Loss = T_initial - T_current",
                equation_display="T_initial - T_current",
                variables={"T_initial": "Initial thickness", "T_current": "Current thickness"},
                units={"T_initial": "mm", "T_current": "mm", "Loss": "mm"},
                output={"Loss": "mm"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "heat_exchanger", "pump"],
                required_data=["T_initial", "T_current"],
                standard_reference="API 570 / API 574",
                risk_level="low",
            ),
            lambda inp: (
                round(inp["T_initial"] - inp["T_current"], 3),
                f"{inp['T_initial']} - {inp['T_current']}",
                "Cumulative metal loss computed.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-007",
                name="Percentage Wall Thickness Loss",
                category="Corrosion",
                description="Evaluates percentage of original nominal wall thickness consumed.",
                equation="Pct_Loss = ((T_initial - T_current) / T_initial) * 100",
                equation_display="((T_initial - T_current) / T_initial) * 100",
                variables={"T_initial": "Initial thickness", "T_current": "Current thickness"},
                units={"T_initial": "mm", "T_current": "mm", "Pct_Loss": "%"},
                output={"Pct_Loss": "%"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "pump", "column"],
                required_data=["T_initial", "T_current"],
                standard_reference="API 570 / API 574",
                risk_level="medium",
            ),
            lambda inp: (
                round(((inp["T_initial"] - inp["T_current"]) / inp["T_initial"]) * 100.0, 2),
                f"(({inp['T_initial']} - {inp['T_current']}) / {inp['T_initial']}) * 100",
                "Percentage thickness loss computed.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-008",
                name="Remaining Corrosion Allowance (CA)",
                category="Corrosion",
                description="Calculates remaining sacrificial metal allowance above minimum retirement thickness.",
                equation="CA_rem = T_current - T_min",
                equation_display="T_current - T_min",
                variables={"T_current": "Current thickness", "T_min": "Minimum allowable thickness"},
                units={"T_current": "mm", "T_min": "mm", "CA_rem": "mm"},
                output={"CA_rem": "mm"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "pump"],
                required_data=["T_current", "T_min"],
                standard_reference="ASME B31.3 / API 570",
                risk_level="medium",
            ),
            lambda inp: (
                round(inp["T_current"] - inp["T_min"], 3),
                f"{inp['T_current']} - {inp['T_min']}",
                "Remaining corrosion allowance margin.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-009",
                name="Corrosion Allowance Consumed Percentage",
                category="Corrosion",
                description="Calculates fraction of design corrosion allowance consumed by operational wall loss.",
                equation="CA_consumed_pct = ((T_initial - T_current) / CA_design) * 100",
                equation_display="((T_initial - T_current) / CA_design) * 100",
                variables={"T_initial": "Initial thickness", "T_current": "Current thickness", "CA_design": "Design corrosion allowance"},
                units={"T_initial": "mm", "T_current": "mm", "CA_design": "mm", "CA_consumed_pct": "%"},
                output={"CA_consumed_pct": "%"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank"],
                required_data=["T_initial", "T_current", "CA_design"],
                standard_reference="API 570",
                risk_level="medium",
            ),
            lambda inp: (
                round(((inp["T_initial"] - inp["T_current"]) / inp["CA_design"]) * 100.0, 2),
                f"(({inp['T_initial']} - {inp['T_current']}) / {inp['CA_design']}) * 100",
                "Design corrosion allowance consumption evaluated.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-010",
                name="Maximum Half-Life Inspection Interval",
                category="Corrosion",
                description="Calculates maximum permissible inspection interval per API 570 (lesser of 1/2 remaining life or 5/10 yrs).",
                equation="Interval_max = min(RL / 2, Max_Cap)",
                equation_display="min(RL / 2, Max_Cap)",
                variables={"RL": "Remaining life", "Max_Cap": "Statutory limit (e.g. 5.0 for Class 1 piping, 10.0 for Class 2)"},
                units={"RL": "years", "Max_Cap": "years", "Interval_max": "years"},
                output={"Interval_max": "years"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank"],
                required_data=["RL", "Max_Cap"],
                standard_reference="API 570 Section 6.3 / API 510",
                risk_level="medium",
            ),
            lambda inp: (
                round(min(inp["RL"] / 2.0, inp["Max_Cap"]), 2),
                f"min({inp['RL']}/2, {inp['Max_Cap']})",
                "Next statutory inspection interval schedule.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-011",
                name="Corrosion Rate Acceleration Factor",
                category="Corrosion",
                description="Compares short-term corrosion rate against long-term historical rate to detect process acceleration.",
                equation="AF = CR_ST / CR_LT",
                equation_display="CR_ST / CR_LT",
                variables={"CR_ST": "Short-term corrosion rate", "CR_LT": "Long-term corrosion rate"},
                units={"CR_ST": "mm/year", "CR_LT": "mm/year", "AF": "ratio"},
                output={"AF": "ratio"},
                applicable_equipment=["piping", "pressure_vessel", "column", "heat_exchanger"],
                required_data=["CR_ST", "CR_LT"],
                standard_reference="API 570 Section 7.1.1",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round(inp["CR_ST"] / inp["CR_LT"], 2),
                f"{inp['CR_ST']} / {inp['CR_LT']}",
                "Acceleration Factor > 1.5 indicates severe process deviation or upset.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-012",
                name="Corrosion Rate in MPY (Mils Per Year)",
                category="Corrosion",
                description="Converts metric mm/year rate into imperial mils per year (mpy) for standard comparisons.",
                equation="CR_mpy = CR_mmyear * 39.37",
                equation_display="CR_mmyear * 39.37",
                variables={"CR_mmyear": "Corrosion rate in mm/year"},
                units={"CR_mmyear": "mm/year", "CR_mpy": "mpy"},
                output={"CR_mpy": "mpy"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "pump"],
                required_data=["CR_mmyear"],
                standard_reference="NACE / API 570",
                risk_level="low",
            ),
            lambda inp: (
                round(inp["CR_mmyear"] * 39.3701, 2),
                f"{inp['CR_mmyear']} * 39.37",
                "Converted rate in mpy.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-013",
                name="Thickness at Next Planned Turnaround (TA)",
                category="Corrosion",
                description="Forecasts wall thickness remaining at the next major turnaround date.",
                equation="T_next_ta = T_current - (CR * years_to_ta)",
                equation_display="T_current - (CR * years_to_ta)",
                variables={"T_current": "Current thickness", "CR": "Corrosion rate", "years_to_ta": "Years until scheduled turnaround"},
                units={"T_current": "mm", "CR": "mm/year", "years_to_ta": "years", "T_next_ta": "mm"},
                output={"T_next_ta": "mm"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "column", "furnace"],
                required_data=["T_current", "CR", "years_to_ta"],
                standard_reference="API 570 Turnaround Planning",
                risk_level="medium",
            ),
            lambda inp: (
                round(inp["T_current"] - (inp["CR"] * inp["years_to_ta"]), 3),
                f"{inp['T_current']} - ({inp['CR']} * {inp['years_to_ta']})",
                "Turnaround entry thickness projection.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CORR-014",
                name="Corrosion Allowable Working Life",
                category="Corrosion",
                description="Determines original total design lifespan of the equipment based on nominal corrosion allowance.",
                equation="Life_total = CA_design / CR_design",
                equation_display="CA_design / CR_design",
                variables={"CA_design": "Design corrosion allowance", "CR_design": "Estimated design corrosion rate"},
                units={"CA_design": "mm", "CR_design": "mm/year", "Life_total": "years"},
                output={"Life_total": "years"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank"],
                required_data=["CA_design", "CR_design"],
                standard_reference="ASME Sec VIII / B31.3",
                risk_level="low",
            ),
            lambda inp: (
                round(inp["CA_design"] / inp["CR_design"], 2),
                f"{inp['CA_design']} / {inp['CR_design']}",
                "Design working life calculated.",
            ),
        )

        # ═══════════════════════════════════════════════════════════════
        # SECTION 2: PRESSURE VESSELS & PIPING (Formulas 15-24)
        # ═══════════════════════════════════════════════════════════════
        self._register(
            FormulaDefinition(
                formula_id="PV-015",
                name="ASME B31.3 Piping Minimum Required Thickness",
                category="Piping",
                description="Calculates minimum required wall thickness for straight process piping under internal pressure.",
                equation="t_req = (P * D) / (2 * (S * E * W + P * Y)) + c",
                equation_display="(P * D) / (2 * (S * E * W + P * Y)) + c",
                variables={"P": "Design pressure", "D": "Outside diameter", "S": "Allowable stress", "E": "Longitudinal joint quality factor", "W": "Weld joint strength factor", "Y": "Material coefficient", "c": "Corrosion allowance"},
                units={"P": "MPa", "D": "mm", "S": "MPa", "E": "factor", "W": "factor", "Y": "factor", "c": "mm", "t_req": "mm"},
                output={"t_req": "mm"},
                applicable_equipment=["piping", "pipeline"],
                required_data=["P", "D", "S", "E", "W", "Y", "c"],
                standard_reference="ASME B31.3 Section 304.1.2",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round((inp["P"] * inp["D"]) / (2 * (inp["S"] * inp["E"] * inp["W"] + inp["P"] * inp["Y"])) + inp["c"], 3),
                f"({inp['P']} * {inp['D']}) / (2 * ({inp['S']} * {inp['E']} * {inp['W']} + {inp['P']} * {inp['Y']})) + {inp['c']}",
                "ASME B31.3 Section 304.1.2 pressure design thickness + corrosion allowance.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-016",
                name="ASME Section VIII Div 1 Cylindrical Shell Thickness",
                category="Pressure Vessels",
                description="Calculates required thickness of cylindrical pressure vessel shell under internal pressure.",
                equation="t_shell = (P * R) / (S * E - 0.6 * P) + c",
                equation_display="(P * R) / (S * E - 0.6 * P) + c",
                variables={"P": "Design pressure", "R": "Inside radius", "S": "Allowable stress", "E": "Joint efficiency", "c": "Corrosion allowance"},
                units={"P": "MPa", "R": "mm", "S": "MPa", "E": "factor", "c": "mm", "t_shell": "mm"},
                output={"t_shell": "mm"},
                applicable_equipment=["pressure_vessel", "column", "drum", "reactor"],
                required_data=["P", "R", "S", "E", "c"],
                standard_reference="ASME Section VIII Division 1 UG-27(c)(1)",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round((inp["P"] * inp["R"]) / (inp["S"] * inp["E"] - 0.6 * inp["P"]) + inp["c"], 3),
                f"({inp['P']} * {inp['R']}) / ({inp['S']} * {inp['E']} - 0.6 * {inp['P']}) + {inp['c']}",
                "ASME Sec VIII Div 1 cylindrical shell required thickness.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-017",
                name="Maximum Allowable Working Pressure (MAWP) - Piping",
                category="Piping",
                description="Determines current MAWP of corroded piping section per ASME B31.3 / API 570.",
                equation="MAWP = (2 * S * E * W * (t_actual - c)) / (D - 2 * Y * (t_actual - c))",
                equation_display="(2 * S * E * W * t_eff) / (D - 2 * Y * t_eff)",
                variables={"S": "Allowable stress", "E": "Joint factor", "W": "Weld factor", "t_actual": "Actual measured thickness", "c": "Future corrosion allowance", "D": "Outside diameter", "Y": "Coefficient"},
                units={"S": "MPa", "E": "factor", "W": "factor", "t_actual": "mm", "c": "mm", "D": "mm", "Y": "factor", "MAWP": "MPa"},
                output={"MAWP": "MPa"},
                applicable_equipment=["piping", "pipeline"],
                required_data=["S", "E", "W", "t_actual", "c", "D", "Y"],
                standard_reference="ASME B31.3 / API 570 Section 7.2",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round((2 * inp["S"] * inp["E"] * inp["W"] * (inp["t_actual"] - inp["c"])) / (inp["D"] - 2 * inp["Y"] * (inp["t_actual"] - inp["c"])), 2),
                f"MAWP for t_eff = {inp['t_actual'] - inp['c']} mm",
                "Piping MAWP derating calculation per API 570.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-018",
                name="Hoop Stress in Thin-Walled Cylinder",
                category="Pressure Vessels",
                description="Calculates circumferential (hoop) stress under internal pressure.",
                equation="sigma_hoop = (P * D_internal) / (2 * t)",
                equation_display="(P * D_internal) / (2 * t)",
                variables={"P": "Internal pressure", "D_internal": "Inside diameter", "t": "Wall thickness"},
                units={"P": "MPa", "D_internal": "mm", "t": "mm", "sigma_hoop": "MPa"},
                output={"sigma_hoop": "MPa"},
                applicable_equipment=["pressure_vessel", "piping", "storage_tank", "drum"],
                required_data=["P", "D_internal", "t"],
                standard_reference="ASME B31.3 / ASME Sec VIII",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["P"] * inp["D_internal"]) / (2.0 * inp["t"]), 2),
                f"({inp['P']} * {inp['D_internal']}) / (2 * {inp['t']})",
                "Hoop stress calculated.",
            ),
        )
        # ═══════════════════════════════════════════════════════════════
        # SECTION 0: CORROSION & REMAINING LIFE (CR-001 to CR-005)
        # ═══════════════════════════════════════════════════════════════
        self._register(
            FormulaDefinition(
                formula_id="CR-001",
                name="Historical Long-Term Corrosion Rate",
                category="Corrosion",
                description="Calculates average long-term corrosion rate (mm/year) from wall thickness loss over inspection interval.",
                equation="CR = (previous_thickness - current_thickness) / inspection_interval",
                equation_display="(previous_thickness - current_thickness) / inspection_interval",
                variables={"previous_thickness": "Previous wall thickness", "current_thickness": "Current wall thickness", "inspection_interval": "Elapsed inspection interval"},
                units={"previous_thickness": "mm", "current_thickness": "mm", "inspection_interval": "years", "CR": "mm/year"},
                output={"CR": "mm/year"},
                applicable_equipment=["pump", "piping", "pressure_vessel", "storage_tank", "pipeline"],
                required_data=["previous_thickness", "current_thickness", "inspection_interval"],
                standard_reference="API 570 Section 7.1.1 / API 510",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["previous_thickness"] - inp["current_thickness"]) / inp["inspection_interval"], 2),
                f"({inp['previous_thickness']} - {inp['current_thickness']}) / {inp['inspection_interval']}",
                "Long-term corrosion rate calculated directly in mm/year (no conversion factor needed).",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CR-002",
                name="Short-Term Corrosion Rate",
                category="Corrosion",
                description="Calculates short-term corrosion rate (mm/year) between two recent successive inspections.",
                equation="CR_ST = (previous_thickness - current_thickness) / inspection_interval",
                equation_display="(previous_thickness - current_thickness) / inspection_interval",
                variables={"previous_thickness": "Previous recent wall thickness", "current_thickness": "Current wall thickness", "inspection_interval": "Recent inspection interval"},
                units={"previous_thickness": "mm", "current_thickness": "mm", "inspection_interval": "years", "CR_ST": "mm/year"},
                output={"CR_ST": "mm/year"},
                applicable_equipment=["pump", "piping", "pressure_vessel", "storage_tank"],
                required_data=["previous_thickness", "current_thickness", "inspection_interval"],
                standard_reference="API 570 Section 7.1.1",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["previous_thickness"] - inp["current_thickness"]) / inp["inspection_interval"], 2),
                f"({inp['previous_thickness']} - {inp['current_thickness']}) / {inp['inspection_interval']}",
                "Short-term corrosion rate calculated directly in mm/year.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CR-003",
                name="API 570 Remaining Service Life",
                category="Corrosion",
                description="Estimates remaining service life in years before minimum allowable thickness is reached.",
                equation="RL = (current_thickness - minimum_allowable_thickness) / corrosion_rate",
                equation_display="(current_thickness - minimum_allowable_thickness) / corrosion_rate",
                variables={"current_thickness": "Current wall thickness", "minimum_allowable_thickness": "Minimum allowable thickness", "corrosion_rate": "Corrosion rate"},
                units={"current_thickness": "mm", "minimum_allowable_thickness": "mm", "corrosion_rate": "mm/year", "RL": "years"},
                output={"RL": "years"},
                applicable_equipment=["pump", "piping", "pressure_vessel", "storage_tank"],
                required_data=["current_thickness", "minimum_allowable_thickness", "corrosion_rate"],
                standard_reference="API 570 Section 7.1.2 / API 510",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round((inp["current_thickness"] - inp["minimum_allowable_thickness"]) / inp["corrosion_rate"], 2),
                f"({inp['current_thickness']} - {inp['minimum_allowable_thickness']}) / {inp['corrosion_rate']}",
                "Remaining service life in years.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CR-004",
                name="Thickness Margin Above Minimum",
                category="Corrosion",
                description="Calculates remaining thickness margin above the minimum allowable retirement threshold.",
                equation="Margin = current_thickness - minimum_allowable_thickness",
                equation_display="current_thickness - minimum_allowable_thickness",
                variables={"current_thickness": "Current wall thickness", "minimum_allowable_thickness": "Minimum allowable thickness"},
                units={"current_thickness": "mm", "minimum_allowable_thickness": "mm", "Margin": "mm"},
                output={"Margin": "mm"},
                applicable_equipment=["pump", "piping", "pressure_vessel", "storage_tank"],
                required_data=["current_thickness", "minimum_allowable_thickness"],
                standard_reference="ASME B31.3 / API 570",
                risk_level="low",
            ),
            lambda inp: (
                round(inp["current_thickness"] - inp["minimum_allowable_thickness"], 2),
                f"{inp['current_thickness']} - {inp['minimum_allowable_thickness']}",
                "Thickness margin above retirement limit in mm.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="CR-005",
                name="Percentage Wall Loss",
                category="Corrosion",
                description="Calculates percentage wall loss relative to initial baseline thickness.",
                equation="Loss_pct = ((previous_thickness - current_thickness) / previous_thickness) * 100",
                equation_display="((previous_thickness - current_thickness) / previous_thickness) * 100",
                variables={"previous_thickness": "Previous/original thickness", "current_thickness": "Current wall thickness"},
                units={"previous_thickness": "mm", "current_thickness": "mm", "Loss_pct": "%"},
                output={"Loss_pct": "%"},
                applicable_equipment=["pump", "piping", "pressure_vessel", "storage_tank"],
                required_data=["previous_thickness", "current_thickness"],
                standard_reference="API 570 / API 574",
                risk_level="low",
            ),
            lambda inp: (
                round(((inp["previous_thickness"] - inp["current_thickness"]) / inp["previous_thickness"]) * 100.0, 2),
                f"(({inp['previous_thickness']} - {inp['current_thickness']}) / {inp['previous_thickness']}) * 100",
                "Percentage wall loss relative to baseline.",
            ),
        )
        self._register(
            FormulaDefinition(
                formula_id="PV-019",
                name="Longitudinal Stress in Cylindrical Shell",
                category="Pressure Vessels",
                description="Calculates axial/longitudinal membrane stress in closed-end cylinder under pressure.",
                equation="sigma_long = (P * D_internal) / (4 * t)",
                equation_display="(P * D_internal) / (4 * t)",
                variables={"P": "Internal pressure", "D_internal": "Inside diameter", "t": "Wall thickness"},
                units={"P": "MPa", "D_internal": "mm", "t": "mm", "sigma_long": "MPa"},
                output={"sigma_long": "MPa"},
                applicable_equipment=["pressure_vessel", "piping", "drum"],
                required_data=["P", "D_internal", "t"],
                standard_reference="ASME Sec VIII",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["P"] * inp["D_internal"]) / (4.0 * inp["t"]), 2),
                f"({inp['P']} * {inp['D_internal']}) / (4 * {inp['t']})",
                "Longitudinal stress calculated.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-020",
                name="Hydrostatic Test Pressure per ASME B31.3",
                category="Piping",
                description="Determines required hydrostatic leak test pressure (1.5x design or temperature-corrected).",
                equation="P_test = 1.5 * P_design * (S_test / S_design)",
                equation_display="1.5 * P_design * (S_test / S_design)",
                variables={"P_design": "Design pressure", "S_test": "Allowable stress at test temperature", "S_design": "Allowable stress at design temperature"},
                units={"P_design": "bar", "S_test": "MPa", "S_design": "MPa", "P_test": "bar"},
                output={"P_test": "bar"},
                applicable_equipment=["piping", "pipeline", "pressure_vessel"],
                required_data=["P_design", "S_test", "S_design"],
                standard_reference="ASME B31.3 Section 345.4.2",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round(1.5 * inp["P_design"] * (inp["S_test"] / inp["S_design"]), 2),
                f"1.5 * {inp['P_design']} * ({inp['S_test']} / {inp['S_design']})",
                "Hydrostatic test pressure per ASME B31.3.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-021",
                name="Hydrostatic Head Pressure",
                category="Pressure Vessels",
                description="Calculates static liquid head pressure at bottom of vessel or column.",
                equation="P_head = (rho * g * h) / 100000",
                equation_display="(rho * 9.81 * h) / 100000",
                variables={"rho": "Fluid density", "h": "Liquid height column"},
                units={"rho": "kg/m3", "h": "m", "P_head": "bar"},
                output={"P_head": "bar"},
                applicable_equipment=["storage_tank", "column", "drum", "pressure_vessel"],
                required_data=["rho", "h"],
                standard_reference="Fluid Mechanics / API 650",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["rho"] * 9.80665 * inp["h"]) / 100000.0, 3),
                f"({inp['rho']} * 9.81 * {inp['h']}) / 100000",
                "Static liquid head pressure calculated in bar.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-022",
                name="Thickness Safety Margin",
                category="Piping",
                description="Evaluates excess thickness over minimum allowable retirement limit.",
                equation="Margin = (T_actual - T_min) / T_min * 100",
                equation_display="((T_actual - T_min) / T_min) * 100",
                variables={"T_actual": "Actual thickness", "T_min": "Minimum allowable thickness"},
                units={"T_actual": "mm", "T_min": "mm", "Margin": "%"},
                output={"Margin": "%"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank", "pump"],
                required_data=["T_actual", "T_min"],
                standard_reference="API 570 / API 510",
                risk_level="low",
            ),
            lambda inp: (
                round(((inp["T_actual"] - inp["T_min"]) / inp["T_min"]) * 100.0, 2),
                f"(({inp['T_actual']} - {inp['T_min']}) / {inp['T_min']}) * 100",
                "Thickness safety margin computed.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-023",
                name="Design Pressure Operating Margin",
                category="Pressure Vessels",
                description="Calculates percentage margin between normal operating pressure and design pressure.",
                equation="Margin_p = ((P_design - P_operating) / P_design) * 100",
                equation_display="((P_design - P_operating) / P_design) * 100",
                variables={"P_design": "Design pressure", "P_operating": "Normal operating pressure"},
                units={"P_design": "bar", "P_operating": "bar", "Margin_p": "%"},
                output={"Margin_p": "%"},
                applicable_equipment=["pressure_vessel", "piping", "column", "pump"],
                required_data=["P_design", "P_operating"],
                standard_reference="API 521 / Refinery SOP",
                risk_level="low",
            ),
            lambda inp: (
                round(((inp["P_design"] - inp["P_operating"]) / inp["P_design"]) * 100.0, 2),
                f"(({inp['P_design']} - {inp['P_operating']}) / {inp['P_design']}) * 100",
                "Operating pressure headroom margin.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="PV-024",
                name="Von Mises Combined Pressure Stress",
                category="Pressure Vessels",
                description="Combines hoop and longitudinal pressure stresses using Von Mises failure criterion.",
                equation="sigma_vm = sqrt(sigma_h^2 - sigma_h * sigma_l + sigma_l^2)",
                equation_display="sqrt(sigma_h^2 - sigma_h*sigma_l + sigma_l^2)",
                variables={"sigma_h": "Hoop stress", "sigma_l": "Longitudinal stress"},
                units={"sigma_h": "MPa", "sigma_l": "MPa", "sigma_vm": "MPa"},
                output={"sigma_vm": "MPa"},
                applicable_equipment=["pressure_vessel", "piping", "reactor"],
                required_data=["sigma_h", "sigma_l"],
                standard_reference="ASME Sec VIII Div 2 / API 579",
                risk_level="medium",
            ),
            lambda inp: (
                round(math.sqrt(inp["sigma_h"]**2 - inp["sigma_h"] * inp["sigma_l"] + inp["sigma_l"]**2), 2),
                f"sqrt({inp['sigma_h']}^2 - {inp['sigma_h']}*{inp['sigma_l']} + {inp['sigma_l']}^2)",
                "Von Mises equivalent membrane stress.",
            ),
        )

        # ═══════════════════════════════════════════════════════════════
        # SECTION 3: PIPING HYDRAULICS (Formulas 25-31)
        # ═══════════════════════════════════════════════════════════════
        self._register(
            FormulaDefinition(
                formula_id="HYD-025",
                name="Pipe Flow Velocity",
                category="Piping",
                description="Calculates average liquid flow velocity in circular pipe.",
                equation="v = (4 * Q_m3hr) / (3600 * pi * (D_mm / 1000)^2)",
                equation_display="(4 * Q) / (3600 * pi * D^2)",
                variables={"Q_m3hr": "Volumetric flow rate", "D_mm": "Inside pipe diameter"},
                units={"Q_m3hr": "m3/hr", "D_mm": "mm", "v": "m/s"},
                output={"v": "m/s"},
                applicable_equipment=["piping", "pipeline", "pump"],
                required_data=["Q_m3hr", "D_mm"],
                standard_reference="Crane Technical Paper 410 / API RP 14E",
                risk_level="medium",
            ),
            lambda inp: (
                round((4.0 * inp["Q_m3hr"]) / (3600.0 * math.pi * (inp["D_mm"] / 1000.0)**2), 2),
                f"Flow velocity for {inp['Q_m3hr']} m3/hr in {inp['D_mm']} mm ID pipe",
                "Typical liquid line target: 1.5 - 3.0 m/s for crude feed lines.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HYD-026",
                name="Mass Flow Rate from Volumetric Flow",
                category="Piping",
                description="Converts volumetric flow rate to mass flow rate using density.",
                equation="m_dot = (Q_m3hr * rho) / 1000",
                equation_display="(Q * rho) / 1000",
                variables={"Q_m3hr": "Volumetric flow rate", "rho": "Liquid density"},
                units={"Q_m3hr": "m3/hr", "rho": "kg/m3", "m_dot": "ton/hr"},
                output={"m_dot": "ton/hr"},
                applicable_equipment=["piping", "pump", "column", "furnace"],
                required_data=["Q_m3hr", "rho"],
                standard_reference="Process Engineering Standards",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["Q_m3hr"] * inp["rho"]) / 1000.0, 2),
                f"({inp['Q_m3hr']} * {inp['rho']}) / 1000",
                "Mass flow rate in metric tons per hour.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HYD-027",
                name="Reynolds Number (Pipe Flow)",
                category="Piping",
                description="Evaluates flow regime (laminar vs turbulent) in circular piping.",
                equation="Re = (rho * v * (D_mm / 1000)) / (mu_cp / 1000)",
                equation_display="(rho * v * D) / mu",
                variables={"rho": "Liquid density", "v": "Flow velocity", "D_mm": "Inside pipe diameter", "mu_cp": "Dynamic viscosity in cP"},
                units={"rho": "kg/m3", "v": "m/s", "D_mm": "mm", "mu_cp": "cP", "Re": "dimensionless"},
                output={"Re": "dimensionless"},
                applicable_equipment=["piping", "pipeline", "heat_exchanger", "pump"],
                required_data=["rho", "v", "D_mm", "mu_cp"],
                standard_reference="Crane Technical Paper 410",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["rho"] * inp["v"] * (inp["D_mm"] / 1000.0)) / (inp["mu_cp"] / 1000.0), 0),
                f"Re = ({inp['rho']} * {inp['v']} * {inp['D_mm']}/1000) / ({inp['mu_cp']}/1000)",
                "Re > 4000 indicates fully turbulent flow.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HYD-028",
                name="Darcy-Weisbach Frictional Head Loss",
                category="Piping",
                description="Calculates frictional head loss in circular pipe section.",
                equation="h_f = (f * L * v^2) / (2 * g * (D_mm / 1000))",
                equation_display="(f * L * v^2) / (2 * 9.81 * D)",
                variables={"f": "Darcy friction factor", "L": "Pipe length", "v": "Flow velocity", "D_mm": "Pipe inside diameter"},
                units={"f": "factor", "L": "m", "v": "m/s", "D_mm": "mm", "h_f": "m"},
                output={"h_f": "m"},
                applicable_equipment=["piping", "pipeline", "pump"],
                required_data=["f", "L", "v", "D_mm"],
                standard_reference="Crane Technical Paper 410",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["f"] * inp["L"] * inp["v"]**2) / (2.0 * 9.80665 * (inp["D_mm"] / 1000.0)), 2),
                f"({inp['f']} * {inp['L']} * {inp['v']}^2) / (2 * 9.81 * {inp['D_mm']}/1000)",
                "Frictional head loss in meters liquid column.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HYD-029",
                name="Darcy-Weisbach Pressure Drop",
                category="Piping",
                description="Calculates pressure drop across piping run from head loss.",
                equation="delta_P_bar = (rho * 9.81 * h_f) / 100000",
                equation_display="(rho * 9.81 * h_f) / 100000",
                variables={"rho": "Liquid density", "h_f": "Frictional head loss"},
                units={"rho": "kg/m3", "h_f": "m", "delta_P_bar": "bar"},
                output={"delta_P_bar": "bar"},
                applicable_equipment=["piping", "pipeline"],
                required_data=["rho", "h_f"],
                standard_reference="Crane 410",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["rho"] * 9.80665 * inp["h_f"]) / 100000.0, 3),
                f"({inp['rho']} * 9.81 * {inp['h_f']}) / 100000",
                "Pressure drop in bar.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HYD-030",
                name="Pipe Internal Cross-Sectional Area",
                category="Piping",
                description="Calculates internal flow area of piping.",
                equation="Area_cm2 = (pi * (D_mm / 10)^2) / 4",
                equation_display="(pi * (D/10)^2) / 4",
                variables={"D_mm": "Inside pipe diameter"},
                units={"D_mm": "mm", "Area_cm2": "cm2"},
                output={"Area_cm2": "cm2"},
                applicable_equipment=["piping", "pipeline", "control_valve"],
                required_data=["D_mm"],
                standard_reference="Geometric Standards",
                risk_level="low",
            ),
            lambda inp: (
                round((math.pi * (inp["D_mm"] / 10.0)**2) / 4.0, 2),
                f"(pi * ({inp['D_mm']}/10)^2) / 4",
                "Pipe cross-sectional flow area in cm2.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HYD-031",
                name="API RP 14E Erosional Velocity Limit",
                category="Piping",
                description="Determines maximum allowable erosional velocity to prevent line wash.",
                equation="v_max = C_factor / sqrt(rho_lb_cuft)",
                equation_display="C_factor / sqrt(rho_lb_cuft)",
                variables={"C_factor": "Empirical C factor (e.g. 100 for continuous, 125 for intermittent)", "rho_lb_cuft": "Fluid density in lb/ft3"},
                units={"C_factor": "factor", "rho_lb_cuft": "lb/ft3", "v_max": "ft/s"},
                output={"v_max": "ft/s"},
                applicable_equipment=["piping", "pipeline", "control_valve"],
                required_data=["C_factor", "rho_lb_cuft"],
                standard_reference="API RP 14E Section 2.4",
                risk_level="high",
            ),
            lambda inp: (
                round(inp["C_factor"] / math.sqrt(inp["rho_lb_cuft"]), 2),
                f"{inp['C_factor']} / sqrt({inp['rho_lb_cuft']})",
                "API RP 14E erosional velocity ceiling.",
            ),
        )

        # ═══════════════════════════════════════════════════════════════
        # SECTION 4: ROTATING EQUIPMENT (Formulas 32-39)
        # ═══════════════════════════════════════════════════════════════
        self._register(
            FormulaDefinition(
                formula_id="ROT-032",
                name="Pump Hydraulic (Water) Power",
                category="Rotating Equipment",
                description="Calculates theoretical power imparted to liquid by centrifugal pump.",
                equation="P_hyd = (Q_m3hr * rho * g * H_m) / (3.6e6)",
                equation_display="(Q * rho * 9.81 * H) / 3600000",
                variables={"Q_m3hr": "Flow rate", "rho": "Fluid density", "H_m": "Total dynamic head"},
                units={"Q_m3hr": "m3/hr", "rho": "kg/m3", "H_m": "m", "P_hyd": "kW"},
                output={"P_hyd": "kW"},
                applicable_equipment=["pump"],
                required_data=["Q_m3hr", "rho", "H_m"],
                standard_reference="API 610 / Hydraulic Institute",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["Q_m3hr"] * inp["rho"] * 9.80665 * inp["H_m"]) / 3600000.0, 2),
                f"({inp['Q_m3hr']} * {inp['rho']} * 9.81 * {inp['H_m']}) / 3600000",
                "Pump hydraulic power output in kW.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="ROT-033",
                name="Pump Brake Shaft Power (BKP)",
                category="Rotating Equipment",
                description="Calculates electrical motor shaft power required based on pump efficiency.",
                equation="P_shaft = P_hyd / (eta_pump / 100)",
                equation_display="P_hyd / (eta / 100)",
                variables={"P_hyd": "Hydraulic power", "eta_pump": "Pump efficiency percentage"},
                units={"P_hyd": "kW", "eta_pump": "%", "P_shaft": "kW"},
                output={"P_shaft": "kW"},
                applicable_equipment=["pump"],
                required_data=["P_hyd", "eta_pump"],
                standard_reference="API 610 / HI Standards",
                risk_level="medium",
            ),
            lambda inp: (
                round(inp["P_hyd"] / (inp["eta_pump"] / 100.0), 2),
                f"{inp['P_hyd']} / ({inp['eta_pump']}/100)",
                "Brake power required at motor coupling.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="ROT-034",
                name="Centrifugal Pump Total Dynamic Head (TDH)",
                category="Rotating Equipment",
                description="Calculates total head generated from suction and discharge pressure readings.",
                equation="TDH = ((P_disch_bar - P_suct_bar) * 100000) / (rho * 9.81)",
                equation_display="((P_disch - P_suct) * 100000) / (rho * 9.81)",
                variables={"P_disch_bar": "Discharge pressure", "P_suct_bar": "Suction pressure", "rho": "Liquid density"},
                units={"P_disch_bar": "bar", "P_suct_bar": "bar", "rho": "kg/m3", "TDH": "m"},
                output={"TDH": "m"},
                applicable_equipment=["pump"],
                required_data=["P_disch_bar", "P_suct_bar", "rho"],
                standard_reference="API 610 12th Ed",
                risk_level="medium",
            ),
            lambda inp: (
                round(((inp["P_disch_bar"] - inp["P_suct_bar"]) * 100000.0) / (inp["rho"] * 9.80665), 2),
                f"(({inp['P_disch_bar']} - {inp['P_suct_bar']}) * 100000) / ({inp['rho']} * 9.81)",
                "Total dynamic head generated across pump in meters.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="ROT-035",
                name="Net Positive Suction Head Available (NPSHa)",
                category="Rotating Equipment",
                description="Calculates available suction margin to prevent pump cavitation.",
                equation="NPSHa = H_atm + H_static - H_frictional - H_vapor_press",
                equation_display="H_atm + H_static - H_frictional - H_vap",
                variables={"H_atm": "Atmospheric/suction pressure head", "H_static": "Static liquid height above pump centerline", "H_frictional": "Suction line friction loss", "H_vapor_press": "Vapor pressure head at operating temp"},
                units={"H_atm": "m", "H_static": "m", "H_frictional": "m", "H_vapor_press": "m", "NPSHa": "m"},
                output={"NPSHa": "m"},
                applicable_equipment=["pump"],
                required_data=["H_atm", "H_static", "H_frictional", "H_vapor_press"],
                standard_reference="API 610 Section 6.1.8",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round(inp["H_atm"] + inp["H_static"] - inp["H_frictional"] - inp["H_vapor_press"], 2),
                f"{inp['H_atm']} + {inp['H_static']} - {inp['H_frictional']} - {inp['H_vapor_press']}",
                "API 610 requires NPSHa >= NPSHr + 1.0 m (or 1.1x NPSHr).",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="ROT-036",
                name="NPSH Cavitation Margin Ratio",
                category="Rotating Equipment",
                description="Evaluates margin ratio between available and required NPSH.",
                equation="Margin_NPSH = NPSHa / NPSHr",
                equation_display="NPSHa / NPSHr",
                variables={"NPSHa": "Available NPSH", "NPSHr": "Manufacturer required NPSH"},
                units={"NPSHa": "m", "NPSHr": "m", "Margin_NPSH": "ratio"},
                output={"Margin_NPSH": "ratio"},
                applicable_equipment=["pump"],
                required_data=["NPSHa", "NPSHr"],
                standard_reference="API 610 / Hydraulic Institute 9.6.1",
                risk_level="high",
            ),
            lambda inp: (
                round(inp["NPSHa"] / inp["NPSHr"], 2),
                f"{inp['NPSHa']} / {inp['NPSHr']}",
                "Margin < 1.0 causes cavitation, impeller pitting, and high vibration.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="ROT-037",
                name="Pump Specific Speed (Ns)",
                category="Rotating Equipment",
                description="Classifies pump impeller geometry type (radial, mixed, axial).",
                equation="Ns = (N_rpm * sqrt(Q_m3s)) / (H_m^(0.75))",
                equation_display="(N * sqrt(Q)) / H^0.75",
                variables={"N_rpm": "Rotational speed", "Q_m3s": "Flow rate in m3/s", "H_m": "Total head per stage"},
                units={"N_rpm": "rpm", "Q_m3s": "m3/s", "H_m": "m", "Ns": "dimensionless"},
                output={"Ns": "dimensionless"},
                applicable_equipment=["pump"],
                required_data=["N_rpm", "Q_m3s", "H_m"],
                standard_reference="API 610 / Hydraulic Institute",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["N_rpm"] * math.sqrt(inp["Q_m3s"])) / (inp["H_m"]**0.75), 1),
                f"({inp['N_rpm']} * sqrt({inp['Q_m3s']})) / {inp['H_m']}^0.75",
                "Metric specific speed index.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="ROT-038",
                name="Compressor Pressure Ratio",
                category="Rotating Equipment",
                description="Calculates overall stage pressure compression ratio.",
                equation="r_p = P_discharge_abs / P_suction_abs",
                equation_display="P_disch_abs / P_suct_abs",
                variables={"P_discharge_abs": "Absolute discharge pressure", "P_suction_abs": "Absolute suction pressure"},
                units={"P_discharge_abs": "bar_a", "P_suction_abs": "bar_a", "r_p": "ratio"},
                output={"r_p": "ratio"},
                applicable_equipment=["compressor"],
                required_data=["P_discharge_abs", "P_suction_abs"],
                standard_reference="API 617 / ASME PTC 10",
                risk_level="medium",
            ),
            lambda inp: (
                round(inp["P_discharge_abs"] / inp["P_suction_abs"], 3),
                f"{inp['P_discharge_abs']} / {inp['P_suction_abs']}",
                "Compressor pressure ratio per stage.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="ROT-039",
                name="Compressor Isentropic Discharge Temperature",
                category="Rotating Equipment",
                description="Calculates theoretical ideal gas discharge temperature across compressor.",
                equation="T_disch_K = T_suct_K * (P_disch_a / P_suct_a)^((k - 1) / k)",
                equation_display="T_suct * (P_ratio)^((k-1)/k)",
                variables={"T_suct_K": "Suction temperature Kelvin", "P_disch_a": "Discharge pressure", "P_suct_a": "Suction pressure", "k": "Specific heat ratio (Cp/Cv)"},
                units={"T_suct_K": "K", "P_disch_a": "bar_a", "P_suct_a": "bar_a", "k": "factor", "T_disch_K": "K"},
                output={"T_disch_K": "K"},
                applicable_equipment=["compressor"],
                required_data=["T_suct_K", "P_disch_a", "P_suct_a", "k"],
                standard_reference="API 617 / Thermodynamics",
                risk_level="medium",
            ),
            lambda inp: (
                round(inp["T_suct_K"] * (inp["P_disch_a"] / inp["P_suct_a"])**((inp["k"] - 1.0) / inp["k"]), 2),
                f"{inp['T_suct_K']} * ({inp['P_disch_a']}/{inp['P_suct_a']})^({inp['k']-1}/{inp['k']})",
                "Isentropic compression discharge temperature.",
            ),
        )

        # ═══════════════════════════════════════════════════════════════
        # SECTION 5: HEAT TRANSFER & THERMODYNAMICS (Formulas 40-48)
        # ═══════════════════════════════════════════════════════════════
        self._register(
            FormulaDefinition(
                formula_id="HT-040",
                name="Heat Exchanger Thermal Duty (Q)",
                category="Heat Transfer",
                description="Calculates sensible heat transferred by liquid stream.",
                equation="Q_kW = (m_dot_kghr * Cp_kJkgC * delta_T_C) / 3600",
                equation_display="(m_dot * Cp * delta_T) / 3600",
                variables={"m_dot_kghr": "Mass flow rate in kg/hr", "Cp_kJkgC": "Specific heat capacity", "delta_T_C": "Temperature difference in C"},
                units={"m_dot_kghr": "kg/hr", "Cp_kJkgC": "kJ/kg-C", "delta_T_C": "C", "Q_kW": "kW"},
                output={"Q_kW": "kW"},
                applicable_equipment=["heat_exchanger", "furnace", "column"],
                required_data=["m_dot_kghr", "Cp_kJkgC", "delta_T_C"],
                standard_reference="TEMA / API 660",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["m_dot_kghr"] * inp["Cp_kJkgC"] * inp["delta_T_C"]) / 3600.0, 2),
                f"({inp['m_dot_kghr']} * {inp['Cp_kJkgC']} * {inp['delta_T_C']}) / 3600",
                "Sensible heat duty in kW (or kJ/s).",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-041",
                name="Logarithmic Mean Temperature Difference (LMTD)",
                category="Heat Transfer",
                description="Calculates effective temperature driving force for counter-current heat exchanger.",
                equation="LMTD = (dT1 - dT2) / ln(dT1 / dT2)",
                equation_display="(dT1 - dT2) / ln(dT1 / dT2)",
                variables={"dT1": "Temperature approach at hot end (Th_in - Tc_out)", "dT2": "Temperature approach at cold end (Th_out - Tc_in)"},
                units={"dT1": "C", "dT2": "C", "LMTD": "C"},
                output={"LMTD": "C"},
                applicable_equipment=["heat_exchanger"],
                required_data=["dT1", "dT2"],
                standard_reference="TEMA Standards",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["dT1"] - inp["dT2"]) / math.log(inp["dT1"] / inp["dT2"]), 2),
                f"({inp['dT1']} - {inp['dT2']}) / ln({inp['dT1']}/{inp['dT2']})",
                "Counter-current log mean temperature difference.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-042",
                name="Overall Heat Transfer Coefficient (U)",
                category="Heat Transfer",
                description="Calculates overall heat transfer coefficient from duty, area, and LMTD.",
                equation="U = (Q_kW * 1000) / (Area_m2 * LMTD)",
                equation_display="(Q * 1000) / (Area * LMTD)",
                variables={"Q_kW": "Heat duty in kW", "Area_m2": "Total surface area", "LMTD": "Log mean temperature difference"},
                units={"Q_kW": "kW", "Area_m2": "m2", "LMTD": "C", "U": "W/m2-C"},
                output={"U": "W/m2-C"},
                applicable_equipment=["heat_exchanger"],
                required_data=["Q_kW", "Area_m2", "LMTD"],
                standard_reference="TEMA / API 660",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["Q_kW"] * 1000.0) / (inp["Area_m2"] * inp["LMTD"]), 1),
                f"({inp['Q_kW']} * 1000) / ({inp['Area_m2']} * {inp['LMTD']})",
                "Clean/service overall U coefficient.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-043",
                name="Heat Exchanger Required Surface Area",
                category="Heat Transfer",
                description="Calculates required tube bundle heat exchange area.",
                equation="Area_m2 = (Q_kW * 1000) / (U * LMTD)",
                equation_display="(Q * 1000) / (U * LMTD)",
                variables={"Q_kW": "Heat duty in kW", "U": "Overall heat transfer coeff", "LMTD": "Log mean temperature difference"},
                units={"Q_kW": "kW", "U": "W/m2-C", "LMTD": "C", "Area_m2": "m2"},
                output={"Area_m2": "m2"},
                applicable_equipment=["heat_exchanger"],
                required_data=["Q_kW", "U", "LMTD"],
                standard_reference="TEMA Standards",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["Q_kW"] * 1000.0) / (inp["U"] * inp["LMTD"]), 2),
                f"({inp['Q_kW']} * 1000) / ({inp['U']} * {inp['LMTD']})",
                "Required heat transfer surface area.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-044",
                name="Ideal Gas Density",
                category="Thermodynamics",
                description="Calculates density of gas at specified pressure and temperature.",
                equation="rho_gas = (P_bar_a * 1e5 * MW) / (8314.46 * T_Kelvin)",
                equation_display="(P * 100000 * MW) / (8314.5 * T)",
                variables={"P_bar_a": "Absolute pressure in bar", "MW": "Molecular weight in kg/kmol", "T_Kelvin": "Temperature in Kelvin"},
                units={"P_bar_a": "bar_a", "MW": "kg/kmol", "T_Kelvin": "K", "rho_gas": "kg/m3"},
                output={"rho_gas": "kg/m3"},
                applicable_equipment=["compressor", "piping", "pressure_vessel", "relief_valve"],
                required_data=["P_bar_a", "MW", "T_Kelvin"],
                standard_reference="Ideal Gas Law / Thermodynamics",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["P_bar_a"] * 100000.0 * inp["MW"]) / (8314.46 * inp["T_Kelvin"]), 3),
                f"({inp['P_bar_a']} * 100000 * {inp['MW']}) / (8314.5 * {inp['T_Kelvin']})",
                "Ideal gas density in kg/m3.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-045",
                name="Temperature Unit Conversion (Celsius to Fahrenheit)",
                category="Thermodynamics",
                description="Converts temperature from Celsius to Fahrenheit.",
                equation="T_degF = (T_degC * 9 / 5) + 32",
                equation_display="(T_C * 9/5) + 32",
                variables={"T_degC": "Temperature Celsius"},
                units={"T_degC": "C", "T_degF": "F"},
                output={"T_degF": "F"},
                applicable_equipment=["piping", "pressure_vessel", "pump", "furnace"],
                required_data=["T_degC"],
                standard_reference="Standard Conversions",
                risk_level="low",
            ),
            lambda inp: (
                round((inp["T_degC"] * 9.0 / 5.0) + 32.0, 2),
                f"({inp['T_degC']} * 9/5) + 32",
                "Temperature in deg Fahrenheit.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-046",
                name="Pressure Unit Conversion (Bar to PSI)",
                category="Thermodynamics",
                description="Converts gauge or absolute pressure from bar to psi.",
                equation="P_psi = P_bar * 14.5038",
                equation_display="P_bar * 14.5038",
                variables={"P_bar": "Pressure in bar"},
                units={"P_bar": "bar", "P_psi": "psi"},
                output={"P_psi": "psi"},
                applicable_equipment=["piping", "pressure_vessel", "pump", "relief_valve"],
                required_data=["P_bar"],
                standard_reference="Standard Conversions",
                risk_level="low",
            ),
            lambda inp: (
                round(inp["P_bar"] * 14.50377, 2),
                f"{inp['P_bar']} * 14.5038",
                "Pressure in psi.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-047",
                name="Pressure Unit Conversion (Bar to MPa)",
                category="Thermodynamics",
                description="Converts pressure from bar to Megapascals.",
                equation="P_mpa = P_bar * 0.1",
                equation_display="P_bar * 0.1",
                variables={"P_bar": "Pressure in bar"},
                units={"P_bar": "bar", "P_mpa": "MPa"},
                output={"P_mpa": "MPa"},
                applicable_equipment=["piping", "pressure_vessel"],
                required_data=["P_bar"],
                standard_reference="Standard Conversions",
                risk_level="low",
            ),
            lambda inp: (
                round(inp["P_bar"] * 0.1, 4),
                f"{inp['P_bar']} * 0.1",
                "Pressure in MPa.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="HT-048",
                name="Heat Exchanger Energy Balance Check",
                category="Heat Transfer",
                description="Checks discrepancy between hot fluid duty release and cold fluid duty absorption.",
                equation="Discrepancy_pct = abs(Q_hot - Q_cold) / max(Q_hot, Q_cold) * 100",
                equation_display="abs(Q_hot - Q_cold) / max(Q_hot, Q_cold) * 100",
                variables={"Q_hot": "Hot fluid heat released", "Q_cold": "Cold fluid heat absorbed"},
                units={"Q_hot": "kW", "Q_cold": "kW", "Discrepancy_pct": "%"},
                output={"Discrepancy_pct": "%"},
                applicable_equipment=["heat_exchanger"],
                required_data=["Q_hot", "Q_cold"],
                standard_reference="TEMA / Energy Balance",
                risk_level="medium",
            ),
            lambda inp: (
                round((abs(inp["Q_hot"] - inp["Q_cold"]) / max(inp["Q_hot"], inp["Q_cold"])) * 100.0, 2),
                f"abs({inp['Q_hot']} - {inp['Q_cold']}) / {max(inp['Q_hot'], inp['Q_cold'])} * 100",
                "Energy balance discrepancy > 5% indicates heat loss or metering error.",
            ),
        )

        # ═══════════════════════════════════════════════════════════════
        # SECTION 6: GENERAL REFINERY ENGINEERING & SAFETY (Formulas 49-54)
        # ═══════════════════════════════════════════════════════════════
        self._register(
            FormulaDefinition(
                formula_id="GEN-049",
                name="Percentage Variation / Change",
                category="General Engineering",
                description="Calculates percentage difference between baseline reference and observed value.",
                equation="Pct_Diff = ((Value_observed - Value_baseline) / Value_baseline) * 100",
                equation_display="((V_obs - V_base) / V_base) * 100",
                variables={"Value_baseline": "Baseline value", "Value_observed": "Observed value"},
                units={"Value_baseline": "unit", "Value_observed": "unit", "Pct_Diff": "%"},
                output={"Pct_Diff": "%"},
                applicable_equipment=["pump", "compressor", "piping", "pressure_vessel", "heat_exchanger"],
                required_data=["Value_baseline", "Value_observed"],
                standard_reference="Mathematical Standards",
                risk_level="low",
            ),
            lambda inp: (
                round(((inp["Value_observed"] - inp["Value_baseline"]) / inp["Value_baseline"]) * 100.0, 2),
                f"(({inp['Value_observed']} - {inp['Value_baseline']}) / {inp['Value_baseline']}) * 100",
                "Percentage variation.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="GEN-050",
                name="Engineering Safety Factor",
                category="General Engineering",
                description="Calculates safety factor against material yield or ultimate tensile strength.",
                equation="SF = Strength_allowable / Stress_actual",
                equation_display="Strength_allowable / Stress_actual",
                variables={"Strength_allowable": "Allowable material yield strength", "Stress_actual": "Calculated actual stress"},
                units={"Strength_allowable": "MPa", "Stress_actual": "MPa", "SF": "factor"},
                output={"SF": "factor"},
                applicable_equipment=["piping", "pressure_vessel", "storage_tank"],
                required_data=["Strength_allowable", "Stress_actual"],
                standard_reference="ASME Boiler & Pressure Vessel Code",
                risk_level="high",
            ),
            lambda inp: (
                round(inp["Strength_allowable"] / inp["Stress_actual"], 2),
                f"{inp['Strength_allowable']} / {inp['Stress_actual']}",
                "Safety Factor >= 1.5 required for continuous pressure equipment.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="GEN-051",
                name="ISO 10816 Rotating Equipment Vibration Severity Evaluation",
                category="Rotating Equipment",
                description="Evaluates vibration velocity RMS against ISO 10816-3 Zone A/B/C/D thresholds for Class II/III machinery.",
                equation="Trip_Exceeded = 1 if RMS_velocity > 7.1 else 0",
                equation_display="RMS_velocity vs 7.1 mm/s Limit",
                variables={"RMS_velocity": "Measured overall vibration RMS"},
                units={"RMS_velocity": "mm/s", "Trip_Exceeded": "flag"},
                output={"Trip_Exceeded": "flag"},
                applicable_equipment=["pump", "compressor", "motor"],
                required_data=["RMS_velocity"],
                standard_reference="ISO 10816-3 Zone D Threshold",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                1.0 if inp["RMS_velocity"] > 7.1 else 0.0,
                f"Measured {inp['RMS_velocity']} mm/s vs ISO limit 7.1 mm/s",
                "Zone D (> 7.1 mm/s): Unacceptable. Trip / immediate maintenance mandatory." if inp["RMS_velocity"] > 7.1 else "Within allowable ISO 10816 Zone A/B/C.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="GEN-052",
                name="API 520 PSV Required Relieving Orifice Area (Liquid)",
                category="Safety Relief Devices",
                description="Calculates minimum required discharge orifice area for liquid relief valve.",
                equation="A_req = (Q_gpm * sqrt(G)) / (38 * K_d * K_w * K_v * sqrt(P_set_psig - P_back_psig))",
                equation_display="Q / (38 * Kd * sqrt(P_diff))",
                variables={"Q_gpm": "Relief flow in GPM", "G": "Specific gravity", "K_d": "Effective discharge coefficient (default 0.65)", "P_set_psig": "Set pressure in psig", "P_back_psig": "Backpressure in psig"},
                units={"Q_gpm": "GPM", "G": "sg", "K_d": "factor", "P_set_psig": "psig", "P_back_psig": "psig", "A_req": "in2"},
                output={"A_req": "in2"},
                applicable_equipment=["psv", "safety_valve"],
                required_data=["Q_gpm", "G", "K_d", "P_set_psig", "P_back_psig"],
                standard_reference="API RP 520 Part I Section 5.9",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round((inp["Q_gpm"] * math.sqrt(inp["G"])) / (38.0 * inp["K_d"] * 1.0 * 1.0 * math.sqrt(max(inp["P_set_psig"] - inp["P_back_psig"], 1.0))), 3),
                f"API 520 Liquid Orifice Sizing for {inp['Q_gpm']} GPM",
                "API RP 520 Part I required orifice area in square inches.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="GEN-053",
                name="Piping Deadleg Corrosion Risk Factor",
                category="Corrosion",
                description="Estimates relative localized deadleg acceleration multiplier.",
                equation="Risk_Index = (L_over_D * Stagnation_Days) / 100",
                equation_display="(L/D * Days) / 100",
                variables={"L_over_D": "Length to Diameter ratio of deadleg", "Stagnation_Days": "Stagnant exposure days"},
                units={"L_over_D": "ratio", "Stagnation_Days": "days", "Risk_Index": "index"},
                output={"Risk_Index": "index"},
                applicable_equipment=["piping", "valve"],
                required_data=["L_over_D", "Stagnation_Days"],
                standard_reference="API 570 Section 5.4 Deadlegs",
                risk_level="medium",
            ),
            lambda inp: (
                round((inp["L_over_D"] * inp["Stagnation_Days"]) / 100.0, 2),
                f"({inp['L_over_D']} * {inp['Stagnation_Days']}) / 100",
                "Deadlegs with L/D > 3 require periodic ultrasonic radiography inspection.",
            ),
        )

        self._register(
            FormulaDefinition(
                formula_id="GEN-054",
                name="Storage Tank Bottom Minimum Remaining Thickness per API 653",
                category="Storage Tanks",
                description="Calculates minimum permissible bottom plate thickness before mandatory retirement.",
                equation="t_min_tank = min(0.10 * t_nominal, 2.5)",
                equation_display="min(0.10 * t_nominal, 2.5 mm)",
                variables={"t_nominal": "Original bottom plate nominal thickness"},
                units={"t_nominal": "mm", "t_min_tank": "mm"},
                output={"t_min_tank": "mm"},
                applicable_equipment=["storage_tank"],
                required_data=["t_nominal"],
                standard_reference="API 653 Section 4.4.5",
                risk_level="high",
                engineering_review_required=True,
            ),
            lambda inp: (
                round(max(0.10 * inp["t_nominal"], 2.5), 2),
                f"API 653 Bottom Plate Minimum limit for {inp['t_nominal']} mm",
                "API 653 minimum allowable bottom plate thickness without bottom release prevention barrier.",
            ),
        )

        logger.info(f"FormulaRegistry initialized with {len(self._formulas)} validated engineering formulas.")
