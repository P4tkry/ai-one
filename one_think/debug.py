"""
Debug logging configuration for AI-ONE.

When DEBUG=1 environment variable is set, enables comprehensive debug logging
for all components: sessions, tools, providers, protocol parsing, etc.
"""

import os
import logging
import sys
from typing import Dict, Any
from datetime import datetime

# Try to import rich for beautiful logging
try:
    from rich.logging import RichHandler
    from rich.console import Console
    from rich.highlighter import ReprHighlighter
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class ColoredDebugLogger:
    """Enhanced debug logger for AI-ONE with beautiful colored output."""
    
    def __init__(self):
        self.debug_enabled = os.getenv('DEBUG', '0') == '1'
        self.logger = logging.getLogger('ai_one_debug')
        
        if self.debug_enabled:
            self._setup_debug_logging()
    
    def _setup_debug_logging(self):
        """Configure detailed debug logging with colors."""
        # Set logging level to DEBUG for all AI-ONE components
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        if HAS_RICH:
            # Rich console handler with beautiful formatting
            console = Console(stderr=True, force_terminal=True)
            rich_handler = RichHandler(
                console=console,
                show_time=True,
                show_level=True,
                show_path=True,
                highlighter=ReprHighlighter(),
                rich_tracebacks=True,
                tracebacks_show_locals=True
            )
            rich_handler.setLevel(logging.DEBUG)
            
            # Add handler to root logger
            if not any(isinstance(h, RichHandler) for h in root_logger.handlers):
                root_logger.addHandler(rich_handler)
                
        else:
            # Fallback to standard colored formatter
            formatter = logging.Formatter(
                '%(asctime)s.%(msecs)03d | %(levelname)8s | %(name)20s | %(funcName)15s:%(lineno)03d | %(message)s',
                datefmt='%H:%M:%S'
            )
            
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            
            # Add handler to root logger
            if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
                root_logger.addHandler(console_handler)
        
        # Set DEBUG level for all AI-ONE components
        for component in [
            'one_think',
            'one_think.core',
            'one_think.core.executor',
            'one_think.core.session', 
            'one_think.core.protocol',
            'one_think.core.message',
            'one_think.tools',
            'one_think.tools.registry',
            'one_think.providers',
            'one_think.aione_wrapper',
            'ai_one_debug'
        ]:
            logging.getLogger(component).setLevel(logging.DEBUG)
    
    def debug_component(self, component: str, action: str, data: Dict[str, Any] = None):
        """Log detailed component debug information."""
        if not self.debug_enabled:
            return
            
        logger = logging.getLogger(f'ai_one_debug.{component}')
        
        message = f"🔍 {action}"
        if data:
            message += f" | Data: {data}"
        
        logger.debug(message)
    
    def debug_request_start(self, request_id: str, user_input: str, session_id: str):
        """Log request start with full details."""
        if not self.debug_enabled:
            return
        
        self.debug_component('request', 'START', {
            'request_id': request_id,
            'user_input': user_input,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        })
    
    def debug_request_end(self, request_id: str, status: str, execution_time_ms: float):
        """Log request completion with timing."""
        if not self.debug_enabled:
            return
            
        self.debug_component('request', 'END', {
            'request_id': request_id,
            'status': status,
            'execution_time_ms': execution_time_ms,
            'timestamp': datetime.now().isoformat()
        })
    
    def debug_llm_call(self, provider: str, messages: list, request_id: str):
        """Log LLM provider calls with full message context."""
        if not self.debug_enabled:
            return
        
        # Handle both dict and object messages
        formatted_messages = []
        for msg in messages:  # All messages - no truncation
            if hasattr(msg, '__dict__'):
                # Object with attributes (Message or ProviderMessage)
                # Try 'type' first (Message), then 'role' (ProviderMessage)
                msg_type = getattr(msg, 'type', getattr(msg, 'role', 'unknown'))
                formatted_messages.append({
                    'type': msg_type,
                    'content': str(getattr(msg, 'content', ''))
                })
            elif isinstance(msg, dict):
                # Dictionary
                formatted_messages.append({
                    'author': msg.get('author', msg.get('role', 'unknown')),
                    'content': msg.get('message', msg.get('content', ''))
                })
            else:
                # String or other
                formatted_messages.append({
                    'type': 'raw',
                    'content': str(msg)
                })
        
        self.debug_component('llm', 'CALL', {
            'provider': provider,
            'request_id': request_id,
            'message_count': len(messages),
            'messages': formatted_messages
        })
    
    def debug_llm_response(self, provider: str, response: str, request_id: str):
        """Log LLM responses."""
        if not self.debug_enabled:
            return
        
        self.debug_component('llm', 'RESPONSE', {
            'provider': provider,
            'request_id': request_id,
            'response_length': len(response),
            'response_preview': response
        })
    
    def debug_tool_execution(self, tool_name: str, params: Dict[str, Any], request_id: str):
        """Log tool execution attempts."""
        if not self.debug_enabled:
            return
            
        self.debug_component('tool', 'EXECUTE', {
            'tool_name': tool_name,
            'request_id': request_id,
            'params_keys': list(params.keys()) if params else [],
            'param_count': len(params) if params else 0
        })
    
    def debug_tool_result(self, tool_name: str, status: str, result_size: int, request_id: str):
        """Log tool execution results."""
        if not self.debug_enabled:
            return
            
        self.debug_component('tool', 'RESULT', {
            'tool_name': tool_name,
            'request_id': request_id,
            'status': status,
            'result_size_bytes': result_size
        })
    
    def debug_session_update(self, session_id: str, action: str, data: Dict[str, Any] = None):
        """Log session state changes."""
        if not self.debug_enabled:
            return
            
        self.debug_component('session', action, {
            'session_id': session_id[:8] + '...',  # Truncate for privacy
            'data': data
        })
    
    def debug_protocol_parse(self, raw_response: str, parsed_type: str, request_id: str):
        """Log protocol parsing details."""
        if not self.debug_enabled:
            return
            
        self.debug_component('protocol', 'PARSE', {
            'request_id': request_id,
            'raw_length': len(raw_response),
            'parsed_type': parsed_type,
            'raw_preview': raw_response
        })


# Global debug logger instance
debug_logger = ColoredDebugLogger()


def debug_component(component: str, action: str, data: Dict[str, Any] = None):
    """Convenience function for component debug logging."""
    debug_logger.debug_component(component, action, data)


def debug_request_start(request_id: str, user_input: str, session_id: str):
    """Convenience function for request start logging."""
    debug_logger.debug_request_start(request_id, user_input, session_id)


def debug_request_end(request_id: str, status: str, execution_time_ms: float):
    """Convenience function for request end logging.""" 
    debug_logger.debug_request_end(request_id, status, execution_time_ms)


def debug_llm_call(provider: str, messages: list, request_id: str):
    """Convenience function for LLM call logging."""
    debug_logger.debug_llm_call(provider, messages, request_id)


def debug_llm_response(provider: str, response: str, request_id: str):
    """Convenience function for LLM response logging."""
    debug_logger.debug_llm_response(provider, response, request_id)


def debug_tool_execution(tool_name: str, params: Dict[str, Any], request_id: str):
    """Convenience function for tool execution logging."""
    debug_logger.debug_tool_execution(tool_name, params, request_id)


def debug_tool_result(tool_name: str, status: str, result_size: int, request_id: str):
    """Convenience function for tool result logging."""
    debug_logger.debug_tool_result(tool_name, status, result_size, request_id)


def debug_session_update(session_id: str, action: str, data: Dict[str, Any] = None):
    """Convenience function for session update logging."""
    debug_logger.debug_session_update(session_id, action, data)


def debug_protocol_parse(raw_response: str, parsed_type: str, request_id: str):
    """Convenience function for protocol parse logging."""
    debug_logger.debug_protocol_parse(raw_response, parsed_type, request_id)