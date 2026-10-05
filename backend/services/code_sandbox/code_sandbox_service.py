import os
import sys
import time
import re
import uuid
import hmac
import hashlib
import tempfile
import subprocess
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

from backend.models.code_sandbox_models import (
    CodeExecutionRequest,
    SandboxExecutionReceipt,
    SandboxExecutionResult,
    ExecutionStatus,
    SandboxStatus,
    NetworkAccessState,
)

logger = logging.getLogger("mrpl.code_sandbox")


class CodeSandboxService:
    """
    Local Isolated Code Sandbox Execution Service.
    Executes generated Python scripts in an isolated, air-gapped temporary environment
    with strict network disabling, execution timeout, and output capture.
    Generates a cryptographically signed SandboxExecutionReceipt for verified execution tracking.
    """

    # Disallowed physical control / SCADA / PLC modules for industrial safety
    FORBIDDEN_IMPORTS = [
        "pymodbus", "pycomm3", "opcua", "snap7", "minimalmodbus",
        "ctypes.windll", "win32api", "win32con", "subprocess", "pynput"
    ]

    _SANDBOX_SECRET = os.environ.get("MRPL_SANDBOX_SECRET", "mrpl-sovereign-sandbox-airgap-secret-key-v1").encode("utf-8")

    NETWORK_ISOLATION_HEADER = '''# --- MRPL AIR-GAPPED SANDBOX SECURITY SHIM ---
import sys
import os
import builtins

# 1. NETWORK RESTRICTIONS (AIR-GAP ENFORCEMENT)
import socket

class _BlockedSocket:
    def __init__(self, *args, **kwargs):
        raise PermissionError("Sandbox Security Policy: Network access is DISABLED in air-gapped execution.")

socket.socket = _BlockedSocket
socket.create_connection = lambda *args, **kwargs: (_ for _ in ()).throw(
    PermissionError("Sandbox Security Policy: Outbound network connections are BLOCKED.")
)
socket.getaddrinfo = lambda *args, **kwargs: (_ for _ in ()).throw(
    PermissionError("Sandbox Security Policy: Network DNS resolution is BLOCKED.")
)
socket.gethostbyname = lambda *args, **kwargs: (_ for _ in ()).throw(
    PermissionError("Sandbox Security Policy: Network DNS resolution is BLOCKED.")
)

try:
    import urllib.request
    urllib.request.urlopen = lambda *args, **kwargs: (_ for _ in ()).throw(
        PermissionError("Sandbox Security Policy: HTTP requests are BLOCKED.")
    )
except ImportError:
    pass

try:
    import http.client
    http.client.HTTPConnection = lambda *args, **kwargs: (_ for _ in ()).throw(
        PermissionError("Sandbox Security Policy: HTTP connections are BLOCKED.")
    )
    http.client.HTTPSConnection = lambda *args, **kwargs: (_ for _ in ()).throw(
        PermissionError("Sandbox Security Policy: HTTPS connections are BLOCKED.")
    )
except ImportError:
    pass

# 2. FILESYSTEM RESTRICTIONS (WORKSPACE CONFINEMENT)
_SANDBOX_DIR = os.path.abspath(os.getcwd())
_ORIG_OPEN = builtins.open

def _sandboxed_open(file, mode="r", *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)):
        try:
            abs_p = os.path.abspath(file)
            is_in_sandbox = abs_p.startswith(_SANDBOX_DIR)
            is_python_runtime = ("python" in abs_p.lower() or "lib" in abs_p.lower()) and any(m in mode for m in ["r", "rb"])
            if not is_in_sandbox and not is_python_runtime:
                raise PermissionError(f"Sandbox Security Policy: Access to path '{file}' outside sandbox workspace is RESTRICTED.")
        except Exception as e:
            if isinstance(e, PermissionError):
                raise
    return _ORIG_OPEN(file, mode, *args, **kwargs)

builtins.open = _sandboxed_open
# ------------------------------------------------------
'''

    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout

    @classmethod
    def _generate_signature(cls, execution_id: str, code_hash: str, exit_code: int, status: str, finish_time: str) -> str:
        """
        Generates HMAC-SHA256 signature for machine-verifiable execution receipts.
        """
        payload = f"{execution_id}:{code_hash}:{exit_code}:{status}:{finish_time}"
        return hmac.new(cls._SANDBOX_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def validate_receipt(cls, receipt: Union[SandboxExecutionReceipt, Dict[str, Any]], code: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Cryptographically and structurally validates a SandboxExecutionReceipt.
        Rejects fabricated, tampered, or unregistered execution claims.
        """
        if receipt is None:
            return False, "NO_SANDBOX_EXECUTION_RECEIPT"

        if isinstance(receipt, dict):
            exec_id = receipt.get("execution_id")
            code_hash = receipt.get("code_hash")
            exit_code = receipt.get("exit_code", 0)
            status = receipt.get("status", "SUCCESS")
            finish_time = receipt.get("finish_time") or receipt.get("timestamp") or ""
            signature = receipt.get("signature", "")
        else:
            exec_id = getattr(receipt, "execution_id", None)
            code_hash = getattr(receipt, "code_hash", None)
            exit_code = getattr(receipt, "exit_code", 0)
            status = getattr(receipt, "status", "SUCCESS")
            finish_time = getattr(receipt, "finish_time", None) or getattr(receipt, "timestamp", "")
            signature = getattr(receipt, "signature", "")

        if not exec_id or not code_hash or not signature:
            return False, "MISSING_RECEIPT_CRYPTOGRAPHIC_FIELDS"

        # Check code hash match if code supplied
        if code is not None:
            clean_code = cls.extract_code_blocks(code)
            expected_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()
            raw_hash = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()
            if code_hash not in (expected_hash, raw_hash):
                return False, f"CODE_HASH_MISMATCH (Expected {expected_hash[:12]}..., Got {code_hash[:12]}...)"

        # Verify HMAC signature
        expected_sig = cls._generate_signature(exec_id, code_hash, exit_code, status, finish_time)
        if not hmac.compare_digest(expected_sig, signature):
            return False, "FABRICATED_OR_INVALID_RECEIPT_SIGNATURE"

        return True, None

    @staticmethod
    def extract_code_blocks(text: str, language: str = "python") -> str:
        """
        Extracts executable code from Markdown code blocks or returns clean text.
        """
        if not text:
            return ""

        pattern = r"```(?:python|py)?\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return "\n\n".join(b.strip() for b in matches)

        clean_text = text.strip()
        return clean_text

    def check_static_security(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Static pre-execution inspection to prevent dangerous calls to physical control/DCS.
        """
        for item in self.FORBIDDEN_IMPORTS:
            if re.search(rf"\bimport\s+{re.escape(item)}\b", code) or re.search(rf"\bfrom\s+{re.escape(item)}\b", code):
                return False, f"Prohibited physical control / system access module '{item}' detected."

        return True, None

    def execute_code(self, req: CodeExecutionRequest) -> SandboxExecutionReceipt:
        """
        Executes code inside an isolated temporary directory with air-gapped network and filesystem restrictions.
        Returns an authoritative, cryptographically signed SandboxExecutionReceipt.
        """
        raw_code = req.code.strip()
        code_to_run = self.extract_code_blocks(raw_code, req.language)
        if not code_to_run:
            code_to_run = raw_code

        code_hash = hashlib.sha256(code_to_run.encode("utf-8")).hexdigest()
        execution_id = f"sandbox-{uuid.uuid4().hex[:12]}"
        t_start = time.time()
        start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start))

        # 1. Static Security Check
        sec_ok, sec_violation = self.check_static_security(code_to_run)
        if not sec_ok:
            t_finish = time.time()
            finish_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_finish))
            sig = self._generate_signature(execution_id, code_hash, 1, "SECURITY_VIOLATION", finish_iso)
            return SandboxExecutionReceipt(
                execution_id=execution_id,
                code=code_to_run,
                language=req.language,
                execution_status=ExecutionStatus.SECURITY_VIOLATION,
                status="SECURITY_VIOLATION",
                stdout="",
                stderr=f"Security Violation: {sec_violation}",
                exit_code=1,
                start_time=start_iso,
                finish_time=finish_iso,
                duration=0.0,
                duration_ms=0,
                execution_time_seconds=0.0,
                execution_time_ms=0,
                code_hash=code_hash,
                timeout_occurred=False,
                timed_out=False,
                sandbox_isolation_status=SandboxStatus.ISOLATED,
                sandbox_status=SandboxStatus.ISOLATED,
                network_disabled_status=NetworkAccessState.DISABLED,
                network_access=NetworkAccessState.DISABLED,
                signature=sig,
                security_checks_passed=False,
                violation_details=sec_violation,
            )

        # 2. Prepare Sandbox Environment
        with tempfile.TemporaryDirectory(prefix="mrpl_sandbox_") as tmp_dir:
            script_path = os.path.join(tmp_dir, "sandbox_script.py")
            
            # Combine isolation shim + user code
            full_script = self.NETWORK_ISOLATION_HEADER + "\n" + code_to_run

            with open(script_path, "w", encoding="utf-8") as f:
                f.write(full_script)

            # Restricted environment variables
            env = {
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
                "PATH": os.environ.get("PATH", ""),
                "PYTHONUNBUFFERED": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "MRPL_SANDBOX_ISOLATED": "1",
                "MRPL_NETWORK_DISABLED": "1",
            }

            try:
                proc = subprocess.run(
                    [sys.executable, script_path],
                    cwd=tmp_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=req.timeout_seconds or self.default_timeout,
                )
                t_finish = time.time()
                duration = round(t_finish - t_start, 4)
                duration_ms = max(1, int(duration * 1000))
                finish_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_finish))
                stdout = proc.stdout.strip()
                stderr = proc.stderr.strip()
                exit_code = proc.returncode

                status_enum = ExecutionStatus.SUCCESS if exit_code == 0 else ExecutionStatus.EXECUTION_FAILED
                status_str = "SUCCESS" if exit_code == 0 else "EXECUTION_FAILED"
                sig = self._generate_signature(execution_id, code_hash, exit_code, status_str, finish_iso)

                return SandboxExecutionReceipt(
                    execution_id=execution_id,
                    code=code_to_run,
                    language=req.language,
                    execution_status=status_enum,
                    status=status_str,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    start_time=start_iso,
                    finish_time=finish_iso,
                    duration=duration,
                    duration_ms=duration_ms,
                    execution_time_seconds=duration,
                    execution_time_ms=duration_ms,
                    code_hash=code_hash,
                    timeout_occurred=False,
                    timed_out=False,
                    sandbox_isolation_status=SandboxStatus.ISOLATED,
                    sandbox_status=SandboxStatus.ISOLATED,
                    network_disabled_status=NetworkAccessState.DISABLED,
                    network_access=NetworkAccessState.DISABLED,
                    signature=sig,
                    security_checks_passed=True,
                )

            except subprocess.TimeoutExpired as te:
                t_finish = time.time()
                duration = round(t_finish - t_start, 4)
                duration_ms = max(1, int(duration * 1000))
                finish_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_finish))
                out_decoded = te.stdout.decode() if (te.stdout and isinstance(te.stdout, bytes)) else (te.stdout or "")
                sig = self._generate_signature(execution_id, code_hash, -1, "TIMEOUT", finish_iso)
                return SandboxExecutionReceipt(
                    execution_id=execution_id,
                    code=code_to_run,
                    language=req.language,
                    execution_status=ExecutionStatus.TIMEOUT,
                    status="TIMEOUT",
                    stdout=out_decoded.strip(),
                    stderr=f"Execution Timed Out after {req.timeout_seconds or self.default_timeout} seconds.",
                    exit_code=-1,
                    start_time=start_iso,
                    finish_time=finish_iso,
                    duration=duration,
                    duration_ms=duration_ms,
                    execution_time_seconds=duration,
                    execution_time_ms=duration_ms,
                    code_hash=code_hash,
                    timeout_occurred=True,
                    timed_out=True,
                    sandbox_isolation_status=SandboxStatus.ISOLATED,
                    sandbox_status=SandboxStatus.ISOLATED,
                    network_disabled_status=NetworkAccessState.DISABLED,
                    network_access=NetworkAccessState.DISABLED,
                    signature=sig,
                    security_checks_passed=True,
                    violation_details="Execution exceeded maximum allowed execution duration.",
                )
            except Exception as e:
                t_finish = time.time()
                duration = round(t_finish - t_start, 4)
                duration_ms = max(1, int(duration * 1000))
                finish_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_finish))
                sig = self._generate_signature(execution_id, code_hash, 1, "EXECUTION_FAILED", finish_iso)
                return SandboxExecutionReceipt(
                    execution_id=execution_id,
                    code=code_to_run,
                    language=req.language,
                    execution_status=ExecutionStatus.EXECUTION_FAILED,
                    status="EXECUTION_FAILED",
                    stdout="",
                    stderr=f"Sandbox Execution Exception: {str(e)}",
                    exit_code=1,
                    start_time=start_iso,
                    finish_time=finish_iso,
                    duration=duration,
                    duration_ms=duration_ms,
                    execution_time_seconds=duration,
                    execution_time_ms=duration_ms,
                    code_hash=code_hash,
                    timeout_occurred=False,
                    timed_out=False,
                    sandbox_isolation_status=SandboxStatus.ISOLATED,
                    sandbox_status=SandboxStatus.ISOLATED,
                    network_disabled_status=NetworkAccessState.DISABLED,
                    network_access=NetworkAccessState.DISABLED,
                    signature=sig,
                    security_checks_passed=False,
                    violation_details=str(e),
                )
