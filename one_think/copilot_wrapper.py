"""
Modern Copilot Integration for AI-ONE.

This module provides the new Copilot integration using:
- Executor + Provider architecture
- Session-based conversation management  
- Tool Registry for dynamic tool dispatch
- Protocol parsing for structured responses

While maintaining backward compatibility with the original copilot.py API.
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from one_think.core import Executor, Session, ExecutionResult, ExecutionStatus
from one_think.providers import create_copilot_provider, CopilotProvider
from one_think.tools import tool_registry

logger = logging.getLogger(__name__)


@dataclass
class CopilotConfig:
    """Configuration for modern Copilot wrapper."""
    model: str = "gpt-4.1"
    max_tool_iterations: int = 5
    enable_tools: bool = True
    auto_discover_tools: bool = True
    system_prompt: Optional[str] = None
    catalog: Optional[str] = None
    timeout: float = 30.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "max_tool_iterations": self.max_tool_iterations,
            "enable_tools": self.enable_tools,
            "auto_discover_tools": self.auto_discover_tools,
            "system_prompt": self.system_prompt,
            "catalog": self.catalog,
            "timeout": self.timeout
        }


class CopilotWrapper:
    """
    Modern Copilot wrapper with full AI-ONE architecture integration.
    
    Features:
    - Session-based conversation management
    - Dynamic tool dispatch via Tool Registry
    - Provider abstraction for LLM communication
    - Protocol parsing for structured responses
    - Usage tracking and metrics
    - Backward compatibility with original API
    
    This replaces the simple ask_question function with a rich
    conversation system while maintaining the same external interface.
    """
    
    def __init__(self, config: Optional[CopilotConfig] = None):
        """
        Initialize modern Copilot wrapper.
        
        Args:
            config: Copilot configuration (uses defaults if None)
        """
        self.config = config or CopilotConfig()
        
        # Initialize core components
        self.provider = self._create_provider()
        self.executor = self._create_executor()
        self._sessions: Dict[str, Session] = {}
        
        # Initialize tools if enabled
        if self.config.enable_tools and self.config.auto_discover_tools:
            tool_count = tool_registry.discover_tools()
            logger.info(f"CopilotWrapper initialized with {tool_count} tools")
        else:
            logger.info("CopilotWrapper initialized without tools")
    
    def _create_provider(self) -> CopilotProvider:
        """Create Copilot provider instance."""
        return create_copilot_provider(
            model=self.config.model,
            timeout=self.config.timeout
        )
    
    def _create_executor(self) -> Executor:
        """Create Executor instance."""
        executor = Executor(
            tool_registry=tool_registry if self.config.enable_tools else None,
            max_tool_iterations=self.config.max_tool_iterations
        )
        executor.set_llm_provider(self.provider)
        return executor
    
    def ask_question(
        self, 
        prompt: str, 
        model: str = None,
        session_id: str = None,
        catalog: str = None,
        system_prompt: str = None
    ) -> tuple[str, str]:
        """
        Ask a question using the modern AI-ONE architecture.
        
        This maintains API compatibility with the original ask_question function
        while providing full session management and tool integration.
        
        Args:
            prompt: User's question/prompt
            model: LLM model to use (overrides config)
            session_id: Session ID for conversation continuity
            catalog: Working directory for tools
            system_prompt: System prompt override
            
        Returns:
            (session_id, response_text) - same format as original
        """
        # Use provided session_id or create new one
        session_id = session_id or str(uuid.uuid4())
        
        # Get or create session
        session = self._get_or_create_session(session_id)
        
        # Override model if provided
        if model and model != self.config.model:
            self.provider.config.model = model
            logger.debug(f"Model overridden to: {model}")
        
        # Set catalog for tools
        if catalog:
            # Store catalog in session metadata for tools to use
            session.metadata = session.metadata or {}
            session.metadata["catalog"] = catalog
        
        # Determine system prompt
        effective_system_prompt = (
            system_prompt or 
            self.config.system_prompt or
            self._get_default_system_prompt()
        )
        
        try:
            # Execute the request
            result = self.executor.execute_request(
                user_input=prompt,
                session=session,
                system_prompt=effective_system_prompt if not session.history else None,
                request_id=f"copilot_{session_id}_{len(session.history)}"
            )
            
            # Log execution details
            logger.info(
                f"Copilot request completed: {result.status.value} "
                f"in {result.execution_time_ms:.1f}ms"
            )
            
            if result.tool_results:
                logger.debug(f"Executed {len(result.tool_results)} tools")
            
            # Return response in original format
            return session_id, result.response
            
        except Exception as e:
            logger.error(f"Copilot request failed: {e}", exc_info=True)
            error_response = f"I encountered an error: {str(e)}"
            return session_id, error_response
    
    def _get_or_create_session(self, session_id: str) -> Session:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
            logger.debug(f"Created new session: {session_id}")
        else:
            logger.debug(f"Using existing session: {session_id}")
        
        return self._sessions[session_id]
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for Copilot."""
        return (
            "You are GitHub Copilot, a helpful AI assistant. "
            "You can help with coding, writing, analysis, and various tasks. "
            "You have access to tools that can help you provide better answers. "
            "When you need to use tools, respond with a JSON tool request. "
            "Otherwise, respond with helpful and accurate information."
        )
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: Session ID to query
            
        Returns:
            Session info dict or None if not found
        """
        if session_id not in self._sessions:
            return None
        
        session = self._sessions[session_id]
        return {
            "session_id": session.id,
            "created_at": session.created_at.isoformat(),
            "message_count": len(session.history),
            "metadata": session.metadata
        }
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return [
            self.get_session_info(session_id) 
            for session_id in self._sessions.keys()
        ]
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear/delete a session.
        
        Args:
            session_id: Session ID to clear
            
        Returns:
            True if session was found and cleared, False otherwise
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session cleared: {session_id}")
            return True
        return False
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        provider_stats = self.provider.get_usage_stats()
        executor_metrics = self.executor.get_metrics()
        
        return {
            "provider": provider_stats,
            "executor": executor_metrics,
            "sessions": {
                "active_count": len(self._sessions),
                "total_messages": sum(len(s.history) for s in self._sessions.values())
            },
            "config": self.config.to_dict()
        }
    
    def reset_usage_stats(self):
        """Reset provider usage statistics."""
        self.provider.reset_usage_stats()
        logger.info("Usage statistics reset")


# Global instance for backward compatibility
_copilot_wrapper = None


def get_copilot_wrapper() -> CopilotWrapper:
    """Get the global Copilot wrapper instance."""
    global _copilot_wrapper
    if _copilot_wrapper is None:
        _copilot_wrapper = CopilotWrapper()
    return _copilot_wrapper


def ask_question(
    prompt: str,
    model: str = 'gpt-4.1',
    session_id: str = None,
    catalog: str = None
) -> tuple[str | None, str]:
    """
    Backward compatible ask_question function.
    
    This function maintains the exact API of the original copilot.py
    while using the modern AI-ONE architecture under the hood.
    
    Args:
        prompt: User's question/prompt
        model: LLM model to use  
        session_id: Session ID for conversation continuity
        catalog: Working directory for tools
        
    Returns:
        (session_id, response_text) - same format as original
    """
    wrapper = get_copilot_wrapper()
    return wrapper.ask_question(prompt, model, session_id, catalog)


def configure_copilot(config: CopilotConfig):
    """
    Configure the global Copilot wrapper.
    
    Args:
        config: New configuration
    """
    global _copilot_wrapper
    _copilot_wrapper = CopilotWrapper(config)
    logger.info("Copilot wrapper reconfigured")


def get_copilot_stats() -> Dict[str, Any]:
    """Get usage statistics from the global wrapper."""
    wrapper = get_copilot_wrapper()
    return wrapper.get_usage_stats()


# For debugging and testing
if __name__ == '__main__':
    # Test the new wrapper
    print("Testing modern Copilot wrapper...")
    
    # Test basic question
    session_id, response = ask_question(
        "What is the capital of France?",
        model="gpt-4.1"
    )
    
    print(f"Session: {session_id}")
    print(f"Response: {response}")
    
    # Get stats
    stats = get_copilot_stats()
    print(f"Stats: {stats}")