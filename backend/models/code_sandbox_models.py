import time
import uuid
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    TIMEOUT = "TIMEOUT"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_HARNESS_ERROR = "VERIFICATION_HARNESS_ERROR"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    TIMEOUT = "TIMEOUT"
    NOT_VERIFIED = "NOT_VERIFIED"


class SandboxStatus(str, Enum):
    ISOLATED = "ISOLATED"
    LOCAL_PROCESS = "LOCAL_PROCESS"
    AIR_GAPPED = "AIR_GAPPED"


class NetworkAccessState(str, Enum):
    DISABLED = "DISABLED"
    BLOCKED = "BLOCKED"
    RESTRICTED = "RESTRICTED"


class CodeExecutionRequest(BaseModel):
    code: str = Field(..., description="Source code to execute in isolated sandbox")
    language: str = Field(default="python", description="Programming language (e.g. python)")
    timeout_seconds: float = Field(default=5.0, description="Execution timeout in seconds")
    test_cases: List[str] = Field(default_factory=list, description="Optional assertion expressions or test scripts")
    expected_outputs: List[str] = Field(default_factory=list, description="Optional expected substrings in stdout")
    inputs: Optional[Dict[str, Any]] = Field(default=None, description="Optional input variables / parameters")


class SandboxExecutionReceipt(BaseModel):
    """
    Authoritative, machine-generated cryptographic proof of actual sandbox execution.
    Returned exclusively by CodeSandboxService.
    """
    execution_id: str = Field(default_factory=lambda: f"sandbox-{uuid.uuid4().hex[:12]}")
    status: str = "SUCCESS"  # SUCCESS, FAILED, TIMEOUT, SECURITY_VIOLATION
    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    start_time: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    finish_time: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    duration: float = 0.0  # Duration in seconds
    duration_ms: int = 0   # Duration in milliseconds
    code_hash: str = ""    # SHA-256 hash of executed code
    sandbox_isolation_status: SandboxStatus = SandboxStatus.ISOLATED
    sandbox_status: SandboxStatus = SandboxStatus.ISOLATED
    network_disabled_status: NetworkAccessState = NetworkAccessState.DISABLED
    network_access: NetworkAccessState = NetworkAccessState.DISABLED
    signature: str = ""    # Cryptographic HMAC-SHA256 signature produced by sandbox
    security_checks_passed: bool = True
    timeout_occurred: bool = False
    timed_out: bool = False
    violation_details: Optional[str] = None
    created_files: List[str] = Field(default_factory=list)
    code: Optional[str] = None
    language: str = "python"
    execution_time_seconds: float = 0.0
    execution_time_ms: int = 0


# Alias for backward compatibility
SandboxExecutionResult = SandboxExecutionReceipt


class CodeVerificationReceipt(BaseModel):
    """
    Verification receipt produced exclusively by CodeVerificationEngine
    after consuming and cryptographically validating a real SandboxExecutionReceipt.
    """
    verification_status: VerificationStatus
    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS
    execution_id: str = ""
    language: str = "python"
    sandbox_status: SandboxStatus = SandboxStatus.ISOLATED
    exit_code: int = 0
    execution_time: float = 0.0
    execution_time_ms: int = 0
    duration: float = 0.0
    duration_ms: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    total_tests: int = 0
    tests_total: int = 0
    test_results: List[Dict[str, Any]] = Field(default_factory=list)
    test_receipts: List[SandboxExecutionReceipt] = Field(default_factory=list)
    network_access: NetworkAccessState = NetworkAccessState.DISABLED
    network_disabled_status: NetworkAccessState = NetworkAccessState.DISABLED
    verification_timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
    code_hash: str = ""
    verification_details: List[str] = Field(default_factory=list)
    lifecycle_stages: List[Dict[str, Any]] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None
    failure_reason: Optional[str] = None
    receipt_signature_verified: bool = False
    execution_receipt: Optional[SandboxExecutionReceipt] = None
