"""
JSON Protocol parsing and validation for AI-ONE.

This module handles parsing LLM responses and validating them against
the expected JSON protocol.

Protocol supports:
1. Response - final answer to user
2. Tool Request - request to execute tools
3. System Refresh Request - request to refresh system prompt
"""

import json
import logging
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

logger = logging.getLogger(__name__)


class ResponseType(str, Enum):
    """Type of response from LLM."""
    RESPONSE = "response"
    TOOL_REQUEST = "tool_request"
    WORKFLOW_REQUEST = "workflow_request"  # NEW
    SYSTEM_REFRESH_REQUEST = "system_refresh_request"
    SYSTEM_INSTRUCTION_REMIND = "system_instruction_remind"


class ToolCall(BaseModel):
    """
    Single tool call specification.
    
    Fields:
        tool_name: Name of tool to execute
        params: Parameters for tool execution
        id: Optional unique identifier for tracking
    """
    tool_name: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None
    
    @field_validator('tool_name')
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """Ensure tool_name is not empty."""
        if not v.strip():
            raise ValueError("tool_name cannot be empty")
        return v.strip()


class WorkflowToolCall(BaseModel):
    """
    Tool call specification for workflows with dependencies.
    
    Fields:
        tool_name: Name of tool to execute
        params: Parameters for tool execution (can contain {step_id.field} references)
        id: Unique identifier for this workflow step (required)
        depends_on: List of step IDs this step depends on
    """
    tool_name: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(..., min_length=1)  # Required for workflows
    depends_on: list[str] = Field(default_factory=list)
    
    @field_validator('tool_name')
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """Ensure tool_name is not empty."""
        if not v.strip():
            raise ValueError("tool_name cannot be empty")
        return v.strip()
        
    @field_validator('id')
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure id is not empty."""
        if not v.strip():
            raise ValueError("id cannot be empty for workflow tools")
        return v.strip()


class Response(BaseModel):
    """
    Final response to user (no tools).
    
    Format:
    {
        "type": "response",
        "content": "answer text"
    }
    """
    type: ResponseType = Field(default=ResponseType.RESPONSE)
    content: str
    
    model_config = ConfigDict(frozen=False)


class ToolRequest(BaseModel):
    """
    Request to execute one or more tools.
    
    Format:
    {
        "type": "tool_request",
        "tools": [
            {
                "tool_name": "web_fetch",
                "params": {"url": "..."},
                "id": "req_001"
            }
        ]
    }
    """
    type: ResponseType = Field(default=ResponseType.TOOL_REQUEST)
    tools: list[ToolCall] = Field(..., min_length=1)
    
    model_config = ConfigDict(frozen=False)
    
    @field_validator('tools')
    @classmethod
    def validate_tools_not_empty(cls, v: list[ToolCall]) -> list[ToolCall]:
        """Ensure at least one tool is requested."""
        if not v:
            raise ValueError("tools list cannot be empty for tool_request")
        return v


class SystemRefreshRequest(BaseModel):
    """
    Request to refresh system prompt.
    
    Format:
    {
        "type": "system_refresh_request",
        "reason": "context window full"
    }
    """
    type: ResponseType = Field(default=ResponseType.SYSTEM_REFRESH_REQUEST)
    reason: Optional[str] = None
    
    model_config = ConfigDict(frozen=False)


class SystemInstructionRemindRequest(BaseModel):
    """
    Request for system instruction reminder.
    
    Format:
    {
        "type": "system_instruction_remind",
        "reason": "need reminder of system instructions"
    }
    """
    type: ResponseType = Field(default=ResponseType.SYSTEM_INSTRUCTION_REMIND)
    reason: Optional[str] = None
    
    model_config = ConfigDict(frozen=False)


class WorkflowRequest(BaseModel):
    """
    Request to execute a workflow of multiple tools with dependencies.
    
    Format:
    {
        "type": "workflow_request", 
        "execution_mode": "sequential",
        "error_handling": "abort",
        "tools": [
            {
                "tool_name": "web_fetch",
                "params": {"url": "..."},
                "id": "fetch_data"
            },
            {
                "tool_name": "python_executor",
                "params": {"code": "process({fetch_data.content})"},
                "id": "process_data",
                "depends_on": ["fetch_data"]
            }
        ]
    }
    """
    type: ResponseType = Field(default=ResponseType.WORKFLOW_REQUEST)
    execution_mode: str = Field(default="sequential")  # "sequential" | "parallel"
    error_handling: str = Field(default="abort")  # "abort" | "skip" | "retry"
    tools: list[WorkflowToolCall] = Field(..., min_length=1)
    
    model_config = ConfigDict(frozen=False)
    
    @field_validator('tools')
    @classmethod
    def validate_workflow_tools(cls, v: list[WorkflowToolCall]) -> list[WorkflowToolCall]:
        """Ensure workflow has at least one tool and valid dependencies."""
        if not v:
            raise ValueError("workflow tools list cannot be empty")
            
        # Validate dependencies reference existing tool IDs
        tool_ids = {tool.id for tool in v}
        for tool in v:
            for dep_id in tool.depends_on:
                if dep_id not in tool_ids:
                    raise ValueError(f"Tool {tool.id} depends on non-existent tool {dep_id}")
        
        return v
    
    @field_validator('execution_mode')
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        """Validate execution mode."""
        if v not in ("sequential", "parallel"):
            raise ValueError("execution_mode must be 'sequential' or 'parallel'")
        return v
        
    @field_validator('error_handling')
    @classmethod
    def validate_error_handling(cls, v: str) -> str:
        """Validate error handling policy."""
        if v not in ("abort", "skip", "retry"):
            raise ValueError("error_handling must be 'abort', 'skip', or 'retry'")
        return v


# Union type for protocol responses
ProtocolResponse = Response | ToolRequest | WorkflowRequest | SystemRefreshRequest | SystemInstructionRemindRequest


class ProtocolParser:
    """
    Parser for LLM JSON responses.
    
    Validates and parses JSON output from LLM into structured protocol objects.
    Handles errors gracefully and provides detailed error messages.
    """
    
    @staticmethod
    def parse(raw_response: str) -> ProtocolResponse:
        """
        Parse raw LLM response into protocol object.
        
        Args:
            raw_response: Raw string response from LLM (should be JSON)
            
        Returns:
            Parsed protocol response (Response, ToolRequest, or SystemRefreshRequest)
            
        Raises:
            ValueError: If response is invalid JSON or doesn't match protocol
        """
        # Parse JSON with fallback to plain text
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned malformed JSON: {e}")
            logger.debug(f"Raw response: {raw_response[:500]}...")
            
            # Return special error response for AI to recognize and fix
            error_details = f"JSON Parse Error: {str(e)}"
            if len(raw_response) > 1000:
                error_details += " (Response may be truncated)"
            
            return Response(content=f"<<JSON_MALFORMED_ERROR>> {error_details}")
        
        # Validate is dict
        if not isinstance(data, dict):
            raise ValueError(
                f"LLM response must be JSON object, got {type(data).__name__}"
            )
        
        # Check for required 'type' field
        if "type" not in data:
            raise ValueError(
                'LLM response missing required field "type"\n'
                f"Response: {json.dumps(data, indent=2)}"
            )
        
        response_type = data.get("type")
        
        # Parse based on type
        try:
            if response_type == "response":
                return Response(**data)
            
            elif response_type == "tool_request":
                return ToolRequest(**data)
            
            elif response_type == "workflow_request":
                return WorkflowRequest(**data)
            
            elif response_type == "system_refresh_request":
                return SystemRefreshRequest(**data)
            
            elif response_type == "system_instruction_remind":
                return SystemInstructionRemindRequest(**data)
            
            else:
                raise ValueError(
                    f'Unknown response type: "{response_type}". '
                    f'Expected one of: response, tool_request, workflow_request, system_refresh_request, system_instruction_remind'
                )
        
        except Exception as e:
            raise ValueError(
                f"Failed to parse {response_type} response: {e}\n"
                f"Data: {json.dumps(data, indent=2)}"
            ) from e
    
    @staticmethod
    def is_tool_request(response: ProtocolResponse) -> bool:
        """Check if response is a tool request."""
        return isinstance(response, ToolRequest)
    
    @staticmethod
    def is_workflow_request(response: ProtocolResponse) -> bool:
        """Check if response is a workflow request."""
        return isinstance(response, WorkflowRequest)
    
    @staticmethod
    def is_system_refresh_request(response: ProtocolResponse) -> bool:
        """Check if response is a system refresh request."""
        return isinstance(response, SystemRefreshRequest)
    
    @staticmethod
    def is_final_response(response: ProtocolResponse) -> bool:
        """Check if response is a final answer (not tool/workflow/refresh request)."""
        return isinstance(response, Response)


class ProtocolValidator:
    """
    Validates protocol responses for correctness and security.
    
    Additional validation beyond Pydantic:
    - Tool name format validation
    - Parameter safety checks
    - Request ID format validation
    """
    
    @staticmethod
    def validate_tool_name(tool_name: str) -> bool:
        """
        Validate tool name format.
        
        Tool names should be:
        - Alphanumeric with underscores
        - Not start with underscore
        - 1-50 characters
        """
        import re
        pattern = r'^[a-zA-Z][a-zA-Z0-9_]{0,49}$'
        return bool(re.match(pattern, tool_name))
    
    @staticmethod
    def validate_request_id(request_id: str) -> bool:
        """
        Validate request ID format.
        
        Request IDs should be:
        - Alphanumeric with underscores, hyphens
        - 1-100 characters
        """
        import re
        pattern = r'^[a-zA-Z0-9_-]{1,100}$'
        return bool(re.match(pattern, request_id))
    
    @staticmethod
    def validate_tool_request(tool_request: ToolRequest) -> tuple[bool, Optional[str]]:
        """
        Validate a tool request for safety.
        
        Returns:
            (is_valid, error_message)
        """
        for idx, tool_call in enumerate(tool_request.tools):
            # Validate tool name format
            if not ProtocolValidator.validate_tool_name(tool_call.tool_name):
                return False, f"Invalid tool_name format at index {idx}: {tool_call.tool_name}"
            
            # Validate request ID if present
            if tool_call.id and not ProtocolValidator.validate_request_id(tool_call.id):
                return False, f"Invalid request ID format at index {idx}: {tool_call.id}"
            
            # Check params is dict
            if not isinstance(tool_call.params, dict):
                return False, f"Params must be dict at index {idx}"
        
        return True, None


def parse_llm_response(raw_response: str) -> ProtocolResponse:
    """
    Convenience function to parse LLM response.
    
    Args:
        raw_response: Raw string from LLM
        
    Returns:
        Parsed protocol response
        
    Raises:
        ValueError: If response is invalid
    """
    return ProtocolParser.parse(raw_response)


# Compatibility aliases for Executor
Protocol = ProtocolParser
ProtocolParseResult = ProtocolResponse
LLMResponse = Response
