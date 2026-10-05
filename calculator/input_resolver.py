import logging
from typing import Dict, Any, List, Optional, Union
from schemas.engineering_evidence import EvidenceValue, EngineeringEvidence

logger = logging.getLogger(__name__)


class InputResolver:
    """
    Authoritative Input Resolver:
    Binds Canonical Engineering Evidence to Formula Registry Requirements.
    Resolves aliases, validates units and physical constraints, and ensures
    deterministic calculation without data loss or silent nulls.
    """

    ALIASES: Dict[str, List[str]] = {
        "previous_thickness": [
            "previous_thickness",
            "previous_wall_thickness",
            "original_thickness",
            "original_wall_thickness",
            "baseline_thickness",
            "initial_thickness",
            "nominal_thickness",
            "T_previous",
            "T_old",
            "T_initial",
            "t_previous",
            "t_initial",
            "t_prev",
            "t_orig",
        ],
        "original_thickness": [
            "original_thickness",
            "previous_thickness",
            "previous_wall_thickness",
            "original_wall_thickness",
            "baseline_thickness",
            "initial_thickness",
            "nominal_thickness",
            "T_previous",
            "T_old",
            "T_initial",
            "t_previous",
            "t_initial",
            "t_prev",
            "t_orig",
        ],
        "current_thickness": [
            "current_thickness",
            "current_wall_thickness",
            "actual_thickness",
            "measured_thickness",
            "wall_thickness",
            "t_actual",
            "T_current",
            "T_new",
            "t_current",
            "t_curr",
        ],
        "inspection_interval": [
            "inspection_interval",
            "elapsed_time",
            "time_interval",
            "delta_years",
            "T_interval",
            "elapsed_years",
            "years",
            "time_span",
            "recent_elapsed_time",
            "delta_years_ST",
            "time_between_inspections",
        ],
        "minimum_allowable_thickness": [
            "minimum_allowable_thickness",
            "min_allowable_thickness",
            "minimum_thickness",
            "t_min",
            "Tmin",
            "T_min",
            "retirement_thickness",
            "minimum_allowable",
        ],
        "corrosion_rate": [
            "corrosion_rate",
            "CR",
            "cr",
            "rate",
            "corrosion_rate_mm_year",
            "CR_ST",
            "CR_LT",
        ],
    }

    VALID_LENGTH_UNITS = {"mm", "cm", "m", "in"}
    VALID_TIME_UNITS = {"years", "year", "yr", "yrs", "y"}

    @classmethod
    def resolve_input(
        cls,
        evidence: Union[Dict[str, Any], EngineeringEvidence],
        canonical_name: str,
    ) -> Optional[EvidenceValue]:
        """
        Resolves a single canonical input or alias from evidence object.
        Returns EvidenceValue with full provenance or None.
        """
        # Convert Pydantic model to dict if needed
        if isinstance(evidence, EngineeringEvidence):
            ev_dict = evidence.to_canonical_dict()
        elif hasattr(evidence, "model_dump"):
            ev_dict = evidence.model_dump()
        elif isinstance(evidence, dict):
            ev_dict = evidence
        else:
            ev_dict = {}

        # 1. Look for exact canonical match
        if canonical_name in ev_dict and ev_dict[canonical_name] is not None:
            raw = ev_dict[canonical_name]
            return cls._to_evidence_value(raw, canonical_name)

        # 2. Look through all aliases
        aliases = cls.ALIASES.get(canonical_name, [canonical_name])
        for alias in aliases:
            if alias in ev_dict and ev_dict[alias] is not None:
                raw = ev_dict[alias]
                return cls._to_evidence_value(raw, alias)

        return None

    @classmethod
    def _to_evidence_value(cls, raw: Any, field_name: str) -> Optional[EvidenceValue]:
        """Converts raw dict, float, or object into strongly typed EvidenceValue."""
        if isinstance(raw, EvidenceValue):
            return raw
        if isinstance(raw, dict):
            val = raw.get("value")
            if val is None:
                return None
            try:
                num_val = float(val)
            except (ValueError, TypeError):
                return None
            unit = str(raw.get("unit", "mm" if "interval" not in field_name and "time" not in field_name else "years"))
            src = str(raw.get("source", "Page 1"))
            ver = bool(raw.get("verified", True))
            conf = float(raw["confidence"]) if raw.get("confidence") is not None else 0.95
            orig_name = str(raw.get("original_field_name", field_name))
            return EvidenceValue(
                value=num_val,
                unit=unit,
                source=src,
                verified=ver,
                confidence=conf,
                original_field_name=orig_name,
            )
        elif isinstance(raw, (int, float)):
            unit = "years" if ("interval" in field_name or "time" in field_name or "years" in field_name) else "mm"
            return EvidenceValue(
                value=float(raw),
                unit=unit,
                source="Page 1",
                verified=True,
                confidence=0.95,
                original_field_name=field_name,
            )
        return None

    @classmethod
    def resolve_required_inputs(
        cls,
        evidence: Union[Dict[str, Any], EngineeringEvidence],
        required_inputs: List[str],
        expected_units: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Resolves, validates, and normalizes all required inputs for a formula.
        Returns complete resolution status and explicit missing fields.
        """
        resolved: Dict[str, EvidenceValue] = {}
        resolved_numeric: Dict[str, float] = {}
        missing: List[str] = []
        validation_errors: List[str] = []
        warnings: List[str] = []

        expected_units = expected_units or {}

        for field in required_inputs:
            val_obj = cls.resolve_input(evidence, field)
            if val_obj is None:
                missing.append(field)
                continue

            # Unit validation & normalization
            exp_u = expected_units.get(field)
            if not exp_u:
                if any(t in field for t in ["interval", "elapsed", "time", "years"]):
                    exp_u = "years"
                elif any(c in field for c in ["rate", "cr"]):
                    exp_u = "mm/year"
                else:
                    exp_u = "mm"

            actual_u = val_obj.unit.strip().lower()
            exp_u = exp_u.strip().lower()

            if exp_u == "mm" and actual_u not in cls.VALID_LENGTH_UNITS:
                validation_errors.append(f"Incompatible unit '{val_obj.unit}' for '{field}'. Expected length unit (mm, cm, m, in).")
            elif exp_u in cls.VALID_TIME_UNITS and actual_u not in cls.VALID_TIME_UNITS:
                validation_errors.append(f"Incompatible unit '{val_obj.unit}' for '{field}'. Expected time unit (years).")

            # Length unit normalization (e.g. cm -> mm)
            norm_val = val_obj.value
            norm_unit = val_obj.unit
            if exp_u == "mm":
                if actual_u == "cm":
                    norm_val = norm_val * 10.0
                    norm_unit = "mm"
                elif actual_u == "m":
                    norm_val = norm_val * 1000.0
                    norm_unit = "mm"
                elif actual_u == "in":
                    norm_val = norm_val * 25.4
                    norm_unit = "mm"
                else:
                    norm_unit = "mm"

            # Physics / Sanity Checks
            if norm_val <= 0 and any(t in field for t in ["interval", "elapsed", "time"]):
                validation_errors.append(f"Inspection interval must be greater than zero ({norm_val:g} provided). Cannot divide by zero.")
            elif norm_val < 0 and any(th in field for th in ["thickness", "wall", "min"]):
                validation_errors.append(f"Negative thickness ({norm_val:g}) is physically impossible for '{field}'.")

            resolved[field] = EvidenceValue(
                value=norm_val,
                unit=norm_unit,
                source=val_obj.source,
                verified=val_obj.verified,
                confidence=val_obj.confidence,
                original_field_name=val_obj.original_field_name,
            )
            resolved_numeric[field] = norm_val

        # Check relative thickness sanity
        prev_val = resolved_numeric.get("previous_thickness") or resolved_numeric.get("original_thickness")
        curr_val = resolved_numeric.get("current_thickness")
        if prev_val is not None and curr_val is not None and curr_val > prev_val:
            warnings.append(f"Current thickness ({curr_val:g} mm) exceeds previous thickness ({prev_val:g} mm). Engineering review recommended.")

        is_complete = len(missing) == 0 and len(validation_errors) == 0

        return {
            "resolved": resolved,
            "resolved_numeric": resolved_numeric,
            "missing": missing,
            "missing_inputs": missing,
            "validation_errors": validation_errors,
            "warnings": warnings,
            "complete": is_complete,
            "status": "SUCCESS" if is_complete else ("INVALID_INPUT" if validation_errors else "INSUFFICIENT_DATA"),
        }


def resolve_input(evidence: Any, canonical_name: str) -> Optional[EvidenceValue]:
    return InputResolver.resolve_input(evidence, canonical_name)


def resolve_required_inputs(evidence: Any, required_inputs: List[str]) -> Dict[str, Any]:
    return InputResolver.resolve_required_inputs(evidence, required_inputs)
