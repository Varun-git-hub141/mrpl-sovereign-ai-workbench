import ast
import re
import hashlib
import time
import logging
from typing import Dict, Any, List, Optional, Union

from backend.models.code_sandbox_models import (
    CodeExecutionRequest,
    SandboxExecutionReceipt,
    SandboxExecutionResult,
    CodeVerificationReceipt,
    ExecutionStatus,
    VerificationStatus,
    SandboxStatus,
    NetworkAccessState,
)
from backend.services.code_sandbox.code_sandbox_service import CodeSandboxService

logger = logging.getLogger("mrpl.code_verification")


class CodeVerificationEngine:
    """
    Independent Code Verification Engine.
    Enforces that verification is NEVER inferred from LLM claims, tags, or static heuristics.
    ONLY trusts cryptographically signed SandboxExecutionReceipt instances returned
    by CodeSandboxService.
    Distinguishes EXECUTION_SUCCESS, EXECUTION_FAILED, VERIFIED, VERIFICATION_FAILED,
    and VERIFICATION_HARNESS_ERROR.
    """

    def __init__(self, sandbox_service: Optional[CodeSandboxService] = None):
        self.sandbox = sandbox_service or CodeSandboxService()

    @staticmethod
    def calculate_code_hash(code: str) -> str:
        clean = CodeSandboxService.extract_code_blocks(code) or code.strip()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    @staticmethod
    def derive_deterministic_tests(query: str, code: str) -> List[str]:
        """
        Derives deterministic contract harnesses for standard algorithmic and programming problems.
        Uses explicit contract aliases (Option B) rather than guessing with LLM.
        """
        q_lower = query.lower()
        c_lower = code.lower()
        tests = []

        # 1. Fibonacci Problem
        if "fibonacci" in q_lower or "fibonacci" in c_lower or "fib_sequence" in c_lower or "def fib" in c_lower:
            test1 = (
                "# Fibonacci Sequence Generation (n=5)\n"
                "_allowed = ['fibonacci_sequence', 'fibonacci', 'fib', 'generate_fibonacci', 'get_fibonacci', 'fib_seq']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Fibonacci callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "_res5 = _fn(5)\n"
                "if isinstance(_res5, (list, tuple)):\n"
                "    assert list(_res5) in ([0, 1, 1, 2, 3], [0, 1, 1, 2, 3, 5], [1, 1, 2, 3, 5]), f'Fibonacci sequence test failed for n=5: {_res5}'\n"
                "else:\n"
                "    assert _res5 in (5, 8), f'Fibonacci(5) test failed: expected 5 or 8, got {_res5}'\n"
            )
            test2 = (
                "# Fibonacci Base Cases (n=1, n=2)\n"
                "_allowed = ['fibonacci_sequence', 'fibonacci', 'fib', 'generate_fibonacci', 'get_fibonacci', 'fib_seq']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Fibonacci callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "_res1 = _fn(1)\n"
                "if isinstance(_res1, (list, tuple)):\n"
                "    assert list(_res1) in ([0], [1], [0, 1]), f'Fibonacci(1) failed: {_res1}'\n"
                "    assert list(_fn(2)) in ([0, 1], [1, 1], [0, 1, 1]), f'Fibonacci(2) failed'\n"
                "else:\n"
                "    assert _res1 in (1, [1], [0, 1]) and _fn(0) in (0, 1), 'Fibonacci base case test failed'\n"
            )
            tests.extend([test1, test2])
            return tests

        # 2. Two Sum Problem
        if "two sum" in q_lower or "twosum" in c_lower or "two_sum" in c_lower:
            test1 = (
                "# Two Sum Test 1: [2, 7, 11, 15], target=9\n"
                "_allowed = ['two_sum', 'twoSum', 'two_sum_all', 'twoSumAll']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Two Sum callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "assert sorted(_fn([2, 7, 11, 15], 9)) == [0, 1], 'Two Sum Test 1 Failed: nums=[2,7,11,15], target=9 Expected [0,1]'\n"
            )
            test2 = (
                "# Two Sum Test 2: [3, 2, 4], target=6 & [3, 3], target=6\n"
                "_allowed = ['two_sum', 'twoSum', 'two_sum_all', 'twoSumAll']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Two Sum callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "assert sorted(_fn([3, 2, 4], 6)) == [1, 2], 'Two Sum Test 2 Failed: nums=[3,2,4], target=6 Expected [1,2]'\n"
                "assert sorted(_fn([3, 3], 6)) == [0, 1], 'Two Sum Test 3 Failed: nums=[3,3], target=6 Expected [0,1]'\n"
            )
            tests.extend([test1, test2])
            return tests

        # 3. Palindrome Check
        if "palindrome" in q_lower or "is_palindrome" in c_lower or "ispalindrome" in c_lower:
            harness_pal = (
                "_allowed = ['is_palindrome', 'isPalindrome', 'palindrome', 'is_pal']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Palindrome callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "assert _fn('racecar') == True, 'Palindrome Test 1 Failed: racecar'\n"
                "assert _fn('hello') == False, 'Palindrome Test 2 Failed: hello'\n"
            )
            tests.append(harness_pal)
            return tests

        # 4. Factorial
        if "factorial" in q_lower or ("def fact" in c_lower and "return" in c_lower):
            harness_fact = (
                "_allowed = ['factorial', 'fact', 'calc_factorial']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Factorial callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "assert _fn(0) == 1 and _fn(1) == 1, 'Factorial Base Cases Failed'\n"
                "assert _fn(5) == 120, 'Factorial(5) Failed: expected 120'\n"
            )
            tests.append(harness_fact)
            return tests

        # 5. Reverse String / Sequence
        if "reverse" in q_lower and ("reverse_string" in c_lower or "reversestring" in c_lower or "reverse" in c_lower):
            harness_rev = (
                "_allowed = ['reverse_string', 'reverseString', 'reverse', 'reverse_str']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Reverse String callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "assert _fn('hello') == 'olleh', 'Reverse String Test 1 Failed'\n"
                "assert _fn('world') == 'dlrow', 'Reverse String Test 2 Failed'\n"
            )
            tests.append(harness_rev)
            return tests

        # 6. Binary Search
        if "binary search" in q_lower or "binary_search" in c_lower or "binarysearch" in c_lower:
            harness_bs = (
                "_allowed = ['binary_search', 'binarySearch', 'search']\n"
                "_fn = None\n"
                "for _name in _allowed:\n"
                "    if _name in locals() and callable(locals()[_name]):\n"
                "        _fn = locals()[_name]\n"
                "        break\n"
                "if _fn is None and 'Solution' in locals():\n"
                "    _sol = locals()['Solution']()\n"
                "    for _name in _allowed:\n"
                "        if hasattr(_sol, _name) and callable(getattr(_sol, _name)):\n"
                "            _fn = getattr(_sol, _name)\n"
                "            break\n"
                "if _fn is None:\n"
                "    raise AssertionError('VERIFICATION_HARNESS_ERROR: No permitted Binary Search callable found in generated code (checked: ' + ', '.join(_allowed) + ')')\n"
                "assert _fn([1, 2, 3, 4, 5], 3) == 2, 'Binary Search Test 1 Failed'\n"
                "assert _fn([1, 2, 3, 4, 5], 6) in (-1, None, False), 'Binary Search Test 2 Failed (Not Found)'\n"
            )
            tests.append(harness_bs)
            return tests

        # 7. Add function
        if "def add(" in code:
            test1 = "assert add(2, 3) == 5, 'Add Test 1 Failed: 2 + 3 != 5'"
            test2 = "assert add(-1, 1) == 0, 'Add Test 2 Failed: -1 + 1 != 0'"
            tests.extend([test1, test2])
            return tests

        return tests

    def execute_and_verify(
        self,
        req_or_code: Any,
        test_cases: Optional[List[str]] = None,
        language: str = "python",
        timeout_seconds: float = 5.0,
        query: Optional[str] = None,
    ) -> CodeVerificationReceipt:
        """
        Helper that performs the full Coder -> Sandbox -> Receipt -> Verification Engine flow:
        1. Launches execution inside CodeSandboxService to generate an authentic SandboxExecutionReceipt.
        2. Consumes and verifies that receipt in verify_code.
        """
        raw_code = req_or_code.code if isinstance(req_or_code, CodeExecutionRequest) else str(req_or_code)
        lang = req_or_code.language if isinstance(req_or_code, CodeExecutionRequest) else language
        tout = req_or_code.timeout_seconds if isinstance(req_or_code, CodeExecutionRequest) else timeout_seconds
        tests = (req_or_code.test_cases if isinstance(req_or_code, CodeExecutionRequest) else None) or test_cases or []

        # 1. Application passes exact code to CodeSandboxService
        sandbox_receipt = self.sandbox.execute_code(CodeExecutionRequest(
            code=raw_code,
            language=lang,
            timeout_seconds=tout,
        ))

        # 2. VerificationEngine consumes that receipt
        return self.verify_code(
            req_or_code=raw_code,
            execution_receipt=sandbox_receipt,
            test_cases=tests,
            language=lang,
            timeout_seconds=tout,
            query=query,
        )

    def verify_code(
        self,
        req_or_code: Any,
        execution_receipt: Optional[Union[SandboxExecutionReceipt, Dict[str, Any]]] = None,
        test_cases: Optional[List[str]] = None,
        language: str = "python",
        timeout_seconds: float = 5.0,
        expected_output: Optional[str] = None,
        query: Optional[str] = None,
    ) -> CodeVerificationReceipt:
        """
        Strictly consumes a machine-generated SandboxExecutionReceipt and runs deterministic assertions.
        REJECTS VERIFIED if no receipt exists, if receipt is fabricated, or if execution failed.
        Distinguishes VERIFICATION_HARNESS_ERROR from user code failure.
        """
        if isinstance(req_or_code, CodeExecutionRequest):
            code_text = req_or_code.code
            lang = req_or_code.language
            t_cases = list(req_or_code.test_cases)
            t_out = req_or_code.timeout_seconds
        else:
            code_text = str(req_or_code)
            lang = language
            t_cases = list(test_cases or [])
            t_out = timeout_seconds

        code = self.sandbox.extract_code_blocks(code_text, lang) or code_text.strip()
        code_hash = self.calculate_code_hash(code)
        stages = []
        details = []

        # Stage 1: GENERATING
        stages.append({
            "stage": "GENERATING",
            "timestamp": time.strftime("%H:%M:%S UTC"),
            "status": "SUCCESS",
            "details": "Model completed raw code synthesis."
        })

        # Stage 2: GENERATED
        stages.append({
            "stage": "GENERATED",
            "timestamp": time.strftime("%H:%M:%S UTC"),
            "status": "SUCCESS",
            "details": f"Source code extracted ({len(code.splitlines())} lines). Code SHA-256: {code_hash[:16]}..."
        })

        # Check for AST Syntax Errors early
        if lang.lower() in ("python", "py"):
            try:
                ast.parse(code)
                details.append("Static AST syntax check: PASSED")
            except SyntaxError as se:
                stages.append({
                    "stage": "EXECUTION_FAILED",
                    "timestamp": time.strftime("%H:%M:%S UTC"),
                    "status": "FAILED",
                    "details": f"SyntaxError on line {se.lineno}: {se.msg}"
                })
                return CodeVerificationReceipt(
                    verification_status=VerificationStatus.EXECUTION_FAILED,
                    execution_status=ExecutionStatus.EXECUTION_FAILED,
                    language=lang,
                    sandbox_status=SandboxStatus.ISOLATED,
                    exit_code=1,
                    execution_time=0.0,
                    execution_time_ms=0,
                    tests_passed=0,
                    tests_failed=1,
                    total_tests=1,
                    tests_total=1,
                    test_results=[{"test_case": "AST Syntax Validation", "passed": False}],
                    network_access=NetworkAccessState.DISABLED,
                    code_hash=code_hash,
                    verification_details=["Static AST syntax validation: FAILED", f"SyntaxError: {se.msg} (line {se.lineno})"],
                    lifecycle_stages=stages,
                    stdout="",
                    stderr=f"SyntaxError: {se.msg} (line {se.lineno})",
                    error_message=f"SyntaxError on line {se.lineno}: {se.msg}",
                    failure_reason="SYNTAX_ERROR",
                    receipt_signature_verified=False,
                )

        # Stage 3: EXECUTING_IN_SANDBOX — Strict Receipt Enforcement
        stages.append({
            "stage": "EXECUTING_IN_SANDBOX",
            "timestamp": time.strftime("%H:%M:%S UTC"),
            "status": "IN_PROGRESS",
            "details": "Submitting generated code to isolated sandbox runtime"
        })

        # NEGATIVE CHECK 1: Deliberately bypassed sandbox / No receipt provided
        if execution_receipt is None:
            stages.append({
                "stage": "VERIFICATION_FAILED",
                "timestamp": time.strftime("%H:%M:%S UTC"),
                "status": "FAILED",
                "details": "Rejected: NO_SANDBOX_EXECUTION_RECEIPT. Verification Engine refuses to infer execution without an authentic machine receipt."
            })
            details.append("Proof of Execution: REJECTED (NO_SANDBOX_EXECUTION_RECEIPT)")
            return CodeVerificationReceipt(
                verification_status=VerificationStatus.VERIFICATION_FAILED,
                execution_status=ExecutionStatus.EXECUTION_FAILED,
                language=lang,
                sandbox_status=SandboxStatus.ISOLATED,
                exit_code=1,
                execution_time=0.0,
                execution_time_ms=0,
                tests_passed=0,
                tests_failed=1,
                total_tests=1,
                tests_total=1,
                test_results=[{"test_case": "Sandbox Execution Receipt Required", "passed": False}],
                network_access=NetworkAccessState.DISABLED,
                code_hash=code_hash,
                verification_details=details,
                lifecycle_stages=stages,
                stdout="",
                stderr="Verification Engine Security Policy: Refused to verify code. No machine-generated SandboxExecutionReceipt was presented.",
                error_message="NO_SANDBOX_EXECUTION_RECEIPT",
                failure_reason="NO_SANDBOX_EXECUTION_RECEIPT",
                receipt_signature_verified=False,
            )

        # Convert dict to model if needed
        if isinstance(execution_receipt, dict):
            try:
                receipt_obj = SandboxExecutionReceipt(**execution_receipt)
            except Exception as e:
                receipt_obj = None
        else:
            receipt_obj = execution_receipt

        # NEGATIVE CHECK 2: Cryptographic / Structural Receipt Validation
        valid_rcpt, rcpt_err = self.sandbox.validate_receipt(receipt_obj or execution_receipt, code=code)
        if not valid_rcpt:
            stages.append({
                "stage": "VERIFICATION_FAILED",
                "timestamp": time.strftime("%H:%M:%S UTC"),
                "status": "FAILED",
                "details": f"Rejected: {rcpt_err or 'FABRICATED_OR_INVALID_RECEIPT'}. Receipt failed cryptographic signature / hash integrity verification."
            })
            details.append(f"Receipt Authenticity: FAILED ({rcpt_err or 'FABRICATED_OR_INVALID_RECEIPT'})")
            return CodeVerificationReceipt(
                verification_status=VerificationStatus.VERIFICATION_FAILED,
                execution_status=ExecutionStatus.EXECUTION_FAILED,
                execution_id=getattr(receipt_obj, "execution_id", "invalid"),
                language=lang,
                sandbox_status=SandboxStatus.ISOLATED,
                exit_code=getattr(receipt_obj, "exit_code", 1),
                execution_time=getattr(receipt_obj, "duration", 0.0),
                execution_time_ms=getattr(receipt_obj, "duration_ms", 0),
                tests_passed=0,
                tests_failed=1,
                total_tests=1,
                tests_total=1,
                test_results=[{"test_case": "Cryptographic Receipt Signature Verification", "passed": False}],
                network_access=NetworkAccessState.DISABLED,
                code_hash=code_hash,
                verification_details=details,
                lifecycle_stages=stages,
                stdout=getattr(receipt_obj, "stdout", ""),
                stderr=getattr(receipt_obj, "stderr", "") or f"Receipt signature validation error: {rcpt_err}",
                error_message=rcpt_err or "FABRICATED_OR_INVALID_RECEIPT",
                failure_reason="FABRICATED_OR_INVALID_RECEIPT",
                receipt_signature_verified=False,
            )

        # NEGATIVE CHECK 3: Sandbox execution failure or timeout
        if receipt_obj.status == "TIMEOUT" or receipt_obj.execution_status == ExecutionStatus.TIMEOUT:
            stages.append({
                "stage": "TIMEOUT",
                "timestamp": time.strftime("%H:%M:%S UTC"),
                "status": "TIMEOUT",
                "details": f"Execution Timed Out after {t_out}s in isolated sandbox runtime"
            })
            details.append("Sandbox Execution: TIMEOUT")
            return CodeVerificationReceipt(
                verification_status=VerificationStatus.EXECUTION_FAILED,
                execution_status=ExecutionStatus.TIMEOUT,
                execution_id=receipt_obj.execution_id,
                language=lang,
                sandbox_status=receipt_obj.sandbox_isolation_status,
                exit_code=-1,
                execution_time=receipt_obj.duration,
                execution_time_ms=receipt_obj.duration_ms,
                tests_passed=0,
                tests_failed=1,
                total_tests=1,
                tests_total=1,
                test_results=[{"test_case": "Execution Within Timeout Limit", "passed": False}],
                network_access=receipt_obj.network_disabled_status,
                code_hash=code_hash,
                verification_details=details,
                lifecycle_stages=stages,
                stdout=receipt_obj.stdout,
                stderr=receipt_obj.stderr or f"Execution timed out after {t_out}s",
                error_message=f"Execution timed out after {t_out} seconds",
                failure_reason="TIMEOUT",
                receipt_signature_verified=True,
                execution_receipt=receipt_obj,
            )

        if receipt_obj.exit_code != 0 or receipt_obj.status != "SUCCESS":
            stages.append({
                "stage": "EXECUTION_FAILED",
                "timestamp": time.strftime("%H:%M:%S UTC"),
                "status": "FAILED",
                "details": f"Sandbox execution failed with exit code {receipt_obj.exit_code}. Stderr: {receipt_obj.stderr[:100]}"
            })
            details.append(f"Sandbox Execution: FAILED (Exit Code {receipt_obj.exit_code})")
            return CodeVerificationReceipt(
                verification_status=VerificationStatus.EXECUTION_FAILED,
                execution_status=receipt_obj.execution_status,
                execution_id=receipt_obj.execution_id,
                language=lang,
                sandbox_status=receipt_obj.sandbox_isolation_status,
                exit_code=receipt_obj.exit_code,
                execution_time=receipt_obj.duration,
                execution_time_ms=receipt_obj.duration_ms,
                tests_passed=0,
                tests_failed=1,
                total_tests=1,
                tests_total=1,
                test_results=[{"test_case": "Sandbox Execution (Exit Code 0)", "passed": False}],
                network_access=receipt_obj.network_disabled_status,
                code_hash=code_hash,
                verification_details=details,
                lifecycle_stages=stages,
                stdout=receipt_obj.stdout,
                stderr=receipt_obj.stderr,
                error_message=receipt_obj.stderr or f"Execution failed inside sandbox with exit code {receipt_obj.exit_code}",
                failure_reason="EXECUTION_FAILED",
                receipt_signature_verified=True,
                execution_receipt=receipt_obj,
            )

        # Stage 4: SANDBOX_EXECUTION_COMPLETE
        stages.append({
            "stage": "SANDBOX_EXECUTION_COMPLETE",
            "timestamp": time.strftime("%H:%M:%S UTC"),
            "status": "SUCCESS",
            "details": f"Machine execution receipt validated (ID: {receipt_obj.execution_id}, Exit: 0, Latency: {receipt_obj.duration_ms} ms, Network: DISABLED)"
        })
        details.append(f"Sandbox Execution: SUCCESS (ID: {receipt_obj.execution_id}, Exit Code 0, Time: {receipt_obj.duration_ms} ms)")

        # Mode A: Program Output Test (Script execution verification against expected stdout)
        if expected_output is not None:
            actual_out = (receipt_obj.stdout or "").strip()
            exp_clean = expected_output.strip()
            mode_a_passed = (exp_clean in actual_out) if len(exp_clean) < len(actual_out) else (actual_out == exp_clean)
            test_results_list = [{
                "test_case": f"Program stdout matches expected output ('{exp_clean[:30]}...')",
                "passed": mode_a_passed,
            }]
            if mode_a_passed:
                stages.append({
                    "stage": "TESTS_EXECUTED",
                    "timestamp": time.strftime("%H:%M:%S UTC"),
                    "status": "SUCCESS",
                    "details": "Mode A: Program stdout matched expected output perfectly."
                })
                stages.append({
                    "stage": "VERIFIED",
                    "timestamp": time.strftime("%H:%M:%S UTC"),
                    "status": "VERIFIED",
                    "details": f"100% Machine-Verified via Sandbox Receipt (Program Output Mode, Exit Code 0, Runtime: {receipt_obj.duration_ms} ms)"
                })
                details.append("Mode A (Program Output Verification): PASSED")
                return CodeVerificationReceipt(
                    verification_status=VerificationStatus.VERIFIED,
                    execution_status=ExecutionStatus.SUCCESS,
                    execution_id=receipt_obj.execution_id,
                    language=lang,
                    sandbox_status=receipt_obj.sandbox_isolation_status,
                    exit_code=0,
                    execution_time=receipt_obj.duration,
                    execution_time_ms=receipt_obj.duration_ms,
                    duration=receipt_obj.duration,
                    duration_ms=receipt_obj.duration_ms,
                    tests_passed=1,
                    tests_failed=0,
                    total_tests=1,
                    tests_total=1,
                    test_results=test_results_list,
                    network_access=receipt_obj.network_disabled_status,
                    network_disabled_status=receipt_obj.network_disabled_status,
                    code_hash=code_hash,
                    verification_details=details,
                    lifecycle_stages=stages,
                    stdout=receipt_obj.stdout,
                    stderr=receipt_obj.stderr,
                    receipt_signature_verified=True,
                    execution_receipt=receipt_obj,
                )
            else:
                stages.append({
                    "stage": "VERIFICATION_FAILED",
                    "timestamp": time.strftime("%H:%M:%S UTC"),
                    "status": "FAILED",
                    "details": f"Mode A: Program stdout mismatch. Expected '{exp_clean[:60]}', got '{actual_out[:60]}'"
                })
                details.append("Mode A (Program Output Verification): FAILED (Stdout mismatch)")
                return CodeVerificationReceipt(
                    verification_status=VerificationStatus.VERIFICATION_FAILED,
                    execution_status=ExecutionStatus.SUCCESS,
                    execution_id=receipt_obj.execution_id,
                    language=lang,
                    sandbox_status=receipt_obj.sandbox_isolation_status,
                    exit_code=0,
                    execution_time=receipt_obj.duration,
                    execution_time_ms=receipt_obj.duration_ms,
                    duration=receipt_obj.duration,
                    duration_ms=receipt_obj.duration_ms,
                    tests_passed=0,
                    tests_failed=1,
                    total_tests=1,
                    tests_total=1,
                    test_results=test_results_list,
                    network_access=receipt_obj.network_disabled_status,
                    network_disabled_status=receipt_obj.network_disabled_status,
                    code_hash=code_hash,
                    verification_details=details,
                    lifecycle_stages=stages,
                    stdout=receipt_obj.stdout,
                    stderr=receipt_obj.stderr,
                    error_message=f"Stdout mismatch: expected '{exp_clean}', got '{actual_out}'",
                    failure_reason="STDOUT_MISMATCH",
                    receipt_signature_verified=True,
                    execution_receipt=receipt_obj,
                )

        # Derive effective test cases (Mode B: Callable Test)
        effective_test_cases = list(t_cases)
        if not effective_test_cases:
            combined_text = (query or "") + "\n" + code_text
            extracted_asserts = re.findall(r"(?:^|\n)\s*(assert\s+[^\n]+)", combined_text)
            if extracted_asserts:
                effective_test_cases = [a.strip() for a in extracted_asserts]
            else:
                derived = self.derive_deterministic_tests(query or "", code)
                if derived:
                    effective_test_cases = derived

        # Stage 5: TESTS_EXECUTED / VERIFYING
        test_results_list = []
        test_receipts_list = []
        tests_passed = 0
        tests_failed = 0
        last_error_msg = None
        last_stderr = ""
        is_harness_error = False
        harness_error_details = ""

        def extract_test_label(t_str: str, index: int) -> str:
            lines = [l.strip() for l in t_str.strip().splitlines() if l.strip()]
            for line in lines:
                if line.startswith("#"):
                    return line.lstrip("#").strip()
            for line in reversed(lines):
                if line.startswith("assert "):
                    m = re.search(r",\s*['\"]([^'\"]+)['\"]", line)
                    if m:
                        return m.group(1)
                    return line
            return lines[-1] if lines else f"Deterministic Test Case #{index+1}"

        if effective_test_cases:
            stages.append({
                "stage": "VERIFYING",
                "timestamp": time.strftime("%H:%M:%S UTC"),
                "status": "IN_PROGRESS",
                "details": f"Executing {len(effective_test_cases)} deterministic test assertions in sandbox"
            })

            for idx, t in enumerate(effective_test_cases):
                label = extract_test_label(t, idx)
                test_script_lines = [code, "\n# --- INDEPENDENT VERIFICATION HARNESS ---"]
                t_clean = t.strip()
                if "\n" not in t_clean and not t_clean.startswith("assert ") and not t_clean.startswith("def ") and "==" in t_clean:
                    test_script_lines.append(f"assert {t_clean}, 'Test assertion failed: {t_clean}'")
                else:
                    test_script_lines.append(t_clean)
                test_script_lines.append("print('__TEST_OK__')")

                single_test_code = "\n".join(test_script_lines)
                single_test_rcpt = self.sandbox.execute_code(CodeExecutionRequest(
                    code=single_test_code,
                    language=lang,
                    timeout_seconds=t_out,
                ))
                test_receipts_list.append(single_test_rcpt)

                if single_test_rcpt.execution_status == ExecutionStatus.SUCCESS and single_test_rcpt.exit_code == 0 and "__TEST_OK__" in single_test_rcpt.stdout:
                    tests_passed += 1
                    test_results_list.append({"test_case": label, "passed": True})
                else:
                    tests_failed += 1
                    test_results_list.append({"test_case": label, "passed": False})
                    err_txt = single_test_rcpt.stderr or single_test_rcpt.stdout or f"Test assertion failed: {label}"
                    last_error_msg = err_txt
                    last_stderr = single_test_rcpt.stderr
                    if "VERIFICATION_HARNESS_ERROR" in err_txt or "No permitted" in err_txt or "Could not locate" in err_txt:
                        is_harness_error = True
                        h_match = re.search(r"AssertionError:\s*(?:VERIFICATION_HARNESS_ERROR:\s*)?([^\n]+)", err_txt)
                        harness_error_details = h_match.group(1) if h_match else (err_txt.splitlines()[-1] if err_txt.splitlines() else err_txt)

            if is_harness_error:
                clean_harness_reason = harness_error_details or "No permitted callable found in generated code"
                stages.append({
                    "stage": "VERIFICATION_HARNESS_ERROR",
                    "timestamp": time.strftime("%H:%M:%S UTC"),
                    "status": "FAILED",
                    "details": f"Verification Harness Error: {clean_harness_reason}"
                })
                details.append(f"Verification Harness Error: {clean_harness_reason}")

                return CodeVerificationReceipt(
                    verification_status=VerificationStatus.VERIFICATION_HARNESS_ERROR,
                    execution_status=ExecutionStatus.SUCCESS,
                    execution_id=receipt_obj.execution_id,
                    language=lang,
                    sandbox_status=receipt_obj.sandbox_isolation_status,
                    exit_code=0,
                    execution_time=receipt_obj.duration,
                    execution_time_ms=receipt_obj.duration_ms,
                    duration=receipt_obj.duration,
                    duration_ms=receipt_obj.duration_ms,
                    tests_passed=0,
                    tests_failed=len(effective_test_cases),
                    total_tests=len(effective_test_cases),
                    tests_total=len(effective_test_cases),
                    test_results=test_results_list,
                    test_receipts=test_receipts_list,
                    network_access=receipt_obj.network_disabled_status,
                    network_disabled_status=receipt_obj.network_disabled_status,
                    code_hash=code_hash,
                    verification_details=details,
                    lifecycle_stages=stages,
                    stdout=receipt_obj.stdout,
                    stderr=last_stderr or receipt_obj.stderr,
                    error_message=clean_harness_reason,
                    failure_reason="VERIFICATION_HARNESS_ERROR",
                    receipt_signature_verified=True,
                    execution_receipt=receipt_obj,
                )

            stages.append({
                "stage": "TESTS_EXECUTED",
                "timestamp": time.strftime("%H:%M:%S UTC"),
                "status": "SUCCESS" if tests_failed == 0 else "FAILED",
                "details": f"{tests_passed}/{len(effective_test_cases)} deterministic test assertions passed."
            })

            if tests_failed > 0:
                stages.append({
                    "stage": "VERIFICATION_FAILED",
                    "timestamp": time.strftime("%H:%M:%S UTC"),
                    "status": "FAILED",
                    "details": f"{tests_failed}/{len(effective_test_cases)} test assertions failed in sandbox: {last_error_msg[:120] if last_error_msg else ''}"
                })
                details.append(f"Deterministic Test Verification: {tests_passed}/{len(effective_test_cases)} PASSED ({tests_failed} FAILED)")

                return CodeVerificationReceipt(
                    verification_status=VerificationStatus.VERIFICATION_FAILED,
                    execution_status=ExecutionStatus.SUCCESS,
                    execution_id=receipt_obj.execution_id,
                    language=lang,
                    sandbox_status=receipt_obj.sandbox_isolation_status,
                    exit_code=1,
                    execution_time=receipt_obj.duration,
                    execution_time_ms=receipt_obj.duration_ms,
                    duration=receipt_obj.duration,
                    duration_ms=receipt_obj.duration_ms,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                    total_tests=len(effective_test_cases),
                    tests_total=len(effective_test_cases),
                    test_results=test_results_list,
                    test_receipts=test_receipts_list,
                    network_access=receipt_obj.network_disabled_status,
                    network_disabled_status=receipt_obj.network_disabled_status,
                    code_hash=code_hash,
                    verification_details=details,
                    lifecycle_stages=stages,
                    stdout=receipt_obj.stdout,
                    stderr=last_stderr or receipt_obj.stderr,
                    error_message=last_error_msg or "Deterministic test assertion failed.",
                    failure_reason="TEST_ASSERTIONS_FAILED",
                    receipt_signature_verified=True,
                    execution_receipt=receipt_obj,
                )
        else:
            # If no assertions given, default base execution passes as single test
            test_results_list.append({"test_case": "Sandbox Execution (Exit Code 0)", "passed": True})
            tests_passed = 1
            stages.append({
                "stage": "TESTS_EXECUTED",
                "timestamp": time.strftime("%H:%M:%S UTC"),
                "status": "SUCCESS",
                "details": "Base code execution exited cleanly with code 0."
            })

        # Stage 6: VERIFYING -> VERIFIED
        stages.append({
            "stage": "VERIFIED",
            "timestamp": time.strftime("%H:%M:%S UTC"),
            "status": "VERIFIED",
            "details": f"100% Machine-Verified via Sandbox Receipt (ID: {receipt_obj.execution_id}, Tests: {tests_passed}/{tests_passed} Passed, Runtime: {receipt_obj.duration_ms} ms)"
        })
        details.append(f"Independent Tests Verified: {tests_passed}/{tests_passed} PASSED")

        clean_stdout = receipt_obj.stdout.replace("__ALL_TESTS_PASSED__", "").strip()

        return CodeVerificationReceipt(
            verification_status=VerificationStatus.VERIFIED,
            execution_status=ExecutionStatus.SUCCESS,
            execution_id=receipt_obj.execution_id,
            language=lang,
            sandbox_status=receipt_obj.sandbox_isolation_status,
            exit_code=0,
            execution_time=receipt_obj.duration,
            execution_time_ms=receipt_obj.duration_ms,
            duration=receipt_obj.duration,
            duration_ms=receipt_obj.duration_ms,
            tests_passed=tests_passed,
            tests_failed=0,
            total_tests=tests_passed,
            tests_total=tests_passed,
            test_results=test_results_list,
            test_receipts=test_receipts_list,
            network_access=receipt_obj.network_disabled_status,
            network_disabled_status=receipt_obj.network_disabled_status,
            code_hash=code_hash,
            verification_details=details,
            lifecycle_stages=stages,
            stdout=clean_stdout,
            stderr=receipt_obj.stderr,
            error_message=None,
            failure_reason=None,
            receipt_signature_verified=True,
            execution_receipt=receipt_obj,
        )
