"""
Soul Tool - System instructions and behavior guidelines management.

Migrated to new JSON format with Pydantic schemas, validation and structured responses.
"""

import os
import time
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from one_think.tools.base import Tool, ToolResponse

load_dotenv()


class SoulTool(Tool):
    """
    Manages SOUL.md file containing system instructions and behavior guidelines.
    
    Operations:
    - read: Get current system instructions
    - write: Replace entire content
    - append: Add to existing content
    - clear: Remove all content
    """
    
    name = "soul"
    description = "Manages system instructions and behavior guidelines (SOUL.md)"
    version = "2.0.0"
    
    # Pydantic schemas
    class Input(BaseModel):
        """Input parameters for soul operations."""
        operation: Literal["read", "write", "append", "clear"] = Field(description="Soul operation: read, write, append, or clear")
        content: Optional[str] = Field(default=None, description="Content to write/append (required for write/append)")
        
    class Output(BaseModel):
        """Output format for soul operations."""
        operation: str = Field(description="Operation that was performed")
        content: Optional[str] = Field(description="Current soul content (for read operations)")
        file_path: str = Field(description="Path to soul file")
        success: bool = Field(description="Whether operation succeeded")
        message: str = Field(description="Status message")
    
    name = "soul"
    description = "Manages SOUL.md file - system instructions and behavior guidelines"
    version = "2.0.0"
    
    def __init__(self):
        super().__init__()
        self.soul_path = self._get_soul_path()
    
    def _get_soul_path(self) -> str:
        """Get SOUL.md file path from environment or use default."""
        soul_path = os.getenv("SOUL_PATH")
        if not soul_path:
            soul_path = "persistent/SOUL.md"
        return soul_path
    
    def _ensure_file_exists(self):
        """Ensure SOUL.md file exists, create with default template if not."""
        if not os.path.exists(self.soul_path):
            os.makedirs(os.path.dirname(self.soul_path) or '.', exist_ok=True)
            
            default_content = """# SOUL - System Instructions

## System Behavior

This section defines how the system should behave and operate.

"""
            with open(self.soul_path, 'w', encoding='utf-8') as f:
                f.write(default_content)
    
    def execute_json(
        self,
        params: dict[str, Any],
        request_id: Optional[str] = None
    ) -> ToolResponse:
        """
        Execute soul operation with strict JSON response.
        
        Args:
            params: {
                "operation": str (required) - read|write|append|clear,
                "content": str (optional) - for write/append operations
            }
            request_id: Optional request ID
            
        Returns:
            ToolResponse with operation result
        """
        
        # Check for help request first
        if params.get("help"):
            return self._create_success_response(
                result={"help": self.get_help()},
                request_id=request_id
            )
        
        start_time = time.perf_counter()
        
        # Validate operation parameter
        error_resp = self.validate_required_params(params, ["operation"])
        if error_resp:
            return error_resp
        
        operation = params["operation"]
        valid_operations = ["read", "write", "append", "clear"]
        
        if operation not in valid_operations:
            return self._create_error_response(
                error_type="ValidationError",
                message=f"Unknown operation: '{operation}'",
                details={
                    "provided": operation,
                    "valid_operations": valid_operations
                },
                request_id=request_id
            )
        
        # Execute operation
        try:
            if operation == "read":
                result = self._read_soul()
            elif operation == "write":
                result = self._write_soul(params.get("content"))
            elif operation == "append":
                result = self._append_soul(params.get("content"))
            elif operation == "clear":
                result = self._clear_soul()
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            return self._create_success_response(
                result=result,
                request_id=request_id,
                execution_time_ms=elapsed_ms,
                metadata={"soul_path": self.soul_path}
            )
        
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return self._create_error_response(
                error_type=type(e).__name__,
                message=str(e),
                details={"operation": operation},
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
    
    def _read_soul(self) -> dict[str, Any]:
        """Read content from SOUL.md file."""
        self._ensure_file_exists()
        
        with open(self.soul_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "operation": "read",
            "content": content,
            "char_count": len(content),
            "line_count": len(content.split('\n')),
            "is_empty": not content.strip()
        }
    
    def _write_soul(self, content: Optional[str]) -> dict[str, Any]:
        """Write content to SOUL.md file (overwrite)."""
        if content is None:
            raise ValueError("Content is required for 'write' operation")
        
        if not content:
            raise ValueError("Content cannot be empty for 'write' operation")
        
        with open(self.soul_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "operation": "write",
            "char_count": len(content),
            "line_count": len(content.split('\n')),
            "message": "Successfully wrote to SOUL.md"
        }
    
    def _append_soul(self, content: Optional[str]) -> dict[str, Any]:
        """Append content to SOUL.md file."""
        if content is None:
            raise ValueError("Content is required for 'append' operation")
        
        if not content:
            raise ValueError("Content cannot be empty for 'append' operation")
        
        self._ensure_file_exists()
        
        with open(self.soul_path, 'a', encoding='utf-8') as f:
            # Add newline if content doesn't start with one
            if not content.startswith('\n'):
                f.write('\n')
            f.write(content)
        
        return {
            "operation": "append",
            "appended_chars": len(content),
            "message": "Successfully appended to SOUL.md"
        }
    
    def _clear_soul(self) -> dict[str, Any]:
        """Clear SOUL.md file content."""
        with open(self.soul_path, 'w', encoding='utf-8') as f:
            f.write("")
        
        return {
            "operation": "clear",
            "message": "Successfully cleared SOUL.md"
        }
    
    def get_help(self) -> str:
        """Return detailed help for soul tool."""
        return f"""
Tool: {self.name} (v{self.version})
Description: {self.description}

PURPOSE:
    Manages SOUL.md file containing:
    - System behavior and personality
    - Communication style and tone
    - Operating principles
    - Technical preferences
    - Response format guidelines
    - Error handling approach

OPERATIONS:

  read - Read current content from SOUL.md
    Parameters: none
    Returns: {{
      "content": "file content",
      "char_count": integer,
      "line_count": integer,
      "is_empty": boolean
    }}

  write - Replace entire SOUL.md content
    Parameters:
      content (string, required): New content to write
    Returns: {{
      "char_count": integer,
      "line_count": integer,
      "message": "success message"
    }}

  append - Append content to SOUL.md
    Parameters:
      content (string, required): Content to append
    Returns: {{
      "appended_chars": integer,
      "message": "success message"
    }}

  clear - Clear all content from SOUL.md
    Parameters: none
    Returns: {{
      "message": "success message"
    }}

CONFIGURATION:
    Set SOUL_PATH in .env file:
        SOUL_PATH=persistent/SOUL.md
    
    Default: persistent/SOUL.md

EXAMPLES:

  1. Read current instructions:
     {{"operation": "read"}}

  2. Write new instructions:
     {{
       "operation": "write",
       "content": "# New SOUL instructions..."
     }}

  3. Append guidelines:
     {{
       "operation": "append",
       "content": "\\n## New Section\\n- Rule 1"
     }}

  4. Clear all:
     {{"operation": "clear"}}

NOTES:
    - File created automatically if doesn't exist
    - SOUL.md can be version controlled
    - Contains instructions, not secrets
    - Use 'write' for complete replacement
    - Use 'append' to add to existing content

Current SOUL path: {self.soul_path}
"""


if __name__ == "__main__":
    tool = SoulTool()
    
    # Test help
    print("=== HELP ===")
    resp = tool(params={"help": True})
    print(resp.result["help"][:300])
    
    # Test read
    print("\n=== READ ===")
    resp = tool(params={"operation": "read"})
    print(f"Status: {resp.status}")
    if resp.status == "success":
        print(f"Content length: {resp.result['char_count']} chars")
        print(f"Lines: {resp.result['line_count']}")
    else:
        print(f"Error: {resp.error}")
