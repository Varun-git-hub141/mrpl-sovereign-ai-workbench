"""
Test suite validating Phase 10A Four-Equipment Engineering Knowledge Base Coverage:
P-201, P-101, V-201, TK-201
"""

import pytest
from backend.services.hybrid_rag import HybridRAGService
from backend.models.rag_models import HybridSearchRequest

@pytest.fixture(scope="module")
def rag_service():
    rag = HybridRAGService()
    rag.index_knowledge_base()
    return rag

def test_four_equipment_knowledge_base_expansion(rag_service):
    stats = rag_service.get_stats()
    assert stats["total_documents"] >= 76, f"Expected at least 76 documents, found {stats['total_documents']}"
    assert stats["total_chunks"] >= 76

    required_tags = ["P-201", "P-101", "V-201", "TK-201"]
    for tag in required_tags:
        dossier = rag_service.get_equipment_dossier(tag)
        assert dossier.total_documents >= 14, f"Equipment {tag} has only {dossier.total_documents} documents (expected >= 14)"
        assert len(dossier.categories_covered) >= 8, f"Equipment {tag} covers only {len(dossier.categories_covered)} categories"
        assert len(dossier.retrieved_evidence) >= 14

def test_p101_equipment_dossier(rag_service):
    dossier = rag_service.get_equipment_dossier("P-101")
    assert dossier.total_documents >= 15
    cats = dossier.documents_by_category
    assert "Inspection Reports" in cats
    assert "Maintenance Records" in cats
    assert "P&IDs / Engineering Drawings" in cats
    assert "SOPs" in cats
    assert "Previous Engineering Decisions" in cats

    # Check inspection locations in text
    all_text = " ".join(c.text.lower() for c in dossier.retrieved_evidence)
    assert "suction nozzle" in all_text
    assert "discharge nozzle" in all_text
    assert "casing" in all_text

def test_v201_equipment_dossier(rag_service):
    dossier = rag_service.get_equipment_dossier("V-201")
    assert dossier.total_documents >= 20
    cats = dossier.documents_by_category
    assert "Inspection Reports" in cats
    assert "Maintenance Records" in cats
    assert "P&IDs / Engineering Drawings" in cats
    assert "SOPs" in cats
    assert "Previous Engineering Decisions" in cats

    all_text = " ".join(c.text.lower() for c in dossier.retrieved_evidence)
    assert "shell course" in all_text or "shell" in all_text
    assert "top head" in all_text or "head" in all_text

def test_tk201_equipment_dossier(rag_service):
    dossier = rag_service.get_equipment_dossier("TK-201")
    assert dossier.total_documents >= 14
    cats = dossier.documents_by_category
    assert "Inspection Reports" in cats
    assert "Maintenance Records" in cats
    assert "P&IDs / Engineering Drawings" in cats
    assert "SOPs" in cats
    assert "Previous Engineering Decisions" in cats

    all_text = " ".join(c.text.lower() for c in dossier.retrieved_evidence)
    assert "annular plate" in all_text or "bottom" in all_text
    assert "settlement" in all_text

def test_search_queries_all_four_equipments(rag_service):
    for tag in ["P-201", "P-101", "V-201", "TK-201"]:
        queries = [
            f"Find all documents for {tag}",
            f"Find all inspection evidence for {tag}",
            f"Find historical measurements for {tag}"
        ]
        for q in queries:
            req = HybridSearchRequest(query=q, top_k=3)
            res = rag_service.hybrid_search(req)
            assert len(res) > 0, f"Search query '{q}' returned 0 results"
            for chunk in res:
                assert chunk.source.document_id is not None
                assert chunk.source.document is not None
                assert chunk.source.section is not None
                assert chunk.source.page >= 1
                assert chunk.text is not None
