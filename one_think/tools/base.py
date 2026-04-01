"""
Base Tool interface for AI-ONE.

All tools must inherit from Tool and implement execute_json() method.
Tools return strict JSON format with status, result, error, and timing.
"""

import json
import time
from typing import Any, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    """
    Standardized tool response format.
    
    All tools MUST return this exact structure.
    
    Fields:
        status: "success" or "error"
        tool: Name of the tool that executed
        request_id: Optional request identifier for tracking
        result: Tool output data (only if success)
        error: Error information (only if error)
        execution_time_ms: Time taken to execute
        metadata: Optional additional information
    """
    status: str = Field(..., pattern="^(success|error)$")
    tool: str
    request_id: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    execution_time_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump(exclude_none=True)


class ToolError(BaseModel):
    """Structured error information."""
    type: str  # Error type/category
    message: str  # Human-readable error message
    details: Optional[dict[str, Any]] = None  # Additional error context


class Tool(ABC):
    """
    Abstract base class for all AI-ONE tools.
    
    Every tool must:
    1. Set `name` (unique identifier)
    2. Set `description` (one-line what it does)
    3. Implement `execute_json()` method
    4. Implement `get_help()` method
    
    Tools return ToolResponse with strict JSON structure.
    """
    
    name: str = "base_tool"
    description: str = "Base tool class"
    version: str = "1.0.0"
    
    def __init__(self):
        """Initialize tool."""
        if self.name == "base_tool":
            raise NotImplementedError(
                "Tool must set a unique 'name' class variable"
            )
    
    @abstractmethod
    def execute_json(
        self,
        params: dict[str, Any],
        request_id: Optional[str] = None
    ) -> ToolResponse:
        """
        Execute tool and return standardized JSON response.
        
        Args:
            params: Tool parameters (validated by tool)
            request_id: Optional request identifier
            
        Returns:
            ToolResponse with status, result/error, timing
            
        Raises:
            Should NOT raise - catch all exceptions and return error response
        """
        raise NotImplementedError("Tool must implement execute_json()")
    
    @abstractmethod
    def get_help(self) -> str:
        """
        Return detailed help text for tool.
        
        Should include:
        - Tool description
        - Parameters (name, type, required/optional, default)
        - Return value structure
        - Usage examples
        - Any limitations or notes
        
        Returns:
            Formatted help text
        """
        raise NotImplementedError("Tool must implement get_help()")
    
    def __call__(
        self,
        params: dict[str, Any],
        request_id: Optional[str] = None
    ) -> ToolResponse:
        """
        Callable interface - wraps execute_json with timing and error handling.
        
        Args:
            params: Tool parameters
            request_id: Optional request ID
            
        Returns:
            ToolResponse (always succeeds, errors in response.status)
        """
        # Handle help request
        if params.get("help") is True:
            return self._create_help_response(request_id)
        
        # Execute with timing
        start_time = time.perf_counter()
        
        try:
            response = self.execute_json(params=params, request_id=request_id)
            
            # Ensure timing is set
            if response.execution_time_ms == 0:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                response.execution_time_ms = elapsed_ms
            
            # Ensure tool name is set
            if response.tool != self.name:
                response.tool = self.name
            
            return response
        
        except Exception as e:
            # Catch any uncaught exceptions and return error response
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return self._create_error_response(
                error_type="UnhandledException",
                message=f"Tool raised unhandled exception: {type(e).__name__}",
                details={"exception": str(e), "type": type(e).__name__},
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
    
    def _create_success_response(
        self,
        result: dict[str, Any],
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> ToolResponse:
        """
        Helper to create success response.
        
        Args:
            result: Tool result data
            request_id: Optional request ID
            execution_time_ms: Execution time (auto-calculated if None)
            metadata: Optional metadata
            
        Returns:
            ToolResponse with status="success"
        """
        return ToolResponse(
            status="success",
            tool=self.name,
            request_id=request_id,
            result=result,
            error=None,
            execution_time_ms=execution_time_ms or 0.0,
            metadata=metadata or {}
        )
    
    def _create_error_response(
        self,
        error_type: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> ToolResponse:
        """
        Helper to create error response.
        
        Args:
            error_type: Error category/type
            message: Human-readable error message
            details: Optional additional error context
            request_id: Optional request ID
            execution_time_ms: Execution time
            metadata: Optional metadata
            
        Returns:
            ToolResponse with status="error"
        """
        error = ToolError(
            type=error_type,
            message=message,
            details=details
        )
        
        return ToolResponse(
            status="error",
            tool=self.name,
            request_id=request_id,
            result=None,
            error=error.model_dump(),
            execution_time_ms=execution_time_ms or 0.0,
            metadata=metadata or {}
        )
    
    def _create_help_response(
        self,
        request_id: Optional[str] = None
    ) -> ToolResponse:
        """
        Create response for help request.
        
        Args:
            request_id: Optional request ID
            
        Returns:
            ToolResponse with help text in result
        """
        help_text = self.get_help()
        return ToolResponse(
            status="success",
            tool=self.name,
            request_id=request_id,
            result={"help": help_text},
            error=None,
            execution_time_ms=0.0,
            metadata={"is_help": True}
        )
    
    def validate_required_params(
        self,
        params: dict[str, Any],
        required: list[str]
    ) -> Optional[ToolResponse]:
        """
        Validate that required parameters are present.
        
        Args:
            params: Parameters to validate
            required: List of required parameter names
            
        Returns:
            None if valid, ToolResponse with error if invalid
        """
        missing = [p for p in required if p not in params]
        
        if missing:
            return self._create_error_response(
                error_type="MissingParameters",
                message=f"Missing required parameters: {', '.join(missing)}",
                details={"missing": missing, "required": required}
            )
        
        return None
    
    def __str__(self) -> str:
        """String representation of tool."""
        return f"Tool: {self.name} - {self.description} | Use 'help': true for details"
    
    def __repr__(self) -> str:
        """Developer representation."""
        return f"<Tool {self.name} v{self.version}>"


# Backward compatibility alias (deprecated)
class ToolLegacy(Tool):
    """
    Legacy tool interface for backward compatibility.
    
    Wraps old execute() -> (stdout, stderr) format to new JSON format.
    Tools should migrate to new Tool class.
    """
    
    def execute(self, arguments: dict[str, str] = None) -> tuple[str, str]:
        """Legacy execute method (deprecated)."""
        return "", "This tool uses legacy interface"
    
    def execute_json(
        self,
        params: dict[str, Any],
        request_id: Optional[str] = None
    ) -> ToolResponse:
        """Wrap legacy execute to JSON format."""
        start_time = time.perf_counter()
        
        try:
            stdout, stderr = self.execute(arguments=params)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            if stderr:
                return self._create_error_response(
                    error_type="ToolError",
                    message=stderr,
                    request_id=request_id,
                    execution_time_ms=elapsed_ms
                )
            
            return self._create_success_response(
                result={"output": stdout},
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
        
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return self._create_error_response(
                error_type=type(e).__name__,
                message=str(e),
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
    
    def get_help(self) -> str:
        """Get help from legacy tool."""
        if hasattr(self, 'get_full_information'):
            return self.get_full_information()
        return f"Tool: {self.name}\n{self.description}"
