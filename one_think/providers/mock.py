"""
Mock provider implementation for AI-ONE testing.

This provider simulates LLM responses for testing and development
without requiring actual API calls.
"""

import time
import logging
from typing import Dict, List, Optional, Any

from .base import (
    LLMProvider, ProviderConfig, ProviderMessage, ProviderResponse, 
    ProviderType
)

logger = logging.getLogger(__name__)


class MockProvider(LLMProvider):
    """
    Mock LLM provider for testing.
    
    Returns predefined responses in sequence, useful for:
    - Unit testing without API calls
    - Development and debugging
    - Performance testing
    """
    
    def __init__(self, config: ProviderConfig, responses: Optional[List[str]] = None):
        """
        Initialize mock provider.
        
        Args:
            config: Provider configuration
            responses: List of responses to cycle through (default: generic responses)
        """
        super().__init__(config)
        
        # Default responses if none provided
        self.responses = responses or [
            '{"type": "response", "content": "This is a mock response."}',
            '{"type": "response", "content": "Another mock response for testing."}',
            '{"type": "tool_request", "tools": [{"tool_name": "test_tool", "params": {"query": "mock"}, "id": "req_1"}]}',
            '{"type": "response", "content": "Mock response after tool call."}'
        ]
        
        self.response_index = 0
        logger.debug(f"Mock provider initialized with {len(self.responses)} responses")
    
    def send_messages(
        self, 
        messages: List[ProviderMessage], 
        request_id: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """Send mock response."""
        start_time = time.time()
        
        # Get next response (cycle through)
        response_content = self.responses[self.response_index % len(self.responses)]
        self.response_index += 1
        
        # Simulate some processing time
        simulate_delay = kwargs.get("simulate_delay", 0.1)
        time.sleep(simulate_delay)
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Calculate mock token usage
        prompt_tokens = sum(len(msg.content.split()) for msg in messages)
        completion_tokens = len(response_content.split())
        
        response = ProviderResponse(
            content=response_content,
            model=self.config.model,
            provider=self.provider_type.value,
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            },
            metadata={
                "mock": True, 
                "message_count": len(messages),
                "response_index": self.response_index - 1
            }
        )
        
        self._update_usage_stats(response)
        
        logger.debug(f"Mock response {self.response_index - 1}: {response_content[:100]}...")
        return response
    
    def validate_config(self) -> List[str]:
        """Mock provider validation (always valid)."""
        return []
    
    def add_response(self, response: str):
        """Add a new response to the rotation."""
        self.responses.append(response)
    
    def set_responses(self, responses: List[str]):
        """Replace all responses."""
        self.responses = responses
        self.response_index = 0
    
    def reset(self):
        """Reset to first response."""
        self.response_index = 0