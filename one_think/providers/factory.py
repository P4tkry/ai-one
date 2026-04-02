"""
Provider factory and utility functions for AI-ONE.

This module provides factory functions and utilities for creating
and managing LLM providers.
"""

import logging
from typing import Dict, List, Optional, Any

from .base import LLMProvider, ProviderConfig, ProviderType
from .copilot import CopilotProvider
from .mock import MockProvider

logger = logging.getLogger(__name__)


def create_provider(provider_type: str, **config_kwargs) -> LLMProvider:
    """
    Factory function to create providers.
    
    Args:
        provider_type: Type of provider ("copilot", "mock", "openai", etc.)
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
        # Placeholder for future providers (OpenAI, Anthropic, etc.)
        raise NotImplementedError(f"Provider {provider_type} not yet implemented")


def create_copilot_provider(model: str = 'gpt-4.1', **kwargs) -> CopilotProvider:
    """
    Convenience function to create Copilot provider.
    
    Args:
        model: LLM model to use
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured CopilotProvider
    """
    return create_provider("copilot", model=model, **kwargs)


def create_mock_provider(
    model: str = 'mock-model', 
    responses: Optional[List[str]] = None,
    **kwargs
) -> MockProvider:
    """
    Convenience function to create Mock provider.
    
    Args:
        model: Mock model name
        responses: List of mock responses to use
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured MockProvider
    """
    provider = create_provider("custom", model=model, **kwargs)
    if responses:
        provider.set_responses(responses)
    return provider


def list_available_providers() -> List[str]:
    """
    Get list of available provider types.
    
    Returns:
        List of provider type strings
    """
    return [p.value for p in ProviderType]


def validate_provider_config(provider_type: str, config: Dict[str, Any]) -> List[str]:
    """
    Validate provider configuration without creating the provider.
    
    Args:
        provider_type: Provider type string
        config: Configuration dictionary
        
    Returns:
        List of validation error messages (empty if valid)
    """
    try:
        # Create temporary provider to validate
        provider = create_provider(provider_type, **config)
        return provider.validate_config()
    except Exception as e:
        return [f"Configuration error: {str(e)}"]