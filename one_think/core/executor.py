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
    LLMResponse, SystemRefreshRequest, ToolCall
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
        llm_provider: Optional[Callable] = None,
        max_tool_iterations: int = 5
    ):
        """
        Initialize executor.
        
        Args:
            tool_registry: Registry for tool discovery and dispatch
            protocol: Protocol parser for LLM responses  
            llm_provider: Function to send messages to LLM (provider abstraction)
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
                logger.debug(f"Parsed response type: {parse_result.response_type}")
            except Exception as e:
                error = f"Protocol parse error: {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                # Return raw text if we can't parse it
                return llm_response_text, tool_results, errors
            
            # Handle different response types
            if parse_result.response_type == "tool_request":
                # Convert protocol tool calls to executor tool requests
                tool_requests = [
                    ToolRequest(tool_name=tc.tool_name, params=tc.params, id=tc.id)
                    for tc in parse_result.tool_request.tools
                ]
                
                # Dispatch tools and continue loop
                iteration_tool_results, iteration_errors = self._dispatch_tools(
                    tool_requests, 
                    session, 
                    execution_id
                )
                tool_results.extend(iteration_tool_results)
                errors.extend(iteration_errors)
                
            elif parse_result.response_type == "system_refresh_request":
                # Handle system refresh request
                self._handle_system_refresh(parse_result.system_refresh_request, session)
                
            elif parse_result.response_type == "response":
                # Text response - we're done
                return parse_result.response.content, tool_results, errors
                
            else:
                # Unknown response type - treat as text
                logger.warning(f"Unknown response type: {parse_result.response_type}")
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
            
            # Call provider
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
                # Format tool result for provider
                tool_result_text = f"Tool '{message.tool_name}' result:\n{json.dumps(message.result, indent=2)}"
                if message.error:
                    tool_result_text += f"\nError: {message.error}"
                
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
                    tool_name=tool_request.tool_name,
                    result=tool_result.result,
                    error=tool_result.error,
                    status=tool_result.status,
                    execution_time_ms=tool_result.execution_time_ms,
                    request_id=request_id
                )
                session.add_message(tool_msg)
                
                logger.debug(f"Tool {tool_request.tool_name} executed: {tool_result.status}")
                
            except Exception as e:
                error = f"Tool dispatch error for '{tool_request.tool_name}': {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                
                # Add error result to session
                error_msg = ToolResultMessage(
                    tool_name=tool_request.tool_name,
                    result=None,
                    error=error,
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
        
        Args:
            refresh_request: System refresh request details
            session: Session to add refresh message to
        """
        logger.info(f"System refresh requested: {refresh_request.reason}")
        
        # This is a placeholder - in a real implementation, you'd:
        # 1. Load fresh system prompt from templates
        # 2. Apply any dynamic content
        # 3. Add to session
        
        refresh_content = "System prompt refreshed due to: " + refresh_request.reason
        refresh_msg = SystemRefreshMessage(content=refresh_content)
        session.add_message(refresh_msg)
    
    def set_llm_provider(self, provider: Callable):
        """Set the LLM provider function."""
        self.llm_provider = provider
        logger.info("LLM provider configured")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get executor metrics and statistics."""
        return {
            "tool_count": len(self.tool_registry.list_tools()),
            "max_tool_iterations": self.max_tool_iterations,
            "has_llm_provider": self.llm_provider is not None,
            "protocol_version": "1.0.0"
        }