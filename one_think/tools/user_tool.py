"""
UserTool - Full JSON migration with Pydantic schemas.
Manages USER.md file with structured JSON responses and validation.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from one_think.tools.base import Tool, ToolResponse

load_dotenv()


class UserTool(Tool):
    """Manages the USER.md file - user information and preferences."""
    
    name = "user"
    description = "Manages the USER.md file - user information and preferences."
    version = "2.0.0"
    
    # Pydantic schemas
    class Input(BaseModel):
        """Input parameters for user operations."""
        operation: Literal["read", "write", "append"] = Field(description="User operation: read, write, or append")
        content: Optional[str] = Field(default=None, description="Content to write/append (required for write/append)")
        
    class Output(BaseModel):
        """Output format for user operations."""
        operation: str = Field(description="Operation that was performed")
        content: Optional[str] = Field(description="Current user content (for read operations)")
        file_path: str = Field(description="Path to user file")
        success: bool = Field(description="Whether operation succeeded")
        message: str = Field(description="Status message")
    
    def __init__(self) -> None:
        super().__init__()
        self.user_path = self._get_user_path()
    
    def _get_user_path(self) -> Path:
        """Get USER.md file path from .env or use default."""
        user_path_str = os.getenv("USER_PATH", "persistent/USER.md")
        return Path(user_path_str)
    
    def _ensure_file_exists(self) -> None:
        """Ensure USER.md file exists, create if not."""
        if not self.user_path.exists():
            # Create directory if needed
            self.user_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file with default template
            default_content = """# USER - User Information
This file stores important information about the user, any context that should be remembered across sessions.
"""
            self.user_path.write_text(default_content, encoding='utf-8')
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute user operation with JSON response."""
        
        # Validate required params
        error = self.validate_required_params(params, required=["operation"])
        if error:
            return error
        
        operation = params["operation"]
        
        # Route to operation handlers
        if operation == "read":
            return self._read_user(request_id)
        elif operation == "write":
            return self._write_user(params, request_id)
        elif operation == "append":
            return self._append_user(params, request_id)
        elif operation == "clear":
            return self._clear_user(request_id)
        else:
            return self._create_error_response(
                f"Unknown operation: '{operation}'. Valid operations: read, write, append, clear",
                request_id=request_id
            )
    
    def _read_user(self, request_id: Optional[str]) -> ToolResponse:
        """Read content from USER.md file."""
        try:
            self._ensure_file_exists()
            content = self.user_path.read_text(encoding='utf-8')
            
            if not content.strip():
                return self._create_success_response(
                    result={
                        "content": "",
                        "message": "USER.md file is empty",
                        "path": str(self.user_path),
                        "size_bytes": 0
                    },
                    request_id=request_id
                )
            
            return self._create_success_response(
                result={
                    "content": content,
                    "path": str(self.user_path),
                    "size_bytes": len(content),
                    "lines": len(content.splitlines())
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error reading USER.md: {e}",
                request_id=request_id
            )
    
    def _write_user(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Write content to USER.md file (overwrite)."""
        content = params.get("content")
        
        if not content:
            return self._create_error_response(
                "Missing required parameter: 'content'",
                request_id=request_id
            )
        
        try:
            # Ensure directory exists
            self.user_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            self.user_path.write_text(content, encoding='utf-8')
            
            lines_count = len(content.splitlines())
            chars_count = len(content)
            
            return self._create_success_response(
                result={
                    "message": f"Successfully wrote to USER.md",
                    "path": str(self.user_path),
                    "lines": lines_count,
                    "characters": chars_count
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error writing to USER.md: {e}",
                request_id=request_id
            )
    
    def _append_user(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Append content to USER.md file."""
        content = params.get("content")
        
        if not content:
            return self._create_error_response(
                "Missing required parameter: 'content'",
                request_id=request_id
            )
        
        try:
            self._ensure_file_exists()
            
            # Read existing content
            existing = self.user_path.read_text(encoding='utf-8')
            
            # Add newline if needed
            if existing and not existing.endswith('\n'):
                content = '\n' + content
            
            # Append
            self.user_path.write_text(existing + content, encoding='utf-8')
            
            return self._create_success_response(
                result={
                    "message": f"Successfully appended to USER.md",
                    "path": str(self.user_path),
                    "appended_characters": len(content)
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error appending to USER.md: {e}",
                request_id=request_id
            )
    
    def _clear_user(self, request_id: Optional[str]) -> ToolResponse:
        """Clear USER.md file content."""
        try:
            self.user_path.write_text("", encoding='utf-8')
            
            return self._create_success_response(
                result={
                    "message": "Successfully cleared USER.md",
                    "path": str(self.user_path)
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error clearing USER.md: {e}",
                request_id=request_id
            )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """User Tool - USER.md Management

DESCRIPTION:
    Manages the USER.md file containing user information and preferences.
    File path is configured in .env via USER_PATH (default: persistent/USER.md).

OPERATIONS:
    read    - Read and display the entire content of USER.md
    write   - Write new content to USER.md (overwrites existing content)
    append  - Append content to the end of USER.md
    clear   - Clear all content from USER.md

PARAMETERS:
    operation (required) - The operation to perform: read, write, append, clear
    content (optional)   - Content for write/append operations

EXAMPLES:
    1. Read user information:
       {"operation": "read"}
    
    2. Write new user information:
       {"operation": "write", "content": "# USER\\n\\n## Name\\nJohn Doe..."}
    
    3. Append additional information:
       {"operation": "append", "content": "\\n## New Project\\n- Project details"}
    
    4. Clear all information:
       {"operation": "clear"}

USER.MD PURPOSE:
    - Store user personal information
    - Define communication preferences
    - Document technical background
    - Track current projects and goals
    - Define working style and availability

WHAT TO INCLUDE:
    - Name and role
    - Contact preferences
    - Technical skills and expertise
    - Current projects and context
    - Working hours and availability
    - Communication style preferences
    - Goals and priorities

CONFIGURATION:
    Set USER_PATH in .env file:
        USER_PATH=persistent/USER.md

RESPONSE FORMAT:
    Success:
        {
            "status": "success",
            "result": {
                "content": "...",      // for read operation
                "message": "...",      // for write/append/clear
                "path": "...",
                "lines": N,            // number of lines
                "characters": N        // number of characters
            }
        }
    
    Error:
        {
            "status": "error",
            "error": {
                "message": "Error description",
                "type": "ToolExecutionError"
            }
        }

NOTES:
    - File is automatically created with default template if it doesn't exist
    - Use 'write' to completely replace content
    - Use 'append' to add to existing content
    - USER.md is stored in persistent/ (not committed to git for privacy)
    - Keep sensitive personal information minimal
"""
