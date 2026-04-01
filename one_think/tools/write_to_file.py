"""
WriteToFile Tool - Full JSON migration
Write content to files with structured responses
"""
from pathlib import Path
from typing import Dict, Any, Optional

from one_think.tools.base import Tool, ToolResponse


class WriteToFile(Tool):
    """Tool for writing content to a file."""

    name = "write_to_file"
    description = "Writes content to a file at a given path."

    DEFAULT_MODE = "w"

    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute file write with JSON response."""
        
        # Validate path
        path_str = params.get("path")
        if not path_str or not isinstance(path_str, str):
            return self._create_error_response(
                "Missing or invalid parameter: 'path'",
                request_id=request_id
            )
        
        # Get content
        content = params.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        
        # Get mode
        mode = params.get("mode", self.DEFAULT_MODE)
        if not isinstance(mode, str):
            return self._create_error_response(
                "'mode' must be a string",
                request_id=request_id
            )
        
        mode = mode.strip().lower()
        if mode not in {"w", "a"}:
            return self._create_error_response(
                "Invalid mode. Use 'w' (overwrite) or 'a' (append)",
                request_id=request_id
            )
        
        path = Path(path_str)
        
        try:
            if path.exists() and path.is_dir():
                return self._create_error_response(
                    "Path points to a directory, not a file",
                    request_id=request_id
                )
            
            # Create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            with path.open(mode, encoding="utf-8") as f:
                f.write(content)
            
            return self._create_success_response(
                result={
                    "message": f"Successfully wrote to file",
                    "path": str(path.resolve()),
                    "mode": mode,
                    "bytes_written": len(content.encode('utf-8')),
                    "characters": len(content),
                    "lines": len(content.splitlines())
                },
                request_id=request_id
            )
        
        except PermissionError:
            return self._create_error_response(
                "Permission denied",
                request_id=request_id
            )
        except OSError as e:
            return self._create_error_response(
                f"File system error: {e}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Unexpected error: {e}",
                request_id=request_id
            )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return f"""WriteToFile Tool

DESCRIPTION:
    Writes content to a file at a given path.

PARAMETERS:
    path (string, required)
        Target file path

    content (string, optional)
        Text to write (default: empty string)

    mode (string, optional)
        Write mode:
        - 'w': overwrite (default)
        - 'a': append

EXAMPLES:
    1. Write new file:
       {{"path": "output.txt", "content": "Hello World", "mode": "w"}}

    2. Append to file:
       {{"path": "log.txt", "content": "\\nNew entry", "mode": "a"}}

    3. Create empty file:
       {{"path": "marker.txt"}}

BEHAVIOR:
    - Creates parent directories if they do not exist
    - Overwrites or appends depending on mode
    - Returns absolute path on success
    - Uses UTF-8 encoding

RESPONSE FORMAT:
    Success:
        {{
            "status": "success",
            "result": {{
                "message": "Successfully wrote to file",
                "path": "/absolute/path/to/file",
                "mode": "w",
                "bytes_written": 123,
                "characters": 100,
                "lines": 5
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
    - Path can be relative or absolute
    - Parent directories are created automatically
    - Use mode='a' to preserve existing content
"""
