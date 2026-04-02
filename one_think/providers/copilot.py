"""
GitHub Copilot CLI provider implementation for AI-ONE.

This module integrates with GitHub Copilot CLI using the --resume session management
and JSON messages format for structured conversations.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any

from .base import (
    LLMProvider, ProviderConfig, ProviderMessage, ProviderResponse, 
    ProviderError, ProviderType
)

logger = logging.getLogger(__name__)


class ProviderConnectionError(ProviderError):
    """Connection-specific provider error."""
    pass


class CopilotProvider(LLMProvider):
    """
    GitHub Copilot CLI provider implementation.
    
    Integrates with GitHub Copilot CLI using:
    - Native session management via --resume={session_id}
    - JSON messages format for structured input
    - Tool results integration in conversation context
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
            messages: Conversation messages (structured format)
            request_id: Request correlation ID
            session_id: Session ID for Copilot CLI --resume parameter
            **kwargs: Additional parameters (catalog, etc.)
            
        Returns:
            Copilot response with structured data
        """
        start_time = time.time()
        
        try:
            # Import copilot functionality
            from .copilot_cli import ask_question
            
            # Convert provider messages to JSON messages format
            json_messages = self._convert_messages_to_json(messages)
            
            # Use provided session_id for Copilot CLI --resume
            copilot_session_id = session_id
            
            # Call Copilot CLI with JSON messages format and streaming if enabled
            stream_enabled = kwargs.get('stream', False)
            
            result_session_id, response_content = ask_question(
                messages=json_messages,  # Structured JSON format
                model=self.config.model,
                session_id=copilot_session_id,
                catalog=kwargs.get('catalog'),
                stream=stream_enabled
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
                    "catalog": kwargs.get("catalog"),
                    "message_count": len(messages)
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
        LEGACY: Extract current prompt from messages (kept for backwards compatibility).
        
        NOTE: With JSON messages format, this is rarely used.
        The new _convert_messages_to_json() is the primary method.
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
        LEGACY: Format messages for Copilot CLI prompt (kept for backwards compatibility).
        
        NOTE: This is mainly used as fallback. With --resume session management
        and JSON format, we typically use structured messages.
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