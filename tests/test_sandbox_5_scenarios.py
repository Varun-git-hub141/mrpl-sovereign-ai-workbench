import sys
import os
import json

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.code_sandbox.code_sandbox_service import CodeSandboxService
from backend.services.code_sandbox.code_verification_engine import CodeVerificationEngine
from backend.models.code_sandbox_models import VerificationStatus, ExecutionStatus

def run_tests():
    engine = CodeVerificationEngine()
    print("=" * 60)
    print("RUNNING 5 SANDBOX VERIFICATION CONTRACT TESTS")
    print("=" * 60)

    # Test 1 — Fibonacci (uses def fibonacci_sequence)
    print("\n--- TEST 1: FIBONACCI (def fibonacci_sequence) ---")
    code1 = """def fibonacci_sequence(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    seq = [0, 1]
    while len(seq) < n:
        seq.append(seq[-1] + seq[-2])
    return seq

print("Fibonacci sequence up to 10 numbers:", fibonacci_sequence(10))
"""
    rcpt1 = engine.execute_and_verify(code1, query="Write python code for fibonacci sequence")
    print(f"Verification Status: {rcpt1.verification_status}")
    print(f"Execution Status: {rcpt1.execution_status}, Exit Code: {rcpt1.exit_code}")
    print(f"Tests Passed: {rcpt1.tests_passed}/{rcpt1.total_tests}")
    assert rcpt1.verification_status == VerificationStatus.VERIFIED, f"Expected VERIFIED, got {rcpt1.verification_status}"
    assert rcpt1.exit_code == 0
    assert rcpt1.tests_passed >= 2
    print("[OK] TEST 1 PASSED: VERIFIED (Exit Code 0, 2/2 tests passed)")

    # Test 2 — Two Sum (uses def two_sum)
    print("\n--- TEST 2: TWO SUM (def two_sum) ---")
    code2 = """def two_sum(nums, target):
    lookup = {}
    for i, num in enumerate(nums):
        diff = target - num
        if diff in lookup:
            return [lookup[diff], i]
        lookup[num] = i
    return []
"""
    rcpt2 = engine.execute_and_verify(code2, query="Write python code for Two Sum")
    print(f"Verification Status: {rcpt2.verification_status}")
    print(f"Execution Status: {rcpt2.execution_status}, Exit Code: {rcpt2.exit_code}")
    print(f"Tests Passed: {rcpt2.tests_passed}/{rcpt2.total_tests}")
    assert rcpt2.verification_status == VerificationStatus.VERIFIED, f"Expected VERIFIED, got {rcpt2.verification_status}"
    assert rcpt2.exit_code == 0
    assert rcpt2.tests_passed >= 2
    print("[OK] TEST 2 PASSED: VERIFIED (Exit Code 0, Tests Pass)")

    # Test 3 — Runtime failure (intentional runtime error)
    print("\n--- TEST 3: RUNTIME FAILURE (1/0 division error) ---")
    code3 = """def calculate():
    x = 10 / 0
    return x

calculate()
"""
    rcpt3 = engine.execute_and_verify(code3, query="Calculate division")
    print(f"Verification Status: {rcpt3.verification_status}")
    print(f"Execution Status: {rcpt3.execution_status}, Exit Code: {rcpt3.exit_code}")
    print(f"Error Message: {rcpt3.error_message}")
    assert rcpt3.verification_status == VerificationStatus.EXECUTION_FAILED, f"Expected EXECUTION_FAILED, got {rcpt3.verification_status}"
    assert rcpt3.exit_code != 0
    print("[OK] TEST 3 PASSED: EXECUTION_FAILED (Non-zero exit code, error captured)")

    # Test 4 — Wrong result (returns incorrect answer)
    print("\n--- TEST 4: WRONG RESULT (two_sum returns [0, 0]) ---")
    code4 = """def two_sum(nums, target):
    return [0, 0]  # Incorrect logic
"""
    rcpt4 = engine.execute_and_verify(code4, query="Write python code for Two Sum")
    print(f"Verification Status: {rcpt4.verification_status}")
    print(f"Execution Status: {rcpt4.execution_status}, Exit Code: {rcpt4.exit_code}")
    print(f"Tests Passed: {rcpt4.tests_passed}/{rcpt4.total_tests}")
    assert rcpt4.verification_status == VerificationStatus.VERIFICATION_FAILED, f"Expected VERIFICATION_FAILED, got {rcpt4.verification_status}"
    print("[OK] TEST 4 PASSED: VERIFICATION_FAILED (Code ran cleanly, tests failed)")

    # Test 5 — Harness mismatch (unsupported/missing callable name)
    print("\n--- TEST 5: HARNESS MISMATCH (unsupported callable name) ---")
    code5 = """def my_unrelated_custom_function(x):
    return x * 2

print("Running custom script:", my_unrelated_custom_function(21))
"""
    rcpt5 = engine.execute_and_verify(code5, query="Write python code for fibonacci sequence")
    print(f"Verification Status: {rcpt5.verification_status}")
    print(f"Execution Status: {rcpt5.execution_status}, Exit Code: {rcpt5.exit_code}")
    print(f"Error Message: {rcpt5.error_message}")
    assert rcpt5.verification_status == VerificationStatus.VERIFICATION_HARNESS_ERROR, f"Expected VERIFICATION_HARNESS_ERROR, got {rcpt5.verification_status}"
    assert rcpt5.execution_status == ExecutionStatus.SUCCESS, "Sandbox execution should be SUCCESS"
    assert "No permitted Fibonacci callable found" in rcpt5.error_message
    print("[OK] TEST 5 PASSED: VERIFICATION_HARNESS_ERROR (Execution SUCCESS, Exit Code 0, Reason: No permitted callable found)")

    print("\n" + "=" * 60)
    print("ALL 5 LIVE TEST CASES COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
