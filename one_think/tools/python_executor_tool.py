"""
PythonExecutorTool - Full JSON migration with Pydantic schemas.
Execute Python code with structured JSON responses and validation.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Literal
from pydantic import BaseModel, Field

from one_think.tools.base import Tool, ToolResponse


class PythonExecutorTool(Tool):
    """
    Tool for executing Python scripts and code with Pydantic validation.

    Execution modes:
    - secure:
        Best-effort restricted execution:
        * no network access at Python level
        * isolated working directory
        * minimal environment
        * resource limits (POSIX)
    - insecure:
        Full local execution with inherited environment and no extra restrictions

    IMPORTANT:
    This is still NOT a hardened security boundary.
    For real isolation use containers / VM / OS sandboxing.
    """

    name = "python_executor"
    description = "Execute Python code or Python script files"
    version = "2.0.0"
    
    # Pydantic schemas for validation
    class Input(BaseModel):
        """Input parameters for Python execution."""
        operation: Literal["execute", "execute_file"] = Field(description="Operation type: execute code or execute file")
        code: Optional[str] = Field(default=None, description="Python code to execute (for execute operation)")
        file_path: Optional[str] = Field(default=None, description="Path to Python file (for execute_file operation)")
        timeout: Optional[int] = Field(default=30, ge=1, le=300, description="Timeout in seconds (1-300)")
        mode: Optional[Literal["secure", "insecure"]] = Field(default="secure", description="Execution mode")
        raw_output: Optional[bool] = Field(default=False, description="Return raw output without processing")
        working_dir: Optional[str] = Field(default=None, description="Working directory for execution")
        
    class Output(BaseModel):
        """Output format for Python execution."""
        operation: str = Field(description="Operation that was executed")
        stdout: str = Field(description="Standard output from execution")
        stderr: str = Field(description="Standard error from execution")
        return_code: int = Field(description="Process return code (0=success)")
        execution_time_ms: float = Field(description="Execution time in milliseconds")
        mode: str = Field(description="Execution mode used")
        timed_out: bool = Field(description="Whether execution timed out")
        working_directory: Optional[str] = Field(description="Working directory used")

    def __init__(self) -> None:
        super().__init__()

        self.allowed_roots = [
            Path(".").resolve(),
            Path("./persistent").resolve(),
            Path("./scripts").resolve(),
            Path("./tests").resolve(),
        ]

        self.base_env = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        }

        # Resource limits for secure mode
        self.secure_limits = {
            "cpu_seconds": 2,
            "memory_bytes": 256 * 1024 * 1024,   # 256 MB
            "file_size_bytes": 10 * 1024 * 1024, # 10 MB
            "nofile": 32,
        }

    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute Python code with JSON response."""
        
        # Validate required params
        error = self.validate_required_params(params, required=["operation"])
        if error:
            return error
        
        operation = params["operation"]
        timeout = self._parse_timeout(params.get("timeout"), default=30)
        mode = self._parse_mode(params.get("mode", "secure"))
        raw_output = self._to_bool(params.get("raw_output", False))
        
        # Route to operation handlers
        if operation == "execute":
            return self._execute_code(params, timeout, mode, raw_output, request_id)
        elif operation == "execute_file":
            return self._execute_file(params, timeout, mode, raw_output, request_id)
        else:
            return self._create_error_response(
                f"Unknown operation: '{operation}'. Valid operations: execute, execute_file",
                request_id=request_id
            )
    
    def _parse_mode(self, value: Any) -> str:
        """Parse execution mode safely."""
        if not isinstance(value, str):
            return "secure"
        
        normalized = value.strip().lower()
        if normalized in {"secure", "insecure"}:
            return normalized
        return "secure"
    
    def _parse_timeout(self, value: Any, default: int = 30) -> int:
        """Parse timeout safely and enforce sane bounds."""
        try:
            timeout = int(value) if value is not None else default
        except (TypeError, ValueError):
            return default
        
        if timeout <= 0:
            return default
        
        return min(timeout, 300)
    
    def _to_bool(self, value: Any) -> bool:
        """Convert common truthy values to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        if isinstance(value, int):
            return value != 0
        return False
    
    def _validate_working_dir(self, working_dir: Any) -> tuple[Optional[Path], str]:
        """Validate and normalize working directory."""
        if working_dir is None:
            return None, ""
        
        if not isinstance(working_dir, str) or not working_dir.strip():
            return None, "Invalid working_dir: must be a non-empty string"
        
        path = Path(working_dir).resolve()
        
        if not path.exists():
            return None, f"Working directory not found: {working_dir}"
        if not path.is_dir():
            return None, f"Working directory is not a directory: {working_dir}"
        
        return path, ""
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check whether a path is within one of the allowed roots."""
        resolved = path.resolve()
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False
    
    def _build_env(self, mode: str) -> dict[str, str]:
        """Build environment for subprocess."""
        env: dict[str, str] = {}
        
        if mode == "secure":
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONNOUSERSITE"] = "1"
            env["HOME"] = tempfile.gettempdir()
            env["TMP"] = tempfile.gettempdir()
            env["TEMP"] = tempfile.gettempdir()
            env["PY_EXECUTOR_MODE"] = "secure"
            env["PY_EXECUTOR_NETWORK"] = "0"
            
            if "PATH" in os.environ:
                env["PATH"] = os.environ["PATH"]
            
            return env
        
        # insecure mode
        env.update(os.environ)
        env.update(self.base_env)
        env["PY_EXECUTOR_MODE"] = "insecure"
        env["PY_EXECUTOR_NETWORK"] = "1"
        return env
    
    def _build_python_cmd(self, target_path: Path, mode: str) -> list[str]:
        """Build python invocation command."""
        if mode == "secure":
            return [sys.executable, "-I", "-S", "-B", "-E", str(target_path)]
        return [sys.executable, str(target_path)]
    
    def _make_preexec_fn(self, mode: str) -> Optional[Callable]:
        """POSIX-only resource limiting hook."""
        if mode != "secure":
            return None
        
        if os.name != "posix":
            return None
        
        def _preexec():
            import resource
            
            limits = self.secure_limits
            
            resource.setrlimit(resource.RLIMIT_CPU, (limits["cpu_seconds"], limits["cpu_seconds"]))
            resource.setrlimit(resource.RLIMIT_AS, (limits["memory_bytes"], limits["memory_bytes"]))
            resource.setrlimit(resource.RLIMIT_FSIZE, (limits["file_size_bytes"], limits["file_size_bytes"]))
            resource.setrlimit(resource.RLIMIT_NOFILE, (limits["nofile"], limits["nofile"]))
            
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        
        return _preexec
    
    def _wrap_secure_code(self, user_code: str) -> str:
        """Wrap user code with a Python-level network blocker."""
        return f'''# --- secure wrapper injected by PythonExecutorTool ---
import socket

class _NetworkDisabledError(RuntimeError):
    pass

def _deny_network(*args, **kwargs):
    raise _NetworkDisabledError("Network access is disabled in secure mode")

socket.socket = _deny_network
socket.create_connection = _deny_network
if hasattr(socket, "socketpair"):
    socket.socketpair = _deny_network
if hasattr(socket, "fromfd"):
    socket.fromfd = _deny_network

# --- user code starts here ---
{user_code}
'''
    
    def _prepare_secure_temp_script(self, source_code: str, tmp_root: Path) -> Path:
        """Create wrapped secure script file in temp directory."""
        wrapped_code = self._wrap_secure_code(source_code)
        tmp_path = tmp_root / "inline_exec.py"
        tmp_path.write_text(wrapped_code, encoding="utf-8")
        return tmp_path
    
    def _prepare_secure_file_script(self, source_path: Path, tmp_root: Path) -> Path:
        """Copy a file into temp dir and prepend secure wrapper."""
        original_code = source_path.read_text(encoding="utf-8")
        wrapped_code = self._wrap_secure_code(original_code)
        tmp_path = tmp_root / source_path.name
        tmp_path.write_text(wrapped_code, encoding="utf-8")
        return tmp_path
    
    def _run_python_target(
        self,
        target_path: Path,
        timeout: int,
        working_dir: Optional[Path],
        executed_label: Optional[str],
        mode: str,
        raw_output: bool,
    ) -> Dict[str, Any]:
        """Run a Python file and collect output."""
        try:
            result = subprocess.run(
                self._build_python_cmd(target_path=target_path, mode=mode),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(working_dir) if working_dir else None,
                env=self._build_env(mode=mode),
                preexec_fn=self._make_preexec_fn(mode),
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "executed": executed_label,
                "mode": mode,
                "timed_out": False
            }
        
        except subprocess.TimeoutExpired:
            return {
                "error": f"Script execution timed out after {timeout} seconds",
                "timed_out": True,
                "timeout": timeout
            }
        except FileNotFoundError as exc:
            return {"error": f"Execution failed: {exc}"}
        except OSError as exc:
            return {"error": f"OS error during execution: {exc}"}
        except Exception as exc:
            return {"error": f"Unexpected execution error: {exc}"}
    
    def _execute_code(
        self,
        params: Dict[str, Any],
        timeout: int,
        mode: str,
        raw_output: bool,
        request_id: Optional[str]
    ) -> ToolResponse:
        """Execute Python code by writing it to a temporary file."""
        code = params.get("code")
        
        if not isinstance(code, str) or not code.strip():
            return self._create_error_response(
                "Missing required parameter: 'code'",
                request_id=request_id
            )
        
        working_dir = params.get("working_dir", ".")
        wd_path, wd_error = self._validate_working_dir(working_dir)
        if wd_error:
            return self._create_error_response(wd_error, request_id=request_id)
        
        try:
            with tempfile.TemporaryDirectory(prefix="pyexec_") as tmp_dir:
                tmp_root = Path(tmp_dir)
                
                # secure -> isolate cwd into temp dir
                # insecure -> use requested working dir
                effective_wd = tmp_root if mode == "secure" else wd_path
                
                if mode == "secure":
                    tmp_path = self._prepare_secure_temp_script(code, tmp_root)
                else:
                    tmp_path = tmp_root / "inline_exec.py"
                    tmp_path.write_text(code, encoding="utf-8")
                
                exec_result = self._run_python_target(
                    target_path=tmp_path,
                    timeout=timeout,
                    working_dir=effective_wd,
                    executed_label="<inline_code>",
                    mode=mode,
                    raw_output=raw_output,
                )
                
                # Check for errors
                if "error" in exec_result:
                    return self._create_error_response(
                        exec_result["error"],
                        request_id=request_id
                    )
                
                # Build result
                result = {
                    "stdout": exec_result["stdout"],
                    "stderr": exec_result["stderr"],
                    "returncode": exec_result["returncode"],
                    "executed": exec_result["executed"],
                    "mode": mode.upper(),
                    "timeout": timeout
                }
                
                # Add raw output if requested
                if raw_output:
                    result["raw_output"] = exec_result["stdout"] + exec_result["stderr"]
                
                return self._create_success_response(
                    result=result,
                    request_id=request_id
                )
        
        except Exception as exc:
            return self._create_error_response(
                f"Error preparing code execution: {exc}",
                request_id=request_id
            )
    
    def _execute_file(
        self,
        params: Dict[str, Any],
        timeout: int,
        mode: str,
        raw_output: bool,
        request_id: Optional[str]
    ) -> ToolResponse:
        """Execute an existing Python file."""
        file_path = params.get("file_path")
        
        if not isinstance(file_path, str) or not file_path.strip():
            return self._create_error_response(
                "Missing required parameter: 'file_path'",
                request_id=request_id
            )
        
        script_path = Path(file_path).resolve()
        
        if not script_path.exists():
            return self._create_error_response(
                f"File not found: {file_path}",
                request_id=request_id
            )
        
        if not script_path.is_file():
            return self._create_error_response(
                f"Path is not a file: {file_path}",
                request_id=request_id
            )
        
        if script_path.suffix.lower() != ".py":
            return self._create_error_response(
                "File must be a Python script (.py)",
                request_id=request_id
            )
        
        if not self._is_path_allowed(script_path):
            allowed = ", ".join(str(p) for p in self.allowed_roots)
            return self._create_error_response(
                f"Access denied: file is outside allowed directories. Allowed roots: {allowed}",
                request_id=request_id
            )
        
        working_dir = params.get("working_dir")
        wd_path, wd_error = self._validate_working_dir(working_dir)
        if wd_error:
            return self._create_error_response(wd_error, request_id=request_id)
        
        if wd_path is None:
            wd_path = script_path.parent
        
        try:
            with tempfile.TemporaryDirectory(prefix="pyexec_") as tmp_dir:
                tmp_root = Path(tmp_dir)
                
                # secure -> run copied/wrapped file in isolated temp cwd
                # insecure -> run original file in normal cwd
                if mode == "secure":
                    effective_wd = tmp_root
                    target_path = self._prepare_secure_file_script(script_path, tmp_root)
                else:
                    effective_wd = wd_path
                    target_path = script_path
                
                exec_result = self._run_python_target(
                    target_path=target_path,
                    timeout=timeout,
                    working_dir=effective_wd,
                    executed_label=file_path,
                    mode=mode,
                    raw_output=raw_output,
                )
                
                # Check for errors
                if "error" in exec_result:
                    return self._create_error_response(
                        exec_result["error"],
                        request_id=request_id
                    )
                
                # Build result
                result = {
                    "stdout": exec_result["stdout"],
                    "stderr": exec_result["stderr"],
                    "returncode": exec_result["returncode"],
                    "executed": exec_result["executed"],
                    "mode": mode.upper(),
                    "file_path": str(script_path),
                    "timeout": timeout
                }
                
                # Add raw output if requested
                if raw_output:
                    result["raw_output"] = exec_result["stdout"] + exec_result["stderr"]
                
                return self._create_success_response(
                    result=result,
                    request_id=request_id
                )
        
        except Exception as exc:
            return self._create_error_response(
                f"Error preparing file execution: {exc}",
                request_id=request_id
            )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        allowed_dirs = os.linesep.join(f"    - {str(p)}" for p in self.allowed_roots)
        
        return f"""Python Executor Tool

DESCRIPTION:
    Execute Python code or Python script files in a subprocess.

EXECUTION MODES:
    secure (default)
        Restricted execution mode designed for safety:
        - network access disabled (Python-level)
        - isolated temporary working directory
        - minimal environment variables
        - resource limits (CPU, memory, file size)

        USE THIS MODE:
        - for untrusted or user-generated code
        - for testing logic, algorithms, parsing, transformations
        - when no internet access is required

        LIMITATIONS:
        - HTTP requests will fail
        - downloading files will fail
        - APIs and external services are unavailable
        - some libraries may break if they expect network or system access

    insecure
        Full local execution with access to system environment:
        - network access ENABLED
        - full environment variables (PATH, HOME, etc.)
        - no additional restrictions

        USE THIS MODE WHEN:
        - your code needs internet access (requests, urllib, APIs)
        - you install packages (pip, poetry, etc.)
        - you access external services (databases, REST APIs)
        - secure mode fails due to missing network or environment

        EXAMPLES:
            - requests.get(...)
            - urllib.request.urlopen(...)
            - downloading models or datasets
            - connecting to external DB / API

        WARNING:
            This mode executes code with full system access.
            Do NOT use with untrusted input.

IMPORTANT:
    This tool is NOT a fully secure sandbox.
    "secure" mode is best-effort only.
    For strong isolation use containers or VM-based execution.

ALLOWED DIRECTORIES:
{allowed_dirs}

OPERATIONS:
    execute
        Execute Python code from a string.

    execute_file
        Execute an existing .py file.

PARAMETERS:
    operation (string, required)
        One of: execute, execute_file

    mode (string, optional)
        One of: secure, insecure
        Default: secure

    code (string)
        Required for operation=execute

    file_path (string)
        Required for operation=execute_file

    timeout (integer, optional)
        Timeout in seconds. Default: 30, max: 300

    working_dir (string, optional)
        Working directory for process execution

    raw_output (boolean, optional)
        If true: returns raw stdout and stderr combined

EXAMPLES:

    # Safe execution (no internet)
    {{"operation": "execute",
      "code": "print('Hello World')"}}

    # This will FAIL in secure mode (no network)
    {{"operation": "execute",
      "mode": "secure",
      "code": "import requests; print(requests.get('https://example.com'))"}}

    # Fix: use insecure mode for network access
    {{"operation": "execute",
      "mode": "insecure",
      "code": "import requests; print(requests.get('https://example.com').status_code)"}}

    # Execute file securely
    {{"operation": "execute_file",
      "file_path": "scripts/test.py",
      "mode": "secure"}}

    # Execute file with full access
    {{"operation": "execute_file",
      "file_path": "scripts/api_client.py",
      "mode": "insecure"}}

RESPONSE FORMAT:
    Success:
        {{
            "status": "success",
            "result": {{
                "stdout": "...",
                "stderr": "...",
                "returncode": 0,
                "executed": "<inline_code>" or "path/to/file.py",
                "mode": "SECURE" or "INSECURE",
                "timeout": 30,
                "raw_output": "..."  // if raw_output=true
            }}
        }}
    
    Error:
        {{
            "status": "error",
            "error": {{
                "message": "Error description",
                "type": "ToolExecutionError"
            }}
        }}

NOTES:
    - If your code fails with network errors -> try mode="insecure"
    - If your code is untrusted -> ALWAYS use mode="secure"
    - STDERR does not always mean failure
    - Non-zero exit code usually indicates an error
"""
