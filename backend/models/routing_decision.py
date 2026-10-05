import time
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .task_profile import TaskProfile, RiskLevel


class CandidateSubscores(BaseModel):
    capability_match: float = Field(0.0, description="Capability compatibility score (0-1)")
    benchmark_score: float = Field(0.0, description="Benchmark score (0-1)")
    context_suitability: float = Field(0.0, description="Context length match score (0-1)")
    hardware_suitability: float = Field(0.0, description="VRAM/CPU suitability score (0-1)")
    latency_score: float = Field(0.0, description="Latency rating (0-1)")
    task_performance: float = Field(0.0, description="Historical performance for task type (0-1)")
    risk_compatibility: float = Field(0.0, description="Risk tolerance compatibility (0-1)")
    policy_compatibility: float = Field(0.0, description="Security policy adherence score (0-1)")
    availability_score: float = Field(1.0, description="Model availability and health readiness score (0-1)")
    resource_penalty: float = Field(0.0, description="Penalty for excessive resource usage (0-1)")


class CandidateEvaluation(BaseModel):
    model_id: str = Field(..., description="Stable internal model identifier")
    ollama_name: str = Field(..., description="Ollama model tag")
    display_name: str = Field("", description="Human-readable model name")
    score: float = Field(0.0, description="Final composite score (0.0 - 1.0)")
    eligible: bool = Field(True, description="Whether the model is eligible to be chosen")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if ineligible")
    subscores: CandidateSubscores = Field(default_factory=CandidateSubscores, description="Granular factor breakdown")


class SelectedModelRole(BaseModel):
    model_id: str = Field(..., description="Internal stable model ID")
    ollama_name: str = Field(..., description="Ollama model tag")
    display_name: str = Field("", description="Model display name")
    role: str = Field("primary", description="Role: primary, independent_verifier, fallback")


class RoutingDecision(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}", description="Unique request trace ID")
    task: TaskProfile = Field(..., description="Analyzed task profile")
    required_capabilities: Dict[str, float] = Field(default_factory=dict, description="Requested capability weights")
    candidates: List[CandidateEvaluation] = Field(default_factory=list, description="All evaluated candidate models")
    selected_models: List[SelectedModelRole] = Field(default_factory=list, description="Assigned execution models and roles")
    verification_required: bool = Field(False, description="Whether secondary independent verification is required")
    reason: str = Field("", description="Mathematical / policy rationale for routing decision")
    local_only: bool = Field(True, description="Air-gap local execution guarantee")
    timestamp: float = Field(default_factory=time.time, description="Epoch timestamp of decision")
