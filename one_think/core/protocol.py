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
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ResponseType(str, Enum):
    """Type of response from LLM."""
    RESPONSE = "response"
    TOOL_REQUEST = "tool_request"
    SYSTEM_REFRESH_REQUEST = "system_refresh_request"


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


# Union type for protocol responses
ProtocolResponse = Response | ToolRequest | SystemRefreshRequest


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
        # Parse JSON
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM response is not valid JSON: {e}\n"
                f"Raw response:\n{raw_response[:500]}"
            ) from e
        
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
            
            elif response_type == "system_refresh_request":
                return SystemRefreshRequest(**data)
            
            else:
                raise ValueError(
                    f'Unknown response type: "{response_type}". '
                    f'Expected one of: response, tool_request, system_refresh_request'
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
    def is_system_refresh_request(response: ProtocolResponse) -> bool:
        """Check if response is a system refresh request."""
        return isinstance(response, SystemRefreshRequest)
    
    @staticmethod
    def is_final_response(response: ProtocolResponse) -> bool:
        """Check if response is a final answer (not tool/refresh request)."""
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
