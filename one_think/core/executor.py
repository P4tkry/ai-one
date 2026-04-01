"""
Execution Engine for AI-ONE.

The Executor is the heart of the system - it orchestrates conversation flow,
parses LLM responses, dispatches tools, and manages the complete request-response cycle.

Architecture:
    User Input → Session → Executor → LLM Provider → Response Processing → Tool Dispatch → Results
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from one_think.core.session import Session
from one_think.core.message import (
    Message, SystemMessage, UserMessage, AssistantMessage, 
    ToolResultMessage, SystemRefreshMessage, MessageType
)
from one_think.core.protocol import (
    Protocol, ProtocolParseResult, ToolRequest as ProtocolToolRequest, 
    LLMResponse, SystemRefreshRequest, ToolCall, ResponseType
)
from one_think.tools.registry import ToolRegistry, tool_registry as global_registry
from one_think.tools.base import ToolResponse


logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of execution operation."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    TOOL_ERROR = "tool_error"
    PARSE_ERROR = "parse_error"


@dataclass
class ToolRequest:
    """Tool request for executor compatibility."""
    tool_name: str
    params: Dict[str, Any]
    id: Optional[str] = None


@dataclass  
class ExecutionResult:
    """Result of executing a user request."""
    status: ExecutionStatus
    response: str
    tool_results: List[ToolResponse] = None
    errors: List[str] = None
    execution_time_ms: float = 0
    session_id: str = None
    request_id: str = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = asdict(self)
        result['status'] = self.status.value
        if self.tool_results:
            result['tool_results'] = [tr.to_dict() for tr in self.tool_results]
        return result


class ExecutorError(Exception):
    """Base exception for executor errors."""
    pass


class ToolDispatchError(ExecutorError):
    """Raised when tool dispatching fails."""
    pass


class LLMProviderError(ExecutorError):
    """Raised when LLM provider fails."""
    pass


class Executor:
    """
    Main execution engine for AI-ONE conversations.
    
    The Executor orchestrates the complete conversation flow:
    1. Receives user input and adds to session
    2. Sends conversation to LLM provider
    3. Parses LLM response (text, tool requests, system refresh)
    4. Dispatches tools using Tool Registry
    5. Processes results and continues conversation
    6. Returns final response to user
    
    Features:
    - Tool request parsing and dispatching
    - Session state management
    - Error handling and recovery
    - Structured logging and metrics
    - Provider abstraction (ready for different LLMs)
    """
    
    def __init__(
        self, 
        tool_registry: Optional[ToolRegistry] = None,
        protocol: Optional[Protocol] = None,
        llm_provider: Optional[Union[Callable, 'LLMProvider']] = None,
        max_tool_iterations: int = 5
    ):
        """
        Initialize executor.
        
        Args:
            tool_registry: Registry for tool discovery and dispatch
            protocol: Protocol parser for LLM responses  
            llm_provider: Function OR Provider instance to send messages to LLM
            max_tool_iterations: Maximum number of tool call iterations per request
        """
        self.tool_registry = tool_registry if tool_registry is not None else global_registry
        self.protocol = protocol or Protocol()
        self.llm_provider = llm_provider
        self.max_tool_iterations = max_tool_iterations
        
        # Ensure tool registry is initialized
        if self.tool_registry and not self.tool_registry._discovery_performed:
            tool_count = self.tool_registry.discover_tools()
            logger.info(f"Executor initialized with {tool_count} tools")
    
    def execute_request(
        self, 
        user_input: str, 
        session: Session,
        system_prompt: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a complete user request.
        
        This is the main entry point that handles:
        1. Adding user message to session
        2. LLM communication loop  
        3. Tool dispatching
        4. Response generation
        
        Args:
            user_input: The user's message/request
            session: Session to execute in
            system_prompt: Optional system prompt (if first message)
            request_id: Optional request correlation ID
            
        Returns:
            ExecutionResult with response and metadata
        """
        start_time = datetime.now()
        execution_id = request_id or f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        logger.info(f"Executing request {execution_id} in session {session.id}")
        
        try:
            # Add system prompt if provided (usually first message)
            if system_prompt:
                system_msg = SystemMessage(content=system_prompt)
                session.add_message(system_msg)
                logger.debug(f"Added system prompt ({len(system_prompt)} chars)")
            
            # Add user message to session
            user_msg = UserMessage(content=user_input)
            session.add_message(user_msg)
            logger.debug(f"Added user message: {user_input[:100]}...")
            
            # Execute the conversation loop
            response, tool_results, errors = self._execute_conversation_loop(session, execution_id)
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Determine status
            if errors:
                status = ExecutionStatus.TOOL_ERROR if tool_results else ExecutionStatus.ERROR
            else:
                status = ExecutionStatus.SUCCESS
            
            result = ExecutionResult(
                status=status,
                response=response,
                tool_results=tool_results,
                errors=errors,
                execution_time_ms=execution_time,
                session_id=session.id,
                request_id=execution_id
            )
            
            logger.info(f"Request {execution_id} completed: {status.value} in {execution_time:.1f}ms")
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"Execution failed: {str(e)}"
            logger.error(f"Request {execution_id} failed: {error_msg}", exc_info=True)
            
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                response=error_msg,
                errors=[error_msg],
                execution_time_ms=execution_time,
                session_id=session.id,
                request_id=execution_id
            )
    
    def _execute_conversation_loop(
        self, 
        session: Session, 
        execution_id: str
    ) -> tuple[str, List[ToolResponse], List[str]]:
        """
        Execute the main conversation loop with tool iterations.
        
        This handles the back-and-forth between LLM and tools:
        1. Send conversation to LLM
        2. Parse response (text, tool requests, system refresh)
        3. Dispatch any tool requests  
        4. Add results to session
        5. Repeat until LLM returns text response or max iterations
        
        Returns:
            (final_response, tool_results, errors)
        """
        tool_results = []
        errors = []
        iteration = 0
        
        while iteration < self.max_tool_iterations:
            iteration += 1
            logger.debug(f"Conversation loop iteration {iteration}")
            
            # Send conversation to LLM
            try:
                llm_response_text = self._call_llm_provider(session)
                logger.debug(f"LLM response ({len(llm_response_text)} chars): {llm_response_text[:200]}...")
            except Exception as e:
                error = f"LLM provider error: {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                return "I encountered an error communicating with the LLM.", tool_results, errors
            
            # Add assistant response to session
            assistant_msg = AssistantMessage(content=llm_response_text)
            session.add_message(assistant_msg)
            
            # Parse the LLM response
            try:
                parse_result = self.protocol.parse(llm_response_text)
                logger.debug(f"Parsed response type: {parse_result.type}")
            except Exception as e:
                error = f"Protocol parse error: {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                # Return raw text if we can't parse it
                return llm_response_text, tool_results, errors
            
            # Handle different response types
            if parse_result.type == ResponseType.TOOL_REQUEST:
                # Convert protocol tool calls to executor tool requests
                tool_requests = [
                    ToolRequest(tool_name=tc.tool_name, params=tc.params, id=tc.id)
                    for tc in parse_result.tools
                ]
                
                # Dispatch tools and continue loop
                iteration_tool_results, iteration_errors = self._dispatch_tools(
                    tool_requests, 
                    session, 
                    execution_id
                )
                tool_results.extend(iteration_tool_results)
                errors.extend(iteration_errors)
                
            elif parse_result.type == ResponseType.SYSTEM_REFRESH_REQUEST:
                # Handle system refresh request
                self._handle_system_refresh(parse_result, session)
                
            elif parse_result.type == ResponseType.RESPONSE:
                # Text response - we're done
                return parse_result.content, tool_results, errors
                
            else:
                # Unknown response type - treat as text
                logger.warning(f"Unknown response type: {parse_result.type}")
                return llm_response_text, tool_results, errors
        
        # Max iterations reached
        warning = f"Maximum tool iterations ({self.max_tool_iterations}) reached"
        logger.warning(warning)
        errors.append(warning)
        return "I've reached the maximum number of tool iterations for this request.", tool_results, errors
    
    def _call_llm_provider(self, session: Session) -> str:
        """
        Send conversation to LLM provider.
        
        Args:
            session: Session with conversation history
            
        Returns:
            Raw LLM response text
            
        Raises:
            LLMProviderError: If provider call fails
        """
        if not self.llm_provider:
            raise LLMProviderError("No LLM provider configured")
        
        try:
            # Convert session to provider format
            messages = self._format_messages_for_provider(session)
            
            # Check if provider is a Provider instance or function
            from one_think.providers import LLMProvider as BaseProvider
            if isinstance(self.llm_provider, BaseProvider):
                # Use Provider interface
                provider_messages = self.llm_provider.format_messages(messages)
                response = self.llm_provider.send_messages(provider_messages)
                return response.content
            else:
                # Use legacy function interface
                response = self.llm_provider(messages)
                
                if not response or not isinstance(response, str):
                    raise LLMProviderError(f"Invalid provider response: {type(response)}")
                    
                return response
            
        except Exception as e:
            raise LLMProviderError(f"Provider call failed: {str(e)}") from e
    
    def _format_messages_for_provider(self, session: Session) -> List[Dict]:
        """
        Format session messages for LLM provider.
        
        Different providers expect different formats. This provides a standard
        OpenAI-style format that can be adapted by provider wrappers.
        
        Args:
            session: Session to format
            
        Returns:
            List of message dicts in OpenAI format
        """
        formatted_messages = []
        
        for message in session.history:
            if isinstance(message, SystemMessage):
                formatted_messages.append({
                    "role": "system",
                    "content": message.content
                })
            elif isinstance(message, UserMessage):
                formatted_messages.append({
                    "role": "user", 
                    "content": message.content
                })
            elif isinstance(message, AssistantMessage):
                formatted_messages.append({
                    "role": "assistant",
                    "content": message.content
                })
            elif isinstance(message, ToolResultMessage):
                # Format tool result for provider - the result is in content as JSON
                try:
                    tool_data = json.loads(message.content)
                    tool_result_text = f"Tool '{message.tool_name}' result:\n{json.dumps(tool_data.get('result'), indent=2)}"
                    if tool_data.get('error'):
                        tool_result_text += f"\nError: {tool_data['error']}"
                except (json.JSONDecodeError, Exception):
                    # Fallback to raw content if JSON parsing fails
                    tool_result_text = f"Tool '{message.tool_name}' result:\n{message.content}"
                
                formatted_messages.append({
                    "role": "system",  # Or "user" depending on provider
                    "content": tool_result_text
                })
            elif isinstance(message, SystemRefreshMessage):
                formatted_messages.append({
                    "role": "system",
                    "content": message.content
                })
        
        return formatted_messages
    
    def _dispatch_tools(
        self, 
        tool_requests: List[ToolRequest], 
        session: Session, 
        execution_id: str
    ) -> tuple[List[ToolResponse], List[str]]:
        """
        Dispatch multiple tool requests.
        
        Args:
            tool_requests: List of tool requests to execute
            session: Session to add results to
            execution_id: Execution ID for correlation
            
        Returns:
            (tool_results, errors)
        """
        tool_results = []
        errors = []
        
        logger.info(f"Dispatching {len(tool_requests)} tools")
        
        for i, tool_request in enumerate(tool_requests):
            request_id = f"{execution_id}_tool_{i+1}"
            logger.debug(f"Dispatching tool: {tool_request.tool_name} (ID: {request_id})")
            
            try:
                # Execute the tool
                tool_result = self._execute_single_tool(tool_request, request_id)
                tool_results.append(tool_result)
                
                # Add result to session
                tool_msg = ToolResultMessage(
                    content=json.dumps({
                        "tool": tool_result.tool,
                        "status": tool_result.status,
                        "result": tool_result.result,
                        "error": tool_result.error,
                        "execution_time_ms": tool_result.execution_time_ms
                    }),
                    tool_name=tool_request.tool_name,
                    status=tool_result.status,
                    request_id=request_id,
                    execution_time_ms=tool_result.execution_time_ms
                )
                session.add_message(tool_msg)
                
                logger.debug(f"Tool {tool_request.tool_name} executed: {tool_result.status}")
                
            except Exception as e:
                error = f"Tool dispatch error for '{tool_request.tool_name}': {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                
                # Add error result to session
                error_msg = ToolResultMessage(
                    content=json.dumps({
                        "tool": tool_request.tool_name,
                        "status": "error",
                        "result": None,
                        "error": error,
                        "execution_time_ms": None
                    }),
                    tool_name=tool_request.tool_name,
                    status="error",
                    request_id=request_id
                )
                session.add_message(error_msg)
        
        return tool_results, errors
    
    def _execute_single_tool(self, tool_request: ToolRequest, request_id: str) -> ToolResponse:
        """
        Execute a single tool request.
        
        Args:
            tool_request: Tool request to execute
            request_id: Request ID for correlation
            
        Returns:
            ToolResponse with result or error
            
        Raises:
            ToolDispatchError: If tool execution fails
        """
        try:
            # Create tool instance
            tool_instance = self.tool_registry.create_tool_instance(tool_request.tool_name)
            
            # Execute tool with parameters
            result = tool_instance.execute_json(
                **tool_request.params,
                request_id=request_id
            )
            
            return result
            
        except Exception as e:
            # Create error response
            error_response = ToolResponse(
                status="error",
                result=None,
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                },
                tool=tool_request.tool_name,
                request_id=request_id,
                execution_time_ms=0
            )
            
            return error_response
    
    def _handle_system_refresh(self, refresh_request: SystemRefreshRequest, session: Session):
        """
        Handle system prompt refresh request.
        
        Rebuilds system prompt with:
        - Core guidelines and instructions
        - Available tools summary  
        - Session context summary
        - Current timestamp and environment
        
        Args:
            refresh_request: System refresh request details
            session: Session to add refresh message to
        """
        reason = refresh_request.reason or "System refresh requested"
        logger.info(f"System refresh requested: {reason}")
        
        # Build comprehensive system prompt
        system_content = self._build_refreshed_system_prompt(session, reason)
        
        # Add system refresh message to session
        refresh_msg = SystemRefreshMessage(
            content=system_content,
            reason=reason
        )
        session.add_message(refresh_msg)
        
        logger.debug(f"System prompt refreshed with {len(system_content)} characters")
    
    def _build_refreshed_system_prompt(self, session: Session, reason: str) -> str:
        """
        Build a comprehensive refreshed system prompt.
        
        Args:
            session: Current session for context
            reason: Reason for refresh
            
        Returns:
            Complete system prompt content
        """
        from datetime import datetime, timezone
        
        # Get message count using correct Session API
        all_messages = session.get_history()
        message_count = len(all_messages)
        
        # Core system prompt components
        system_parts = [
            "# AI-ONE System Prompt (Refreshed)",
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"Refresh reason: {reason}",
            f"Session ID: {session.id}",
            f"Message count: {message_count}",
            "",
            "## Core Instructions",
            "You are an AI assistant integrated with AI-ONE tool system.",
            "You can request tools in JSON format and provide natural language responses.",
            "",
            "## Available Response Types",
            "1. Natural response: {\"type\": \"response\", \"content\": \"your answer\"}",
            "2. Tool request: {\"type\": \"tool_request\", \"tools\": [{\"tool_name\": \"...\", \"params\": {...}, \"id\": \"req_1\"}]}",
            "3. System refresh: {\"type\": \"system_refresh_request\", \"reason\": \"why\"}",
            "",
            "## Guidelines",
            "- Use tools when needed to gather information or perform actions",
            "- Provide clear, helpful responses to user questions",
            "- Be concise but thorough in explanations",
            "- Handle errors gracefully and inform the user",
            "",
        ]
        
        # Add available tools summary
        if hasattr(self, 'tool_registry') and self.tool_registry:
            try:
                available_tools = list(self.tool_registry.list_tools())
                system_parts.extend([
                    f"## Available Tools ({len(available_tools)} total)",
                    "Tools you can request:",
                ])
                
                # Group tools by category for better organization
                tool_categories = {}
                for tool_name in available_tools:
                    try:
                        metadata = self.tool_registry.get_tool_metadata(tool_name)
                        category = getattr(metadata, 'category', 'General')
                        if category not in tool_categories:
                            tool_categories[category] = []
                        tool_categories[category].append(tool_name)
                    except Exception:
                        # Fallback if metadata unavailable
                        if 'General' not in tool_categories:
                            tool_categories['General'] = []
                        tool_categories['General'].append(tool_name)
                
                # Add tools by category
                for category, tools in sorted(tool_categories.items()):
                    system_parts.append(f"### {category}")
                    for tool_name in sorted(tools):
                        system_parts.append(f"- {tool_name}")
                    system_parts.append("")
                    
            except Exception as e:
                system_parts.extend([
                    "## Available Tools",
                    f"Error loading tool registry: {str(e)}",
                    "Use tools cautiously and check for errors.",
                    "",
                ])
        
        # Add session context summary if session has history
        if message_count > 1:
            # Count message types for context
            msg_counts = {}
            recent_messages = []
            
            # Get recent messages (last 10)
            recent_msg_list = all_messages[-10:] if len(all_messages) > 10 else all_messages
            
            for msg in recent_msg_list:
                msg_type = msg.type.value if hasattr(msg.type, 'value') else str(msg.type)
                msg_counts[msg_type] = msg_counts.get(msg_type, 0) + 1
                recent_messages.append(f"- {msg_type}: {msg.content[:50]}...")
            
            system_parts.extend([
                "## Session Context",
                f"Recent conversation has {message_count} messages:",
                f"Types: {', '.join(f'{k}({v})' for k, v in msg_counts.items())}",
                "",
                "Recent messages:",
            ])
            system_parts.extend(recent_messages[-5:])  # Last 5 messages
            system_parts.append("")
        
        # Add refresh-specific instructions
        system_parts.extend([
            "## Refresh Instructions",
            "This is a system prompt refresh. You should:",
            "- Continue the conversation naturally",
            "- Use updated tool information if needed",
            "- Maintain context from previous messages",
            "- Apply any new guidelines or capabilities",
            "",
            "You may now proceed with the conversation."
        ])
        
        return "\n".join(system_parts)
    
    def set_llm_provider(self, provider: Union[Callable, 'LLMProvider']):
        """Set the LLM provider function or Provider instance."""
        self.llm_provider = provider
        provider_type = "Provider instance" if hasattr(provider, 'send_messages') else "function"
        logger.info(f"LLM provider configured: {provider_type}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get executor metrics and statistics."""
        return {
            "tool_count": len(self.tool_registry.list_tools()),
            "max_tool_iterations": self.max_tool_iterations,
            "has_llm_provider": self.llm_provider is not None,
            "protocol_version": "1.0.0"
        }