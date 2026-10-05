from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any, List


class EvidenceValue(BaseModel):
    value: float
    unit: str
    source: str = "native_text"
    page: int = 1
    verified: bool = False
    confidence: Optional[float] = 0.95
    original_field_name: Optional[str] = None


class EngineeringEvidence(BaseModel):
    equipment_tag: str

    previous_thickness: Optional[EvidenceValue] = None
    current_thickness: Optional[EvidenceValue] = None
    minimum_allowable_thickness: Optional[EvidenceValue] = None

    inspection_interval: Optional[EvidenceValue] = None

    inspection_date: Optional[str] = None
    report_id: Optional[str] = None

    # Helper property for original_thickness alias
    @property
    def original_thickness(self) -> Optional[EvidenceValue]:
        return self.previous_thickness

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Serializes into standard canonical dictionary with provenance."""
        res: Dict[str, Any] = {"equipment_tag": self.equipment_tag}
        if self.previous_thickness:
            res["previous_thickness"] = self.previous_thickness.model_dump()
            res["original_thickness"] = self.previous_thickness.model_dump()
        if self.current_thickness:
            res["current_thickness"] = self.current_thickness.model_dump()
        if self.minimum_allowable_thickness:
            res["minimum_allowable_thickness"] = self.minimum_allowable_thickness.model_dump()
        if self.inspection_interval:
            res["inspection_interval"] = self.inspection_interval.model_dump()
        if self.inspection_date:
            res["inspection_date"] = self.inspection_date
        if self.report_id:
            res["report_id"] = self.report_id
        return res
