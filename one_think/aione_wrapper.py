"""
AI-ONE Modern Interface Integration.

This module provides the enhanced AI-ONE interface using:
- Executor + Provider architecture
- Session-based conversation management  
- Tool Registry for dynamic tool dispatch
- Protocol parsing for structured responses

While maintaining backward compatibility with the original API.
"""

import logging
import uuid
from typing import Optional, Dict, Any, List

from .core import Executor, ExecutionResult
from .core import Session
from .tools import tool_registry
from .providers import create_copilot_provider, CopilotProvider
from .debug import (
    debug_request_start, debug_request_end, debug_session_update,
    debug_component
)

logger = logging.getLogger(__name__)


class AiOneConfig:
    """Configuration for modern AI-ONE wrapper."""
    
    def __init__(
        self,
        model: str = 'gpt-4.1',
        enable_tools: bool = True,
        max_tool_iterations: int = 5,
        system_prompt: Optional[str] = None,
        session_timeout: int = 3600,  # 1 hour
        debug: bool = False
    ):
        self.model = model
        self.enable_tools = enable_tools
        self.max_tool_iterations = max_tool_iterations
        self.system_prompt = system_prompt
        self.session_timeout = session_timeout
        self.debug = debug


class AiOneWrapper:
    """
    Modern AI-ONE wrapper with full architecture integration.
    
    This class combines:
    - Executor: Tool orchestration and protocol parsing
    - Provider: LLM backend integration (Copilot, OpenAI, etc.)
    - Session: Conversation state management
    - Tools: Dynamic tool registry and execution
    
    Features:
    - Session-based conversations with state persistence
    - Tool integration via dynamic registry
    - Provider abstraction supporting multiple LLM backends
    - JSON protocol for structured requests/responses
    - Usage statistics and session monitoring
    """
    
    def __init__(self, config: Optional[AiOneConfig] = None):
        """
        Initialize modern AI-ONE wrapper.
        
        Args:
            config: AI-ONE configuration (uses defaults if None)
        """
        self.config = config or AiOneConfig()
        
        # Initialize tool registry
        self.tool_registry = tool_registry if self.config.enable_tools else None
        
        # Initialize executor (without provider - will be provided per request)
        self.executor = Executor(
            tool_registry=self.tool_registry,
            max_tool_iterations=self.config.max_tool_iterations
        )
        
        # Session management
        self._sessions: Dict[str, Session] = {}
        
        # Log initialization
        if self.tool_registry:
            tool_count = len(self.tool_registry.list_tools())
            logger.info(f"AiOneWrapper initialized with {tool_count} tools")
        else:
            logger.info("AiOneWrapper initialized without tools")
    
    def _create_provider(self) -> CopilotProvider:
        """Create Copilot provider instance."""
        return create_copilot_provider(
            model=self.config.model
        )
    
    def ask_question_with_git_style(
        self,
        question: str, 
        session_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        system_prompt: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Ask a question using the modern AI-ONE architecture with git-style status callbacks.
        
        Args:
            question: User question/prompt
            session_id: Session ID (auto-generated if None)
            progress_callback: Function to call with status updates (message, type)
            system_prompt: Custom system prompt (uses default if None)
            
        Returns:
            Tuple of (session_id, response_text)
        """
        # Generate session ID if needed
        if session_id is None:
            session_id = str(uuid.uuid4())
            if progress_callback:
                progress_callback("Creating new session", "session")

        # Generate request ID for tracking
        request_id = f"aione_{session_id[:8]}_{uuid.uuid4().hex[:8]}"
        
        # Debug request start
        debug_request_start(request_id, question, session_id)
        
        try:
            
            # Get or create session
            session = self._get_or_create_session(session_id)
            debug_session_update(session_id, 'RETRIEVED', {
                'requests_count': session.stats['requests_count'],
                'created_at': session.created_at.isoformat()
            })
            
            # Determine system prompt - only send once per session
            if not session.system_prompt_sent:
                final_system_prompt = system_prompt or self.config.system_prompt or self._get_default_system_prompt()
                if progress_callback:
                    progress_callback("Loading system prompt", "system_prompt")
                session.system_prompt_sent = True  # Mark as sent
            else:
                final_system_prompt = None  # Don't send system prompt again
                
            debug_component('wrapper', 'SYSTEM_PROMPT', {
                'custom_provided': system_prompt is not None,
                'config_provided': self.config.system_prompt is not None,
                'prompt_length': len(final_system_prompt) if final_system_prompt is not None else 0
            })
            
            # Create provider
            provider = self._create_provider()
            debug_component('wrapper', 'PROVIDER_CREATED', {
                'provider_type': type(provider).__name__,
                'model': getattr(provider, 'model', 'unknown')
            })
            
            # Initialize executor with provider for this request
            executor = Executor(
                tool_registry=self.tool_registry,
                llm_provider=provider,
                max_tool_iterations=self.config.max_tool_iterations
            )
            debug_component('wrapper', 'EXECUTOR_CREATED', {
                'max_iterations': self.config.max_tool_iterations,
                'tools_enabled': self.tool_registry is not None
            })
            
            # Add progress callback for thinking phase
            if progress_callback:
                progress_callback("AI thinking", "thinking")
            
            # Execute request
            result: ExecutionResult = executor.execute_request(
                user_input=question,
                session=session,
                system_prompt=final_system_prompt,
                request_id=request_id
            )
            
            # Signal thinking completion
            if progress_callback:
                progress_callback("Thinking complete", "thinking_complete")
            
            # Log results
            logger.info(
                f"AI-ONE request completed: {result.status.value} "
                f"(tools: {len(result.tool_results) if result.tool_results else 0})"
            )
            
            if result.tool_results:
                logger.debug(f"Executed {len(result.tool_results)} tools")
                debug_component('wrapper', 'TOOLS_EXECUTED', {
                    'tool_count': len(result.tool_results),
                    'tool_names': [tr.tool for tr in result.tool_results] if result.tool_results else []
                })
            
            # Debug request completion
            debug_request_end(request_id, result.status.value, result.execution_time_ms)
            
            # Return response in original format
            return session_id, result.response
            
        except Exception as e:
            if progress_callback:
                progress_callback("Request failed", "thinking_complete")
            logger.error(f"AI-ONE request failed: {e}", exc_info=True)
            debug_component('wrapper', 'REQUEST_FAILED', {
                'request_id': request_id,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            error_response = f"I encountered an error: {str(e)}"
            return session_id, error_response

    def ask_question(
        self,
        question: str, 
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Ask a question using the modern AI-ONE architecture.
        
        Args:
            question: User question/prompt
            session_id: Session ID (auto-generated if None)
            system_prompt: Custom system prompt (uses default if None)
            
        Returns:
            Tuple of (session_id, response_text)
        """
        # Generate session ID if needed
        if session_id is None:
            session_id = str(uuid.uuid4())
            debug_component('wrapper', 'NEW_SESSION_GENERATED', {'session_id': session_id[:8] + '...'})

        # Generate request ID for tracking
        request_id = f"aione_{session_id[:8]}_{uuid.uuid4().hex[:8]}"
        
        # Debug request start
        debug_request_start(request_id, question, session_id)
        
        try:
            
            # Get or create session
            session = self._get_or_create_session(session_id)
            debug_session_update(session_id, 'RETRIEVED', {
                'requests_count': session.stats['requests_count'],
                'created_at': session.created_at.isoformat()
            })
            
            # Determine system prompt - only send once per session
            if not session.system_prompt_sent:
                final_system_prompt = system_prompt or self.config.system_prompt or self._get_default_system_prompt()
                session.system_prompt_sent = True  # Mark as sent
            else:
                final_system_prompt = None  # Don't send system prompt again
            debug_component('wrapper', 'SYSTEM_PROMPT', {
                'custom_provided': system_prompt is not None,
                'config_provided': self.config.system_prompt is not None,
                'prompt_length': len(final_system_prompt) if final_system_prompt is not None else 0
            })
            
            # Create provider
            provider = self._create_provider()
            debug_component('wrapper', 'PROVIDER_CREATED', {
                'provider_type': type(provider).__name__,
                'model': getattr(provider, 'model', 'unknown')
            })
            
            # Initialize executor with provider for this request
            # Note: For now we create executor per request with provider
            # TODO: Consider caching executors with different providers
            executor = Executor(
                tool_registry=self.tool_registry,
                llm_provider=provider,
                max_tool_iterations=self.config.max_tool_iterations
            )
            debug_component('wrapper', 'EXECUTOR_CREATED', {
                'max_iterations': self.config.max_tool_iterations,
                'tools_enabled': self.tool_registry is not None
            })
            
            # Execute request
            result: ExecutionResult = executor.execute_request(
                user_input=question,
                session=session,
                system_prompt=final_system_prompt,
                request_id=request_id
            )
            
            # Log results
            logger.info(
                f"AI-ONE request completed: {result.status.value} "
                f"(tools: {len(result.tool_results) if result.tool_results else 0})"
            )
            
            if result.tool_results:
                logger.debug(f"Executed {len(result.tool_results)} tools")
                debug_component('wrapper', 'TOOLS_EXECUTED', {
                    'tool_count': len(result.tool_results),
                    'tool_names': [tr.tool for tr in result.tool_results] if result.tool_results else []
                })
            
            # Debug request completion
            debug_request_end(request_id, result.status.value, result.execution_time_ms)
            
            # Return response in original format
            return session_id, result.response
            
        except Exception as e:
            logger.error(f"AI-ONE request failed: {e}", exc_info=True)
            debug_component('wrapper', 'REQUEST_FAILED', {
                'request_id': request_id,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
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
        """Get default system prompt for AI-ONE with tool integration from instructions."""
        from .templates import instruction_loader
        
        # Load from instruction with detailed tool descriptions
        return instruction_loader.get_system_prompt(tool_registry=self.tool_registry)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: Session to query
            
        Returns:
            Session info dictionary or None if session not found
        """
        if session_id not in self._sessions:
            return None
            
        session = self._sessions[session_id]
        return {
            'session_id': session.id,
            'created_at': session.created_at.isoformat(),
            'last_activity': session.last_activity.isoformat() if session.last_activity else None,
            'metadata': session.metadata,
            'stats': session.stats
        }
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions.
        
        Returns:
            List of session info dictionaries
        """
        return [
            self.get_session_info(session_id) 
            for session_id in self._sessions.keys()
        ]
    
    def cleanup_session(self, session_id: str) -> bool:
        """
        Remove a session and clean up resources.
        
        Args:
            session_id: Session to remove
            
        Returns:
            True if session was removed, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session cleaned up: {session_id}")
            return True
        return False
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics.
        
        Returns:
            Statistics dictionary with session, tool, and provider metrics
        """
        total_sessions = len(self._sessions)
        total_requests = sum(session.stats.get('requests_count', 0) for session in self._sessions.values())
        
        return {
            'sessions': {
                'total_count': total_sessions,
                'active_count': total_sessions,
                'total_requests': total_requests
            },
            'executor': {},  # TODO: Consider tracking executor stats across requests
            'tools': {
                'available_count': len(self.tool_registry.list_tools()) if self.tool_registry else 0,
                'registry_enabled': self.config.enable_tools
            }
        }
    
    def refresh_system_prompt(self, session_id: str) -> bool:
        """
        Manually trigger system prompt refresh for a session.
        
        Args:
            session_id: Session to refresh
            
        Returns:
            True if refresh was triggered, False if session not found
        """
        if session_id not in self._sessions:
            return False
        
        try:
            # For now, just reset the session context
            # In the future, this could trigger LLM context refresh
            session = self._sessions[session_id]
            session.metadata['last_prompt_refresh'] = session.last_activity.isoformat() if session.last_activity else None
            logger.info(f"System prompt refresh triggered for session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh system prompt for {session_id}: {e}")
            return False


# Global wrapper instance for backward compatibility
_aione_wrapper = None


def get_aione_wrapper() -> AiOneWrapper:
    """Get the global AI-ONE wrapper instance."""
    global _aione_wrapper
    if _aione_wrapper is None:
        _aione_wrapper = AiOneWrapper()
    return _aione_wrapper


def ask_question(question: str, session_id: Optional[str] = None) -> tuple[str, str]:
    """
    Ask a question using the default AI-ONE wrapper.
    
    This function maintains the exact API of the original interface
    while using the modern architecture internally.
    
    Args:
        question: User question
        session_id: Optional session ID
        
    Returns:
        Tuple of (session_id, response)
    """
    wrapper = get_aione_wrapper()
    return wrapper.ask_question(question, session_id)


def configure_aione(config: AiOneConfig):
    """
    Configure the global AI-ONE wrapper.
    
    Args:
        config: New configuration to apply
    """
    global _aione_wrapper
    _aione_wrapper = AiOneWrapper(config)
    logger.info("AI-ONE wrapper reconfigured")


def get_aione_stats() -> Dict[str, Any]:
    """Get usage statistics from the global wrapper."""
    wrapper = get_aione_wrapper()
    return wrapper.get_usage_stats()


# For testing and development
if __name__ == "__main__":
    print("Testing modern AI-ONE wrapper...")
    
    wrapper = AiOneWrapper()
    session_id, response = wrapper.ask_question("Hello, can you help me?")
    print(f"Session: {session_id}")
    print(f"Response: {response}")
    
    stats = get_aione_stats()
    print(f"Stats: {stats}")