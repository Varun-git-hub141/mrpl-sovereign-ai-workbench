import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health/system")
    assert res.status_code == 200
    data = res.json()
    assert "ollama" in data
    assert "hardware" in data
    assert "models" in data


def test_api_sovereignty_status():
    res = client.get("/api/sovereignty/status")
    assert res.status_code == 200
    data = res.json()
    assert data["air_gap_active"] is True
    assert data["data_leaves_machine"] is False


def test_api_registry_models():
    res = client.get("/api/registry/models")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 3
    model_names = [m["ollama_name"] for m in data["models"]]
    assert "qwen2.5-coder:3b" in model_names
    assert "qwen3:4b" in model_names
    assert "qwen2.5vl:3b" in model_names


def test_api_route_endpoint():
    # Coding query
    res = client.post(
        "/api/route",
        json={"query": "Write Python code to calculate corrosion rate from thickness survey."},
    )
    assert res.status_code == 200
    data = res.json()
    assert "task_profile" in data
    assert "execution_plan" in data
    assert data["task_profile"]["task_type"] in ["coding", "engineering_calculation"]
    assert data["execution_plan"]["primary_model"]["ollama_name"] == "qwen2.5-coder:3b"


def test_api_route_vision_endpoint():
    # P&ID query with image file
    res = client.post(
        "/api/route",
        json={
            "query": "Analyze this P&ID diagram and identify valves on pump suction.",
            "files": [{"name": "pid.png", "size": 100000}],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["task_profile"]["task_type"] == "multimodal_document_analysis"
    assert data["execution_plan"]["primary_model"]["ollama_name"] == "qwen2.5vl:3b"
    assert data["execution_plan"]["vision_required"] is True


def test_api_route_high_risk_endpoint():
    # Equipment approval query
    res = client.post(
        "/api/route",
        json={"query": "Should P-101 be approved for continued operation?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["task_profile"]["risk"] == "high"
    assert data["verification_required"] is True
    assert data["execution_plan"]["primary_model"]["role"] == "primary"
    assert data["execution_plan"]["verifier_model"] is not None
    assert data["execution_plan"]["human_approval_required"] is True
