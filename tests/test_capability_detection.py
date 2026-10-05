import pytest
from backend.services.discovery import ModelDiscoveryService
from backend.services.capability_probe import CapabilityProbeService
from backend.models.model_profile import CapabilitySource, CapabilityEntry, ModelProfile


class MockProbeAdapter:
    def generate(self, model, prompt, system=None, images=None, options=None):
        if "lowest vibration" in prompt:
            return {"success": True, "response": "P-103 has lowest vibration"}
        if "function `add(a, b)`" in prompt:
            return {"success": True, "response": "def add(a, b):\n    return a + b"}
        if "Calculate" in prompt:
            return {"success": True, "response": "0.72 mm/year"}
        return {"success": True, "response": "OK"}


def test_capability_provenance_tracking():
    probe_svc = CapabilityProbeService(adapter=MockProbeAdapter())
    
    # Create test profile
    model = ModelProfile(
        id="model-test",
        ollama_name="test-model:3b",
        display_name="Test Model",
        family="test",
        parameter_size="3B",
        quantization="Q4_K_M",
    )
    
    # Initial source is unknown/declared
    assert model.capabilities.reasoning.source in [CapabilitySource.UNKNOWN, CapabilitySource.DECLARED]
    
    # Run probe
    result = probe_svc.probe_model(model)
    
    # Provenance source must now be PROBE
    assert model.capabilities.reasoning.source == CapabilitySource.PROBE
    assert model.capabilities.reasoning.score >= 0.80
    assert model.capabilities.coding.source == CapabilitySource.PROBE
    assert model.capabilities.coding.score >= 0.80
