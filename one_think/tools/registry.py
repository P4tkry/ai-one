"""
Tool Registry - Dynamic tool discovery and loading system.

This registry automatically discovers all available tools, provides type-safe
instantiation, and manages tool metadata for the execution engine.
"""

import importlib
import inspect
import pkgutil
import logging
from pathlib import Path
from typing import Dict, List, Type, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime

from one_think.tools.base import Tool, ToolResponse


logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata about a registered tool."""
    name: str
    class_name: str
    module_path: str
    description: str
    help_text: str
    version: str
    author: str
    tags: List[str]
    requires_params: Set[str]
    optional_params: Set[str]
    registered_at: datetime


class ToolDiscoveryError(Exception):
    """Raised when tool discovery fails."""
    pass


class ToolInstantiationError(Exception):
    """Raised when tool instantiation fails."""
    pass


class ToolRegistry:
    """
    Central registry for tool discovery, instantiation and metadata management.
    
    Features:
    - Automatic tool discovery from tools package
    - Type-safe tool instantiation
    - Tool metadata extraction and caching
    - Plugin architecture support
    - Validation of tool implementations
    """
    
    def __init__(self):
        self._tools: Dict[str, Type[Tool]] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._instances: Dict[str, Tool] = {}
        self._discovery_performed = False
        
    def discover_tools(self, package_path: Optional[str] = None) -> int:
        """
        Discover all available tools in the tools package.
        
        Args:
            package_path: Optional path to tools package (defaults to one_think.tools)
            
        Returns:
            Number of tools discovered
            
        Raises:
            ToolDiscoveryError: If discovery fails
        """
        if package_path is None:
            package_path = "one_think.tools"
            
        try:
            # Clear existing registry
            self._tools.clear()
            self._metadata.clear()
            self._instances.clear()
            
            discovered_count = 0
            
            # Import the tools package
            tools_module = importlib.import_module(package_path)
            tools_package_path = Path(tools_module.__file__).parent
            
            # Iterate through all Python files in tools directory
            for module_finder, module_name, is_pkg in pkgutil.iter_modules([str(tools_package_path)]):
                if module_name.startswith('_') or module_name in ['base', 'registry', 'test_base']:
                    continue
                    
                full_module_name = f"{package_path}.{module_name}"
                
                try:
                    # Import the module
                    module = importlib.import_module(full_module_name)
                    
                    # Find Tool subclasses in the module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (obj != Tool and 
                            issubclass(obj, Tool) and 
                            obj.__module__ == full_module_name and
                            not getattr(obj, '__abstract__', False)):
                            
                            # Check if class has explicit name attribute
                            if hasattr(obj, 'name') and obj.name:
                                tool_name = obj.name
                            else:
                                tool_name = self._extract_tool_name(name, module_name)
                            
                            # Register the tool
                            self._tools[tool_name] = obj
                            
                            # Extract metadata
                            metadata = self._extract_metadata(obj, tool_name, full_module_name)
                            self._metadata[tool_name] = metadata
                            
                            discovered_count += 1
                            logger.info(f"Discovered tool: {tool_name} ({obj.__name__})")
                            
                except ImportError as e:
                    logger.warning(f"Failed to import {full_module_name}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error discovering tools in {full_module_name}: {e}")
                    continue
            
            self._discovery_performed = True
            logger.info(f"Tool discovery completed. Found {discovered_count} tools.")
            
            return discovered_count
            
        except Exception as e:
            raise ToolDiscoveryError(f"Tool discovery failed: {e}") from e
    
    def _extract_tool_name(self, class_name: str, module_name: str) -> str:
        """Extract tool name from class name or module name."""
        # Remove 'Tool' suffix if present
        if class_name.endswith('Tool'):
            name = class_name[:-4]
        else:
            name = class_name
            
        # Convert camelCase to snake_case
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append('_')
            result.append(char.lower())
            
        tool_name = ''.join(result)
        
        # Fallback to module name if extraction doesn't look right
        if len(tool_name) < 2:
            tool_name = module_name.replace('_tool', '').replace('tool_', '')
            
        return tool_name
    
    def _extract_metadata(self, tool_class: Type[Tool], tool_name: str, module_path: str) -> ToolMetadata:
        """Extract metadata from a tool class."""
        # Get basic info
        description = getattr(tool_class, '__doc__', '') or 'No description available'
        description = description.strip().split('\n')[0]  # First line only
        
        # Try to get help text
        try:
            # Create temporary instance to get help
            temp_instance = tool_class()
            help_text = temp_instance.get_help()
        except Exception:
            help_text = description
            
        # Extract parameter info from execute_json signature
        requires_params = set()
        optional_params = set()
        
        try:
            sig = inspect.signature(tool_class.execute_json)
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'request_id']:
                    continue
                if param.default == inspect.Parameter.empty:
                    requires_params.add(param_name)
                else:
                    optional_params.add(param_name)
        except Exception:
            # Fallback: try to parse from params dict if execute_json takes **kwargs
            pass
            
        return ToolMetadata(
            name=tool_name,
            class_name=tool_class.__name__,
            module_path=module_path,
            description=description,
            help_text=help_text,
            version=getattr(tool_class, '__version__', '1.0.0'),
            author=getattr(tool_class, '__author__', 'AI-ONE'),
            tags=getattr(tool_class, '__tags__', []),
            requires_params=requires_params,
            optional_params=optional_params,
            registered_at=datetime.now()
        )
    
    def get_tool(self, tool_name: str) -> Type[Tool]:
        """
        Get tool class by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool class
            
        Raises:
            KeyError: If tool is not found
        """
        if not self._discovery_performed:
            self.discover_tools()
            
        if tool_name not in self._tools:
            available = ", ".join(self._tools.keys())
            raise KeyError(f"Tool '{tool_name}' not found. Available: {available}")
            
        return self._tools[tool_name]
    
    def create_tool_instance(self, tool_name: str, **init_kwargs) -> Tool:
        """
        Create an instance of a tool.
        
        Args:
            tool_name: Name of the tool
            **init_kwargs: Additional arguments for tool constructor
            
        Returns:
            Tool instance
            
        Raises:
            ToolInstantiationError: If instantiation fails
        """
        try:
            tool_class = self.get_tool(tool_name)
            
            instance = tool_class(**init_kwargs)
            
            # Cache the instance for reuse
            cache_key = f"{tool_name}_{hash(frozenset(init_kwargs.items()))}"
            self._instances[cache_key] = instance
            
            return instance
            
        except Exception as e:
            raise ToolInstantiationError(f"Failed to create instance of '{tool_name}': {e}") from e
    
    def get_tool_metadata(self, tool_name: str) -> ToolMetadata:
        """
        Get metadata for a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool metadata
            
        Raises:
            KeyError: If tool is not found
        """
        if not self._discovery_performed:
            self.discover_tools()
            
        if tool_name not in self._metadata:
            available = ", ".join(self._metadata.keys())
            raise KeyError(f"Tool '{tool_name}' metadata not found. Available: {available}")
            
        return self._metadata[tool_name]
    
    def list_tools(self) -> List[str]:
        """
        Get list of all available tool names.
        
        Returns:
            List of tool names
        """
        if not self._discovery_performed:
            self.discover_tools()
            
        return list(self._tools.keys())
    
    def list_tools_with_metadata(self) -> Dict[str, ToolMetadata]:
        """
        Get all tools with their metadata.
        
        Returns:
            Dictionary mapping tool names to metadata
        """
        if not self._discovery_performed:
            self.discover_tools()
            
        return self._metadata.copy()
    
    def get_tools_formatted(self, format_style: str = "list") -> str:
        """
        Get tools in formatted string representation.
        
        Args:
            format_style: Format style ("list", "detailed", "compact")
                - "list": "tool1, tool2, tool3"
                - "detailed": "tool1 - description1\ntool2 - description2"  
                - "compact": "tool1 - short desc, tool2 - short desc"
        
        Returns:
            Formatted tools string
        """
        if not self._discovery_performed:
            self.discover_tools()
        
        if format_style == "list":
            return ', '.join(self.list_tools())
        
        elif format_style == "detailed":
            lines = []
            for tool_name, metadata in self._metadata.items():
                lines.append(f"{tool_name} - {metadata.description}")
            return '\n'.join(lines)
        
        elif format_style == "compact":
            items = []
            for tool_name, metadata in self._metadata.items():
                # Use first sentence of description for compact format
                short_desc = metadata.description.split('.')[0] if '.' in metadata.description else metadata.description
                items.append(f"{tool_name} - {short_desc}")
            return ', '.join(items)
        
        else:
            raise ValueError(f"Unknown format style: {format_style}")
    
    
    def validate_tool_implementation(self, tool_name: str) -> List[str]:
        """
        Validate that a tool is properly implemented.
        
        Args:
            tool_name: Name of the tool to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        try:
            tool_class = self.get_tool(tool_name)
            
            # Check if it has execute_json method
            if not hasattr(tool_class, 'execute_json'):
                errors.append("Missing execute_json method")
            else:
                # Check method signature
                try:
                    sig = inspect.signature(tool_class.execute_json)
                    if 'request_id' not in sig.parameters:
                        errors.append("execute_json missing request_id parameter")
                except Exception as e:
                    errors.append(f"Invalid execute_json signature: {e}")
            
            # Check if it has get_help method
            if not hasattr(tool_class, 'get_help'):
                errors.append("Missing get_help method")
            
            # Try to instantiate
            try:
                instance = tool_class()
            except Exception as e:
                errors.append(f"Failed to instantiate: {e}")
                
        except Exception as e:
            errors.append(f"Failed to load tool class: {e}")
            
        return errors
    
    def validate_all_tools(self) -> Dict[str, List[str]]:
        """
        Validate all registered tools.
        
        Returns:
            Dictionary mapping tool names to their validation errors
        """
        if not self._discovery_performed:
            self.discover_tools()
            
        results = {}
        for tool_name in self._tools.keys():
            results[tool_name] = self.validate_tool_implementation(tool_name)
            
        return results
    
    def get_tools_by_tag(self, tag: str) -> List[str]:
        """
        Get tools that have a specific tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of tool names with the tag
        """
        if not self._discovery_performed:
            self.discover_tools()
            
        matching_tools = []
        for tool_name, metadata in self._metadata.items():
            if tag in metadata.tags:
                matching_tools.append(tool_name)
                
        return matching_tools
    
    def clear_cache(self):
        """Clear all cached tool instances."""
        self._instances.clear()
        
    def reload_tools(self) -> int:
        """
        Reload all tools (useful for development).
        
        Returns:
            Number of tools reloaded
        """
        self._discovery_performed = False
        self.clear_cache()
        return self.discover_tools()


# Global registry instance
tool_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return tool_registry


def discover_tools() -> int:
    """Convenience function to discover tools using global registry."""
    return tool_registry.discover_tools()


def get_tool(tool_name: str) -> Type[Tool]:
    """Convenience function to get tool class from global registry."""
    return tool_registry.get_tool(tool_name)


def create_tool(tool_name: str, **kwargs) -> Tool:
    """Convenience function to create tool instance from global registry."""
    return tool_registry.create_tool_instance(tool_name, **kwargs)


def list_available_tools() -> List[str]:
    """Convenience function to list all available tools."""
    return tool_registry.list_tools()