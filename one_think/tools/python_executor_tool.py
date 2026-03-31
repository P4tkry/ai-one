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
    - Direct code execution still allows arbitrary Python code.
    """

    name = "python_executor"
    description = "Execute Python code or Python script files"

    arguments = {
        "operation": "Operation to perform: execute, execute_file, help",
        "code": "Python code to execute (required for 'execute')",
        "file_path": "Path to Python file to execute (required for 'execute_file')",
        "timeout": "Optional timeout in seconds (default: 30)",
        "working_dir": "Optional working directory for execution",
        "help": "Show help information (optional, boolean)",
    }

    def __init__(self) -> None:
        super().__init__()

        # Restrict execute_file to these directories.
        # Adjust these to match your project layout.
        self.allowed_roots = [
            Path(".").resolve(),
            Path("./persistent").resolve(),
            Path("./scripts").resolve(),
            Path("./tests").resolve(),
        ]

        # Minimal environment passed to subprocess.
        # Add variables here if your scripts need them.
        self.base_env = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
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

        if operation == "execute":
            code = arguments.get("code")
            working_dir = arguments.get("working_dir", ".")
            return self._execute_code(code=code, timeout=timeout, working_dir=working_dir)

        if operation == "execute_file":
            file_path = arguments.get("file_path")
            working_dir = arguments.get("working_dir")
            return self._execute_file(file_path=file_path, timeout=timeout, working_dir=working_dir)

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

        # Hard cap to avoid extremely long executions by mistake
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

    def _build_env(self) -> dict[str, str]:
        """
        Build environment for subprocess.

        Intentionally restrictive. Extend if needed.
        """
        env: dict[str, str] = {}

        # Keep a minimal PATH so Python can run dependencies if needed
        if "PATH" in os.environ:
            env["PATH"] = os.environ["PATH"]

        # Keep common system settings if present
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
    ) -> str:
        """Format subprocess output in a consistent way."""
        output: list[str] = []

        if executed_label:
            output.append(f"=== EXECUTED: {executed_label} ===")

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

    def _run_python_target(
        self,
        target_path: Path,
        timeout: int,
        working_dir: Path | None,
        executed_label: str | None = None,
    ) -> Tuple[str, str]:
        """Run a Python file and collect output."""
        try:
            result = subprocess.run(
                [sys.executable, str(target_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(working_dir) if working_dir else None,
                env=self._build_env(),
            )

            formatted = self._format_result(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                executed_label=executed_label,
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
    ) -> Tuple[str, str]:
        """Execute Python code by writing it to a temporary file."""
        if not isinstance(code, str) or not code.strip():
            return "", "Missing required argument: code"

        wd_path, wd_error = self._validate_working_dir(working_dir)
        if wd_error:
            return "", wd_error

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as tmp_file:
                tmp_file.write(code)
                tmp_path = Path(tmp_file.name)

            try:
                return self._run_python_target(
                    target_path=tmp_path,
                    timeout=timeout,
                    working_dir=wd_path,
                    executed_label="<inline_code>",
                )
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        except Exception as exc:
            return "", f"Error preparing code execution: {exc}"

    def _execute_file(
        self,
        file_path: Any,
        timeout: int = 30,
        working_dir: Any = None,
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

        return self._run_python_target(
            target_path=script_path,
            timeout=timeout,
            working_dir=wd_path,
            executed_label=file_path,
        )

    def _show_help(self) -> Tuple[str, str]:
        """Show help information."""
        help_text = f"""Python Executor Tool

DESCRIPTION:
    Execute Python code or Python script files in a subprocess.

IMPORTANT:
    This tool is not a secure sandbox.
    It is intended for trusted or local development use.
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

EXAMPLES:
    {{"operation": "execute", "code": "print('Hello World')"}}

    {{"operation": "execute",
      "code": "for i in range(3):\\n    print(i)",
      "timeout": 10}}

    {{"operation": "execute_file", "file_path": "scripts/test.py"}}

    {{"operation": "execute_file",
      "file_path": "persistent/process_data.py",
      "timeout": 60}}

OUTPUT FORMAT:
    === EXECUTED: ... ===
    === STDOUT ===
    ...
    === STDERR ===
    ...
    === EXIT CODE: N ===

NOTES:
    - STDERR does not always mean failure.
    - Non-zero exit code usually indicates an error.
    - Direct code execution can run arbitrary Python.
"""
        return help_text, ""