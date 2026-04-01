"""
Tests for Tool Registry system.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path
from datetime import datetime

from one_think.tools.registry import (
    ToolRegistry, 
    ToolMetadata,
    ToolDiscoveryError,
    ToolInstantiationError,
    get_registry,
    discover_tools,
    get_tool,
    create_tool,
    list_available_tools
)
from one_think.tools.base import Tool, ToolResponse


class MockTool(Tool):
    """Mock tool for testing."""
    name = "mock_tool"
    __version__ = "1.0.0"
    __author__ = "Test Author"
    __tags__ = ["test", "mock"]
    
    def execute_json(self, test_param: str, optional_param: str = "default", request_id: str = None) -> ToolResponse:
        return self._create_success_response({"test": test_param}, request_id)
    
    def get_help(self) -> str:
        return "Mock tool for testing"


class AnotherMockTool(Tool):
    """Another mock tool for testing."""
    name = "another_mock_tool"
    
    def execute_json(self, request_id: str = None) -> ToolResponse:
        return self._create_success_response({"result": "another"}, request_id)
    
    def get_help(self) -> str:
        return "Another mock tool"


class TestToolRegistry(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.registry = ToolRegistry()
    
    def test_initialization(self):
        """Test registry initialization."""
        self.assertFalse(self.registry._discovery_performed)
        self.assertEqual(len(self.registry._tools), 0)
        self.assertEqual(len(self.registry._metadata), 0)
        self.assertEqual(len(self.registry._instances), 0)
    
    def test_extract_tool_name(self):
        """Test tool name extraction."""
        # Test with Tool suffix
        self.assertEqual(self.registry._extract_tool_name("WebFetchTool", "web_fetch"), "web_fetch")
        
        # Test without Tool suffix
        self.assertEqual(self.registry._extract_tool_name("WebFetch", "web_fetch"), "web_fetch")
        
        # Test camelCase conversion
        self.assertEqual(self.registry._extract_tool_name("AiWebSearchTool", "ai_web_search"), "ai_web_search")
        
        # Test fallback to module name
        self.assertEqual(self.registry._extract_tool_name("X", "user_tool"), "user")
    
    def test_extract_metadata(self):
        """Test metadata extraction."""
        metadata = self.registry._extract_metadata(MockTool, "mock", "test.module")
        
        self.assertEqual(metadata.name, "mock")
        self.assertEqual(metadata.class_name, "MockTool")
        self.assertEqual(metadata.module_path, "test.module")
        self.assertEqual(metadata.version, "1.0.0")
        self.assertEqual(metadata.author, "Test Author")
        self.assertEqual(metadata.tags, ["test", "mock"])
        self.assertIn("test_param", metadata.requires_params)
        self.assertIn("optional_param", metadata.optional_params)
        self.assertIsInstance(metadata.registered_at, datetime)
    
    @patch('one_think.tools.registry.importlib.import_module')
    @patch('one_think.tools.registry.pkgutil.iter_modules')
    def test_discover_tools_success(self, mock_iter_modules, mock_import):
        """Test successful tool discovery."""
        # Mock the tools module
        mock_tools_module = Mock()
        mock_tools_module.__file__ = "/fake/path/one_think/tools/__init__.py"
        
        # Mock module iteration
        mock_iter_modules.return_value = [
            (None, "mock_tool", False),
            (None, "another_tool", False),
            (None, "_private", False),  # Should be ignored
            (None, "base", False),      # Should be ignored
        ]
        
        # Mock individual tool modules
        mock_tool_module = Mock()
        mock_tool_module.__name__ = "one_think.tools.mock_tool"
        
        mock_another_module = Mock()
        mock_another_module.__name__ = "one_think.tools.another_tool"
        
        def import_side_effect(module_name):
            if module_name == "one_think.tools":
                return mock_tools_module
            elif module_name == "one_think.tools.mock_tool":
                # Add MockTool to module
                setattr(mock_tool_module, 'MockTool', MockTool)
                MockTool.__module__ = "one_think.tools.mock_tool"
                return mock_tool_module
            elif module_name == "one_think.tools.another_tool":
                # Add AnotherMockTool to module
                setattr(mock_another_module, 'AnotherMockTool', AnotherMockTool)  
                AnotherMockTool.__module__ = "one_think.tools.another_tool"
                return mock_another_module
            else:
                raise ImportError(f"No module named {module_name}")
        
        mock_import.side_effect = import_side_effect
        
        # Test discovery
        count = self.registry.discover_tools()
        
        # Should discover MockTool and AnotherMockTool (not _private or base)
        self.assertEqual(count, 2)
        self.assertTrue(self.registry._discovery_performed)
        self.assertIn("mock", self.registry._tools)
        self.assertIn("another_mock", self.registry._tools)
        self.assertEqual(len(self.registry._metadata), 2)
    
    def test_discover_tools_import_error(self):
        """Test discovery with import errors."""
        with patch('one_think.tools.registry.importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("Module not found")
            
            with self.assertRaises(ToolDiscoveryError):
                self.registry.discover_tools()
    
    def test_get_tool_without_discovery(self):
        """Test getting tool triggers discovery."""
        with patch.object(self.registry, 'discover_tools', return_value=1) as mock_discover:
            self.registry._tools['test'] = MockTool
            
            tool_class = self.registry.get_tool('test')
            
            mock_discover.assert_called_once()
            self.assertEqual(tool_class, MockTool)
    
    def test_get_tool_not_found(self):
        """Test getting non-existent tool."""
        self.registry._discovery_performed = True
        self.registry._tools = {'existing': MockTool}
        
        with self.assertRaises(KeyError) as context:
            self.registry.get_tool('nonexistent')
        
        self.assertIn("Tool 'nonexistent' not found", str(context.exception))
        self.assertIn("existing", str(context.exception))
    
    def test_create_tool_instance(self):
        """Test tool instance creation."""
        self.registry._discovery_performed = True
        self.registry._tools['mock'] = MockTool
        
        instance = self.registry.create_tool_instance('mock')
        
        self.assertIsInstance(instance, MockTool)
        self.assertEqual(len(self.registry._instances), 1)
    
    def test_create_tool_instance_with_kwargs(self):
        """Test tool instance creation with init kwargs."""
        class ParameterizedTool(Tool):
            name = "parameterized_tool"
            
            def __init__(self, config_value="default"):
                super().__init__()
                self.config_value = config_value
                
            def execute_json(self, request_id: str = None) -> ToolResponse:
                return self._create_success_response({"config": self.config_value}, request_id)
            
            def get_help(self) -> str:
                return "Parameterized tool"
        
        self.registry._discovery_performed = True
        self.registry._tools['param'] = ParameterizedTool
        
        instance = self.registry.create_tool_instance('param', config_value="custom")
        
        self.assertEqual(instance.config_value, "custom")
    
    def test_create_tool_instance_error(self):
        """Test tool instance creation error."""
        class FailingTool(Tool):
            def __init__(self):
                raise ValueError("Initialization failed")
        
        self.registry._discovery_performed = True
        self.registry._tools['failing'] = FailingTool
        
        with self.assertRaises(ToolInstantiationError):
            self.registry.create_tool_instance('failing')
    
    def test_get_tool_metadata(self):
        """Test getting tool metadata."""
        metadata = ToolMetadata(
            name="test",
            class_name="TestTool", 
            module_path="test.module",
            description="Test description",
            help_text="Test help",
            version="1.0.0",
            author="Test Author",
            tags=["test"],
            requires_params=set(),
            optional_params=set(),
            registered_at=datetime.now()
        )
        
        self.registry._discovery_performed = True
        self.registry._metadata['test'] = metadata
        
        result = self.registry.get_tool_metadata('test')
        
        self.assertEqual(result, metadata)
    
    def test_list_tools(self):
        """Test listing available tools."""
        self.registry._discovery_performed = True
        self.registry._tools = {'tool1': MockTool, 'tool2': AnotherMockTool}
        
        tools = self.registry.list_tools()
        
        self.assertEqual(set(tools), {'tool1', 'tool2'})
    
    def test_list_tools_with_metadata(self):
        """Test listing tools with metadata."""
        metadata1 = Mock()
        metadata2 = Mock()
        
        self.registry._discovery_performed = True
        self.registry._metadata = {'tool1': metadata1, 'tool2': metadata2}
        
        result = self.registry.list_tools_with_metadata()
        
        self.assertEqual(result, {'tool1': metadata1, 'tool2': metadata2})
    
    def test_validate_tool_implementation_valid(self):
        """Test validation of valid tool."""
        self.registry._discovery_performed = True
        self.registry._tools['mock'] = MockTool
        
        errors = self.registry.validate_tool_implementation('mock')
        
        self.assertEqual(errors, [])
    
    def test_validate_tool_implementation_invalid(self):
        """Test validation of invalid tool."""
        class InvalidTool(Tool):
            name = "invalid_tool"
            pass  # Missing execute_json and get_help
        
        self.registry._discovery_performed = True
        self.registry._tools['invalid'] = InvalidTool
        
        errors = self.registry.validate_tool_implementation('invalid')
        
        self.assertGreater(len(errors), 0)
        # Check for abstract method error instead of "Missing execute_json"  
        self.assertTrue(any("abstract" in error.lower() for error in errors))
    
    def test_validate_all_tools(self):
        """Test validation of all tools."""
        class ValidTool(Tool):
            name = "valid_tool"
            
            def execute_json(self, request_id: str = None) -> ToolResponse:
                return self._create_success_response({}, request_id)
            def get_help(self) -> str:
                return "Valid tool"
        
        class InvalidTool(Tool):
            name = "invalid_tool"
            pass
        
        self.registry._discovery_performed = True
        self.registry._tools = {'valid': ValidTool, 'invalid': InvalidTool}
        
        results = self.registry.validate_all_tools()
        
        self.assertEqual(results['valid'], [])
        self.assertGreater(len(results['invalid']), 0)
    
    def test_get_tools_by_tag(self):
        """Test getting tools by tag."""
        metadata1 = ToolMetadata("tool1", "Tool1", "test", "", "", "1.0", "", ["web", "search"], set(), set(), datetime.now())
        metadata2 = ToolMetadata("tool2", "Tool2", "test", "", "", "1.0", "", ["web"], set(), set(), datetime.now())
        metadata3 = ToolMetadata("tool3", "Tool3", "test", "", "", "1.0", "", ["file"], set(), set(), datetime.now())
        
        self.registry._discovery_performed = True
        self.registry._metadata = {'tool1': metadata1, 'tool2': metadata2, 'tool3': metadata3}
        
        web_tools = self.registry.get_tools_by_tag('web')
        search_tools = self.registry.get_tools_by_tag('search')
        
        self.assertEqual(set(web_tools), {'tool1', 'tool2'})
        self.assertEqual(search_tools, ['tool1'])
    
    def test_clear_cache(self):
        """Test cache clearing."""
        self.registry._instances['test'] = Mock()
        
        self.registry.clear_cache()
        
        self.assertEqual(len(self.registry._instances), 0)
    
    def test_reload_tools(self):
        """Test reloading tools."""
        with patch.object(self.registry, 'discover_tools', return_value=5) as mock_discover:
            self.registry._discovery_performed = True
            self.registry._instances['test'] = Mock()
            
            count = self.registry.reload_tools()
            
            self.assertEqual(count, 5)
            mock_discover.assert_called_once()
            self.assertEqual(len(self.registry._instances), 0)


class TestGlobalFunctions(unittest.TestCase):
    
    @patch('one_think.tools.registry.tool_registry')
    def test_get_registry(self, mock_registry):
        """Test get_registry function."""
        result = get_registry()
        self.assertEqual(result, mock_registry)
    
    @patch('one_think.tools.registry.tool_registry')
    def test_discover_tools_function(self, mock_registry):
        """Test discover_tools function."""
        mock_registry.discover_tools.return_value = 10
        
        result = discover_tools()
        
        self.assertEqual(result, 10)
        mock_registry.discover_tools.assert_called_once()
    
    @patch('one_think.tools.registry.tool_registry')
    def test_get_tool_function(self, mock_registry):
        """Test get_tool function."""
        mock_registry.get_tool.return_value = MockTool
        
        result = get_tool('mock')
        
        self.assertEqual(result, MockTool)
        mock_registry.get_tool.assert_called_once_with('mock')
    
    @patch('one_think.tools.registry.tool_registry')
    def test_create_tool_function(self, mock_registry):
        """Test create_tool function."""
        mock_instance = Mock()
        mock_registry.create_tool_instance.return_value = mock_instance
        
        result = create_tool('mock', config='test')
        
        self.assertEqual(result, mock_instance)
        mock_registry.create_tool_instance.assert_called_once_with('mock', config='test')
    
    @patch('one_think.tools.registry.tool_registry')
    def test_list_available_tools_function(self, mock_registry):
        """Test list_available_tools function."""
        mock_registry.list_tools.return_value = ['tool1', 'tool2']
        
        result = list_available_tools()
        
        self.assertEqual(result, ['tool1', 'tool2'])
        mock_registry.list_tools.assert_called_once()


if __name__ == '__main__':
    unittest.main()