"""
MemoryTool - Full JSON migration with Pydantic schemas.
Manages MEMORY.md file with structured JSON responses and validation.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from one_think.tools.base import Tool, ToolResponse

load_dotenv()


class MemoryTool(Tool):
    """Manages the MEMORY.md file - important context across sessions."""
    
    name = "memory"
    description = "Manages the MEMORY.md file - important information and context the model should remember."
    version = "2.0.0"
    
    # Pydantic schemas
    class Input(BaseModel):
        """Input parameters for memory operations."""
        operation: Literal["read", "write", "append"] = Field(description="Memory operation: read, write, or append")
        content: Optional[str] = Field(default=None, description="Content to write/append (required for write/append)")
        
    class Output(BaseModel):
        """Output format for memory operations."""
        operation: str = Field(description="Operation that was performed")
        content: Optional[str] = Field(description="Current memory content (for read operations)")
        file_path: str = Field(description="Path to memory file")
        success: bool = Field(description="Whether operation succeeded")
        message: str = Field(description="Status message")
    
    def __init__(self) -> None:
        super().__init__()
        self.memory_path = self._get_memory_path()
    
    def _get_memory_path(self) -> Path:
        """Get MEMORY.md file path from .env or use default."""
        memory_path_str = os.getenv("MEMORY_PATH", "persistent/MEMORY.md")
        return Path(memory_path_str)
    
    def _ensure_file_exists(self) -> None:
        """Ensure MEMORY.md file exists, create if not."""
        if not self.memory_path.exists():
            # Create directory if needed
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file with default template
            default_content = """# MEMORY - Important Context

This file stores important information that the model should remember across sessions.

"""
            self.memory_path.write_text(default_content, encoding='utf-8')
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute memory operation with JSON response."""
        
        # Validate required params
        error = self.validate_required_params(params, required=["operation"])
        if error:
            return error
        
        operation = params["operation"]
        
        # Route to operation handlers
        if operation == "read":
            return self._read_memory(request_id)
        elif operation == "write":
            return self._write_memory(params, request_id)
        elif operation == "append":
            return self._append_memory(params, request_id)
        elif operation == "clear":
            return self._clear_memory(request_id)
        else:
            return self._create_error_response(
                f"Unknown operation: '{operation}'. Valid operations: read, write, append, clear",
                request_id=request_id
            )
    
    def _read_memory(self, request_id: Optional[str]) -> ToolResponse:
        """Read content from MEMORY.md file."""
        try:
            self._ensure_file_exists()
            content = self.memory_path.read_text(encoding='utf-8')
            
            if not content.strip():
                return self._create_success_response(
                    result={
                        "content": "",
                        "message": "MEMORY.md file is empty",
                        "path": str(self.memory_path),
                        "size_bytes": 0
                    },
                    request_id=request_id
                )
            
            return self._create_success_response(
                result={
                    "content": content,
                    "path": str(self.memory_path),
                    "size_bytes": len(content),
                    "lines": len(content.splitlines())
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error reading MEMORY.md: {e}",
                request_id=request_id
            )
    
    def _write_memory(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Write content to MEMORY.md file (overwrite)."""
        content = params.get("content")
        
        if not content:
            return self._create_error_response(
                "Missing required parameter: 'content'",
                request_id=request_id
            )
        
        try:
            # Ensure directory exists
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            self.memory_path.write_text(content, encoding='utf-8')
            
            lines_count = len(content.splitlines())
            chars_count = len(content)
            
            return self._create_success_response(
                result={
                    "message": f"Successfully wrote to MEMORY.md",
                    "path": str(self.memory_path),
                    "lines": lines_count,
                    "characters": chars_count
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error writing to MEMORY.md: {e}",
                request_id=request_id
            )
    
    def _append_memory(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Append content to MEMORY.md file."""
        content = params.get("content")
        
        if not content:
            return self._create_error_response(
                "Missing required parameter: 'content'",
                request_id=request_id
            )
        
        try:
            self._ensure_file_exists()
            
            # Read existing content
            existing = self.memory_path.read_text(encoding='utf-8')
            
            # Add newline if needed
            if existing and not existing.endswith('\n'):
                content = '\n' + content
            
            # Append
            self.memory_path.write_text(existing + content, encoding='utf-8')
            
            return self._create_success_response(
                result={
                    "message": f"Successfully appended to MEMORY.md",
                    "path": str(self.memory_path),
                    "appended_characters": len(content)
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error appending to MEMORY.md: {e}",
                request_id=request_id
            )
    
    def _clear_memory(self, request_id: Optional[str]) -> ToolResponse:
        """Clear MEMORY.md file content."""
        try:
            self.memory_path.write_text("", encoding='utf-8')
            
            return self._create_success_response(
                result={
                    "message": "Successfully cleared MEMORY.md",
                    "path": str(self.memory_path)
                },
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error clearing MEMORY.md: {e}",
                request_id=request_id
            )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """Memory Tool - MEMORY.md Management

DESCRIPTION:
    Manages the MEMORY.md file containing important context and information
    that the model should remember across sessions.
    File path is configured in .env via MEMORY_PATH (default: persistent/MEMORY.md).

OPERATIONS:
    read    - Read and display the entire content of MEMORY.md
    write   - Write new content to MEMORY.md (overwrites existing content)
    append  - Append content to the end of MEMORY.md
    clear   - Clear all content from MEMORY.md

PARAMETERS:
    operation (required) - The operation to perform: read, write, append, clear
    content (optional)   - Content for write/append operations

EXAMPLES:
    1. Read memory:
       {"operation": "read"}
    
    2. Write new memory:
       {"operation": "write", "content": "# Important context..."}
    
    3. Append to memory:
       {"operation": "append", "content": "\\n## New info\\n- Remember X"}
    
    4. Clear memory:
       {"operation": "clear"}

MEMORY.MD PURPOSE:
    - Store important context across sessions
    - Remember key decisions and their rationale
    - Track learned user preferences
    - Document important facts about the project
    - Keep notes on recurring issues or patterns
    - Store information that should persist

WHAT TO STORE:
    ✅ Important project decisions
    ✅ User preferences discovered during conversations
    ✅ Key facts about the codebase or architecture
    ✅ Lessons learned from past mistakes
    ✅ Recurring patterns or issues
    ✅ Important context that shouldn't be forgotten
    ✅ Custom workflows or procedures
    
    ❌ Sensitive personal data
    ❌ Passwords or credentials (use credentials_tool)
    ❌ Temporary notes (use regular files)

USAGE PATTERNS:
    1. After important decisions:
       Store the decision and reasoning for future reference
    
    2. When user corrects you:
       Remember the correction to avoid repeating mistakes
    
    3. Learning preferences:
       Track user's style preferences, naming conventions, etc.
    
    4. Project context:
       Remember key aspects of the project that are frequently relevant

CONFIGURATION:
    Set MEMORY_PATH in .env file:
        MEMORY_PATH=persistent/MEMORY.md

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
    - MEMORY.md is stored in persistent/ (not committed to git)
    - Review and clean periodically to keep relevant
"""
