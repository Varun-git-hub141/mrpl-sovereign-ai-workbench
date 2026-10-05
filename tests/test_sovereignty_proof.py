import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.telemetry.audit import (
    record_network_event,
    get_live_sovereignty_telemetry,
    run_sovereignty_test,
    build_sovereignty_proof,
)

client = TestClient(app)


def test_sovereignty_telemetry_endpoint():
    """Verify GET /api/sovereignty/telemetry returns full air-gap and runtime telemetry."""
    response = client.get("/api/sovereignty/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert data["endpoint"] == "127.0.0.1:11434"
    assert data["provider"] == "Ollama"
    assert isinstance(data["external_calls"], int)
    assert data["data_egress_bytes"] == 0
    assert data["external_ai_apis"] == "NONE"
    assert data["session_airgap_verified"] is True

    # Check 3-tier air-gap levels
    assert "airgap_levels" in data
    levels = data["airgap_levels"]
    assert levels["level_1_application"]["status"] == "VERIFIED"
    assert levels["level_1_application"]["external_ai_providers_configured"] == 0
    assert levels["level_2_host_network"]["policy"] == "Application-level sovereignty verified."
    assert "Physical air-gap status must be verified by infrastructure controls." in levels["level_3_physical_airgap"]["disclaimer"]

    # Check models list
    assert "models_status" in data
    assert len(data["models_status"]) > 0
    for m in data["models_status"]:
      assert m["location"] == "LOCAL"
      assert m["provider"] == "Ollama"
      assert m["endpoint"] == "127.0.0.1:11434"
      assert m["external_provider"] == "NONE"

    # Check network activity structure
    assert "network_activity" in data
    assert "summary" in data["network_activity"]
    summary = data["network_activity"]["summary"]
    assert summary["data_egress_bytes"] == 0


def test_sovereignty_test_endpoint():
    """Verify POST /api/sovereignty/test runs empirical probe and returns signed proof."""
    response = client.post("/api/sovereignty/test")
    assert response.status_code == 200
    data = response.json()

    assert data["result"] == "PASS"
    assert data["test_id"].startswith("SOV-TEST-")
    assert "timestamp" in data
    assert "inference_latency_ms" in data

    checks = data["checks"]
    assert checks["ollama_reachable"] is True
    assert checks["local_model_discovered"] is True
    assert checks["local_inference_successful"] is True
    assert checks["endpoint"] == "127.0.0.1:11434"
    assert checks["external_ai_providers"] == 0
    assert checks["external_inference_calls"] == 0
    assert checks["model_downloads"] == 0


def test_record_network_event_ring_buffer():
    """Verify network event recording adds to telemetry log correctly."""
    record_network_event(
        destination="127.0.0.1:11434",
        event_type="Ollama Unit Test",
        status="ALLOWED",
        payload_bytes=256
    )
    telem = get_live_sovereignty_telemetry()
    events = telem["network_activity"]["events"]
    assert any(e["destination"] == "127.0.0.1:11434" and e["type"] == "Ollama Unit Test" for e in events)
    assert isinstance(telem["external_calls"], int)
    assert telem["data_egress_bytes"] == 0


def test_build_sovereignty_proof_dynamic_model():
    """Verify build_sovereignty_proof reflects the real selected model, never hardcoding."""
    proof_custom = build_sovereignty_proof(
        task_id="TASK-UNIT-101",
        selected_model="custom-qwen-test:7b",
        execution_timeline=[
            {"step": "Task Analyzer", "time": "10:00:00", "detail": "DOMAIN=ENGINEERING"},
            {"step": "Model Router", "time": "10:00:01", "detail": "Selected: custom-qwen-test:7b"},
            {"step": "Local Ollama", "time": "10:00:02", "detail": "127.0.0.1:11434"},
            {"step": "Inference completed", "time": "10:00:03", "detail": "Latency 450ms"}
        ]
    )

    assert proof_custom["selected_model"] == "custom-qwen-test:7b"
    assert proof_custom["execution_mode"] == "LOCAL"
    assert proof_custom["inference_endpoint"] == "127.0.0.1:11434"
    assert proof_custom["provider"] == "Ollama"
    assert proof_custom["network_mode"] == "LOCAL ONLY"
    assert proof_custom["external_api"] == "NONE"
    assert proof_custom["sovereignty_status"] == "LOCAL_VERIFIED"
    assert len(proof_custom["execution_timeline"]) == 4


def test_orchestration_execution_contains_sovereignty_proof():
    """Verify executing a task via /api/execute returns a valid sovereignty proof."""
    req_body = {
        "query": "What is the wall thickness of P-201?",
    }
    response = client.post("/api/execute", json=req_body)
    assert response.status_code == 200
    data = response.json()

    assert "sovereignty_proof" in data
    proof = data["sovereignty_proof"]
    assert proof["execution_mode"] == "LOCAL"
    assert proof["inference_endpoint"] == "127.0.0.1:11434"
    assert proof["provider"] == "Ollama"
    assert proof["network_mode"] == "LOCAL ONLY"
    assert proof["external_api"] == "NONE"
    assert proof["sovereignty_status"] == "LOCAL_VERIFIED"
    assert len(proof["execution_timeline"]) >= 3
