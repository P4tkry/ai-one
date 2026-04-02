"""
AI-ONE Provider Package

Clean provider interface for different LLM backends.

This package provides unified abstractions for LLM providers including:
- GitHub Copilot CLI (via CopilotProvider)
- Mock provider for testing (MockProvider)
- Extensible base classes for custom providers

Architecture:
    Executor → Provider Interface → LLM Backend

Usage:
    from one_think.providers import create_provider, CopilotProvider
    
    # Create via factory
    provider = create_provider("copilot", model="gpt-4.1")
    
    # Or create directly
    config = ProviderConfig(ProviderType.COPILOT, model="gpt-4.1")
    provider = CopilotProvider(config)
"""

# Base interfaces and types
from .base import (
    LLMProvider,
    ProviderConfig, 
    ProviderMessage,
    ProviderResponse,
    ProviderError,
    ProviderType
)

# Specific provider implementations
from .copilot import CopilotProvider, ProviderConnectionError
from .mock import MockProvider

# Factory functions and utilities
from .factory import (
    create_provider,
    create_copilot_provider,
    create_mock_provider,
    list_available_providers,
    validate_provider_config
)

# Convenient exports for backward compatibility
__all__ = [
    # Base classes
    'LLMProvider',
    'ProviderConfig', 
    'ProviderMessage',
    'ProviderResponse',
    'ProviderError',
    'ProviderType',
    
    # Provider implementations
    'CopilotProvider',
    'MockProvider',
    'ProviderConnectionError',
    
    # Factory functions
    'create_provider',
    'create_copilot_provider',
    'create_mock_provider',
    'list_available_providers',
    'validate_provider_config'
]