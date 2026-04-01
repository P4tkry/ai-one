"""
Tools module for AI-ONE.

Provides base Tool interface and all available tools.
All tools return strict JSON format via ToolResponse.
"""

from one_think.tools.base import Tool, ToolResponse, ToolError, ToolLegacy

# Import existing tools (they'll need migration)
# For now, we'll export both new and legacy interfaces

__all__ = [
    'Tool',
    'ToolResponse',
    'ToolError',
    'ToolLegacy',
]

