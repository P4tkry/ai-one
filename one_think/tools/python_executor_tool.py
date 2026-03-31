import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Tuple

from one_think.tools import Tool


class PythonExecutorTool(Tool):
    """
    Tool for executing Python scripts and code.

    Security model:
    - This tool is intended for trusted/local use.
    - It is NOT a secure sandbox.
    - By default, file execution is restricted to allowed directories.
    - Optional "sandbox" mode adds best-effort isolation and resource limits.
    """

    name = "python_executor"
    description = "Execute Python code or Python script files"

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

        # Default resource limits for sandbox mode
        self.sandbox_limits = {
            "cpu_seconds": 2,
            "memory_bytes": 256 * 1024 * 1024,   # 256 MB
            "file_size_bytes": 10 * 1024 * 1024, # 10 MB
            "nofile": 32,
        }

    def execute(self, arguments: dict[str, Any]) -> Tuple[str, str]:
        """Execute the selected tool operation."""
        if not isinstance(arguments, dict):
            return "", "Arguments must be a dictionary"

        if self._to_bool(arguments.get("help", False)):
            return self._show_help()

        operation = arguments.get("operation")
        if not isinstance(operation, str) or not operation.strip():
            return "", "Missing required argument: 'operation'"

        operation = operation.strip()
        timeout = self._parse_timeout(arguments.get("timeout"), default=30)
        sandbox = self._to_bool(arguments.get("sandbox", False))
        sandbox_network = self._to_bool(arguments.get("sandbox_network", False))
        sandbox_readonly = self._to_bool(arguments.get("sandbox_readonly", True))
        raw_output = self._to_bool(arguments.get("raw_output", False))

        if operation == "execute":
            code = arguments.get("code")
            working_dir = arguments.get("working_dir", ".")
            return self._execute_code(
                code=code,
                timeout=timeout,
                working_dir=working_dir,
                sandbox=sandbox,
                sandbox_network=sandbox_network,
                sandbox_readonly=sandbox_readonly,
                raw_output=raw_output,
            )

        if operation == "execute_file":
            file_path = arguments.get("file_path")
            working_dir = arguments.get("working_dir")
            return self._execute_file(
                file_path=file_path,
                timeout=timeout,
                working_dir=working_dir,
                sandbox=sandbox,
                sandbox_network=sandbox_network,
                sandbox_readonly=sandbox_readonly,
                raw_output=raw_output,
            )

        if operation == "help":
            return self._show_help()

        return "", "Unknown operation. Valid operations: execute, execute_file, help"

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

    def _validate_working_dir(self, working_dir: Any) -> Tuple[Path | None, str]:
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

    def _build_env(self, sandbox: bool = False, sandbox_network: bool = False) -> dict[str, str]:
        """
        Build environment for subprocess.

        sandbox=False:
            Minimal inherited environment.

        sandbox=True:
            Much more restrictive environment.
        """
        env: dict[str, str] = {}

        if sandbox:
            # Minimal environment in sandbox mode
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONNOUSERSITE"] = "1"
            env["HOME"] = tempfile.gettempdir()
            env["TMP"] = tempfile.gettempdir()
            env["TEMP"] = tempfile.gettempdir()

            # Policy flag only; does NOT truly disable networking at OS level.
            env["PY_EXECUTOR_SANDBOX"] = "1"
            env["PY_EXECUTOR_NETWORK"] = "1" if sandbox_network else "0"

            # Minimal PATH so sys.executable dependencies still work
            if "PATH" in os.environ:
                env["PATH"] = os.environ["PATH"]

            return env

        # Non-sandbox: lightly restricted env
        if "PATH" in os.environ:
            env["PATH"] = os.environ["PATH"]

        for key in ("SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "TMP", "TEMP"):
            if key in os.environ:
                env[key] = os.environ[key]

        env.update(self.base_env)
        return env

    def _format_result(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        executed_label: str | None = None,
        sandbox: bool = False,
    ) -> str:
        """Format subprocess output in a consistent way."""
        output: list[str] = []

        if executed_label:
            output.append(f"=== EXECUTED: {executed_label} ===")

        output.append(f"=== SANDBOX MODE: {'ON' if sandbox else 'OFF'} ===")

        if stdout:
            output.append("=== STDOUT ===")
            output.append(stdout.rstrip())

        if stderr:
            output.append("=== STDERR ===")
            output.append(stderr.rstrip())

        output.append(f"=== EXIT CODE: {returncode} ===")

        if not stdout and not stderr:
            output.append("Script executed successfully (no output)")

        return "\n".join(output)

    def _build_python_cmd(self, target_path: Path, sandbox: bool) -> list[str]:
        """
        Build python invocation command.

        In sandbox mode use isolated flags:
        -I : isolated mode
        -S : don't import site
        -B : don't write .pyc
        -E : ignore PYTHON* environment variables
        """
        if sandbox:
            return [sys.executable, "-I", "-S", "-B", "-E", str(target_path)]
        return [sys.executable, str(target_path)]

    def _make_preexec_fn(self, sandbox: bool):
        """
        POSIX-only resource limiting hook.
        Returns None on unsupported systems.
        """
        if not sandbox:
            return None

        if os.name != "posix":
            return None

        def _preexec():
            import resource

            limits = self.sandbox_limits

            # CPU time
            resource.setrlimit(resource.RLIMIT_CPU, (limits["cpu_seconds"], limits["cpu_seconds"]))

            # Address space / memory
            resource.setrlimit(resource.RLIMIT_AS, (limits["memory_bytes"], limits["memory_bytes"]))

            # Max file size
            resource.setrlimit(resource.RLIMIT_FSIZE, (limits["file_size_bytes"], limits["file_size_bytes"]))

            # Max open files
            resource.setrlimit(resource.RLIMIT_NOFILE, (limits["nofile"], limits["nofile"]))

            # No child processes
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))

        return _preexec

    def _run_python_target(
        self,
        target_path: Path,
        timeout: int,
        working_dir: Path | None,
        executed_label: str | None = None,
        sandbox: bool = False,
        sandbox_network: bool = False,
        raw_output: bool = False,
    ) -> Tuple[str, str]:
        """Run a Python file and collect output."""
        try:
            result = subprocess.run(
                self._build_python_cmd(target_path=target_path, sandbox=sandbox),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(working_dir) if working_dir else None,
                env=self._build_env(sandbox=sandbox, sandbox_network=sandbox_network),
                preexec_fn=self._make_preexec_fn(sandbox),
            )

            if raw_output:
                # Return raw output: stdout, then stderr if present
                output = result.stdout
                if result.stderr:
                    output += result.stderr
                return output, ""
            else:
                # Return formatted output (original behavior)
                formatted = self._format_result(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    returncode=result.returncode,
                    executed_label=executed_label,
                    sandbox=sandbox,
                )
                return formatted, ""

        except subprocess.TimeoutExpired:
            return "", f"Script execution timed out after {timeout} seconds"
        except FileNotFoundError as exc:
            return "", f"Execution failed: {exc}"
        except OSError as exc:
            return "", f"OS error during execution: {exc}"
        except Exception as exc:
            return "", f"Unexpected execution error: {exc}"

    def _execute_code(
        self,
        code: Any,
        timeout: int = 30,
        working_dir: Any = ".",
        sandbox: bool = False,
        sandbox_network: bool = False,
        sandbox_readonly: bool = True,
        raw_output: bool = False,
    ) -> Tuple[str, str]:
        """Execute Python code by writing it to a temporary file."""
        if not isinstance(code, str) or not code.strip():
            return "", "Missing required argument: code"

        wd_path, wd_error = self._validate_working_dir(working_dir)
        if wd_error:
            return "", wd_error

        try:
            with tempfile.TemporaryDirectory(prefix="pyexec_") as tmp_dir:
                tmp_root = Path(tmp_dir)

                # In sandbox_readonly mode use temp dir as cwd to reduce accidental writes
                effective_wd = tmp_root if sandbox and sandbox_readonly else wd_path

                tmp_path = tmp_root / "inline_exec.py"
                tmp_path.write_text(code, encoding="utf-8")

                return self._run_python_target(
                    target_path=tmp_path,
                    timeout=timeout,
                    working_dir=effective_wd,
                    executed_label="<inline_code>",
                    sandbox=sandbox,
                    sandbox_network=sandbox_network,
                    raw_output=raw_output,
                )

        except Exception as exc:
            return "", f"Error preparing code execution: {exc}"

    def _execute_file(
        self,
        file_path: Any,
        timeout: int = 30,
        working_dir: Any = None,
        sandbox: bool = False,
        sandbox_network: bool = False,
        sandbox_readonly: bool = True,
        raw_output: bool = False,
    ) -> Tuple[str, str]:
        """Execute an existing Python file."""
        if not isinstance(file_path, str) or not file_path.strip():
            return "", "Missing required argument: file_path"

        script_path = Path(file_path).resolve()

        if not script_path.exists():
            return "", f"File not found: {file_path}"

        if not script_path.is_file():
            return "", f"Path is not a file: {file_path}"

        if script_path.suffix.lower() != ".py":
            return "", "File must be a Python script (.py)"

        if not self._is_path_allowed(script_path):
            allowed = ", ".join(str(p) for p in self.allowed_roots)
            return "", (
                "Access denied: file is outside allowed directories. "
                f"Allowed roots: {allowed}"
            )

        wd_path, wd_error = self._validate_working_dir(working_dir)
        if wd_error:
            return "", wd_error

        if wd_path is None:
            wd_path = script_path.parent

        try:
            with tempfile.TemporaryDirectory(prefix="pyexec_") as tmp_dir:
                tmp_root = Path(tmp_dir)
                effective_wd = tmp_root if sandbox and sandbox_readonly else wd_path

                return self._run_python_target(
                    target_path=script_path,
                    timeout=timeout,
                    working_dir=effective_wd,
                    executed_label=file_path,
                    sandbox=sandbox,
                    sandbox_network=sandbox_network,
                    raw_output=raw_output,
                )
        except Exception as exc:
            return "", f"Error preparing file execution: {exc}"

    def _show_help(self) -> Tuple[str, str]:
        """Show help information."""
        help_text = f"""Python Executor Tool

DESCRIPTION:
    Execute Python code or Python script files in a subprocess.

IMPORTANT:
    This tool is not a secure sandbox.
    Sandbox mode is best-effort hardening only.
    File execution is restricted to allowed directories.

ALLOWED DIRECTORIES:
    {os.linesep.join(f"    - {str(p)}" for p in self.allowed_roots)}

OPERATIONS:
    execute
        Execute Python code from a string.

    execute_file
        Execute an existing .py file.

    help
        Show this help message.

PARAMETERS:
    operation (string, required)
        One of: execute, execute_file, help

    code (string)
        Required for operation=execute

    file_path (string)
        Required for operation=execute_file

    timeout (integer, optional)
        Timeout in seconds. Default: 30, max: 300

    working_dir (string, optional)
        Working directory for process execution

    sandbox (boolean, optional)
        Enable best-effort sandbox mode

    sandbox_network (boolean, optional)
        Allow network in sandbox mode. Default: false
        NOTE: this is policy metadata only unless enforced externally.

    sandbox_readonly (boolean, optional)
        Use isolated temp working directory in sandbox mode. Default: true

EXAMPLES:
    {{"operation": "execute", "code": "print('Hello World')"}}

    {{"operation": "execute",
      "code": "print('safe-ish run')",
      "sandbox": true}}

    {{"operation": "execute_file",
      "file_path": "scripts/test.py",
      "sandbox": true,
      "timeout": 5}}

OUTPUT FORMAT:
    === EXECUTED: ... ===
    === SANDBOX MODE: ON/OFF ===
    === STDOUT ===
    ...
    === STDERR ===
    ...
    === EXIT CODE: N ===

NOTES:
    - STDERR does not always mean failure.
    - Non-zero exit code usually indicates an error.
    - Sandbox mode is not a full security boundary.
"""
        return help_text, ""