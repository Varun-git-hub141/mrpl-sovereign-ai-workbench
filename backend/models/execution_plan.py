import time
import uuid
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from backend.models.task_profile import RiskLevel


from enum import Enum


class ExecutionStrategy(str, Enum):
    SINGLE_PASS_DIRECT = "single_pass_direct"
    MULTI_MODEL_CROSS_VERIFICATION = "multi_model_cross_verification"
    DETERMINISTIC_TOOL_VERIFICATION = "deterministic_tool_verification"
    HUMAN_IN_THE_LOOP_GATE = "human_in_the_loop_gate"


class ModelRoleAssignment(BaseModel):
    model_id: str = Field(..., description="Stable internal model identifier")
    ollama_name: str = Field(..., description="Ollama model tag")
    display_name: str = Field("", description="Human-readable model name")
    role: str = Field("primary", description="Role: primary, independent_verifier, fallback")
    architecture: str = Field("unknown", description="Architecture family")


class VerificationSpec(BaseModel):
    cross_model: Union[str, bool] = Field("NOT_REQUIRED", description="REQUIRED, NOT_REQUIRED, or OPTIONAL")
    evidence: Union[str, bool] = Field("NOT_REQUIRED", description="REQUIRED, NOT_REQUIRED, or OPTIONAL")
    deterministic: Union[str, bool] = Field("NOT_REQUIRED", description="REQUIRED, NOT_REQUIRED, or OPTIONAL")
    contradiction_check: Union[str, bool] = Field("REQUIRED", description="REQUIRED, NOT_REQUIRED, or OPTIONAL")

    def __init__(
        self,
        cross_model: Union[str, bool] = "NOT_REQUIRED",
        evidence: Union[str, bool] = "NOT_REQUIRED",
        deterministic: Union[str, bool] = "NOT_REQUIRED",
        contradiction_check: Union[str, bool] = "REQUIRED",
        cross_model_required: Optional[bool] = None,
        deterministic_required: Optional[bool] = None,
        evidence_required: Optional[bool] = None,
        contradiction_check_required: Optional[bool] = None,
        **data,
    ):
        if deterministic_required is not None:
            deterministic = "REQUIRED" if deterministic_required else "NOT_REQUIRED"
        if cross_model_required is not None:
            cross_model = "REQUIRED" if cross_model_required else "NOT_REQUIRED"
        if evidence_required is not None:
            evidence = "REQUIRED" if evidence_required else "NOT_REQUIRED"
        if contradiction_check_required is not None:
            contradiction_check = "REQUIRED" if contradiction_check_required else "NOT_REQUIRED"
        super().__init__(
            cross_model=cross_model,
            evidence=evidence,
            deterministic=deterministic,
            contradiction_check=contradiction_check,
            **data,
        )

    @property
    def cross_model_required(self) -> bool:
        return self.cross_model in ("REQUIRED", True, "true", "True")

    @property
    def deterministic_required(self) -> bool:
        return self.deterministic in ("REQUIRED", True, "true", "True")

    @property
    def evidence_required(self) -> bool:
        return self.evidence in ("REQUIRED", True, "true", "True")

    @property
    def contradiction_check_required(self) -> bool:
        return self.contradiction_check in ("REQUIRED", True, "true", "True")


class ExecutionPlan(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}", description="Unique request trace ID")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of plan generation")
    risk: RiskLevel = Field(RiskLevel.LOW, description="Determined operational risk tier")
    strategy: Union[ExecutionStrategy, str] = Field(ExecutionStrategy.SINGLE_PASS_DIRECT, description="Assigned execution strategy")
    
    primary_model: ModelRoleAssignment = Field(..., description="Primary assigned execution model")
    verifier_model: Optional[ModelRoleAssignment] = Field(None, description="Independent verifier model if required")
    verification_independence: str = Field("NOT_APPLICABLE", description="HIGHER, LIMITED, or NOT_APPLICABLE")
    
    required_tools: List[str] = Field(default_factory=list, description="Local tools, calculators, and sandboxes required")
    required_capabilities: Dict[str, float] = Field(default_factory=dict, description="Capability demands")
    
    verification_spec: VerificationSpec = Field(default_factory=VerificationSpec, description="Required verification procedures")
    human_approval_required: bool = Field(False, description="Flag indicating human-in-the-loop review gate")
    
    fallback_models: List[str] = Field(default_factory=list, description="Ordered list of eligible fallback model tags")
    deliverable_type: str = Field("technical_answer", description="Expected output artifact format")
    
    local_only: bool = Field(True, description="Enforces air-gapped on-premise execution")
    vision_required: bool = Field(False, description="Whether multimodal visual inference is required")
    ocr_required: bool = Field(False, description="Whether OCR parsing is required")
    rag_required: bool = Field(False, description="Whether local RAG evidence retrieval is required")
    
    plan_rationale: str = Field("", description="Mathematical and policy reasoning behind this execution strategy")
