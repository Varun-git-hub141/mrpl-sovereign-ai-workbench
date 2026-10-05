import time
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class CapabilitySource(str, Enum):
    DECLARED = "declared"
    METADATA = "metadata"
    PROBE = "probe"
    BENCHMARK = "benchmark"
    MANUAL_OVERRIDE = "manual_override"
    OBSERVED = "observed"
    UNKNOWN = "unknown"


class ModelHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    RESOURCE_LIMITED = "resource_limited"
    ERROR = "error"


class CapabilityEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    score: float = Field(0.5, ge=0.0, le=1.0, description="Normalized score 0.0 to 1.0")
    source: CapabilitySource = Field(CapabilitySource.UNKNOWN, description="Provenance source of capability score")
    last_updated: float = Field(default_factory=time.time, description="Timestamp of score assignment")
    evidence: Optional[str] = Field(None, description="Diagnostic evidence or probe result reference")

    def __float__(self) -> float:
        return float(self.score)

    def __gt__(self, other: Any) -> bool:
        return self.score > float(other)

    def __ge__(self, other: Any) -> bool:
        return self.score >= float(other)

    def __lt__(self, other: Any) -> bool:
        return self.score < float(other)

    def __le__(self, other: Any) -> bool:
        return self.score <= float(other)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, CapabilityEntry):
            return self.score == other.score and self.source == other.source
        return self.score == float(other)


def _coerce_capability(v: Any) -> CapabilityEntry:
    if isinstance(v, CapabilityEntry):
        return v
    if isinstance(v, dict):
        return CapabilityEntry(
            score=float(v.get("score", 0.5)),
            source=CapabilitySource(v.get("source", "unknown")),
            evidence=v.get("evidence"),
        )
    if isinstance(v, (int, float)):
        return CapabilityEntry(score=max(0.0, min(1.0, float(v))), source=CapabilitySource.UNKNOWN)
    return CapabilityEntry(score=0.5, source=CapabilitySource.UNKNOWN)


class CapabilityVector(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    reasoning: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.5, source=CapabilitySource.UNKNOWN))
    coding: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.0, source=CapabilitySource.UNKNOWN))
    vision: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.0, source=CapabilitySource.UNKNOWN))
    document_understanding: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.5, source=CapabilitySource.UNKNOWN))
    mathematics: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.5, source=CapabilitySource.UNKNOWN))
    ocr: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.0, source=CapabilitySource.UNKNOWN))
    tool_use: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.5, source=CapabilitySource.UNKNOWN))
    general: CapabilityEntry = Field(default_factory=lambda: CapabilityEntry(score=0.5, source=CapabilitySource.UNKNOWN))

    @model_validator(mode="before")
    @classmethod
    def convert_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            converted = {}
            for k, v in data.items():
                converted[k] = _coerce_capability(v)
            return converted
        return data

    def to_dict(self) -> Dict[str, float]:
        return self.to_score_dict()

    def to_score_dict(self) -> Dict[str, float]:
        return {
            "reasoning": float(self.reasoning.score),
            "coding": float(self.coding.score),
            "vision": float(self.vision.score),
            "document_understanding": float(self.document_understanding.score),
            "mathematics": float(self.mathematics.score),
            "ocr": float(self.ocr.score),
            "tool_use": float(self.tool_use.score),
            "general": float(self.general.score),
        }

    def get_score(self, dim: str) -> float:
        entry = getattr(self, dim, None)
        if isinstance(entry, CapabilityEntry):
            return entry.score
        elif isinstance(entry, (int, float)):
            return float(entry)
        return 0.5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityVector":
        return cls.from_scores(data)

    @classmethod
    def from_scores(cls, scores: Dict[str, Any], default_source: CapabilitySource = CapabilitySource.UNKNOWN) -> "CapabilityVector":
        fields = {}
        for dim in ["reasoning", "coding", "vision", "document_understanding", "mathematics", "ocr", "tool_use", "general"]:
            if dim in scores:
                val = scores[dim]
                if isinstance(val, dict):
                    fields[dim] = CapabilityEntry(
                        score=float(val.get("score", 0.5)),
                        source=CapabilitySource(val.get("source", default_source.value)),
                        evidence=val.get("evidence"),
                    )
                elif isinstance(val, CapabilityEntry):
                    fields[dim] = val
                else:
                    fields[dim] = CapabilityEntry(
                        score=max(0.0, min(1.0, float(val))),
                        source=default_source,
                    )
            else:
                fields[dim] = CapabilityEntry(score=0.5, source=default_source)
        return cls(**fields)


class HardwareRequirements(BaseModel):
    estimated_vram_gb: float = Field(4.0, description="Estimated VRAM required for full GPU offload in GB")
    cpu_supported: bool = Field(True, description="Whether model can run via CPU inference fallback")
    gpu_supported: bool = Field(True, description="Whether model supports GPU acceleration")
    required_ram_gb: float = Field(6.0, description="Required system RAM if running on CPU or hybrid offload")


class PerformanceStats(BaseModel):
    benchmark_score: float = Field(0.75, ge=0.0, le=1.0, description="Empirical or configured benchmark quality score")
    latency_score: float = Field(0.80, ge=0.0, le=1.0, description="Normalized latency speed rating (higher is faster)")
    avg_latency_ms: float = Field(800.0, description="Rolling average inference latency in milliseconds")
    p95_latency_ms: float = Field(1500.0, description="95th percentile latency in milliseconds")
    recent_latencies: List[float] = Field(default_factory=list, description="Recent execution latencies in ms (last 30)")
    success_rate: float = Field(1.0, ge=0.0, le=1.0, description="Inference execution reliability score")
    total_calls: int = Field(0, description="Total number of inference runs recorded")
    successful_calls: int = Field(0, description="Total successful executions")
    failed_calls: int = Field(0, description="Total failed executions")


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Stable internal unique identifier (e.g., model-f72c60ca)")
    ollama_name: str = Field(..., description="Actual Ollama model tag (e.g., qwen2.5-coder:3b)")
    display_name: str = Field("", description="Human readable display name")
    family: str = Field("qwen", description="Base architecture family")
    architecture: str = Field("qwen", description="Specific model architecture (e.g. qwen2, qwen25vl, llama)")
    parameter_size: str = Field("3B", description="Model parameter size (e.g. 3.1B, 4.0B)")
    quantization: str = Field("Q4_K_M", description="Quantization level")
    capabilities: CapabilityVector = Field(default_factory=CapabilityVector)
    context_length: int = Field(32768, description="Maximum context window in tokens")
    hardware: HardwareRequirements = Field(default_factory=HardwareRequirements)
    performance: PerformanceStats = Field(default_factory=PerformanceStats)
    availability: bool = Field(True, description="Whether model is currently discoverable and responsive")
    health: ModelHealthStatus = Field(ModelHealthStatus.HEALTHY, description="Current health status")
    local_only: bool = Field(True, description="Enforces air-gapped on-premise operation")
    source: str = Field("ollama", description="Runtime provider backend")
    last_discovered: float = Field(default_factory=time.time, description="Timestamp of discovery")
    last_benchmark: Optional[float] = Field(None, description="Timestamp of latest benchmark")
    last_probe: Optional[float] = Field(None, description="Timestamp of latest capability probe")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw metadata extracted from Ollama or overrides")
