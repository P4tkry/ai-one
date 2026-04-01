"""
Tests for Executor system.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
from datetime import datetime

from one_think.core.executor import (
    Executor, 
    ExecutionResult, 
    ExecutionStatus,
    ExecutorError,
    ToolDispatchError,
    LLMProviderError,
    ToolRequest
)
from one_think.core.session import Session
from one_think.core.message import UserMessage, SystemMessage, AssistantMessage
from one_think.core.protocol import ProtocolParser, ProtocolResponse, ToolCall
from one_think.tools.registry import ToolRegistry
from one_think.tools.base import Tool, ToolResponse


class MockTool(Tool):
    """Mock tool for testing."""
    name = "mock_tool"
    
    def execute_json(self, test_param: str = "default", request_id: str = None) -> ToolResponse:
        return self._create_success_response({"result": test_param}, request_id)
    
    def get_help(self) -> str:
        return "Mock tool for testing"


class FailingTool(Tool):
    """Tool that always fails."""
    name = "failing_tool"
    
    def execute_json(self, request_id: str = None) -> ToolResponse:
        raise ValueError("Tool execution failed")
    
    def get_help(self) -> str:
        return "Failing tool for testing"


class TestExecutor(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        # Create mock tool registry
        self.mock_registry = Mock(spec=ToolRegistry)
        self.mock_registry._discovery_performed = True
        self.mock_registry.discover_tools.return_value = 2
        self.mock_registry.list_tools.return_value = ["mock_tool", "failing_tool"]
        
        # Create mock protocol
        self.mock_protocol = Mock(spec=ProtocolParser)
        
        # Create mock LLM provider
        self.mock_llm_provider = Mock(return_value="Mock LLM response")
        
        # Create executor
        self.executor = Executor(
            tool_registry=self.mock_registry,
            protocol=self.mock_protocol,
            llm_provider=self.mock_llm_provider,
            max_tool_iterations=3
        )
        
        # Create test session
        self.session = Session()
    
    def test_initialization(self):
        """Test executor initialization."""
        executor = Executor()
        
        self.assertIsNotNone(executor.tool_registry)
        self.assertIsNotNone(executor.protocol)
        self.assertEqual(executor.max_tool_iterations, 5)
        self.assertIsNone(executor.llm_provider)
    
    def test_initialization_with_tool_discovery(self):
        """Test initialization triggers tool discovery."""
        mock_registry = Mock(spec=ToolRegistry)
        mock_registry._discovery_performed = False
        mock_registry.discover_tools.return_value = 10
        
        executor = Executor(tool_registry=mock_registry)
        
        mock_registry.discover_tools.assert_called_once()
    
    def test_set_llm_provider(self):
        """Test setting LLM provider."""
        provider_func = Mock()
        self.executor.set_llm_provider(provider_func)
        
        self.assertEqual(self.executor.llm_provider, provider_func)
    
    def test_format_messages_for_provider(self):
        """Test message formatting for LLM provider."""
        # Add various message types to session
        self.session.add_message(SystemMessage(content="System prompt"))
        self.session.add_message(UserMessage(content="User message"))
        self.session.add_message(AssistantMessage(content="Assistant response"))
        
        # Format messages
        formatted = self.executor._format_messages_for_provider(self.session)
        
        self.assertEqual(len(formatted), 3)
        
        # Check system message
        self.assertEqual(formatted[0]["role"], "system")
        self.assertEqual(formatted[0]["content"], "System prompt")
        
        # Check user message
        self.assertEqual(formatted[1]["role"], "user")
        self.assertEqual(formatted[1]["content"], "User message")
        
        # Check assistant message
        self.assertEqual(formatted[2]["role"], "assistant")
        self.assertEqual(formatted[2]["content"], "Assistant response")
    
    def test_execute_request_simple_text(self):
        """Test executing request with simple text response."""
        # Mock protocol to return text response
        parse_result = Mock()
        parse_result.response_type = "response"
        parse_result.response = Mock()
        parse_result.response.content = "This is a text response"
        self.mock_protocol.parse.return_value = parse_result
        
        # Execute request
        result = self.executor.execute_request(
            "Hello, world!",
            self.session,
            system_prompt="Test system prompt"
        )
        
        # Verify result
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.response, "This is a text response")
        self.assertEqual(len(result.tool_results or []), 0)
        self.assertEqual(len(result.errors or []), 0)
        self.assertIsNotNone(result.execution_time_ms)
        
        # Verify session state
        self.assertEqual(len(self.session.history), 3)  # system + user + assistant
        self.assertIsInstance(self.session.history[0], SystemMessage)
        self.assertIsInstance(self.session.history[1], UserMessage)
        self.assertIsInstance(self.session.history[2], AssistantMessage)
        
        # Verify LLM provider called
        self.mock_llm_provider.assert_called_once()
    
    def test_execute_request_with_tools(self):
        """Test executing request with tool calls."""
        # Mock protocol to return tool request first, then text
        tool_call = ToolCall(
            tool_name="mock_tool",
            params={"test_param": "hello"},
            id="req_1"
        )
        
        parse_result_1 = Mock()
        parse_result_1.response_type = "tool_request"
        parse_result_1.tool_request = Mock()
        parse_result_1.tool_request.tools = [tool_call]
        
        parse_result_2 = Mock()
        parse_result_2.response_type = "response"
        parse_result_2.response = Mock()
        parse_result_2.response.content = "Tool execution complete"
        
        self.mock_protocol.parse.side_effect = [parse_result_1, parse_result_2]
        
        # Mock tool execution
        mock_tool_instance = MockTool()
        self.mock_registry.create_tool_instance.return_value = mock_tool_instance
        
        # Mock LLM responses (first for tool request, second for final response)
        self.mock_llm_provider.side_effect = [
            '{"type": "tool_request", "tools": [...]}',
            "Tool execution complete"
        ]
        
        # Execute request
        result = self.executor.execute_request("Execute a tool", self.session)
        
        # Verify result
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.response, "Tool execution complete")
        self.assertEqual(len(result.tool_results), 1)
        self.assertEqual(result.tool_results[0].result["result"], "hello")
        
        # Verify tool registry called
        self.mock_registry.create_tool_instance.assert_called_once_with("mock_tool")
        
        # Verify LLM called twice (initial + after tool)
        self.assertEqual(self.mock_llm_provider.call_count, 2)
    
    def test_execute_request_tool_error(self):
        """Test request execution with tool errors."""
        # Mock protocol to return tool request
        tool_call = ToolCall(
            tool_name="failing_tool",
            params={},
            id="req_1"
        )
        
        parse_result = Mock()
        parse_result.response_type = "tool_request"
        parse_result.tool_request = Mock()
        parse_result.tool_request.tools = [tool_call]
        
        self.mock_protocol.parse.return_value = parse_result
        
        # Mock failing tool
        failing_tool = FailingTool()
        self.mock_registry.create_tool_instance.return_value = failing_tool
        
        # Execute request
        result = self.executor.execute_request("Execute failing tool", self.session)
        
        # Verify result shows tool error
        self.assertEqual(result.status, ExecutionStatus.TOOL_ERROR)
        self.assertGreater(len(result.errors or []), 0)
        self.assertEqual(len(result.tool_results), 1)
        self.assertEqual(result.tool_results[0].status, "error")
    
    def test_execute_request_llm_provider_error(self):
        """Test request execution with LLM provider error."""
        # Mock LLM provider to fail
        self.mock_llm_provider.side_effect = Exception("LLM connection failed")
        
        # Execute request
        result = self.executor.execute_request("Test request", self.session)
        
        # Verify error result
        self.assertEqual(result.status, ExecutionStatus.ERROR)
        self.assertIn("LLM provider error", result.response)
        self.assertGreater(len(result.errors or []), 0)
    
    def test_execute_request_protocol_parse_error(self):
        """Test request execution with protocol parse error."""
        # Mock protocol to fail parsing
        self.mock_protocol.parse.side_effect = Exception("Parse failed")
        
        # Execute request
        result = self.executor.execute_request("Test request", self.session)
        
        # Should return raw LLM response when parse fails
        self.assertEqual(result.status, ExecutionStatus.ERROR)
        self.assertEqual(result.response, "Mock LLM response")
        self.assertGreater(len(result.errors or []), 0)
    
    def test_execute_request_max_iterations(self):
        """Test request execution hitting max tool iterations."""
        # Mock protocol to always return tool requests
        tool_call = ToolCall(
            tool_name="mock_tool",
            params={"test_param": "loop"},
            id="req_loop"
        )
        
        parse_result = Mock()
        parse_result.response_type = "tool_request"
        parse_result.tool_request = Mock()
        parse_result.tool_request.tools = [tool_call]
        
        self.mock_protocol.parse.return_value = parse_result
        
        # Mock tool execution
        mock_tool_instance = MockTool()
        self.mock_registry.create_tool_instance.return_value = mock_tool_instance
        
        # Execute request
        result = self.executor.execute_request("Infinite tool loop", self.session)
        
        # Should hit max iterations
        self.assertEqual(result.status, ExecutionStatus.ERROR)
        self.assertIn("Maximum tool iterations", result.response)
        self.assertGreater(len(result.errors or []), 0)
        
        # Should have called LLM max_tool_iterations times
        self.assertEqual(self.mock_llm_provider.call_count, 3)  # max_tool_iterations
    
    def test_call_llm_provider_no_provider(self):
        """Test calling LLM provider when none is set."""
        self.executor.llm_provider = None
        
        with self.assertRaises(LLMProviderError):
            self.executor._call_llm_provider(self.session)
    
    def test_call_llm_provider_invalid_response(self):
        """Test calling LLM provider with invalid response."""
        self.executor.llm_provider = Mock(return_value=None)
        
        with self.assertRaises(LLMProviderError):
            self.executor._call_llm_provider(self.session)
    
    def test_execute_single_tool_success(self):
        """Test successful single tool execution."""
        tool_request = ToolRequest(
            tool_name="mock_tool",
            params={"test_param": "success"},
            id="req_1"
        )
        
        mock_tool_instance = MockTool()
        self.mock_registry.create_tool_instance.return_value = mock_tool_instance
        
        result = self.executor._execute_single_tool(tool_request, "test_req")
        
        self.assertEqual(result.status, "success")
        self.assertEqual(result.result["result"], "success")
        self.assertIsNone(result.error)
        self.assertEqual(result.request_id, "test_req")
    
    def test_execute_single_tool_failure(self):
        """Test failed single tool execution."""
        tool_request = ToolRequest(
            tool_name="failing_tool",
            params={},
            id="req_1"
        )
        
        failing_tool = FailingTool()
        self.mock_registry.create_tool_instance.return_value = failing_tool
        
        result = self.executor._execute_single_tool(tool_request, "test_req")
        
        self.assertEqual(result.status, "error")
        self.assertIsNone(result.result)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error["type"], "ValueError")
        self.assertEqual(result.request_id, "test_req")
    
    def test_dispatch_tools_multiple(self):
        """Test dispatching multiple tools."""
        tool_requests = [
            ToolRequest(tool_name="mock_tool", params={"test_param": "first"}, id="req_1"),
            ToolRequest(tool_name="mock_tool", params={"test_param": "second"}, id="req_2")
        ]
        
        mock_tool_instance = MockTool()
        self.mock_registry.create_tool_instance.return_value = mock_tool_instance
        
        tool_results, errors = self.executor._dispatch_tools(tool_requests, self.session, "exec_1")
        
        # Should execute both tools successfully
        self.assertEqual(len(tool_results), 2)
        self.assertEqual(len(errors), 0)
        
        # Check results
        self.assertEqual(tool_results[0].result["result"], "first")
        self.assertEqual(tool_results[1].result["result"], "second")
        
        # Should have added tool result messages to session
        tool_messages = [msg for msg in self.session.history if hasattr(msg, 'tool_name')]
        self.assertEqual(len(tool_messages), 2)
    
    def test_dispatch_tools_with_failure(self):
        """Test dispatching tools with one failure."""
        tool_requests = [
            ToolRequest(tool_name="mock_tool", params={"test_param": "success"}, id="req_1"),
            ToolRequest(tool_name="nonexistent_tool", params={}, id="req_2")
        ]
        
        def create_tool_side_effect(tool_name):
            if tool_name == "mock_tool":
                return MockTool()
            else:
                raise ValueError(f"Tool {tool_name} not found")
        
        self.mock_registry.create_tool_instance.side_effect = create_tool_side_effect
        
        tool_results, errors = self.executor._dispatch_tools(tool_requests, self.session, "exec_1")
        
        # Should have one successful result and one error
        self.assertEqual(len(tool_results), 1)
        self.assertEqual(len(errors), 1)
        
        # Successful result
        self.assertEqual(tool_results[0].result["result"], "success")
        
        # Error recorded
        self.assertIn("nonexistent_tool", errors[0])
    
    def test_handle_system_refresh(self):
        """Test handling system refresh request."""
        from one_think.core.protocol import SystemRefreshRequest
        
        refresh_request = SystemRefreshRequest(reason="Need to recall guidelines")
        
        self.executor._handle_system_refresh(refresh_request, self.session)
        
        # Should add refresh message to session
        self.assertEqual(len(self.session.history), 1)
        from one_think.core.message import SystemRefreshMessage
        self.assertIsInstance(self.session.history[0], SystemRefreshMessage)
        self.assertIn("Need to recall guidelines", self.session.history[0].content)
    
    def test_get_metrics(self):
        """Test getting executor metrics."""
        metrics = self.executor.get_metrics()
        
        self.assertIn("tool_count", metrics)
        self.assertIn("max_tool_iterations", metrics)
        self.assertIn("has_llm_provider", metrics)
        self.assertIn("protocol_version", metrics)
        
        self.assertEqual(metrics["max_tool_iterations"], 3)
        self.assertTrue(metrics["has_llm_provider"])


class TestExecutionResult(unittest.TestCase):
    
    def test_execution_result_creation(self):
        """Test creating execution result."""
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            response="Test response",
            tool_results=[],
            errors=None,
            execution_time_ms=123.45,
            session_id="session_123",
            request_id="req_456"
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.response, "Test response")
        self.assertEqual(result.execution_time_ms, 123.45)
    
    def test_execution_result_to_dict(self):
        """Test converting execution result to dictionary."""
        mock_tool_result = Mock(spec=ToolResponse)
        mock_tool_result.to_dict.return_value = {"tool": "mock", "status": "success"}
        
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            response="Test response",
            tool_results=[mock_tool_result],
            errors=["error1"],
            execution_time_ms=100.0,
            session_id="session_123",
            request_id="req_456"
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict["status"], "success")
        self.assertEqual(result_dict["response"], "Test response")
        self.assertEqual(len(result_dict["tool_results"]), 1)
        self.assertEqual(result_dict["errors"], ["error1"])
        self.assertEqual(result_dict["execution_time_ms"], 100.0)


if __name__ == '__main__':
    unittest.main()