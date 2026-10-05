import re
import hashlib
import logging
from typing import List, Dict, Any, Optional
from backend.models.model_profile import (
    ModelProfile,
    CapabilityVector,
    CapabilitySource,
    CapabilityEntry,
    HardwareRequirements,
    PerformanceStats,
    ModelHealthStatus,
)
from backend.services.ollama_adapter import OllamaAdapter

logger = logging.getLogger("mrpl.discovery")


class ModelDiscoveryService:
    """
    Dynamically discovers installed Ollama models, parses architectural and
    tensor metadata, and constructs normalized ModelProfile representations.
    """

    def __init__(self, adapter: Optional[OllamaAdapter] = None):
        self.adapter = adapter or OllamaAdapter()

    def discover_all_models(self, overrides: Optional[Dict[str, Any]] = None) -> List[ModelProfile]:
        """
        Discovers all currently installed models in local Ollama and merges with
        any configured overrides.
        """
        overrides = overrides or {}
        raw_tags = self.adapter.list_tags()
        profiles: List[ModelProfile] = []

        for tag_info in raw_tags:
            name = tag_info.get("name", "")
            if not name:
                continue

            try:
                profile = self._build_profile_from_tag(tag_info, overrides.get(name, {}))
                profiles.append(profile)
            except Exception as e:
                logger.error(f"Error parsing metadata for model {name}: {e}", exc_info=True)

        return profiles

    def _build_profile_from_tag(self, tag_info: Dict[str, Any], override_config: Dict[str, Any]) -> ModelProfile:
        name = tag_info.get("name", "")
        digest = tag_info.get("digest", "")
        details = tag_info.get("details", {})
        capabilities_list = tag_info.get("capabilities", [])
        size_bytes = tag_info.get("size", 0)

        # Stable internal ID derived from digest or model tag
        if digest:
            clean_digest = digest.replace("sha256:", "")[:8]
            stable_id = f"model-{clean_digest}"
        else:
            stable_id = f"model-{hashlib.md5(name.encode('utf-8')).hexdigest()[:8]}"

        # Model details
        family = details.get("family", "unknown")
        parameter_size = details.get("parameter_size", "unknown")
        quantization = details.get("quantization_level", "Q4_K_M")
        context_length = details.get("context_length", 32768)

        # Base human-readable display name
        display_name = override_config.get("display_name") or self._generate_display_name(name, parameter_size)

        # Parse capabilities
        capabilities = self._detect_capabilities(name, family, capabilities_list, details, override_config.get("capabilities"))

        # Hardware requirements estimation
        hardware = self._estimate_hardware(parameter_size, size_bytes, override_config.get("hardware"))

        # Performance baseline
        perf_override = override_config.get("performance", {})
        performance = PerformanceStats(
            benchmark_score=float(perf_override.get("benchmark_score", 0.75)),
            latency_score=float(perf_override.get("latency_score", 0.80)),
        )

        return ModelProfile(
            id=stable_id,
            ollama_name=name,
            display_name=display_name,
            family=family,
            architecture=family,
            parameter_size=parameter_size,
            quantization=quantization,
            capabilities=capabilities,
            context_length=int(context_length),
            hardware=hardware,
            performance=performance,
            availability=True,
            health=ModelHealthStatus.HEALTHY,
            local_only=True,
            source="ollama",
            metadata={
                "size_bytes": size_bytes,
                "digest": digest,
                "ollama_capabilities": capabilities_list,
                "modified_at": tag_info.get("modified_at"),
            },
        )

    def _generate_display_name(self, name: str, param_size: str) -> str:
        clean = name.replace(":", " ").replace("-", " ").title()
        return f"{clean} ({param_size})"

    def _detect_capabilities(
        self,
        name: str,
        family: str,
        ollama_caps: List[str],
        details: Dict[str, Any],
        explicit_overrides: Optional[Dict[str, Any]],
    ) -> CapabilityVector:
        """
        Calculates capability vector with provenance:
        1. Explicit manual overrides -> source=MANUAL_OVERRIDE
        2. Ollama & architecture capabilities -> source=METADATA
        3. Known architectural signals -> source=METADATA
        4. Safe defaults -> source=DECLARED
        """
        caps_map = {
            "reasoning": CapabilityEntry(score=0.60, source=CapabilitySource.DECLARED),
            "coding": CapabilityEntry(score=0.50, source=CapabilitySource.DECLARED),
            "vision": CapabilityEntry(score=0.05, source=CapabilitySource.DECLARED),
            "document_understanding": CapabilityEntry(score=0.60, source=CapabilitySource.DECLARED),
            "mathematics": CapabilityEntry(score=0.55, source=CapabilitySource.DECLARED),
            "ocr": CapabilityEntry(score=0.05, source=CapabilitySource.DECLARED),
            "tool_use": CapabilityEntry(score=0.50, source=CapabilitySource.DECLARED),
            "general": CapabilityEntry(score=0.70, source=CapabilitySource.DECLARED),
        }

        # Ollama reported capabilities (Metadata)
        if "vision" in ollama_caps or "vl" in family.lower() or "vision" in name.lower():
            caps_map["vision"] = CapabilityEntry(score=0.95, source=CapabilitySource.METADATA, evidence="Ollama reported vision capability")
            caps_map["ocr"] = CapabilityEntry(score=0.90, source=CapabilitySource.METADATA, evidence="Multimodal vision architecture supports OCR")
            caps_map["document_understanding"] = CapabilityEntry(score=0.90, source=CapabilitySource.METADATA, evidence="Multimodal document understanding")

        if "tools" in ollama_caps:
            caps_map["tool_use"] = CapabilityEntry(score=0.80, source=CapabilitySource.METADATA, evidence="Ollama reported tools capability")

        if "thinking" in ollama_caps or "qwen3" in family.lower() or "r1" in name.lower():
            caps_map["reasoning"] = CapabilityEntry(score=0.95, source=CapabilitySource.METADATA, evidence="Ollama reported thinking / deep reasoning")
            caps_map["mathematics"] = CapabilityEntry(score=0.90, source=CapabilitySource.METADATA, evidence="Reasoning model math specialization")
            caps_map["document_understanding"] = CapabilityEntry(score=0.88, source=CapabilitySource.METADATA, evidence="Complex reasoning document support")

        # Name / family hints (weak signals)
        name_lower = name.lower()
        if "coder" in name_lower or "code" in name_lower:
            caps_map["coding"] = CapabilityEntry(score=0.95, source=CapabilitySource.METADATA, evidence="Coder architecture specialization")
            caps_map["mathematics"] = CapabilityEntry(score=0.85, source=CapabilitySource.METADATA)
            caps_map["reasoning"] = CapabilityEntry(score=0.82, source=CapabilitySource.METADATA)
            caps_map["tool_use"] = CapabilityEntry(score=0.85, source=CapabilitySource.METADATA)

        # Merge with explicit overrides (Authoritative)
        if explicit_overrides and isinstance(explicit_overrides, dict):
            for k, v in explicit_overrides.items():
                if k in caps_map:
                    if isinstance(v, dict):
                        caps_map[k] = CapabilityEntry(
                            score=float(v.get("score", 0.5)),
                            source=CapabilitySource.MANUAL_OVERRIDE,
                            evidence="User configured override",
                        )
                    else:
                        caps_map[k] = CapabilityEntry(
                            score=float(v),
                            source=CapabilitySource.MANUAL_OVERRIDE,
                            evidence="User configured override",
                        )

        return CapabilityVector(**caps_map)

    def _estimate_hardware(
        self,
        param_size_str: str,
        size_bytes: int,
        explicit_hw: Optional[Dict[str, Any]],
    ) -> HardwareRequirements:
        if size_bytes > 0:
            size_gb = size_bytes / (1024**3)
            est_vram = round(size_gb + 0.8, 1)
            req_ram = round(size_gb + 2.0, 1)
        else:
            m = re.search(r"(\d+(\.\d+)?)", param_size_str)
            if m:
                p_val = float(m.group(1))
                est_vram = round(p_val * 0.9 + 0.5, 1)
                req_ram = round(p_val * 1.2 + 1.0, 1)
            else:
                est_vram = 4.0
                req_ram = 6.0

        if explicit_hw and isinstance(explicit_hw, dict):
            return HardwareRequirements(
                estimated_vram_gb=float(explicit_hw.get("estimated_vram_gb", est_vram)),
                cpu_supported=bool(explicit_hw.get("cpu_supported", True)),
                gpu_supported=bool(explicit_hw.get("gpu_supported", True)),
                required_ram_gb=float(explicit_hw.get("required_ram_gb", req_ram)),
            )

        return HardwareRequirements(
            estimated_vram_gb=est_vram,
            cpu_supported=True,
            gpu_supported=True,
            required_ram_gb=req_ram,
        )
