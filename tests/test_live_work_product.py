# tests/test_live_work_product.py
import os
import json
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.models.work_product_models import DeliverableStatus

@pytest.fixture
def client():
    return TestClient(app)

def test_live_work_product(client):
    print("======================================================================")
    print("  TESTING LIVE WORK PRODUCT ENDPOINTS & VERIFICATION")
    print("======================================================================")
    
    # 1. Test direct work product endpoint
    res = client.post("/api/work-products/generate", json={
        "entity_tag": "V-201",
        "query": "Generate V-201 Inspection Review Note"
    })
    assert res.status_code == 200
    res_data = res.json()
    
    print("\n1. Direct /api/work-products/generate Response:")
    print(f"   Status: {res_data.get('status')}")
    print(f"   Work Product Title: {res_data.get('work_product', {}).get('title')}")
    print(f"   Download URL: {res_data.get('download_url')}")
    print(f"   Calculations count: {len(res_data.get('work_product', {}).get('calculations', []))}")
    receipt = res_data.get("verification_receipt") or {}
    print(f"   Receipt Status: {receipt.get('status')}")
    print(f"   Receipt Checks Passed: {receipt.get('checks_passed')}/{receipt.get('checks_total')}")
    
    assert receipt.get("status") == "VERIFIED_DELIVERABLE"
    assert res_data.get("status") == "VERIFIED_DELIVERABLE"
    assert receipt.get("checks_failed") == 0

    # 2. Test download endpoint
    dl_url = res_data.get("download_url")
    dl_res = client.get(dl_url)
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 1000
    print(f"\n2. Download response size: {len(dl_res.content)} bytes")

    # 3. Test orchestrator execution path via /api/execute
    exec_res = client.post("/api/execute", json={
        "query": "Generate V-201 Inspection Review Note"
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    
    print("\n3. Orchestrator /api/execute Response:")
    print(f"   Is Verified Work Product: {exec_data.get('is_verified_work_product')}")
    wp = exec_data.get("generated_work_product", {})
    wp_receipt = exec_data.get("deliverable_verification_receipt", {})
    print(f"   WP Title: {wp.get('title')}")
    print(f"   Receipt Status: {wp_receipt.get('status')}")
    
    assert exec_data.get("is_verified_work_product") is True
    assert wp_receipt.get("status") == "VERIFIED_DELIVERABLE"

    print("\n======================================================================")
    print("  ALL LIVE WORK PRODUCT TESTS PASSED SUCCESSFULLY (100%)")
    print("======================================================================")

if __name__ == "__main__":
    test_client = TestClient(app)
    test_live_work_product(test_client)

