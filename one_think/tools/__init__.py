"""
Tools module for AI-ONE.

Provides base Tool interface, tool registry system, and all available tools.
All tools return strict JSON format via ToolResponse.

Usage:
    from one_think.tools import tool_registry, discover_tools, get_tool, create_tool
    
    # Discover all available tools
    tool_count = discover_tools()
    
    # Get a specific tool class
    tool_class = get_tool('web_fetch')
    
    # Create tool instance
    tool_instance = create_tool('web_fetch')
    
    # List all tools
    tools = tool_registry.list_tools()
"""

from one_think.tools.base import Tool, ToolResponse, ToolError, ToolLegacy
from one_think.tools.registry import (
    ToolRegistry,
    ToolMetadata,
    ToolDiscoveryError,
    ToolInstantiationError,
    tool_registry,
    get_registry,
    discover_tools,
    get_tool,
    create_tool,
    list_available_tools
)

__all__ = [
    # Base classes
    'Tool',
    'ToolResponse', 
    'ToolError',
    'ToolLegacy',
    
    # Registry system
    'ToolRegistry',
    'ToolMetadata',
    'ToolDiscoveryError',
    'ToolInstantiationError',
    'tool_registry',
    'get_registry',
    'discover_tools',
    'get_tool',
    'create_tool', 
    'list_available_tools',
]

