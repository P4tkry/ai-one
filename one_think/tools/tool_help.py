"""
Tool for getting help and documentation from other tools.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from .base import Tool, ToolResponse


class ToolHelpInput(BaseModel):
    """Input schema for tool help requests."""
    tool_name: str = Field(description="Name of the tool to get help for")


class ToolHelpOutput(BaseModel):
    """Output schema for tool help responses."""
    tool_name: str = Field(description="Name of the requested tool")
    help_text: str = Field(description="Complete help documentation")
    available: bool = Field(description="Whether the tool is available")


class ToolHelpTool(Tool):
    """Tool for getting help documentation from other tools."""
    
    name: str = "tool_help"
    description: str = "Get detailed help and documentation for any available tool"
    version: str = "2.0.0"
    
    Input = ToolHelpInput
    Output = ToolHelpOutput
    
    def __init__(self, tool_registry=None):
        """Initialize with tool registry for help lookup."""
        super().__init__()
        self.tool_registry = tool_registry
        
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Get help for a specified tool."""
        
        # Validate input
        try:
            input_data = self.Input(**params)
        except Exception as e:
            return self._create_error_response(
                f"Invalid input parameters: {e}",
                request_id=request_id
            )
        
        tool_name = input_data.tool_name
        
        # Check if we have tool registry
        if not self.tool_registry:
            return self._create_error_response(
                "Tool registry not available - cannot provide help",
                request_id=request_id
            )
        
        try:
            # Get available tools
            available_tools = self.tool_registry.list_tools()
            
            if tool_name not in available_tools:
                return self._create_success_response(
                    result={
                        "tool_name": tool_name,
                        "help_text": f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools)}",
                        "available": False
                    },
                    request_id=request_id
                )
            
            # Create tool instance and get help
            tool_instance = self.tool_registry.create_tool_instance(tool_name)
            help_text = tool_instance.get_help()
            
            return self._create_success_response(
                result={
                    "tool_name": tool_name,
                    "help_text": help_text,
                    "available": True
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                f"Failed to get help for '{tool_name}': {e}",
                request_id=request_id
            )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """Tool Help Tool

DESCRIPTION:
    Get detailed help and documentation for any available tool.
    This tool provides access to comprehensive documentation for all tools
    in the AI-ONE system, including parameters, examples, and usage notes.

PARAMETERS:
    tool_name (string, required)
        Name of the tool to get help for

RESPONSE FORMAT:
    Success:
        {
            "status": "success",
            "result": {
                "tool_name": "requested_tool",
                "help_text": "Complete help documentation...",
                "available": true
            }
        }
    
    Tool not found:
        {
            "status": "success", 
            "result": {
                "tool_name": "missing_tool",
                "help_text": "Tool 'missing_tool' not found. Available tools: ...",
                "available": false
            }
        }

USAGE EXAMPLES:
    Get help for python executor:
        {"tool_name": "python_executor"}
    
    Get help for memory tool:
        {"tool_name": "memory"}
        
    Check available tools:
        {"tool_name": "nonexistent"} (will list all available tools)

PURPOSE:
    This tool enables the AI to discover and understand the capabilities
    of other tools before using them, ensuring proper usage and better results.
"""