import pytest
from backend.services.discovery import ModelDiscoveryService
from backend.models.model_profile import CapabilityVector, ModelHealthStatus


class MockAdapter:
    def list_tags(self):
        return [
            {
                "name": "qwen2.5-coder:3b",
                "digest": "f72c60cabf6237b07f6e632b2c48d533cef25eda2efbd34bed21c5e9c01e6225",
                "size": 1929912626,
                "details": {
                    "family": "qwen2",
                    "parameter_size": "3.1B",
                    "quantization_level": "Q4_K_M",
                    "context_length": 32768,
                },
                "capabilities": ["completion", "tools", "insert"],
            },
            {
                "name": "qwen3:4b",
                "digest": "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7",
                "size": 2497293931,
                "details": {
                    "family": "qwen3",
                    "parameter_size": "4.0B",
                    "quantization_level": "Q4_K_M",
                    "context_length": 262144,
                },
                "capabilities": ["completion", "tools", "thinking"],
            },
            {
                "name": "qwen2.5vl:3b",
                "digest": "fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1",
                "size": 3200627168,
                "details": {
                    "family": "qwen25vl",
                    "parameter_size": "3.8B",
                    "quantization_level": "Q4_K_M",
                    "context_length": 128000,
                },
                "capabilities": ["vision", "completion"],
            },
        ]


def test_model_discovery_parsing():
    discovery = ModelDiscoveryService(adapter=MockAdapter())
    profiles = discovery.discover_all_models()

    assert len(profiles) == 3

    # Test Coder Profile
    coder = next(p for p in profiles if "coder" in p.ollama_name)
    assert coder.id.startswith("model-f72c60ca")
    assert coder.family == "qwen2"
    assert coder.parameter_size == "3.1B"
    assert coder.capabilities.coding >= 0.85
    assert coder.local_only is True
    assert coder.health == ModelHealthStatus.HEALTHY

    # Test Vision Profile
    vl = next(p for p in profiles if "vl" in p.ollama_name)
    assert vl.id.startswith("model-fb90415c")
    assert vl.capabilities.vision >= 0.90
    assert vl.capabilities.ocr >= 0.85

    # Test Reasoning Profile
    q3 = next(p for p in profiles if p.ollama_name == "qwen3:4b")
    assert q3.id.startswith("model-359d7dd4")
    assert q3.capabilities.reasoning >= 0.90
    assert q3.context_length == 262144


def test_override_precedence():
    discovery = ModelDiscoveryService(adapter=MockAdapter())
    overrides = {
        "qwen2.5-coder:3b": {
            "display_name": "Custom Coder Special",
            "capabilities": {
                "coding": 0.99,
                "vision": 0.40,
            },
        }
    }
    profiles = discovery.discover_all_models(overrides=overrides)
    coder = next(p for p in profiles if "coder" in p.ollama_name)

    assert coder.display_name == "Custom Coder Special"
    assert coder.capabilities.coding == 0.99
    assert coder.capabilities.vision == 0.40
