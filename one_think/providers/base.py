"""
Base provider interface and shared components for AI-ONE.

This module defines the core abstractions that all LLM providers must implement,
along with common data structures and utilities.
"""

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
    """Message structure for LLM provider interface."""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        if self.metadata is None:
            self.metadata = {}


@dataclass 
class ProviderResponse:
    """Response from LLM provider."""
    content: str
    model: str
    provider: str
    request_id: Optional[str] = None
    execution_time_ms: float = 0
    usage: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM providers must implement this interface to work with the AI-ONE executor.
    This ensures consistent behavior regardless of the underlying LLM service.
    """
    
    def __init__(self, config: ProviderConfig):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider configuration
        """
        self.config = config
        self.provider_type = config.provider_type
        self.model = config.model
        
        # Usage tracking
        self._usage_stats = {
            "requests": 0,
            "tokens_sent": 0, 
            "tokens_received": 0,
            "errors": 0,
            "total_time_ms": 0.0
        }
        
        # Provider state
        self.session_id: Optional[str] = None
    
    @abstractmethod
    def send_messages(
        self, 
        messages: List[ProviderMessage],
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Send messages to the LLM and get response.
        
        Args:
            messages: List of conversation messages
            session_id: Optional session ID for conversation continuity
            request_id: Optional request ID for tracking
            **kwargs: Provider-specific parameters
            
        Returns:
            ProviderResponse with LLM output
            
        Raises:
            ProviderError: If the request fails
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> List[str]:
        """
        Validate provider configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        pass
    
    def format_messages(self, messages: List[Dict[str, str]]) -> List[ProviderMessage]:
        """
        Convert generic message dictionaries to ProviderMessage objects.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
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