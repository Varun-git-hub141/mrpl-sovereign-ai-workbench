import os
import json
import yaml
import logging
import threading
from typing import Dict, List, Optional, Any
from backend.config import (
    MODEL_OVERRIDES_FILE,
    REGISTRY_CACHE_FILE,
    METRICS_DB_FILE,
)
from backend.models.model_profile import (
    ModelProfile,
    CapabilityVector,
    ModelHealthStatus,
)
from backend.services.discovery import ModelDiscoveryService

logger = logging.getLogger("mrpl.registry")


class ModelRegistry:
    """
    Central repository for Model Profiles, capability vectors, overrides,
    and rolling execution telemetry.
    """

    def __init__(self, discovery_service: Optional[ModelDiscoveryService] = None):
        self.discovery_service = discovery_service or ModelDiscoveryService()
        self._profiles: Dict[str, ModelProfile] = {}  # Key: stable_id
        self._name_to_id: Dict[str, str] = {}  # Key: ollama_name -> stable_id
        self._lock = threading.RLock()
        self.load_overrides()
        self.load_metrics()
        self.refresh_discovery()

    def load_overrides(self) -> Dict[str, Any]:
        """
        Loads configuration overrides from YAML file.
        """
        if MODEL_OVERRIDES_FILE.exists():
            try:
                with open(MODEL_OVERRIDES_FILE, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self._overrides = data.get("models", {})
                    return self._overrides
            except Exception as e:
                logger.error(f"Failed to read model overrides from {MODEL_OVERRIDES_FILE}: {e}")
        self._overrides = {}
        return self._overrides

    def save_overrides(self, new_overrides: Dict[str, Any]) -> bool:
        """
        Saves updated model capability and metadata overrides to YAML file.
        """
        with self._lock:
            try:
                data = {"models": new_overrides}
                with open(MODEL_OVERRIDES_FILE, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False)
                self._overrides = new_overrides
                self.refresh_discovery()
                return True
            except Exception as e:
                logger.error(f"Failed to write model overrides: {e}")
                return False

    def refresh_discovery(self) -> List[ModelProfile]:
        """
        Dynamically triggers Ollama model discovery and updates the registry.
        """
        with self._lock:
            discovered = self.discovery_service.discover_all_models(self._overrides)
            self._profiles.clear()
            self._name_to_id.clear()

            for p in discovered:
                # Merge existing performance telemetry if available
                if p.ollama_name in self._metrics:
                    m = self._metrics[p.ollama_name]
                    p.performance.total_calls = m.get("total_calls", 0)
                    p.performance.successful_calls = m.get("successful_calls", 0)
                    p.performance.avg_latency_ms = m.get("avg_latency_ms", p.performance.avg_latency_ms)
                    p.performance.p95_latency_ms = m.get("p95_latency_ms", p.performance.p95_latency_ms)
                    p.performance.recent_latencies = m.get("recent_latencies", [])
                    p.performance.success_rate = m.get("success_rate", 1.0)
                    p.performance.latency_score = m.get("latency_score", p.performance.latency_score)

                self._profiles[p.id] = p
                self._name_to_id[p.ollama_name] = p.id

            logger.info(f"ModelRegistry refreshed: {len(self._profiles)} active models registered.")
            return list(self._profiles.values())

    def get_all(self) -> List[ModelProfile]:
        with self._lock:
            return list(self._profiles.values())

    def get_by_id(self, model_id: str) -> Optional[ModelProfile]:
        with self._lock:
            return self._profiles.get(model_id)

    def get_by_name(self, ollama_name: str) -> Optional[ModelProfile]:
        with self._lock:
            mid = self._name_to_id.get(ollama_name)
            if mid:
                return self._profiles.get(mid)
            return None

    def update_capability_override(self, ollama_name: str, capabilities: Dict[str, float]) -> bool:
        """
        Modifies capability scores for a model and persists changes to YAML config.
        """
        with self._lock:
            self.load_overrides()
            if ollama_name not in self._overrides:
                self._overrides[ollama_name] = {}
            if "capabilities" not in self._overrides[ollama_name]:
                self._overrides[ollama_name]["capabilities"] = {}

            self._overrides[ollama_name]["capabilities"].update(capabilities)
            return self.save_overrides(self._overrides)

    def update_model_health(self, model_id: str, health: ModelHealthStatus, availability: bool):
        with self._lock:
            if model_id in self._profiles:
                self._profiles[model_id].health = health
                self._profiles[model_id].availability = availability

    def record_execution(
        self,
        model_name_or_id: str,
        latency_ms: float,
        success: bool,
        task_type: Optional[str] = None,
    ):
        """
        Records execution metadata (latency, success/failure) to continuously
        update latency and reliability scores without logging confidential prompt content.
        """
        with self._lock:
            profile = self.get_by_id(model_name_or_id) or self.get_by_name(model_name_or_id)
            if not profile:
                return

            name = profile.ollama_name
            if name not in self._metrics:
                self._metrics[name] = {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "recent_latencies": [],
                    "avg_latency_ms": latency_ms,
                    "p95_latency_ms": latency_ms,
                    "success_rate": 1.0,
                    "latency_score": 0.80,
                }

            m = self._metrics[name]
            m["total_calls"] += 1
            if success:
                m["successful_calls"] += 1

            recents = m["recent_latencies"]
            recents.append(latency_ms)
            if len(recents) > 30:
                recents.pop(0)

            # Recompute rolling stats
            m["avg_latency_ms"] = round(sum(recents) / len(recents), 2)
            sorted_lat = sorted(recents)
            p95_idx = int(len(sorted_lat) * 0.95)
            m["p95_latency_ms"] = round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 2)
            m["success_rate"] = round(m["successful_calls"] / m["total_calls"], 3)

            # Compute normalized latency score (scale 0.3 to 1.0)
            avg_l = m["avg_latency_ms"]
            m["latency_score"] = round(max(0.3, min(1.0, 1.0 - (avg_l / 40000.0))), 2)

            # Update live profile in memory
            profile.performance.total_calls = m["total_calls"]
            profile.performance.successful_calls = m["successful_calls"]
            profile.performance.avg_latency_ms = m["avg_latency_ms"]
            profile.performance.p95_latency_ms = m["p95_latency_ms"]
            profile.performance.recent_latencies = m["recent_latencies"]
            profile.performance.success_rate = m["success_rate"]
            profile.performance.latency_score = m["latency_score"]

            self._save_metrics()

    def load_metrics(self):
        self._metrics = {}
        if METRICS_DB_FILE.exists():
            try:
                with open(METRICS_DB_FILE, "r", encoding="utf-8") as f:
                    self._metrics = json.load(f)
            except Exception as e:
                logger.error(f"Error loading metrics DB: {e}")

    def _save_metrics(self):
        try:
            with open(METRICS_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self._metrics, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metrics DB: {e}")
