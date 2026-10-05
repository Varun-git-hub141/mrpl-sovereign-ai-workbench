"""
MRPL SOVEREIGN AI WORKBENCH — CODER SANDBOX EXECUTION PROOF & RECEIPT TEST SUITE

Tests that the CodeVerificationEngine NEVER infers code execution from LLM claims,
tool list presence, or UI state, but strictly trusts machine-generated, cryptographically
signed SandboxExecutionReceipt instances produced by CodeSandboxService.

Test Cases:
1. NEGATIVE TEST 1: Deliberately bypass CodeSandboxService -> pass code directly to CodeVerificationEngine
   -> Expected: VERIFICATION_FAILED with reason "NO_SANDBOX_EXECUTION_RECEIPT"
2. NEGATIVE TEST 2: Provide fabricated / tampered / fake execution receipt
   -> Expected: Rejection with FABRICATED_OR_INVALID_RECEIPT / signature failure
3. NEGATIVE TEST 3: Code hash mismatch (receipt for different code)
   -> Expected: Rejection with CODE_HASH_MISMATCH
4. POSITIVE TEST: Coder generates Two Sum code -> passes to CodeSandboxService -> launches in isolated sandbox
   -> Captures all required receipt fields (execution_id, exit_code, stdout, duration, hash, isolation, network disabled)
   -> CodeVerificationEngine consumes receipt -> runs deterministic assertions -> VERIFIED
5. NEGATIVE TEST 4: Buggy code -> sandbox execution fails or test assertion fails -> VERIFICATION_FAILED
6. NEGATIVE TEST 5: Security / Network egress attempt -> blocked with 0 network egress
7. LIFECYCLE PROGRESSION TEST: Verifies all required lifecycle states:
   GENERATING -> GENERATED -> EXECUTING_IN_SANDBOX -> SANDBOX_EXECUTION_COMPLETE -> TESTS_EXECUTED -> VERIFYING -> VERIFIED
"""

import sys
import os
import unittest
import hashlib
import time

sys.path.insert(0, os.path.abspath("."))

from backend.models.code_sandbox_models import (
    CodeExecutionRequest,
    SandboxExecutionReceipt,
    CodeVerificationReceipt,
    ExecutionStatus,
    VerificationStatus,
    SandboxStatus,
    NetworkAccessState,
)
from backend.services.code_sandbox.code_sandbox_service import CodeSandboxService
from backend.services.code_sandbox.code_verification_engine import CodeVerificationEngine


class TestCoderSandboxExecutionProof(unittest.TestCase):
    def setUp(self):
        self.sandbox = CodeSandboxService(default_timeout=5.0)
        self.verifier = CodeVerificationEngine(sandbox_service=self.sandbox)

    def test_negative_1_bypass_sandbox_rejected_no_receipt(self):
        """
        NEGATIVE TEST 1:
        Generate code but deliberately bypass CodeSandboxService.
        Pass the code directly to CodeVerificationEngine.
        Expected: VERIFICATION_FAILED with reason "NO_SANDBOX_EXECUTION_RECEIPT".
        """
        code = """
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        diff = target - n
        if diff in seen:
            return [seen[diff], i]
        seen[n] = i
    return []
"""
        # Call verify_code without an execution_receipt
        receipt = self.verifier.verify_code(
            req_or_code=code,
            execution_receipt=None,  # Deliberate bypass!
            language="python",
            query="Write Python code for Two Sum",
        )

        self.assertEqual(receipt.verification_status, VerificationStatus.VERIFICATION_FAILED)
        self.assertEqual(receipt.failure_reason, "NO_SANDBOX_EXECUTION_RECEIPT")
        self.assertIn("NO_SANDBOX_EXECUTION_RECEIPT", receipt.error_message)
        self.assertFalse(receipt.receipt_signature_verified)

    def test_negative_2_fabricated_fake_receipt_rejected(self):
        """
        NEGATIVE TEST 2:
        Provide a fabricated/fake execution receipt.
        Expected: Rejected unless it can be cryptographically/structurally tied to an actual sandbox execution.
        """
        code = "def two_sum(nums, target): return [0, 1]"
        fake_hash = hashlib.sha256(code.encode()).hexdigest()

        fake_receipt = SandboxExecutionReceipt(
            execution_id="sandbox-fake-forged-id-123",
            status="SUCCESS",
            exit_code=0,
            stdout="Fake output claiming it passed",
            stderr="",
            duration=0.05,
            duration_ms=50,
            code_hash=fake_hash,
            sandbox_isolation_status=SandboxStatus.ISOLATED,
            network_disabled_status=NetworkAccessState.DISABLED,
            signature="deadbeef_totally_fake_signature_not_from_sandbox",  # Forged signature
        )

        receipt = self.verifier.verify_code(
            req_or_code=code,
            execution_receipt=fake_receipt,
            language="python",
            query="Write Python code for Two Sum",
        )

        self.assertEqual(receipt.verification_status, VerificationStatus.VERIFICATION_FAILED)
        self.assertEqual(receipt.failure_reason, "FABRICATED_OR_INVALID_RECEIPT")
        self.assertFalse(receipt.receipt_signature_verified)

    def test_negative_3_code_hash_mismatch_rejected(self):
        """
        NEGATIVE TEST 3:
        Receipt is valid for Code A, but submitted for verification with modified Code B.
        Expected: Rejected due to code hash mismatch.
        """
        code_a = "def add(a, b): return a + b"
        code_b = "def add(a, b): return a * b"  # Tampered/Different code

        # Execute code_a to get authentic receipt
        receipt_a = self.sandbox.execute_code(CodeExecutionRequest(code=code_a))
        self.assertEqual(receipt_a.status, "SUCCESS")

        # Pass receipt_a with code_b
        res = self.verifier.verify_code(
            req_or_code=code_b,
            execution_receipt=receipt_a,
            language="python",
        )

        self.assertEqual(res.verification_status, VerificationStatus.VERIFICATION_FAILED)
        self.assertEqual(res.failure_reason, "FABRICATED_OR_INVALID_RECEIPT")
        self.assertIn("CODE_HASH_MISMATCH", res.error_message)

    def test_positive_flow_two_sum_full_execution_proof(self):
        """
        POSITIVE TEST: Full required lifecycle flow:
        1. Coder generates code
        2. Exact code passed to CodeSandboxService
        3. CodeSandboxService executes in isolated sandbox
        4. Captures execution_id, exit_code, stdout, stderr, timestamps, duration, hash, isolation, network disabled, signature
        5. CodeVerificationEngine consumes receipt and runs deterministic assertions
        6. VERIFIED status achieved.
        """
        two_sum_code = """
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

if __name__ == "__main__":
    print(two_sum([2, 7, 11, 15], 9))
"""
        # 1. Application passes exact generated code to CodeSandboxService
        sandbox_receipt = self.sandbox.execute_code(CodeExecutionRequest(
            code=two_sum_code,
            language="python",
            timeout_seconds=5.0,
        ))

        # Check all required captured fields on machine receipt
        self.assertTrue(sandbox_receipt.execution_id.startswith("sandbox-"))
        self.assertEqual(sandbox_receipt.status, "SUCCESS")
        self.assertEqual(sandbox_receipt.exit_code, 0)
        self.assertIn("[0, 1]", sandbox_receipt.stdout)
        self.assertEqual(sandbox_receipt.stderr, "")
        self.assertGreater(sandbox_receipt.duration_ms, 0)
        self.assertEqual(sandbox_receipt.sandbox_isolation_status, SandboxStatus.ISOLATED)
        self.assertEqual(sandbox_receipt.network_disabled_status, NetworkAccessState.DISABLED)
        self.assertTrue(len(sandbox_receipt.signature) > 20)
        self.assertTrue(len(sandbox_receipt.code_hash) == 64)

        # 2. CodeVerificationEngine consumes that receipt
        verif_receipt = self.verifier.verify_code(
            req_or_code=two_sum_code,
            execution_receipt=sandbox_receipt,
            language="python",
            query="Write Python code for Two Sum",
        )

        # Verification asserts
        self.assertEqual(verif_receipt.verification_status, VerificationStatus.VERIFIED)
        self.assertEqual(verif_receipt.execution_status, ExecutionStatus.SUCCESS)
        self.assertEqual(verif_receipt.exit_code, 0)
        self.assertTrue(verif_receipt.receipt_signature_verified)
        self.assertEqual(verif_receipt.tests_passed, 3)  # 3 deterministic assertions
        self.assertEqual(verif_receipt.tests_failed, 0)
        self.assertEqual(verif_receipt.execution_id, sandbox_receipt.execution_id)
        self.assertEqual(verif_receipt.network_disabled_status, NetworkAccessState.DISABLED)

        # Verify lifecycle stages present
        stage_names = [s["stage"] for s in verif_receipt.lifecycle_stages]
        self.assertIn("GENERATING", stage_names)
        self.assertIn("GENERATED", stage_names)
        self.assertIn("EXECUTING_IN_SANDBOX", stage_names)
        self.assertIn("SANDBOX_EXECUTION_COMPLETE", stage_names)
        self.assertIn("TESTS_EXECUTED", stage_names)
        self.assertIn("VERIFIED", stage_names)

    def test_negative_4_buggy_code_assertions_failed(self):
        """
        NEGATIVE TEST 4:
        Code generates incorrect results for Two Sum.
        Receipt exists and exit_code is 0, but deterministic assertion tests fail.
        Expected: VERIFICATION_FAILED with reason TEST_ASSERTIONS_FAILED.
        """
        buggy_code = """
def two_sum(nums, target):
    return [0, 0]  # Buggy implementation
"""
        sandbox_receipt = self.sandbox.execute_code(CodeExecutionRequest(code=buggy_code))
        self.assertEqual(sandbox_receipt.exit_code, 0)

        verif_receipt = self.verifier.verify_code(
            req_or_code=buggy_code,
            execution_receipt=sandbox_receipt,
            query="Write Python code for Two Sum",
        )

        self.assertEqual(verif_receipt.verification_status, VerificationStatus.VERIFICATION_FAILED)
        self.assertEqual(verif_receipt.failure_reason, "TEST_ASSERTIONS_FAILED")
        self.assertGreater(verif_receipt.tests_failed, 0)

    def test_negative_5_network_blocked_airgap_enforced(self):
        """
        NEGATIVE TEST 5:
        Code attempts network egress via socket/HTTP.
        Expected: Blocked by air-gapped sandbox security shim with PermissionError.
        """
        net_code = """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('1.1.1.1', 80))
"""
        sandbox_receipt = self.sandbox.execute_code(CodeExecutionRequest(code=net_code))
        self.assertNotEqual(sandbox_receipt.exit_code, 0)
        self.assertIn("PermissionError", sandbox_receipt.stderr)
        self.assertEqual(sandbox_receipt.network_disabled_status, NetworkAccessState.DISABLED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
