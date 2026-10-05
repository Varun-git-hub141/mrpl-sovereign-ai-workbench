import urllib.request
import json

def test_api():
    print("Testing /api/execute for Fibonacci...")
    req_data = json.dumps({"query": "Write python code for fibonacci sequence"}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/execute",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode("utf-8"))
        cv = res.get("code_verification_receipt")
        print("Response received:")
        print(f"  Model Executed: {res.get('model_actually_executed')}")
        print(f"  Execution Status: {res.get('execution_status')}")
        if cv:
            print(f"  Code Verification Status: {cv.get('verification_status')}")
            print(f"  Exit Code: {cv.get('exit_code')}")
            print(f"  Tests Passed: {cv.get('tests_passed')}/{cv.get('total_tests')}")
            print(f"  Duration: {cv.get('duration_ms')} ms")
            print(f"  Network Disabled: {cv.get('network_disabled_status')}")
            assert cv.get("verification_status") == "VERIFIED", f"Expected VERIFIED, got {cv.get('verification_status')}"
            assert cv.get("exit_code") == 0
            assert cv.get("tests_passed") >= 2
        else:
            print("  Warning: No code_verification_receipt in response")

    print("\nTesting /api/history to verify Generic Coding label and CODE badge...")
    req_h = urllib.request.Request("http://127.0.0.1:8000/api/history?limit=3")
    with urllib.request.urlopen(req_h) as response:
        hist = json.loads(response.read().decode("utf-8"))
        items = hist.get("items", [])
        if items:
            latest = items[0]
            print(f"  Latest Activity Query: {latest.get('query')}")
            print(f"  File Badge: {latest.get('file_badge')} (Badge Class: {latest.get('badge_class')})")
            print(f"  Operation Type: {latest.get('operation_type')}")
            assert latest.get("file_badge") != "RAG", "Generic coding should NOT have RAG badge"
            print("  [OK] History verified: NOT labeled as RAG!")

    print("\nAPI E2E Test completed successfully!")

if __name__ == "__main__":
    test_api()
