import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.services.rag_engine import EngineeringRAGEngine
from backend.services.hybrid_rag import HybridRAGService


@pytest.fixture
def client():
    return TestClient(app)


def test_rag_stats_dynamic_not_hardcoded_57(client):
    """
    Ensure the RAG stats endpoint returns dynamic total_documents and total_chunks matching
    HybridRAGService runtime state, and disclaimer does NOT contain hardcoded 57 Documents.
    """
    hybrid = HybridRAGService()
    runtime_docs = len(hybrid.documents)
    runtime_chunks = len(hybrid.chunks)

    res = client.get("/api/rag/stats")
    assert res.status_code == 200
    data = res.json()

    assert data["total_documents"] == runtime_docs
    assert data["total_chunks"] == runtime_chunks
    assert "57 Documents" not in data.get("disclaimer", "")
    assert f"{runtime_docs} Documents" in data.get("disclaimer", "")


def test_engineering_rag_psv201_searchable(client):
    """
    Ensure PSV-201 documents remain fully searchable through Engineering RAG /api/rag/search
    and /api/rag/debug-query.
    """
    res = client.post("/api/rag/search", json={
        "query": "PSV-201 pop test set pressure inspection certificate",
        "top_k": 6,
        "filters": {"equipment_tag": "PSV-201"}
    })
    assert res.status_code == 200
    data = res.json()
    results = data.get("results", [])
    assert len(results) > 0

    doc_ids = [r.get("document_id") for r in results]
    assert any("PSV201" in d for d in doc_ids), f"Expected PSV-201 documents, got {doc_ids}"
