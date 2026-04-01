"""
Tests for Provider Interface system.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime

from one_think.providers import (
    LLMProvider,
    CopilotProvider,
    MockProvider,
    ProviderConfig,
    ProviderMessage,
    ProviderResponse,
    ProviderType,
    ProviderError,
    ProviderConnectionError,
    create_provider,
    create_copilot_provider,
    create_mock_provider
)


class TestProviderConfig(unittest.TestCase):
    
    def test_provider_config_creation(self):
        """Test creating provider config."""
        config = ProviderConfig(
            provider_type=ProviderType.COPILOT,
            model="gpt-4.1",
            timeout=30.0
        )
        
        self.assertEqual(config.provider_type, ProviderType.COPILOT)
        self.assertEqual(config.model, "gpt-4.1")
        self.assertEqual(config.timeout, 30.0)
        self.assertEqual(config.extra_params, {})
    
    def test_provider_config_with_extras(self):
        """Test config with extra parameters."""
        config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
            extra_params={"custom": "value"}
        )
        
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.extra_params["custom"], "value")


class TestProviderMessage(unittest.TestCase):
    
    def test_provider_message_creation(self):
        """Test creating provider message."""
        message = ProviderMessage(
            role="user",
            content="Hello, world!",
            metadata={"source": "test"}
        )
        
        self.assertEqual(message.role, "user")
        self.assertEqual(message.content, "Hello, world!")
        self.assertEqual(message.metadata["source"], "test")
    
    def test_provider_message_to_dict(self):
        """Test converting message to dict."""
        message = ProviderMessage(role="user", content="Test")
        message_dict = message.to_dict()
        
        self.assertEqual(message_dict["role"], "user")
        self.assertEqual(message_dict["content"], "Test")
        # metadata is empty but should not be included if empty
        if message.metadata:
            self.assertIn("metadata", message_dict)


class TestProviderResponse(unittest.TestCase):
    
    def test_provider_response_creation(self):
        """Test creating provider response."""
        response = ProviderResponse(
            content="Test response",
            model="gpt-4.1",
            provider="copilot",
            execution_time_ms=123.45
        )
        
        self.assertEqual(response.content, "Test response")
        self.assertEqual(response.model, "gpt-4.1")
        self.assertEqual(response.provider, "copilot")
        self.assertEqual(response.execution_time_ms, 123.45)
        self.assertIsInstance(response.timestamp, datetime)
    
    def test_provider_response_to_dict(self):
        """Test converting response to dict."""
        response = ProviderResponse(
            content="Test",
            model="test-model",
            provider="test-provider"
        )
        
        response_dict = response.to_dict()
        self.assertEqual(response_dict["content"], "Test")
        self.assertIn("timestamp", response_dict)


class TestMockProvider(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.config = ProviderConfig(
            provider_type=ProviderType.CUSTOM,
            model="mock-model"
        )
        self.provider = MockProvider(self.config)
    
    def test_mock_provider_initialization(self):
        """Test mock provider initialization."""
        self.assertEqual(self.provider.model, "mock-model")
        self.assertEqual(len(self.provider.responses), 1)
        self.assertEqual(self.provider.responses[0], "Mock response from LLM")
    
    def test_mock_provider_custom_responses(self):
        """Test mock provider with custom responses."""
        custom_responses = ["Response 1", "Response 2", "Response 3"]
        provider = MockProvider(self.config, custom_responses)
        
        self.assertEqual(provider.responses, custom_responses)
    
    def test_mock_provider_send_messages(self):
        """Test sending messages to mock provider."""
        messages = [
            ProviderMessage(role="user", content="Hello")
        ]
        
        response = self.provider.send_messages(messages, request_id="test-123")
        
        self.assertEqual(response.content, "Mock response from LLM")
        self.assertEqual(response.model, "mock-model")
        self.assertEqual(response.provider, "custom")
        self.assertEqual(response.request_id, "test-123")
        self.assertGreater(response.execution_time_ms, 0)
        self.assertIsNotNone(response.usage)
        self.assertTrue(response.metadata["mock"])
    
    def test_mock_provider_cycling_responses(self):
        """Test that mock provider cycles through responses."""
        custom_responses = ["First", "Second", "Third"]
        provider = MockProvider(self.config, custom_responses)
        messages = [ProviderMessage(role="user", content="Test")]
        
        # Get responses and verify cycling
        response1 = provider.send_messages(messages)
        response2 = provider.send_messages(messages)
        response3 = provider.send_messages(messages)
        response4 = provider.send_messages(messages)  # Should cycle back to first
        
        self.assertEqual(response1.content, "First")
        self.assertEqual(response2.content, "Second")
        self.assertEqual(response3.content, "Third")
        self.assertEqual(response4.content, "First")  # Cycled back
    
    def test_mock_provider_usage_stats(self):
        """Test mock provider usage statistics."""
        messages = [ProviderMessage(role="user", content="Test message")]
        
        # Initial stats should be zero
        initial_stats = self.provider.get_usage_stats()
        self.assertEqual(initial_stats["requests"], 0)
        
        # Send message and check updated stats
        self.provider.send_messages(messages, simulate_delay=0)
        
        stats = self.provider.get_usage_stats()
        self.assertEqual(stats["requests"], 1)
        self.assertGreater(stats["tokens_sent"], 0)
        self.assertGreater(stats["tokens_received"], 0)
        self.assertGreater(stats["total_time_ms"], 0)
    
    def test_mock_provider_validate_config(self):
        """Test mock provider config validation."""
        errors = self.provider.validate_config()
        self.assertEqual(errors, [])  # Mock provider is always valid


class TestCopilotProvider(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.config = ProviderConfig(
            provider_type=ProviderType.COPILOT,
            model="gpt-4.1"
        )
    
    def test_copilot_provider_initialization(self):
        """Test Copilot provider initialization."""
        provider = CopilotProvider(self.config)
        
        self.assertEqual(provider.model, "gpt-4.1")
        self.assertEqual(provider.provider_type, ProviderType.COPILOT)
        self.assertIsNone(provider.session_id)
    
    def test_copilot_provider_validation(self):
        """Test Copilot provider config validation."""
        provider = CopilotProvider(self.config)
        errors = provider.validate_config()
        
        self.assertEqual(errors, [])  # Valid config
    
    def test_copilot_provider_invalid_config(self):
        """Test Copilot provider with invalid config."""
        invalid_config = ProviderConfig(
            provider_type=ProviderType.OPENAI,  # Wrong type
            model=""  # Empty model
        )
        
        with self.assertRaises(ProviderError):
            CopilotProvider(invalid_config)
    
    @patch('one_think.copilot.ask_question')
    def test_copilot_provider_send_messages(self, mock_ask_question):
        """Test sending messages to Copilot provider."""
        # Mock the copilot.ask_question function
        mock_ask_question.return_value = ("session-123", "Hello from Copilot!")
        
        provider = CopilotProvider(self.config)
        messages = [
            ProviderMessage(role="system", content="You are helpful"),
            ProviderMessage(role="user", content="Hello")
        ]
        
        response = provider.send_messages(messages, request_id="test-req")
        
        # Verify response
        self.assertEqual(response.content, "Hello from Copilot!")
        self.assertEqual(response.model, "gpt-4.1")
        self.assertEqual(response.provider, "copilot")
        self.assertEqual(response.request_id, "test-req")
        self.assertEqual(response.metadata["session_id"], "session-123")
        
        # Verify session ID was updated
        self.assertEqual(provider.session_id, "session-123")
        
        # Verify copilot was called correctly
        mock_ask_question.assert_called_once()
        call_args = mock_ask_question.call_args
        self.assertEqual(call_args[1]["model"], "gpt-4.1")
    
    @patch('one_think.copilot.ask_question')
    def test_copilot_provider_error_handling(self, mock_ask_question):
        """Test Copilot provider error handling."""
        # Mock copilot to raise an exception
        mock_ask_question.side_effect = RuntimeError("copilot failed (code 1)")
        
        provider = CopilotProvider(self.config)
        messages = [ProviderMessage(role="user", content="Test")]
        
        with self.assertRaises(ProviderConnectionError):
            provider.send_messages(messages)
        
        # Verify error stats were updated
        stats = provider.get_usage_stats()
        self.assertEqual(stats["errors"], 1)
    
    def test_copilot_format_messages(self):
        """Test Copilot message formatting."""
        provider = CopilotProvider(self.config)
        messages = [
            ProviderMessage(role="system", content="System prompt"),
            ProviderMessage(role="user", content="User message"),
            ProviderMessage(role="assistant", content="Assistant reply")
        ]
        
        formatted = provider._format_messages_for_copilot(messages)
        
        expected = "System: System prompt\n\nUser: User message\n\nAssistant: Assistant reply"
        self.assertEqual(formatted, expected)
    
    def test_copilot_set_session_id(self):
        """Test setting Copilot session ID."""
        provider = CopilotProvider(self.config)
        provider.set_session_id("custom-session-123")
        
        self.assertEqual(provider.session_id, "custom-session-123")


class TestProviderFactory(unittest.TestCase):
    
    def test_create_copilot_provider(self):
        """Test creating Copilot provider via factory."""
        provider = create_provider("copilot", model="gpt-4.1")
        
        self.assertIsInstance(provider, CopilotProvider)
        self.assertEqual(provider.model, "gpt-4.1")
        self.assertEqual(provider.provider_type, ProviderType.COPILOT)
    
    def test_create_mock_provider(self):
        """Test creating mock provider via factory."""
        provider = create_provider("custom", model="test-model")
        
        self.assertIsInstance(provider, MockProvider)
        self.assertEqual(provider.model, "test-model")
    
    def test_create_provider_invalid_type(self):
        """Test creating provider with invalid type."""
        with self.assertRaises(ValueError):
            create_provider("invalid-type", model="test")
    
    def test_create_provider_not_implemented(self):
        """Test creating provider type that's not implemented."""
        with self.assertRaises(NotImplementedError):
            create_provider("openai", model="gpt-4")
    
    def test_convenience_functions(self):
        """Test convenience factory functions."""
        # Test Copilot convenience function
        copilot_provider = create_copilot_provider("gpt-4.1")
        self.assertIsInstance(copilot_provider, CopilotProvider)
        self.assertEqual(copilot_provider.model, "gpt-4.1")
        
        # Test mock convenience function
        mock_provider = create_mock_provider(["Test response"], "mock-model")
        self.assertIsInstance(mock_provider, MockProvider)
        self.assertEqual(mock_provider.responses, ["Test response"])
        self.assertEqual(mock_provider.model, "mock-model")


class TestLLMProviderBase(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        # Create mock provider for testing base functionality
        self.config = ProviderConfig(
            provider_type=ProviderType.CUSTOM,
            model="test-model"
        )
        self.provider = MockProvider(self.config)
    
    def test_format_messages(self):
        """Test formatting messages from dict to ProviderMessage."""
        message_dicts = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there", "metadata": {"test": True}}
        ]
        
        provider_messages = self.provider.format_messages(message_dicts)
        
        self.assertEqual(len(provider_messages), 2)
        self.assertIsInstance(provider_messages[0], ProviderMessage)
        self.assertEqual(provider_messages[0].role, "user")
        self.assertEqual(provider_messages[0].content, "Hello")
        
        self.assertEqual(provider_messages[1].role, "assistant")
        self.assertEqual(provider_messages[1].metadata["test"], True)
    
    def test_usage_stats_reset(self):
        """Test resetting usage statistics."""
        # Generate some usage
        messages = [ProviderMessage(role="user", content="Test")]
        self.provider.send_messages(messages)
        
        # Verify stats exist
        stats = self.provider.get_usage_stats()
        self.assertGreater(stats["requests"], 0)
        
        # Reset and verify
        self.provider.reset_usage_stats()
        reset_stats = self.provider.get_usage_stats()
        self.assertEqual(reset_stats["requests"], 0)
        self.assertEqual(reset_stats["total_time_ms"], 0.0)
    
    def test_create_error_response(self):
        """Test creating error response."""
        error = ValueError("Test error")
        error_response = self.provider._create_error_response(
            error, 
            request_id="test-123", 
            execution_time_ms=100.0
        )
        
        self.assertIn("Test error", error_response.content)
        self.assertEqual(error_response.request_id, "test-123")
        self.assertEqual(error_response.execution_time_ms, 100.0)
        self.assertTrue(error_response.metadata["error"])
        self.assertEqual(error_response.metadata["error_type"], "ValueError")


if __name__ == '__main__':
    unittest.main()