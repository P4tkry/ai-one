"""
Provider Interface - LLM abstraction layer for AI-ONE.

This module provides a clean abstraction for different LLM providers,
allowing the Executor to work with various backends (Copilot, OpenAI, Anthropic, etc.)
without knowing implementation details.

Architecture:
    Executor → Provider → LLM Backend (Copilot CLI, OpenAI API, etc.)
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Types of supported LLM providers."""
    COPILOT = "copilot"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    CUSTOM = "custom"


@dataclass
class ProviderConfig:
    """Configuration for LLM providers."""
    provider_type: ProviderType
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = 30.0
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    extra_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


@dataclass
class ProviderMessage:
    """Standardized message format for providers."""
    role: str  # "system", "user", "assistant"
    content: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {"role": self.role, "content": self.content}
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class ProviderResponse:
    """Standardized response from LLM providers."""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    request_id: Optional[str] = None
    execution_time_ms: float = 0
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat() if self.timestamp else None
        return result


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class ProviderConnectionError(ProviderError):
    """Raised when provider connection fails."""
    pass


class ProviderAuthenticationError(ProviderError):
    """Raised when provider authentication fails."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""
    pass


class ProviderQuotaExceededError(ProviderError):
    """Raised when provider quota is exceeded."""
    pass


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    This provides a uniform interface that the Executor can use
    regardless of the underlying LLM service.
    
    Features:
    - Standardized message format
    - Error handling and retries
    - Usage tracking and quotas
    - Request/response logging
    - Provider-specific optimizations
    """
    
    def __init__(self, config: ProviderConfig):
        """
        Initialize provider.
        
        Args:
            config: Provider configuration
        """
        self.config = config
        self.provider_type = config.provider_type
        self.model = config.model
        self._usage_stats = {
            "requests": 0,
            "tokens_sent": 0,
            "tokens_received": 0,
            "errors": 0,
            "total_time_ms": 0.0
        }
    
    @abstractmethod
    def send_messages(
        self, 
        messages: List[ProviderMessage], 
        request_id: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Send messages to LLM and get response.
        
        Args:
            messages: List of conversation messages
            request_id: Optional request correlation ID
            **kwargs: Provider-specific parameters
            
        Returns:
            Provider response with content and metadata
            
        Raises:
            ProviderError: If request fails
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> List[str]:
        """
        Validate provider configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        pass
    
    def format_messages(self, messages: List[Dict[str, Any]]) -> List[ProviderMessage]:
        """
        Convert standard message format to provider messages.
        
        Args:
            messages: List of message dicts with role/content
            
        Returns:
            List of ProviderMessage objects
        """
        provider_messages = []
        for msg in messages:
            provider_msg = ProviderMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                metadata=msg.get("metadata", {})
            )
            provider_messages.append(provider_msg)
        return provider_messages
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get provider usage statistics."""
        return self._usage_stats.copy()
    
    def reset_usage_stats(self):
        """Reset usage statistics."""
        self._usage_stats = {
            "requests": 0,
            "tokens_sent": 0, 
            "tokens_received": 0,
            "errors": 0,
            "total_time_ms": 0.0
        }
    
    def _update_usage_stats(self, response: ProviderResponse, error: bool = False):
        """Update internal usage statistics."""
        self._usage_stats["requests"] += 1
        self._usage_stats["total_time_ms"] += response.execution_time_ms
        
        if error:
            self._usage_stats["errors"] += 1
        
        if response.usage:
            self._usage_stats["tokens_sent"] += response.usage.get("prompt_tokens", 0)
            self._usage_stats["tokens_received"] += response.usage.get("completion_tokens", 0)
    
    def _create_error_response(
        self, 
        error: Exception, 
        request_id: Optional[str] = None,
        execution_time_ms: float = 0
    ) -> ProviderResponse:
        """Create error response."""
        return ProviderResponse(
            content=f"Error: {str(error)}",
            model=self.model,
            provider=self.provider_type.value,
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            metadata={"error": True, "error_type": type(error).__name__}
        )


class CopilotProvider(LLMProvider):
    """
    Copilot CLI provider implementation.
    
    Wraps the existing copilot.py functionality in the Provider interface.
    """
    
    def __init__(self, config: ProviderConfig):
        """Initialize Copilot provider."""
        super().__init__(config)
        self.session_id = None  # Will be managed per conversation
        
        # Validate Copilot-specific config
        validation_errors = self.validate_config()
        if validation_errors:
            raise ProviderError(f"Invalid Copilot config: {validation_errors}")
    
    def send_messages(
        self, 
        messages: List[ProviderMessage], 
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Send messages to Copilot CLI with session management.
        
        Args:
            messages: Conversation messages (only current prompt - history handled by Copilot CLI)
            request_id: Request correlation ID
            session_id: Session ID for Copilot CLI --resume parameter
            **kwargs: Additional parameters (catalog, etc.)
            
        Returns:
            Copilot response
        """
        start_time = time.time()
        
        try:
            # Import copilot functionality
            from one_think.copilot import ask_question, build_messages
            
            # Convert provider messages to JSON messages format
            json_messages = self._convert_messages_to_json(messages)
            
            # Use provided session_id for Copilot CLI --resume
            copilot_session_id = session_id
            
            # Call Copilot CLI with JSON messages format
            result_session_id, response_content = ask_question(
                messages=json_messages,  # Now using JSON format
                model=self.config.model,
                session_id=copilot_session_id,
                catalog=kwargs.get('catalog')
            )
            
            # Update session ID for future requests
            self.session_id = result_session_id
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Create response
            response = ProviderResponse(
                content=response_content,
                model=self.config.model,
                provider=self.provider_type.value,
                request_id=request_id,
                execution_time_ms=execution_time_ms,
                metadata={
                    "session_id": result_session_id,
                    "catalog": kwargs.get("catalog")
                }
            )
            
            # Update usage stats
            self._update_usage_stats(response)
            
            logger.debug(f"Copilot request completed in {execution_time_ms:.1f}ms")
            return response
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Copilot provider error: {e}", exc_info=True)
            
            # Create error response and update stats
            error_response = self._create_error_response(e, request_id, execution_time_ms)
            self._update_usage_stats(error_response, error=True)
            
            # Re-raise as provider error
            if "failed (code" in str(e):
                raise ProviderConnectionError(f"Copilot CLI failed: {e}") from e
            else:
                raise ProviderError(f"Copilot provider error: {e}") from e
    
    def _convert_messages_to_json(self, messages: List[ProviderMessage]) -> List[Dict[str, str]]:
        """
        Convert provider messages to JSON format for Copilot CLI.
        
        Args:
            messages: Provider messages
            
        Returns:
            List of JSON message objects with 'author' and 'message' fields
        """
        json_messages = []
        
        for message in messages:
            if message.role == "system":
                json_messages.append({
                    "author": "system",
                    "message": message.content
                })
            elif message.role == "user":
                json_messages.append({
                    "author": "user", 
                    "message": message.content
                })
            elif message.role == "assistant":
                json_messages.append({
                    "author": "assistant",
                    "message": message.content
                })
            elif message.role == "tool":
                json_messages.append({
                    "author": "tool",
                    "message": message.content
                })
            else:
                # Handle custom roles
                json_messages.append({
                    "author": message.role,
                    "message": message.content
                })
        
        return json_messages
    
    def _extract_current_prompt(self, messages: List[ProviderMessage]) -> str:
        """
        Extract current prompt from messages, including system prompt if present.
        
        For first message in session, we need to include system prompt.
        For subsequent messages, Copilot CLI handles context via --resume.
        
        Args:
            messages: Provider messages
            
        Returns:
            Formatted prompt for Copilot CLI
        """
        # Check if we have system prompt (indicates first message)
        system_message = None
        user_message = None
        
        for message in messages:
            if message.role == "system":
                system_message = message
            elif message.role == "user":
                user_message = message
        
        # If we have system prompt, combine it with user message
        if system_message and user_message:
            return f"{system_message.content}\n\nUser: {user_message.content}"
        elif user_message:
            return user_message.content
        else:
            # Fallback: format all messages
            return self._format_messages_for_copilot(messages)
    
    def _format_messages_for_copilot(self, messages: List[ProviderMessage]) -> str:
        """
        Format messages for Copilot CLI prompt.
        
        NOTE: This method is now mainly used as fallback.
        With --resume session management, we typically only send current prompts.
        """
        prompt_parts = []
        
        for message in messages:
            if message.role == "system":
                prompt_parts.append(f"System: {message.content}")
            elif message.role == "user":
                prompt_parts.append(f"User: {message.content}")
            elif message.role == "assistant":
                prompt_parts.append(f"Assistant: {message.content}")
            else:
                # Handle custom roles
                prompt_parts.append(f"{message.role.title()}: {message.content}")
        
        return "\n\n".join(prompt_parts)
    
    def validate_config(self) -> List[str]:
        """Validate Copilot provider configuration."""
        errors = []
        
        # Check that provider type is Copilot
        if self.config.provider_type != ProviderType.COPILOT:
            errors.append("Provider type must be COPILOT")
        
        # Check model is specified
        if not self.config.model:
            errors.append("Model must be specified")
        
        # Copilot doesn't use API keys, so no validation needed there
        
        return errors
    
    def set_session_id(self, session_id: str):
        """Set the Copilot session ID for conversation continuity."""
        self.session_id = session_id
        logger.debug(f"Copilot session ID set to: {session_id}")


class MockProvider(LLMProvider):
    """
    Mock provider for testing and development.
    
    Returns predefined responses for testing the Provider interface
    without calling actual LLM services.
    """
    
    def __init__(self, config: ProviderConfig, responses: List[str] = None):
        """
        Initialize mock provider.
        
        Args:
            config: Provider configuration
            responses: List of predefined responses (cycles through)
        """
        super().__init__(config)
        self.responses = responses or ["Mock response from LLM"]
        self.response_index = 0
    
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
        time.sleep(kwargs.get("simulate_delay", 0.1))
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        response = ProviderResponse(
            content=response_content,
            model=self.config.model,
            provider=self.provider_type.value,
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            usage={
                "prompt_tokens": sum(len(msg.content.split()) for msg in messages),
                "completion_tokens": len(response_content.split()),
                "total_tokens": sum(len(msg.content.split()) for msg in messages) + len(response_content.split())
            },
            metadata={"mock": True, "message_count": len(messages)}
        )
        
        self._update_usage_stats(response)
        
        return response
    
    def validate_config(self) -> List[str]:
        """Mock provider validation (always valid)."""
        return []


def create_provider(provider_type: str, **config_kwargs) -> LLMProvider:
    """
    Factory function to create providers.
    
    Args:
        provider_type: Type of provider ("copilot", "mock", etc.)
        **config_kwargs: Configuration parameters
        
    Returns:
        Configured provider instance
        
    Raises:
        ValueError: If provider type is unsupported
    """
    # Convert string to enum
    try:
        provider_enum = ProviderType(provider_type.lower())
    except ValueError:
        available = [p.value for p in ProviderType]
        raise ValueError(f"Unsupported provider type: {provider_type}. Available: {available}")
    
    # Create config
    config = ProviderConfig(
        provider_type=provider_enum,
        **config_kwargs
    )
    
    # Create appropriate provider
    if provider_enum == ProviderType.COPILOT:
        return CopilotProvider(config)
    elif provider_enum == ProviderType.CUSTOM:
        # For testing - return mock
        return MockProvider(config)
    else:
        # Other providers can be implemented here
        raise NotImplementedError(f"Provider {provider_type} not implemented yet")


def create_copilot_provider(model: str = "gpt-4.1", **kwargs) -> CopilotProvider:
    """Convenience function to create Copilot provider."""
    return create_provider("copilot", model=model, **kwargs)


def create_llm_provider_function(provider: 'LLMProvider') -> Callable:
    """
    Create a function wrapper for a Provider instance.
    
    This allows Provider instances to be used where the Executor
    expects a function-based provider.
    
    Args:
        provider: Provider instance
        
    Returns:
        Function that takes messages and returns response text
    """
    def provider_function(messages: List[Dict[str, Any]]) -> str:
        """Provider function wrapper."""
        provider_messages = provider.format_messages(messages)
        response = provider.send_messages(provider_messages)
        return response.content
    
    return provider_function
def create_mock_provider(responses: List[str] = None, model: str = "mock-model") -> MockProvider:
    """Convenience function to create mock provider."""
    return MockProvider(
        ProviderConfig(provider_type=ProviderType.CUSTOM, model=model),
        responses=responses
    )