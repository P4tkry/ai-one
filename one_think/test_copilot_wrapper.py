"""
Tests for modern Copilot wrapper.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import uuid

from one_think.copilot_wrapper import (
    CopilotWrapper,
    CopilotConfig,
    ask_question,
    configure_copilot,
    get_copilot_wrapper,
    get_copilot_stats
)
from one_think.core import Session, ExecutionResult, ExecutionStatus
from one_think.providers import CopilotProvider


class TestCopilotConfig(unittest.TestCase):
    
    def test_copilot_config_defaults(self):
        """Test default Copilot configuration."""
        config = CopilotConfig()
        
        self.assertEqual(config.model, "gpt-4.1")
        self.assertEqual(config.max_tool_iterations, 5)
        self.assertTrue(config.enable_tools)
        self.assertTrue(config.auto_discover_tools)
        self.assertIsNone(config.system_prompt)
        self.assertEqual(config.timeout, 30.0)
    
    def test_copilot_config_custom(self):
        """Test custom Copilot configuration."""
        config = CopilotConfig(
            model="gpt-4",
            max_tool_iterations=3,
            enable_tools=False,
            system_prompt="Custom prompt"
        )
        
        self.assertEqual(config.model, "gpt-4")
        self.assertEqual(config.max_tool_iterations, 3)
        self.assertFalse(config.enable_tools)
        self.assertEqual(config.system_prompt, "Custom prompt")
    
    def test_copilot_config_to_dict(self):
        """Test converting config to dict."""
        config = CopilotConfig(model="test-model")
        config_dict = config.to_dict()
        
        self.assertEqual(config_dict["model"], "test-model")
        self.assertIn("max_tool_iterations", config_dict)
        self.assertIn("enable_tools", config_dict)


class TestCopilotWrapper(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        # Create config with tools disabled to avoid discovery
        self.config = CopilotConfig(
            model="test-model",
            enable_tools=False,
            auto_discover_tools=False
        )
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_copilot_wrapper_initialization(self, mock_registry, mock_create_provider):
        """Test Copilot wrapper initialization."""
        # Mock provider creation
        mock_provider = Mock(spec=CopilotProvider)
        mock_create_provider.return_value = mock_provider
        
        wrapper = CopilotWrapper(self.config)
        
        # Verify initialization
        self.assertEqual(wrapper.config, self.config)
        self.assertEqual(wrapper.provider, mock_provider)
        self.assertIsNotNone(wrapper.executor)
        self.assertEqual(len(wrapper._sessions), 0)
        
        # Verify provider was created with correct config
        mock_create_provider.assert_called_once_with(
            model="test-model",
            timeout=30.0
        )
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_copilot_wrapper_with_tools(self, mock_registry, mock_create_provider):
        """Test wrapper initialization with tools enabled."""
        mock_provider = Mock(spec=CopilotProvider)
        mock_create_provider.return_value = mock_provider
        mock_registry.discover_tools.return_value = 12
        
        config = CopilotConfig(enable_tools=True, auto_discover_tools=True)
        wrapper = CopilotWrapper(config)
        
        # Should discover tools
        mock_registry.discover_tools.assert_called_once()
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_ask_question_basic(self, mock_registry, mock_create_provider):
        """Test basic ask_question functionality."""
        # Mock provider and executor
        mock_provider = Mock(spec=CopilotProvider)
        mock_create_provider.return_value = mock_provider
        
        wrapper = CopilotWrapper(self.config)
        
        # Mock executor result
        mock_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            response="Test response from Copilot",
            execution_time_ms=150.0
        )
        wrapper.executor.execute_request = Mock(return_value=mock_result)
        
        # Test ask_question
        session_id, response = wrapper.ask_question(
            "What is the capital of France?",
            model="test-model"
        )
        
        # Verify response
        self.assertIsInstance(session_id, str)
        self.assertEqual(response, "Test response from Copilot")
        
        # Verify executor was called
        wrapper.executor.execute_request.assert_called_once()
        call_args = wrapper.executor.execute_request.call_args[1]
        self.assertEqual(call_args["user_input"], "What is the capital of France?")
        self.assertIsNotNone(call_args["session"])
        self.assertIsNotNone(call_args["system_prompt"])
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_ask_question_session_continuity(self, mock_registry, mock_create_provider):
        """Test session continuity across multiple questions."""
        mock_provider = Mock(spec=CopilotProvider)
        mock_create_provider.return_value = mock_provider
        
        wrapper = CopilotWrapper(self.config)
        
        # Mock executor results
        mock_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            response="Response",
            execution_time_ms=100.0
        )
        wrapper.executor.execute_request = Mock(return_value=mock_result)
        
        # First question
        session_id1, response1 = wrapper.ask_question("Question 1")
        
        # Second question with same session
        session_id2, response2 = wrapper.ask_question("Question 2", session_id=session_id1)
        
        # Should use same session
        self.assertEqual(session_id1, session_id2)
        
        # Should have created only one session
        self.assertEqual(len(wrapper._sessions), 1)
        
        # Verify executor was called twice
        self.assertEqual(wrapper.executor.execute_request.call_count, 2)
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_ask_question_error_handling(self, mock_registry, mock_create_provider):
        """Test ask_question error handling."""
        mock_provider = Mock(spec=CopilotProvider)
        mock_create_provider.return_value = mock_provider
        
        wrapper = CopilotWrapper(self.config)
        
        # Mock executor to raise exception
        wrapper.executor.execute_request = Mock(side_effect=Exception("Test error"))
        
        session_id, response = wrapper.ask_question("Test question")
        
        # Should return error response
        self.assertIn("error", response.lower())
        self.assertIn("Test error", response)
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_session_management(self, mock_registry, mock_create_provider):
        """Test session management methods."""
        mock_provider = Mock(spec=CopilotProvider)
        mock_create_provider.return_value = mock_provider
        
        wrapper = CopilotWrapper(self.config)
        
        # Create session by asking question
        mock_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            response="Response",
            execution_time_ms=100.0
        )
        wrapper.executor.execute_request = Mock(return_value=mock_result)
        
        session_id, _ = wrapper.ask_question("Test")
        
        # Test get_session_info
        session_info = wrapper.get_session_info(session_id)
        self.assertIsNotNone(session_info)
        self.assertEqual(session_info["session_id"], session_id)
        self.assertIn("created_at", session_info)
        self.assertIn("message_count", session_info)
        
        # Test list_sessions
        sessions = wrapper.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], session_id)
        
        # Test clear_session
        cleared = wrapper.clear_session(session_id)
        self.assertTrue(cleared)
        self.assertEqual(len(wrapper._sessions), 0)
        
        # Test clearing non-existent session
        cleared_again = wrapper.clear_session(session_id)
        self.assertFalse(cleared_again)
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_get_usage_stats(self, mock_registry, mock_create_provider):
        """Test usage statistics."""
        mock_provider = Mock(spec=CopilotProvider)
        mock_provider.get_usage_stats.return_value = {
            "requests": 1,
            "tokens_sent": 10,
            "tokens_received": 20
        }
        mock_create_provider.return_value = mock_provider
        
        wrapper = CopilotWrapper(self.config)
        wrapper.executor.get_metrics = Mock(return_value={
            "tool_count": 12,
            "max_tool_iterations": 5
        })
        
        # Create a session for stats
        wrapper._sessions["test"] = Mock()
        wrapper._sessions["test"].history = ["msg1", "msg2"]
        
        stats = wrapper.get_usage_stats()
        
        # Verify stats structure
        self.assertIn("provider", stats)
        self.assertIn("executor", stats)
        self.assertIn("sessions", stats)
        self.assertIn("config", stats)
        
        # Verify session stats
        self.assertEqual(stats["sessions"]["active_count"], 1)
        self.assertEqual(stats["sessions"]["total_messages"], 2)
    
    @patch('one_think.copilot_wrapper.create_copilot_provider')
    @patch('one_think.copilot_wrapper.tool_registry')
    def test_default_system_prompt(self, mock_registry, mock_create_provider):
        """Test default system prompt."""
        mock_provider = Mock(spec=CopilotProvider)
        mock_create_provider.return_value = mock_provider
        
        wrapper = CopilotWrapper(self.config)
        default_prompt = wrapper._get_default_system_prompt()
        
        self.assertIn("GitHub Copilot", default_prompt)
        self.assertIn("helpful", default_prompt)
        self.assertIn("tools", default_prompt)


class TestBackwardCompatibility(unittest.TestCase):
    
    @patch('one_think.copilot_wrapper.get_copilot_wrapper')
    def test_ask_question_function(self, mock_get_wrapper):
        """Test backward compatible ask_question function."""
        # Mock wrapper
        mock_wrapper = Mock()
        mock_wrapper.ask_question.return_value = ("session-123", "Response")
        mock_get_wrapper.return_value = mock_wrapper
        
        # Call function
        session_id, response = ask_question(
            "Test question",
            model="gpt-4.1",
            session_id="existing-session"
        )
        
        # Verify result
        self.assertEqual(session_id, "session-123")
        self.assertEqual(response, "Response")
        
        # Verify wrapper was called correctly
        mock_wrapper.ask_question.assert_called_once_with(
            "Test question",
            "gpt-4.1",
            "existing-session",
            None
        )
    
    @patch('one_think.copilot_wrapper.CopilotWrapper')
    def test_configure_copilot(self, mock_wrapper_class):
        """Test configure_copilot function."""
        config = CopilotConfig(model="custom-model")
        
        configure_copilot(config)
        
        # Should create new wrapper with config
        mock_wrapper_class.assert_called_once_with(config)
    
    @patch('one_think.copilot_wrapper.get_copilot_wrapper')
    def test_get_copilot_stats(self, mock_get_wrapper):
        """Test get_copilot_stats function."""
        mock_wrapper = Mock()
        mock_wrapper.get_usage_stats.return_value = {"requests": 1}
        mock_get_wrapper.return_value = mock_wrapper
        
        stats = get_copilot_stats()
        
        self.assertEqual(stats, {"requests": 1})
        mock_wrapper.get_usage_stats.assert_called_once()


if __name__ == '__main__':
    unittest.main()