import pytest
from backend.services.policy_engine import PolicyEngine
from backend.telemetry.audit import NetworkEgressGuard
from backend.models.model_profile import ModelProfile
from backend.models.task_profile import TaskProfile, RiskLevel


def test_airgap_and_policy_enforcement():
    policy = PolicyEngine()

    # Local model
    local_model = ModelProfile(
        id="model-local",
        ollama_name="local:3b",
        display_name="Local Model",
        local_only=True,
    )
    task = TaskProfile(risk=RiskLevel.LOW)
    res = policy.evaluate_model_policy(local_model, task)
    assert res["allowed"] is True

    # Cloud model attempt
    cloud_model = ModelProfile(
        id="model-cloud",
        ollama_name="cloud:3b",
        display_name="Cloud Model",
        local_only=False,
    )
    res_cloud = policy.evaluate_model_policy(cloud_model, task)
    assert res_cloud["allowed"] is False
    assert "air-gap" in res_cloud["reasons"][0].lower()


def test_network_egress_guard():
    # Local address allowed
    assert NetworkEgressGuard.validate_url("http://127.0.0.1:11434") is True
    assert NetworkEgressGuard.validate_url("http://localhost:11434") is True

    # External addresses blocked
    assert NetworkEgressGuard.validate_url("https://api.openai.com/v1") is False
    assert NetworkEgressGuard.validate_url("https://api.anthropic.com/v1") is False
    assert NetworkEgressGuard.validate_url("https://huggingface.co/api") is False

    status = NetworkEgressGuard.get_sovereignty_status()
    assert status["external_llm_calls"] >= 3
    assert status["air_gap_active"] is True
